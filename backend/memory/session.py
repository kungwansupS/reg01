import os
import json
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

def get_or_create_history(session_id, context=""):
    path = get_session_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    history = [{"role": "user", "parts": [{"text": context}]}] if context else []
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history

def save_history(session_id, history):
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

    path = get_session_path(session_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(deduped_history, f, ensure_ascii=False, indent=2)

def append_to_history(session_id, new_entry):
    history = get_or_create_history(session_id)
    if history and history[-1]["role"] == new_entry["role"] and \
       history[-1]["parts"][0]["text"] == new_entry["parts"][0]["text"]:
        return
    history.append(new_entry)
    save_history(session_id, history)

def clear_history(session_id):
    path = get_session_path(session_id)
    if os.path.exists(path):
        os.remove(path)