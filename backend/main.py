"""
REG-01 Main Application
FastAPI + SocketIO + Background Workers

โครงสร้าง:
- main.py: Application setup & routing
- router/webhook_router.py: Facebook webhooks
- router/chat_router.py: Chat API (speech, text, TTS)
- router/socketio_handlers.py: Real-time events
- router/background_tasks.py: Workers (FB, maintenance, vector sync)
- router/admin_router.py: Admin dashboard (existing)
- router/database_router.py: Database management (existing)
"""
from fastapi import FastAPI
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
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# ✅ Import configurations
from app.config import BOT_SETTINGS_FILE
from app.utils.llm.llm_model import close_llm_clients
from app.utils.llm.llm import ask_llm
from app.utils.token_counter import calculate_cost

# ✅ Import routers
from router.admin_router import router as admin_router
from router.database_router import router as database_router
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

# ----------------------------------------------------------------------------- #
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------- #
def hash_id(user_id: str) -> str:
    """Hash user ID for privacy"""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]

def write_audit_log(
    user_id: str,
    platform: str,
    user_input: str,
    ai_response: str,
    latency: float,
    rating: str = "none",
    tokens: dict = None,
    model_name: str = None
):
    """Write audit log with token tracking"""
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "anon_id": hash_id(user_id),
        "platform": platform,
        "input": user_input[:300],
        "output": ai_response[:300],
        "latency": round(latency, 2),
        "rating": rating
    }
    
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
    with open("logs/user_audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

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

# ----------------------------------------------------------------------------- #
# APPLICATION SETUP
# ----------------------------------------------------------------------------- #
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(
    title="REG-01 Backend",
    version="2.0.0",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
    ]
)

asgi_app = socketio.ASGIApp(sio, app)

# ✅ Mount static files
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

# ✅ Include routers
app.include_router(webhook_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router)
app.include_router(database_router)

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

# ----------------------------------------------------------------------------- #
# LIFECYCLE EVENTS
# ----------------------------------------------------------------------------- #
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info("🚀 Starting REG-01 Application...")
    
    # ✅ Sync vector database
    await background_tasks.sync_vector_db()
    
    # ✅ Build hybrid search index
    await background_tasks.build_hybrid_index()
    
    # ✅ Start background workers
    asyncio.create_task(background_tasks.maintenance_loop())
    for _ in range(5):
        asyncio.create_task(background_tasks.fb_worker())
    
    logger.info("✅ Application ready")

async def cleanup():
    """Cleanup before shutdown"""
    logger.info("🧹 Starting cleanup...")
    
    # ✅ Close LLM clients
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

# ✅ Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ✅ Register atexit
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