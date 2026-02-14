import copy
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


MAX_TRACES = 300
MAX_STRING_LEN = 4000
MAX_LIST_ITEMS = 120
MAX_DICT_ITEMS = 160

_lock = threading.Lock()
_trace_ids: deque[str] = deque()
_traces: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_value(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "<trimmed:depth>"

    if isinstance(value, str):
        if len(value) <= MAX_STRING_LEN:
            return value
        return f"{value[:MAX_STRING_LEN]}...[trimmed {len(value) - MAX_STRING_LEN} chars]"

    if isinstance(value, list):
        items = value[:MAX_LIST_ITEMS]
        out = [_trim_value(item, depth + 1) for item in items]
        if len(value) > MAX_LIST_ITEMS:
            out.append(f"<trimmed:{len(value) - MAX_LIST_ITEMS} more>")
        return out

    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= MAX_DICT_ITEMS:
                out["__trimmed_items__"] = len(value) - MAX_DICT_ITEMS
                break
            out[str(key)] = _trim_value(item, depth + 1)
        return out

    return value


def _summary(trace: Dict[str, Any]) -> Dict[str, Any]:
    steps = trace.get("steps") or []
    return {
        "trace_id": trace.get("trace_id"),
        "session_id": trace.get("session_id"),
        "status": trace.get("status"),
        "source": trace.get("source"),
        "started_at": trace.get("started_at"),
        "ended_at": trace.get("ended_at"),
        "latency_ms": trace.get("latency_ms"),
        "step_count": len(steps),
        "message_preview": (trace.get("message") or "")[:160],
    }


def record_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    trace_id = str(trace.get("trace_id") or uuid.uuid4().hex)
    entry = _trim_value(copy.deepcopy(trace))
    if not isinstance(entry, dict):
        entry = {}

    entry["trace_id"] = trace_id
    entry.setdefault("started_at", _now_iso())
    entry.setdefault("ended_at", _now_iso())
    entry.setdefault("status", "ok")
    entry.setdefault("steps", [])

    with _lock:
        if trace_id in _traces:
            try:
                _trace_ids.remove(trace_id)
            except ValueError:
                pass

        _trace_ids.append(trace_id)
        _traces[trace_id] = entry

        while len(_trace_ids) > MAX_TRACES:
            old_id = _trace_ids.popleft()
            _traces.pop(old_id, None)

        return _summary(entry)


def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    trace_key = str(trace_id or "").strip()
    if not trace_key:
        return None
    with _lock:
        entry = _traces.get(trace_key)
        return copy.deepcopy(entry) if entry else None


def list_traces(
    limit: int = 60,
    session_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    capped = max(1, min(200, int(limit)))
    session_filter = str(session_id or "").strip()
    status_filter = str(status or "").strip().lower()

    out: List[Dict[str, Any]] = []
    with _lock:
        for trace_id in reversed(_trace_ids):
            entry = _traces.get(trace_id)
            if not entry:
                continue
            if session_filter and str(entry.get("session_id") or "") != session_filter:
                continue
            if status_filter and str(entry.get("status") or "").lower() != status_filter:
                continue
            out.append(_summary(entry))
            if len(out) >= capped:
                break
    return out
