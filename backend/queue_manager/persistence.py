"""
Queue Persistence — บันทึก/โหลด pending items ผ่าน Redis

เมื่อ server ถูกปิด (graceful หรือ crash) คำขอที่ค้างอยู่ในคิวจะถูกบันทึกลง Redis
เมื่อเปิด server ใหม่ ระบบจะตรวจสอบ key นี้และถามผู้ดูแลว่า:
  - ต้องการประมวลผลคำขอค้าง → re-submit เข้าคิว
  - ล้างคิวทิ้ง → ลบ key

Redis key: reg01:queue_state
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("QueuePersistence")

REDIS_QUEUE_KEY = "reg01:queue_state"
# TTL สำหรับ queue state (7 วัน — คิวค้างเก่ากว่านี้ไม่มีประโยชน์)
QUEUE_STATE_TTL = 7 * 86400

# Legacy — kept as a constant for callers that still pass a path arg (ignored)
DEFAULT_PERSIST_PATH = REDIS_QUEUE_KEY


def _get_redis():
    """Get Redis client (lazy import to avoid circular deps at module load time)."""
    from memory.redis_client import get_redis
    return get_redis()


# ─────────────────────────────────────────────────────────────────────────── #
# SAVE (async)
# ─────────────────────────────────────────────────────────────────────────── #
async def save_pending_items(
    items: List[Dict[str, Any]],
    path: str = REDIS_QUEUE_KEY,
) -> bool:
    """
    บันทึก pending items ลง Redis

    Args:
        items: list ของ dict ที่มี key: request_id, user_id, session_id, msg, submitted_at, priority
        path: ignored (kept for API compat)

    Returns:
        True ถ้าบันทึกสำเร็จ
    """
    if not items:
        await clear_persisted()
        return True

    try:
        r = _get_redis()
        state = {
            "saved_at": datetime.now().isoformat(),
            "saved_at_ts": time.time(),
            "count": len(items),
            "items": items,
        }
        await r.set(REDIS_QUEUE_KEY, json.dumps(state, ensure_ascii=False), ex=QUEUE_STATE_TTL)
        logger.info("[Persistence] Saved %d pending items to Redis", len(items))
        return True
    except Exception as exc:
        logger.error("[Persistence] Failed to save: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────── #
# LOAD (async)
# ─────────────────────────────────────────────────────────────────────────── #
async def load_pending_items(
    path: str = REDIS_QUEUE_KEY,
) -> Optional[Dict[str, Any]]:
    """
    โหลด pending items จาก Redis

    Returns:
        dict ที่มี keys: saved_at, count, items
        หรือ None ถ้าไม่มี key หรือข้อมูลเสีย
    """
    try:
        r = _get_redis()
        raw = await r.get(REDIS_QUEUE_KEY)
        if not raw:
            return None

        state = json.loads(raw)

        if not isinstance(state, dict) or "items" not in state:
            logger.warning("[Persistence] Invalid state format in Redis")
            return None

        items = state.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            logger.info("[Persistence] State empty in Redis, removing")
            await clear_persisted()
            return None

        # Validate each item has required fields
        required_fields = {"user_id", "session_id", "msg"}
        valid_items = []
        for item in items:
            if isinstance(item, dict) and required_fields.issubset(item.keys()):
                valid_items.append(item)
            else:
                logger.warning("[Persistence] Skipping invalid item: %s", item)

        if not valid_items:
            logger.info("[Persistence] No valid items found, removing key")
            await clear_persisted()
            return None

        state["items"] = valid_items
        state["count"] = len(valid_items)

        logger.info(
            "[Persistence] Loaded %d pending items (saved at %s)",
            len(valid_items),
            state.get("saved_at", "unknown"),
        )
        return state

    except json.JSONDecodeError as exc:
        logger.error("[Persistence] Corrupted state in Redis: %s", exc)
        await clear_persisted()
        return None
    except Exception as exc:
        logger.error("[Persistence] Failed to load: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────── #
# CLEAR (async)
# ─────────────────────────────────────────────────────────────────────────── #
async def clear_persisted(path: str = REDIS_QUEUE_KEY) -> bool:
    """ลบ persisted state จาก Redis"""
    try:
        r = _get_redis()
        await r.delete(REDIS_QUEUE_KEY)
        logger.info("[Persistence] Cleared persisted state from Redis")
        return True
    except Exception as exc:
        logger.error("[Persistence] Failed to clear: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────── #
# DISPLAY (for console prompt) — pure functions, no I/O
# ─────────────────────────────────────────────────────────────────────────── #
def format_pending_summary(state: Dict[str, Any], max_display: int = 20) -> str:
    """
    สร้าง summary string สำหรับแสดงใน console

    แสดง:
    - เวลาที่บันทึก
    - จำนวนคำขอทั้งหมด
    - รายการคำถาม (สูงสุด max_display)
    """
    items = state.get("items", [])
    saved_at = state.get("saved_at", "unknown")
    saved_ts = state.get("saved_at_ts", 0)

    # คำนวณเวลาที่ผ่านไป
    if saved_ts > 0:
        elapsed = time.time() - saved_ts
        if elapsed < 60:
            age_str = f"{int(elapsed)} วินาทีที่แล้ว"
        elif elapsed < 3600:
            age_str = f"{int(elapsed / 60)} นาทีที่แล้ว"
        elif elapsed < 86400:
            age_str = f"{int(elapsed / 3600)} ชั่วโมงที่แล้ว"
        else:
            age_str = f"{int(elapsed / 86400)} วันที่แล้ว"
    else:
        age_str = "ไม่ทราบ"

    lines = [
        "",
        "=" * 70,
        "  📋 พบคิวค้างจากการเปิด Server ครั้งก่อน",
        "=" * 70,
        f"  บันทึกเมื่อ : {saved_at} ({age_str})",
        f"  จำนวนคำขอ  : {len(items)} รายการ",
        "-" * 70,
    ]

    # แสดงรายการ
    display_items = items[:max_display]
    for i, item in enumerate(display_items, 1):
        user_id = item.get("user_id", "?")
        session_id = item.get("session_id", "?")
        msg = item.get("msg", "")
        # Truncate long messages
        if len(msg) > 60:
            msg = msg[:57] + "..."
        # Format submitted_at
        sub_ts = item.get("submitted_at", 0)
        if sub_ts > 0:
            time_str = datetime.fromtimestamp(sub_ts).strftime("%H:%M:%S")
        else:
            time_str = "--:--:--"

        platform = "FB" if session_id.startswith("fb_") else "Web"
        lines.append(
            f"  {i:3d}. [{platform}] {time_str} | {user_id[:20]:<20s} | {msg}"
        )

    if len(items) > max_display:
        lines.append(f"  ... และอีก {len(items) - max_display} รายการ")

    lines.append("-" * 70)
    lines.append("")
    lines.append("  เลือกการดำเนินการ:")
    lines.append("    [1] ประมวลผลคิวค้าง (ตอบคำถามที่ค้างไว้)")
    lines.append("    [2] ล้างคิวทิ้งทั้งหมด (เริ่มต้นใหม่)")
    lines.append("    [3] แสดงรายละเอียดเพิ่มเติม")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_detailed_list(state: Dict[str, Any]) -> str:
    """แสดงรายละเอียดคำถามทั้งหมดแบบไม่ตัด"""
    items = state.get("items", [])
    lines = [
        "",
        "=" * 70,
        f"  📋 รายละเอียดคิวค้างทั้งหมด ({len(items)} รายการ)",
        "=" * 70,
    ]

    for i, item in enumerate(items, 1):
        user_id = item.get("user_id", "?")
        session_id = item.get("session_id", "?")
        msg = item.get("msg", "")
        sub_ts = item.get("submitted_at", 0)
        if sub_ts > 0:
            time_str = datetime.fromtimestamp(sub_ts).strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "unknown"

        platform = "Facebook" if session_id.startswith("fb_") else "Web"
        lines.append(f"  ─── รายการที่ {i} ───")
        lines.append(f"  Platform  : {platform}")
        lines.append(f"  User      : {user_id}")
        lines.append(f"  Session   : {session_id}")
        lines.append(f"  เวลาส่ง   : {time_str}")
        lines.append(f"  คำถาม     : {msg}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
