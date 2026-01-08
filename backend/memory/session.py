import logging
from typing import Optional, List, Dict
from memory.session_db import session_db
from memory.memory import summarize_chat_history

logger = logging.getLogger(__name__)

MAX_HISTORY_LENGTH = 30
NUM_RECENT_TO_KEEP = 10


def get_or_create_history(
    session_id: str, 
    context: str = "", 
    user_name: Optional[str] = None, 
    user_picture: Optional[str] = None, 
    platform: Optional[str] = None
) -> List[Dict]:
    """
    ดึงหรือสร้างประวัติการสนทนา (ใช้ Database)
    
    Args:
        session_id: Session ID
        context: ข้อความเริ่มต้น (optional)
        user_name: ชื่อผู้ใช้
        user_picture: รูปโปรไฟล์
        platform: แพลตฟอร์ม (web, facebook, line)
    
    Returns:
        ประวัติการสนทนาในรูปแบบ list of dict
    """
    try:
        session_data = session_db.get_or_create_session(
            session_id=session_id,
            user_name=user_name,
            user_picture=user_picture,
            platform=platform or "web"
        )
        
        history = session_data['history']
        
        # ถ้ามี context และยังไม่มีข้อความใด ให้เพิ่ม
        if context and len(history) == 0:
            session_db.add_message(session_id, "user", context)
            history.append({
                "role": "user",
                "parts": [{"text": context}]
            })
        
        logger.debug(f"✅ Loaded {len(history)} messages for {session_id}")
        return history
        
    except Exception as e:
        logger.error(f"❌ Error loading session {session_id}: {e}")
        return []


def save_history(
    session_id: str, 
    history: List[Dict], 
    user_name: Optional[str] = None, 
    user_picture: Optional[str] = None, 
    platform: Optional[str] = None
):
    """
    บันทึกประวัติการสนทนา (ใช้ Database)
    ✅ Summary จะถูกเก็บเป็น role="system" ไม่แสดงให้ user เห็น
    
    Args:
        session_id: Session ID
        history: ประวัติการสนทนา
        user_name: ชื่อผู้ใช้ (optional)
        user_picture: รูปโปรไฟล์ (optional)
        platform: แพลตฟอร์ม (optional)
    """
    try:
        # อัปเดต session info ถ้ามี
        if user_name or user_picture or platform:
            session_db.get_or_create_session(
                session_id=session_id,
                user_name=user_name,
                user_picture=user_picture,
                platform=platform
            )
        
        # ลบข้อความซ้ำ
        deduped_history = []
        for entry in history:
            if not deduped_history or deduped_history[-1] != entry:
                deduped_history.append(entry)
        
        # จัดการความยาวของ history
        if len(deduped_history) > MAX_HISTORY_LENGTH:
            # สรุปข้อความเก่า
            to_summarize = deduped_history[:-NUM_RECENT_TO_KEEP]
            recent = deduped_history[-NUM_RECENT_TO_KEEP:]
            
            summary_text = summarize_chat_history(to_summarize)
            
            # ล้างประวัติเก่าและเพิ่มสรุป + ข้อความล่าสุด
            session_db.clear_history(session_id)
            
            # ✅ เพิ่มข้อความสรุปเป็น role="system" (ไม่แสดงให้ user)
            if summary_text:
                session_db.add_message(
                    session_id, 
                    "system",  # ✅ ใช้ "system" แทน "user" หรือ "model"
                    f"[INTERNAL SUMMARY] {summary_text}"
                )
                logger.info(f"📝 Saved summary for {session_id}: {len(summary_text)} chars")
            
            # เพิ่มข้อความล่าสุด
            for msg in recent:
                role = msg.get("role", "user")
                text = msg.get("parts", [{}])[0].get("text", "")
                
                # ✅ กรองเฉพาะ user และ model (ไม่เก็บ system)
                if text and role in ["user", "model"]:
                    session_db.add_message(session_id, role, text)
        else:
            # เพิ่มเฉพาะข้อความใหม่
            current_messages = session_db.get_history(session_id)
            current_count = len(current_messages)
            
            # เพิ่มเฉพาะข้อความที่ยังไม่มีใน DB
            for msg in deduped_history[current_count:]:
                role = msg.get("role", "user")
                text = msg.get("parts", [{}])[0].get("text", "")
                
                # ✅ กรองเฉพาะ user และ model
                if text and role in ["user", "model"]:
                    session_db.add_message(session_id, role, text)
        
        logger.debug(f"✅ Saved history for {session_id}")
        
    except Exception as e:
        logger.error(f"❌ Error saving session {session_id}: {e}")


def get_bot_enabled(session_id: str) -> bool:
    """
    ดึงสถานะ Bot ของ Session นี้
    
    Args:
        session_id: Session ID
    
    Returns:
        True ถ้าเปิด Bot, False ถ้าปิด
    """
    try:
        return session_db.get_bot_enabled(session_id)
    except Exception as e:
        logger.error(f"❌ Error getting bot status for {session_id}: {e}")
        return True  # Default เปิด


def set_bot_enabled(session_id: str, enabled: bool) -> bool:
    """
    ตั้งค่าสถานะ Bot ของ Session นี้
    
    Args:
        session_id: Session ID
        enabled: True เพื่อเปิด, False เพื่อปิด
    
    Returns:
        True ถ้าสำเร็จ
    """
    try:
        success = session_db.set_bot_enabled(session_id, enabled)
        
        if success:
            logger.info(f"✅ Bot {'enabled' if enabled else 'disabled'} for {session_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error setting bot status for {session_id}: {e}")
        return False


def cleanup_old_sessions(days: int = 7) -> int:
    """
    ลบ sessions ที่ไม่มีกิจกรรมเกินจำนวนวันที่กำหนด
    
    Args:
        days: จำนวนวันที่ไม่มีกิจกรรม
    
    Returns:
        จำนวน sessions ที่ถูกลบ
    """
    try:
        count = session_db.cleanup_old_sessions(days)
        logger.info(f"🧹 Cleaned up {count} old sessions")
        return count
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up sessions: {e}")
        return 0


def clear_history(session_id: str):
    """
    ลบประวัติการสนทนาทั้งหมดของ session
    
    Args:
        session_id: Session ID
    """
    try:
        session_db.clear_history(session_id)
        logger.info(f"🗑️ Cleared history for {session_id}")
        
    except Exception as e:
        logger.error(f"❌ Error clearing history for {session_id}: {e}")


def get_visible_history(session_id: str) -> List[Dict]:
    """
    ✅ ดึงประวัติที่แสดงให้ user เห็น (เฉพาะ user และ model)
    ไม่รวม system messages
    
    Args:
        session_id: Session ID
    
    Returns:
        List of visible messages
    """
    try:
        all_history = session_db.get_history(session_id)
        
        # กรองเฉพาะ user และ model
        visible = [
            msg for msg in all_history
            if msg.get("role") in ["user", "model"]
        ]
        
        return visible
        
    except Exception as e:
        logger.error(f"❌ Error getting visible history for {session_id}: {e}")
        return []