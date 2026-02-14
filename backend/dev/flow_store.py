import copy
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FLOW_CONFIG_FILE = os.path.join(BASE_DIR, "flow_config.json")
FLOW_HISTORY_FILE = os.path.join(BASE_DIR, "flow_config_history.json")
FLOW_HISTORY_MAX_ITEMS = 240

DEFAULT_FLOW_CONFIG: Dict[str, Any] = {
    "rag": {
        "mode": "keyword",  # keyword | always | never
        "top_k": 5,
        "use_hybrid": True,
        "use_llm_rerank": True,
        "use_intent_analysis": True,
    },
    "memory": {
        "enable_summary": True,
        "recent_messages": 10,
    },
    "pose": {
        "enabled": True,
    },
    "faq": {
        "auto_learn": True,
        "lookup_enabled": True,
        "block_time_sensitive": True,
        "max_age_days": 45,
        "time_sensitive_ttl_hours": 6,
        "min_answer_chars": 30,
        "min_retrieval_score": 0.35,
        "similarity_threshold": 0.9,
    },
    "prompt": {
        "extra_context_instruction": "",
    },
}

_lock = threading.Lock()
_cache_state: Optional[Dict[str, Any]] = None
_cache_mtime: Optional[float] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sanitize_config(raw_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = _deep_merge(DEFAULT_FLOW_CONFIG, raw_config or {})

    rag = cfg["rag"]
    rag_mode = str(rag.get("mode", "keyword")).lower().strip()
    if rag_mode not in {"keyword", "always", "never"}:
        rag_mode = "keyword"
    rag["mode"] = rag_mode
    rag["top_k"] = max(1, min(20, int(rag.get("top_k", 5))))
    rag["use_hybrid"] = bool(rag.get("use_hybrid", True))
    rag["use_llm_rerank"] = bool(rag.get("use_llm_rerank", True))
    rag["use_intent_analysis"] = bool(rag.get("use_intent_analysis", True))

    memory = cfg["memory"]
    memory["enable_summary"] = bool(memory.get("enable_summary", True))
    memory["recent_messages"] = max(1, min(30, int(memory.get("recent_messages", 10))))

    pose = cfg["pose"]
    pose["enabled"] = bool(pose.get("enabled", True))

    faq = cfg["faq"]
    faq["auto_learn"] = bool(faq.get("auto_learn", True))
    faq["lookup_enabled"] = bool(faq.get("lookup_enabled", True))
    faq["block_time_sensitive"] = bool(faq.get("block_time_sensitive", True))
    faq["max_age_days"] = max(1, min(365, _safe_int(faq.get("max_age_days"), 45)))
    faq["time_sensitive_ttl_hours"] = max(1, min(168, _safe_int(faq.get("time_sensitive_ttl_hours"), 6)))
    faq["min_answer_chars"] = max(10, min(2000, _safe_int(faq.get("min_answer_chars"), 30)))
    faq["min_retrieval_score"] = max(0.0, min(1.0, _safe_float(faq.get("min_retrieval_score"), 0.35)))
    faq["similarity_threshold"] = max(0.5, min(0.99, _safe_float(faq.get("similarity_threshold"), 0.9)))

    prompt = cfg["prompt"]
    prompt["extra_context_instruction"] = str(
        prompt.get("extra_context_instruction", "")
    ).strip()

    return cfg


def _default_state() -> Dict[str, Any]:
    return {
        "revision": 1,
        "updated_at": _now_iso(),
        "updated_by": "system",
        "config": copy.deepcopy(DEFAULT_FLOW_CONFIG),
    }


def _write_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(FLOW_CONFIG_FILE), exist_ok=True)
    temp_file = f"{FLOW_CONFIG_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, FLOW_CONFIG_FILE)


def _snapshot_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "revision": int(state.get("revision", 0)),
        "updated_at": str(state.get("updated_at") or _now_iso()),
        "updated_by": str(state.get("updated_by") or "system"),
        "config": _sanitize_config(state.get("config") if isinstance(state.get("config"), dict) else {}),
    }


def _load_history_uncached() -> Dict[str, Any]:
    if not os.path.exists(FLOW_HISTORY_FILE):
        return {"items": []}
    try:
        with open(FLOW_HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"items": []}

    items = raw.get("items") if isinstance(raw, dict) else []
    if not isinstance(items, list):
        items = []

    clean: list[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        clean.append(_snapshot_from_state(item))
        if len(clean) >= FLOW_HISTORY_MAX_ITEMS:
            break
    return {"items": clean}


def _write_history(history: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(FLOW_HISTORY_FILE), exist_ok=True)
    temp_file = f"{FLOW_HISTORY_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, FLOW_HISTORY_FILE)


def _append_history_entry(state: Dict[str, Any]) -> None:
    snapshot = _snapshot_from_state(state)
    history = _load_history_uncached()
    items = history.get("items", [])
    if not isinstance(items, list):
        items = []

    items = [item for item in items if int(item.get("revision", -1)) != snapshot["revision"]]
    items.append(snapshot)
    items.sort(key=lambda item: int(item.get("revision", 0)))
    history["items"] = items[-FLOW_HISTORY_MAX_ITEMS:]
    _write_history(history)


def _load_state_uncached() -> Dict[str, Any]:
    if not os.path.exists(FLOW_CONFIG_FILE):
        state = _default_state()
        _write_state(state)
        _append_history_entry(state)
        return state

    try:
        with open(FLOW_CONFIG_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        state = _default_state()
        _write_state(state)
        _append_history_entry(state)
        return state

    if not isinstance(state, dict):
        state = _default_state()

    state.setdefault("revision", 1)
    state.setdefault("updated_at", _now_iso())
    state.setdefault("updated_by", "system")
    state["config"] = _sanitize_config(state.get("config", {}))
    return state


def get_flow_state() -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    with _lock:
        mtime = os.path.getmtime(FLOW_CONFIG_FILE) if os.path.exists(FLOW_CONFIG_FILE) else None
        if _cache_state is not None and _cache_mtime == mtime:
            return copy.deepcopy(_cache_state)

        state = _load_state_uncached()
        _cache_state = state
        _cache_mtime = os.path.getmtime(FLOW_CONFIG_FILE) if os.path.exists(FLOW_CONFIG_FILE) else None
        return copy.deepcopy(state)


def save_flow_config(raw_config: Dict[str, Any], updated_by: str = "dev") -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    with _lock:
        current = _load_state_uncached()
        new_state = {
            "revision": int(current.get("revision", 0)) + 1,
            "updated_at": _now_iso(),
            "updated_by": updated_by or "dev",
            "config": _sanitize_config(raw_config),
        }
        _write_state(new_state)
        _append_history_entry(new_state)
        _cache_state = new_state
        _cache_mtime = os.path.getmtime(FLOW_CONFIG_FILE) if os.path.exists(FLOW_CONFIG_FILE) else None
        return copy.deepcopy(new_state)


def get_effective_flow_config(override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    active = get_flow_state().get("config", {})
    if override:
        active = _deep_merge(active, override)
    return _sanitize_config(active)


def list_flow_history(limit: int = 40) -> Dict[str, Any]:
    capped = max(1, min(FLOW_HISTORY_MAX_ITEMS, int(limit)))
    with _lock:
        current = _load_state_uncached()
        history = _load_history_uncached()
        items = history.get("items", [])
        if not any(int(item.get("revision", -1)) == int(current.get("revision", -2)) for item in items):
            _append_history_entry(current)
            history = _load_history_uncached()
            items = history.get("items", [])
        sorted_items = sorted(items, key=lambda item: int(item.get("revision", 0)), reverse=True)
        return {
            "current_revision": int(current.get("revision", 0)),
            "items": copy.deepcopy(sorted_items[:capped]),
        }


def rollback_flow_revision(revision: int, updated_by: str = "dev-rollback") -> Dict[str, Any]:
    target = None
    target_revision = int(revision)
    with _lock:
        history = _load_history_uncached()
        for item in history.get("items", []):
            if int(item.get("revision", -1)) == target_revision:
                target = copy.deepcopy(item)
                break

    if not target:
        raise ValueError(f"Flow revision not found: {target_revision}")

    return save_flow_config(target.get("config", {}), updated_by=updated_by or "dev-rollback")
