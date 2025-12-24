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
# ENV & CONFIG
# ----------------------------------------------------------------------------- #
load_dotenv()
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "verify123")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

# ThreadPool สำหรับรันงานที่เป็น Sync (STT, Pose)
executor = ThreadPoolExecutor(max_workers=10)

# ----------------------------------------------------------------------------- #
# SOCKET.IO + FASTAPI (ASGI)
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

# ----------------------------------------------------------------------------- #
# STATIC FILES / INDEX
# ----------------------------------------------------------------------------- #
app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

# ----------------------------------------------------------------------------- #
# QUEUE SYSTEM (For Facebook Webhook)
# ----------------------------------------------------------------------------- #
fb_task_queue = asyncio.Queue()
session_locks = {}

async def get_session_lock(session_id: str):
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

async def fb_worker():
    """Worker ประมวลผลข้อความจาก Facebook เบื้องหลัง"""
    while True:
        task = await fb_task_queue.get()
        psid = task.get("psid")
        user_text = task.get("text")
        session_id = task.get("session_id")

        async with await get_session_lock(session_id):
            try:
                print(f"[Worker] กำลังประมวลผลข้อความจาก {psid}: {user_text}")
                
                # 1. จัดการ History
                history = get_or_create_history(session_id, context_prompt)
                history.append({"role": "user", "parts": [{"text": user_text}]})
                save_history(session_id, history)

                # 2. เรียก LLM
                result = await ask_llm(user_text, session_id, emit_fn=sio.emit)
                reply = (result.get("text") or "").replace("//", " ")
                from_faq = result.get("from_faq", False)

                if from_faq and reply:
                    # history มีการอัปเดตข้างใน ask_llm แล้วในระดับหนึ่ง แต่เพื่อความชัวร์ตรวจสอบ logic ใน llm.py ด้วย
                    pass

                # 3. Suggest Pose (รันแบบขนานใน Thread เพราะเป็น Sync)
                loop = asyncio.get_event_loop()
                motion = await loop.run_in_executor(executor, suggest_pose, reply)

                # 4. ส่งออกผ่าน Socket และ Facebook
                await sio.emit("ai_response", {"motion": motion, "text": reply})
                await send_fb_text(psid, reply or " ")

            except Exception as e:
                print(f"[Worker Error]: {e}")
            finally:
                fb_task_queue.task_done()

@app.on_event("startup")
async def startup_event():
    # เริ่ม Worker จำนวน 3 ตัวเพื่อประมวลผลขนานกัน
    for _ in range(3):
        asyncio.create_task(fb_worker())

# ----------------------------------------------------------------------------- #
# HELPERS
# ----------------------------------------------------------------------------- #
def clear_pycache():
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))
        for f in files:
            if f.endswith(".pyc"):
                os.remove(os.path.join(root, f))
clear_pycache()

async def send_fb_text(psid: str, text: str):
    if not FB_PAGE_ACCESS_TOKEN:
        print("FB_PAGE_ACCESS_TOKEN is empty.")
        return
    url = f"{GRAPH_BASE}/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    data = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {"text": (text or "")[:1999]},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(url, params=params, json=data)
            r.raise_for_status()
        except Exception as e:
            print(f"Facebook Send API Error: {e}")

def verify_signature(app_secret: str, signature_header: str, body: bytes) -> bool:
    if not app_secret: return True
    if not signature_header or "=" not in signature_header: return False
    algo, their_hex = signature_header.split("=", 1)
    if algo != "sha256": return False
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, their_hex)

# ----------------------------------------------------------------------------- #
# ROUTES
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

    # --- Voice mode ---
    if audio:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(await audio.read())
            temp_path = temp_audio.name

        # รัน STT ใน Thread เพื่อไม่ให้บล็อกคนอื่น
        text = await loop.run_in_executor(executor, transcribe, temp_path)
        await sio.emit("subtitle", {"speaker": "user", "text": text.replace("//", " ")})

        history = get_or_create_history(session_id, context_prompt)
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(session_id, history)

    # --- Text mode ---
    elif text:
        history = get_or_create_history(session_id, context_prompt)
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(session_id, history)

    if not text or text == "❌ ไม่เข้าใจเสียง":
        return {"text": "", "motion": ""}

    # ประมวลผล LLM
    result = await ask_llm(text, session_id, emit_fn=sio.emit)
    reply = result["text"]
    
    # ประมวลผล Pose ใน Thread
    motion = await loop.run_in_executor(executor, suggest_pose, reply)

    await sio.emit("ai_response", {"motion": motion, "text": reply.replace("//", " ")})
    return {"text": reply.replace("//", " "), "motion": motion}

@app.post("/api/speak")
async def handle_speak(text: str = Form(...)):
    async def generate():
        async for chunk in speak(text):
            yield chunk
        await sio.emit("speech_done")
    return StreamingResponse(generate(), media_type="audio/mpeg")

@app.post("/api/clear_history")
async def clear_history_route(session_id: str = ""):
    if not session_id: session_id = str(uuid.uuid4())
    clear_history(session_id)
    return {"status": "cleared", "session_id": session_id}

@app.get("/webhook")
async def fb_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        return PlainTextResponse(challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")

SEEN_MIDS = {}
DUP_TTL = 600

def seen_mid(mid: str) -> bool:
    now = time.time()
    expired = [k for k, v in SEEN_MIDS.items() if v < now]
    for k in expired: del SEEN_MIDS[k]
    if mid in SEEN_MIDS: return True
    SEEN_MIDS[mid] = now + DUP_TTL
    return False

@app.post("/webhook")
async def fb_webhook(request: Request):
    raw = await request.body()
    if not verify_signature(FB_APP_SECRET, request.headers.get("X-Hub-Signature-256"), raw):
        raise HTTPException(status_code=403, detail="Bad signature")

    payload = json.loads(raw.decode("utf-8"))
    
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event["sender"]["id"]
            if "message" in event:
                msg = event["message"]
                if msg.get("is_echo") or "text" not in msg: continue
                
                mid = msg.get("mid")
                if mid and seen_mid(mid): continue

                user_text = msg["text"].strip()
                # ใส่ลงใน Queue แล้วตอบ 200 ทันที
                await fb_task_queue.put({
                    "psid": psid,
                    "text": user_text,
                    "session_id": f"fb:{psid}"
                })

    return JSONResponse({"status": "accepted"}) # ตอบกลับ Facebook ทันที

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)