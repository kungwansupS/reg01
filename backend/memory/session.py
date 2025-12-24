import json
import os
import redis
import logging
from app.config import REDIS_URL, SESSION_DIR
from memory.memory import summarize_chat_history

logger = logging.getLogger(__name__)

# ตรวจสอบการเชื่อมต่อ Redis
try:
    r = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    r.ping()
    USE_REDIS = True
    logger.info("✅ Redis connected: Using Redis for session management.")
except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
    USE_REDIS = False
    os.makedirs(SESSION_DIR, exist_ok=True)
    logger.warning("⚠️ Redis not found: Falling back to Local File Storage.")

MAX_HISTORY_LENGTH = 30
NUM_RECENT_TO_KEEP = 10
SESSION_TTL = 86400

def get_session_path(session_id):
    return os.path.join(SESSION_DIR, f"{session_id}.json")

def get_or_create_history(session_id, context=""):
    if USE_REDIS:
        key = f"session:{session_id}"
        data = r.get(key)
        if data:
            return json.loads(data)
    else:
        path = get_session_path(session_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    # หากไม่มีข้อมูลเดิม ให้สร้างใหม่
    history = [{"role": "user", "parts": [{"text": context}]}] if context else []
    save_history(session_id, history)
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
        deduped_history = [{"role": "system", "parts": [{"text": f"สรุปบทสนทนาก่อนหน้านี้:\n{summary_text}"}]}] + recent

    if USE_REDIS:
        r.setex(f"session:{session_id}", SESSION_TTL, json.dumps(deduped_history, ensure_ascii=False))
    else:
        path = get_session_path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(deduped_history, f, ensure_ascii=False, indent=2)

def clear_history(session_id):
    if USE_REDIS:
        r.delete(f"session:{session_id}")
    else:
        path = get_session_path(session_id)
        if os.path.exists(path): os.remove(path)