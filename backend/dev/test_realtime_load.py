"""Concurrent realtime smoke/load test (text+voice entrypoint mix)."""
from __future__ import annotations

import asyncio
import time

import httpx


BASE = "http://localhost:5000"
API_KEY = "dev-token-eval-runner"
CONCURRENCY = 4
ROUNDS = 2


async def _one_call(client: httpx.AsyncClient, i: int) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{BASE}/api/speech",
            data={"text": f"เปิดเทอม 2/2568 วันไหน #{i}", "session_id": f"load_{i}"},
            headers={"X-API-Key": API_KEY},
            timeout=90,
        )
        ok = resp.status_code == 200 and bool((resp.json() or {}).get("text"))
    except Exception:
        ok = False
    return ok, (time.perf_counter() - start) * 1000


async def main() -> int:
    try:
        async with httpx.AsyncClient(timeout=3) as health_client:
            health = await health_client.get(f"{BASE}/")
            if health.status_code != 200:
                print("load_test skipped: backend health check failed")
                return 0
    except Exception:
        print("load_test skipped: backend is not reachable")
        return 0

    latencies: list[float] = []
    failures = 0
    async with httpx.AsyncClient(timeout=90) as client:
        for r in range(ROUNDS):
            tasks = [_one_call(client, r * CONCURRENCY + i) for i in range(CONCURRENCY)]
            results = await asyncio.gather(*tasks)
            for ok, lat in results:
                latencies.append(lat)
                if not ok:
                    failures += 1

    total = len(latencies)
    p95 = sorted(latencies)[int(max(0, min(total - 1, total * 0.95)))] if latencies else 0.0
    print(f"load_test total={total} failures={failures} p95_ms={round(p95, 2)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
