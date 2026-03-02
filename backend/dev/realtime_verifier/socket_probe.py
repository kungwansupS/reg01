import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import socketio


@dataclass
class TurnResult:
    turn_id: str
    fixture_id: str
    status: str
    error: str = ""
    t_eos: float = 0.0
    t_first_audio: float = 0.0
    t_interrupted: float = 0.0
    t_turn_complete: float = 0.0
    server_metrics: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


class RealtimeSocketProbe:
    def __init__(self, backend_url: str, socket_path: str = "socket.io"):
        self.backend_url = backend_url.rstrip("/")
        self.socket_path = socket_path
        self.sio = socketio.AsyncClient(reconnection=False)
        self.session_id = f"rv-{uuid.uuid4().hex[:10]}"
        self._turn: TurnResult | None = None
        self._connected = asyncio.Event()
        self._registered = asyncio.Event()
        self._first_audio = asyncio.Event()
        self._turn_done = asyncio.Event()
        self._interrupted = asyncio.Event()
        self._bind_handlers()

    def _bind_handlers(self) -> None:
        @self.sio.event
        async def connect():
            self._connected.set()
            await self.sio.emit("client_register_session", {"session_id": self.session_id})

        @self.sio.on("session_registered")
        async def _on_registered(data):
            if isinstance(data, dict) and str(data.get("session_id")) == self.session_id:
                self._registered.set()

        @self.sio.on("live_audio_out")
        async def _on_live_audio_out(_data):
            now = time.perf_counter()
            if self._turn:
                if self._turn.t_first_audio == 0:
                    self._turn.t_first_audio = now
                    self._first_audio.set()
                self._turn.events.append({"event": "live_audio_out", "ts": now})

        @self.sio.on("live_turn_complete")
        async def _on_live_turn_complete(data):
            now = time.perf_counter()
            if self._turn:
                self._turn.t_turn_complete = now
                if isinstance(data, dict):
                    if data.get("turn_id"):
                        self._turn.turn_id = str(data["turn_id"])
                    if isinstance(data.get("metrics"), dict):
                        self._turn.server_metrics = data["metrics"]
                self._turn.events.append({"event": "live_turn_complete", "ts": now})
                self._turn_done.set()

        @self.sio.on("live_interrupted")
        async def _on_live_interrupted(data):
            now = time.perf_counter()
            if self._turn:
                self._turn.t_interrupted = now
                self._turn.events.append({"event": "live_interrupted", "ts": now, "data": data})
                self._interrupted.set()

        @self.sio.on("live_error")
        async def _on_live_error(data):
            now = time.perf_counter()
            if self._turn:
                self._turn.status = "error"
                self._turn.error = str((data or {}).get("message") or "live_error")
                self._turn.events.append({"event": "live_error", "ts": now, "data": data})
                self._turn_done.set()

    async def connect(self) -> None:
        await self.sio.connect(self.backend_url, socketio_path=self.socket_path)
        await asyncio.wait_for(self._connected.wait(), timeout=5)
        await asyncio.wait_for(self._registered.wait(), timeout=5)

    async def disconnect(self) -> None:
        if self.sio.connected:
            await self.sio.disconnect()

    async def run_turn(self, fixture_id: str, chunks_b64: list[str], timeout_s: float, inter_chunk_sleep_s: float) -> TurnResult:
        self._first_audio.clear()
        self._turn_done.clear()
        self._interrupted.clear()
        self._turn = TurnResult(turn_id="", fixture_id=fixture_id, status="ok")

        await self.sio.emit("live_start", {"session_id": self.session_id})
        for chunk in chunks_b64:
            await self.sio.emit("live_audio_in", {"session_id": self.session_id, "audio": chunk})
            if inter_chunk_sleep_s > 0:
                await asyncio.sleep(inter_chunk_sleep_s)

        self._turn.t_eos = time.perf_counter()
        await self.sio.emit("live_stop", {"session_id": self.session_id})

        try:
            await asyncio.wait_for(self._turn_done.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            self._turn.status = "timeout"
            self._turn.error = "turn_timeout"

        return self._turn

    async def run_barge_in(self, fixture_id: str, first_chunks: list[str], interrupt_chunk: str, timeout_s: float, inter_chunk_sleep_s: float) -> TurnResult:
        self._first_audio.clear()
        self._turn_done.clear()
        self._interrupted.clear()
        self._turn = TurnResult(turn_id="", fixture_id=fixture_id, status="ok")

        await self.sio.emit("live_start", {"session_id": self.session_id})
        for chunk in first_chunks:
            await self.sio.emit("live_audio_in", {"session_id": self.session_id, "audio": chunk})
            if inter_chunk_sleep_s > 0:
                await asyncio.sleep(inter_chunk_sleep_s)

        self._turn.t_eos = time.perf_counter()
        await self.sio.emit("live_stop", {"session_id": self.session_id})

        await asyncio.wait_for(self._first_audio.wait(), timeout=timeout_s)
        t_barge = time.perf_counter()
        self._turn.events.append({"event": "barge_in_sent", "ts": t_barge})
        await self.sio.emit("live_audio_in", {"session_id": self.session_id, "audio": interrupt_chunk})

        try:
            await asyncio.wait_for(self._interrupted.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            self._turn.status = "timeout"
            self._turn.error = "barge_in_timeout"

        return self._turn
