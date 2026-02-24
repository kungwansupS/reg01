import copy
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIO_FILE = os.path.join(BASE_DIR, "test_scenarios.json")
MAX_SCENARIOS = 200

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


def _normalize_id(value: Any, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    chars = []
    for char in raw:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
        elif char in {" ", "."}:
            chars.append("_")
    normalized = "".join(chars).strip("_")
    return normalized or fallback


def _sanitize_scenario(raw: Dict[str, Any]) -> Dict[str, Any]:
    scenario_id = _normalize_id(raw.get("id"), f"scenario_{uuid.uuid4().hex[:8]}")
    name = str(raw.get("name") or scenario_id).strip()[:120]
    description = str(raw.get("description") or "").strip()[:2000]
    message = str(raw.get("message") or "").strip()[:8000]
    config_override = raw.get("config_override") if isinstance(raw.get("config_override"), dict) else {}

    item = {
        "id": scenario_id,
        "name": name or scenario_id,
        "description": description,
        "message": message,
        "config_override": _deep_merge({}, config_override),
        "updated_at": str(raw.get("updated_at") or _now_iso()),
        "updated_by": str(raw.get("updated_by") or "dev"),
    }

    if raw.get("created_at"):
        item["created_at"] = str(raw.get("created_at"))

    for key in [
        "last_run_at",
        "last_trace_id",
        "last_latency_ms",
        "last_tokens_total",
        "last_output_preview",
    ]:
        if key in raw:
            item[key] = raw.get(key)

    if "created_at" not in item:
        item["created_at"] = item["updated_at"]

    return item


def _default_state() -> Dict[str, Any]:
    return {
        "revision": 1,
        "updated_at": _now_iso(),
        "updated_by": "system",
        "scenarios": [],
    }


def _write_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SCENARIO_FILE), exist_ok=True)
    temp_path = f"{SCENARIO_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, SCENARIO_FILE)


def _load_state_uncached() -> Dict[str, Any]:
    if not os.path.exists(SCENARIO_FILE):
        state = _default_state()
        _write_state(state)
        return state

    try:
        with open(SCENARIO_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        state = _default_state()
        _write_state(state)
        return state

    if not isinstance(state, dict):
        state = _default_state()

    state.setdefault("revision", 1)
    state.setdefault("updated_at", _now_iso())
    state.setdefault("updated_by", "system")

    raw_items = state.get("scenarios")
    if not isinstance(raw_items, list):
        raw_items = []

    clean_items: list[Dict[str, Any]] = []
    used_ids = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        scenario = _sanitize_scenario(raw)
        base_id = scenario["id"]
        if base_id in used_ids:
            suffix = 2
            while f"{base_id}_{suffix}" in used_ids:
                suffix += 1
            scenario["id"] = f"{base_id}_{suffix}"
        used_ids.add(scenario["id"])
        clean_items.append(scenario)
        if len(clean_items) >= MAX_SCENARIOS:
            break

    state["scenarios"] = clean_items
    return state


def get_scenario_state() -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    with _lock:
        mtime = os.path.getmtime(SCENARIO_FILE) if os.path.exists(SCENARIO_FILE) else None
        if _cache_state is not None and _cache_mtime == mtime:
            return copy.deepcopy(_cache_state)

        state = _load_state_uncached()
        _cache_state = state
        _cache_mtime = os.path.getmtime(SCENARIO_FILE) if os.path.exists(SCENARIO_FILE) else None
        return copy.deepcopy(state)


def list_scenarios(limit: int = 200) -> list[Dict[str, Any]]:
    state = get_scenario_state()
    capped = max(1, min(MAX_SCENARIOS, int(limit)))
    scenarios = state.get("scenarios", [])
    sorted_items = sorted(
        scenarios,
        key=lambda item: (str(item.get("updated_at") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    return copy.deepcopy(sorted_items[:capped])


def save_scenario(raw: Dict[str, Any], updated_by: str = "dev") -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    with _lock:
        state = _load_state_uncached()
        scenario = _sanitize_scenario(raw or {})
        scenario["updated_by"] = updated_by or "dev"
        scenario["updated_at"] = _now_iso()

        items = state.get("scenarios", [])
        index = next((idx for idx, item in enumerate(items) if item.get("id") == scenario["id"]), -1)
        if index >= 0:
            scenario["created_at"] = str(items[index].get("created_at") or scenario["updated_at"])
            for key in [
                "last_run_at",
                "last_trace_id",
                "last_latency_ms",
                "last_tokens_total",
                "last_output_preview",
            ]:
                if key in items[index] and key not in scenario:
                    scenario[key] = items[index].get(key)
            items[index] = scenario
        else:
            items.append(scenario)

        state["scenarios"] = items[:MAX_SCENARIOS]
        state["revision"] = int(state.get("revision", 0)) + 1
        state["updated_at"] = _now_iso()
        state["updated_by"] = updated_by or "dev"

        _write_state(state)
        _cache_state = state
        _cache_mtime = os.path.getmtime(SCENARIO_FILE) if os.path.exists(SCENARIO_FILE) else None
        return copy.deepcopy(scenario)


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    sid = _normalize_id(scenario_id, "")
    if not sid:
        return None
    state = get_scenario_state()
    for item in state.get("scenarios", []):
        if item.get("id") == sid:
            return copy.deepcopy(item)
    return None


def delete_scenario(scenario_id: str, updated_by: str = "dev") -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    sid = _normalize_id(scenario_id, "")
    if not sid:
        raise ValueError("Invalid scenario id")

    with _lock:
        state = _load_state_uncached()
        items = state.get("scenarios", [])
        next_items = [item for item in items if item.get("id") != sid]
        if len(next_items) == len(items):
            raise ValueError(f"Scenario not found: {sid}")

        state["scenarios"] = next_items
        state["revision"] = int(state.get("revision", 0)) + 1
        state["updated_at"] = _now_iso()
        state["updated_by"] = updated_by or "dev"
        _write_state(state)
        _cache_state = state
        _cache_mtime = os.path.getmtime(SCENARIO_FILE) if os.path.exists(SCENARIO_FILE) else None
        return {
            "status": "deleted",
            "scenario_id": sid,
            "revision": state["revision"],
            "updated_at": state["updated_at"],
        }


def save_scenario_run(
    scenario_id: str,
    trace_id: str,
    latency_ms: float,
    output_text: str,
    tokens_total: int,
    updated_by: str = "dev",
) -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    sid = _normalize_id(scenario_id, "")
    if not sid:
        raise ValueError("Invalid scenario id")

    with _lock:
        state = _load_state_uncached()
        items = state.get("scenarios", [])
        index = next((idx for idx, item in enumerate(items) if item.get("id") == sid), -1)
        if index < 0:
            raise ValueError(f"Scenario not found: {sid}")

        item = copy.deepcopy(items[index])
        item["last_run_at"] = _now_iso()
        item["last_trace_id"] = str(trace_id or "")
        item["last_latency_ms"] = round(float(latency_ms or 0), 2)
        item["last_tokens_total"] = int(tokens_total or 0)
        item["last_output_preview"] = str(output_text or "")[:600]
        item["updated_at"] = _now_iso()
        item["updated_by"] = updated_by or "dev"
        items[index] = item

        state["scenarios"] = items
        state["revision"] = int(state.get("revision", 0)) + 1
        state["updated_at"] = _now_iso()
        state["updated_by"] = updated_by or "dev"

        _write_state(state)
        _cache_state = state
        _cache_mtime = os.path.getmtime(SCENARIO_FILE) if os.path.exists(SCENARIO_FILE) else None
        return copy.deepcopy(item)
