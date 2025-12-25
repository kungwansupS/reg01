import os
import json
import time
from app.config import SESSION_DIR
from memory.memory import summarize_chat_history

# สร้างโฟลเดอร์เก็บ Session และ Logs หากยังไม่มี
os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

MAX_HISTORY_LENGTH = 30
NUM_RECENT_TO_KEEP = 10

def get_session_path(session_id):
    # ปรับให้ปลอดภัยต่อการตั้งชื่อไฟล์ (รองรับ id ที่มีอักขระพิเศษ)
    safe_id = "".join([c for c in str(session_id) if c.isalnum() or c in ("-", "_")])
    return os.path.join(SESSION_DIR, f"{safe_id}.json")

def get_or_create_history(session_id, context="", user_name=None, user_picture=None, platform=None):
    path = get_session_path(session_id)
    
    # Robust Platform & Name Detection
    is_fb = str(session_id).startswith("fb_")
    detected_platform = platform or ("facebook" if is_fb else "web")
    
    clean_uid = str(session_id).replace("fb_", "")
    default_name = f"{detected_platform.capitalize()} User {clean_uid[:5]}"
    
    # ใช้รูปที่ส่งมา ถ้าไม่มีให้ใช้ Gravatar
    final_pic = user_picture or "https://www.gravatar.com/avatar/?d=mp"

    data_to_save = None

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Migration: หากเป็นโครงสร้างเก่า (List) ให้แปลงเป็นโครงสร้างใหม่ (Dict)
                if isinstance(data, list):
                    data = {
                        "user_info": {
                            "name": user_name or default_name,
                            "picture": final_pic,
                            "platform": detected_platform
                        },
                        "history": data
                    }
                    data_to_save = data
                
                # อัปเดต Metadata หากมีการส่งข้อมูลใหม่ที่ต่างจากเดิมมา
                if user_name and data.get("user_info", {}).get("name") != user_name:
                    if "user_info" not in data: data["user_info"] = {}
                    data["user_info"]["name"] = user_name
                    data_to_save = data
                
                if user_picture and data.get("user_info", {}).get("picture") != user_picture:
                    if "user_info" not in data: data["user_info"] = {}
                    data["user_info"]["picture"] = user_picture
                    data_to_save = data

                if data_to_save:
                    # บันทึกข้อมูลที่ Update/Migrate แล้ว
                    save_history(session_id, data["history"], **data["user_info"])
                
                return data.get("history", [])
        except (json.JSONDecodeError, Exception):
            pass 

    # กรณีสร้างไฟล์ใหม่
    initial_history = [{"role": "user", "parts": [{"text": context}]}] if context else []
    default_data = {
        "user_info": {
            "name": user_name or default_name,
            "picture": final_pic,
            "platform": detected_platform
        },
        "history": initial_history
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_data, f, ensure_ascii=False, indent=2)
    return default_data["history"]

def save_history(session_id, history, user_name=None, user_picture=None, platform=None):
    path = get_session_path(session_id)
    
    is_fb = str(session_id).startswith("fb_")
    detected_platform = platform or ("facebook" if is_fb else "web")
    clean_uid = str(session_id).replace("fb_", "")
    
    # เตรียมข้อมูล Metadata เริ่มต้น
    user_info = {
        "name": user_name or f"{detected_platform.capitalize()} User {clean_uid[:5]}", 
        "picture": user_picture or "https://www.gravatar.com/avatar/?d=mp", 
        "platform": detected_platform
    }
    
    # พยายามอ่านข้อมูลเดิมเพื่อไม่ให้ Metadata หายไป
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if isinstance(old_data, dict):
                    current_info = old_data.get("user_info", {})
                    # ใช้ค่าใหม่ถ้ามีการส่งมา ถ้าไม่มีใช้ค่าเดิมในไฟล์
                    user_info["name"] = user_name or current_info.get("name", user_info["name"])
                    user_info["picture"] = user_picture or current_info.get("picture", user_info["picture"])
                    user_info["platform"] = platform or current_info.get("platform", user_info["platform"])
        except: pass

    # ป้องกันการบันทึกข้อความซ้ำติดกัน
    deduped_history = []
    for entry in history:
        if not deduped_history or deduped_history[-1] != entry:
            deduped_history.append(entry)

    # จัดการสรุปบทสนทนาหากยาวเกินไป (Summarization)
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
        "history": deduped_history
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

def cleanup_old_sessions(days=7):
    try:
        now = time.time()
        cutoff = now - (days * 86400)
        count = 0
        for filename in os.listdir(SESSION_DIR):
            if filename.endswith(".json"):
                path = os.path.join(SESSION_DIR, filename)
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    count += 1
        return count
    except Exception as e:
        print(f"Cleanup Error: {e}")
        return 0

def clear_history(session_id):
    path = get_session_path(session_id)
    if os.path.exists(path):
        os.remove(path)