"""
Decoupled LLM Request Queue System

โมดูลนี้แยกส่วนจากระบบหลักอย่างสมบูรณ์ (zero application imports)
รับ handler function ตอน init และจัดการ:

- Request queuing พร้อม capacity limits
- Worker pool สำหรับ parallel processing
- Per-user fairness (จำกัดจำนวน request ต่อผู้ใช้)
- Real-time queue position updates ผ่าน emit callback
- Request timeout & overflow protection
- Error isolation (handler error ไม่ crash workers)
- Graceful shutdown
- Health monitoring & statistics
- Queue persistence ข้าม server restart
- Recovery: ประมวลผลคิวค้าง หรือ ล้างทิ้ง

รองรับ 100+ concurrent users
"""

import asyncio
import atexit
import logging
import time
import uuid
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from queue_manager.persistence import (
    save_pending_items,
    load_pending_items,
    clear_persisted,
    format_pending_summary,
    format_detailed_list,
    DEFAULT_PERSIST_PATH,
)

logger = logging.getLogger("QueueManager")


# ─────────────────────────────────────────────────────────────────────────── #
# EXCEPTIONS
# ─────────────────────────────────────────────────────────────────────────── #
class QueueFullError(Exception):
    """Raised when the queue is at capacity or per-user limit reached."""
    pass


class QueueTimeoutError(Exception):
    """Raised when a request times out waiting in queue."""
    pass


# ─────────────────────────────────────────────────────────────────────────── #
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────── #
@dataclass
class QueueConfig:
    max_size: int = 200             # Max total items in queue
    num_workers: int = 10           # Number of worker coroutines
    per_user_limit: int = 3         # Max pending+active requests per user
    request_timeout: float = 120.0  # Seconds before request times out
    health_log_interval: float = 60.0  # Seconds between health log outputs
    persist_path: str = DEFAULT_PERSIST_PATH  # Path for queue state file


# ─────────────────────────────────────────────────────────────────────────── #
# QUEUE ITEM
# ─────────────────────────────────────────────────────────────────────────── #
@dataclass
class QueueItem:
    request_id: str
    user_id: str
    session_id: str
    msg: str
    future: asyncio.Future
    emit_fn: Optional[Callable] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)
    submitted_at: float = 0.0
    priority: int = 0  # Lower number = higher priority (reserved for future use)


# ─────────────────────────────────────────────────────────────────────────── #
# LLM REQUEST QUEUE
# ─────────────────────────────────────────────────────────────────────────── #
class LLMRequestQueue:
    """
    Decoupled request queue for LLM processing.

    ไม่มี import จาก application — handler function ถูก inject ตอน init
    ทำให้ระบบคิวแยกจากระบบหลักอย่างสมบูรณ์ ป้องกันข้อผิดพลาดข้ามระบบ

    Usage:
        queue = LLMRequestQueue(handler_fn=ask_llm, config=QueueConfig())
        await queue.start()

        # From HTTP handler:
        result = await queue.submit(user_id, session_id, msg, emit_fn)

        # Shutdown:
        await queue.shutdown()
    """

    def __init__(
        self,
        handler_fn: Callable,
        config: Optional[QueueConfig] = None,
    ):
        if not callable(handler_fn):
            raise ValueError("handler_fn must be callable")

        self._handler = handler_fn
        self._config = config or QueueConfig()

        # Internal queue (unbounded — capacity managed by self._pending)
        self._queue: asyncio.Queue = asyncio.Queue()

        # Tracking structures
        self._pending: OrderedDict[str, QueueItem] = OrderedDict()
        self._active: Dict[str, QueueItem] = {}
        self._per_user_pending: Dict[str, int] = defaultdict(int)
        self._per_user_active: Dict[str, int] = defaultdict(int)

        # Concurrency control
        self._lock = asyncio.Lock()
        self._workers: List[asyncio.Task] = []
        self._health_task: Optional[asyncio.Task] = None
        self._running = False

        # Persistence
        self._persist_path = self._config.persist_path

        # Statistics (atomic increments via lock)
        self._total_submitted = 0
        self._total_processed = 0
        self._total_errors = 0
        self._total_timeouts = 0
        self._total_rejected = 0
        self._total_cancelled = 0
        self._started_at: Optional[float] = None
        self._peak_pending = 0
        self._peak_active = 0

    # ───────────────────────────────────────────────────────────────────── #
    # LIFECYCLE
    # ───────────────────────────────────────────────────────────────────── #
    async def start(self):
        """Start worker pool and health monitor."""
        if self._running:
            logger.warning("Queue already running")
            return

        self._running = True
        self._started_at = time.time()

        for i in range(self._config.num_workers):
            task = asyncio.create_task(self._worker(i), name=f"queue-worker-{i}")
            self._workers.append(task)

        self._health_task = asyncio.create_task(
            self._health_monitor(), name="queue-health"
        )

        # ลงทะเบียน atexit handler สำหรับกรณี crash หรือ kill process
        atexit.register(self._emergency_persist)

        logger.info(
            "✅ [Queue] Started | workers=%d max_size=%d per_user=%d timeout=%ds",
            self._config.num_workers,
            self._config.max_size,
            self._config.per_user_limit,
            int(self._config.request_timeout),
        )

    async def shutdown(self):
        """Gracefully shut down queue — persist pending, cancel futures, wait for workers."""
        if not self._running:
            return

        logger.info("🛑 [Queue] Shutting down...")
        self._running = False

        # Persist pending + active items before cancelling
        self._persist_state()

        # Cancel all pending futures
        async with self._lock:
            for item in self._pending.values():
                if not item.future.done():
                    item.future.cancel()
            self._pending.clear()
            self._per_user_pending.clear()

        # Cancel health monitor
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()

        # Cancel workers
        for task in self._workers:
            task.cancel()

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        logger.info("✅ [Queue] Shutdown complete | stats=%s", self.get_stats())

    # ───────────────────────────────────────────────────────────────────── #
    # SUBMIT
    # ───────────────────────────────────────────────────────────────────── #
    async def submit(
        self,
        user_id: str,
        session_id: str,
        msg: str,
        emit_fn: Optional[Callable] = None,
        priority: int = 0,
        **kwargs,
    ) -> dict:
        """
        Submit a request to the queue and wait for the result.

        Args:
            user_id: Identifier for rate limiting / fairness
            session_id: Chat session identifier
            msg: User message text
            emit_fn: async callable(event, payload) for real-time updates
            priority: Reserved for future priority queuing
            **kwargs: Extra args passed to handler_fn

        Returns:
            dict from handler_fn (e.g. {"text": ..., "tokens": ...})

        Raises:
            QueueFullError: Queue at capacity or per-user limit reached
            QueueTimeoutError: Request timed out
            RuntimeError: Queue not running
        """
        if not self._running:
            raise RuntimeError("Queue is not running")

        # ── Per-user limit check ──
        async with self._lock:
            user_total = (
                self._per_user_pending.get(user_id, 0)
                + self._per_user_active.get(user_id, 0)
            )
            if user_total >= self._config.per_user_limit:
                self._total_rejected += 1
                raise QueueFullError(
                    f"ระบบกำลังประมวลผลคำขอของคุณอยู่ กรุณารอสักครู่ "
                    f"(สูงสุด {self._config.per_user_limit} คำขอพร้อมกันต่อผู้ใช้)"
                )

            # ── Total capacity check ──
            total_in_system = len(self._pending) + len(self._active)
            if total_in_system >= self._config.max_size:
                self._total_rejected += 1
                raise QueueFullError(
                    "ระบบมีผู้ใช้งานจำนวนมากในขณะนี้ "
                    "กรุณาลองใหม่อีกครั้งในอีกสักครู่"
                )

        # ── Create queue item ──
        request_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        item = QueueItem(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            msg=msg,
            future=future,
            emit_fn=emit_fn,
            kwargs=kwargs,
            submitted_at=time.time(),
            priority=priority,
        )

        # ── Register in tracking ──
        async with self._lock:
            self._pending[request_id] = item
            self._per_user_pending[user_id] = self._per_user_pending.get(user_id, 0) + 1
            self._total_submitted += 1
            self._peak_pending = max(self._peak_pending, len(self._pending))

        # ── Put in async queue for workers ──
        await self._queue.put(item)

        # ── Notify user of queue position ──
        position = await self.get_position(request_id)
        if position > 0:
            await self._emit_safe(emit_fn, "queue_position", {
                "position": position,
                "request_id": request_id,
                "estimated_wait": position * 5,
                "status": "queued",
            })
            # Also send as ai_status for backward-compatible UI
            await self._emit_safe(
                emit_fn, "ai_status",
                {"status": f"กำลังรอคิว ลำดับที่ {position} ..."},
            )

        logger.info(
            "[Queue] Submitted request=%s user=%s session=%s pos=%d pending=%d active=%d",
            request_id[:8], user_id[:16], session_id[:16],
            position, len(self._pending), len(self._active),
        )

        # ── Wait for result with timeout ──
        try:
            result = await asyncio.wait_for(
                future, timeout=self._config.request_timeout
            )
            return result

        except asyncio.TimeoutError:
            self._total_timeouts += 1
            async with self._lock:
                self._pending.pop(request_id, None)
                self._per_user_pending[user_id] = max(
                    0, self._per_user_pending.get(user_id, 0) - 1
                )
            logger.warning(
                "[Queue] Timeout request=%s user=%s (%.0fs)",
                request_id[:8], user_id[:16], self._config.request_timeout,
            )
            raise QueueTimeoutError(
                f"คำขอหมดเวลารอ ({int(self._config.request_timeout)}s) "
                "กรุณาลองใหม่อีกครั้ง"
            )

        except asyncio.CancelledError:
            self._total_cancelled += 1
            async with self._lock:
                self._pending.pop(request_id, None)
                self._per_user_pending[user_id] = max(
                    0, self._per_user_pending.get(user_id, 0) - 1
                )
            raise

        except Exception:
            # Clean up tracking on unexpected errors
            async with self._lock:
                self._pending.pop(request_id, None)
                self._per_user_pending[user_id] = max(
                    0, self._per_user_pending.get(user_id, 0) - 1
                )
            raise

    # ───────────────────────────────────────────────────────────────────── #
    # WORKER
    # ───────────────────────────────────────────────────────────────────── #
    async def _worker(self, worker_id: int):
        """Worker coroutine — pulls items from queue and processes them."""
        logger.debug("[Queue] Worker #%d started", worker_id)

        while self._running:
            item: Optional[QueueItem] = None
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception:
                continue

            # Skip if already done (timeout / cancel)
            if item.future.done():
                async with self._lock:
                    self._pending.pop(item.request_id, None)
                    self._per_user_pending[item.user_id] = max(
                        0, self._per_user_pending.get(item.user_id, 0) - 1
                    )
                self._queue.task_done()
                continue

            # ── Move from pending → active ──
            async with self._lock:
                self._pending.pop(item.request_id, None)
                self._per_user_pending[item.user_id] = max(
                    0, self._per_user_pending.get(item.user_id, 0) - 1
                )
                self._active[item.request_id] = item
                self._per_user_active[item.user_id] = (
                    self._per_user_active.get(item.user_id, 0) + 1
                )
                self._peak_active = max(self._peak_active, len(self._active))

            wait_time = time.time() - item.submitted_at

            # ── Notify: processing started ──
            await self._emit_safe(item.emit_fn, "queue_position", {
                "position": 0,
                "request_id": item.request_id,
                "status": "processing",
                "waited": round(wait_time, 1),
            })
            await self._emit_safe(
                item.emit_fn, "ai_status",
                {"status": "กำลังประมวลผล..."},
            )

            logger.info(
                "[Queue] Worker #%d processing request=%s user=%s waited=%.1fs",
                worker_id, item.request_id[:8], item.user_id[:16], wait_time,
            )

            # ── Call handler (isolated from worker) ──
            try:
                result = await self._handler(
                    item.msg,
                    item.session_id,
                    emit_fn=item.emit_fn,
                    **item.kwargs,
                )

                if not item.future.done():
                    item.future.set_result(result)
                self._total_processed += 1

                process_time = time.time() - item.submitted_at
                logger.info(
                    "[Queue] Worker #%d completed request=%s total=%.1fs",
                    worker_id, item.request_id[:8], process_time,
                )

            except Exception as exc:
                self._total_errors += 1
                logger.error(
                    "[Queue] Worker #%d error request=%s: %s",
                    worker_id, item.request_id[:8], exc,
                )
                if not item.future.done():
                    item.future.set_exception(exc)

            finally:
                # ── Clean up active tracking ──
                async with self._lock:
                    self._active.pop(item.request_id, None)
                    self._per_user_active[item.user_id] = max(
                        0, self._per_user_active.get(item.user_id, 0) - 1
                    )
                    # Prune zero-count entries
                    if self._per_user_active.get(item.user_id, 0) == 0:
                        self._per_user_active.pop(item.user_id, None)
                    if self._per_user_pending.get(item.user_id, 0) == 0:
                        self._per_user_pending.pop(item.user_id, None)

                self._queue.task_done()

                # ── Broadcast updated positions to remaining pending ──
                await self._notify_pending_positions()

        logger.debug("[Queue] Worker #%d stopped", worker_id)

    # ───────────────────────────────────────────────────────────────────── #
    # POSITION & NOTIFICATIONS
    # ───────────────────────────────────────────────────────────────────── #
    async def get_position(self, request_id: str) -> int:
        """
        Get current queue position (1-based).
        Returns 0 if actively processing or not found.
        """
        async with self._lock:
            if request_id in self._active:
                return 0
            keys = list(self._pending.keys())
            try:
                return keys.index(request_id) + 1
            except ValueError:
                return 0

    async def _notify_pending_positions(self):
        """Notify all pending users of their updated queue position."""
        async with self._lock:
            items = list(self._pending.values())

        for idx, item in enumerate(items):
            if item.future.done():
                continue
            pos = idx + 1
            await self._emit_safe(item.emit_fn, "queue_position", {
                "position": pos,
                "request_id": item.request_id,
                "status": "queued",
                "estimated_wait": pos * 5,
            })
            await self._emit_safe(
                item.emit_fn, "ai_status",
                {"status": f"กำลังรอคิว ลำดับที่ {pos} ..."},
            )

    @staticmethod
    async def _emit_safe(
        emit_fn: Optional[Callable],
        event: str,
        payload: dict,
    ) -> None:
        """Fire-and-forget emit with error isolation."""
        if not emit_fn:
            return
        try:
            await emit_fn(event, payload)
        except Exception:
            pass

    # ───────────────────────────────────────────────────────────────────── #
    # CANCEL
    # ───────────────────────────────────────────────────────────────────── #
    async def cancel(self, request_id: str) -> bool:
        """Cancel a pending request by request_id. Returns True if found."""
        async with self._lock:
            item = self._pending.pop(request_id, None)
            if item:
                self._per_user_pending[item.user_id] = max(
                    0, self._per_user_pending.get(item.user_id, 0) - 1
                )
                if not item.future.done():
                    item.future.cancel()
                self._total_cancelled += 1
                return True
        return False

    # ───────────────────────────────────────────────────────────────────── #
    # PERSISTENCE
    # ───────────────────────────────────────────────────────────────────── #
    def _persist_state(self) -> None:
        """บันทึก pending + active items ลง disk (sync, เรียกตอน shutdown)"""
        items_to_save = []

        # รวม pending items
        for item in self._pending.values():
            items_to_save.append({
                "request_id": item.request_id,
                "user_id": item.user_id,
                "session_id": item.session_id,
                "msg": item.msg,
                "submitted_at": item.submitted_at,
                "priority": item.priority,
            })

        # รวม active items (กำลังประมวลผลแต่ยังไม่เสร็จ)
        for item in self._active.values():
            items_to_save.append({
                "request_id": item.request_id,
                "user_id": item.user_id,
                "session_id": item.session_id,
                "msg": item.msg,
                "submitted_at": item.submitted_at,
                "priority": item.priority,
            })

        save_pending_items(items_to_save, self._persist_path)

    @staticmethod
    def check_pending_on_disk(persist_path: str = DEFAULT_PERSIST_PATH):
        """
        ตรวจสอบว่ามีคิวค้างจาก session ก่อนหน้าหรือไม่
        เรียกก่อน start() ตอน server boot

        Returns:
            dict ที่มี keys: saved_at, count, items หรือ None
        """
        return load_pending_items(persist_path)

    @staticmethod
    def format_pending_for_display(
        state: dict,
        max_display: int = 20,
    ) -> str:
        """สร้าง summary string สำหรับแสดง console"""
        return format_pending_summary(state, max_display)

    @staticmethod
    def format_pending_detailed(state: dict) -> str:
        """แสดงรายละเอียดทั้งหมด"""
        return format_detailed_list(state)

    @staticmethod
    def clear_pending_on_disk(persist_path: str = DEFAULT_PERSIST_PATH) -> bool:
        """ล้างไฟล์คิวค้าง"""
        return clear_persisted(persist_path)

    async def recover_pending(
        self,
        items: List[dict],
        send_fb_text_fn: Optional[Callable] = None,
    ) -> dict:
        """
        ประมวลผลคิวค้างจาก session ก่อนหน้า

        สำหรับ web users: ประมวลผลและบันทึกลง session history
                          (HTTP connection หายแล้ว แต่ผลลัพธ์จะอยู่ใน history)
        สำหรับ FB users: ประมวลผลและส่งตอบกลับทาง Facebook

        Args:
            items: list ของ dict (user_id, session_id, msg, ...)
            send_fb_text_fn: async callable(psid, text) สำหรับส่ง FB reply

        Returns:
            dict: {"processed": N, "errors": N, "details": [...]}
        """
        if not self._running:
            raise RuntimeError("Queue must be started before recovery")

        results = {"processed": 0, "errors": 0, "details": []}

        logger.info("[Queue Recovery] Processing %d pending items...", len(items))

        for item in items:
            user_id = item.get("user_id", "unknown")
            session_id = item.get("session_id", "unknown")
            msg = item.get("msg", "")
            is_fb = session_id.startswith("fb_")

            if not msg.strip():
                logger.warning("[Queue Recovery] Skipping empty message for %s", session_id)
                continue

            try:
                # เรียก handler โดยตรง (ไม่ผ่าน queue submit เพราะไม่มี HTTP caller รอ)
                result = await self._handler(msg, session_id)
                reply = result.get("text", "")

                # ส่ง FB reply ถ้าเป็น FB user
                if is_fb and send_fb_text_fn and reply:
                    psid = session_id.replace("fb_", "", 1)
                    fb_message = f"[Bot พี่เร็ก] {reply.replace('//', '')}"
                    try:
                        await send_fb_text_fn(psid, fb_message)
                        logger.info("[Queue Recovery] FB reply sent to %s", psid[:16])
                    except Exception as fb_exc:
                        logger.warning("[Queue Recovery] FB send failed for %s: %s", psid[:16], fb_exc)

                results["processed"] += 1
                results["details"].append({
                    "user_id": user_id,
                    "session_id": session_id,
                    "status": "ok",
                    "reply_preview": reply[:80] if reply else "",
                })

                logger.info(
                    "[Queue Recovery] ✅ %s/%s → %s",
                    user_id[:16], session_id[:16], reply[:50] if reply else "(empty)",
                )

            except Exception as exc:
                results["errors"] += 1
                results["details"].append({
                    "user_id": user_id,
                    "session_id": session_id,
                    "status": "error",
                    "error": str(exc),
                })
                logger.error(
                    "[Queue Recovery] ❌ %s/%s error: %s",
                    user_id[:16], session_id[:16], exc,
                )

        # ล้างไฟล์หลังประมวลผลเสร็จ
        clear_persisted(self._persist_path)

        logger.info(
            "[Queue Recovery] Complete: processed=%d errors=%d",
            results["processed"], results["errors"],
        )
        return results

    # ───────────────────────────────────────────────────────────────────── #
    # STATISTICS & HEALTH
    # ───────────────────────────────────────────────────────────────────── #
    def get_stats(self) -> dict:
        """Get queue statistics (thread-safe read of atomic counters)."""
        uptime = round(time.time() - self._started_at, 1) if self._started_at else 0
        throughput = (
            round(self._total_processed / max(uptime, 1) * 60, 2) if uptime > 0 else 0
        )

        return {
            "running": self._running,
            "config": {
                "max_size": self._config.max_size,
                "num_workers": self._config.num_workers,
                "per_user_limit": self._config.per_user_limit,
                "request_timeout": self._config.request_timeout,
            },
            "current": {
                "pending": len(self._pending),
                "active": len(self._active),
                "available_slots": max(
                    0,
                    self._config.max_size - len(self._pending) - len(self._active),
                ),
            },
            "totals": {
                "submitted": self._total_submitted,
                "processed": self._total_processed,
                "errors": self._total_errors,
                "timeouts": self._total_timeouts,
                "rejected": self._total_rejected,
                "cancelled": self._total_cancelled,
            },
            "peaks": {
                "max_pending": self._peak_pending,
                "max_active": self._peak_active,
            },
            "throughput_per_min": throughput,
            "uptime_seconds": uptime,
            "active_users": len(self._per_user_active),
        }

    async def _health_monitor(self):
        """Periodic health logging + crash-safe persist + worker self-healing."""
        _persist_counter = 0

        while self._running:
            try:
                await asyncio.sleep(self._config.health_log_interval)
                if not self._running:
                    break

                stats = self.get_stats()
                current = stats["current"]
                totals = stats["totals"]

                # Only log if there's activity
                if totals["submitted"] > 0 or current["pending"] > 0 or current["active"] > 0:
                    logger.info(
                        "[Queue Health] pending=%d active=%d processed=%d "
                        "errors=%d timeouts=%d rejected=%d throughput=%.1f/min",
                        current["pending"],
                        current["active"],
                        totals["processed"],
                        totals["errors"],
                        totals["timeouts"],
                        totals["rejected"],
                        stats["throughput_per_min"],
                    )

                # Warn if queue is getting full
                capacity_pct = (
                    (current["pending"] + current["active"])
                    / max(self._config.max_size, 1)
                    * 100
                )
                if capacity_pct > 75:
                    logger.warning(
                        "⚠️ [Queue] High load: %.0f%% capacity (%d/%d)",
                        capacity_pct,
                        current["pending"] + current["active"],
                        self._config.max_size,
                    )

                # ── Periodic persist (crash protection) ──
                # บันทึกทุก 5 รอบ health check (~5 นาที) ถ้ามี pending/active items
                _persist_counter += 1
                if _persist_counter >= 5 and (current["pending"] > 0 or current["active"] > 0):
                    _persist_counter = 0
                    try:
                        self._persist_state()
                        logger.debug("[Queue Health] Periodic persist: %d items saved",
                                     current["pending"] + current["active"])
                    except Exception as pe:
                        logger.warning("[Queue Health] Periodic persist failed: %s", pe)
                elif current["pending"] == 0 and current["active"] == 0:
                    _persist_counter = 0

                # ── Worker self-healing ──
                # ตรวจสอบว่า worker ตายหรือไม่ ถ้าตายให้สร้างใหม่
                dead_workers = []
                for i, task in enumerate(self._workers):
                    if task.done():
                        dead_workers.append(i)
                        exc = task.exception() if not task.cancelled() else None
                        if exc:
                            logger.error(
                                "⚠️ [Queue] Worker #%d died: %s — restarting", i, exc
                            )
                        else:
                            logger.warning(
                                "⚠️ [Queue] Worker #%d stopped unexpectedly — restarting", i
                            )

                for i in dead_workers:
                    new_task = asyncio.create_task(
                        self._worker(i), name=f"queue-worker-{i}"
                    )
                    self._workers[i] = new_task
                    logger.info("✅ [Queue] Worker #%d restarted", i)

            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error("[Queue Health] Monitor error: %s", exc)

    def _emergency_persist(self):
        """
        atexit handler — บันทึก state เมื่อ process ถูก kill/crash
        เรียกแบบ synchronous (ไม่ใช้ async) เพราะ event loop อาจปิดแล้ว
        """
        if not self._pending and not self._active:
            return
        try:
            self._persist_state()
            count = len(self._pending) + len(self._active)
            # atexit: print instead of logger (logger may be closed)
            print(f"[Queue] Emergency persist: {count} items saved to {self._persist_path}")
        except Exception:
            pass
