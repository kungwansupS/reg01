"""
SocketIO Event Handlers
จัดการ real-time communication ผ่าน WebSocket
"""
import httpx
import logging
from memory.session import get_or_create_history, save_history, get_bot_enabled

logger = logging.getLogger("SocketIOHandlers")

# ✅ Global references
sio = None
send_fb_text_fn = None

def init_socketio_handlers(socketio_instance, fb_sender_fn):
    """Initialize SocketIO handlers"""
    global sio, send_fb_text_fn
    sio = socketio_instance
    send_fb_text_fn = fb_sender_fn
    
    # Register handlers
    sio.on("admin_manual_reply")(handle_admin_manual_reply)

async def handle_admin_manual_reply(sid, data):
    """
    จัดการเมื่อ Admin ส่งข้อความตอบกลับด้วยตนเอง
    
    Args:
        sid: Socket ID
        data: {uid, text, platform}
    """
    uid = data.get("uid")
    text = data.get("text")
    platform = data.get("platform")
    
    if not uid or not text:
        logger.warning("⚠️ Invalid admin reply data")
        return
    
    # ✅ Check if bot is enabled
    if get_bot_enabled(uid):
        await sio.emit("admin_error", {
            "message": "กรุณาปิด Auto Bot ก่อนส่งข้อความ"
        }, room=sid)
        return
    
    formatted_msg = f"[Admin]: {text}"
    
    # ✅ Send to appropriate platform
    if platform == "facebook":
        fb_psid = uid.replace("fb_", "")
        await send_fb_text_fn(fb_psid, text)
        logger.info(f"📤 Admin replied to FB user {fb_psid}")
    else:
        # Send to web client
        await sio.emit("ai_response", {
            "motion": "Happy",
            "text": text
        })
        logger.info(f"📤 Admin replied to web user {uid}")
    
    # ✅ Save to history
    history = get_or_create_history(uid)
    history.append({
        "role": "model",
        "parts": [{"text": formatted_msg}]
    })
    save_history(uid, history)
    
    # ✅ Broadcast to admin dashboard
    await sio.emit("admin_bot_reply", {
        "platform": platform,
        "uid": uid,
        "text": formatted_msg
    })
