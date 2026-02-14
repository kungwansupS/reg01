from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
import socketio
import os
import json
import signal
import atexit
import httpx
import asyncio
import datetime
import hashlib
import re
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from dotenv import load_dotenv

# Import configurations
from app.config import (
    ALLOWED_ORIGINS,
    AUDIT_LOG_RETENTION_DAYS,
    AUDIT_LOG_MAX_SIZE_MB,
)
from app.utils.llm.llm_model import close_llm_clients
from app.utils.llm.llm import ask_llm
from app.utils.token_counter import calculate_cost
from dev.local_access import ensure_local_request

# Import routers
from router.admin_router import router as admin_router
from router.database_router import router as database_router
from router.dev_router import router as dev_router
from router import webhook_router, chat_router, socketio_handlers, background_tasks

# ----------------------------------------------------------------------------- #
# CONFIGURATION
# ----------------------------------------------------------------------------- #
load_dotenv()

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBackend")

# ----------------------------------------------------------------------------- #
# GLOBAL STATE
# ----------------------------------------------------------------------------- #
executor = ThreadPoolExecutor(max_workers=10)
fb_task_queue = asyncio.Queue()
session_locks = {}
AUDIT_LOG_PATH = os.path.join("logs", "user_audit.log")
_audit_lock = Lock()
_last_audit_trim_ts = 0.0
_SENSITIVE_KV_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|secret)\b\s*[:=]\s*([^\s,;]+)"
)
_SENSITIVE_TOKEN_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
]

# ----------------------------------------------------------------------------- #
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------- #
def hash_id(user_id: str) -> str:
    """Hash user ID for privacy"""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def _redact_sensitive_text(text: str) -> str:
    cleaned = str(text or "")

    def _mask_kv(match: re.Match) -> str:
        return f"{match.group(1)}=[REDACTED]"

    cleaned = _SENSITIVE_KV_PATTERN.sub(_mask_kv, cleaned)
    for pattern in _SENSITIVE_TOKEN_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def _trim_audit_log_if_needed(force: bool = False) -> None:
    global _last_audit_trim_ts

    now_ts = time.time()
    if not force and now_ts - _last_audit_trim_ts < 3600:
        return

    with _audit_lock:
        if not os.path.exists(AUDIT_LOG_PATH):
            _last_audit_trim_ts = now_ts
            return

        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            _last_audit_trim_ts = now_ts
            return

        changed = False
        cutoff = datetime.datetime.now() - datetime.timedelta(days=AUDIT_LOG_RETENTION_DAYS)
        kept_lines = []
        for line in lines:
            row = line.strip()
            if not row:
                changed = True
                continue
            try:
                parsed = json.loads(row)
                ts = datetime.datetime.strptime(
                    str(parsed.get("timestamp", "")),
                    "%Y-%m-%d %H:%M:%S",
                )
                if ts < cutoff:
                    changed = True
                    continue
            except Exception:
                # Keep unparsable rows instead of dropping data unexpectedly.
                pass
            kept_lines.append(line if line.endswith("\n") else f"{line}\n")

        max_bytes = max(1, AUDIT_LOG_MAX_SIZE_MB) * 1024 * 1024
        while kept_lines and sum(len(item.encode("utf-8")) for item in kept_lines) > max_bytes:
            kept_lines.pop(0)
            changed = True

        if changed:
            with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(kept_lines)

        _last_audit_trim_ts = now_ts


def write_audit_log(
    user_id: str,
    platform: str,
    user_input: str,
    ai_response: str,
    latency: float,
    rating: str = "none",
    tokens: dict = None,
    model_name: str = None,
    session_id: str = None,
    trace_id: str = None,
):
    """Write audit log with token tracking"""
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "anon_id": hash_id(user_id),
        "platform": platform,
        "input": _redact_sensitive_text(user_input)[:300],
        "output": _redact_sensitive_text(ai_response)[:300],
        "latency": round(latency, 2),
        "rating": rating
    }

    if session_id:
        log_entry["session_id"] = str(session_id)
    if trace_id:
        log_entry["trace_id"] = str(trace_id)
    
    if tokens:
        log_entry["tokens"] = {
            "prompt": tokens.get("prompt_tokens", 0),
            "completion": tokens.get("completion_tokens", 0),
            "total": tokens.get("total_tokens", 0),
            "cached": tokens.get("cached", False)
        }
        
        if model_name:
            cost = calculate_cost(tokens, model_name)
            if cost > 0:
                log_entry["tokens"]["cost_usd"] = round(cost, 6)
    
    os.makedirs("logs", exist_ok=True)
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    _trim_audit_log_if_needed()

async def send_fb_text(psid: str, text: str):
    """Send message to Facebook Messenger"""
    if not FB_PAGE_ACCESS_TOKEN:
        return
    
    url = f"{GRAPH_BASE}/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    data = {
        "recipient": {"id": psid},
        "message": {"text": (text or "")[:1999]}
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(url, json=data)

allow_all_origins = "*" in ALLOWED_ORIGINS
cors_origins = ["*"] if allow_all_origins else ALLOWED_ORIGINS
socketio_origins = "*" if allow_all_origins else cors_origins

# ----------------------------------------------------------------------------- #
# APPLICATION SETUP
# ----------------------------------------------------------------------------- #
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=socketio_origins)
app = FastAPI(
    title="REG-01 Backend",
    version="2.0.0",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=not allow_all_origins,
            allow_methods=["*"],
            allow_headers=["*"]
        )
    ]
)

asgi_app = socketio.ASGIApp(sio, app)

app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

# ----------------------------------------------------------------------------- #
# INITIALIZE ROUTERS
# ----------------------------------------------------------------------------- #
webhook_router.init_webhook_router(fb_task_queue)
chat_router.init_chat_router(sio, session_locks, write_audit_log)
socketio_handlers.init_socketio_handlers(sio, send_fb_text)
background_tasks.init_background_tasks(
    sio,
    fb_task_queue,
    session_locks,
    write_audit_log,
    ask_llm,
    send_fb_text
)

app.include_router(webhook_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router)
app.include_router(database_router)
app.include_router(dev_router)

# ----------------------------------------------------------------------------- #
# STATIC PAGES
# ----------------------------------------------------------------------------- #
@app.get("/")
async def serve_index():
    """Serve main chat interface"""
    return FileResponse("frontend/index.html")

@app.get("/admin")
async def serve_admin():
    """Serve admin dashboard"""
    return FileResponse("frontend/admin.html")

@app.get("/dev")
async def serve_dev(request: Request):
    """Serve developer flow dashboard"""
    ensure_local_request(request)
    return FileResponse("frontend/dev.html")

# ----------------------------------------------------------------------------- #
# LIFECYCLE EVENTS
# ----------------------------------------------------------------------------- #
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info("🚀 Starting REG-01 Application...")
    
    _trim_audit_log_if_needed(force=True)
    await background_tasks.run_startup_embedding_pipeline()
    
    asyncio.create_task(background_tasks.maintenance_loop())
    for _ in range(5):
        asyncio.create_task(background_tasks.fb_worker())
    
    logger.info("✅ Application ready")

async def cleanup():
    """Cleanup before shutdown"""
    logger.info("🧹 Starting cleanup...")
    
    await close_llm_clients()
    
    logger.info("✅ Cleanup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    await cleanup()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"📡 Received signal {signum}")
    asyncio.create_task(cleanup())

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

atexit.register(lambda: asyncio.run(cleanup()))

# ----------------------------------------------------------------------------- #
# ENTRY POINT
# ----------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:asgi_app",
        host="0.0.0.0",
        port=5000,
        reload=False
    )
