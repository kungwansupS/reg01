"""
Gold-Set Evaluation Runner (Run #1)
Executes a gold-set evaluation against the CMU Reg Assistant backend.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# --- Configuration ---
BASE_URL = "http://localhost:5000"
API_KEY = "dev-token-eval-runner"
GOLD_SET_PATH = "backend/dev/gold_set_data.json"
LOG_DIR = "team-space/eval/logs"
REPORT_DIR = "team-space/eval/reports"
ALLOWED_DIFFICULTY = {"Easy", "Medium", "Hard"}
ALLOWED_BEHAVIOR = {"answer", "abstain", "clarify"}
ALLOWED_ERROR_TYPES = {"none", "timeout", "rate_limit", "invalid_response", "system_error"}

# --- JSON Schema Validation ---
def validate_log_entry(entry):
    """Verifies that a log entry matches the operational schema."""
    required = {
        "run_id": str,
        "question_id": str,
        "question": str,
        "actual_response": str,
        "score": int,
        "http_status": int,
        "expected_behavior": str,
        "scorer": str,
    }
    for key, typ in required.items():
        if key not in entry or not isinstance(entry[key], typ):
            return False

    if entry.get("difficulty") not in ALLOWED_DIFFICULTY:
        return False
    if entry.get("expected_behavior") not in ALLOWED_BEHAVIOR:
        return False
    if entry.get("score", -1) < 0 or entry.get("score", 6) > 5:
        return False
    if entry.get("scorer") != "human":
        return False

    error_type = entry.get("error_type")
    if error_type is not None and error_type not in ALLOWED_ERROR_TYPES:
        return False

    # Optional fields with expected types if present
    optional_types: dict[str, Any] = {
        "category": str,
        "difficulty": str,
        "expected_answer": str,
        "expected_behavior": str,
        "latency_ms": int,
        "has_hallucination": bool,
        "has_citation": bool,
        "scorer_notes": str,
        "timestamp": str,
    }
    for key, typ in optional_types.items():
        if key in entry and not isinstance(entry[key], typ):
            return False
    return True


def _detect_error_type(status_code: int, error_msg: str | None) -> str:
    if error_msg:
        lowered = str(error_msg).lower()
        if "timeout" in lowered:
            return "timeout"
        if "429" in lowered or "rate limit" in lowered:
            return "rate_limit"
        return "system_error"
    if status_code >= 500:
        return "system_error"
    if status_code >= 400:
        return "invalid_response"
    return "none"


def _ensure_dirs() -> None:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)


def _load_existing_results(run_id: str) -> list[dict[str, Any]]:
    log_file = os.path.join(LOG_DIR, f"{run_id}_raw.json")
    if not os.path.exists(log_file):
        return []
    with open(log_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    return loaded if isinstance(loaded, list) else []


def _write_results(run_id: str, results: list[dict[str, Any]]) -> str:
    log_file = os.path.join(LOG_DIR, f"{run_id}_raw.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return log_file


def _schema_pass_rate(results: list[dict[str, Any]]) -> tuple[int, int]:
    passed = sum(1 for row in results if validate_log_entry(row))
    return passed, len(results)

# --- Backend Communication ---
def send_request(question, session_id):
    """Sends a question to the /api/speech endpoint and measures latency."""
    start_time = time.time()
    try:
        r = requests.post(
            f"{BASE_URL}/api/speech",
            data={"text": question, "session_id": session_id},
            headers={"X-API-Key": API_KEY},
            timeout=120
        )
        latency = int((time.time() - start_time) * 1000)
        payload = r.json() if "application/json" in r.headers.get("content-type", "").lower() else {}
        return r.status_code, payload.get("text", ""), latency, None
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return 0, "", latency, str(e)

# --- Execution Logic ---
def run_evaluation(run_id=None, resume=False, cooldown_sec=30, max_questions=None):
    """Main loop to execute all questions in the gold-set."""
    _ensure_dirs()
    if not run_id:
        run_id = f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)
    if not isinstance(questions, list):
        raise ValueError("gold_set_data.json must be a JSON list")

    results = _load_existing_results(run_id) if resume else []
    processed = {row.get("question_id") for row in results if isinstance(row, dict)}
    executed = 0
    print(f"Starting Evaluation Run: {run_id} (resume={resume})")

    for item in questions:
        if max_questions is not None and executed >= max_questions:
            break
        q_id = item.get("question_id", "")
        if q_id in processed:
            continue
        print(f"Processing {q_id}: {str(item.get('question', ''))[:50]}...")

        status, response, latency, error = send_request(item["question"], f"{run_id}_{q_id}")
        error_type = _detect_error_type(status, error)
        log_entry = {
            "run_id": run_id,
            "question_id": q_id,
            "category": item.get("category", ""),
            "difficulty": item.get("difficulty", "Easy"),
            "question": item.get("question", ""),
            "expected_answer": item.get("expected_answer", ""),
            "expected_behavior": item.get("expected_behavior", "answer"),
            "actual_response": response,
            "http_status": status,
            "latency_ms": latency,
            "score": 0,
            "has_hallucination": False,
            "has_citation": False,
            "error_type": error_type,
            "scorer": "human",
            "scorer_notes": "",
            "timestamp": datetime.now().isoformat(),
        }
        if not validate_log_entry(log_entry):
            raise ValueError(f"schema validation failed for {q_id}: {log_entry}")
        results.append(log_entry)
        executed += 1
        _write_results(run_id, results)
        if cooldown_sec > 0:
            time.sleep(cooldown_sec)

    log_file = _write_results(run_id, results)
    schema_passed, total = _schema_pass_rate(results)
    print(f"Schema validation pass: {schema_passed}/{total}")
    print(f"Evaluation complete. Logs saved to {log_file}")
    return run_id

# --- Report Generation ---
def generate_summary_report(run_id):
    """Calculates metrics and generates a Markdown report."""
    _ensure_dirs()
    log_file = os.path.join(LOG_DIR, f"{run_id}_raw.json")
    if not os.path.exists(log_file):
        raise FileNotFoundError(f"log file not found: {log_file}")
    with open(log_file, "r", encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list) or not rows:
        raise ValueError("raw log is empty")

    total = len(rows)
    scores = [int(r.get("score", 0)) for r in rows]
    avg_score = round(sum(scores) / total, 4)
    hard_pass = round((sum(1 for s in scores if s >= 3) / total) * 100, 2)
    hallucination_rate = round((sum(1 for r in rows if r.get("has_hallucination")) / total) * 100, 2)
    abstain_total = sum(1 for r in rows if r.get("expected_behavior") == "abstain")
    correct_abstain = sum(
        1
        for r in rows
        if r.get("expected_behavior") == "abstain" and int(r.get("score", 0)) >= 3
    )
    correct_abstain_rate = round((correct_abstain / abstain_total) * 100, 2) if abstain_total else 0.0
    avg_latency_ms = round(sum(int(r.get("latency_ms", 0)) for r in rows) / total, 2)
    severe_failures = [
        r for r in rows if int(r.get("score", 0)) <= 1 or int(r.get("http_status", 0)) == 0
    ]
    status_counts: defaultdict[int, int] = defaultdict(int)
    by_category: dict[str, list[int]] = defaultdict(list)
    schema_passed, schema_total = _schema_pass_rate(rows)
    for r in rows:
        status_counts[int(r.get("http_status", 0))] += 1
        by_category[str(r.get("category", "unknown"))].append(int(r.get("score", 0)))

    gate_status = "PASS"
    if avg_score < 3.0 or hard_pass < 80.0 or hallucination_rate > 10.0:
        gate_status = "FAIL"
    if len(severe_failures) >= 5:
        gate_status = "SEVERE-FAIL"

    lines = [
        f"# Eval Report: {run_id}",
        "",
        f"- Generated: {datetime.now().isoformat()}",
        f"- Gate Status: **{gate_status}**",
        "",
        "## Metrics",
        f"- Questions: {total}",
        f"- Avg Score: {avg_score}/5",
        f"- Hard-pass Rate (score>=3): {hard_pass}%",
        f"- Hallucination Rate: {hallucination_rate}%",
        f"- Correct Abstain Rate: {correct_abstain_rate}%",
        f"- Avg Latency: {avg_latency_ms} ms",
        f"- Schema Validation Pass: {schema_passed}/{schema_total}",
        "",
        "## HTTP Status Distribution",
    ]
    for code in sorted(status_counts):
        lines.append(f"- {code}: {status_counts[code]}")

    lines.extend(["", "## Category Scores"])
    for cat in sorted(by_category):
        cat_scores = by_category[cat]
        lines.append(f"- {cat}: {round(sum(cat_scores)/len(cat_scores), 4)}/5 ({len(cat_scores)} questions)")

    lines.extend(["", "## Severe Failures"])
    if severe_failures:
        for row in severe_failures[:20]:
            lines.append(
                f"- {row.get('question_id')}: score={row.get('score')} status={row.get('http_status')} error={row.get('error_type')}"
            )
    else:
        lines.append("- None")

    report_file = os.path.join(REPORT_DIR, f"{run_id}_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report generated: {report_file}")
    return report_file


def parse_args():
    parser = argparse.ArgumentParser(description="Run gold-set evaluation for CMU Reg assistant")
    parser.add_argument("--run-id", default=None, help="Run identifier. If omitted, auto generated.")
    parser.add_argument("--resume", action="store_true", help="Resume from existing run log.")
    parser.add_argument("--cooldown", type=int, default=30, help="Cooldown seconds between requests.")
    parser.add_argument("--max-questions", type=int, default=None, help="Limit number of questions for quick test.")
    parser.add_argument("--skip-report", action="store_true", help="Skip report generation.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    rid = run_evaluation(
        run_id=args.run_id,
        resume=args.resume,
        cooldown_sec=args.cooldown,
        max_questions=args.max_questions,
    )
    if not args.skip_report:
        generate_summary_report(rid)
    print(f"Next steps: manual scoring required for {rid}")
