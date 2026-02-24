"""
SocketIO Event Handlers
จัดการ real-time communication ผ่าน WebSocket
"""
import logging
import os
import hmac
from memory.session import get_or_create_history, save_history, get_bot_enabled

logger = logging.getLogger("SocketIOHandlers")

sio = None
send_fb_text_fn = None
WEB_SESSION_ROOM_PREFIX = "web_session:"


def web_session_room(session_id: str) -> str:
    return f"{WEB_SESSION_ROOM_PREFIX}{str(session_id or '').strip()}"


async def emit_to_web_session(event: str, payload: dict, session_id: str):
    if not sio:
        return
    session_key = str(session_id or "").strip()
    if not session_key:
        return
    await sio.emit(event, payload, room=web_session_room(session_key))


def _is_valid_admin_socket_token(raw_token: str) -> bool:
    token = str(raw_token or "").strip()
    if not token:
        return False
    expected = os.getenv("ADMIN_TOKEN", "super-secret-key")
    return hmac.compare_digest(token, expected)

def init_socketio_handlers(socketio_instance, fb_sender_fn):
    """Initialize SocketIO handlers"""
    global sio, send_fb_text_fn
    sio = socketio_instance
    send_fb_text_fn = fb_sender_fn
    
    sio.on("admin_manual_reply")(handle_admin_manual_reply)
    sio.on("client_register_session")(handle_client_register_session)


async def handle_client_register_session(sid, data):
    session_id = ""
    if isinstance(data, dict):
        session_id = str(data.get("session_id") or "").strip()

    if not session_id:
        logger.warning("Invalid client_register_session payload")
        return

    room = web_session_room(session_id)
    await sio.enter_room(sid, room)
    await sio.emit("session_registered", {"session_id": session_id}, room=sid)
    logger.info(f"Registered sid={sid} to room={room}")

async def handle_admin_manual_reply(sid, data):
    """
    จัดการเมื่อ Admin ส่งข้อความตอบกลับด้วยตนเอง
    
    Args:
        sid: Socket ID
        data: {uid, text, platform}
    """
    if not isinstance(data, dict):
        logger.warning("Invalid admin reply payload type")
        return

    uid = data.get("uid")
    text = data.get("text")
    platform = data.get("platform")
    admin_token = data.get("admin_token")
    
    if not uid or not text:
        logger.warning("⚠️ Invalid admin reply data")
        return

    if not _is_valid_admin_socket_token(admin_token):
        logger.warning("Unauthorized admin_manual_reply attempt")
        await sio.emit("admin_error", {"message": "Unauthorized admin socket action"}, room=sid)
        return
    
    if await get_bot_enabled(uid):
        await sio.emit("admin_error", {
            "message": "กรุณาปิด Auto Bot ก่อนส่งข้อความ"
        }, room=sid)
        return
    
    formatted_msg = f"[Admin]: {text}"
    
    if platform == "facebook":
        fb_psid = uid.replace("fb_", "")
        await send_fb_text_fn(fb_psid, text)
        logger.info(f"📤 Admin replied to FB user {fb_psid}")
    else:
        await emit_to_web_session("ai_response", {
            "motion": "Happy",
            "text": text
        }, uid)
        logger.info(f"📤 Admin replied to web user {uid}")
    
    history = await get_or_create_history(uid)
    history.append({
        "role": "model",
        "parts": [{"text": formatted_msg}]
    })
    await save_history(uid, history)
    
    await sio.emit("admin_bot_reply", {
        "platform": platform,
        "uid": uid,
        "text": formatted_msg
    })
