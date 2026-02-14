import copy
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_HISTORY_FILE = os.path.join(BASE_DIR, "env_history.json")
ENV_HISTORY_MAX_ITEMS = 120

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    chars = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
    return "".join(chars)


def _default_state() -> Dict[str, Any]:
    return {"items": []}


def _read_state() -> Dict[str, Any]:
    if not os.path.exists(ENV_HISTORY_FILE):
        return _default_state()
    try:
        with open(ENV_HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default_state()

    items = raw.get("items") if isinstance(raw, dict) else []
    if not isinstance(items, list):
        items = []

    clean: list[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        snapshot_id = _normalize_id(item.get("id")) or f"env_{uuid.uuid4().hex[:10]}"
        content = str(item.get("content") or "")
        clean.append(
            {
                "id": snapshot_id,
                "updated_at": str(item.get("updated_at") or _now_iso()),
                "updated_by": str(item.get("updated_by") or "dev"),
                "size": len(content),
                "preview": content[:220],
                "content": content,
            }
        )
        if len(clean) >= ENV_HISTORY_MAX_ITEMS:
            break
    return {"items": clean}


def _write_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(ENV_HISTORY_FILE), exist_ok=True)
    temp_path = f"{ENV_HISTORY_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, ENV_HISTORY_FILE)


def save_env_snapshot(content: str, updated_by: str = "dev") -> Dict[str, Any]:
    normalized = str(content or "").replace("\r\n", "\n")
    item = {
        "id": f"env_{uuid.uuid4().hex[:12]}",
        "updated_at": _now_iso(),
        "updated_by": updated_by or "dev",
        "size": len(normalized),
        "preview": normalized[:220],
        "content": normalized,
    }

    with _lock:
        state = _read_state()
        items = state.get("items", [])
        if not isinstance(items, list):
            items = []
        items.append(item)
        items = sorted(items, key=lambda row: str(row.get("updated_at") or ""), reverse=True)
        state["items"] = items[:ENV_HISTORY_MAX_ITEMS]
        _write_state(state)
    return copy.deepcopy(item)


def list_env_history(limit: int = 40) -> Dict[str, Any]:
    capped = max(1, min(ENV_HISTORY_MAX_ITEMS, int(limit)))
    with _lock:
        state = _read_state()
        items = state.get("items", [])
        out = []
        for item in items[:capped]:
            out.append(
                {
                    "id": item.get("id"),
                    "updated_at": item.get("updated_at"),
                    "updated_by": item.get("updated_by"),
                    "size": int(item.get("size") or 0),
                    "preview": item.get("preview") or "",
                }
            )
        return {"items": out}


def get_env_snapshot(snapshot_id: str) -> Optional[Dict[str, Any]]:
    sid = _normalize_id(snapshot_id)
    if not sid:
        return None

    with _lock:
        state = _read_state()
        for item in state.get("items", []):
            if _normalize_id(item.get("id")) == sid:
                return copy.deepcopy(item)
    return None
