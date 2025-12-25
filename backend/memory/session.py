import os
import json
import time
from app.config import SESSION_DIR
from memory.memory import summarize_chat_history

# ตรวจสอบและสร้างโฟลเดอร์เก็บ Session และ Logs
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR, exist_ok=True)
if not os.path.exists("logs"):
    os.makedirs("logs", exist_ok=True)

MAX_HISTORY_LENGTH = 30
NUM_RECENT_TO_KEEP = 10

def get_session_path(session_id):
    """สร้าง Path สำหรับไฟล์ JSON โดยล้างอักขระพิเศษเพื่อความปลอดภัย"""
    safe_id = "".join([c for c in str(session_id) if c.isalnum() or c in ("-", "_")])
    return os.path.join(SESSION_DIR, f"{safe_id}.json")

def get_or_create_history(session_id, context="", user_name=None, user_picture=None, platform=None):
    """ดึงหรือสร้างประวัติการแชท พร้อมจัดการ Migration ข้อมูลเก่าอัตโนมัติ"""
    path = get_session_path(session_id)
    
    is_fb = str(session_id).startswith("fb_")
    detected_platform = platform or ("facebook" if is_fb else "web")
    clean_uid = str(session_id).replace("fb_", "")
    
    default_name = f"{detected_platform.capitalize()} User {clean_uid[:5]}"
    final_pic = user_picture or "https://www.gravatar.com/avatar/?d=mp"

    data_to_save = None

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Migration Logic: เปลี่ยนจาก List เป็น Dict อัตโนมัติ
                if isinstance(data, list):
                    data = {
                        "user_info": {
                            "name": user_name or default_name,
                            "picture": final_pic,
                            "platform": detected_platform
                        },
                        "bot_enabled": True,  # ✅ Default เปิด Bot
                        "history": data
                    }
                    data_to_save = data
                
                # อัปเดต Metadata หากมีข้อมูลใหม่ส่งเข้ามา
                if "user_info" not in data:
                    data["user_info"] = {"name": default_name, "picture": final_pic, "platform": detected_platform}
                    data_to_save = data
                
                # ✅ เพิ่ม bot_enabled ถ้ายังไม่มี (Default = True)
                if "bot_enabled" not in data:
                    data["bot_enabled"] = True
                    data_to_save = data
                
                if user_name and data["user_info"].get("name") != user_name:
                    data["user_info"]["name"] = user_name
                    data_to_save = data
                
                if user_picture and data["user_info"].get("picture") != user_picture:
                    data["user_info"]["picture"] = user_picture
                    data_to_save = data

                if data_to_save:
                    save_history(session_id, data.get("history", []), **data["user_info"])
                
                return data.get("history", [])
        except Exception as e:
            print(f"Error reading session {session_id}: {e}")
            return []

    # กรณีสร้างใหม่
    initial_history = [{"role": "user", "parts": [{"text": context}]}] if context else []
    new_session_data = {
        "user_info": {
            "name": user_name or default_name,
            "picture": final_pic,
            "platform": detected_platform
        },
        "bot_enabled": True,  # ✅ Default เปิด Bot
        "history": initial_history
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(new_session_data, f, ensure_ascii=False, indent=2)
    return new_session_data["history"]

def save_history(session_id, history, user_name=None, user_picture=None, platform=None):
    path = get_session_path(session_id)
    
    is_fb = str(session_id).startswith("fb_")
    detected_platform = platform or ("facebook" if is_fb else "web")
    clean_uid = str(session_id).replace("fb_", "")
    
    # ดึงข้อมูลเดิมมาตั้งต้น
    user_info = {
        "name": user_name or f"{detected_platform.capitalize()} User {clean_uid[:5]}", 
        "picture": user_picture or "https://www.gravatar.com/avatar/?d=mp", 
        "platform": detected_platform
    }
    
    bot_enabled = True  # Default
    
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if isinstance(old_data, dict):
                    user_info = old_data.get("user_info", user_info)
                    bot_enabled = old_data.get("bot_enabled", True)  # ✅ เก็บค่าเดิม
        except: pass

    # อัปเดต Metadata ใหม่ถ้ามีข้อมูลส่งมา
    if user_name: user_info["name"] = user_name
    if user_picture: user_info["picture"] = user_picture
    if detected_platform: user_info["platform"] = detected_platform

    deduped_history = []
    for entry in history:
        if not deduped_history or deduped_history[-1] != entry:
            deduped_history.append(entry)

    if len(deduped_history) > MAX_HISTORY_LENGTH:
        to_summarize = deduped_history[:-NUM_RECENT_TO_KEEP]
        recent = deduped_history[-NUM_RECENT_TO_KEEP:]
        summary_text = summarize_chat_history(to_summarize)
        deduped_history = [{
            "role": "system",
            "parts": [{"text": f"สรุปบทสนทนาก่อนหน้านี้:\n{summary_text}"}]
        }] + recent

    final_data = {
        "user_info": user_info,
        "bot_enabled": bot_enabled,  # ✅ เก็บสถานะ Bot
        "history": deduped_history
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

def get_bot_enabled(session_id):
    """✅ ฟังก์ชันใหม่: ดึงสถานะ Bot ของ Session นี้"""
    path = get_session_path(session_id)
    if not os.path.exists(path):
        return True  # Default เปิด
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("bot_enabled", True)
    except:
        return True

def set_bot_enabled(session_id, enabled):
    """✅ ฟังก์ชันใหม่: ตั้งค่าสถานะ Bot ของ Session นี้"""
    path = get_session_path(session_id)
    if not os.path.exists(path):
        # สร้าง session ใหม่ถ้ายังไม่มี
        get_or_create_history(session_id)
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        data["bot_enabled"] = enabled
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error setting bot_enabled for {session_id}: {e}")
        return False

def cleanup_old_sessions(days=7):
    """ลบเซสชันที่ไม่มีความเคลื่อนไหวเกินจำนวนวันที่กำหนด"""
    try:
        cutoff = time.time() - (days * 86400)
        count = 0
        for filename in os.listdir(SESSION_DIR):
            if filename.endswith(".json"):
                path = os.path.join(SESSION_DIR, filename)
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    count += 1
        return count
    except: return 0

def clear_history(session_id):
    path = get_session_path(session_id)
    if os.path.exists(path):
        os.remove(path)