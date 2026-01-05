from fastapi import FastAPI, Request, UploadFile, Form, HTTPException, Depends, Response
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
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
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from app.tts import speak
from app.stt import transcribe
from app.utils.llm.llm import ask_llm
from app.utils.pose import suggest_pose
from app.utils.token_counter import calculate_cost
from app.config import BOT_SETTINGS_FILE, PDF_QUICK_USE_FOLDER
from dotenv import load_dotenv
from memory.session import (
    get_or_create_history, 
    save_history, 
    cleanup_old_sessions,
    get_bot_enabled,
    set_bot_enabled
)
# นำเข้า Vector Manager สำหรับระบบ Sync ใน Phase 3
from app.utils.vector_manager import vector_manager

# นำเข้า Admin Router
from router.admin_router import router as admin_router

# ----------------------------------------------------------------------------- #
# SETUP & CONFIG
# ----------------------------------------------------------------------------- #
load_dotenv()
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

executor = ThreadPoolExecutor(max_workers=10)
fb_task_queue = asyncio.Queue()
session_locks = {}

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBackend")

async def get_session_lock(session_id: str):
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

def hash_id(user_id: str) -> str:
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
    """
    เขียน Audit Log พร้อมการติดตาม Token
    """
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

# ----------------------------------------------------------------------------- #
# APP & WORKERS
# ----------------------------------------------------------------------------- #
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])])

# ติดตั้ง Admin Router
app.include_router(admin_router)

asgi_app = socketio.ASGIApp(sio, app)

# เมาท์ static folders
app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

async def sync_vector_db():
    """
    [PHASE 3] ตรวจสอบความเปลี่ยนแปลงของไฟล์ .txt และอัปเดตลง Vector DB อัตโนมัติ
    พร้อม metadata extraction
    """
    def run_sync():
        from app.utils.metadata_extractor import metadata_extractor
        
        logger.info("🔍 [Vector DB] Starting startup synchronization...")
        if not os.path.exists(PDF_QUICK_USE_FOLDER):
            logger.warning(f"⚠️ [Vector DB] Quick-use folder not found: {PDF_QUICK_USE_FOLDER}")
            return

        sync_count = 0
        for root, _, files in os.walk(PDF_QUICK_USE_FOLDER):
            for filename in sorted(files):
                if filename.endswith(".txt"):
                    filepath = os.path.join(root, filename)
                    needs_upd, file_hash = vector_manager.needs_update(filepath)
                    
                    if needs_upd:
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                            
                            # แบ่งข้อมูลโดยใช้ separator มาตรฐาน
                            separator = "==================="
                            chunks = [c.strip() for c in content.split(separator) if c.strip()]
                            
                            # ✅ Extract metadata
                            metadata = metadata_extractor.extract(content, filepath)
                            
                            # ✅ Add with metadata
                            vector_manager.add_document(filepath, chunks, metadata)
                            vector_manager.update_registry(filepath, file_hash)
                            sync_count += 1
                        except Exception as e:
                            logger.error(f"❌ [Vector DB] Sync failed for {filename}: {e}")
        
        if sync_count > 0:
            logger.info(f"✅ [Vector DB] Synchronization complete. Updated {sync_count} files.")
        else:
            logger.info("✅ [Vector DB] Database is already up-to-date.")

    # รันใน Thread เพื่อไม่ให้บล็อกการทำงานหลัก
    await asyncio.to_thread(run_sync)

async def build_hybrid_index():
    """
    [PHASE 3] Build BM25 index for hybrid search
    """
    def run_build():
        from retriever.hybrid_retriever import hybrid_retriever
        
        logger.info("🔨 [Hybrid] Building BM25 index...")
        
        # Get all chunks from vector database
        chunks = vector_manager.get_all_chunks()
        
        if not chunks:
            logger.warning("⚠️ [Hybrid] No chunks found in vector DB")
            return
        
        # Build BM25 index
        hybrid_retriever.build_index(chunks)
        logger.info(f"✅ [Hybrid] BM25 index ready with {len(chunks)} chunks")
    
    await asyncio.to_thread(run_build)

async def maintenance_loop():
    """งานบำรุงรักษาระบบรายวัน"""
    while True:
        try:
            # Cleanup old sessions (older than 7 days)
            cleanup_old_sessions(days=7)
            logger.info("🧹 Maintenance: Old sessions cleaned up")
        except Exception as e:
            logger.error(f"❌ Maintenance error: {e}")
        
        # Sleep for 24 hours
        await asyncio.sleep(86400)

async def fb_worker():
    """Worker สำหรับจัดการข้อความจาก Facebook Messenger"""
    from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
    
    while True:
        task = await fb_task_queue.get()
        psid = task["psid"]
        user_text = task["text"]
        start_time = time.time()
        
        session_id = f"fb_{psid}"
        logger.info(f"📩 Processing FB message: {session_id}")
        
        user_name = f"FB User {psid[:5]}"
        user_pic = "https://www.gravatar.com/avatar/?d=mp"
        
        if FB_PAGE_ACCESS_TOKEN:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"https://graph.facebook.com/{psid}?fields=name,picture&access_token={FB_PAGE_ACCESS_TOKEN}", 
                        timeout=3
                    )
                    if r.status_code == 200:
                        data = r.json()
                        user_name = data.get("name", user_name)
                        user_pic = data.get("picture", {}).get("data", {}).get("url", user_pic)
            except Exception as e:
                logger.error(f"❌ Fetch FB Profile Error: {e}")

        await sio.emit("admin_new_message", {
            "platform": "facebook", "uid": session_id, "text": user_text, 
            "user_name": user_name, "user_pic": user_pic
        })
        
        bot_enabled = get_bot_enabled(session_id)
        if not bot_enabled:
            history = get_or_create_history(session_id, user_name=user_name, user_picture=user_pic, platform="facebook")
            history.append({"role": "user", "parts": [{"text": user_text}]})
            save_history(session_id, history, user_name=user_name, user_picture=user_pic, platform="facebook")
            fb_task_queue.task_done()
            continue

        async with await get_session_lock(session_id):
            try:
                get_or_create_history(session_id, user_name=user_name, user_picture=user_pic, platform="facebook")
                result = await ask_llm(user_text, session_id, emit_fn=sio.emit)
                reply = result["text"]
                tokens = result.get("tokens", {})
                
                fb_message = f"[Bot พี่เร็ก] {reply.replace('//', '')}"
                await send_fb_text(psid, fb_message)
                
                await sio.emit("admin_bot_reply", {"platform": "facebook", "uid": session_id, "text": fb_message})
                
                model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else (OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME)
                write_audit_log(psid, "facebook", user_text, reply, time.time() - start_time, tokens=tokens, model_name=model_name)
            except Exception as e: 
                logger.error(f"❌ FB Worker Error: {e}")
            finally: 
                fb_task_queue.task_done()

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting application...")
    
    # [PHASE 3] ซิงค์ข้อมูลลง Vector DB ตอนเริ่มต้น
    await sync_vector_db()
    
    # ✅ [PHASE 3] Build hybrid search index
    await build_hybrid_index()
    
    # Start background tasks
    asyncio.create_task(maintenance_loop())
    for _ in range(5): 
        asyncio.create_task(fb_worker())
    
    logger.info("✅ Application, Vector DB, and Hybrid Search are ready")

# ----------------------------------------------------------------------------- #
# PUBLIC ENDPOINTS
# ----------------------------------------------------------------------------- #
@app.get("/webhook")
async def fb_verify(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(content="Invalid Token", status_code=403)

@app.post("/webhook")
async def fb_webhook(request: Request):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8"))
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event and "text" in event["message"] and not event["message"].get("is_echo"):
                    await fb_task_queue.put({"psid": event["sender"]["id"], "text": event["message"]["text"].strip()})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
    return JSONResponse({"status": "accepted"})

@app.post("/api/speech")
async def handle_speech(
    request: Request,
    text: str = Form(None),
    session_id: str = Form(None),
    user_name: str = Form(None),
    user_pic: str = Form(None),
    audio: UploadFile = Form(None),
    auth: str = Depends(APIKeyHeader(name="X-API-Key", auto_error=False))
):
    from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
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
            if os.path.exists(temp_path): os.remove(temp_path)

    if not text: return {"text": "", "motion": "Idle"}
    
    await sio.emit("admin_new_message", {
        "platform": "web", "uid": final_session_id, "text": text, 
        "user_name": final_user_name, "user_pic": final_user_pic
    })

    bot_enabled = get_bot_enabled(final_session_id)
    if not bot_enabled:
        history = get_or_create_history(final_session_id, user_name=final_user_name, user_picture=final_user_pic, platform="web")
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(final_session_id, history, user_name=final_user_name, user_picture=final_user_pic, platform="web")
        return {"text": "ขณะนี้ Bot ปิดให้บริการ (Admin กำลังดูแลคุณ)", "motion": "Idle"}

    async with await get_session_lock(final_session_id):
        get_or_create_history(final_session_id, user_name=final_user_name, user_picture=final_user_pic, platform="web")
        result = await ask_llm(text, final_session_id, emit_fn=sio.emit)
        reply = result["text"]
        motion = await suggest_pose(reply)
        tokens = result.get("tokens", {})
    
    model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else (OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME)
    write_audit_log(user_id, "web", text, reply, time.time() - start_time, tokens=tokens, model_name=model_name)
    
    display_text = f"[Bot พี่เร็ก] {reply.replace('//', ' ')}"
    await sio.emit("admin_bot_reply", {"platform": "web", "uid": final_session_id, "text": display_text})
    await sio.emit("ai_response", {"motion": motion, "text": display_text})
    
    return {"text": display_text, "motion": motion}

@app.post("/api/speak")
async def text_to_speech(text: str = Form(...)):
    """แปลงข้อความเป็นเสียงและส่งแบบ Streaming"""
    async def audio_stream():
        try:
            async for chunk in speak(text): yield chunk
        except Exception: yield b'\x00' * 1024
    return StreamingResponse(audio_stream(), media_type="audio/mpeg")

async def send_fb_text(psid: str, text: str):
    """ส่งข้อความกลับไปยัง Facebook API"""
    if not FB_PAGE_ACCESS_TOKEN: return
    url = f"{GRAPH_BASE}/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    data = {"recipient": {"id": psid}, "message": {"text": (text or "")[:1999]}}
    async with httpx.AsyncClient(timeout=15) as client: 
        await client.post(url, json=data)

@sio.on("admin_manual_reply")
async def handle_admin_reply(sid, data):
    """จัดการเมื่อ Admin พิมพ์ตอบเอง"""
    uid, text, platform = data.get("uid"), data.get("text"), data.get("platform")
    if get_bot_enabled(uid):
        await sio.emit("admin_error", {"message": "กรุณาปิด Auto Bot ก่อนส่งข้อความ"}, room=sid)
        return
    formatted_msg = f"[Admin]: {text}"
    if platform == "facebook":
        await send_fb_text(uid.replace("fb_", ""), text)
    else:
        await sio.emit("ai_response", {"motion": "Happy", "text": text})
        
    history = get_or_create_history(uid)
    history.append({"role": "model", "parts": [{"text": formatted_msg}]})
    save_history(uid, history)
    await sio.emit("admin_bot_reply", {"platform": platform, "uid": uid, "text": formatted_msg})

@app.get("/")
async def serve_index(): return FileResponse("frontend/index.html")

@app.get("/admin")
async def serve_admin(): return FileResponse("frontend/admin.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)