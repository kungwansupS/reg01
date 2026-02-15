"""
Tier 2: RAG FAQ Cache — Exact-Match + Daily Refresh
────────────────────────────────────────────────────
Cached Q&A from RAG retrieval pipeline.

Key design decisions:
  1. EXACT string match only (after whitespace normalization).
     "เปิดเทอมวันไหน" ≠ "เปิดเทอมวันไหนครับ"
  2. No SentenceTransformer — zero model loading overhead.
  3. TTL = 24 hours default. Daily refresh re-validates all entries.
  4. Low-quality answers are never cached.
  5. Backward-compatible with all admin API endpoints.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_FILE = os.path.join(BASE_DIR, "cache/faq_cache.json")

MAX_FAQ = 500
DEFAULT_TTL_SECONDS = 86400  # 24 hours
DEFAULT_MIN_ANSWER_CHARS = 30

LOW_QUALITY_PATTERNS = [
    re.compile(r"ขออภัย.*(ขัดข้อง|ชั่วคราว|ไม่สามารถ)", re.IGNORECASE),
    re.compile(r"ระบบ.*ขัดข้อง", re.IGNORECASE),
    re.compile(r"ไม่พบข้อมูล", re.IGNORECASE),
    re.compile(r"ไม่มีข้อมูล", re.IGNORECASE),
    re.compile(r"ไม่แน่ใจ|ไม่ทราบ", re.IGNORECASE),
    re.compile(r"ข้อมูลส่วนนี้ไม่มีระบุ", re.IGNORECASE),
    re.compile(r"พี่ไม่มีข้อมูล", re.IGNORECASE),
    re.compile(r"\berror\b|\bexception\b|\btimeout\b", re.IGNORECASE),
    re.compile(r"\bsorry\b|\btemporar(y|ily)\b|\bunknown\b", re.IGNORECASE),
]

_LOCK = RLock()

# ─── Helpers ──────────────────────────────────────────────────────

def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: Any) -> str:
    """Collapse whitespace only — NO lowercasing, NO stemming."""
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


def _is_low_quality_answer(answer: str, min_chars: int = DEFAULT_MIN_ANSWER_CHARS) -> bool:
    text = _normalize_text(answer)
    if len(text) < min_chars:
        return True
    if text.count("?") >= 8:
        return True
    return any(p.search(text) for p in LOW_QUALITY_PATTERNS)


def _is_entry_expired(entry: Dict[str, Any], now_utc: datetime) -> bool:
    updated_at = _parse_iso_to_utc(entry.get("last_validated") or entry.get("last_updated"))
    if updated_at is None:
        return True
    ttl = _safe_int(entry.get("ttl_seconds"), DEFAULT_TTL_SECONDS, 60, 365 * 86400)
    return (now_utc - updated_at).total_seconds() > ttl


# ─── Cache I/O ────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            return loaded if isinstance(loaded, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


faq_cache: Dict[str, Any] = _load_cache()


def save_faq_cache() -> None:
    with _LOCK:
        try:
            os.makedirs(os.path.dirname(FAQ_FILE), exist_ok=True)
            with open(FAQ_FILE, "w", encoding="utf-8") as f:
                json.dump(faq_cache, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("Save FAQ Error: %s", exc, exc_info=True)


def _cleanup_cache_locked(now_utc: Optional[datetime] = None) -> int:
    now_utc = now_utc or _now_utc()
    removed = 0
    for question, entry in list(faq_cache.items()):
        if not isinstance(entry, dict):
            del faq_cache[question]
            removed += 1
            continue
        if not _normalize_text(entry.get("answer")):
            del faq_cache[question]
            removed += 1
            continue
        if _is_low_quality_answer(str(entry.get("answer", ""))):
            del faq_cache[question]
            removed += 1
            continue
        if _is_entry_expired(entry, now_utc):
            del faq_cache[question]
            removed += 1
    return removed


# ─── Core API: get / update ───────────────────────────────────────

def get_faq_answer(
    question: str,
    similarity_threshold: Optional[float] = None,  # kept for API compat, ignored
    include_meta: bool = False,
    allow_time_sensitive: bool = True,  # changed default: allow all
    max_age_days: Optional[Any] = None,  # kept for API compat
):
    """
    Exact-match FAQ lookup.
    Returns cached answer ONLY if the normalized question matches exactly.
    """
    question_text = _normalize_text(question)
    if not question_text:
        return None

    now_utc = _now_utc()

    with _LOCK:
        if not faq_cache:
            return None
        entry = faq_cache.get(question_text)
        if not isinstance(entry, dict):
            return None
        if _is_entry_expired(entry, now_utc):
            return None

        answer = str(entry.get("answer") or "").strip()
        if not answer:
            return None

        # Update hit stats
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_hit_at"] = now_utc.isoformat()
        save_faq_cache()

    logger.info("[FAQ HIT] exact match: '%s' (hits=%d)", question_text[:60], entry.get("count", 0))

    if include_meta:
        return {
            "answer": answer,
            "question": question_text,
            "score": 1.0,  # exact match = perfect score
            "time_sensitive": False,
            "last_updated": entry.get("last_updated"),
            "last_validated": entry.get("last_validated"),
            "ttl_seconds": _safe_int(entry.get("ttl_seconds"), DEFAULT_TTL_SECONDS, 60, 365 * 86400),
        }
    return answer


def update_faq(question: str, answer: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Auto-learn: cache a RAG answer for exact-match future lookups.
    Only caches high-quality answers from successful RAG retrievals.
    """
    metadata = metadata or {}
    question_text = _normalize_text(question)
    answer_text = _normalize_text(answer)
    now_iso = _now_utc().isoformat()

    if not question_text or not answer_text:
        return {"updated": False, "reason": "empty_question_or_answer"}

    min_answer_chars = _safe_int(metadata.get("min_answer_chars"), DEFAULT_MIN_ANSWER_CHARS, 10, 2000)
    if _is_low_quality_answer(answer_text, min_chars=min_answer_chars):
        return {"updated": False, "reason": "low_quality_answer"}

    # Require RAG retrieval context
    require_retrieval = bool(metadata.get("require_retrieval", False))
    retrieval_count = _safe_int(metadata.get("retrieval_count"), 0, 0, 1000)
    if require_retrieval and retrieval_count <= 0:
        return {"updated": False, "reason": "no_retrieval_context"}

    retrieval_top_score = float(metadata.get("retrieval_top_score", 0.0))
    min_retrieval_score = float(metadata.get("min_retrieval_score", 0.35))
    if require_retrieval and retrieval_count > 0 and retrieval_top_score < min_retrieval_score:
        return {
            "updated": False,
            "reason": "retrieval_score_too_low",
            "retrieval_top_score": retrieval_top_score,
            "min_retrieval_score": min_retrieval_score,
        }

    source = str(metadata.get("source") or "rag").strip().lower() or "rag"
    ttl = _safe_int(metadata.get("ttl_seconds"), DEFAULT_TTL_SECONDS, 60, 365 * 86400)

    with _LOCK:
        # Exact match update or create
        existing = faq_cache.get(question_text, {})
        if isinstance(existing, dict) and existing:
            # Update existing entry
            existing["answer"] = answer_text
            existing["last_updated"] = now_iso
            existing["last_validated"] = now_iso
            existing["learned_count"] = int(existing.get("learned_count", 0)) + 1
            existing["retrieval_top_score"] = retrieval_top_score
            existing["source"] = source
            existing["ttl_seconds"] = ttl
            faq_cache[question_text] = existing
        else:
            # Evict oldest if at capacity
            if len(faq_cache) >= MAX_FAQ:
                sorted_faq = sorted(
                    faq_cache.items(),
                    key=lambda item: (
                        int(item[1].get("count", 0)) if isinstance(item[1], dict) else 0,
                        str(item[1].get("last_updated", "")) if isinstance(item[1], dict) else "",
                    ),
                )
                del faq_cache[sorted_faq[0][0]]

            faq_cache[question_text] = {
                "answer": answer_text,
                "count": 0,
                "last_updated": now_iso,
                "last_validated": now_iso,
                "learned": True,
                "learned_count": 1,
                "source": source,
                "ttl_seconds": ttl,
                "retrieval_top_score": retrieval_top_score,
            }

        save_faq_cache()

    return {
        "updated": True,
        "action": "updated_existing" if existing else "created",
        "matched_question": question_text,
        "similarity": 1.0,
    }


# ─── Daily Refresh Support ────────────────────────────────────────

def get_entries_needing_refresh(max_age_hours: int = 24) -> List[str]:
    """Return list of questions whose entries are older than max_age_hours."""
    now_utc = _now_utc()
    max_age_sec = max_age_hours * 3600
    stale = []
    with _LOCK:
        for question, entry in faq_cache.items():
            if not isinstance(entry, dict):
                continue
            validated_at = _parse_iso_to_utc(entry.get("last_validated") or entry.get("last_updated"))
            if validated_at is None or (now_utc - validated_at).total_seconds() > max_age_sec:
                stale.append(question)
    return stale


def mark_validated(question: str, new_answer: Optional[str] = None) -> bool:
    """
    Mark an FAQ entry as validated (refreshed).
    If new_answer is provided and differs, update it.
    Returns True if entry was found and updated.
    """
    question_text = _normalize_text(question)
    now_iso = _now_utc().isoformat()
    with _LOCK:
        entry = faq_cache.get(question_text)
        if not isinstance(entry, dict):
            return False
        entry["last_validated"] = now_iso
        if new_answer is not None:
            new_text = _normalize_text(new_answer)
            if new_text and not _is_low_quality_answer(new_text):
                old_answer = _normalize_text(entry.get("answer", ""))
                if new_text != old_answer:
                    entry["answer"] = new_text
                    entry["last_updated"] = now_iso
                    logger.info("[FAQ REFRESH] Answer updated for: '%s'", question_text[:60])
        faq_cache[question_text] = entry
        save_faq_cache()
    return True


def invalidate_entry(question: str) -> bool:
    """Remove an FAQ entry that failed refresh validation."""
    question_text = _normalize_text(question)
    with _LOCK:
        if question_text in faq_cache:
            del faq_cache[question_text]
            save_faq_cache()
            logger.info("[FAQ INVALIDATE] Removed stale entry: '%s'", question_text[:60])
            return True
    return False


# ─── Admin API (backward-compatible) ──────────────────────────────

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
            expired = _is_entry_expired(entry, now_utc)

            if expired and not include_expired:
                continue
            if query_text:
                if query_text not in question.lower() and query_text not in answer_norm.lower():
                    continue

            preview = answer_norm if len(answer_norm) <= 220 else f"{answer_norm[:220]}...[{len(answer_norm)-220} more]"
            rows.append({
                "question": question,
                "answer_preview": preview,
                "count": int(entry.get("count", 0)),
                "learned": bool(entry.get("learned", False)),
                "learned_count": int(entry.get("learned_count", 0)),
                "source": str(entry.get("source") or ""),
                "time_sensitive": False,
                "ttl_seconds": _safe_int(entry.get("ttl_seconds"), DEFAULT_TTL_SECONDS, 60, 365 * 86400),
                "expired": bool(expired),
                "last_updated": str(entry.get("last_updated") or ""),
                "last_validated": str(entry.get("last_validated") or ""),
                "last_hit_at": str(entry.get("last_hit_at") or ""),
            })

    rows.sort(key=lambda r: (1 if r.get("expired") else 0, -int(r.get("count", 0))))
    return {
        "total": len(rows),
        "items": rows[:capped],
        "query": query_text,
        "include_expired": bool(include_expired),
    }


def get_faq_entry(question: str) -> Optional[Dict[str, Any]]:
    target = _normalize_text(question)
    if not target:
        return None

    with _LOCK:
        entry = faq_cache.get(target)
        if not isinstance(entry, dict):
            return None

        now_utc = _now_utc()
        expired = _is_entry_expired(entry, now_utc)
        return {
            "question": target,
            "answer": str(entry.get("answer") or ""),
            "count": int(entry.get("count", 0)),
            "learned": bool(entry.get("learned", False)),
            "learned_count": int(entry.get("learned_count", 0)),
            "source": str(entry.get("source") or ""),
            "time_sensitive": False,
            "ttl_seconds": _safe_int(entry.get("ttl_seconds"), DEFAULT_TTL_SECONDS, 60, 365 * 86400),
            "expired": bool(expired),
            "last_updated": str(entry.get("last_updated") or ""),
            "last_validated": str(entry.get("last_validated") or ""),
            "last_hit_at": str(entry.get("last_hit_at") or ""),
            "metadata": {
                k: v for k, v in entry.items()
                if k not in {
                    "answer", "count", "learned", "learned_count", "source",
                    "time_sensitive", "ttl_seconds", "last_updated",
                    "last_validated", "last_hit_at",
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

        ttl_value = _safe_int(ttl_seconds, DEFAULT_TTL_SECONDS, 60, 365 * 86400)
        entry = dict(existing)
        entry["answer"] = answer_text
        entry["count"] = int(count_value if count_value is not None else int(existing.get("count", 1) or 1))
        entry["learned"] = bool(existing.get("learned", True))
        entry["learned_count"] = int(existing.get("learned_count", 0))
        entry["ttl_seconds"] = int(ttl_value)
        entry["source"] = source_value
        entry["last_updated"] = now_iso
        entry["last_validated"] = now_iso

        faq_cache[question_text] = entry
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
        if target not in faq_cache:
            raise ValueError(f"FAQ entry not found: {target}")
        del faq_cache[target]
        save_faq_cache()
        return {"deleted": True, "question": target}


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
            1 for e in faq_cache.values() if isinstance(e, dict) and bool(e.get("learned"))
        )
        expired_count = sum(
            1 for e in faq_cache.values() if isinstance(e, dict) and _is_entry_expired(e, now_utc)
        )
        stale_count = len(get_entries_needing_refresh())
        top_questions = sorted(
            faq_cache.items(),
            key=lambda item: int(item[1].get("count", 0)) if isinstance(item[1], dict) else 0,
            reverse=True,
        )[:10]

    return {
        "total_knowledge_base": total,
        "auto_learned_count": learned_count,
        "expired_entries": expired_count,
        "stale_entries_needing_refresh": stale_count,
        "time_sensitive_entries": 0,
        "top_faqs": [
            {"question": q, "hits": int(p.get("count", 0)) if isinstance(p, dict) else 0}
            for q, p in top_questions
        ],
    }
