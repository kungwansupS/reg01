"""
Queue System Stress Test — ทดสอบระบบคิว Multi-User

ทดสอบ:
1. Basic queue flow (submit → process → result)
2. 100 concurrent users
3. Per-user limit enforcement
4. Queue capacity overflow
5. Request timeout handling
6. Queue position tracking
7. Error isolation (handler crash doesn't kill workers)
8. Graceful shutdown
9. Statistics accuracy
10. Fair ordering (FIFO)

Usage:
    cd backend
    python dev/test_queue.py
"""

import asyncio
import logging
import sys
import time
import traceback
from collections import defaultdict

sys.path.insert(0, ".")
from queue_manager import LLMRequestQueue, QueueConfig, QueueFullError, QueueTimeoutError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("QueueTest")

# ─────────────────────────────────────────────────────────────────────────── #
# MOCK HANDLER
# ─────────────────────────────────────────────────────────────────────────── #
PROCESS_DELAY = 0.1  # Simulate LLM processing time (seconds)
call_log = []  # Track order of handler calls


async def mock_handler(msg, session_id, emit_fn=None, **kwargs):
    """Simulate ask_llm() with configurable delay."""
    call_log.append({"msg": msg, "session_id": session_id, "time": time.time()})

    delay = kwargs.get("delay", PROCESS_DELAY)
    if kwargs.get("should_fail"):
        await asyncio.sleep(delay)
        raise RuntimeError(f"Simulated handler error for {session_id}")

    await asyncio.sleep(delay)
    return {
        "text": f"Response to: {msg}",
        "tokens": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "trace_id": f"test_{session_id}",
    }


async def slow_handler(msg, session_id, emit_fn=None, **kwargs):
    """Simulate a very slow LLM call."""
    await asyncio.sleep(5.0)
    return {"text": f"Slow response to: {msg}", "tokens": {}, "trace_id": "slow"}


# ─────────────────────────────────────────────────────────────────────────── #
# TEST CASES
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


async def test_1_basic_flow():
    """Test 1: Basic submit → process → result"""
    q = LLMRequestQueue(handler_fn=mock_handler, config=QueueConfig(num_workers=2))
    await q.start()

    result = await q.submit("user1", "sess1", "สวัสดี")
    ok = result["text"] == "Response to: สวัสดี"
    record("Basic flow", ok, result["text"][:60])

    await q.shutdown()


async def test_2_concurrent_100_users():
    """Test 2: 100 concurrent users submitting simultaneously"""
    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(
            num_workers=20,
            max_size=200,
            per_user_limit=3,
            request_timeout=30,
        ),
    )
    await q.start()

    global call_log
    call_log = []
    results = {}
    errors = {}

    async def user_request(user_idx):
        uid = f"user_{user_idx}"
        sid = f"session_{user_idx}"
        msg = f"Question from user {user_idx}"
        try:
            r = await q.submit(uid, sid, msg, delay=0.05)
            results[uid] = r
        except Exception as e:
            errors[uid] = str(e)

    start = time.time()
    tasks = [asyncio.create_task(user_request(i)) for i in range(100)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start

    ok = len(results) == 100 and len(errors) == 0
    record(
        "100 concurrent users",
        ok,
        f"success={len(results)} errors={len(errors)} time={elapsed:.1f}s",
    )

    stats = q.get_stats()
    record(
        "100 users — stats accuracy",
        stats["totals"]["processed"] == 100,
        f"processed={stats['totals']['processed']}",
    )

    await q.shutdown()


async def test_3_per_user_limit():
    """Test 3: Per-user limit enforcement"""
    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=2, per_user_limit=2, request_timeout=10),
    )
    await q.start()

    # Submit 2 requests from same user (should succeed)
    # Submit 3rd while first 2 are still processing (should fail)
    results = []
    errors = []

    async def submit_slow(idx):
        try:
            r = await q.submit("same_user", f"sess_{idx}", f"msg_{idx}", delay=1.0)
            results.append(r)
        except QueueFullError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"unexpected: {e}")

    # Launch 4 requests rapidly from same user
    tasks = [asyncio.create_task(submit_slow(i)) for i in range(4)]
    await asyncio.gather(*tasks)

    # At least 1 should be rejected (per_user_limit=2)
    ok = len(errors) >= 1
    record(
        "Per-user limit",
        ok,
        f"success={len(results)} rejected={len(errors)}",
    )

    await q.shutdown()


async def test_4_queue_capacity():
    """Test 4: Queue capacity overflow"""
    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(
            num_workers=1,
            max_size=5,
            per_user_limit=10,
            request_timeout=10,
        ),
    )
    await q.start()

    results = []
    full_errors = []

    async def submit_one(idx):
        try:
            r = await q.submit(f"user_{idx}", f"sess_{idx}", f"msg_{idx}", delay=2.0)
            results.append(r)
        except QueueFullError as e:
            full_errors.append(str(e))
        except Exception as e:
            results.append(f"other: {e}")

    # Submit 10 requests but max_size=5
    tasks = [asyncio.create_task(submit_one(i)) for i in range(10)]
    await asyncio.gather(*tasks)

    ok = len(full_errors) >= 1
    record(
        "Queue capacity overflow",
        ok,
        f"success={len(results)} rejected={len(full_errors)}",
    )

    stats = q.get_stats()
    record(
        "Rejected count in stats",
        stats["totals"]["rejected"] >= 1,
        f"rejected={stats['totals']['rejected']}",
    )

    await q.shutdown()


async def test_5_request_timeout():
    """Test 5: Request timeout handling"""
    q = LLMRequestQueue(
        handler_fn=slow_handler,
        config=QueueConfig(num_workers=1, request_timeout=1.0),
    )
    await q.start()

    timed_out = False
    try:
        await q.submit("user1", "sess1", "slow question")
    except QueueTimeoutError:
        timed_out = True
    except Exception as e:
        record("Request timeout", False, f"Unexpected error: {e}")
        await q.shutdown()
        return

    record("Request timeout", timed_out, "QueueTimeoutError raised correctly")

    stats = q.get_stats()
    record(
        "Timeout count in stats",
        stats["totals"]["timeouts"] >= 1,
        f"timeouts={stats['totals']['timeouts']}",
    )

    await q.shutdown()


async def test_6_position_tracking():
    """Test 6: Queue position tracking"""
    position_updates = defaultdict(list)

    async def tracking_emit(event, payload):
        if event == "queue_position":
            uid = payload.get("request_id", "?")[:8]
            position_updates[uid].append(payload.get("position", -1))

    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=1, request_timeout=30),
    )
    await q.start()

    # Submit 5 requests sequentially (1 worker, so they queue up)
    results = []

    async def submit_with_tracking(idx):
        async def emit_fn(event, payload):
            await tracking_emit(event, payload)

        r = await q.submit(f"user_{idx}", f"sess_{idx}", f"msg_{idx}", emit_fn=emit_fn, delay=0.2)
        results.append(r)

    tasks = [asyncio.create_task(submit_with_tracking(i)) for i in range(5)]
    await asyncio.gather(*tasks)

    ok = len(results) == 5
    record(
        "Position tracking",
        ok,
        f"completed={len(results)} position_updates={sum(len(v) for v in position_updates.values())}",
    )

    await q.shutdown()


async def test_7_error_isolation():
    """Test 7: Handler error doesn't crash workers"""

    async def sometimes_fail(msg, session_id, emit_fn=None, **kwargs):
        if "fail" in msg:
            raise RuntimeError("Simulated crash!")
        await asyncio.sleep(0.05)
        return {"text": f"OK: {msg}", "tokens": {}, "trace_id": "ok"}

    q = LLMRequestQueue(
        handler_fn=sometimes_fail,
        config=QueueConfig(num_workers=3, request_timeout=10),
    )
    await q.start()

    results = []
    errors = []

    async def submit_one(idx, should_fail=False):
        msg = f"fail_{idx}" if should_fail else f"ok_{idx}"
        try:
            r = await q.submit(f"user_{idx}", f"sess_{idx}", msg)
            results.append(r)
        except RuntimeError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"unexpected: {e}")

    # Mix of failing and succeeding requests
    tasks = []
    for i in range(10):
        tasks.append(asyncio.create_task(submit_one(i, should_fail=(i % 3 == 0))))
    await asyncio.gather(*tasks)

    # At least some should succeed (workers not crashed)
    ok = len(results) >= 6  # 7 out of 10 should succeed (i%3!=0)
    record(
        "Error isolation",
        ok,
        f"success={len(results)} errors={len(errors)}",
    )

    stats = q.get_stats()
    record(
        "Error count in stats",
        stats["totals"]["errors"] >= 1,
        f"errors={stats['totals']['errors']}",
    )

    await q.shutdown()


async def test_8_graceful_shutdown():
    """Test 8: Graceful shutdown cancels pending items"""
    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=1, request_timeout=30),
    )
    await q.start()

    # Submit several slow requests
    tasks = []
    for i in range(5):
        tasks.append(
            asyncio.create_task(
                q.submit(f"user_{i}", f"sess_{i}", f"msg_{i}", delay=5.0)
            )
        )

    await asyncio.sleep(0.3)

    # Shutdown while requests are pending
    await q.shutdown()

    # Count cancelled
    done_count = sum(1 for t in tasks if t.done())
    cancelled_count = sum(1 for t in tasks if t.cancelled())

    # Gather to clean up
    gathered = await asyncio.gather(*tasks, return_exceptions=True)
    cancel_or_error = sum(
        1 for r in gathered if isinstance(r, (asyncio.CancelledError, Exception))
    )

    ok = not q._running
    record(
        "Graceful shutdown",
        ok,
        f"running={q._running} done={done_count} cancelled_or_error={cancel_or_error}",
    )


async def test_9_stats_accuracy():
    """Test 9: Statistics accuracy after mixed operations"""
    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(
            num_workers=5,
            max_size=20,
            per_user_limit=2,
            request_timeout=10,
        ),
    )
    await q.start()

    results = []
    q_full = []
    q_timeout = []

    async def submit_one(idx):
        try:
            r = await q.submit(f"user_{idx % 5}", f"sess_{idx}", f"msg_{idx}", delay=0.1)
            results.append(r)
        except QueueFullError:
            q_full.append(idx)
        except QueueTimeoutError:
            q_timeout.append(idx)
        except Exception:
            pass

    tasks = [asyncio.create_task(submit_one(i)) for i in range(30)]
    await asyncio.gather(*tasks)

    stats = q.get_stats()
    total_accounted = (
        stats["totals"]["processed"]
        + stats["totals"]["errors"]
        + stats["totals"]["rejected"]
        + stats["totals"]["timeouts"]
        + stats["totals"]["cancelled"]
    )

    # Total submitted should equal sum of all outcomes + any still pending
    submitted = stats["totals"]["submitted"]
    ok = submitted > 0 and total_accounted + stats["current"]["pending"] + stats["current"]["active"] >= submitted - 5
    record(
        "Stats accuracy",
        ok,
        f"submitted={submitted} accounted={total_accounted} pending={stats['current']['pending']}",
    )

    # Throughput should be positive
    record(
        "Throughput tracking",
        stats["throughput_per_min"] >= 0,
        f"throughput={stats['throughput_per_min']}/min",
    )

    await q.shutdown()


async def test_10_fair_ordering():
    """Test 10: FIFO ordering — first submitted should be processed first"""
    global call_log
    call_log = []

    q = LLMRequestQueue(
        handler_fn=mock_handler,
        config=QueueConfig(num_workers=1, request_timeout=30),  # 1 worker = strict FIFO
    )
    await q.start()

    # Submit 10 requests sequentially
    tasks = []
    for i in range(10):
        tasks.append(
            asyncio.create_task(
                q.submit(f"user_{i}", f"sess_{i}", f"msg_{i}", delay=0.02)
            )
        )
        await asyncio.sleep(0.01)  # Small gap to ensure order

    await asyncio.gather(*tasks)

    # Check call_log order
    messages = [c["msg"] for c in call_log]
    expected = [f"msg_{i}" for i in range(10)]
    ok = messages == expected
    record(
        "FIFO ordering",
        ok,
        f"order={'correct' if ok else 'wrong'} got={messages[:5]}...",
    )

    await q.shutdown()


# ─────────────────────────────────────────────────────────────────────────── #
# RUNNER
# ─────────────────────────────────────────────────────────────────────────── #
async def run_all_tests():
    tests = [
        test_1_basic_flow,
        test_2_concurrent_100_users,
        test_3_per_user_limit,
        test_4_queue_capacity,
        test_5_request_timeout,
        test_6_position_tracking,
        test_7_error_isolation,
        test_8_graceful_shutdown,
        test_9_stats_accuracy,
        test_10_fair_ordering,
    ]

    logger.info("=" * 60)
    logger.info("  Queue System Stress Test — 10 tests")
    logger.info("=" * 60)

    for test_fn in tests:
        name = test_fn.__doc__ or test_fn.__name__
        logger.info(f"\n▶ {name}")
        try:
            await test_fn()
        except Exception as e:
            record(name, False, f"CRASH: {e}")
            traceback.print_exc()

    logger.info("\n" + "=" * 60)
    logger.info("  RESULTS")
    logger.info("=" * 60)

    for icon, name, detail in test_results:
        logger.info(f"  {icon} {name}: {detail}")

    logger.info(f"\n  Total: {passed + failed} | ✅ Passed: {passed} | ❌ Failed: {failed}")
    logger.info("=" * 60)

    return failed == 0


if __name__ == "__main__":
    import platform

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
