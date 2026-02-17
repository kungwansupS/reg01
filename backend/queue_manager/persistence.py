"""
Queue Persistence — บันทึก/โหลด pending items ลง disk

เมื่อ server ถูกปิด (graceful หรือ crash) คำขอที่ค้างอยู่ในคิวจะถูกบันทึก
เมื่อเปิด server ใหม่ ระบบจะตรวจสอบไฟล์นี้และถามผู้ดูแลว่า:
  - ต้องการประมวลผลคำขอค้าง → re-submit เข้าคิว
  - ล้างคิวทิ้ง → ลบไฟล์

ไฟล์: queue_state.json เก็บใน logs/
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("QueuePersistence")

DEFAULT_PERSIST_PATH = os.path.join("logs", "queue_state.json")


def _ensure_dir(path: str) -> None:
    """สร้าง directory ถ้ายังไม่มี"""
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────── #
# SAVE
# ─────────────────────────────────────────────────────────────────────────── #
def save_pending_items(
    items: List[Dict[str, Any]],
    path: str = DEFAULT_PERSIST_PATH,
) -> bool:
    """
    บันทึก pending items ลงไฟล์ JSON

    Args:
        items: list ของ dict ที่มี key: request_id, user_id, session_id, msg, submitted_at, priority
        path: path สำหรับบันทึกไฟล์

    Returns:
        True ถ้าบันทึกสำเร็จ
    """
    if not items:
        # ไม่มีอะไรต้องบันทึก — ลบไฟล์ถ้ามี
        clear_persisted(path)
        return True

    try:
        _ensure_dir(path)
        state = {
            "saved_at": datetime.now().isoformat(),
            "saved_at_ts": time.time(),
            "count": len(items),
            "items": items,
        }
        # Write atomically via temp file
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        # Atomic rename (Windows: replace if exists)
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)
        logger.info("[Persistence] Saved %d pending items to %s", len(items), path)
        return True
    except Exception as exc:
        logger.error("[Persistence] Failed to save: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────── #
# LOAD
# ─────────────────────────────────────────────────────────────────────────── #
def load_pending_items(
    path: str = DEFAULT_PERSIST_PATH,
) -> Optional[Dict[str, Any]]:
    """
    โหลด pending items จากไฟล์ JSON

    Returns:
        dict ที่มี keys: saved_at, count, items
        หรือ None ถ้าไม่มีไฟล์หรือไฟล์เสีย
    """
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        # Validate structure
        if not isinstance(state, dict) or "items" not in state:
            logger.warning("[Persistence] Invalid state file format")
            return None

        items = state.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            logger.info("[Persistence] State file empty, removing")
            clear_persisted(path)
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
            logger.info("[Persistence] No valid items found, removing file")
            clear_persisted(path)
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
        logger.error("[Persistence] Corrupted state file: %s", exc)
        # Backup corrupted file for debugging
        try:
            backup = path + ".corrupted"
            if os.path.exists(path):
                os.replace(path, backup)
                logger.info("[Persistence] Corrupted file backed up to %s", backup)
        except Exception:
            pass
        return None
    except Exception as exc:
        logger.error("[Persistence] Failed to load: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────── #
# CLEAR
# ─────────────────────────────────────────────────────────────────────────── #
def clear_persisted(path: str = DEFAULT_PERSIST_PATH) -> bool:
    """ลบไฟล์ persisted state"""
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info("[Persistence] Cleared persisted state: %s", path)
        return True
    except Exception as exc:
        logger.error("[Persistence] Failed to clear: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────── #
# DISPLAY (for console prompt)
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
