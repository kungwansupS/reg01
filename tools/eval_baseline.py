import argparse
import json
import re
import statistics
import time
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List

import requests


ERROR_SIGNATURES = [
    "ระบบขัดข้องชั่วคราว",
    "ขออภัย",
    "error",
]


@dataclass
class EvalRow:
    idx: int
    question: str
    expected: str
    predicted: str
    status_code: int
    latency_sec: float
    similarity: float
    exact_match: bool
    is_fallback_error: bool
    request_failed: bool


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("[Bot พี่เร็ก]", " ")
    text = text.replace("//", " ")
    text = text.replace("**", " ")
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\u0E00-\u0E7Fa-zA-Z0-9 ]+", "", text)
    return text.strip()


def is_fallback_error(text: str) -> bool:
    lower = (text or "").lower()
    return any(sig.lower() in lower for sig in ERROR_SIGNATURES)


def calc_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def load_eval_set(path: Path, limit: int) -> List[tuple]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = [(q, str(meta.get("answer", ""))) for q, meta in data.items()]
    return items[:limit] if limit > 0 else items


def run_eval(api_url: str, eval_set: List[tuple], timeout_sec: int, session_prefix: str) -> List[EvalRow]:
    rows: List[EvalRow] = []
    for i, (question, expected) in enumerate(eval_set, start=1):
        predicted = ""
        status_code = 0
        request_failed = False

        start = time.perf_counter()
        try:
            response = requests.post(
                api_url,
                files={"text": (None, question), "session_id": (None, f"{session_prefix}_{i}")},
                timeout=timeout_sec,
            )
            status_code = response.status_code
            if response.headers.get("content-type", "").startswith("application/json"):
                predicted = response.json().get("text", "")
            else:
                predicted = response.text
        except Exception as exc:
            request_failed = True
            predicted = f"[REQUEST_FAILED] {exc}"
        latency = time.perf_counter() - start

        similarity = calc_similarity(predicted, expected)
        exact_match = normalize_text(predicted) == normalize_text(expected)
        fallback = is_fallback_error(predicted)

        rows.append(
            EvalRow(
                idx=i,
                question=question,
                expected=expected,
                predicted=predicted,
                status_code=status_code,
                latency_sec=round(latency, 3),
                similarity=round(similarity, 4),
                exact_match=exact_match,
                is_fallback_error=fallback,
                request_failed=request_failed,
            )
        )
    return rows


def summarize(rows: List[EvalRow]) -> dict:
    total = len(rows)
    if total == 0:
        return {"total": 0}

    ok_rows = [r for r in rows if r.status_code == 200 and not r.request_failed]
    sims = [r.similarity for r in rows]
    latencies = [r.latency_sec for r in rows]

    summary = {
        "total": total,
        "http_ok_rate": round(len(ok_rows) / total, 4),
        "request_fail_rate": round(sum(r.request_failed for r in rows) / total, 4),
        "fallback_error_rate": round(sum(r.is_fallback_error for r in rows) / total, 4),
        "exact_match_rate": round(sum(r.exact_match for r in rows) / total, 4),
        "mean_similarity": round(statistics.mean(sims), 4),
        "median_similarity": round(statistics.median(sims), 4),
        "pass_rate_sim_ge_0_60": round(sum(r.similarity >= 0.6 for r in rows) / total, 4),
        "mean_latency_sec": round(statistics.mean(latencies), 3),
        "p95_latency_sec": round(sorted(latencies)[int((total - 1) * 0.95)], 3),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline QA accuracy evaluator for REG-01")
    parser.add_argument("--api-url", default="http://127.0.0.1:5000/api/speech")
    parser.add_argument("--dataset", default="backend/memory/cache/faq_cache.json")
    parser.add_argument("--limit", type=int, default=20, help="0 means use all")
    parser.add_argument("--timeout-sec", type=int, default=45)
    parser.add_argument("--session-prefix", default="eval_baseline")
    parser.add_argument("--output", default="tools/eval_baseline_result.json")
    args = parser.parse_args()

    eval_set = load_eval_set(Path(args.dataset), args.limit)
    rows = run_eval(args.api_url, eval_set, args.timeout_sec, args.session_prefix)
    summary = summarize(rows)

    result = {
        "api_url": args.api_url,
        "dataset": args.dataset,
        "limit": args.limit,
        "summary": summary,
        "rows": [asdict(r) for r in rows],
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Baseline Evaluation Summary")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved detailed result: {out_path}")


if __name__ == "__main__":
    main()
