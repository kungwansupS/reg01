"""
Tier 1: Greeting & Casual Response Cache
─────────────────────────────────────────
ตอบคำถามทั่วไป (สวัสดี, ขอบคุณ, ฯลฯ) ทันทีโดยไม่ต้องเรียก LLM หรือ RAG
ใช้ exact match หลัง normalize (whitespace collapse + lowercase)
Token cost: 0

ใช้งาน:
    from memory.greeting_cache import get_greeting_response
    reply = get_greeting_response("สวัสดีครับ")  # → "สวัสดีครับ พี่เร็กยินดีให้คำปรึกษาเรื่องการเรียนที่ มช. นะครับ"
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GREETING_FILE = os.path.join(BASE_DIR, "cache", "greeting_cache.json")


def _normalize(text: str) -> str:
    """Normalize: strip + collapse whitespace + lowercase."""
    return " ".join(str(text or "").strip().split()).lower()


# ─── Default greeting patterns ────────────────────────────────────
# Key = normalized form, value = response text
# These are loaded once then merged with the JSON file on disk.
_DEFAULT_GREETINGS = {
    # ── Thai greetings ──
    "สวัสดี": "สวัสดีครับ // พี่เร็กยินดีให้คำปรึกษาเรื่องการเรียนที่ มช. นะครับ",
    "สวัสดีครับ": "สวัสดีครับ // พี่เร็กยินดีให้คำปรึกษาเรื่องการเรียนที่ มช. นะครับ",
    "สวัสดีค่ะ": "สวัสดีครับ // พี่เร็กยินดีให้คำปรึกษาเรื่องการเรียนที่ มช. นะครับ",
    "หวัดดี": "หวัดดีครับ // มีอะไรให้พี่ช่วยไหมครับ",
    "หวัดดีครับ": "หวัดดีครับ // มีอะไรให้พี่ช่วยไหมครับ",
    "หวัดดีค่ะ": "หวัดดีครับ // มีอะไรให้พี่ช่วยไหมครับ",
    "ดี": "ดีครับ // มีอะไรอยากถามไหมครับ",
    "ดีครับ": "ดีครับ // มีอะไรอยากถามไหมครับ",
    "ดีค่ะ": "ดีครับ // มีอะไรอยากถามไหมครับ",
    # ── Thai thanks ──
    "ขอบคุณ": "ยินดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    "ขอบคุณครับ": "ยินดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    "ขอบคุณค่ะ": "ยินดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    "ขอบคุณมากครับ": "ยินดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    "ขอบคุณมากค่ะ": "ยินดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    "ขอบใจ": "ยินดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    # ── Thai farewell ──
    "บาย": "บายครับ // แล้วเจอกันนะครับ",
    "บายครับ": "บายครับ // แล้วเจอกันนะครับ",
    "บายค่ะ": "บายครับ // แล้วเจอกันนะครับ",
    "ลาก่อน": "ลาก่อนครับ // แล้วเจอกันนะครับ",
    "ลาก่อนครับ": "ลาก่อนครับ // แล้วเจอกันนะครับ",
    "ไปก่อนนะ": "โอเคครับ // แล้วเจอกันนะครับ",
    "ไปก่อนนะครับ": "โอเคครับ // แล้วเจอกันนะครับ",
    # ── Thai identity ──
    "เป็นใคร": "พี่ชื่อเร็ก // เป็นผู้ช่วย AI ของมหาวิทยาลัยเชียงใหม่ // คอยตอบคำถามเรื่องการลงทะเบียนเรียนและปฏิทินการศึกษาครับ",
    "คุณเป็นใคร": "พี่ชื่อเร็ก // เป็นผู้ช่วย AI ของมหาวิทยาลัยเชียงใหม่ // คอยตอบคำถามเรื่องการลงทะเบียนเรียนและปฏิทินการศึกษาครับ",
    "ชื่ออะไร": "พี่ชื่อเร็กครับ // เป็นผู้ช่วย AI สำหรับนักศึกษา มช.",
    "คุณชื่ออะไร": "พี่ชื่อเร็กครับ // เป็นผู้ช่วย AI สำหรับนักศึกษา มช.",
    "พี่เร็กคือใคร": "พี่เร็กเป็นผู้ช่วย AI ของมหาวิทยาลัยเชียงใหม่ // คอยตอบคำถามเรื่องปฏิทินการศึกษาและระเบียบการลงทะเบียนเรียนครับ",
    "คุณคือใคร": "พี่ชื่อเร็ก // เป็นผู้ช่วย AI ของมหาวิทยาลัยเชียงใหม่ // คอยตอบคำถามเรื่องการลงทะเบียนเรียนและปฏิทินการศึกษาครับ",
    "คุณทำอะไรได้บ้าง": "พี่เร็กช่วยตอบคำถามเกี่ยวกับปฏิทินการศึกษา // การลงทะเบียน // การถอนวิชา // ค่าธรรมเนียม // และข้อมูลอื่นๆ ของ มช. ครับ",
    # ── Thai acknowledgment ──
    "โอเค": "ครับ // มีอะไรเพิ่มเติมถามได้เลยนะครับ",
    "โอเคครับ": "ครับ // มีอะไรเพิ่มเติมถามได้เลยนะครับ",
    "ได้เลย": "ครับ // มีอะไรเพิ่มเติมถามได้เลยนะครับ",
    "ได้เลยครับ": "ครับ // มีอะไรเพิ่มเติมถามได้เลยนะครับ",
    "เข้าใจแล้ว": "ดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    "เข้าใจแล้วครับ": "ดีครับ // ถ้ามีอะไรสงสัยเพิ่มเติมถามได้เลยนะครับ",
    # ── English greetings ──
    "hi": "Hi! // I'm Reg, CMU's assistant. How can I help you?",
    "hello": "Hello! // I'm Reg, CMU's assistant. How can I help you?",
    "hey": "Hey! // How can I help you today?",
    "thanks": "You're welcome! // Feel free to ask anything else.",
    "thank you": "You're welcome! // Feel free to ask anything else.",
    "bye": "Bye! // See you next time.",
    "goodbye": "Goodbye! // See you next time.",
}


def _load_from_disk() -> dict:
    """Load greeting cache from JSON file."""
    try:
        if os.path.exists(GREETING_FILE):
            with open(GREETING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load greeting cache: %s", exc)
    return {}


def _save_to_disk(data: dict) -> None:
    """Save greeting cache to JSON file."""
    try:
        os.makedirs(os.path.dirname(GREETING_FILE), exist_ok=True)
        with open(GREETING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.error("Failed to save greeting cache: %s", exc)


# ─── Initialize: merge defaults with disk file ────────────────────
_greeting_map: dict = {}

def _init_greeting_map():
    global _greeting_map
    _greeting_map = dict(_DEFAULT_GREETINGS)
    disk = _load_from_disk()
    _greeting_map.update(disk)
    # Persist merged result
    if disk != _greeting_map:
        _save_to_disk(_greeting_map)
    logger.info("Greeting cache loaded: %d entries", len(_greeting_map))

_init_greeting_map()


# ─── Public API ───────────────────────────────────────────────────

def get_greeting_response(text: str) -> Optional[str]:
    """
    Check if text is a greeting/casual phrase.
    Returns response string if exact match found, None otherwise.
    Uses normalized (whitespace-collapsed + lowercased) comparison.
    """
    normalized = _normalize(text)
    if not normalized:
        return None
    return _greeting_map.get(normalized)


def add_greeting(text: str, response: str) -> bool:
    """Add or update a greeting entry. Returns True if added."""
    key = _normalize(text)
    if not key or not response.strip():
        return False
    _greeting_map[key] = response.strip()
    _save_to_disk(_greeting_map)
    return True


def remove_greeting(text: str) -> bool:
    """Remove a greeting entry. Returns True if removed."""
    key = _normalize(text)
    if key in _greeting_map:
        del _greeting_map[key]
        _save_to_disk(_greeting_map)
        return True
    return False


def list_greetings() -> dict:
    """List all greeting entries."""
    return dict(_greeting_map)


def greeting_count() -> int:
    """Return number of greeting entries."""
    return len(_greeting_map)
