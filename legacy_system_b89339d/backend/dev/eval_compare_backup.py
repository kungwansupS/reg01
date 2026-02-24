"""
Compare answer accuracy between current system and backup system via /api/speech.

Usage:
  python -m backend.dev.eval_compare_backup
  python -m backend.dev.eval_compare_backup --current-url http://127.0.0.1:5000 --backup-url http://127.0.0.1:5001
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

import requests

from backend.dev.eval_multi_mode import _build_cases


def _clean_output(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^\[Bot[^\]]*\]\s*", "", value, flags=re.IGNORECASE)
    value = value.replace("//", "").strip()
    return value


def _p50(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    return float(sorted_vals[max(0, int(len(sorted_vals) * 0.5) - 1)])


def _p90(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    return float(sorted_vals[max(0, int(len(sorted_vals) * 0.9) - 1)])


def _run_one_system(
    *,
    label: str,
    base_url: str,
    api_key: str,
    timeout_seconds: int,
    pause_seconds: float,
) -> Dict[str, Any]:
    cases = _build_cases()
    rows: List[Dict[str, Any]] = []
    latencies: List[float] = []
    pass_count = 0
    http_ok_count = 0

    endpoint = f"{base_url.rstrip('/')}/api/speech"
    headers = {}
    if str(api_key or "").strip():
        headers["X-API-Key"] = str(api_key).strip()

    for case in cases:
        payload = {
            "text": case.message,
            "session_id": f"cmp_{label}_{case.case_id}_{uuid.uuid4().hex[:8]}",
        }
        row: Dict[str, Any] = {
            "id": case.case_id,
            "category": case.category,
            "message": case.message,
            "expected": case.expected,
            "http_ok": False,
            "status_code": None,
            "ok": False,
            "latency_seconds": None,
            "output": "",
            "error": "",
        }
        started = time.perf_counter()
        try:
            resp = requests.post(endpoint, data=payload, headers=headers, timeout=timeout_seconds)
            latency = round(time.perf_counter() - started, 3)
            row["latency_seconds"] = latency
            row["status_code"] = int(resp.status_code)
            row["http_ok"] = bool(200 <= int(resp.status_code) < 300)
            if row["http_ok"]:
                http_ok_count += 1
                data = resp.json() if "application/json" in str(resp.headers.get("content-type", "")) else {}
                output = _clean_output(str((data or {}).get("text") or ""))
                row["output"] = output
                row["ok"] = bool(case.validator(output))
                if row["ok"]:
                    pass_count += 1
            else:
                row["error"] = str(resp.text)[:500]
        except Exception as exc:  # noqa: BLE001
            row["latency_seconds"] = round(time.perf_counter() - started, 3)
            row["error"] = str(exc)
        rows.append(row)
        if isinstance(row.get("latency_seconds"), (int, float)):
            latencies.append(float(row["latency_seconds"]))
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    total_cases = len(cases)
    accuracy = (pass_count / total_cases * 100.0) if total_cases else 0.0
    summary = {
        "label": label,
        "base_url": base_url,
        "cases_total": total_cases,
        "http_ok": http_ok_count,
        "accuracy_pass": pass_count,
        "accuracy_rate": round(accuracy, 2),
        "latency_seconds": {
            "avg": round(float(statistics.mean(latencies)), 3) if latencies else 0.0,
            "p50": round(_p50(latencies), 3) if latencies else 0.0,
            "p90": round(_p90(latencies), 3) if latencies else 0.0,
            "max": round(float(max(latencies)), 3) if latencies else 0.0,
        },
    }
    return {"summary": summary, "rows": rows}


def run_compare(
    *,
    current_url: str,
    backup_url: str,
    api_key: str,
    timeout_seconds: int,
    pause_seconds: float,
) -> Dict[str, Any]:
    current = _run_one_system(
        label="current",
        base_url=current_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        pause_seconds=pause_seconds,
    )
    backup = _run_one_system(
        label="backup",
        base_url=backup_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        pause_seconds=pause_seconds,
    )
    cur_acc = float(current["summary"]["accuracy_rate"])
    bak_acc = float(backup["summary"]["accuracy_rate"])
    if cur_acc > bak_acc:
        winner = "current"
    elif bak_acc > cur_acc:
        winner = "backup"
    else:
        winner = "tie"

    return {
        "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "winner": winner,
        "delta_accuracy_pct": round(cur_acc - bak_acc, 2),
        "current": current,
        "backup": backup,
        "cases": [
            {
                "case_id": c.case_id,
                "category": c.category,
                "message": c.message,
                "expected": c.expected,
            }
            for c in _build_cases()
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-url", default="http://127.0.0.1:5000")
    parser.add_argument("--backup-url", default="http://127.0.0.1:5001")
    parser.add_argument("--api-key", default="local-dev-user")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--pause-seconds", type=float, default=0.8)
    parser.add_argument("--output", default="backend/dev/eval_compare_backup_report.json")
    args = parser.parse_args()

    report = run_compare(
        current_url=str(args.current_url),
        backup_url=str(args.backup_url),
        api_key=str(args.api_key),
        timeout_seconds=int(args.timeout_seconds),
        pause_seconds=float(args.pause_seconds),
    )
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    cur = report["current"]["summary"]
    bak = report["backup"]["summary"]
    print(f"[COMPARE] current accuracy={cur['accuracy_rate']}% ({cur['accuracy_pass']}/{cur['cases_total']})")
    print(f"[COMPARE] backup  accuracy={bak['accuracy_rate']}% ({bak['accuracy_pass']}/{bak['cases_total']})")
    print(f"[COMPARE] winner={report['winner']} delta(current-backup)={report['delta_accuracy_pct']}%")
    print(f"[COMPARE] report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

