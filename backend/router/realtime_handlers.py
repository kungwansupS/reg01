"""
Realtime voice handlers (Phase 1, local-first).

Implements:
- live_start
- live_audio_in
- live_stop
- live_client_metric

Primary path avoids external realtime APIs. Audio output is generated locally
as PCM16 chunks so frontend live page can play immediately.
"""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import struct
import tempfile
import time
import uuid
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from app.stt import transcribe
from app.stt_stream import StreamingSTTSession
from app.utils.llm.llm import ask_llm


ResolveSessionFn = Callable[[str, dict | None], str]
EmitToSessionFn = Callable[[str, dict, str], Awaitable[None]]


@dataclass
class RealtimeSession:
    session_id: str
    audio_buffer: bytearray = field(default_factory=bytearray)
    speaking: bool = False
    turn_task: asyncio.Task | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    turn_id: str = ""
    eos_ts: float = 0.0
    last_audio_in_ts: float = 0.0
    interruption_started_ts: float = 0.0
    chunk_window_started_ts: float = 0.0
    chunk_count_in_window: int = 0
    stt_stream: StreamingSTTSession = field(default_factory=StreamingSTTSession)


_resolve_session_id: ResolveSessionFn | None = None
_emit_to_session: EmitToSessionFn | None = None
_sessions: dict[str, RealtimeSession] = {}

_ROOT_DIR = Path(__file__).resolve().parents[2]
_REALTIME_EVAL_DIR = _ROOT_DIR / "team-space" / "eval" / "realtime"
_REALTIME_LOG_PATH = _REALTIME_EVAL_DIR / "realtime_metrics.jsonl"
_REALTIME_LLM_TIMEOUT_MS = max(100, int(os.getenv("REALTIME_LLM_TIMEOUT_MS", "600")))
_REALTIME_MAX_CHUNKS_PER_SEC = max(20, int(os.getenv("REALTIME_MAX_CHUNKS_PER_SEC", "80")))
_REALTIME_MAX_BUFFER_BYTES = max(8192, int(os.getenv("REALTIME_MAX_BUFFER_BYTES", str(3 * 1024 * 1024))))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_realtime_log(entry: dict) -> None:
    _REALTIME_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with _REALTIME_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _get_or_create_session(session_id: str) -> RealtimeSession:
    ses = _sessions.get(session_id)
    if ses is None:
        ses = RealtimeSession(session_id=session_id)
        _sessions[session_id] = ses
    return ses


async def _emit(event: str, payload: dict, session_id: str) -> None:
    if _emit_to_session:
        await _emit_to_session(event, payload, session_id)


def _decode_pcm_base64(audio_b64: str) -> bytes:
    try:
        return base64.b64decode(audio_b64)
    except Exception:
        return b""


def _pcm_chunk_to_base64(chunk: bytes) -> str:
    return base64.b64encode(chunk).decode("ascii")


def _synthesize_local_pcm(text: str, sample_rate: int = 24000) -> bytes:
    """Generate simple local PCM16 mono tone as fallback audio."""
    text = str(text or "").strip()
    if not text:
        return b""

    duration_sec = max(0.8, min(6.0, len(text) * 0.03))
    n_samples = int(duration_sec * sample_rate)
    amp = 0.18
    freq = 220.0 + (len(text) % 6) * 30.0

    out = bytearray()
    attack = int(0.05 * sample_rate)
    release = int(0.08 * sample_rate)
    for i in range(n_samples):
        envelope = 1.0
        if i < attack:
            envelope = i / max(1, attack)
        elif i > n_samples - release:
            envelope = max(0.0, (n_samples - i) / max(1, release))
        s = math.sin(2.0 * math.pi * freq * (i / sample_rate))
        value = int(max(-32767, min(32767, s * amp * envelope * 32767)))
        out.extend(struct.pack("<h", value))
    return bytes(out)


def _write_pcm16_wav(tmp_path: str, pcm: bytes, sample_rate: int = 16000) -> None:
    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


async def _process_turn(session_id: str) -> None:
    ses = _get_or_create_session(session_id)
    async with ses.lock:
        raw_pcm = bytes(ses.audio_buffer)
        ses.audio_buffer.clear()

    if not raw_pcm:
        await _emit("live_error", {"message": "No audio received"}, session_id)
        return

    turn_id = ses.turn_id or f"{session_id}-{uuid.uuid4().hex[:8]}"
    t_turn_start = time.perf_counter()
    metrics = {
        "turn_id": turn_id,
        "session_id": session_id,
        "turn_start_ts": t_turn_start,
        "eos_ts": ses.eos_ts or ses.last_audio_in_ts,
        "stt_start_ts": 0.0,
        "stt_end_ts": 0.0,
        "llm_start_ts": 0.0,
        "llm_end_ts": 0.0,
        "tts_start_ts": 0.0,
        "first_audio_out_ts": 0.0,
        "turn_complete_ts": 0.0,
        "error": "",
    }

    try:
        user_text = ""
        metrics["stt_start_ts"] = time.perf_counter()
        user_text = await ses.stt_stream.flush_and_transcribe()
        metrics["stt_end_ts"] = time.perf_counter()
        if not user_text:
            tmp_path = ""
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                await asyncio.to_thread(_write_pcm16_wav, tmp_path, raw_pcm, 16000)
                user_text = await asyncio.to_thread(transcribe, tmp_path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        if not user_text or user_text.startswith("❌") or user_text.startswith("⚠"):
            metrics["error"] = user_text or "STT failed"
            await _emit("live_error", {"message": metrics["error"]}, session_id)
            return

        await _emit("live_text", {"text": user_text}, session_id)

        metrics["llm_start_ts"] = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                ask_llm(user_text, session_id, runtime_profile="realtime", trace_source="realtime"),
                timeout=_REALTIME_LLM_TIMEOUT_MS / 1000.0,
            )
            metrics["llm_end_ts"] = time.perf_counter()
            ai_text = str(result.get("text") or "").strip()
        except asyncio.TimeoutError:
            metrics["llm_end_ts"] = time.perf_counter()
            metrics["error"] = "llm_timeout"
            ai_text = "ขออภัย ตอนนี้ระบบตอบสนองช้า กรุณาถามสั้นลงอีกครั้งครับ"

        if not ai_text:
            metrics["error"] = "empty_ai_response"
            ai_text = "ขออภัย ไม่สามารถประมวลผลคำตอบได้ในขณะนี้"

        await _emit("live_speaking", {"speaking": True}, session_id)
        ses.speaking = True

        pcm = _synthesize_local_pcm(ai_text, 24000)
        chunk_size = 4096
        metrics["tts_start_ts"] = time.perf_counter()

        sent_first_chunk = False
        for i in range(0, len(pcm), chunk_size):
            chunk = pcm[i : i + chunk_size]
            if not sent_first_chunk:
                metrics["first_audio_out_ts"] = time.perf_counter()
                sent_first_chunk = True
                eos_ref = metrics["eos_ts"]
                eos_to_first = (metrics["first_audio_out_ts"] - eos_ref) * 1000 if eos_ref else None
                await _emit(
                    "live_metrics",
                    {
                        "turn_id": turn_id,
                        "metric": "eos_to_first_audio_ms",
                        "value": eos_to_first,
                        "source": "server",
                    },
                    session_id,
                )

            await _emit("live_audio_out", {"audio": _pcm_chunk_to_base64(chunk)}, session_id)
            await asyncio.sleep(0)

        await _emit("live_text", {"text": ai_text}, session_id)
        await _emit("live_speaking", {"speaking": False}, session_id)

        metrics["turn_complete_ts"] = time.perf_counter()
        eos_ref = metrics["eos_ts"]
        metrics["eos_to_first_audio_ms"] = (
            round((metrics["first_audio_out_ts"] - eos_ref) * 1000, 2)
            if eos_ref and metrics["first_audio_out_ts"]
            else None
        )
        metrics["stt_ms"] = round((metrics["stt_end_ts"] - metrics["stt_start_ts"]) * 1000, 2) if metrics["stt_end_ts"] else None
        metrics["llm_ms"] = round((metrics["llm_end_ts"] - metrics["llm_start_ts"]) * 1000, 2) if metrics["llm_end_ts"] else None
        metrics["turn_total_ms"] = round((metrics["turn_complete_ts"] - t_turn_start) * 1000, 2)

        await _emit("live_turn_complete", {"turn_id": turn_id, "metrics": metrics}, session_id)
        ses.speaking = False
    except asyncio.CancelledError:
        ses.speaking = False
        metrics["error"] = "cancelled"
        metrics["turn_complete_ts"] = time.perf_counter()
        await _emit("live_speaking", {"speaking": False}, session_id)
        raise
    finally:
        _append_realtime_log({"timestamp": _iso_now(), "kind": "server_turn", **metrics})


async def handle_live_start(sid: str, data: dict | None = None):
    if not _resolve_session_id:
        return
    session_id = _resolve_session_id(sid, data)
    if not session_id:
        return

    ses = _get_or_create_session(session_id)
    async with ses.lock:
        ses.audio_buffer.clear()
    ses.turn_id = ""
    ses.eos_ts = 0.0
    ses.last_audio_in_ts = 0.0
    ses.interruption_started_ts = 0.0

    await _emit("live_speaking", {"speaking": False}, session_id)


async def handle_live_audio_in(sid: str, data: dict | None = None):
    if not _resolve_session_id or not isinstance(data, dict):
        return
    session_id = _resolve_session_id(sid, data)
    if not session_id:
        return

    audio_b64 = str(data.get("audio") or "")
    pcm = _decode_pcm_base64(audio_b64)
    if not pcm:
        return

    ses = _get_or_create_session(session_id)
    ses.last_audio_in_ts = time.perf_counter()
    now = ses.last_audio_in_ts
    if ses.chunk_window_started_ts == 0.0 or (now - ses.chunk_window_started_ts) >= 1.0:
        ses.chunk_window_started_ts = now
        ses.chunk_count_in_window = 0
    ses.chunk_count_in_window += 1
    if ses.chunk_count_in_window > _REALTIME_MAX_CHUNKS_PER_SEC:
        await _emit("live_error", {"message": "Rate limit: too many audio chunks"}, session_id)
        return

    if ses.turn_task and not ses.turn_task.done():
        ses.interruption_started_ts = time.perf_counter()
        ses.turn_task.cancel()
        ses.speaking = False
        interrupted_ts = time.perf_counter()
        reaction_ms = round((interrupted_ts - ses.interruption_started_ts) * 1000, 2)
        await _emit(
            "live_interrupted",
            {
                "reason": "barge_in",
                "turn_id": ses.turn_id,
                "metrics": {"interruption_reaction_ms": reaction_ms},
            },
            session_id,
        )
        await _emit("live_metrics", {"turn_id": ses.turn_id, "metric": "interruption_reaction_ms", "value": reaction_ms, "source": "server"}, session_id)
        await _emit("live_speaking", {"speaking": False}, session_id)

        _append_realtime_log(
            {
                "timestamp": _iso_now(),
                "kind": "server_interrupt",
                "session_id": session_id,
                "turn_id": ses.turn_id,
                "interruption_reaction_ms": reaction_ms,
            }
        )

    async with ses.lock:
        if len(ses.audio_buffer) + len(pcm) > _REALTIME_MAX_BUFFER_BYTES:
            await _emit("live_error", {"message": "Audio buffer limit exceeded"}, session_id)
            ses.audio_buffer.clear()
            return
        ses.audio_buffer.extend(pcm)
    await ses.stt_stream.feed_pcm16(pcm)


async def handle_live_stop(sid: str, data: dict | None = None):
    if not _resolve_session_id:
        return
    session_id = _resolve_session_id(sid, data if isinstance(data, dict) else None)
    if not session_id:
        return

    ses = _get_or_create_session(session_id)
    ses.turn_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
    ses.eos_ts = time.perf_counter()

    if ses.turn_task and not ses.turn_task.done():
        ses.turn_task.cancel()
    ses.turn_task = asyncio.create_task(_process_turn(session_id))


async def handle_live_client_metric(sid: str, data: dict | None = None):
    if not _resolve_session_id or not isinstance(data, dict):
        return
    session_id = _resolve_session_id(sid, data)
    if not session_id:
        return

    payload = {
        "timestamp": _iso_now(),
        "kind": "client_metric",
        "session_id": session_id,
        "turn_id": str(data.get("turn_id") or ""),
        "metric": str(data.get("metric") or ""),
        "value": data.get("value"),
        "client_ts_ms": data.get("client_ts_ms"),
        "meta": data.get("meta") if isinstance(data.get("meta"), dict) else {},
    }
    _append_realtime_log(payload)


def init_realtime_handlers(
    socketio_instance,
    resolve_session_id_fn: ResolveSessionFn,
    emit_to_session_fn: EmitToSessionFn,
):
    global _resolve_session_id, _emit_to_session
    _resolve_session_id = resolve_session_id_fn
    _emit_to_session = emit_to_session_fn

    socketio_instance.on("live_start")(handle_live_start)
    socketio_instance.on("live_audio_in")(handle_live_audio_in)
    socketio_instance.on("live_stop")(handle_live_stop)
    socketio_instance.on("live_client_metric")(handle_live_client_metric)
