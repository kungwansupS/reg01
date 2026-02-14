"""
Multi-mode factual evaluation for REG-01 assistant.

Evaluates:
1. Accuracy by mode and category (rule-based)
2. Latency (client + server)
3. Token usage (prompt/completion/total)

Usage:
  python -m backend.dev.eval_multi_mode
  python -m backend.dev.eval_multi_mode --mode testclient
  python -m backend.dev.eval_multi_mode --mode http --base-url http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _contains_all(text: str, terms: List[str]) -> bool:
    normalized = _normalize_text(text)
    return all(term.lower() in normalized for term in terms)


def _contains_any(text: str, terms: List[str]) -> bool:
    normalized = _normalize_text(text)
    return any(term.lower() in normalized for term in terms)


def _is_system_error_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    return "ระบบขัดข้อง" in normalized or "temporarily unavailable" in normalized


def _rule_qr_deadline(text: str) -> bool:
    normalized = _normalize_text(text)
    return (
        ("23.00" in normalized or "23:00" in normalized or "23 น" in normalized)
        and ("qr" in normalized or "คิวอาร์" in normalized)
    )


def _rule_credit_treasury_deadline(text: str) -> bool:
    normalized = _normalize_text(text)
    return (
        ("16.30" in normalized or "16:30" in normalized or "16.3" in normalized)
        and "บัตรเครดิต" in normalized
        and "กองคลัง" in normalized
    )


def _rule_out_of_scope_weather(text: str) -> bool:
    if _is_system_error_reply(text):
        return False
    return _contains_any(
        text,
        [
            "ไม่พบข้อมูล",
            "ไม่มีข้อมูล",
            "ในเอกสาร",
            "ขอบเขต",
            "ไม่สามารถ",
            "ขออภัย",
        ],
    )


@dataclass
class EvalCase:
    case_id: str
    category: str
    message: str
    expected: str
    validator: Callable[[str], bool]
    scorable: bool = True


def _build_cases() -> List[EvalCase]:
    return [
        EvalCase(
            case_id="calendar_open_sem1_2568",
            category="calendar",
            message="เปิดภาคการศึกษา ภาคเรียนที่ 1 ปีการศึกษา 2568 วันไหน",
            expected="23 มิถุนายน 2568",
            validator=lambda out: _contains_all(out, ["23", "มิถุนายน", "2568"]),
        ),
        EvalCase(
            case_id="calendar_open_sem2_2568",
            category="calendar",
            message="เปิดภาคการศึกษา ภาคเรียนที่ 2 ปีการศึกษา 2568 วันไหน",
            expected="17 พฤศจิกายน 2568",
            validator=lambda out: _contains_all(out, ["17", "พฤศจิกายน", "2568"]),
        ),
        EvalCase(
            case_id="calendar_fee_window_sem1_2568",
            category="calendar",
            message="ชำระเงินค่าธรรมเนียม ภาคเรียนที่ 1/2568 ช่วงวันไหน",
            expected="7-11 กรกฎาคม 2568",
            validator=lambda out: _contains_all(out, ["7", "11", "กรกฎาคม", "2568"]),
        ),
        EvalCase(
            case_id="calendar_midterm_sem1_2568",
            category="calendar",
            message="สอบกลางภาค ภาคเรียนที่ 1/2568 ช่วงไหน",
            expected="25-31 สิงหาคม 2568",
            validator=lambda out: _contains_all(out, ["25", "31", "สิงหาคม", "2568"]),
        ),
        EvalCase(
            case_id="procedure_withdraw_no_w_sem2_2568",
            category="procedure",
            message="ถอนกระบวนวิชาแบบไม่ได้รับ W ภาคเรียนที่ 2/2568 ช่วงไหน",
            expected="15-28 พฤศจิกายน 2568",
            validator=lambda out: _contains_all(out, ["15", "28", "พฤศจิกายน", "2568"]),
        ),
        EvalCase(
            case_id="payment_qr_deadline",
            category="payment",
            message="ชำระค่าธรรมเนียมผ่าน QR CODE ได้ถึงกี่โมง",
            expected="23.00 น.",
            validator=_rule_qr_deadline,
        ),
        EvalCase(
            case_id="payment_credit_treasury_deadline",
            category="payment",
            message="ชำระด้วยบัตรเครดิตที่กองคลังได้ถึงกี่โมง",
            expected="16.30 น.",
            validator=_rule_credit_treasury_deadline,
        ),
        EvalCase(
            case_id="out_of_scope_weather",
            category="out_of_scope",
            message="พรุ่งนี้ฝนตกไหมที่เชียงใหม่",
            expected="ควรตอบว่าอยู่นอกขอบเขตข้อมูลเอกสาร/ไม่มีข้อมูล",
            validator=_rule_out_of_scope_weather,
        ),
    ]


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return statistics.mean(values)


def _p90(values: List[float]) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * 0.9) - 1)
    return sorted_vals[idx]


def _build_modes() -> Dict[str, Optional[Dict[str, Any]]]:
    low_cost = {
        "memory": {"enable_summary": False, "recent_messages": 4},
        "rag": {"top_k": 3, "use_llm_rerank": False, "use_intent_analysis": False},
        "faq": {"auto_learn": False},
    }
    return {
        "default": None,
        "no_rag": {
            "rag": {
                "mode": "never",
                "top_k": 3,
                "use_hybrid": False,
                "use_llm_rerank": False,
                "use_intent_analysis": False,
            },
            "memory": {"enable_summary": False, "recent_messages": 4},
            "faq": {"auto_learn": False},
        },
        "always_rag": {
            "rag": {
                "mode": "always",
                "top_k": 5,
                "use_hybrid": True,
                "use_llm_rerank": True,
                "use_intent_analysis": True,
            },
            "memory": {"enable_summary": True, "recent_messages": 8},
            "faq": {"auto_learn": False},
        },
        "low_cost": low_cost,
    }


def _run_one_case(
    post_json: Callable[[Dict[str, Any], int], Any],
    mode_name: str,
    mode_cfg: Optional[Dict[str, Any]],
    case: EvalCase,
    timeout_seconds: int,
    include_debug: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "message": case.message,
        "session_id": f"eval_{mode_name}_{case.case_id}_{uuid.uuid4().hex[:8]}",
        "include_debug": bool(include_debug),
    }
    if mode_cfg:
        payload["config_override"] = mode_cfg

    row: Dict[str, Any] = {
        "mode": mode_name,
        "id": case.case_id,
        "category": case.category,
        "message": case.message,
        "expected": case.expected,
        "scorable": bool(case.scorable),
        "http_ok": False,
        "status_code": None,
        "ok": False,
        "latency_seconds_client": None,
        "latency_seconds_server": None,
        "trace_id": "",
        "tokens": {"prompt": 0, "completion": 0, "total": 0, "error": False},
        "output": "",
        "error": "",
    }

    started = time.perf_counter()
    try:
        response = post_json(payload, timeout_seconds)
        row["latency_seconds_client"] = round(time.perf_counter() - started, 3)
        row["status_code"] = int(response.status_code)
        row["http_ok"] = bool(200 <= int(response.status_code) < 300)
        if not row["http_ok"]:
            row["error"] = str(response.text)[:500]
            return row

        data = response.json()
        result = data.get("result") if isinstance(data, dict) else {}
        if not isinstance(result, dict):
            result = {}
        output_text = str(result.get("text") or "")
        tokens = result.get("tokens") if isinstance(result.get("tokens"), dict) else {}

        row["output"] = output_text
        row["trace_id"] = str(data.get("trace_id") or result.get("trace_id") or "")
        row["latency_seconds_server"] = float(data.get("latency_seconds") or 0.0)
        row["tokens"] = {
            "prompt": int(tokens.get("prompt_tokens", 0) or 0),
            "completion": int(tokens.get("completion_tokens", 0) or 0),
            "total": int(tokens.get("total_tokens", 0) or 0),
            "error": bool(tokens.get("error", False)),
        }
        if case.scorable:
            row["ok"] = bool(case.validator(output_text)) and not _is_system_error_reply(output_text)
        else:
            row["ok"] = not _is_system_error_reply(output_text)
        return row
    except Exception as exc:
        row["error"] = str(exc)
        return row


def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    http_ok = [row for row in rows if bool(row.get("http_ok"))]
    scorable_ok = [row for row in http_ok if bool(row.get("scorable"))]
    passed = [row for row in scorable_ok if bool(row.get("ok"))]

    lat_server = [float(row.get("latency_seconds_server") or 0.0) for row in http_ok]
    tok_total = [int((row.get("tokens") or {}).get("total", 0)) for row in http_ok]
    tok_prompt = [int((row.get("tokens") or {}).get("prompt", 0)) for row in http_ok]
    tok_completion = [int((row.get("tokens") or {}).get("completion", 0)) for row in http_ok]

    total_tokens = sum(tok_total)
    total_prompt = sum(tok_prompt)
    total_completion = sum(tok_completion)

    by_category: Dict[str, Dict[str, Any]] = {}
    for row in scorable_ok:
        cat = str(row.get("category") or "unknown")
        bucket = by_category.setdefault(cat, {"cases": 0, "pass": 0})
        bucket["cases"] += 1
        if bool(row.get("ok")):
            bucket["pass"] += 1

    for cat, bucket in by_category.items():
        cases = int(bucket["cases"])
        bucket["accuracy_rate"] = round((int(bucket["pass"]) / cases * 100.0), 2) if cases else 0.0

    return {
        "cases_total": len(rows),
        "http_ok": len(http_ok),
        "scorable_cases": len(scorable_ok),
        "accuracy_pass": len(passed),
        "accuracy_rate": round((len(passed) / len(scorable_ok) * 100.0), 2) if scorable_ok else 0.0,
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
            "prompt_share_pct": round((total_prompt / max(1, total_tokens) * 100.0), 2) if tok_total else None,
            "completion_share_pct": round((total_completion / max(1, total_tokens) * 100.0), 2) if tok_total else None,
            "total_tokens_all_cases": int(total_tokens),
        },
        "by_category": by_category,
    }


def run_eval(
    *,
    mode: str,
    base_url: str,
    dev_token: str,
    timeout_seconds: int,
    include_debug: bool,
    pause_seconds: float,
    selected_modes: Optional[List[str]] = None,
    selected_case_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    all_modes = _build_modes()
    all_cases = _build_cases()

    if selected_modes:
        wanted_modes = {str(item).strip() for item in selected_modes if str(item).strip()}
        modes = {name: cfg for name, cfg in all_modes.items() if name in wanted_modes}
        if not modes:
            raise ValueError(f"No valid modes selected. available={list(all_modes.keys())}")
    else:
        modes = all_modes

    if selected_case_ids:
        wanted_case_ids = {str(item).strip() for item in selected_case_ids if str(item).strip()}
        cases = [case for case in all_cases if case.case_id in wanted_case_ids]
        if not cases:
            raise ValueError("No valid case ids selected.")
    else:
        cases = all_cases

    if mode not in {"http", "testclient"}:
        raise ValueError(f"Unsupported mode: {mode}")

    close_callback: Optional[Callable[[], None]] = None
    post_json: Optional[Callable[[Dict[str, Any], int], Any]] = None
    headers = {"X-Dev-Token": dev_token, "Content-Type": "application/json"}

    if mode == "http":
        url = f"{base_url.rstrip('/')}/api/dev/test"
        session = requests.Session()

        def _post(payload: Dict[str, Any], timeout: int):
            return session.post(url, headers=headers, json=payload, timeout=timeout)

        post_json = _post
        close_callback = session.close
    else:
        backend_root = os.path.abspath("backend")
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        from fastapi.testclient import TestClient
        import main as backend_main

        client = TestClient(backend_main.app)

        def _post(payload: Dict[str, Any], timeout: int):
            return client.post("/api/dev/test", headers=headers, json=payload)

        post_json = _post
        close_callback = client.close

    mode_rows: Dict[str, List[Dict[str, Any]]] = {name: [] for name in modes.keys()}
    flat_rows: List[Dict[str, Any]] = []
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        total_calls = len(cases) * len(modes)
        current = 0
        for mode_name, mode_cfg in modes.items():
            for case in cases:
                current += 1
                row = _run_one_case(
                    post_json=post_json,
                    mode_name=mode_name,
                    mode_cfg=mode_cfg,
                    case=case,
                    timeout_seconds=timeout_seconds,
                    include_debug=include_debug,
                )
                mode_rows[mode_name].append(row)
                flat_rows.append(row)
                print(
                    f"[{current}/{total_calls}] "
                    f"mode={mode_name} case={case.case_id} "
                    f"status={row['status_code']} ok={row['ok']} "
                    f"lat={row['latency_seconds_client']}"
                )
                if pause_seconds > 0 and current < total_calls:
                    time.sleep(float(pause_seconds))
    finally:
        if close_callback:
            close_callback()

    mode_summary: Dict[str, Any] = {}
    for mode_name, rows in mode_rows.items():
        mode_summary[mode_name] = _aggregate(rows)

    overall = _aggregate(flat_rows)
    return {
        "run_at": started_at,
        "runner_mode": mode,
        "base_url": base_url,
        "modes": list(modes.keys()),
        "cases": [
            {
                "case_id": case.case_id,
                "category": case.category,
                "message": case.message,
                "expected": case.expected,
                "scorable": bool(case.scorable),
            }
            for case in cases
        ],
        "mode_summary": mode_summary,
        "overall": overall,
        "rows": flat_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["http", "testclient"], default="testclient")
    parser.add_argument("--base-url", default=os.getenv("BENCH_BASE_URL", "http://127.0.0.1:5000"))
    parser.add_argument("--dev-token", default=os.getenv("DEV_TOKEN", "dev-secret-key"))
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--include-debug", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    parser.add_argument(
        "--modes",
        default="",
        help="Comma-separated mode names from eval set (default,no_rag,always_rag,low_cost).",
    )
    parser.add_argument(
        "--case-ids",
        default="",
        help="Comma-separated case ids to run (leave empty for all).",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("backend", "dev", "eval_multi_mode_report_latest.json"),
    )
    args = parser.parse_args()

    selected_modes = [item.strip() for item in str(args.modes or "").split(",") if item.strip()]
    selected_case_ids = [item.strip() for item in str(args.case_ids or "").split(",") if item.strip()]

    report = run_eval(
        mode=str(args.mode),
        base_url=str(args.base_url),
        dev_token=str(args.dev_token),
        timeout_seconds=int(args.timeout_seconds),
        include_debug=bool(args.include_debug),
        pause_seconds=float(args.pause_seconds),
        selected_modes=selected_modes or None,
        selected_case_ids=selected_case_ids or None,
    )

    output_path = str(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    brief = {
        "run_at": report["run_at"],
        "runner_mode": report["runner_mode"],
        "overall": report["overall"],
        "mode_summary": report["mode_summary"],
        "output": output_path,
    }
    print("\n=== EVAL SUMMARY ===")
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
