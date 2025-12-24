from fastapi import FastAPI, Request, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
import socketio
import tempfile
import shutil
import os
import uuid
import json
import hmac
import hashlib
import httpx
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.tts import speak
from app.stt import transcribe
from app.prompt.prompt import context_prompt
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from dotenv import load_dotenv
from memory.session import clear_history, get_or_create_history, save_history

# ----------------------------------------------------------------------------- #
# SETUP & CONCURRENCY CONFIG
# ----------------------------------------------------------------------------- #
load_dotenv()
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "verify123")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

# กำหนด Pool สำหรับงานประมวลผลหนัก (CPU-bound)
executor = ThreadPoolExecutor(max_workers=10)
fb_task_queue = asyncio.Queue()
session_locks = {}

async def get_session_lock(session_id: str):
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

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
        session_id = task["session_id"]

        async with await get_session_lock(session_id):
            try:
                # ประมวลผลผ่าน LLM (ซึ่งรวม RAG และ FAQ แล้วจาก Phase 2)
                result = await ask_llm(user_text, session_id, emit_fn=sio.emit)
                reply = (result.get("text") or "").replace("//", " ")
                
                # ทำนายท่าทาง (Pose) แบบขนาน
                loop = asyncio.get_event_loop()
                motion = await loop.run_in_executor(executor, suggest_pose, reply)

                # ส่งผลลัพธ์
                await sio.emit("ai_response", {"motion": motion, "text": reply})
                await send_fb_text(psid, reply or " ")
            except Exception as e:
                print(f"Worker Error: {e}")
            finally:
                fb_task_queue.task_done()

@app.on_event("startup")
async def startup_event():
    # รัน Worker 3 ตัวพร้อมกัน
    for _ in range(3):
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
):
    if not session_id:
        session_id = str(uuid.uuid4())
    
    loop = asyncio.get_event_loop()

    if audio:
        # ส่งสถานะกำลังรับเสียง
        await sio.emit("ai_status", {"status": "👂 กำลังฟังและแปลงเสียง..."})
        
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(await audio.read())
            temp_path = temp_audio.name

        # รัน STT (แบบ Thread-safe จากที่แก้ใน stt.py)
        text = await loop.run_in_executor(executor, transcribe, temp_path)
        
        if text.startswith("✖️") or text == "❌ ไม่เข้าใจเสียง":
            await sio.emit("ai_status", {"status": text})
            return {"text": text, "motion": "none"}
            
        await sio.emit("subtitle", {"speaker": "user", "text": text.replace("//", " ")})

    if not text:
        return JSONResponse(status_code=400, content={"error": "No input"})

    # ล็อค Session เพื่อป้องกันการอัปเดต History ซ้อนกัน
    async with await get_session_lock(session_id):
        # บันทึกฝั่ง User
        history = get_or_create_history(session_id, context_prompt)
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(session_id, history)

        # ถาม LLM
        result = await ask_llm(text, session_id, emit_fn=sio.emit)
        reply = result["text"]
        
        # ถาม Pose
        motion = await loop.run_in_executor(executor, suggest_pose, reply)

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
                user_text = event["message"]["text"].strip()
                # เข้าคิวเพื่อตอบ Facebook ให้ทันใน 2 วินาที
                await fb_task_queue.put({
                    "psid": psid,
                    "text": user_text,
                    "session_id": f"fb:{psid}"
                })
    return JSONResponse({"status": "accepted"})

# ----------------------------------------------------------------------------- #
# HELPERS (FACEBOOK)
# ----------------------------------------------------------------------------- #
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