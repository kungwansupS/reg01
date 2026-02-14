import json
import logging
import os
import re
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Optional

from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_FILE = os.path.join(BASE_DIR, "cache/faq_cache.json")

MAX_FAQ = 500
SIM_THRESHOLD = 0.9
ANSWER_CONFLICT_SIM_THRESHOLD = 0.68
PROTECTED_HIT_COUNT = 3
DEFAULT_STATIC_TTL_DAYS = 45
DEFAULT_TIME_SENSITIVE_TTL_HOURS = 6
DEFAULT_MIN_ANSWER_CHARS = 30
DEFAULT_MIN_RETRIEVAL_SCORE = 0.35

TIME_PATTERNS = [
    re.compile(
        r"(today|tomorrow|yesterday|now|current|latest|"
        r"this\s+(week|month|semester|term|year)|next\s+(week|month|semester|term|year))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(วันนี้|พรุ่งนี้|เมื่อวาน|ตอนนี้|ล่าสุด|ปัจจุบัน|อัปเดต|อัพเดต|"
        r"เทอมนี้|ภาคเรียนนี้|ปีนี้|สัปดาห์นี้|เดือนนี้|อีกกี่|กี่วัน|เมื่อไหร่|วันไหน|เวลาไหน)",
        re.IGNORECASE,
    ),
]

LOW_QUALITY_PATTERNS = [
    re.compile(r"ขออภัย.*(ขัดข้อง|ชั่วคราว|ไม่สามารถ)", re.IGNORECASE),
    re.compile(r"ระบบ.*ขัดข้อง", re.IGNORECASE),
    re.compile(r"ไม่พบข้อมูล", re.IGNORECASE),
    re.compile(r"ไม่แน่ใจ|ไม่ทราบ", re.IGNORECASE),
    re.compile(r"\berror\b|\bexception\b|\btimeout\b", re.IGNORECASE),
    re.compile(r"\bsorry\b|\btemporar(y|ily)\b|\bunknown\b", re.IGNORECASE),
]

_LOCK = RLock()
_question_vec_cache: Dict[str, Any] = {}


def _load_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _safe_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


MAX_FAQ = _load_env_int("FAQ_MAX_ITEMS", MAX_FAQ, 50, 5000)
SIM_THRESHOLD = _safe_float(os.getenv("FAQ_SIM_THRESHOLD"), SIM_THRESHOLD, 0.5, 0.99)
DEFAULT_STATIC_TTL_DAYS = _load_env_int("FAQ_STATIC_TTL_DAYS", DEFAULT_STATIC_TTL_DAYS, 1, 365)
DEFAULT_TIME_SENSITIVE_TTL_HOURS = _load_env_int(
    "FAQ_TIME_SENSITIVE_TTL_HOURS", DEFAULT_TIME_SENSITIVE_TTL_HOURS, 1, 168
)
DEFAULT_MIN_ANSWER_CHARS = _load_env_int("FAQ_MIN_ANSWER_CHARS", DEFAULT_MIN_ANSWER_CHARS, 10, 2000)

# Load model once at module level.
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

try:
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        faq_cache = loaded if isinstance(loaded, dict) else {}
except (FileNotFoundError, json.JSONDecodeError):
    faq_cache = {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_iso_to_utc(raw_value: Any) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_time_sensitive(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in TIME_PATTERNS)


def _is_low_quality_answer(answer: str, min_answer_chars: int) -> bool:
    text = _normalize_text(answer)
    if len(text) < min_answer_chars:
        return True
    if text.count("?") >= 8:
        return True
    for pattern in LOW_QUALITY_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _looks_unusable_answer(answer: str) -> bool:
    text = _normalize_text(answer)
    if not text:
        return True
    if text.count("?") >= 8:
        return True
    for pattern in LOW_QUALITY_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _compute_ttl_seconds(
    *,
    time_sensitive: bool,
    max_age_days: Optional[Any] = None,
    time_sensitive_ttl_hours: Optional[Any] = None,
) -> int:
    static_days = _safe_int(max_age_days, DEFAULT_STATIC_TTL_DAYS, 1, 365)
    dynamic_hours = _safe_int(
        time_sensitive_ttl_hours,
        DEFAULT_TIME_SENSITIVE_TTL_HOURS,
        1,
        168,
    )
    if time_sensitive:
        return dynamic_hours * 3600
    return static_days * 86400


def _entry_ttl_seconds(
    entry: Dict[str, Any],
    max_age_days: Optional[Any] = None,
    question_text: str = "",
) -> int:
    entry_ttl = entry.get("ttl_seconds")
    if entry_ttl is not None:
        return _safe_int(entry_ttl, 3600, 60, 365 * 86400)
    inferred_time_sensitive = bool(entry.get("time_sensitive", _is_time_sensitive(question_text)))
    return _compute_ttl_seconds(
        time_sensitive=inferred_time_sensitive,
        max_age_days=max_age_days,
        time_sensitive_ttl_hours=entry.get("time_sensitive_ttl_hours"),
    )


def _is_entry_expired(
    entry: Dict[str, Any],
    now_utc: datetime,
    max_age_days: Optional[Any] = None,
    question_text: str = "",
) -> bool:
    updated_at = _parse_iso_to_utc(entry.get("last_updated"))
    if updated_at is None:
        return True
    age_seconds = (now_utc - updated_at).total_seconds()
    return age_seconds > _entry_ttl_seconds(
        entry,
        max_age_days=max_age_days,
        question_text=question_text,
    )


def save_faq_cache() -> None:
    with _LOCK:
        try:
            os.makedirs(os.path.dirname(FAQ_FILE), exist_ok=True)
            with open(FAQ_FILE, "w", encoding="utf-8") as f:
                json.dump(faq_cache, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("Save FAQ Error: %s", exc, exc_info=True)


def encode_text(text: str):
    return model.encode(text, convert_to_tensor=True, show_progress_bar=False)


def _question_vector(text: str):
    normalized = _normalize_text(text)
    if not normalized:
        return encode_text("")
    with _LOCK:
        cached = _question_vec_cache.get(normalized)
    if cached is not None:
        return cached
    vector = encode_text(normalized)
    with _LOCK:
        _question_vec_cache[normalized] = vector
    return vector


def _cleanup_cache_locked(now_utc: Optional[datetime] = None) -> int:
    now_utc = now_utc or _now_utc()
    removed = 0
    for question, entry in list(faq_cache.items()):
        if not isinstance(entry, dict):
            del faq_cache[question]
            _question_vec_cache.pop(question, None)
            removed += 1
            continue
        if not _normalize_text(entry.get("answer")):
            del faq_cache[question]
            _question_vec_cache.pop(question, None)
            removed += 1
            continue
        if _looks_unusable_answer(str(entry.get("answer", ""))):
            del faq_cache[question]
            _question_vec_cache.pop(question, None)
            removed += 1
            continue
        if _is_entry_expired(entry, now_utc, question_text=question):
            del faq_cache[question]
            _question_vec_cache.pop(question, None)
            removed += 1
    return removed


def _answer_similarity(answer_a: str, answer_b: str) -> float:
    vec_a = encode_text(_normalize_text(answer_a))
    vec_b = encode_text(_normalize_text(answer_b))
    return float(util.cos_sim(vec_a, vec_b).item())


def get_faq_answer(
    question: str,
    similarity_threshold: Optional[float] = None,
    include_meta: bool = False,
    allow_time_sensitive: bool = False,
    max_age_days: Optional[Any] = None,
):
    question_text = _normalize_text(question)
    if not question_text:
        return None

    threshold = _safe_float(similarity_threshold, SIM_THRESHOLD, 0.5, 0.99)
    now_utc = _now_utc()

    with _LOCK:
        if not faq_cache:
            return None
        removed = _cleanup_cache_locked(now_utc)
        if removed:
            save_faq_cache()
        items = list(faq_cache.items())

    if not items:
        return None

    query_vec = _question_vector(question_text)
    best_match = None
    best_score = threshold

    for cached_question, entry in items:
        if not isinstance(entry, dict):
            continue
        entry_time_sensitive = bool(entry.get("time_sensitive", _is_time_sensitive(cached_question)))
        if not allow_time_sensitive and entry_time_sensitive:
            continue
        if _is_entry_expired(
            entry,
            now_utc,
            max_age_days=max_age_days,
            question_text=cached_question,
        ):
            continue
        score = float(util.cos_sim(query_vec, _question_vector(cached_question)).item())
        if score > best_score:
            best_score = score
            best_match = cached_question

    if not best_match:
        return None

    with _LOCK:
        entry = faq_cache.get(best_match)
        if not isinstance(entry, dict):
            return None
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_hit_at"] = now_utc.isoformat()
        save_faq_cache()
        answer = str(entry.get("answer") or "")
        metadata = {
            "question": best_match,
            "score": round(best_score, 4),
            "time_sensitive": bool(entry.get("time_sensitive", _is_time_sensitive(best_match))),
            "last_updated": entry.get("last_updated"),
            "ttl_seconds": _entry_ttl_seconds(
                entry,
                max_age_days=max_age_days,
                question_text=best_match,
            ),
        }

    if include_meta:
        return {"answer": answer, **metadata}
    return answer


def update_faq(question: str, answer: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = metadata or {}
    question_text = _normalize_text(question)
    answer_text = _normalize_text(answer)
    now_iso = _now_utc().isoformat()

    if not question_text or not answer_text:
        return {"updated": False, "reason": "empty_question_or_answer"}

    min_answer_chars = _safe_int(
        metadata.get("min_answer_chars"),
        DEFAULT_MIN_ANSWER_CHARS,
        10,
        2000,
    )
    if _is_low_quality_answer(answer_text, min_answer_chars=min_answer_chars):
        return {"updated": False, "reason": "low_quality_answer"}

    block_time_sensitive = bool(metadata.get("block_time_sensitive", True))
    question_is_time_sensitive = _is_time_sensitive(question_text)
    answer_is_time_sensitive = _is_time_sensitive(answer_text)
    time_sensitive = question_is_time_sensitive or answer_is_time_sensitive
    if block_time_sensitive and time_sensitive:
        return {"updated": False, "reason": "time_sensitive_blocked"}

    require_retrieval = bool(metadata.get("require_retrieval", False))
    retrieval_count = _safe_int(metadata.get("retrieval_count"), 0, 0, 1000)
    if require_retrieval and retrieval_count <= 0:
        return {"updated": False, "reason": "no_retrieval_context"}

    min_retrieval_score = _safe_float(
        metadata.get("min_retrieval_score"),
        DEFAULT_MIN_RETRIEVAL_SCORE,
        0.0,
        1.0,
    )
    retrieval_top_score = _safe_float(metadata.get("retrieval_top_score"), 0.0, 0.0, 1.0)
    if require_retrieval and retrieval_count > 0 and retrieval_top_score < min_retrieval_score:
        return {
            "updated": False,
            "reason": "retrieval_score_too_low",
            "retrieval_top_score": retrieval_top_score,
            "min_retrieval_score": min_retrieval_score,
        }

    ttl_seconds = _compute_ttl_seconds(
        time_sensitive=time_sensitive,
        max_age_days=metadata.get("max_age_days"),
        time_sensitive_ttl_hours=metadata.get("time_sensitive_ttl_hours"),
    )

    query_vec = _question_vector(question_text)
    best_match = None
    best_score = SIM_THRESHOLD
    with _LOCK:
        existing_questions = list(faq_cache.keys())
    for cached_question in existing_questions:
        score = float(util.cos_sim(query_vec, _question_vector(cached_question)).item())
        if score > best_score:
            best_score = score
            best_match = cached_question

    source = str(metadata.get("source") or "auto").strip().lower()
    if not source:
        source = "auto"

    if best_match:
        with _LOCK:
            current_entry = faq_cache.get(best_match, {})
            current_answer = _normalize_text(current_entry.get("answer"))
            hit_count = int(current_entry.get("count", 0))

        if current_answer and current_answer != answer_text:
            answer_similarity = _answer_similarity(current_answer, answer_text)
            if hit_count >= PROTECTED_HIT_COUNT and answer_similarity < ANSWER_CONFLICT_SIM_THRESHOLD:
                return {
                    "updated": False,
                    "reason": "conflict_with_verified_answer",
                    "matched_question": best_match,
                    "answer_similarity": round(answer_similarity, 4),
                }

        with _LOCK:
            entry = faq_cache.get(best_match, {})
            entry["answer"] = answer_text
            entry["last_updated"] = now_iso
            entry["learned"] = True
            entry["time_sensitive"] = time_sensitive
            entry["ttl_seconds"] = ttl_seconds
            entry["source"] = source
            entry["min_answer_chars"] = min_answer_chars
            entry["learned_count"] = int(entry.get("learned_count", 0)) + 1
            entry["retrieval_top_score"] = retrieval_top_score
            faq_cache[best_match] = entry
            save_faq_cache()

        return {
            "updated": True,
            "action": "updated_existing",
            "matched_question": best_match,
            "similarity": round(best_score, 4),
            "time_sensitive": time_sensitive,
        }

    with _LOCK:
        if len(faq_cache) >= MAX_FAQ:
            sorted_faq = sorted(
                faq_cache.items(),
                key=lambda item: (
                    int(item[1].get("count", 0)) if isinstance(item[1], dict) else 0,
                    str(item[1].get("last_updated", "")) if isinstance(item[1], dict) else "",
                ),
            )
            oldest_question = sorted_faq[0][0]
            del faq_cache[oldest_question]
            _question_vec_cache.pop(oldest_question, None)

        faq_cache[question_text] = {
            "answer": answer_text,
            "count": 1,
            "last_updated": now_iso,
            "learned": True,
            "learned_count": 1,
            "time_sensitive": time_sensitive,
            "ttl_seconds": ttl_seconds,
            "source": source,
            "min_answer_chars": min_answer_chars,
            "retrieval_top_score": retrieval_top_score,
        }
        save_faq_cache()

    return {
        "updated": True,
        "action": "created",
        "matched_question": question_text,
        "similarity": 1.0,
        "time_sensitive": time_sensitive,
    }


def list_faq_entries(
    limit: int = 300,
    query: str = "",
    include_expired: bool = False,
) -> Dict[str, Any]:
    now_utc = _now_utc()
    query_text = _normalize_text(query).lower()
    capped = max(1, min(2000, int(limit)))

    with _LOCK:
        rows = []
        for question, entry in faq_cache.items():
            if not isinstance(entry, dict):
                continue
            answer = str(entry.get("answer") or "").strip()
            if not answer:
                continue

            answer_norm = _normalize_text(answer)
            expired = _is_entry_expired(entry, now_utc, question_text=question)
            time_sensitive = bool(entry.get("time_sensitive", _is_time_sensitive(question)))
            ttl_seconds = _entry_ttl_seconds(entry, question_text=question)

            if expired and not include_expired:
                continue
            if query_text:
                hay_q = question.lower()
                hay_a = answer_norm.lower()
                if query_text not in hay_q and query_text not in hay_a:
                    continue

            preview = answer_norm if len(answer_norm) <= 220 else f"{answer_norm[:220]}...[{len(answer_norm)-220} more]"
            rows.append(
                {
                    "question": question,
                    "answer_preview": preview,
                    "count": int(entry.get("count", 0)),
                    "learned": bool(entry.get("learned", False)),
                    "learned_count": int(entry.get("learned_count", 0)),
                    "source": str(entry.get("source") or ""),
                    "time_sensitive": time_sensitive,
                    "ttl_seconds": int(ttl_seconds),
                    "expired": bool(expired),
                    "last_updated": str(entry.get("last_updated") or ""),
                    "last_hit_at": str(entry.get("last_hit_at") or ""),
                }
            )

    rows.sort(
        key=lambda row: (
            1 if row.get("expired") else 0,
            -int(row.get("count", 0)),
            str(row.get("last_updated") or ""),
        )
    )

    total = len(rows)
    result = rows[:capped]
    return {
        "total": total,
        "items": result,
        "query": query_text,
        "include_expired": bool(include_expired),
    }


def get_faq_entry(question: str) -> Optional[Dict[str, Any]]:
    target = _normalize_text(question)
    if not target:
        return None

    with _LOCK:
        key = target if target in faq_cache else None
        if key is None:
            for candidate in faq_cache.keys():
                if _normalize_text(candidate) == target:
                    key = candidate
                    break
        if key is None:
            return None
        entry = faq_cache.get(key)
        if not isinstance(entry, dict):
            return None

        now_utc = _now_utc()
        time_sensitive = bool(entry.get("time_sensitive", _is_time_sensitive(key)))
        ttl_seconds = _entry_ttl_seconds(entry, question_text=key)
        expired = _is_entry_expired(entry, now_utc, question_text=key)
        return {
            "question": key,
            "answer": str(entry.get("answer") or ""),
            "count": int(entry.get("count", 0)),
            "learned": bool(entry.get("learned", False)),
            "learned_count": int(entry.get("learned_count", 0)),
            "source": str(entry.get("source") or ""),
            "time_sensitive": time_sensitive,
            "ttl_seconds": int(ttl_seconds),
            "expired": bool(expired),
            "last_updated": str(entry.get("last_updated") or ""),
            "last_hit_at": str(entry.get("last_hit_at") or ""),
            "metadata": {
                k: v
                for k, v in entry.items()
                if k
                not in {
                    "answer",
                    "count",
                    "learned",
                    "learned_count",
                    "source",
                    "time_sensitive",
                    "ttl_seconds",
                    "last_updated",
                    "last_hit_at",
                }
            },
        }


def save_faq_entry(
    *,
    question: str,
    answer: str,
    original_question: Optional[str] = None,
    count: Optional[Any] = None,
    time_sensitive: Optional[bool] = None,
    ttl_seconds: Optional[Any] = None,
    source: str = "dev-ui",
) -> Dict[str, Any]:
    question_text = _normalize_text(question)
    answer_text = str(answer or "").strip()
    if not question_text or not answer_text:
        raise ValueError("Question and answer are required.")

    original_text = _normalize_text(original_question)
    count_value = _safe_int(count, 1, 0, 1_000_000) if count is not None else None
    source_value = _normalize_text(source or "dev-ui").lower() or "dev-ui"
    now_iso = _now_utc().isoformat()

    with _LOCK:
        existing = {}
        if original_text and original_text in faq_cache:
            existing = dict(faq_cache.get(original_text) or {})
        elif question_text in faq_cache:
            existing = dict(faq_cache.get(question_text) or {})

        if original_text and original_text != question_text and original_text in faq_cache:
            del faq_cache[original_text]
            _question_vec_cache.pop(original_text, None)

        inferred_time_sensitive = _is_time_sensitive(question_text) or _is_time_sensitive(answer_text)
        time_sensitive_value = (
            bool(time_sensitive)
            if time_sensitive is not None
            else bool(existing.get("time_sensitive", inferred_time_sensitive))
        )

        if ttl_seconds is None:
            ttl_value = _safe_int(
                existing.get("ttl_seconds"),
                _compute_ttl_seconds(time_sensitive=time_sensitive_value),
                60,
                365 * 86400,
            )
        else:
            ttl_value = _safe_int(ttl_seconds, _compute_ttl_seconds(time_sensitive=time_sensitive_value), 60, 365 * 86400)

        entry = dict(existing)
        entry["answer"] = answer_text
        entry["count"] = int(count_value if count_value is not None else int(existing.get("count", 1) or 1))
        entry["learned"] = bool(existing.get("learned", True))
        entry["learned_count"] = int(existing.get("learned_count", 0))
        entry["time_sensitive"] = bool(time_sensitive_value)
        entry["ttl_seconds"] = int(ttl_value)
        entry["source"] = source_value
        entry["last_updated"] = now_iso

        faq_cache[question_text] = entry
        _question_vec_cache.pop(question_text, None)
        save_faq_cache()

    payload = get_faq_entry(question_text)
    if not payload:
        raise ValueError("Unable to save FAQ entry.")
    payload["saved"] = True
    return payload


def delete_faq_entry(question: str) -> Dict[str, Any]:
    target = _normalize_text(question)
    if not target:
        raise ValueError("Question is required.")

    with _LOCK:
        key = target if target in faq_cache else None
        if key is None:
            for candidate in faq_cache.keys():
                if _normalize_text(candidate) == target:
                    key = candidate
                    break
        if key is None:
            raise ValueError(f"FAQ entry not found: {target}")

        del faq_cache[key]
        _question_vec_cache.pop(key, None)
        save_faq_cache()
        return {"deleted": True, "question": key}


def purge_expired_faq_entries() -> Dict[str, Any]:
    with _LOCK:
        removed = _cleanup_cache_locked(_now_utc())
        if removed:
            save_faq_cache()
    return {"removed": int(removed)}


def get_faq_analytics() -> Dict[str, Any]:
    now_utc = _now_utc()
    with _LOCK:
        total = len(faq_cache)
        learned_count = sum(
            1 for entry in faq_cache.values() if isinstance(entry, dict) and bool(entry.get("learned"))
        )
        expired_count = sum(
            1
            for question, entry in faq_cache.items()
            if isinstance(entry, dict) and _is_entry_expired(entry, now_utc, question_text=question)
        )
        time_sensitive_count = sum(
            1
            for question, entry in faq_cache.items()
            if isinstance(entry, dict) and bool(entry.get("time_sensitive", _is_time_sensitive(question)))
        )
        top_questions = sorted(
            faq_cache.items(),
            key=lambda item: int(item[1].get("count", 0)) if isinstance(item[1], dict) else 0,
            reverse=True,
        )[:10]

    return {
        "total_knowledge_base": total,
        "auto_learned_count": learned_count,
        "expired_entries": expired_count,
        "time_sensitive_entries": time_sensitive_count,
        "top_faqs": [
            {
                "question": question,
                "hits": int(payload.get("count", 0)) if isinstance(payload, dict) else 0,
            }
            for question, payload in top_questions
        ],
    }
