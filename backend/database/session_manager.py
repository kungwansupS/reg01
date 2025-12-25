# backend/database/session_manager.py
"""
Session Manager with Database Backend
แทนที่ระบบ JSON file เดิม
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.exc import SQLAlchemyError

from database.connection import get_db
from database.models import User, Message, Session, FAQ

logger = logging.getLogger(__name__)

# ========================================================================
# Session Management
# ========================================================================

def get_or_create_user(
    session_id: str,
    platform: str = "web",
    user_name: str = None,
    user_picture: str = None
) -> User:
    """
    ดึงหรือสร้าง User
    
    Args:
        session_id: Unique session ID
        platform: facebook, web, line
        user_name: ชื่อผู้ใช้
        user_picture: URL รูปโปรไฟล์
    
    Returns:
        User object
    """
    with get_db() as db:
        # ลองหา user ที่มีอยู่
        user = db.query(User).filter(User.session_id == session_id).first()
        
        if user:
            # อัปเดตข้อมูล
            updated = False
            
            if user_name and user.name != user_name:
                user.name = user_name
                updated = True
            
            if user_picture and user.picture_url != user_picture:
                user.picture_url = user_picture
                updated = True
            
            # อัปเดต last_active
            user.last_active = datetime.utcnow()
            
            if updated:
                db.commit()
            
            logger.debug(f"✅ Retrieved existing user: {session_id}")
            return user
        
        # สร้างใหม่
        clean_uid = session_id.replace("fb_", "")
        default_name = f"{platform.capitalize()} User {clean_uid[:5]}"
        default_pic = "https://www.gravatar.com/avatar/?d=mp"
        
        user = User(
            session_id=session_id,
            platform=platform,
            name=user_name or default_name,
            picture_url=user_picture or default_pic,
            bot_enabled=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"✨ Created new user: {session_id}")
        return user


def get_or_create_history(
    session_id: str,
    context: str = "",
    user_name: str = None,
    user_picture: str = None,
    platform: str = None
) -> List[Dict]:
    """
    ดึงประวัติการสนทนา (รูปแบบเดิม - backward compatible)
    
    Returns:
        List of message dicts เหมือนระบบ JSON เดิม
    """
    # ตรวจจับ platform จาก session_id
    if not platform:
        platform = "facebook" if session_id.startswith("fb_") else "web"
    
    with get_db() as db:
        # ดึงหรือสร้าง user
        user = get_or_create_user(session_id, platform, user_name, user_picture)
        
        # ดึงข้อความล่าสุด 30 ข้อความ
        messages = db.query(Message)\
            .filter(Message.user_id == user.id)\
            .order_by(Message.created_at.desc())\
            .limit(30)\
            .all()
        
        # แปลงเป็นรูปแบบเดิม
        history = []
        
        if context:
            history.append({
                "role": "system",
                "parts": [{"text": context}]
            })
        
        # เรียงจากเก่า → ใหม่
        for msg in reversed(messages):
            history.append(msg.to_dict())
        
        logger.debug(f"📖 Retrieved {len(messages)} messages for {session_id}")
        return history


def save_history(
    session_id: str,
    history: List[Dict],
    user_name: str = None,
    user_picture: str = None,
    platform: str = None
) -> bool:
    """
    บันทึกประวัติการสนทนา
    
    Args:
        session_id: Unique session ID
        history: List of message dicts
        user_name: ชื่อผู้ใช้
        user_picture: URL รูปโปรไฟล์
        platform: facebook, web, line
    
    Returns:
        bool: สำเร็จหรือไม่
    """
    if not platform:
        platform = "facebook" if session_id.startswith("fb_") else "web"
    
    try:
        with get_db() as db:
            # ดึงหรือสร้าง user
            user = get_or_create_user(session_id, platform, user_name, user_picture)
            
            # ดึงข้อความที่มีอยู่แล้ว
            existing_messages = db.query(Message)\
                .filter(Message.user_id == user.id)\
                .order_by(Message.created_at)\
                .all()
            
            existing_count = len(existing_messages)
            
            # บันทึกเฉพาะข้อความใหม่
            new_messages = []
            for i, msg in enumerate(history):
                # ข้าม system messages และข้อความเก่า
                if msg.get("role") == "system":
                    continue
                
                if i < existing_count:
                    continue
                
                # สร้าง Message object
                message = Message(
                    user_id=user.id,
                    role=msg.get("role", "user"),
                    content=msg.get("parts", [{}])[0].get("text", ""),
                    motion=msg.get("motion"),
                    latency=msg.get("latency"),
                    from_faq=msg.get("from_faq", False)
                )
                new_messages.append(message)
            
            if new_messages:
                db.bulk_save_objects(new_messages)
                logger.info(f"💾 Saved {len(new_messages)} new messages for {session_id}")
            
            # จำกัดจำนวนข้อความ (เก็บไว้แค่ 100 ข้อความล่าสุด)
            total_messages = existing_count + len(new_messages)
            if total_messages > 100:
                # ลบข้อความเก่า
                old_messages = db.query(Message)\
                    .filter(Message.user_id == user.id)\
                    .order_by(Message.created_at)\
                    .limit(total_messages - 100)\
                    .all()
                
                for old_msg in old_messages:
                    db.delete(old_msg)
                
                logger.info(f"🗑️ Cleaned up {len(old_messages)} old messages")
            
            db.commit()
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to save history: {e}")
        return False


def get_bot_enabled(session_id: str) -> bool:
    """
    ตรวจสอบสถานะ Bot
    
    Args:
        session_id: Unique session ID
    
    Returns:
        bool: Bot เปิดอยู่หรือไม่
    """
    try:
        with get_db() as db:
            user = db.query(User).filter(User.session_id == session_id).first()
            
            if user:
                return user.bot_enabled
            
            # Default: เปิด
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to get bot status: {e}")
        return True


def set_bot_enabled(session_id: str, enabled: bool) -> bool:
    """
    ตั้งค่าสถานะ Bot
    
    Args:
        session_id: Unique session ID
        enabled: เปิดหรือปิด Bot
    
    Returns:
        bool: สำเร็จหรือไม่
    """
    try:
        with get_db() as db:
            user = db.query(User).filter(User.session_id == session_id).first()
            
            if not user:
                # สร้าง user ใหม่
                platform = "facebook" if session_id.startswith("fb_") else "web"
                user = get_or_create_user(session_id, platform)
            
            user.bot_enabled = enabled
            db.commit()
            
            logger.info(f"🔄 Set bot_enabled={enabled} for {session_id}")
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to set bot status: {e}")
        return False


def cleanup_old_sessions(days: int = 7) -> int:
    """
    ลบ sessions เก่าที่ไม่ได้ใช้งาน
    
    Args:
        days: จำนวนวันที่ไม่มีการใช้งาน
    
    Returns:
        int: จำนวน users ที่ถูกลบ
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with get_db() as db:
            # หา users ที่ไม่ได้ใช้งานนาน
            old_users = db.query(User)\
                .filter(User.last_active < cutoff_date)\
                .all()
            
            count = len(old_users)
            
            if count > 0:
                # ลบ users (messages จะถูกลบอัตโนมัติเพราะ cascade)
                for user in old_users:
                    db.delete(user)
                
                db.commit()
                logger.info(f"🗑️ Cleaned up {count} old sessions")
            
            return count
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Cleanup failed: {e}")
        return 0


def clear_history(session_id: str) -> bool:
    """
    ล้างประวัติการสนทนา
    
    Args:
        session_id: Unique session ID
    
    Returns:
        bool: สำเร็จหรือไม่
    """
    try:
        with get_db() as db:
            user = db.query(User).filter(User.session_id == session_id).first()
            
            if user:
                # ลบข้อความทั้งหมด
                db.query(Message).filter(Message.user_id == user.id).delete()
                db.commit()
                logger.info(f"🗑️ Cleared history for {session_id}")
                return True
            
            return False
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Failed to clear history: {e}")
        return False


# ========================================================================
# Migration Helper
# ========================================================================

def migrate_from_json(json_dir: str = "backend/memory/session_storage") -> Dict:
    """
    ย้ายข้อมูลจาก JSON files ไปยัง Database
    
    Args:
        json_dir: โฟลเดอร์ที่เก็บ JSON files
    
    Returns:
        dict: สถิติการย้ายข้อมูล
    """
    import json
    import glob
    
    stats = {
        'total_files': 0,
        'migrated': 0,
        'failed': 0,
        'skipped': 0
    }
    
    if not os.path.exists(json_dir):
        logger.warning(f"⚠️ JSON directory not found: {json_dir}")
        return stats
    
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    stats['total_files'] = len(json_files)
    
    logger.info(f"🔄 Starting migration of {len(json_files)} JSON files...")
    
    for json_file in json_files:
        try:
            # อ่าน JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ดึง session_id จากชื่อไฟล์
            session_id = os.path.basename(json_file).replace('.json', '')
            
            # ตรวจสอบว่ามีอยู่แล้วหรือไม่
            with get_db() as db:
                existing = db.query(User).filter(User.session_id == session_id).first()
                if existing:
                    stats['skipped'] += 1
                    continue
            
            # แปลงข้อมูล
            if isinstance(data, dict):
                user_info = data.get('user_info', {})
                history = data.get('history', [])
                bot_enabled = data.get('bot_enabled', True)
            else:
                # รูปแบบเก่า (array)
                user_info = {}
                history = data
                bot_enabled = True
            
            platform = user_info.get('platform', 'web')
            user_name = user_info.get('name')
            user_picture = user_info.get('picture')
            
            # สร้าง user
            user = get_or_create_user(session_id, platform, user_name, user_picture)
            
            # ตั้งค่า bot_enabled
            with get_db() as db:
                db_user = db.query(User).filter(User.id == user.id).first()
                db_user.bot_enabled = bot_enabled
                db.commit()
            
            # บันทึก messages
            save_history(session_id, history, user_name, user_picture, platform)
            
            stats['migrated'] += 1
            logger.info(f"✅ Migrated: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate {json_file}: {e}")
            stats['failed'] += 1
    
    logger.info(f"✅ Migration completed: {stats['migrated']} migrated, {stats['skipped']} skipped, {stats['failed']} failed")
    return stats


# ========================================================================
# Export Helper
# ========================================================================

def export_to_json(output_dir: str = "backend/database/exports") -> bool:
    """
    Export ข้อมูลจาก Database กลับไปเป็น JSON
    
    Args:
        output_dir: โฟลเดอร์สำหรับเก็บ JSON files
    
    Returns:
        bool: สำเร็จหรือไม่
    """
    import json
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        with get_db() as db:
            users = db.query(User).all()
            
            for user in users:
                # ดึงข้อความทั้งหมด
                messages = db.query(Message)\
                    .filter(Message.user_id == user.id)\
                    .order_by(Message.created_at)\
                    .all()
                
                # สร้าง JSON structure
                data = {
                    'user_info': {
                        'name': user.name,
                        'picture': user.picture_url,
                        'platform': user.platform
                    },
                    'bot_enabled': user.bot_enabled,
                    'history': [msg.to_dict() for msg in messages]
                }
                
                # บันทึกเป็น JSON
                filename = os.path.join(output_dir, f"{user.session_id}.json")
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Exported {len(users)} sessions to {output_dir}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Export failed: {e}")
        return False
