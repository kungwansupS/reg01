from fastapi import FastAPI, Request, UploadFile, Form, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware import Middleware
import socketio
import tempfile
import os
import shutil
import uuid
import json
import hmac
import hashlib
import httpx
import asyncio
import time
import datetime
import logging
from typing import List, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.tts import speak
from app.stt import transcribe
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER, SESSION_DIR
from dotenv import load_dotenv
from memory.session import get_or_create_history, save_history, cleanup_old_sessions
from memory.faq_cache import get_faq_analytics
from pdf_to_txt import process_pdfs

# ----------------------------------------------------------------------------- #
# SETUP & CONFIG
# ----------------------------------------------------------------------------- #
load_dotenv()
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "super-secret-key")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

executor = ThreadPoolExecutor(max_workers=10)
fb_task_queue = asyncio.Queue()
session_locks = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AdminBackend")

async def get_session_lock(session_id: str):
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

# ----------------------------------------------------------------------------- #
# SECURITY & ADMIN DEPENDENCIES
# ----------------------------------------------------------------------------- #
user_request_history = defaultdict(list)
RATE_LIMIT_COUNT = 15 
ADMIN_API_KEY_HEADER = APIKeyHeader(name="X-Admin-Token", auto_error=False)

async def verify_admin(auth: str = Depends(ADMIN_API_KEY_HEADER)):
    if auth != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin Token")
    return auth

def hash_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]

def is_rate_limited(user_id: str) -> bool:
    now = time.time()
    user_request_history[user_id] = [t for t in user_request_history[user_id] if now - t < 60]
    if len(user_request_history[user_id]) >= RATE_LIMIT_COUNT:
        return True
    user_request_history[user_id].append(now)
    return False

def write_audit_log(user_id: str, platform: str, user_input: str, ai_response: str, latency: float, rating: str = "none"):
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "anon_id": hash_id(user_id),
        "platform": platform,
        "input": user_input[:300],
        "output": ai_response[:300],
        "latency": round(latency, 2),
        "rating": rating
    }
    os.makedirs("logs", exist_ok=True)
    with open("logs/user_audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# ----------------------------------------------------------------------------- #
# APP & WORKERS
# ----------------------------------------------------------------------------- #
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])])
asgi_app = socketio.ASGIApp(sio, app)

app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

async def fb_worker():
    while True:
        task = await fb_task_queue.get()
        psid = task["psid"]; user_text = task["text"]
        start_time = time.time()
        if is_rate_limited(psid):
            await send_fb_text(psid, "⚠️ คุณส่งข้อความบ่อยเกินไป โปรดรอสักครู่")
            fb_task_queue.task_done(); continue
        async with await get_session_lock(f"fb_{psid}"):
            try:
                result = await ask_llm(user_text, f"fb_{psid}", emit_fn=sio.emit)
                reply = result["text"]
                display_reply = reply.replace("//", "")
                await send_fb_text(psid, display_reply)
                write_audit_log(psid, "facebook", user_text, reply, time.time() - start_time)
            except Exception as e: logger.error(f"FB Error: {e}")
            finally: fb_task_queue.task_done()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(maintenance_loop())
    for _ in range(5): asyncio.create_task(fb_worker())

async def maintenance_loop():
    while True:
        cleanup_old_sessions(days=7)
        await asyncio.sleep(86400)

# ----------------------------------------------------------------------------- #
# ENDPOINTS
# ----------------------------------------------------------------------------- #
@app.get("/webhook")
async def fb_verify(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe":
        if params.get("hub.verify_token") == FB_VERIFY_TOKEN:
            return Response(content=params.get("hub.challenge"), media_type="text/plain")
        return Response(content="Verification failed", status_code=403)
    return Response(content="Invalid mode", status_code=400)

@app.post("/webhook")
async def fb_webhook(request: Request):
    raw = await request.body()
    if not verify_signature(FB_APP_SECRET, request.headers.get("X-Hub-Signature-256"), raw):
        raise HTTPException(status_code=403, detail="Bad signature")
    payload = json.loads(raw.decode("utf-8"))
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event["sender"]["id"]
            if "message" in event and "text" in event["message"] and not event["message"].get("is_echo"):
                await fb_task_queue.put({"psid": psid, "text": event["message"]["text"].strip()})
    return JSONResponse({"status": "accepted"})

@app.post("/api/speech")
async def handle_speech(
    request: Request,
    text: str = Form(None),
    session_id: str = Form(None),
    audio: UploadFile = Form(None),
    auth: str = Depends(APIKeyHeader(name="X-API-Key", auto_error=False))
):
    start_time = time.time()
    user_id = auth or "anonymous"
    final_session_id = user_id if user_id != "local-dev-user" else (session_id or str(uuid.uuid4()))
    if is_rate_limited(user_id): raise HTTPException(status_code=429, detail="Rate limit exceeded")
    if audio:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp:
            temp.write(await audio.read())
            temp_path = temp.name
        try: text = await asyncio.get_event_loop().run_in_executor(executor, transcribe, temp_path)
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)
    async with await get_session_lock(final_session_id):
        result = await ask_llm(text, final_session_id, emit_fn=sio.emit)
        reply = result["text"]; motion = await suggest_pose(reply)
    write_audit_log(user_id, "web", text, reply, time.time() - start_time)
    display_text = reply.replace("//", " ")
    await sio.emit("ai_response", {"motion": motion, "text": display_text})
    return {"text": display_text, "motion": motion}

# ----------------------------------------------------------------------------- #
# ADMIN ENDPOINTS (BROWSER SUPPORTED)
# ----------------------------------------------------------------------------- #
@app.get("/api/admin/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    logs = []
    if os.path.exists("logs/user_audit.log"):
        with open("logs/user_audit.log", "r", encoding="utf-8") as f:
            logs = [json.loads(line) for line in f.readlines()][-100:]
    return {"recent_logs": logs, "faq_analytics": get_faq_analytics(), "system_time": datetime.datetime.now().isoformat()}

@app.get("/api/admin/files", dependencies=[Depends(verify_admin)])
async def list_admin_files(root: str = "docs", subdir: str = ""):
    """เปิดดูไฟล์และโฟลเดอร์ใน static/docs หรือ static/quick_use"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    
    # Security: ป้องกันการใช้ .. เพื่อออกนอกโฟลเดอร์
    clean_subdir = subdir.lstrip("/").replace("..", "")
    target_dir = os.path.join(base_path, clean_subdir)
    
    if not os.path.exists(target_dir):
        return {"root": root, "entries": [], "current_path": clean_subdir}

    entries = []
    for item in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item)
        is_dir = os.path.isdir(item_path)
        # สร้าง relative path สำหรับใช้งานต่อ
        rel_path = os.path.join(clean_subdir, item).replace("\\", "/")
        entries.append({
            "name": item,
            "is_dir": is_dir,
            "path": rel_path,
            "ext": "".join(Path(item).suffixes).lower() if not is_dir else ""
        })
    
    return {
        "root": root,
        "current_path": clean_subdir,
        "entries": sorted(entries, key=lambda x: (not x["is_dir"], x["name"].lower()))
    }

@app.post("/api/admin/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form("")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF allowed")
    
    clean_dir = target_dir.lstrip("/").replace("..", "")
    dest_folder = os.path.join(PDF_INPUT_FOLDER, clean_dir)
    os.makedirs(dest_folder, exist_ok=True)
    
    safe_name = "".join([c for c in file.filename if c.isalnum() or c in ('.', '_', '-')]).strip()
    file_path = os.path.join(dest_folder, safe_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "path": os.path.join(clean_dir, safe_name).replace("\\", "/")}

@app.post("/api/admin/process-rag", dependencies=[Depends(verify_admin)])
async def trigger_rag_process():
    try:
        await asyncio.get_event_loop().run_in_executor(executor, process_pdfs)
        return {"status": "completed"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/files", dependencies=[Depends(verify_admin)])
async def delete_item(root: str, path: str):
    """ลบไฟล์หรือโฟลเดอร์ตาม path ที่ระบุ"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    target = os.path.join(base_path, path.lstrip("/").replace("..", ""))
    
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Not found")
        
    if os.path.isdir(target):
        shutil.rmtree(target)
    else:
        os.remove(target)
    return {"status": "deleted"}

async def send_fb_text(psid: str, text: str):
    if not FB_PAGE_ACCESS_TOKEN: return
    url = f"{GRAPH_BASE}/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    data = {"recipient": {"id": psid}, "message": {"text": (text or "")[:1999]}}
    async with httpx.AsyncClient(timeout=15) as client: await client.post(url, json=data)

def verify_signature(app_secret, signature_header, body):
    if not app_secret or not signature_header: return True
    try:
        algo, their_hex = signature_header.split("=", 1)
        digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, their_hex)
    except: return False

@app.get("/")
async def serve_index(): return FileResponse("frontend/index.html")

@app.get("/admin")
async def serve_admin(): return FileResponse("frontend/admin.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)