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
from app.prompt.prompt import context_prompt
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from dotenv import load_dotenv
from memory.session import get_or_create_history, save_history

# ----------------------------------------------------------------------------- #
# SETUP & CONCURRENCY CONFIG
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
# RATE LIMIT & AUDIT LOG SYSTEM
# ----------------------------------------------------------------------------- #
user_request_history = defaultdict(list)
RATE_LIMIT_COUNT = 10  
RATE_LIMIT_WINDOW = 60 

def is_rate_limited(user_id: str) -> bool:
    now = time.time()
    user_request_history[user_id] = [t for t in user_request_history[user_id] if now - t < RATE_LIMIT_WINDOW]
    if len(user_request_history[user_id]) >= RATE_LIMIT_COUNT:
        return True
    user_request_history[user_id].append(now)
    return False

def write_audit_log(user_id: str, platform: str, user_input: str, ai_response: str):
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "platform": platform,
        "input": user_input[:500],  # ตัดสั้นเพื่อประหยัดพื้นที่ log
        "output": ai_response[:500]
    }
    os.makedirs("logs", exist_ok=True)
    with open("logs/user_audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# ----------------------------------------------------------------------------- #
# SECURITY & ACCESS CONTROL
# ----------------------------------------------------------------------------- #
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_token(request: Request, api_key: str = Depends(api_key_header)):
    client_host = request.client.host
    if client_host in ["127.0.0.1", "localhost"]:
        return api_key or "local-dev-user"
    if not api_key:
        print(f"🔒 [Security]: Unauthorized access attempt from {client_host}")
        raise HTTPException(status_code=403, detail="Unauthorized: กรุณาเข้าสู่ระบบ")
    return api_key

# ----------------------------------------------------------------------------- #
# FASTAPI & SOCKET.IO
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

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

# ----------------------------------------------------------------------------- #
# BACKGROUND WORKER (FOR FACEBOOK)
# ----------------------------------------------------------------------------- #
async def fb_worker():
    while True:
        task = await fb_task_queue.get()
        psid = task["psid"]
        user_text = task["text"]
        session_id = f"fb_{psid}"

        # Check Rate Limit for FB User
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
                
                # Write Audit Log
                write_audit_log(psid, "facebook", user_text, reply)
            except Exception as e:
                print(f"Worker Error: {e}")
            finally:
                fb_task_queue.task_done()

@app.on_event("startup")
async def startup_event():
    for _ in range(5):
        asyncio.create_task(fb_worker())

# ----------------------------------------------------------------------------- #
# API ROUTES
# ----------------------------------------------------------------------------- #
@app.post("/api/speech")
async def handle_speech(
    request: Request,
    text: str = Form(None),
    session_id: str = Form(None),
    audio: UploadFile = Form(None),
    auth: str = Depends(verify_token)
):
    # 1. Identity: ใช้ auth (API Key/SSO ID) เป็น session_id หลัก
    final_session_id = auth if auth != "local-dev-user" else (session_id or str(uuid.uuid4()))

    # 2. Rate Limit Check
    if is_rate_limited(final_session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: กรุณาลองใหม่ในอีก 1 นาที")

    loop = asyncio.get_event_loop()
    if audio:
        await sio.emit("ai_status", {"status": "👂 พี่เร็กกำลังฟังอยู่ครับ..."})
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(await audio.read())
            temp_path = temp_audio.name
        text = await loop.run_in_executor(executor, transcribe, temp_path)
        if text.startswith("✖️") or text == "❌ ไม่เข้าใจเสียง":
            await sio.emit("ai_status", {"status": text})
            return {"text": text, "motion": "none"}
        await sio.emit("subtitle", {"speaker": "user", "text": text.replace("//", " ")})

    if not text:
        return JSONResponse(status_code=400, content={"error": "No input"})

    async with await get_session_lock(final_session_id):
        result = await ask_llm(text, final_session_id, emit_fn=sio.emit)
        reply = result["text"]
        motion = await suggest_pose(reply)

    # 3. Audit Logging
    write_audit_log(final_session_id, "web", text, reply)

    await sio.emit("ai_response", {"motion": motion, "text": reply.replace("//", " ")})
    await sio.emit("ai_status", {"status": ""})
    return {"text": reply.replace("//", " "), "motion": motion}

@app.post("/api/speak")
async def handle_speak(
    text: str = Form(...),
    auth: str = Depends(verify_token)
):
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
                user_text = event["message"]["text"].strip()
                await fb_task_queue.put({
                    "psid": psid,
                    "text": user_text
                })
    return JSONResponse({"status": "accepted"})

async def send_fb_text(psid: str, text: str):
    if not FB_PAGE_ACCESS_TOKEN: return
    url = f"{GRAPH_BASE}/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    data = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {"text": (text or "")[:1999]},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(url, params=params, json=data)

def verify_signature(app_secret, signature_header, body):
    if not app_secret: return True
    if not signature_header or "=" not in signature_header: return False
    algo, their_hex = signature_header.split("=", 1)
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, their_hex)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)