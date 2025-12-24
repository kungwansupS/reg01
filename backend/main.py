from fastapi import FastAPI, Request, UploadFile, Form, HTTPException, Depends, Security
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware import Middleware
import socketio
import tempfile
import os
import uuid
import json
import hmac
import hashlib
import httpx
import asyncio
import time
import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from app.tts import speak
from app.stt import transcribe
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from dotenv import load_dotenv
from memory.session import get_or_create_history, save_history, cleanup_old_sessions

# ----------------------------------------------------------------------------- #
# SETUP & CONFIG
# ----------------------------------------------------------------------------- #
load_dotenv()
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

executor = ThreadPoolExecutor(max_workers=10)
fb_task_queue = asyncio.Queue()
session_locks = {}

async def get_session_lock(session_id: str):
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

# ----------------------------------------------------------------------------- #
# SECURITY, PRIVACY & LOGGING
# ----------------------------------------------------------------------------- #
user_request_history = defaultdict(list)
RATE_LIMIT_COUNT = 10  
RATE_LIMIT_WINDOW = 60 

def hash_id(user_id: str) -> str:
    """เข้ารหัส User ID เพื่อความเป็นส่วนตัวใน Log"""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]

def is_rate_limited(user_id: str) -> bool:
    now = time.time()
    user_request_history[user_id] = [t for t in user_request_history[user_id] if now - t < RATE_LIMIT_WINDOW]
    if len(user_request_history[user_id]) >= RATE_LIMIT_COUNT:
        return True
    user_request_history[user_id].append(now)
    return False

def write_audit_log(user_id: str, platform: str, user_input: str, ai_response: str, latency: float):
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "anon_id": hash_id(user_id),
        "platform": platform,
        "input": user_input[:500],
        "output": ai_response[:500],
        "latency_sec": round(latency, 3)
    }
    os.makedirs("logs", exist_ok=True)
    with open("logs/user_audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# ----------------------------------------------------------------------------- #
# BACKGROUND TASKS (MAINTENANCE & WORKERS)
# ----------------------------------------------------------------------------- #
async def system_maintenance_task():
    """รันทุก 24 ชม. เพื่อล้างไฟล์ขยะ"""
    while True:
        deleted_count = cleanup_old_sessions(days=7)
        if deleted_count > 0:
            print(f"🧹 [Maintenance]: Cleaned up {deleted_count} old session files.")
        await asyncio.sleep(86400)

async def fb_worker():
    while True:
        task = await fb_task_queue.get()
        psid = task["psid"]
        user_text = task["text"]
        session_id = f"fb_{psid}"
        start_time = time.time()

        if is_rate_limited(psid):
            await send_fb_text(psid, "⚠️ คุณส่งข้อความบ่อยเกินไป โปรดรอสักครู่ครับ")
            fb_task_queue.task_done()
            continue

        async with await get_session_lock(session_id):
            try:
                result = await ask_llm(user_text, session_id, emit_fn=sio.emit)
                reply = (result.get("text") or "").replace("//", " ")
                motion = await suggest_pose(reply)
                
                await sio.emit("ai_response", {"motion": motion, "text": reply})
                await send_fb_text(psid, reply or " ")
                
                write_audit_log(psid, "facebook", user_text, reply, time.time() - start_time)
            except Exception as e:
                print(f"❌ [FB Worker Error]: {e}")
                await send_fb_text(psid, "ขออภัยครับ พี่เร็กติดธุระด่วน กรุณาลองใหม่ภายหลัง")
            finally:
                fb_task_queue.task_done()

# ----------------------------------------------------------------------------- #
# FASTAPI SETUP
# ----------------------------------------------------------------------------- #
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
)
asgi_app = socketio.ASGIApp(sio, app)

app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

@app.on_event("startup")
async def startup_event():
    # Start Maintenance Task
    asyncio.create_task(system_maintenance_task())
    # Start FB Workers
    for _ in range(5):
        asyncio.create_task(fb_worker())

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

# ----------------------------------------------------------------------------- #
# API ENDPOINTS
# ----------------------------------------------------------------------------- #
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

    if is_rate_limited(user_id):
        raise HTTPException(status_code=429, detail="ใจเย็นๆ ครับ พี่เร็กตอบไม่ทันแล้ว!")

    loop = asyncio.get_event_loop()
    if audio:
        await sio.emit("ai_status", {"status": "👂 พี่เร็กกำลังฟังอยู่ครับ..."})
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(await audio.read())
            temp_path = temp_audio.name
        try:
            text = await loop.run_in_executor(executor, transcribe, temp_path)
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

        if text.startswith("✖️") or text == "❌ ไม่เข้าใจเสียง":
            await sio.emit("ai_status", {"status": text})
            return {"text": text, "motion": "none"}
        await sio.emit("subtitle", {"speaker": "user", "text": text.replace("//", " ")})

    if not text:
        return JSONResponse(status_code=400, content={"error": "No input"})

    async with await get_session_lock(final_session_id):
        try:
            result = await ask_llm(text, final_session_id, emit_fn=sio.emit)
            reply = result["text"]
            motion = await suggest_pose(reply)
        except Exception as e:
            print(f"❌ [API Error]: {e}")
            raise HTTPException(status_code=500, detail="ระบบ AI ขัดข้องชั่วคราว")

    write_audit_log(user_id, "web", text, reply, time.time() - start_time)
    await sio.emit("ai_response", {"motion": motion, "text": reply.replace("//", " ")})
    await sio.emit("ai_status", {"status": ""})
    return {"text": reply.replace("//", " "), "motion": motion}

@app.post("/api/speak")
async def handle_speak(text: str = Form(...)):
    async def generate():
        async for chunk in speak(text):
            yield chunk
        await sio.emit("speech_done")
    return StreamingResponse(generate(), media_type="audio/mpeg")

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

async def send_fb_text(psid: str, text: str):
    if not FB_PAGE_ACCESS_TOKEN: return
    url = f"{GRAPH_BASE}/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    data = {"recipient": {"id": psid}, "messaging_type": "RESPONSE", "message": {"text": (text or "")[:1999]}}
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(url, json=data)

def verify_signature(app_secret, signature_header, body):
    if not app_secret or not signature_header: return True
    algo, their_hex = signature_header.split("=", 1)
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, their_hex)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)