import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import socketio
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydub.utils import which as ffmpeg_which

from .facebook import send_facebook_text
from .repositories.knowledge_store import KnowledgeStore
from .repositories.session_store import SessionStore
from .services.assistant_service import AssistantService
from .services.llm_gateway import LLMGateway
from .services.stt_service import transcribe_upload
from .services.tts_service import stream_tts
from .settings import Settings, load_settings


def _hash_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def _client_identifier(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _verify_facebook_signature(app_secret: str, payload: bytes, signature_header: str | None) -> bool:
    if not app_secret:
        return True
    if not signature_header or "=" not in signature_header:
        return False
    algorithm, received_digest = signature_header.split("=", 1)
    if algorithm.lower() != "sha256":
        return False
    expected = hmac.new(app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_digest)


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = max(1, int(limit))
        self.window = max(1, int(window_seconds))
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = int(self.window - (now - bucket[0])) + 1
                return False, max(1, retry_after)
            bucket.append(now)
            return True, 0


class BackendRuntime:
    def __init__(self, settings: Settings, sio: socketio.AsyncServer) -> None:
        self.settings = settings
        self.sio = sio
        self.session_store = SessionStore(settings.sessions_db_path)
        self.knowledge_store = KnowledgeStore(settings.docs_folder)
        self.gateway = LLMGateway(settings)
        self.assistant = AssistantService(self.session_store, self.knowledge_store, self.gateway)
        self._audit_lock = threading.Lock()
        self._bot_lock = threading.Lock()
        self._bot_enabled: dict[str, bool] = {}

        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path = settings.logs_dir / "user_audit.log"

    def reload_indexes(self) -> None:
        self.knowledge_store.reload()

    async def shutdown(self) -> None:
        await self.gateway.close()

    def get_bot_enabled(self, session_id: str) -> bool:
        with self._bot_lock:
            return self._bot_enabled.get(session_id, True)

    def set_bot_enabled(self, session_id: str, enabled: bool) -> None:
        with self._bot_lock:
            self._bot_enabled[session_id] = enabled

    def set_all_bot_enabled(self, enabled: bool) -> int:
        sessions = self.session_store.list_sessions(limit=5000)
        with self._bot_lock:
            for item in sessions:
                self._bot_enabled[item["id"]] = enabled
        return len(sessions)

    def write_audit(
        self,
        user_id: str,
        platform: str,
        user_input: str,
        output: str,
        latency: float,
        provider: str = "none",
        model: str = "none",
    ) -> None:
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "anon_id": _hash_id(user_id),
            "platform": platform,
            "input": (user_input or "")[:500],
            "output": (output or "")[:500],
            "latency": round(latency, 3),
            "provider": provider,
            "model": model,
        }
        try:
            with self._audit_lock:
                with self.audit_log_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            logging.getLogger("BackendCore").exception("Failed to write audit log")

    def read_recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.audit_log_path.exists():
            return []
        try:
            with self._audit_lock:
                lines = self.audit_log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            parsed: list[dict[str, Any]] = []
            for line in lines[-limit:]:
                try:
                    parsed.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return parsed
        except Exception:
            logging.getLogger("BackendCore").exception("Failed to read audit log")
            return []

    def readiness_report(self) -> dict[str, Any]:
        checks: dict[str, dict[str, Any]] = {}

        try:
            with sqlite3.connect(self.settings.sessions_db_path) as conn:
                conn.execute("SELECT 1")
            checks["session_store"] = {"ok": True, "detail": str(self.settings.sessions_db_path)}
        except Exception as exc:
            checks["session_store"] = {"ok": False, "detail": str(exc)}

        chunk_count = len(self.knowledge_store._chunks)
        checks["knowledge_index"] = {"ok": chunk_count > 0, "detail": f"{chunk_count} chunks loaded"}

        providers = self.gateway.available_providers()
        checks["llm_provider"] = {"ok": bool(providers), "detail": providers}

        index_exists = (self.settings.frontend_dir / "index.html").exists()
        checks["frontend_index"] = {"ok": index_exists, "detail": str(self.settings.frontend_dir / "index.html")}

        ffmpeg_path = ffmpeg_which("ffmpeg") or ffmpeg_which("avconv")
        checks["audio_transcoder"] = {
            "ok": bool(ffmpeg_path),
            "detail": ffmpeg_path or "missing ffmpeg/avconv",
        }

        required = ("session_store", "knowledge_index", "llm_provider")
        ok = all(checks[name]["ok"] for name in required)
        return {"ok": ok, "environment": self.settings.environment, "checks": checks}


def create_asgi_app() -> tuple[Any, FastAPI, socketio.AsyncServer, BackendRuntime]:
    settings = load_settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger("BackendCore")

    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=settings.socket_cors)
    app = FastAPI(title="REG-01 Backend", version="4.1.0")

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts or ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins if settings.allowed_origins else ["*"],
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    runtime = BackendRuntime(settings, sio)
    speech_limiter = SlidingWindowRateLimiter(settings.speech_rate_limit, settings.rate_limit_window_seconds)
    webhook_limiter = SlidingWindowRateLimiter(settings.webhook_rate_limit, settings.rate_limit_window_seconds)

    app.state.runtime = runtime
    app.state.settings = settings

    if settings.frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(settings.frontend_dir), html=False), name="static")
    if settings.assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(settings.assets_dir), html=False), name="assets")

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled exception request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                {"detail": "internal_error", "request_id": request_id},
                status_code=500,
            )
        elapsed = time.perf_counter() - start
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        logger.info(
            "request_id=%s client=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            _client_identifier(request),
            request.method,
            request.url.path,
            response.status_code,
            elapsed * 1000,
        )
        return response

    @app.on_event("startup")
    async def _startup() -> None:
        errors, warnings = settings.validate()
        if errors:
            for item in errors:
                logger.error("Startup validation error: %s", item)
            raise RuntimeError("Invalid production configuration")
        for item in warnings:
            logger.warning("Startup validation warning: %s", item)

        logger.info("Starting backend core environment=%s", settings.environment)
        runtime.reload_indexes()
        logger.info("Knowledge chunks loaded=%s", len(runtime.knowledge_store._chunks))
        logger.info("Configured providers=%s", runtime.gateway.available_providers())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        logger.info("Shutting down backend core")
        await runtime.shutdown()

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": "core", "environment": settings.environment}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        report = runtime.readiness_report()
        return JSONResponse(report, status_code=200 if report["ok"] else 503)

    @app.get("/")
    async def serve_index():
        index_path = settings.frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse({"detail": "index.html not found"}, status_code=404)

    @app.get("/admin")
    async def serve_admin():
        admin_path = settings.frontend_dir / "admin.html"
        if admin_path.exists():
            return FileResponse(str(admin_path))
        return JSONResponse({"detail": "admin.html not found"}, status_code=404)

    @app.post("/api/speech")
    async def api_speech(
        request: Request,
        text: str = Form(None),
        session_id: str = Form(None),
        user_name: str = Form(None),
        audio: UploadFile = Form(None),
        x_api_key: str = Header(None, alias="X-API-Key"),
    ):
        allowed, retry_after = speech_limiter.allow(f"speech:{_client_identifier(request)}")
        if not allowed:
            return JSONResponse(
                {"detail": "rate_limited", "retry_after_seconds": retry_after},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        start = time.time()
        sid = (session_id or x_api_key or str(uuid.uuid4())).strip()
        sid = sid[:128] if sid else str(uuid.uuid4())
        uname = (user_name or f"Web User {sid[:6]}").strip()
        platform = "web"

        user_text = (text or "").strip()
        if user_text and len(user_text) > settings.max_text_chars:
            return JSONResponse(
                {"detail": f"text_too_long (max {settings.max_text_chars} chars)"},
                status_code=422,
            )

        if audio and not user_text:
            raw_audio = await audio.read()
            if len(raw_audio) > settings.max_audio_bytes:
                return JSONResponse(
                    {"detail": f"audio_too_large (max {settings.max_audio_bytes} bytes)"},
                    status_code=413,
                )
            user_text = await transcribe_upload(raw_audio, suffix=Path(audio.filename or ".webm").suffix)
            user_text = (user_text or "").strip()

        if not user_text:
            return {"text": "", "motion": "Idle", "session_id": sid}

        await sio.emit(
            "admin_new_message",
            {"platform": platform, "uid": sid, "text": user_text, "user_name": uname},
        )
        await sio.emit("subtitle", {"speaker": "user", "text": user_text})

        if not runtime.get_bot_enabled(sid):
            disabled_text = "Auto-reply is disabled for this session. Please wait for an admin response."
            runtime.session_store.append_message(sid, platform, "user", user_text)
            runtime.session_store.append_message(sid, platform, "model", disabled_text)
            await sio.emit("ai_response", {"text": disabled_text, "motion": "Idle"})
            runtime.write_audit(sid, platform, user_text, disabled_text, time.time() - start)
            return {
                "text": disabled_text,
                "motion": "Idle",
                "session_id": sid,
                "provider": "none",
                "model": "manual",
                "sources": [],
            }

        await sio.emit("ai_status", {"status": "กำลังประมวลผลคำตอบ..."})

        reply = await runtime.assistant.answer(sid, platform, user_text)
        display_text = reply.text

        await sio.emit("admin_bot_reply", {"platform": platform, "uid": sid, "text": f"[Bot REG-01] {display_text}"})
        await sio.emit("ai_response", {"text": display_text, "motion": reply.motion})

        runtime.write_audit(
            sid,
            platform,
            user_text,
            display_text,
            time.time() - start,
            provider=reply.provider,
            model=reply.model,
        )

        return {
            "text": display_text,
            "motion": reply.motion,
            "session_id": sid,
            "provider": reply.provider,
            "model": reply.model,
            "sources": [vars(item) for item in reply.sources],
        }

    @app.post("/api/speak")
    async def api_speak(text: str = Form(...)):
        async def _stream():
            async for chunk in stream_tts(text):
                yield chunk

        return StreamingResponse(_stream(), media_type="audio/mpeg")

    @app.get("/webhook")
    async def webhook_verify(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ):
        if hub_mode == "subscribe" and hub_verify_token == settings.fb_verify_token:
            return Response(content=hub_challenge or "", media_type="text/plain")
        return JSONResponse({"error": "verification failed"}, status_code=403)

    @app.post("/webhook")
    async def webhook_receive(request: Request):
        allowed, retry_after = webhook_limiter.allow(f"webhook:{_client_identifier(request)}")
        if not allowed:
            return JSONResponse(
                {"detail": "rate_limited", "retry_after_seconds": retry_after},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        raw_payload = await request.body()
        signature = request.headers.get("x-hub-signature-256")
        if settings.fb_app_secret and not _verify_facebook_signature(settings.fb_app_secret, raw_payload, signature):
            return JSONResponse({"detail": "invalid_signature"}, status_code=403)

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except json.JSONDecodeError:
            return JSONResponse({"detail": "invalid_json"}, status_code=400)

        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender = event.get("sender", {}).get("id")
                message = event.get("message", {}) or {}
                text = (message.get("text") or "").strip()
                is_echo = bool(message.get("is_echo"))

                if is_echo or not sender or not text:
                    continue

                await sio.emit(
                    "admin_new_message",
                    {"platform": "facebook", "uid": sender, "text": text, "user_name": f"FB {sender[:6]}"},
                )

                if not runtime.get_bot_enabled(sender):
                    disabled_text = "Auto-reply is disabled for this session. Please wait for an admin response."
                    runtime.session_store.append_message(sender, "facebook", "user", text)
                    runtime.session_store.append_message(sender, "facebook", "model", disabled_text)
                    await send_facebook_text(settings, sender, disabled_text)
                    runtime.write_audit(sender, "facebook", text, disabled_text, 0.0)
                    continue

                start = time.time()
                reply = await runtime.assistant.answer(sender, "facebook", text)
                await send_facebook_text(settings, sender, reply.text)
                await sio.emit(
                    "admin_bot_reply",
                    {"platform": "facebook", "uid": sender, "text": f"[Bot REG-01] {reply.text}"},
                )
                runtime.write_audit(
                    sender,
                    "facebook",
                    text,
                    reply.text,
                    time.time() - start,
                    provider=reply.provider,
                    model=reply.model,
                )
        return {"status": "ok"}

    async def _verify_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
        if not settings.admin_token:
            raise HTTPException(status_code=503, detail="admin_disabled")
        if x_admin_token != settings.admin_token:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/admin/stats", dependencies=[Depends(_verify_admin)])
    async def admin_stats():
        logs = runtime.read_recent_audit(limit=120)
        avg_latency = round(sum(item.get("latency", 0) for item in logs) / len(logs), 3) if logs else 0.0
        return {
            "recent_logs": logs,
            "faq_analytics": {
                "total_knowledge_base": len(runtime.knowledge_store._chunks),
                "top_faqs": [],
            },
            "bot_settings": {"facebook": True, "line": False, "web": True},
            "token_analytics": {
                "total_tokens": 0,
                "avg_tokens_per_request": 0,
                "cache_hit_rate": 0,
                "total_cost_usd": 0.0,
                "estimated_avg_latency": avg_latency,
            },
        }

    @app.get("/api/admin/chat/sessions", dependencies=[Depends(_verify_admin)])
    async def admin_chat_sessions():
        sessions = runtime.session_store.list_sessions(limit=400)
        for session in sessions:
            session["bot_enabled"] = runtime.get_bot_enabled(session["id"])
        return sessions

    @app.get("/api/admin/chat/history/{platform}/{uid}", dependencies=[Depends(_verify_admin)])
    async def admin_chat_history(platform: str, uid: str):
        history = runtime.session_store.get_history(uid, limit=300)
        if platform:
            return history
        return history

    @app.post("/api/admin/bot-toggle", dependencies=[Depends(_verify_admin)])
    async def admin_bot_toggle(session_id: str = Form(...), status: str = Form(...)):
        enabled = _parse_bool(status)
        runtime.set_bot_enabled(session_id, enabled)
        return {"status": "success", "session_id": session_id, "bot_enabled": enabled}

    @app.post("/api/admin/bot-toggle-all", dependencies=[Depends(_verify_admin)])
    async def admin_bot_toggle_all(status: str = Form(...)):
        enabled = _parse_bool(status)
        updated = runtime.set_all_bot_enabled(enabled)
        return {"status": "success", "updated_count": updated, "bot_enabled": enabled}

    @app.post("/api/admin/process-rag", dependencies=[Depends(_verify_admin)])
    async def admin_process_rag():
        runtime.reload_indexes()
        return {"status": "completed", "chunks": len(runtime.knowledge_store._chunks)}

    @app.get("/api/admin/files", dependencies=[Depends(_verify_admin)])
    async def admin_files_disabled():
        return {"root": "disabled", "current_path": "", "entries": []}

    @app.post("/api/admin/move", dependencies=[Depends(_verify_admin)])
    async def admin_move_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.post("/api/admin/upload", dependencies=[Depends(_verify_admin)])
    async def admin_upload_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.get("/api/admin/view", dependencies=[Depends(_verify_admin)])
    async def admin_view_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.post("/api/admin/edit", dependencies=[Depends(_verify_admin)])
    async def admin_edit_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.post("/api/admin/mkdir", dependencies=[Depends(_verify_admin)])
    async def admin_mkdir_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.post("/api/admin/rename", dependencies=[Depends(_verify_admin)])
    async def admin_rename_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.post("/api/admin/copy", dependencies=[Depends(_verify_admin)])
    async def admin_copy_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @app.delete("/api/admin/files", dependencies=[Depends(_verify_admin)])
    async def admin_delete_disabled():
        raise HTTPException(status_code=501, detail="file_management_disabled")

    @sio.event
    async def connect(sid, environ):
        logger.info("Socket connected sid=%s", sid)

    @sio.event
    async def disconnect(sid):
        logger.info("Socket disconnected sid=%s", sid)

    @sio.on("admin_manual_reply")
    async def admin_manual_reply(sid, data):
        platform = (data or {}).get("platform")
        uid = (data or {}).get("uid")
        text = ((data or {}).get("text") or "").strip()
        if not uid or not text:
            await sio.emit("admin_error", {"message": "invalid payload"}, to=sid)
            return

        runtime.session_store.append_message(uid, platform or "web", "model", f"[Admin] {text}")
        if platform == "facebook":
            await send_facebook_text(settings, uid, text)
        else:
            await sio.emit("ai_response", {"text": text, "motion": "Talking"})
        await sio.emit("admin_bot_reply", {"platform": platform or "web", "uid": uid, "text": f"[Admin] {text}"})

    asgi_app = socketio.ASGIApp(sio, app)
    return asgi_app, app, sio, runtime
