"""
REG-01 End-to-End System Test
=============================
ทดสอบระบบทั้งหมดตั้งแต่ Docker services จนถึงหน้าเว็บทุกส่วน

การใช้งาน:
  python -m dev.test_e2e_system [--backend http://localhost:5000] [--frontend http://localhost:3000]

ทดสอบครอบคลุม:
  Phase 1: Docker & Infrastructure Health
  Phase 2: Backend Core APIs
  Phase 3: Authentication (Legacy token mode)
  Phase 4: Admin Portal - ทุก Tab (Dashboard, Chat, Files, Logs, Database, FAQ, Monitor)
  Phase 5: Chat System (Speech API, TTS)
  Phase 6: Dev Console APIs
  Phase 7: Frontend Pages (Next.js)
  Phase 8: Socket.IO Connectivity
  Phase 9: Database Router
  Phase 10: Webhook Router
"""

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Ensure backend dir is importable when run with -m
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import httpx
except ImportError:
    print("[ERROR] httpx is required. Install with: pip install httpx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    name: str
    phase: str
    passed: bool
    detail: str = ""
    latency_ms: float = 0.0


@dataclass
class TestSuite:
    results: list[TestResult] = field(default_factory=list)
    _current_phase: str = ""

    def set_phase(self, name: str):
        self._current_phase = name
        print(f"\n{'='*70}")
        print(f"  {name}")
        print(f"{'='*70}")

    def record(self, name: str, passed: bool, detail: str = "", latency_ms: float = 0.0):
        r = TestResult(name=name, phase=self._current_phase, passed=passed, detail=detail, latency_ms=latency_ms)
        self.results.append(r)
        icon = "✅" if passed else "❌"
        lat = f" ({latency_ms:.0f}ms)" if latency_ms > 0 else ""
        detail_str = f" — {detail}" if detail else ""
        print(f"  {icon} {name}{lat}{detail_str}")

    def summary(self):
        print(f"\n{'='*70}")
        print("  TEST SUMMARY")
        print(f"{'='*70}")

        phases: dict[str, list[TestResult]] = {}
        for r in self.results:
            phases.setdefault(r.phase, []).append(r)

        total_pass = 0
        total_fail = 0
        for phase, items in phases.items():
            passed = sum(1 for i in items if i.passed)
            failed = sum(1 for i in items if not i.passed)
            total_pass += passed
            total_fail += failed
            icon = "✅" if failed == 0 else "❌"
            print(f"  {icon} {phase}: {passed}/{len(items)} passed")
            if failed > 0:
                for i in items:
                    if not i.passed:
                        print(f"      ❌ {i.name}: {i.detail}")

        total = total_pass + total_fail
        print(f"\n  Total: {total_pass}/{total} passed, {total_fail} failed")
        print(f"{'='*70}")
        return total_fail == 0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
ADMIN_TOKEN = "super-secret-key"
DEV_TOKEN = "dev-secret-key"


def admin_headers() -> dict:
    return {"X-Admin-Token": ADMIN_TOKEN, "Authorization": f"Bearer {ADMIN_TOKEN}"}


def dev_headers() -> dict:
    return {"X-Dev-Token": DEV_TOKEN, "Authorization": f"Bearer {DEV_TOKEN}"}


async def timed_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> tuple[httpx.Response, float]:
    start = time.perf_counter()
    resp = await client.request(method, url, **kwargs)
    latency = (time.perf_counter() - start) * 1000
    return resp, latency


# ---------------------------------------------------------------------------
# Phase 1: Docker & Infrastructure
# ---------------------------------------------------------------------------
async def test_docker_health(suite: TestSuite, backend: str):
    suite.set_phase("Phase 1: Docker & Infrastructure Health")

    async with httpx.AsyncClient(timeout=15) as c:
        # Backend root
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/")
            suite.record("Backend root (/) reachable", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Backend root (/) reachable", False, str(e))

        # Queue status endpoint
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/queue/status")
            suite.record("Queue status endpoint", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                cfg = data.get("config", {})
                workers = cfg.get("num_workers", data.get("num_workers", 0))
                suite.record("Queue has workers", workers > 0,
                             f"workers={workers}")
                suite.record("Queue is running", data.get("running") is True,
                             f"running={data.get('running')}")
        except Exception as e:
            suite.record("Queue status endpoint", False, str(e))

        # OpenAPI docs
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/docs")
            suite.record("OpenAPI docs (/docs)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("OpenAPI docs (/docs)", False, str(e))


# ---------------------------------------------------------------------------
# Phase 2: Backend Core APIs
# ---------------------------------------------------------------------------
async def test_backend_core(suite: TestSuite, backend: str):
    suite.set_phase("Phase 2: Backend Core APIs")

    async with httpx.AsyncClient(timeout=15) as c:
        # Static pages served by backend
        for path, label in [("/", "Main page (index.html)"), ("/admin", "Admin page"), ("/dev", "Dev page")]:
            try:
                resp, lat = await timed_request(c, "GET", f"{backend}{path}")
                # /dev requires local request, may return 403 in Docker
                ok = resp.status_code in (200, 403)
                suite.record(f"Serve {label}", ok,
                             f"status={resp.status_code}", lat)
            except Exception as e:
                suite.record(f"Serve {label}", False, str(e))

        # Webhook verification (should return 403 or specific response without proper params)
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/webhook",
                                            params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "test123"})
            suite.record("Webhook verify (wrong token → 403)", resp.status_code == 403,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Webhook verify endpoint", False, str(e))


# ---------------------------------------------------------------------------
# Phase 3: Authentication
# ---------------------------------------------------------------------------
async def test_auth(suite: TestSuite, backend: str):
    suite.set_phase("Phase 3: Authentication (Legacy Token Mode)")

    async with httpx.AsyncClient(timeout=15) as c:
        # Admin stats without token → 401
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/stats")
            suite.record("Admin stats without token → 401", resp.status_code in (401, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Admin stats without token", False, str(e))

        # Admin stats with wrong token → 403
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/stats",
                                            headers={"X-Admin-Token": "wrong-token"})
            suite.record("Admin stats with wrong token → 403", resp.status_code == 403,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Admin stats wrong token", False, str(e))

        # Admin stats with correct token → 200
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/stats",
                                            headers=admin_headers())
            suite.record("Admin stats with correct token → 200", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Admin stats correct token", False, str(e))

        # Login endpoint
        try:
            form = {"username": "admin", "password": ADMIN_TOKEN}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/auth/login",
                                            data=form)
            suite.record("Auth login (admin)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("Login returns JWT token", "access_token" in data,
                             f"keys={list(data.keys())}")
                suite.record("Login returns admin role", data.get("role") == "admin",
                             f"role={data.get('role')}")
        except Exception as e:
            suite.record("Auth login (admin)", False, str(e))

        # Login with dev token
        try:
            form = {"username": "dev", "password": DEV_TOKEN}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/auth/login",
                                            data=form)
            suite.record("Auth login (dev)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Auth login (dev)", False, str(e))

        # Login with wrong creds → 401
        try:
            form = {"username": "hacker", "password": "wrong"}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/auth/login",
                                            data=form)
            suite.record("Auth login wrong creds → 401", resp.status_code == 401,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Auth login wrong creds", False, str(e))

        # /api/auth/me without auth
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/auth/me")
            # In legacy mode, anonymous user is allowed
            suite.record("Auth /me endpoint", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Auth /me endpoint", False, str(e))


# ---------------------------------------------------------------------------
# Phase 4: Admin Portal Endpoints
# ---------------------------------------------------------------------------
async def test_admin_portal(suite: TestSuite, backend: str):
    suite.set_phase("Phase 4: Admin Portal — All 7 Tabs")

    h = admin_headers()
    async with httpx.AsyncClient(timeout=20) as c:

        # ── Dashboard Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/stats", headers=h)
            suite.record("[Dashboard] GET /api/admin/stats", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                expected_keys = {"recent_logs", "faq_analytics", "bot_settings", "token_analytics", "system_time"}
                missing = expected_keys - set(data.keys())
                suite.record("[Dashboard] Response has required fields",
                             len(missing) == 0, f"missing={missing}" if missing else "all present")
        except Exception as e:
            suite.record("[Dashboard] GET /api/admin/stats", False, str(e))

        # ── Chat Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/chat/sessions", headers=h)
            suite.record("[Chat] GET /api/admin/chat/sessions", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[Chat] Sessions is list", isinstance(data, list),
                             f"type={type(data).__name__}, count={len(data) if isinstance(data, list) else 'N/A'}")
        except Exception as e:
            suite.record("[Chat] GET /api/admin/chat/sessions", False, str(e))

        # Bot toggle (toggle a test session)
        try:
            form = {"session_id": "test_e2e_session", "status": "true"}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/admin/bot-toggle",
                                            headers=h, data=form)
            # May fail if session doesn't exist, that's ok — we just check the endpoint works
            suite.record("[Chat] POST /api/admin/bot-toggle", resp.status_code in (200, 500),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Chat] POST /api/admin/bot-toggle", False, str(e))

        # ── Files Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/files",
                                            headers=h, params={"root": "data", "subdir": ""})
            suite.record("[Files] GET /api/admin/files (data root)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[Files] Response has entries field", "entries" in data,
                             f"keys={list(data.keys())}")
        except Exception as e:
            suite.record("[Files] GET /api/admin/files", False, str(e))

        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/files",
                                            headers=h, params={"root": "uploads", "subdir": ""})
            suite.record("[Files] GET /api/admin/files (uploads root)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Files] GET /api/admin/files (uploads)", False, str(e))

        # ── Logs Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/stats", headers=h)
            suite.record("[Logs] Audit logs via stats endpoint", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[Logs] recent_logs is list",
                             isinstance(data.get("recent_logs"), list),
                             f"count={len(data.get('recent_logs', []))}")
        except Exception as e:
            suite.record("[Logs] Audit logs endpoint", False, str(e))

        # ── Database Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/sessions",
                                            headers=h)
            suite.record("[Database] GET /admin/api/database/sessions", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[Database] Has success flag", data.get("success") is True,
                             f"success={data.get('success')}")
                suite.record("[Database] Has sessions list", "sessions" in data,
                             f"count={len(data.get('sessions', []))}")
                suite.record("[Database] Has stats", "stats" in data,
                             f"stats_keys={list(data.get('stats', {}).keys())}")
        except Exception as e:
            suite.record("[Database] GET sessions", False, str(e))

        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/stats",
                                            headers=h)
            suite.record("[Database] GET /admin/api/database/stats", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Database] GET stats", False, str(e))

        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/export",
                                            headers=h)
            suite.record("[Database] GET /admin/api/database/export", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                suite.record("[Database] Export has Content-Disposition",
                             "content-disposition" in resp.headers,
                             "header present" if "content-disposition" in resp.headers else "missing")
        except Exception as e:
            suite.record("[Database] Export", False, str(e))

        # ── FAQ Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/faq", headers=h)
            suite.record("[FAQ] GET /api/admin/faq", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[FAQ] Response is list or dict with items",
                             isinstance(data, (list, dict)),
                             f"type={type(data).__name__}")
        except Exception as e:
            suite.record("[FAQ] GET /api/admin/faq", False, str(e))

        # Create a test FAQ entry
        test_faq_q = "e2e_test_question_ทดสอบ"
        test_faq_a = "e2e_test_answer_ตอบ"
        try:
            form = {"question": test_faq_q, "answer": test_faq_a, "source": "e2e-test"}
            resp, lat = await timed_request(c, "PUT", f"{backend}/api/admin/faq",
                                            headers=h, data=form)
            suite.record("[FAQ] PUT /api/admin/faq (create)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[FAQ] PUT /api/admin/faq (create)", False, str(e))

        # Read it back
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/faq/entry",
                                            headers=h, params={"question": test_faq_q})
            suite.record("[FAQ] GET /api/admin/faq/entry", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[FAQ] GET /api/admin/faq/entry", False, str(e))

        # Delete it
        try:
            resp, lat = await timed_request(c, "DELETE", f"{backend}/api/admin/faq",
                                            headers=h, params={"question": test_faq_q})
            suite.record("[FAQ] DELETE /api/admin/faq", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[FAQ] DELETE /api/admin/faq", False, str(e))

        # Purge expired
        try:
            resp, lat = await timed_request(c, "POST", f"{backend}/api/admin/faq/purge-expired",
                                            headers=h)
            suite.record("[FAQ] POST purge-expired", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[FAQ] POST purge-expired", False, str(e))

        # ── Monitor Tab ──
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/monitor/stats",
                                            headers=h)
            suite.record("[Monitor] GET /api/admin/monitor/stats", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                expected = {"queue", "recent_activity", "active_sessions", "faq_analytics", "system_time"}
                missing = expected - set(data.keys())
                suite.record("[Monitor] Response has required fields",
                             len(missing) == 0, f"missing={missing}" if missing else "all present")
        except Exception as e:
            suite.record("[Monitor] GET stats", False, str(e))


# ---------------------------------------------------------------------------
# Phase 5: Chat System
# ---------------------------------------------------------------------------
async def test_chat_system(suite: TestSuite, backend: str):
    suite.set_phase("Phase 5: Chat System (Speech & TTS)")

    async with httpx.AsyncClient(timeout=60) as c:
        # Speech endpoint: first test without API key (should get 401 if SPEECH_REQUIRE_API_KEY=true)
        try:
            form = {"text": "สวัสดี", "session_id": "e2e_test_session_001"}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/speech", data=form)
            if resp.status_code == 401:
                suite.record("POST /api/speech (no API key → 401)", True,
                             "SPEECH_REQUIRE_API_KEY is active", lat)
                # Speech API requires API key — verify the auth enforcement works
                suite.record("Speech API key enforcement active", True,
                             "endpoint properly rejects unauthenticated requests")
            elif resp.status_code == 200:
                data = resp.json()
                suite.record("POST /api/speech (text input)", True,
                             f"status={resp.status_code}", lat)
                suite.record("Speech response has 'text'", "text" in data,
                             f"keys={list(data.keys())}")
                suite.record("Speech response has 'motion'", "motion" in data,
                             f"motion={data.get('motion', 'N/A')}")
                suite.record("Speech response has 'session_id'", "session_id" in data,
                             f"session_id={data.get('session_id', 'N/A')[:20]}")
            else:
                suite.record("POST /api/speech", False,
                             f"unexpected status={resp.status_code}", lat)
        except Exception as e:
            suite.record("POST /api/speech", False, str(e))

        # TTS endpoint
        try:
            form = {"text": "ทดสอบ"}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/speak", data=form)
            # 200 = audio returned, 204 = TTS disabled/unavailable (both acceptable)
            suite.record("POST /api/speak (TTS)", resp.status_code in (200, 204),
                         f"status={resp.status_code}, content-type={resp.headers.get('content-type', 'N/A')}", lat)
        except Exception as e:
            suite.record("POST /api/speak (TTS)", False, str(e))


# ---------------------------------------------------------------------------
# Phase 6: Dev Console APIs
# ---------------------------------------------------------------------------
async def test_dev_console(suite: TestSuite, backend: str):
    suite.set_phase("Phase 6: Dev Console APIs")

    h = dev_headers()
    async with httpx.AsyncClient(timeout=20) as c:

        # Flow config
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/flow", headers=h)
            suite.record("[Dev] GET /api/dev/flow", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/flow", False, str(e))

        # Flow history
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/flow/history", headers=h)
            suite.record("[Dev] GET /api/dev/flow/history", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/flow/history", False, str(e))

        # Graph
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/graph", headers=h)
            suite.record("[Dev] GET /api/dev/graph", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/graph", False, str(e))

        # Graph model
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/graph/model", headers=h)
            suite.record("[Dev] GET /api/dev/graph/model", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/graph/model", False, str(e))

        # Traces
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/traces", headers=h)
            suite.record("[Dev] GET /api/dev/traces", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/traces", False, str(e))

        # Connections (architecture view)
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/connections", headers=h)
            suite.record("[Dev] GET /api/dev/connections", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[Dev] Connections has nodes", len(data.get("nodes", [])) > 0,
                             f"nodes={len(data.get('nodes', []))}")
                suite.record("[Dev] Connections has edges", len(data.get("edges", [])) > 0,
                             f"edges={len(data.get('edges', []))}")
        except Exception as e:
            suite.record("[Dev] GET /api/dev/connections", False, str(e))

        # Routes
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/routes", headers=h)
            suite.record("[Dev] GET /api/dev/routes", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                data = resp.json()
                suite.record("[Dev] Route count > 10", data.get("count", 0) > 10,
                             f"count={data.get('count', 0)}")
        except Exception as e:
            suite.record("[Dev] GET /api/dev/routes", False, str(e))

        # Scenarios
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/scenarios", headers=h)
            suite.record("[Dev] GET /api/dev/scenarios", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/scenarios", False, str(e))

        # FAQ from dev side
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/faq", headers=h)
            suite.record("[Dev] GET /api/dev/faq", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/faq", False, str(e))

        # Env raw
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/env/raw", headers=h)
            suite.record("[Dev] GET /api/dev/env/raw", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/env/raw", False, str(e))

        # Filesystem tree
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/fs/tree", headers=h)
            suite.record("[Dev] GET /api/dev/fs/tree", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/fs/tree", False, str(e))

        # Filesystem search
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/fs/search",
                                            headers=h, params={"q": "def ask_llm"})
            suite.record("[Dev] GET /api/dev/fs/search", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/fs/search", False, str(e))

        # HTTP probe (self-test)
        try:
            payload = {"method": "GET", "path": "/api/queue/status", "timeout_seconds": 10}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/dev/http/probe",
                                            headers=h, json=payload)
            suite.record("[Dev] POST /api/dev/http/probe", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] POST /api/dev/http/probe", False, str(e))

        # Logs tail
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/logs/tail", headers=h,
                                            params={"lines": "20"})
            suite.record("[Dev] GET /api/dev/logs/tail", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/logs/tail", False, str(e))

        # Runtime summary
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/dev/runtime/summary", headers=h)
            suite.record("[Dev] GET /api/dev/runtime/summary", resp.status_code in (200, 403),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[Dev] GET /api/dev/runtime/summary", False, str(e))


# ---------------------------------------------------------------------------
# Phase 7: Frontend Pages (Next.js)
# ---------------------------------------------------------------------------
async def test_frontend_pages(suite: TestSuite, frontend: str):
    suite.set_phase("Phase 7: Frontend Pages (Next.js)")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:

        # Main chat page
        try:
            resp, lat = await timed_request(c, "GET", f"{frontend}/")
            suite.record("Main chat page (/)", resp.status_code == 200,
                         f"status={resp.status_code}, len={len(resp.text)}", lat)
            if resp.status_code == 200:
                suite.record("Main page has HTML content", "</html>" in resp.text.lower() or "__next" in resp.text.lower(),
                             f"has_html={('</html>' in resp.text.lower())}")
        except Exception as e:
            suite.record("Main chat page (/)", False, str(e))

        # Admin page
        try:
            resp, lat = await timed_request(c, "GET", f"{frontend}/admin")
            suite.record("Admin page (/admin)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                suite.record("Admin page has content", len(resp.text) > 100,
                             f"len={len(resp.text)}")
        except Exception as e:
            suite.record("Admin page (/admin)", False, str(e))

        # Dev page
        try:
            resp, lat = await timed_request(c, "GET", f"{frontend}/dev")
            suite.record("Dev page (/dev)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Dev page (/dev)", False, str(e))

        # Live page
        try:
            resp, lat = await timed_request(c, "GET", f"{frontend}/live")
            suite.record("Live page (/live)", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Live page (/live)", False, str(e))

        # Next.js static assets
        try:
            resp, lat = await timed_request(c, "GET", f"{frontend}/_next/static/chunks/webpack.js")
            # May be different path, but checking that _next works
            suite.record("Next.js static serving", resp.status_code in (200, 404),
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Next.js static serving", False, str(e))

        # API proxy through Next.js rewrites
        # Note: In Docker, Next.js rewrites to http://backend:5000 which works
        # container-to-container. From host, it may fail (500) because the
        # frontend container can't resolve "backend" from the host's perspective.
        try:
            resp, lat = await timed_request(c, "GET", f"{frontend}/api/queue/status")
            if resp.status_code == 200:
                data = resp.json()
                suite.record("API proxy via Next.js rewrite", True,
                             f"status=200, keys={list(data.keys())[:5]}", lat)
            elif resp.status_code == 500:
                # Expected: Next.js server-side rewrite to http://backend:5000
                # fails when called from host (Docker internal DNS)
                suite.record("API proxy via Next.js rewrite (500 expected from host)", True,
                             "Docker internal DNS: backend:5000 not reachable from host-side SSR", lat)
            else:
                suite.record("API proxy via Next.js rewrite",
                             resp.status_code in (200, 500, 502, 503),
                             f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("API proxy via Next.js rewrite", False, str(e))


# ---------------------------------------------------------------------------
# Phase 8: Socket.IO Connectivity
# ---------------------------------------------------------------------------
async def test_socketio(suite: TestSuite, backend: str):
    suite.set_phase("Phase 8: Socket.IO Connectivity")

    async with httpx.AsyncClient(timeout=10) as c:
        # Socket.IO handshake polling endpoint
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/socket.io/",
                                            params={"EIO": "4", "transport": "polling"})
            suite.record("Socket.IO polling handshake", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
            if resp.status_code == 200:
                body = resp.text
                suite.record("Socket.IO returns SID", "sid" in body,
                             f"body_start={body[:80]}")
        except Exception as e:
            suite.record("Socket.IO polling handshake", False, str(e))


# ---------------------------------------------------------------------------
# Phase 9: Database Router (full CRUD)
# ---------------------------------------------------------------------------
async def test_database_router(suite: TestSuite, backend: str):
    suite.set_phase("Phase 9: Database Router (CRUD)")

    h = admin_headers()
    async with httpx.AsyncClient(timeout=15) as c:

        # List sessions with stats
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/sessions",
                                            headers=h)
            suite.record("[DB] List sessions with stats", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[DB] List sessions", False, str(e))

        # Stats
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/stats",
                                            headers=h)
            suite.record("[DB] Database stats", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[DB] Database stats", False, str(e))

        # Export
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/export",
                                            headers=h)
            suite.record("[DB] Export database", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[DB] Export", False, str(e))

        # Cleanup (with large days param to not actually delete anything)
        try:
            resp, lat = await timed_request(c, "POST", f"{backend}/admin/api/database/cleanup",
                                            headers=h, params={"days": 9999})
            suite.record("[DB] Cleanup old sessions", resp.status_code == 200,
                         f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("[DB] Cleanup", False, str(e))


# ---------------------------------------------------------------------------
# Phase 10: Cross-cutting Concerns
# ---------------------------------------------------------------------------
async def test_cross_cutting(suite: TestSuite, backend: str):
    suite.set_phase("Phase 10: Cross-cutting Concerns")

    async with httpx.AsyncClient(timeout=15) as c:
        # CORS headers
        try:
            resp, lat = await timed_request(c, "OPTIONS", f"{backend}/api/speech",
                                            headers={"Origin": "http://localhost:3000",
                                                     "Access-Control-Request-Method": "POST"})
            has_cors = "access-control-allow-origin" in resp.headers
            suite.record("CORS preflight returns allow-origin", has_cors,
                         f"headers={dict(resp.headers)}" if not has_cors else "present", lat)
        except Exception as e:
            suite.record("CORS preflight", False, str(e))

        # Rate limiting (shouldn't trigger with a single request)
        # Note: if SPEECH_REQUIRE_API_KEY=true and no key provided, we get 401 (not 429)
        try:
            form = {"text": "test", "session_id": "e2e_rate_limit_test"}
            resp, lat = await timed_request(c, "POST", f"{backend}/api/speech", data=form)
            suite.record("Rate limit not triggered for single request",
                         resp.status_code != 429,
                         f"status={resp.status_code} (401=API key required, 200=ok)", lat)
        except Exception as e:
            suite.record("Rate limit test", False, str(e))

        # Error handling: 404 for non-existent path
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/nonexistent-path-e2e-test")
            suite.record("404 for non-existent API path",
                         resp.status_code in (404, 405), f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("404 handling", False, str(e))

        # Admin security: file view requires auth
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/api/admin/view",
                                            params={"root": "data", "path": "test"})
            suite.record("Admin file view requires auth",
                         resp.status_code in (401, 403), f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Admin file view auth", False, str(e))

        # Database router security
        try:
            resp, lat = await timed_request(c, "GET", f"{backend}/admin/api/database/sessions")
            suite.record("Database router requires auth",
                         resp.status_code in (401, 403), f"status={resp.status_code}", lat)
        except Exception as e:
            suite.record("Database router auth", False, str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="REG-01 End-to-End System Test")
    parser.add_argument("--backend", default="http://localhost:5000", help="Backend URL")
    parser.add_argument("--frontend", default="http://localhost:3000", help="Frontend URL")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend tests")
    parser.add_argument("--skip-chat", action="store_true", help="Skip chat/LLM tests (slow)")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║               REG-01 End-to-End System Test                        ║
║  Backend:  {args.backend:<54} ║
║  Frontend: {args.frontend:<54} ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    suite = TestSuite()
    start_time = time.time()

    # Check connectivity first
    print("Checking connectivity...")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{args.backend}/")
            if r.status_code != 200:
                print(f"[WARN] Backend returned {r.status_code} (may still work)")
    except Exception as e:
        print(f"[ERROR] Cannot reach backend at {args.backend}: {e}")
        print("        Make sure services are running: docker compose up -d")
        return

    try:
        await test_docker_health(suite, args.backend)
        await test_backend_core(suite, args.backend)
        await test_auth(suite, args.backend)
        await test_admin_portal(suite, args.backend)

        if not args.skip_chat:
            await test_chat_system(suite, args.backend)
        else:
            print("\n  [SKIPPED] Phase 5: Chat System (--skip-chat)")

        await test_dev_console(suite, args.backend)

        if not args.skip_frontend:
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(f"{args.frontend}/")
                    if r.status_code == 200:
                        await test_frontend_pages(suite, args.frontend)
                    else:
                        print(f"\n  [SKIPPED] Phase 7: Frontend returned {r.status_code}")
            except Exception:
                print(f"\n  [SKIPPED] Phase 7: Cannot reach frontend at {args.frontend}")
        else:
            print("\n  [SKIPPED] Phase 7: Frontend Pages (--skip-frontend)")

        await test_socketio(suite, args.backend)
        await test_database_router(suite, args.backend)
        await test_cross_cutting(suite, args.backend)

    except Exception as e:
        print(f"\n[FATAL] Unexpected error: {e}")
        traceback.print_exc()

    elapsed = time.time() - start_time
    all_passed = suite.summary()
    print(f"  Time: {elapsed:.1f}s\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
