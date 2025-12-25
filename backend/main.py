from fastapi import FastAPI, Request, UploadFile, Form, HTTPException, Depends, Response
from fastapi.responses import JSONResponse, FileResponse
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
from app.config import BOT_SETTINGS_FILE
from dotenv import load_dotenv
from memory.session import (
    get_or_create_history, 
    save_history, 
    cleanup_old_sessions,
    get_bot_enabled,  # ✅ เพิ่ม import
    set_bot_enabled   # ✅ เพิ่ม import
)

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

# ❌ ลบฟังก์ชัน is_bot_enabled เก่าออก (ไม่ใช้แล้ว)

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

async def fb_worker():
    """Worker สำหรับประมวลผลข้อความจาก Facebook"""
    while True:
        task = await fb_task_queue.get()
        psid = task["psid"]
        user_text = task["text"]
        start_time = time.time()
        
        # ✅ สร้าง session_id แบบ unified (fb_PSID)
        session_id = f"fb_{psid}"
        logger.info(f"📩 Processing FB message: {session_id}")
        
        # ดึงข้อมูลจาก Facebook (ทั้งชื่อและรูป)
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
                        logger.info(f"   👤 User: {user_name}")
            except Exception as e:
                logger.error(f"   ❌ Fetch FB Profile Error: {e}")

        # ✅ แจ้งเตือน Admin ผ่าน Socket พร้อมข้อมูลโปรไฟล์
        await sio.emit("admin_new_message", {
            "platform": "facebook", 
            "uid": session_id,  # ส่ง fb_PSID
            "text": user_text, 
            "user_name": user_name,
            "user_pic": user_pic
        })
        logger.info(f"   📤 Sent to admin: {session_id}")
        
        # ✅ ตรวจสอบ Bot Status จาก Session นี้
        bot_enabled = get_bot_enabled(session_id)
        
        if not bot_enabled:
            logger.info(f"   🤖 Bot disabled for session: {session_id}")
            history = get_or_create_history(session_id, user_name=user_name, user_picture=user_pic, platform="facebook")
            history.append({"role": "user", "parts": [{"text": user_text}]})
            save_history(session_id, history, user_name=user_name, user_picture=user_pic, platform="facebook")
            fb_task_queue.task_done()
            continue

        async with await get_session_lock(session_id):
            try:
                # บันทึกข้อมูล metadata ลง session ก่อนถาม LLM
                get_or_create_history(session_id, user_name=user_name, user_picture=user_pic, platform="facebook")
                
                result = await ask_llm(user_text, session_id, emit_fn=sio.emit)
                reply = result["text"]
                
                # ✅ เพิ่ม [Bot พี่เร็ก] นำหน้าข้อความที่ส่งไปยัง Facebook
                fb_message = f"[Bot พี่เร็ก] {reply.replace('//', '')}"
                await send_fb_text(psid, fb_message)
                
                # ✅ ส่งคำตอบ Bot กลับไปให้ Admin (พร้อม prefix)
                await sio.emit("admin_bot_reply", {
                    "platform": "facebook", 
                    "uid": session_id,  # ส่ง fb_PSID
                    "text": fb_message
                })
                
                write_audit_log(psid, "facebook", user_text, reply, time.time() - start_time)
                logger.info(f"   ✅ Processed successfully")
            except Exception as e: 
                logger.error(f"   ❌ FB Worker Error: {e}")
            finally: 
                fb_task_queue.task_done()

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting application...")
    asyncio.create_task(maintenance_loop())
    for _ in range(5): 
        asyncio.create_task(fb_worker())
    logger.info("✅ Application started")

async def maintenance_loop():
    """งานบำรุงรักษาระบบ"""
    while True:
        cleanup_old_sessions(days=7)
        await asyncio.sleep(86400)

# ----------------------------------------------------------------------------- #
# PUBLIC ENDPOINTS
# ----------------------------------------------------------------------------- #
@app.get("/webhook")
async def fb_verify(request: Request):
    """Webhook Verification สำหรับ Facebook"""
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == FB_VERIFY_TOKEN:
        logger.info("✅ Facebook webhook verified")
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    logger.warning("❌ Invalid verification token")
    return Response(content="Invalid Token", status_code=403)

@app.post("/webhook")
async def fb_webhook(request: Request):
    """รับข้อความจาก Facebook Messenger"""
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8"))
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event and "text" in event["message"] and not event["message"].get("is_echo"):
                    psid = event["sender"]["id"]
                    text = event["message"]["text"].strip()
                    logger.info(f"📨 Received FB message from {psid}")
                    await fb_task_queue.put({"psid": psid, "text": text})
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
    """จัดการข้อความจาก Web Interface"""
    start_time = time.time()
    user_id = auth or "anonymous"
    final_session_id = session_id if session_id else (user_id if user_id != "local-dev-user" else str(uuid.uuid4()))
    final_user_name = user_name or f"Web User {final_session_id[:5]}"
    final_user_pic = user_pic or "https://www.gravatar.com/avatar/?d=mp"
    
    logger.info(f"🌐 Web request from session: {final_session_id}")
    
    if audio:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp:
            temp.write(await audio.read())
            temp_path = temp.name
        try:
            text = await asyncio.get_event_loop().run_in_executor(executor, transcribe, temp_path)
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    if not text:
        return {"text": "", "motion": "Idle"}

    # ✅ แจ้งเตือน Admin
    await sio.emit("admin_new_message", {
        "platform": "web", 
        "uid": final_session_id, 
        "text": text, 
        "user_name": final_user_name,
        "user_pic": final_user_pic
    })

    # ✅ ตรวจสอบ Bot Status จาก Session นี้
    bot_enabled = get_bot_enabled(final_session_id)
    
    if not bot_enabled:
        logger.info(f"   🤖 Bot disabled for session: {final_session_id}")
        history = get_or_create_history(final_session_id, user_name=final_user_name, user_picture=final_user_pic, platform="web")
        history.append({"role": "user", "parts": [{"text": text}]})
        save_history(final_session_id, history, user_name=final_user_name, user_picture=final_user_pic, platform="web")
        return {"text": "ขณะนี้ Bot ปิดให้บริการ (Admin กำลังดูแลคุณ)", "motion": "Idle"}

    async with await get_session_lock(final_session_id):
        get_or_create_history(final_session_id, user_name=final_user_name, user_picture=final_user_pic, platform="web")
        result = await ask_llm(text, final_session_id, emit_fn=sio.emit)
        reply = result["text"]
        motion = await suggest_pose(reply)
        
    write_audit_log(user_id, "web", text, reply, time.time() - start_time)
    
    # ✅ เพิ่ม [Bot พี่เร็ก] นำหน้าข้อความที่ส่งไปยัง Web
    display_text = f"[Bot พี่เร็ก] {reply.replace('//', ' ')}"
    
    await sio.emit("admin_bot_reply", {
        "platform": "web", 
        "uid": final_session_id, 
        "text": display_text
    })
    await sio.emit("ai_response", {"motion": motion, "text": display_text})
    
    logger.info(f"   ✅ Web request processed")
    return {"text": display_text, "motion": motion}

async def send_fb_text(psid: str, text: str):
    """ส่งข้อความกลับไปยัง Facebook"""
    if not FB_PAGE_ACCESS_TOKEN: return
    url = f"{GRAPH_BASE}/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    data = {"recipient": {"id": psid}, "message": {"text": (text or "")[:1999]}}
    async with httpx.AsyncClient(timeout=15) as client: 
        await client.post(url, json=data)

@sio.on("admin_manual_reply")
async def handle_admin_reply(sid, data):
    """จัดการข้อความที่ Admin ส่งกลับ"""
    uid = data.get("uid")
    text = data.get("text")
    platform = data.get("platform")
    
    logger.info(f"👨‍💼 Admin manual reply to {platform}/{uid}")
    
    # ✅ ตรวจสอบ Bot Status ของ Session นี้
    bot_enabled = get_bot_enabled(uid)
    
    if bot_enabled:
        logger.warning(f"   ⚠️ Bot is still enabled for session: {uid}")
        await sio.emit("admin_error", {
            "message": f"กรุณาปิด Auto Bot ของ Session นี้ก่อนส่งข้อความ"
        }, room=sid)
        return

    formatted_msg = f"[Admin]: {text}"

    # ✅ ส่งข้อความไปยังผู้ใช้
    if platform == "facebook":
        # ตัด fb_ ออกเพื่อส่งไปยัง Facebook API (ต้องการแค่ PSID)
        clean_psid = uid.replace("fb_", "")
        await send_fb_text(clean_psid, text)
        logger.info(f"   📤 Sent to Facebook: {clean_psid}")
    else:
        await sio.emit("ai_response", {"motion": "Happy", "text": text})
        logger.info(f"   📤 Sent to Web client")

    # ✅ บันทึกลง session (ใช้ uid ตรงๆ)
    history = get_or_create_history(uid)
    history.append({"role": "model", "parts": [{"text": formatted_msg}]})
    save_history(uid, history)
    
    # ✅ แจ้งกลับไปยัง Admin UI
    await sio.emit("admin_bot_reply", {
        "platform": platform, 
        "uid": uid, 
        "text": formatted_msg
    })
    
    logger.info(f"   ✅ Admin reply processed")

@app.get("/")
async def serve_index(): 
    return FileResponse("frontend/index.html")

@app.get("/admin")
async def serve_admin(): 
    return FileResponse("frontend/admin.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=5000, reload=False)