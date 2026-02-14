"""
Runtime benchmark for REG-01 assistant.

Measures:
1. Response latency (server + client observed)
2. Rule-based factual accuracy on known calendar/payment facts
3. Token usage distribution (prompt/completion/total)

Usage:
  python -m backend.dev.benchmark_runtime
  python -m backend.dev.benchmark_runtime --base-url http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import requests


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _contains_all(text: str, terms: List[str]) -> bool:
    normalized = _normalize_text(text)
    return all(term.lower() in normalized for term in terms)


def _rule_qr_deadline(text: str) -> bool:
    normalized = _normalize_text(text)
    has_time = ("23.00" in normalized) or ("23:00" in normalized) or ("23 น" in normalized)
    has_channel = ("qr" in normalized) or ("คิวอาร์" in normalized)
    return has_time and has_channel


def _rule_credit_treasury_deadline(text: str) -> bool:
    normalized = _normalize_text(text)
    has_time = ("16.30" in normalized) or ("16:30" in normalized) or ("16.3" in normalized)
    has_channel = ("บัตรเครดิต" in normalized) or ("กองคลัง" in normalized)
    return has_time and has_channel


def _is_system_error_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    return "ระบบขัดข้อง" in normalized or "temporarily unavailable" in normalized


@dataclass
class BenchCase:
    case_id: str
    message: str
    validator: Callable[[str], bool]
    expected: str


def _build_cases() -> List[BenchCase]:
    return [
        BenchCase(
            case_id="open_sem1_2568",
            message="เปิดภาคการศึกษา ภาคเรียนที่ 1 ปีการศึกษา 2568 วันไหน",
            validator=lambda out: _contains_all(out, ["23", "มิถุนายน", "2568"]),
            expected="23 มิถุนายน 2568",
        ),
        BenchCase(
            case_id="open_sem2_2568",
            message="เปิดภาคการศึกษา ภาคเรียนที่ 2 ปีการศึกษา 2568 วันไหน",
            validator=lambda out: _contains_all(out, ["17", "พฤศจิกายน", "2568"]),
            expected="17 พฤศจิกายน 2568",
        ),
        BenchCase(
            case_id="fee_window_sem1_2568",
            message="ชำระเงินค่าธรรมเนียม ภาคเรียนที่ 1/2568 ช่วงวันไหน",
            validator=lambda out: _contains_all(out, ["7", "11", "กรกฎาคม", "2568"]),
            expected="7-11 กรกฎาคม 2568",
        ),
        BenchCase(
            case_id="midterm_sem1_2568",
            message="สอบกลางภาค ภาคเรียนที่ 1/2568 ช่วงไหน",
            validator=lambda out: _contains_all(out, ["25", "31", "สิงหาคม", "2568"]),
            expected="25-31 สิงหาคม 2568",
        ),
        BenchCase(
            case_id="payment_qr_deadline",
            message="ชำระค่าธรรมเนียมผ่าน QR CODE ได้ถึงกี่โมง",
            validator=_rule_qr_deadline,
            expected="QR ชำระได้ถึง 23.00 น.",
        ),
        BenchCase(
            case_id="payment_credit_treasury_deadline",
            message="ชำระด้วยบัตรเครดิตที่กองคลังได้ถึงกี่โมง",
            validator=_rule_credit_treasury_deadline,
            expected="บัตรเครดิตที่กองคลัง ชำระได้ถึง 16.30 น.",
        ),
    ]


def _p90(values: List[float]) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * 0.9) - 1)
    return sorted_vals[idx]


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return statistics.mean(values)


def _run_case(
    post_json: Callable[[Dict[str, object], int], object],
    case: BenchCase,
    timeout_seconds: int,
    include_debug: bool,
    config_override: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    payload = {
        "message": case.message,
        "session_id": f"bench_{case.case_id}_{int(time.time())}",
        "include_debug": bool(include_debug),
    }
    if config_override:
        payload["config_override"] = config_override

    started = time.perf_counter()
    row: Dict[str, object] = {
        "id": case.case_id,
        "message": case.message,
        "expected": case.expected,
        "http_ok": False,
        "status_code": None,
        "latency_seconds_client": None,
        "latency_seconds_server": None,
        "trace_id": "",
        "tokens": {"prompt": 0, "completion": 0, "total": 0, "error": False},
        "output": "",
        "ok": False,
        "error": "",
    }

    try:
        response = post_json(payload, timeout_seconds)
        elapsed = time.perf_counter() - started
        row["latency_seconds_client"] = round(elapsed, 3)
        row["status_code"] = int(response.status_code)
        status_ok = bool(200 <= int(response.status_code) < 300)
        row["http_ok"] = status_ok
        if not status_ok:
            row["error"] = response.text[:500]
            return row

        data = response.json()
        result = data.get("result") if isinstance(data, dict) else {}
        if not isinstance(result, dict):
            result = {}

        output_text = str(result.get("text") or "")
        tokens = result.get("tokens") if isinstance(result.get("tokens"), dict) else {}

        row["output"] = output_text
        row["latency_seconds_server"] = float(data.get("latency_seconds") or 0.0)
        row["trace_id"] = str(data.get("trace_id") or result.get("trace_id") or "")
        row["tokens"] = {
            "prompt": int(tokens.get("prompt_tokens", 0) or 0),
            "completion": int(tokens.get("completion_tokens", 0) or 0),
            "total": int(tokens.get("total_tokens", 0) or 0),
            "error": bool(tokens.get("error", False)),
        }
        row["ok"] = bool(case.validator(output_text)) and not _is_system_error_reply(output_text)
        return row
    except Exception as exc:
        row["error"] = str(exc)
        return row


def run_benchmark(
    base_url: str,
    dev_token: str,
    timeout_seconds: int,
    include_debug: bool,
    mode: str = "http",
    config_override: Optional[Dict[str, object]] = None,
    case_ids: Optional[List[str]] = None,
    pause_seconds: float = 0.0,
) -> Dict[str, object]:
    cases = _build_cases()
    if case_ids:
        wanted = set(case_ids)
        cases = [case for case in cases if case.case_id in wanted]
    rows: List[Dict[str, object]] = []
    headers = {
        "X-Dev-Token": dev_token,
        "Content-Type": "application/json",
    }

    close_callback: Optional[Callable[[], None]] = None
    post_json: Optional[Callable[[Dict[str, object], int], object]] = None

    if mode == "http":
        url = f"{base_url.rstrip('/')}/api/dev/test"
        session = requests.Session()

        def _post_json(payload: Dict[str, object], timeout: int):
            return session.post(url, headers=headers, json=payload, timeout=timeout)

        post_json = _post_json

        def _close():
            session.close()

        close_callback = _close
    elif mode == "testclient":
        backend_root = os.path.abspath("backend")
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        from fastapi.testclient import TestClient
        import main as backend_main

        test_client = TestClient(backend_main.app)

        def _post_json(payload: Dict[str, object], timeout: int):
            return test_client.post("/api/dev/test", headers=headers, json=payload)

        post_json = _post_json
        close_callback = test_client.close
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    try:
        for index, case in enumerate(cases, start=1):
            row = _run_case(
                post_json=post_json,
                case=case,
                timeout_seconds=timeout_seconds,
                include_debug=include_debug,
                config_override=config_override,
            )
            rows.append(row)
            print(
                f"[{index}/{len(cases)}] {case.case_id} "
                f"status={row['status_code']} ok={row['ok']} "
                f"lat={row['latency_seconds_client']}"
            )
            if pause_seconds > 0 and index < len(cases):
                time.sleep(float(pause_seconds))
    finally:
        if close_callback:
            close_callback()

    ok_rows = [row for row in rows if bool(row.get("http_ok"))]
    pass_rows = [row for row in ok_rows if bool(row.get("ok"))]

    lat_server = [float(row.get("latency_seconds_server") or 0.0) for row in ok_rows]
    tok_total = [int((row.get("tokens") or {}).get("total", 0)) for row in ok_rows]
    tok_prompt = [int((row.get("tokens") or {}).get("prompt", 0)) for row in ok_rows]
    tok_completion = [int((row.get("tokens") or {}).get("completion", 0)) for row in ok_rows]

    total_tokens_sum = sum(tok_total)
    prompt_sum = sum(tok_prompt)
    completion_sum = sum(tok_completion)

    summary: Dict[str, object] = {
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": base_url,
        "cases": len(rows),
        "http_ok": len(ok_rows),
        "accuracy_pass": len(pass_rows),
        "accuracy_rate": round((len(pass_rows) / len(ok_rows) * 100.0), 2) if ok_rows else 0.0,
        "latency_seconds": {
            "avg": round(_safe_mean(lat_server), 3) if lat_server else None,
            "p50": round(statistics.median(lat_server), 3) if lat_server else None,
            "p90": round(_p90(lat_server), 3) if lat_server else None,
            "min": round(min(lat_server), 3) if lat_server else None,
            "max": round(max(lat_server), 3) if lat_server else None,
        },
        "tokens": {
            "avg_total": round(_safe_mean(tok_total), 1) if tok_total else None,
            "avg_prompt": round(_safe_mean(tok_prompt), 1) if tok_prompt else None,
            "avg_completion": round(_safe_mean(tok_completion), 1) if tok_completion else None,
            "prompt_share_pct": round((prompt_sum / max(1, total_tokens_sum) * 100.0), 2) if tok_total else None,
            "completion_share_pct": round((completion_sum / max(1, total_tokens_sum) * 100.0), 2) if tok_total else None,
            "total_tokens_all_cases": int(total_tokens_sum),
        },
        "rows": rows,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("BENCH_BASE_URL", "http://127.0.0.1:5000"))
    parser.add_argument("--dev-token", default=os.getenv("DEV_TOKEN", "dev-secret-key"))
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--mode", choices=["http", "testclient"], default="http")
    parser.add_argument("--include-debug", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=0.0)
    parser.add_argument("--cases", default="", help="Comma-separated case ids to run.")
    parser.add_argument(
        "--config-override-json",
        default="",
        help="JSON string for flow config override used in /api/dev/test payload.",
    )
    parser.add_argument(
        "--config-override-file",
        default="",
        help="Path to JSON file for flow config override.",
    )
    parser.add_argument("--output", default=os.path.join("backend", "dev", "benchmark_report_latest.json"))
    args = parser.parse_args()

    case_ids: Optional[List[str]] = None
    if str(args.cases or "").strip():
        case_ids = [item.strip() for item in str(args.cases).split(",") if item.strip()]

    config_override: Optional[Dict[str, object]] = None
    if str(args.config_override_json or "").strip() and str(args.config_override_file or "").strip():
        raise ValueError("Use either --config-override-json or --config-override-file, not both.")

    if str(args.config_override_json or "").strip():
        parsed = json.loads(str(args.config_override_json))
        if not isinstance(parsed, dict):
            raise ValueError("--config-override-json must be a JSON object")
        config_override = parsed
    elif str(args.config_override_file or "").strip():
        with open(str(args.config_override_file), "r", encoding="utf-8-sig") as handle:
            parsed = json.load(handle)
        if not isinstance(parsed, dict):
            raise ValueError("--config-override-file must point to a JSON object.")
        config_override = parsed

    summary = run_benchmark(
        base_url=args.base_url,
        dev_token=args.dev_token,
        timeout_seconds=int(args.timeout_seconds),
        include_debug=bool(args.include_debug),
        mode=str(args.mode),
        config_override=config_override,
        case_ids=case_ids,
        pause_seconds=float(args.pause_seconds),
    )

    output_path = str(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print("\n=== BENCHMARK SUMMARY ===")
    print(
        json.dumps(
            {
                "cases": summary["cases"],
                "http_ok": summary["http_ok"],
                "accuracy_pass": summary["accuracy_pass"],
                "accuracy_rate": summary["accuracy_rate"],
                "latency_seconds": summary["latency_seconds"],
                "tokens": summary["tokens"],
                "output": output_path,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
