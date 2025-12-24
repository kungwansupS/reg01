from fastapi import FastAPI, Request, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
import socketio
import tempfile
import os
import uuid
import json
import hmac
import hashlib
import httpx
import redis
import logging

from app.config import FB_PAGE_ACCESS_TOKEN, FB_VERIFY_TOKEN, FB_APP_SECRET, REDIS_URL
from app.tts import speak
from app.stt import transcribe
from app.prompt.prompt import context_prompt
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from memory.session import clear_history, get_or_create_history, save_history

logger = logging.getLogger(__name__)

# Redis for Duplicate Checking
try:
    r_mid = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    r_mid.ping()
    USE_REDIS_MID = True
except:
    USE_REDIS_MID = False
    SEEN_MIDS_LOCAL = {}

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])])
asgi_app = socketio.ASGIApp(sio, app)

app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

@app.get("/")
async def serve_index(): return FileResponse("frontend/index.html")

def seen_mid(mid: str) -> bool:
    if USE_REDIS_MID:
        key = f"mid:{mid}"
        if r_mid.exists(key): return True
        r_mid.setex(key, 600, "1")
        return False
    else:
        if mid in SEEN_MIDS_LOCAL: return True
        SEEN_MIDS_LOCAL[mid] = os.times().elapsed
        return False

async def send_fb_text(psid: str, text: str):
    if not FB_PAGE_ACCESS_TOKEN: return
    url = f"https://graph.facebook.com/v19.0/me/messages"
    data = {"recipient": {"id": psid}, "messaging_type": "RESPONSE", "message": {"text": (text or "")[:1999]}}
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(url, params={"access_token": FB_PAGE_ACCESS_TOKEN}, json=data)

@app.post("/api/speech")
async def handle_speech(request: Request, text: str = Form(None), session_id: str = Form(None), audio: UploadFile = Form(None)):
    session_id = session_id or str(uuid.uuid4())
    if audio:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(await audio.read())
            text = transcribe(tmp.name)
        await sio.emit("subtitle", {"speaker": "user", "text": text.replace("//", " ")})

    if not text or text == "❌ ไม่เข้าใจเสียง": return {"text": "", "motion": ""}

    history = get_or_create_history(session_id, context_prompt)
    history.append({"role": "user", "parts": [{"text": text}]})
    save_history(session_id, history)

    result = await ask_llm(text, session_id, emit_fn=sio.emit)
    reply = result["text"]
    motion = suggest_pose(reply)

    await sio.emit("ai_response", {"motion": motion, "text": reply.replace("//", " ")})
    return {"text": reply, "motion": motion}

@app.post("/api/speak")
async def handle_speak(text: str = Form(...)):
    async def generate():
        async for chunk in speak(text): yield chunk
        await sio.emit("speech_done")
    return StreamingResponse(generate(), media_type="audio/mpeg")

@app.get("/webhook")
async def fb_verify(request: Request):
    if request.query_params.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return PlainTextResponse(request.query_params.get("hub.challenge"))
    raise HTTPException(status_code=403)

@app.post("/webhook")
async def fb_webhook(request: Request):
    payload = json.loads((await request.body()).decode("utf-8"))
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event["sender"]["id"]
            if "message" in event and "text" in event["message"] and not event["message"].get("is_echo"):
                mid = event["message"].get("mid")
                if mid and seen_mid(mid): continue
                user_text = event["message"]["text"]
                history = get_or_create_history(f"fb:{psid}", context_prompt)
                history.append({"role": "user", "parts": [{"text": user_text}]})
                save_history(f"fb:{psid}", history)
                result = await ask_llm(user_text, f"fb:{psid}", emit_fn=sio.emit)
                await send_fb_text(psid, result["text"])
    return JSONResponse({"status": "ok"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000)