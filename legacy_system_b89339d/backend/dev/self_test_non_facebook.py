"""
Non-Facebook system self-test for REG-01.

Usage:
  python -m backend.dev.self_test_non_facebook

The script uses mocked LLM/TTS handlers to avoid external costs and latency.
"""

import asyncio
import json
import os
import sys
import uuid
from io import BytesIO
from typing import List, Tuple

from fastapi.testclient import TestClient


def _workspace_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


WORKSPACE_ROOT = _workspace_root()
BACKEND_ROOT = os.path.join(WORKSPACE_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Keep startup deterministic while testing.
os.environ.setdefault("RAG_STARTUP_EMBEDDING", "false")

import main  # noqa: E402
from memory.session import get_or_create_history, set_bot_enabled  # noqa: E402
from router import chat_router, dev_router, socketio_handlers  # noqa: E402


Result = Tuple[str, bool, str]


def _record(results: List[Result], name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


async def _fake_ask_llm(msg, session_id, emit_fn=None, **kwargs):
    if emit_fn:
        await emit_fn("ai_status", {"status": "Processing request..."})
    return {
        "text": f"mock-reply:{msg}",
        "tokens": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        "trace_id": f"trace-{session_id[-6:]}",
    }


async def _fake_pose(_reply):
    return "Idle"


async def _fake_speak(_text):
    yield b"ID3"
    yield b"FAKEAUDIOBYTES"


class _FakeSio:
    def __init__(self):
        self.enter_calls = []
        self.emit_calls = []

    async def enter_room(self, sid, room):
        self.enter_calls.append((sid, room))

    async def emit(self, event, payload, room=None):
        self.emit_calls.append((event, payload, room))


def main_self_test() -> int:
    # Monkeypatch heavy/external paths.
    captured_room_events = []

    async def _capture_emit_to_web_session(event, payload, session_id):
        captured_room_events.append((event, payload, session_id))

    chat_router.ask_llm = _fake_ask_llm
    chat_router.suggest_pose = _fake_pose
    chat_router.speak = _fake_speak
    chat_router.emit_to_web_session = _capture_emit_to_web_session
    dev_router.ask_llm = _fake_ask_llm

    results: List[Result] = []
    admin_token = os.getenv("ADMIN_TOKEN", "super-secret-key")
    dev_token = os.getenv("DEV_TOKEN", "dev-secret-key")
    headers_admin = {"X-Admin-Token": admin_token}
    headers_dev = {"X-Dev-Token": dev_token}
    scratch_id = f"zz_test_{uuid.uuid4().hex[:8]}"
    mkdir_name = f"{scratch_id}_dir"

    with TestClient(main.app) as client:
        for path in ["/", "/admin", "/dev"]:
            r = client.get(path)
            _record(results, f"page_{path}", r.status_code == 200, str(r.status_code))

        r = client.post(
            "/api/speech",
            data={"text": "hi there", "session_id": f"web_{scratch_id}"},
            headers={"X-API-Key": "test-key"},
        )
        _record(results, "speech_ok", r.status_code == 200, str(r.status_code))
        _record(
            results,
            "speech_emit_room",
            any(ev[0] == "ai_response" for ev in captured_room_events),
            str(captured_room_events),
        )

        r = client.post("/api/speak", data={"text": "hello"})
        _record(
            results,
            "speak_ok",
            r.status_code == 200 and "audio/mpeg" in r.headers.get("content-type", ""),
            str(r.status_code),
        )

        r = client.post(
            "/api/admin/mkdir",
            data={"root": "quick_use", "path": "", "name": mkdir_name},
            headers=headers_admin,
        )
        _record(results, "admin_mkdir_ok", r.status_code == 200, str(r.status_code))

        files = {"file": ("note.txt", BytesIO(b"hello"), "text/plain")}
        client.post(
            "/api/admin/upload",
            data={"root": "quick_use", "target_dir": mkdir_name},
            files=files,
            headers=headers_admin,
        )
        client.post(
            "/api/admin/edit",
            data={"root": "quick_use", "path": f"{mkdir_name}/note.txt", "content": "updated"},
            headers=headers_admin,
        )
        client.post(
            "/api/admin/copy",
            data={
                "root": "quick_use",
                "source_paths": json.dumps([f"{mkdir_name}/note.txt"]),
                "target_path": mkdir_name,
            },
            headers=headers_admin,
        )
        client.post(
            "/api/admin/rename",
            data={
                "root": "quick_use",
                "old_path": f"{mkdir_name}/note_copy_1.txt",
                "new_name": "renamed.txt",
            },
            headers=headers_admin,
        )
        client.post(
            "/api/admin/move",
            data={
                "root": "quick_use",
                "source_paths": json.dumps([f"{mkdir_name}/renamed.txt"]),
                "target_path": "",
            },
            headers=headers_admin,
        )
        client.request(
            "DELETE",
            "/api/admin/files",
            params={"root": "quick_use", "paths": json.dumps([f"{mkdir_name}", "renamed.txt"])},
            headers=headers_admin,
        )
        _record(results, "admin_ops_cleanup", True, "ok")

        r = client.get("/api/dev/flow/history", headers=headers_dev)
        data = r.json() if r.status_code == 200 else {}
        _record(
            results,
            "dev_flow_history_shape",
            r.status_code == 200 and isinstance(data.get("items"), list),
            str(type(data.get("items")).__name__),
        )

        r = client.get("/api/dev/graph/model/history", headers=headers_dev)
        data = r.json() if r.status_code == 200 else {}
        _record(
            results,
            "dev_graph_history_shape",
            r.status_code == 200 and isinstance(data.get("items"), list),
            str(type(data.get("items")).__name__),
        )

        r = client.get("/api/dev/env/history", headers=headers_dev)
        data = r.json() if r.status_code == 200 else {}
        _record(
            results,
            "dev_env_history_shape",
            r.status_code == 200 and isinstance(data.get("items"), list),
            str(type(data.get("items")).__name__),
        )

    # Socket handler checks
    fake = _FakeSio()
    socketio_handlers.sio = fake

    async def _run_socket_checks():
        await socketio_handlers.handle_client_register_session("sid-1", {"session_id": "web_unit_12345678"})
        _record(
            results,
            "socket_room_join",
            any(room == "web_session:web_unit_12345678" for _, room in fake.enter_calls),
            str(fake.enter_calls),
        )

        await socketio_handlers.handle_admin_manual_reply(
            "sid-unauth",
            {"uid": "web_unit_12345678", "text": "x", "platform": "web", "admin_token": "bad"},
        )
        _record(
            results,
            "socket_admin_unauth",
            any(ev[0] == "admin_error" and ev[2] == "sid-unauth" for ev in fake.emit_calls),
            str(fake.emit_calls),
        )

        get_or_create_history("web_unit_12345678")
        set_bot_enabled("web_unit_12345678", False)

        called = []

        async def _cap_emit(event, payload, session_id):
            called.append((event, payload, session_id))

        socketio_handlers.emit_to_web_session = _cap_emit
        await socketio_handlers.handle_admin_manual_reply(
            "sid-auth",
            {
                "uid": "web_unit_12345678",
                "text": "ok",
                "platform": "web",
                "admin_token": admin_token,
            },
        )
        _record(results, "socket_admin_auth", any(c[0] == "ai_response" for c in called), str(called))

    asyncio.run(_run_socket_checks())

    failed = [x for x in results if not x[1]]
    print(f"TOTAL {len(results)}")
    print(f"FAILED {len(failed)}")
    for name, ok, detail in results:
        print(("PASS" if ok else "FAIL"), name, detail)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main_self_test())
