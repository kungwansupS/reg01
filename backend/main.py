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

from app.tts import speak
from app.stt import transcribe
from app.prompt.prompt import context_prompt
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from dotenv import load_dotenv
from memory.session import clear_history, get_or_create_history, save_history

# ----------------------------------------------------------------------------- #
# ENV
# ----------------------------------------------------------------------------- #
load_dotenv()
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "verify123")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

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
# CLEAN PY CACHE
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

# ----------------------------------------------------------------------------- #
# HELPERS (Facebook)
# ----------------------------------------------------------------------------- #
async def send_fb_text(psid: str, text: str):
    """ส่งข้อความกลับผู้ใช้ทาง Messenger Send API"""
    if not FB_PAGE_ACCESS_TOKEN:
        print("FB_PAGE_ACCESS_TOKEN is empty — cannot send message.")
        return
    url = f"{GRAPH_BASE}/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    data = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {"text": (text or "")[:1999]},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, params=params, json=data)
        if r.is_error:
            print("Send API error:", r.status_code, r.text)
        r.raise_for_status()


def verify_signature(app_secret: str, signature_header: str, body: bytes) -> bool:
    """
    ตรวจ X-Hub-Signature-256 ที่ Facebookแนบมา (ป้องกันปลอม request)
    ถ้าไม่ได้ตั้ง FB_APP_SECRET ไว้ จะยอมผ่านเสมอ (สำหรับ dev)
    """
    if not app_secret:
        return True
    if not signature_header or "=" not in signature_header:
        return False
    algo, their_hex = signature_header.split("=", 1)
    if algo != "sha256":
        return False
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, their_hex)

# ----------------------------------------------------------------------------- #
# ROUTES: API ของโปรเจกต์เดิม
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

    # --- Voice mode ---
    if audio:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(await audio.read())
            temp_path = temp_audio.name

        text = transcribe(temp_path)
        await sio.emit("subtitle", {"speaker": "user", "text": text.replace("//", " ")})

        history = get_or_create_history(session_id, context_prompt)
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(session_id, history)

    # --- Text mode ---
    elif text:
        print(f"ข้อความจาก input: {text}")
        history = get_or_create_history(session_id, context_prompt)
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(session_id, history)

    if not text:
        return JSONResponse(status_code=400, content={"error": "กรุณาส่ง audio หรือ text"})

    print(f"ได้ข้อความ: {text}")
    if text == "❌ ไม่เข้าใจเสียง":
        return {"text": "", "motion": ""}

    result = await ask_llm(text, session_id, emit_fn=sio.emit)
    reply = result["text"]
    from_faq = result.get("from_faq", False)

    print(f"ตอบกลับ: {reply}")
    motion = suggest_pose(reply)

    if from_faq:
        history = get_or_create_history(session_id, context_prompt)
        history.append({"role": "model", "parts": [{"text": reply}]})
        save_history(session_id, history)

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


@app.post("/api/clear_history")
async def clear_history_route(session_id: str = ""):
    if not session_id:
        session_id = str(uuid.uuid4())
    clear_history(session_id)
    return {"status": "cleared", "session_id": session_id}

# ----------------------------------------------------------------------------- #
# ROUTES: Facebook Webhook (GET/POST)
# ----------------------------------------------------------------------------- #
@app.get("/webhook")
async def fb_verify(request: Request):
    """
    ใช้ตอน Verify Callback URL
    Facebook จะส่ง hub.mode / hub.verify_token / hub.challenge มาเป็น query string
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    print(f"VERIFY: mode={mode}, token={token}, challenge={challenge}")

    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        return PlainTextResponse(challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


# ----------------------------------------------------------------------------- #
# POST /webhook (แก้ไขแล้ว: ตอบเฉพาะข้อความ + กันข้อความซ้ำ)
# ----------------------------------------------------------------------------- #
SEEN_MIDS = {}
DUP_TTL = 600

def seen_mid(mid: str) -> bool:
    """คืนค่า True ถ้าเคยเห็น mid นี้แล้ว"""
    now = time.time()
    expired = [k for k, v in SEEN_MIDS.items() if v < now]
    for k in expired:
        del SEEN_MIDS[k]
    if mid in SEEN_MIDS:
        return True
    SEEN_MIDS[mid] = now + DUP_TTL
    return False


@app.post("/webhook")
async def fb_webhook(request: Request):
    raw = await request.body()
    if not verify_signature(FB_APP_SECRET, request.headers.get("X-Hub-Signature-256"), raw):
        raise HTTPException(status_code=403, detail="Bad signature")

    payload = json.loads(raw.decode("utf-8"))
    print("Incoming webhook event:", json.dumps(payload, ensure_ascii=False))

    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event["sender"]["id"]
            session_id = f"fb:{psid}"

            if "message" in event:
                msg = event["message"]

                if msg.get("is_echo"):
                    continue
                if "text" not in msg or not msg["text"].strip():
                    continue

                mid = msg.get("mid")
                if mid and seen_mid(mid):
                    print(f"ข้ามข้อความซ้ำ mid={mid}")
                    continue

                user_text = msg["text"].strip()
                print(f"ข้อความจากผู้ใช้: {user_text}")

                history = get_or_create_history(session_id, context_prompt)
                history.append({"role": "user", "parts": [{"text": user_text}]})
                save_history(session_id, history)

                result = await ask_llm(user_text, session_id, emit_fn=sio.emit)
                reply = (result.get("text") or "").replace("//", " ")
                from_faq = result.get("from_faq", False)

                if from_faq and reply:
                    history.append({"role": "model", "parts": [{"text": reply}]})
                    save_history(session_id, history)

                motion = suggest_pose(reply)
                await sio.emit("ai_response", {"motion": motion, "text": reply})
                await send_fb_text(psid, reply or " ")

            elif "postback" in event:
                payload_str = event["postback"].get("payload", "")
                await send_fb_text(psid, f"ได้รับ postback: {payload_str}")

    return JSONResponse({"status": "ok"})

# ----------------------------------------------------------------------------- #
# START SERVER
# ----------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)
