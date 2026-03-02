from dataclasses import dataclass
from typing import Any


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


@dataclass
class RunMetrics:
    total_turns: int
    error_turns: int
    turn_error_rate: float
    eos_to_first_audio_ms: list[float]
    interruption_reaction_ms: list[float]
    eos_p95_ms: float | None
    interrupt_p90_ms: float | None


def aggregate(turns: list[dict[str, Any]]) -> RunMetrics:
    eos_vals: list[float] = []
    interrupt_vals: list[float] = []
    errors = 0

    for t in turns:
        status = str(t.get("status") or "")
        if status != "ok":
            errors += 1

        eos = t.get("end_of_speech_to_first_audio_ms")
        # EOS->first-audio KPI excludes dedicated barge-in scenarios.
        is_barge_case = str(t.get("fixture_id") or "").endswith("-barge")
        if isinstance(eos, (int, float)) and not is_barge_case:
            eos_vals.append(float(eos))

        irr = t.get("interruption_reaction_ms")
        if isinstance(irr, (int, float)):
            interrupt_vals.append(float(irr))

    total = len(turns)
    return RunMetrics(
        total_turns=total,
        error_turns=errors,
        turn_error_rate=(errors / total) if total else 0.0,
        eos_to_first_audio_ms=eos_vals,
        interruption_reaction_ms=interrupt_vals,
        eos_p95_ms=_percentile(eos_vals, 0.95),
        interrupt_p90_ms=_percentile(interrupt_vals, 0.90),
    )
