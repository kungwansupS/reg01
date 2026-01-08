"""
Chat Router
จัดการ API สำหรับ chat interface (speech, text, TTS)
"""
from fastapi import APIRouter, Request, UploadFile, Form, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import StreamingResponse
import tempfile
import os
import uuid
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.tts import speak
from app.stt import transcribe
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from app.utils.token_counter import calculate_cost
from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
from memory.session import get_or_create_history, save_history, get_bot_enabled

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("ChatRouter")

executor = ThreadPoolExecutor(max_workers=10)

sio = None
session_locks = {}
audit_logger = None

def init_chat_router(socketio_instance, locks_dict, audit_log_fn):
    """Initialize router with dependencies"""
    global sio, session_locks, audit_logger
    sio = socketio_instance
    session_locks = locks_dict
    audit_logger = audit_log_fn

async def get_session_lock(session_id: str):
    """Get or create session lock"""
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

@router.post("/speech")
async def handle_speech(
    request: Request,
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
    user_id = auth or "anonymous"
    final_session_id = session_id if session_id else (user_id if user_id != "local-dev-user" else str(uuid.uuid4()))
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
        return {"text": "", "motion": "Idle"}
    
    await sio.emit("admin_new_message", {
        "platform": "web",
        "uid": final_session_id,
        "text": text,
        "user_name": final_user_name,
        "user_pic": final_user_pic
    })

    bot_enabled = get_bot_enabled(final_session_id)
    if not bot_enabled:
        history = get_or_create_history(
            final_session_id,
            user_name=final_user_name,
            user_picture=final_user_pic,
            platform="web"
        )
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(
            final_session_id,
            history,
            user_name=final_user_name,
            user_picture=final_user_pic,
            platform="web"
        )
        return {"text": "ขณะนี้ Bot ปิดให้บริการ (Admin กำลังดูแลคุณ)", "motion": "Idle"}

    async with await get_session_lock(final_session_id):
        get_or_create_history(
            final_session_id,
            user_name=final_user_name,
            user_picture=final_user_pic,
            platform="web"
        )
        
        result = await ask_llm(text, final_session_id, emit_fn=sio.emit)
        reply = result["text"]
        motion = await suggest_pose(reply)
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
            model_name=model_name
        )
    
    display_text = f"[Bot พี่เร็ก] {reply.replace('//', '')}"
    await sio.emit("admin_bot_reply", {
        "platform": "web",
        "uid": final_session_id,
        "text": display_text
    })
    await sio.emit("ai_response", {
        "motion": motion,
        "text": display_text
    })
    
    return {"text": display_text, "motion": motion}

@router.post("/speak")
async def text_to_speech(text: str = Form(...)):
    """
    Convert text to speech (TTS)
    Returns audio stream in MP3 format
    """
    async def audio_stream():
        try:
            async for chunk in speak(text):
                yield chunk
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            yield b'\x00' * 1024
    
    return StreamingResponse(audio_stream(), media_type="audio/mpeg")
