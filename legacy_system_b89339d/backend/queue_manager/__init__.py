"""
Queue Manager — Decoupled LLM Request Queue System

ระบบคิวแยกส่วนจากระบบหลัก รองรับ multi-user สูงสุด 100+ คนพร้อมกัน
- Request queuing with capacity limits
- Worker pool for parallel processing
- Per-user fairness (max requests per user)
- Real-time queue position updates via callback
- Request timeout & overflow protection
- Error isolation (handler errors don't crash workers)
- Queue persistence ข้าม server restart
- Recovery: ประมวลผลคิวค้าง หรือ ล้างทิ้ง
"""

from queue_manager.request_queue import (
    LLMRequestQueue,
    QueueConfig,
    QueueFullError,
    QueueTimeoutError,
)
from queue_manager.persistence import (
    load_pending_items,
    clear_persisted,
    format_pending_summary,
    format_detailed_list,
    DEFAULT_PERSIST_PATH,
)

__all__ = [
    "LLMRequestQueue",
    "QueueConfig",
    "QueueFullError",
    "QueueTimeoutError",
    "load_pending_items",
    "clear_persisted",
    "format_pending_summary",
    "format_detailed_list",
    "DEFAULT_PERSIST_PATH",
]
