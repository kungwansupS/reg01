import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_reports(report_dir: str, run_id: str, run_summary: dict[str, Any], turns: list[dict[str, Any]]) -> tuple[str, str]:
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{run_id}.json"
    md_path = out_dir / f"{run_id}.md"

    payload = {
        "run_id": run_id,
        "timestamp": _iso_now(),
        "summary": run_summary,
        "turns": turns,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append(f"# Realtime Verifier Report: {run_id}")
    lines.append("")
    lines.append(f"- Timestamp: {payload['timestamp']}")
    lines.append(f"- Total turns: {run_summary.get('total_turns', 0)}")
    lines.append(f"- Error turns: {run_summary.get('error_turns', 0)}")
    lines.append(f"- Turn error rate: {run_summary.get('turn_error_rate', 0):.4f}")
    lines.append(f"- EOS->FirstAudio P95 (ms): {run_summary.get('eos_p95_ms')}")
    lines.append(f"- Interruption P90 (ms): {run_summary.get('interrupt_p90_ms')}")
    lines.append("")
    lines.append("## Turn Results")
    lines.append("")
    lines.append("| turn_id | fixture | status | eos_to_first_audio_ms | interruption_reaction_ms | error |")
    lines.append("|---|---|---|---:|---:|---|")
    for t in turns:
        lines.append(
            f"| {t.get('turn_id','')} | {t.get('fixture_id','')} | {t.get('status','')} | "
            f"{t.get('end_of_speech_to_first_audio_ms','')} | {t.get('interruption_reaction_ms','')} | {t.get('error','')} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(json_path), str(md_path)
