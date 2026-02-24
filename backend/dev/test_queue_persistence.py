"""
Queue Persistence & Recovery Test (Redis backend)

ทดสอบ:
1.  Save pending items to Redis
2.  Load pending items from Redis
3.  Clear persisted state
4.  Corrupted data handling
5.  Empty data handling
6.  Invalid items filtering
7.  Format summary display
8.  Format detailed display
9.  Shutdown persists state (pending + active)
10. Recovery processes items correctly
11. Recovery sends FB replies
12. Recovery handles handler errors gracefully
13. Recovery clears key after completion
14. Persistence survives rapid save/load cycles
15. Edge case: very long messages
16. Edge case: save empty clears key
17. Loading nonexistent key returns None
18. Recovery skips empty messages
19. Format summary age strings
20. LLMRequestQueue static async methods

Usage:
    cd backend
    python dev/test_queue_persistence.py

Requires:
    - Redis server running (REDIS_URL env or redis://localhost:6379/0)
"""

import asyncio
import json
import logging
import os
import platform
import sys
import time
import traceback

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv()

from memory.redis_client import init_redis, close_redis, get_redis
from queue_manager import LLMRequestQueue, QueueConfig
from queue_manager.persistence import (
    save_pending_items,
    load_pending_items,
    clear_persisted,
    format_pending_summary,
    format_detailed_list,
    REDIS_QUEUE_KEY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("PersistenceTest")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─────────────────────────────────────────────────────────────────────────── #
# TEST INFRASTRUCTURE
# ─────────────────────────────────────────────────────────────────────────── #
passed = 0
failed = 0
test_results = []


def record(name, success, detail=""):
    global passed, failed
    if success:
        passed += 1
        test_results.append(("✅", name, detail))
    else:
        failed += 1
        test_results.append(("❌", name, detail))


async def clear_test_key():
    """Clear the Redis queue key before each test."""
    r = get_redis()
    await r.delete(REDIS_QUEUE_KEY)


def sample_items(n=5):
    return [
        {
            "request_id": f"req_{i:04d}",
            "user_id": f"user_{i}",
            "session_id": f"sess_{i}" if i % 2 == 0 else f"fb_{i}",
            "msg": f"คำถามที่ {i} จากผู้ใช้",
            "submitted_at": time.time() - (n - i) * 10,
            "priority": 0,
        }
        for i in range(n)
    ]


# ─────────────────────────────────────────────────────────────────────────── #
# MOCK HANDLERS
# ─────────────────────────────────────────────────────────────────────────── #
handler_calls = []
fb_sent = []


async def mock_handler(msg, session_id, emit_fn=None, **kwargs):
    handler_calls.append({"msg": msg, "session_id": session_id})
    await asyncio.sleep(0.05)
    return {"text": f"ตอบ: {msg}", "tokens": {}, "trace_id": "test"}


async def failing_handler(msg, session_id, emit_fn=None, **kwargs):
    if "fail" in msg:
        raise RuntimeError(f"Handler error for {session_id}")
    await asyncio.sleep(0.05)
    return {"text": f"OK: {msg}", "tokens": {}, "trace_id": "test"}


async def mock_send_fb(psid, text):
    fb_sent.append({"psid": psid, "text": text})


# ─────────────────────────────────────────────────────────────────────────── #
# TESTS (all async)
# ─────────────────────────────────────────────────────────────────────────── #
async def test_01_save():
    """Test 1: Save pending items to Redis"""
    await clear_test_key()
    items = sample_items(3)
    ok = await save_pending_items(items)
    r = get_redis()
    exists = await r.exists(REDIS_QUEUE_KEY)
    record("Save to Redis", ok and exists, f"saved={ok} exists={exists}")


async def test_02_load():
    """Test 2: Load pending items from Redis"""
    await clear_test_key()
    items = sample_items(5)
    await save_pending_items(items)
    state = await load_pending_items()
    ok = state is not None and state["count"] == 5
    record("Load from Redis", ok, f"count={state['count'] if state else 0}")


async def test_03_clear():
    """Test 3: Clear persisted state"""
    await clear_test_key()
    await save_pending_items(sample_items(2))
    await clear_persisted()
    r = get_redis()
    exists = await r.exists(REDIS_QUEUE_KEY)
    ok = not exists
    record("Clear persisted", ok)


async def test_04_corrupted_data():
    """Test 4: Corrupted data handling"""
    r = get_redis()
    await r.set(REDIS_QUEUE_KEY, "{invalid json!!!")
    state = await load_pending_items()
    ok = state is None
    # Should have cleared the corrupted key
    exists = await r.exists(REDIS_QUEUE_KEY)
    record("Corrupted data handling", ok and not exists, f"state=None cleared={not exists}")


async def test_05_empty_data():
    """Test 5: Empty data handling"""
    r = get_redis()
    await r.set(REDIS_QUEUE_KEY, json.dumps({"items": [], "count": 0, "saved_at": "test"}))
    state = await load_pending_items()
    ok = state is None  # Empty items should return None
    record("Empty data handling", ok)


async def test_06_invalid_items():
    """Test 6: Invalid items filtering"""
    r = get_redis()
    items = [
        {"user_id": "u1", "session_id": "s1", "msg": "valid"},
        {"user_id": "u2"},  # missing session_id and msg
        "not a dict",
        {"user_id": "u3", "session_id": "s3", "msg": "also valid"},
    ]
    await r.set(REDIS_QUEUE_KEY, json.dumps({"items": items, "count": 4, "saved_at": "test"}))
    state = await load_pending_items()
    ok = state is not None and state["count"] == 2
    record("Invalid items filtering", ok, f"valid_count={state['count'] if state else 0}")


def test_07_format_summary():
    """Test 7: Format summary display"""
    items = sample_items(10)
    state = {"items": items, "count": 10, "saved_at": "2026-02-17T18:00:00", "saved_at_ts": time.time() - 300}
    text = format_pending_summary(state, max_display=5)
    ok = "พบคิวค้าง" in text and "10 รายการ" in text and "อีก 5 รายการ" in text
    record("Format summary", ok, f"lines={len(text.splitlines())}")


def test_08_format_detailed():
    """Test 8: Format detailed display"""
    items = sample_items(3)
    state = {"items": items, "count": 3, "saved_at": "test"}
    text = format_detailed_list(state)
    ok = "รายการที่ 1" in text and "รายการที่ 3" in text
    record("Format detailed", ok, f"lines={len(text.splitlines())}")


async def test_09_shutdown_persists():
    """Test 9: Shutdown persists pending + active items"""
    await clear_test_key()

    async def slow_handler(msg, session_id, emit_fn=None, **kwargs):
        await asyncio.sleep(5.0)
        return {"text": msg, "tokens": {}}

    q = LLMRequestQueue(
        handler_fn=slow_handler,
        config=QueueConfig(num_workers=1, request_timeout=30),
    )
    await q.start()

    # Submit 3 items — 1 will be active, 2 pending
    tasks = []
    for i in range(3):
        tasks.append(asyncio.create_task(
            q.submit(f"user_{i}", f"sess_{i}", f"msg_{i}")
        ))

    await asyncio.sleep(0.3)  # Let 1 become active

    await q.shutdown()

    # Check persisted key
    state = await load_pending_items()
    ok = state is not None and state["count"] >= 1
    record(
        "Shutdown persists state",
        ok,
        f"persisted={state['count'] if state else 0} items",
    )

    # Clean up tasks
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await clear_persisted()


async def test_10_recovery_processes():
    """Test 10: Recovery processes items correctly"""
    global handler_calls
    handler_calls = []
    await clear_test_key()

    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=3),
    )
    await q.start()

    items = sample_items(5)
    result = await q.recover_pending(items)

    ok = result["processed"] == 5 and result["errors"] == 0
    record("Recovery processes items", ok, f"processed={result['processed']} errors={result['errors']}")

    # Verify handler was called for each
    ok2 = len(handler_calls) == 5
    record("Recovery called handler for all", ok2, f"calls={len(handler_calls)}")

    await q.shutdown()


async def test_11_recovery_sends_fb():
    """Test 11: Recovery sends FB replies"""
    global fb_sent
    fb_sent = []
    await clear_test_key()

    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=2),
    )
    await q.start()

    items = [
        {"user_id": "fb_123", "session_id": "fb_123", "msg": "FB question 1"},
        {"user_id": "web_456", "session_id": "web_456", "msg": "Web question"},
        {"user_id": "fb_789", "session_id": "fb_789", "msg": "FB question 2"},
    ]
    result = await q.recover_pending(items, send_fb_text_fn=mock_send_fb)

    ok = result["processed"] == 3
    fb_count = len(fb_sent)
    ok2 = fb_count == 2  # Only FB items get FB replies
    record("Recovery sends FB replies", ok and ok2, f"fb_sent={fb_count}")

    # Verify correct PSIDs
    psids = [s["psid"] for s in fb_sent]
    ok3 = "123" in psids and "789" in psids
    record("Recovery correct FB PSIDs", ok3, f"psids={psids}")

    await q.shutdown()


async def test_12_recovery_error_handling():
    """Test 12: Recovery handles handler errors gracefully"""
    await clear_test_key()

    q = LLMRequestQueue(
        handler_fn=failing_handler,
        config=QueueConfig(num_workers=2),
    )
    await q.start()

    items = [
        {"user_id": "u1", "session_id": "s1", "msg": "normal question"},
        {"user_id": "u2", "session_id": "s2", "msg": "fail this one"},
        {"user_id": "u3", "session_id": "s3", "msg": "another normal"},
    ]
    result = await q.recover_pending(items)

    ok = result["processed"] == 2 and result["errors"] == 1
    record("Recovery error handling", ok, f"processed={result['processed']} errors={result['errors']}")

    # Check details
    error_items = [d for d in result["details"] if d["status"] == "error"]
    ok2 = len(error_items) == 1 and "Handler error" in error_items[0].get("error", "")
    record("Recovery error details", ok2, f"error_msg={error_items[0].get('error', '')[:40] if error_items else 'none'}")

    await q.shutdown()


async def test_13_recovery_clears_key():
    """Test 13: Recovery clears Redis key after completion"""
    await clear_test_key()

    # Pre-save items
    await save_pending_items(sample_items(3))
    r = get_redis()
    assert await r.exists(REDIS_QUEUE_KEY), "Key should exist before recovery"

    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=2),
    )
    await q.start()

    items = sample_items(3)
    await q.recover_pending(items)

    exists = await r.exists(REDIS_QUEUE_KEY)
    ok = not exists
    record("Recovery clears Redis key", ok)

    await q.shutdown()


async def test_14_rapid_save_load():
    """Test 14: Persistence survives rapid save/load cycles"""
    errors = 0

    for i in range(50):
        items = sample_items(i % 10 + 1)
        if not await save_pending_items(items):
            errors += 1
        state = await load_pending_items()
        if state is None or state["count"] != len(items):
            errors += 1

    ok = errors == 0
    record("Rapid save/load (50 cycles)", ok, f"errors={errors}")
    await clear_persisted()


async def test_15_long_messages():
    """Test 15: Very long messages"""
    await clear_test_key()
    items = [
        {
            "user_id": "u1",
            "session_id": "s1",
            "msg": "ก" * 10000,  # 10K chars
            "submitted_at": time.time(),
        },
        {
            "user_id": "u2",
            "session_id": "s2",
            "msg": "A" * 50000,  # 50K chars
            "submitted_at": time.time(),
        },
    ]
    await save_pending_items(items)
    state = await load_pending_items()
    ok = state is not None and state["count"] == 2
    # Verify message integrity
    ok2 = len(state["items"][0]["msg"]) == 10000 and len(state["items"][1]["msg"]) == 50000
    record("Long messages persist", ok and ok2, f"msg_lens={[len(i['msg']) for i in state['items']]}")
    await clear_persisted()


async def test_16_save_no_items_clears():
    """Test 16: Saving empty list clears existing key"""
    await clear_test_key()

    # Create key first
    await save_pending_items(sample_items(3))
    r = get_redis()
    assert await r.exists(REDIS_QUEUE_KEY)

    # Save empty → should delete key
    await save_pending_items([])
    exists = await r.exists(REDIS_QUEUE_KEY)
    ok = not exists
    record("Empty save clears key", ok)


async def test_17_nonexistent_load():
    """Test 17: Loading nonexistent key returns None"""
    await clear_test_key()
    state = await load_pending_items()
    ok = state is None
    record("Nonexistent key returns None", ok)


async def test_18_recovery_skips_empty_msg():
    """Test 18: Recovery skips items with empty messages"""
    global handler_calls
    handler_calls = []
    await clear_test_key()

    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=2),
    )
    await q.start()

    items = [
        {"user_id": "u1", "session_id": "s1", "msg": "valid"},
        {"user_id": "u2", "session_id": "s2", "msg": ""},
        {"user_id": "u3", "session_id": "s3", "msg": "   "},
        {"user_id": "u4", "session_id": "s4", "msg": "also valid"},
    ]
    result = await q.recover_pending(items)

    ok = result["processed"] == 2  # Only 2 valid msgs
    record("Recovery skips empty msgs", ok, f"processed={result['processed']}")

    await q.shutdown()


def test_19_format_summary_age():
    """Test 19: Format summary shows correct age strings"""
    # 30 seconds ago
    state1 = {"items": sample_items(1), "count": 1, "saved_at": "test", "saved_at_ts": time.time() - 30}
    text1 = format_pending_summary(state1)
    ok1 = "วินาที" in text1

    # 2 hours ago
    state2 = {"items": sample_items(1), "count": 1, "saved_at": "test", "saved_at_ts": time.time() - 7200}
    text2 = format_pending_summary(state2)
    ok2 = "ชั่วโมง" in text2

    # 3 days ago
    state3 = {"items": sample_items(1), "count": 1, "saved_at": "test", "saved_at_ts": time.time() - 259200}
    text3 = format_pending_summary(state3)
    ok3 = "วัน" in text3

    record("Summary age strings", ok1 and ok2 and ok3, f"sec={ok1} hr={ok2} day={ok3}")


async def test_20_static_methods():
    """Test 20: LLMRequestQueue static async methods work correctly"""
    await clear_test_key()

    # Save via persistence directly
    await save_pending_items(sample_items(3))

    # Use static methods (now async)
    state = await LLMRequestQueue.check_pending_on_disk()
    ok1 = state is not None and state["count"] == 3

    summary = LLMRequestQueue.format_pending_for_display(state)
    ok2 = "พบคิวค้าง" in summary

    detailed = LLMRequestQueue.format_pending_detailed(state)
    ok3 = "รายการที่ 1" in detailed

    await LLMRequestQueue.clear_pending_on_disk()
    r = get_redis()
    exists = await r.exists(REDIS_QUEUE_KEY)
    ok4 = not exists

    record("Static methods", ok1 and ok2 and ok3 and ok4, f"check={ok1} summary={ok2} detail={ok3} clear={ok4}")


# ─────────────────────────────────────────────────────────────────────────── #
# RUNNER
# ─────────────────────────────────────────────────────────────────────────── #
async def run_all_tests():
    # Initialize Redis
    await init_redis(REDIS_URL)
    logger.info("✅ Redis connected for testing")

    # Pure display tests (sync — no Redis needed)
    sync_tests = [
        test_07_format_summary,
        test_08_format_detailed,
        test_19_format_summary_age,
    ]

    # All persistence & recovery tests (async — need Redis)
    async_tests = [
        test_01_save,
        test_02_load,
        test_03_clear,
        test_04_corrupted_data,
        test_05_empty_data,
        test_06_invalid_items,
        test_09_shutdown_persists,
        test_10_recovery_processes,
        test_11_recovery_sends_fb,
        test_12_recovery_error_handling,
        test_13_recovery_clears_key,
        test_14_rapid_save_load,
        test_15_long_messages,
        test_16_save_no_items_clears,
        test_17_nonexistent_load,
        test_18_recovery_skips_empty_msg,
        test_20_static_methods,
    ]

    logger.info("=" * 60)
    logger.info("  Queue Persistence & Recovery Test (Redis) — 20 tests")
    logger.info("=" * 60)

    for test_fn in sync_tests:
        name = test_fn.__doc__ or test_fn.__name__
        logger.info(f"\n▶ {name}")
        try:
            test_fn()
        except Exception as e:
            record(name, False, f"CRASH: {e}")
            traceback.print_exc()

    for test_fn in async_tests:
        name = test_fn.__doc__ or test_fn.__name__
        logger.info(f"\n▶ {name}")
        try:
            await test_fn()
        except Exception as e:
            record(name, False, f"CRASH: {e}")
            traceback.print_exc()

    # Cleanup
    await clear_test_key()
    await close_redis()

    logger.info("\n" + "=" * 60)
    logger.info("  RESULTS")
    logger.info("=" * 60)

    for icon, name, detail in test_results:
        logger.info(f"  {icon} {name}: {detail}")

    logger.info(f"\n  Total: {passed + failed} | ✅ Passed: {passed} | ❌ Failed: {failed}")
    logger.info("=" * 60)

    return failed == 0


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
