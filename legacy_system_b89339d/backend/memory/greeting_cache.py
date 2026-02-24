"""
Tier 1 greeting cache backed by Redis.

Exact match after normalization (trim + collapse whitespace + lowercase).
"""

import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_GREETING_FILE = os.path.join(BASE_DIR, "cache", "greeting_cache.json")
REDIS_GREETING_KEY = "reg01:greeting:map"

_init_lock: Optional[asyncio.Lock] = None
_initialized = False


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().split()).lower()


_DEFAULT_GREETINGS = {
    "สวัสดี": "สวัสดีครับ // มีอะไรให้ช่วยได้บ้างครับ",
    "สวัสดีครับ": "สวัสดีครับ // มีอะไรให้ช่วยได้บ้างครับ",
    "หวัดดี": "หวัดดีครับ // มีอะไรให้ช่วยได้บ้างครับ",
    "ขอบคุณ": "ยินดีครับ // ถ้ามีอะไรถามเพิ่มได้เลยครับ",
    "ขอบคุณครับ": "ยินดีครับ // ถ้ามีอะไรถามเพิ่มได้เลยครับ",
    "ไปก่อน": "ได้เลยครับ // แล้วเจอกันครับ",
    "บาย": "บายครับ // แล้วเจอกันครับ",
    "คุณคือใคร": "ผมคือ Reg ผู้ช่วย AI ของ มช. ครับ",
    "ทำอะไรได้บ้าง": "ช่วยตอบคำถามเรื่องการเรียน ปฏิทิน และข้อมูลที่เกี่ยวกับ มช. ได้ครับ",
    "hi": "Hi! I'm Reg, CMU's assistant. How can I help you?",
    "hello": "Hello! I'm Reg, CMU's assistant. How can I help you?",
    "thanks": "You're welcome! Feel free to ask anything else.",
    "thank you": "You're welcome! Feel free to ask anything else.",
    "bye": "Bye! See you next time.",
}


def _get_redis():
    from memory.redis_client import get_redis
    return get_redis()


def _load_legacy_json() -> dict:
    """
    One-time loader for old JSON cache. If present, values are merged into Redis.
    """
    try:
        if os.path.exists(LEGACY_GREETING_FILE):
            with open(LEGACY_GREETING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load legacy greeting cache: %s", exc)
    return {}


async def _ensure_initialized() -> None:
    global _initialized, _init_lock
    if _initialized:
        return
    if _init_lock is None:
        _init_lock = asyncio.Lock()

    async with _init_lock:
        if _initialized:
            return

        r = _get_redis()
        existing = await r.hgetall(REDIS_GREETING_KEY)

        merged = dict(_DEFAULT_GREETINGS)
        legacy = _load_legacy_json()
        for key, value in legacy.items():
            nkey = _normalize(key)
            nval = str(value or "").strip()
            if nkey and nval:
                merged[nkey] = nval

        updates = {}
        for key, value in merged.items():
            if key not in existing or existing.get(key) != value:
                updates[key] = value

        if updates:
            await r.hset(REDIS_GREETING_KEY, mapping=updates)

        _initialized = True
        logger.info("Greeting cache initialized in Redis: %d entries", await r.hlen(REDIS_GREETING_KEY))


async def get_greeting_response(text: str) -> Optional[str]:
    normalized = _normalize(text)
    if not normalized:
        return None
    await _ensure_initialized()
    r = _get_redis()
    value = await r.hget(REDIS_GREETING_KEY, normalized)
    return str(value) if value is not None else None


async def add_greeting(text: str, response: str) -> bool:
    key = _normalize(text)
    value = str(response or "").strip()
    if not key or not value:
        return False
    await _ensure_initialized()
    r = _get_redis()
    await r.hset(REDIS_GREETING_KEY, key, value)
    return True


async def remove_greeting(text: str) -> bool:
    key = _normalize(text)
    if not key:
        return False
    await _ensure_initialized()
    r = _get_redis()
    removed = await r.hdel(REDIS_GREETING_KEY, key)
    return bool(removed)


async def list_greetings() -> dict:
    await _ensure_initialized()
    r = _get_redis()
    return dict(await r.hgetall(REDIS_GREETING_KEY))


async def greeting_count() -> int:
    await _ensure_initialized()
    r = _get_redis()
    return int(await r.hlen(REDIS_GREETING_KEY))
