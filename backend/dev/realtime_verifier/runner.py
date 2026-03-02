import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

if __package__ in (None, ""):
    # Support direct execution: `python backend/dev/realtime_verifier/runner.py`
    _backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)
    from dev.realtime_verifier.audio_fixtures import default_fixtures
    from dev.realtime_verifier.config import DEFAULT_CONFIG, VerifierConfig
    from dev.realtime_verifier.latency_collector import aggregate
    from dev.realtime_verifier.report_generator import write_reports
    from dev.realtime_verifier.socket_probe import RealtimeSocketProbe
else:
    from .audio_fixtures import default_fixtures
    from .config import DEFAULT_CONFIG, VerifierConfig
    from .latency_collector import aggregate
    from .report_generator import write_reports
    from .socket_probe import RealtimeSocketProbe


def _mk_run_id(prefix: str = "realtime_run") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _turn_to_record(turn) -> dict:
    eos_to_first = None
    if turn.t_eos and turn.t_first_audio:
        eos_to_first = round((turn.t_first_audio - turn.t_eos) * 1000, 2)

    interruption_reaction = None
    barge_sent = None
    for ev in turn.events:
        if ev.get("event") == "barge_in_sent":
            barge_sent = ev.get("ts")
            break
    if barge_sent and turn.t_interrupted:
        interruption_reaction = round((turn.t_interrupted - barge_sent) * 1000, 2)

    return {
        "turn_id": turn.turn_id,
        "fixture_id": turn.fixture_id,
        "status": turn.status,
        "error": turn.error,
        "end_of_speech_to_first_audio_ms": eos_to_first,
        "interruption_reaction_ms": interruption_reaction,
        "server_metrics": turn.server_metrics,
    }


async def run_once(cfg: VerifierConfig, turns: int, include_barge_in: bool, run_id: str) -> tuple[dict, list[dict]]:
    probe = RealtimeSocketProbe(cfg.backend_url, cfg.socket_path)
    fixtures = default_fixtures()

    results: list[dict] = []
    await probe.connect()
    try:
        for i in range(turns):
            fx = fixtures[i % len(fixtures)]
            tr = await probe.run_turn(
                fixture_id=fx.fixture_id,
                chunks_b64=fx.chunks_b64,
                timeout_s=cfg.turn_timeout_s,
                inter_chunk_sleep_s=cfg.inter_chunk_sleep_s,
            )
            results.append(_turn_to_record(tr))

        if include_barge_in:
            fx = fixtures[0]
            interrupt_chunk = fx.chunks_b64[0] if fx.chunks_b64 else ""
            tr = await probe.run_barge_in(
                fixture_id=f"{fx.fixture_id}-barge",
                first_chunks=fx.chunks_b64,
                interrupt_chunk=interrupt_chunk,
                timeout_s=cfg.turn_timeout_s,
                inter_chunk_sleep_s=cfg.inter_chunk_sleep_s,
            )
            results.append(_turn_to_record(tr))
    finally:
        await probe.disconnect()

    agg = aggregate(results)
    summary = {
        "run_id": run_id,
        "total_turns": agg.total_turns,
        "error_turns": agg.error_turns,
        "turn_error_rate": round(agg.turn_error_rate, 4),
        "eos_p95_ms": None if agg.eos_p95_ms is None else round(agg.eos_p95_ms, 2),
        "interrupt_p90_ms": None if agg.interrupt_p90_ms is None else round(agg.interrupt_p90_ms, 2),
        "targets": {
            "eos_to_first_audio_p95_ms": cfg.eos_to_first_audio_p95_ms,
            "interruption_reaction_p90_ms": cfg.interruption_reaction_p90_ms,
            "turn_error_rate_max": cfg.turn_error_rate_max,
        },
        "pass": {
            "eos_to_first_audio": agg.eos_p95_ms is not None and agg.eos_p95_ms <= cfg.eos_to_first_audio_p95_ms,
            "interruption_reaction": agg.interrupt_p90_ms is None or agg.interrupt_p90_ms <= cfg.interruption_reaction_p90_ms,
            "turn_error_rate": agg.turn_error_rate <= cfg.turn_error_rate_max,
        },
    }
    return summary, results


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Realtime verifier runner")
    p.add_argument("--backend", default=DEFAULT_CONFIG.backend_url)
    p.add_argument("--turns", type=int, default=5)
    p.add_argument("--include-barge-in", action="store_true")
    p.add_argument("--run-id", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or _mk_run_id()
    cfg = VerifierConfig(backend_url=args.backend)

    started = time.perf_counter()
    summary, turns = asyncio.run(run_once(cfg, args.turns, args.include_barge_in, run_id))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    summary["elapsed_ms"] = elapsed_ms

    json_path, md_path = write_reports(cfg.report_dir, run_id, summary, turns)
    print(f"[realtime-verifier] run_id={run_id}")
    print(f"[realtime-verifier] json={json_path}")
    print(f"[realtime-verifier] md={md_path}")
    print(f"[realtime-verifier] summary={summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
