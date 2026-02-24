"""
Chat Router
จัดการ API สำหรับ chat interface (speech, text, TTS)
"""
from collections import defaultdict, deque
from fastapi import APIRouter, Request, UploadFile, Form, Depends, HTTPException, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import StreamingResponse
import tempfile
import os
import re
import uuid
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.tts_multi import speak, is_tts_available
from app.stt import transcribe
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from dev.flow_store import get_effective_flow_config
from app.config import (
    LLM_PROVIDER,
    GEMINI_MODEL_NAME,
    OPENAI_MODEL_NAME,
    LOCAL_MODEL_NAME,
    ALLOWED_ORIGINS,
    SPEECH_REQUIRE_API_KEY,
    SPEECH_ALLOWED_API_KEYS,
    SPEECH_RATE_LIMIT_PER_MINUTE,
)
from memory.session import get_or_create_history, save_history, get_bot_enabled
from router.socketio_handlers import emit_to_web_session
from queue_manager import QueueFullError, QueueTimeoutError

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("ChatRouter")

executor = ThreadPoolExecutor(max_workers=10)

sio = None
session_locks = {}
audit_logger = None
llm_queue = None
_rate_limit_lock = asyncio.Lock()
_rate_windows = defaultdict(deque)
_session_pattern = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_allowed_api_keys = set(SPEECH_ALLOWED_API_KEYS)


def _is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    cleaned = [item.strip() for item in ALLOWED_ORIGINS if str(item).strip()]
    if "*" in cleaned:
        return True
    return origin in cleaned


def _validate_session_id(raw_session_id: str) -> str:
    value = str(raw_session_id or "").strip()
    if _session_pattern.match(value):
        return value
    return ""


def _issue_server_session_id() -> str:
    return f"web_{uuid.uuid4().hex}"


async def _enforce_rate_limit(key: str) -> None:
    now_ts = time.time()
    window_start = now_ts - 60.0
    async with _rate_limit_lock:
        q = _rate_windows[key]
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= SPEECH_RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({SPEECH_RATE_LIMIT_PER_MINUTE}/minute).",
            )
        q.append(now_ts)


def _resolve_session_id(request: Request, incoming_session_id: str) -> str:
    incoming_sid = _validate_session_id(incoming_session_id)
    if incoming_sid:
        return incoming_sid

    cookie_sid = _validate_session_id(request.cookies.get("reg01_sid"))
    if cookie_sid:
        return cookie_sid
    return _issue_server_session_id()

def init_chat_router(socketio_instance, locks_dict, audit_log_fn, queue_instance=None):
    """Initialize router with dependencies"""
    global sio, session_locks, audit_logger, llm_queue
    sio = socketio_instance
    session_locks = locks_dict
    audit_logger = audit_log_fn
    llm_queue = queue_instance

async def get_session_lock(session_id: str):
    """Get or create session lock"""
    return session_locks.setdefault(session_id, asyncio.Lock())

@router.post("/speech")
async def handle_speech(
    request: Request,
    response: Response,
    text: str = Form(None),
    session_id: str = Form(None),
    user_name: str = Form(None),
    user_pic: str = Form(None),
    audio: UploadFile = Form(None),
    auth: str = Depends(APIKeyHeader(name="X-API-Key", auto_error=False))
):
    """
    Handle speech/text input from web interface
    - รับ audio file หรือ text
    - ประมวลผลด้วย STT (ถ้าเป็น audio)
    - ส่งไปยัง LLM
    - คืนค่า response พร้อม motion
    """
    start_time = time.time()
    origin = (request.headers.get("origin") or "").strip()
    if not _is_origin_allowed(origin):
        raise HTTPException(status_code=403, detail="Origin not allowed.")

    api_key = str(auth or "").strip()
    if SPEECH_REQUIRE_API_KEY and not api_key:
        raise HTTPException(status_code=401, detail="Missing API key.")
    if _allowed_api_keys:
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key.")
        if api_key not in _allowed_api_keys:
            raise HTTPException(status_code=401, detail="Invalid API key.")

    client_ip = (request.client.host if request.client else "unknown").strip()
    rate_limit_key = api_key if api_key else f"ip:{client_ip}"
    await _enforce_rate_limit(rate_limit_key)

    final_session_id = _resolve_session_id(request, session_id)
    if _validate_session_id(request.cookies.get("reg01_sid")) != final_session_id:
        response.set_cookie(
            key="reg01_sid",
            value=final_session_id,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            path="/",
        )
    response.headers["X-Session-Id"] = final_session_id

    user_id = api_key or client_ip
    final_user_name = user_name or f"Web User {final_session_id[:5]}"
    final_user_pic = user_pic or "https://www.gravatar.com/avatar/?d=mp"
    
    if audio:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp:
            temp.write(await audio.read())
            temp_path = temp.name
        
        try:
            text = await asyncio.get_event_loop().run_in_executor(executor, transcribe, temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    if not text:
        return {"text": "", "motion": "Idle", "session_id": final_session_id}
    
    if sio:
        await sio.emit("admin_new_message", {
            "platform": "web",
            "uid": final_session_id,
            "text": text,
            "user_name": final_user_name,
            "user_pic": final_user_pic
        })

    bot_enabled = await get_bot_enabled(final_session_id)
    if not bot_enabled:
        history = await get_or_create_history(
            final_session_id,
            user_name=final_user_name,
            user_picture=final_user_pic,
            platform="web"
        )
        history.append({"role": "user", "parts": [{"text": text}]})
        await save_history(
            final_session_id,
            history,
            user_name=final_user_name,
            user_picture=final_user_pic,
            platform="web"
        )
        return {
            "text": "ขณะนี้ Bot ปิดให้บริการ (Admin กำลังดูแลคุณ)",
            "motion": "Idle",
            "session_id": final_session_id,
        }

    async with await get_session_lock(final_session_id):
        await get_or_create_history(
            final_session_id,
            user_name=final_user_name,
            user_picture=final_user_pic,
            platform="web"
        )

        async def _emit_to_session(event_name: str, payload: dict):
            await emit_to_web_session(event_name, payload, final_session_id)

        # ── Submit to decoupled queue system ──
        try:
            if llm_queue:
                result = await llm_queue.submit(
                    user_id=user_id,
                    session_id=final_session_id,
                    msg=text,
                    emit_fn=_emit_to_session,
                )
            else:
                result = await ask_llm(text, final_session_id, emit_fn=_emit_to_session)
        except QueueFullError as qfe:
            logger.warning("Queue full for user=%s: %s", user_id[:16], qfe)
            return {
                "text": str(qfe),
                "motion": "Idle",
                "session_id": final_session_id,
                "queue_error": "full",
            }
        except QueueTimeoutError as qte:
            logger.warning("Queue timeout for user=%s: %s", user_id[:16], qte)
            return {
                "text": str(qte),
                "motion": "Idle",
                "session_id": final_session_id,
                "queue_error": "timeout",
            }

        reply = result["text"]
        trace_id = result.get("trace_id")
        flow_config = get_effective_flow_config()
        if flow_config.get("pose", {}).get("enabled", True):
            motion = await suggest_pose(reply)
        else:
            motion = "Idle"
        tokens = result.get("tokens", {})
    
    model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else (
        OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
    )
    
    if audit_logger:
        audit_logger(
            user_id,
            "web",
            text,
            reply,
            time.time() - start_time,
            tokens=tokens,
            model_name=model_name,
            session_id=final_session_id,
            trace_id=trace_id,
        )
    
    display_text = f"[Bot พี่เร็ก] {reply.replace('//', '')}"
    if sio:
        await sio.emit("admin_bot_reply", {
            "platform": "web",
            "uid": final_session_id,
            "text": display_text
        })

    await emit_to_web_session("ai_response", {
        "motion": motion,
        "text": display_text,
        "tts_text": reply,
    }, final_session_id)
    
    return {
        "text": display_text,
        "tts_text": reply,
        "motion": motion,
        "session_id": final_session_id,
    }

@router.post("/speak")
async def text_to_speech(text: str = Form(...)):
    """
    Convert text to speech (TTS)
    Returns audio stream in MP3 format
    """
    if not is_tts_available():
        return Response(status_code=204)

    stream = speak(text)
    try:
        first_chunk = await asyncio.wait_for(anext(stream), timeout=8.0)
    except StopAsyncIteration:
        return Response(status_code=204)
    except asyncio.TimeoutError:
        logger.warning("TTS prefetch timed out; skipping audio for this turn.")
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return Response(status_code=204)

    async def audio_stream():
        yield first_chunk
        try:
            async for chunk in stream:
                if chunk:
                    yield chunk
        except Exception as e:
            logger.error(f"TTS stream error: {e}")

    return StreamingResponse(audio_stream(), media_type="audio/mpeg")
