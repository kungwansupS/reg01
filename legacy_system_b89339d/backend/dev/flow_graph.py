import copy
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dev.flow_store import get_effective_flow_config


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPH_MODEL_FILE = os.path.join(BASE_DIR, "flow_graph_model.json")
GRAPH_MODEL_HISTORY_FILE = os.path.join(BASE_DIR, "flow_graph_model_history.json")
GRAPH_MODEL_HISTORY_MAX_ITEMS = 240

DEFAULT_GRAPH_MODEL: Dict[str, Any] = {
    "meta": {
        "title": "REG-01 Runtime Flow",
        "description": "Editable runtime graph model for dev console",
    },
    "nodes": [
        {
            "id": "ingress",
            "title": "Ingress Router",
            "group": "io",
            "description": "Receive inbound message from web or webhook route.",
            "file_refs": [
                "backend/router/chat_router.py",
                "backend/router/webhook_router.py",
                "backend/main.py",
            ],
            "lane": 0,
            "order": 0,
            "enabled": True,
            "badges": ["web", "facebook"],
        },
        {
            "id": "stt",
            "title": "Speech-to-Text",
            "group": "io",
            "description": "Transcribe audio input before entering LLM pipeline.",
            "file_refs": [
                "backend/app/stt.py",
                "backend/router/chat_router.py",
            ],
            "lane": 1,
            "order": 0,
            "enabled": True,
            "badges": ["conditional: audio"],
        },
        {
            "id": "session",
            "title": "Session + Memory",
            "group": "memory",
            "description": "Load and persist conversation history and summary.",
            "file_refs": [
                "backend/memory/session.py",
                "backend/memory/session_db.py",
                "backend/memory/memory.py",
            ],
            "lane": 1,
            "order": 1,
            "enabled": True,
            "badges": ["summary=on", "recent=10"],
        },
        {
            "id": "prompt",
            "title": "Prompt Builder",
            "group": "prompt",
            "description": "Build prompt with context, summary, and recent history.",
            "file_refs": [
                "backend/app/utils/llm/llm.py",
                "backend/app/prompt/prompt.py",
                "backend/app/prompt/request_prompt.py",
            ],
            "lane": 2,
            "order": 1,
            "enabled": True,
            "badges": ["lang-detect"],
        },
        {
            "id": "llm_primary",
            "title": "LLM Call #1",
            "group": "llm",
            "description": "Initial response or route decision for RAG.",
            "file_refs": [
                "backend/app/utils/llm/llm.py",
                "backend/app/utils/llm/llm_model.py",
            ],
            "lane": 3,
            "order": 1,
            "enabled": True,
            "badges": ["primary"],
        },
        {
            "id": "rag_gate",
            "title": "RAG Decision Gate",
            "group": "routing",
            "description": "Route by rag.mode: keyword, always, never.",
            "file_refs": [
                "backend/app/utils/llm/llm.py",
                "backend/dev/flow_store.py",
            ],
            "lane": 4,
            "order": 1,
            "enabled": True,
            "badges": ["mode=keyword", "top_k=5"],
        },
        {
            "id": "retriever",
            "title": "Hybrid Retriever",
            "group": "retrieval",
            "description": "Search context from vector/BM25 with rerank options.",
            "file_refs": [
                "backend/retriever/context_selector.py",
                "backend/retriever/hybrid_retriever.py",
                "backend/app/utils/vector_manager.py",
            ],
            "lane": 5,
            "order": 0,
            "enabled": True,
            "badges": ["hybrid=on", "rerank=on", "intent=on"],
        },
        {
            "id": "llm_rag",
            "title": "LLM Call #2 (RAG)",
            "group": "llm",
            "description": "Create final answer from retrieved context.",
            "file_refs": ["backend/app/utils/llm/llm.py"],
            "lane": 6,
            "order": 0,
            "enabled": True,
            "badges": ["secondary"],
        },
        {
            "id": "faq_learn",
            "title": "FAQ Auto Learn",
            "group": "memory",
            "description": "Update FAQ cache automatically for qualified answers.",
            "file_refs": [
                "backend/memory/faq_cache.py",
                "backend/app/utils/llm/llm.py",
            ],
            "lane": 6,
            "order": 1,
            "enabled": True,
            "badges": ["auto_learn=on"],
        },
        {
            "id": "answer_post",
            "title": "Answer Post-Process",
            "group": "post",
            "description": "Merge direct answer path and RAG answer path.",
            "file_refs": [
                "backend/app/utils/llm/llm.py",
                "backend/router/chat_router.py",
                "backend/router/background_tasks.py",
            ],
            "lane": 6,
            "order": 2,
            "enabled": True,
            "badges": ["merge"],
        },
        {
            "id": "pose",
            "title": "Pose Suggestion",
            "group": "post",
            "description": "Infer animation pose from response text.",
            "file_refs": [
                "backend/app/utils/pose.py",
                "backend/router/chat_router.py",
            ],
            "lane": 7,
            "order": 1,
            "enabled": True,
            "badges": ["enabled=on"],
        },
        {
            "id": "output",
            "title": "Output Emit + TTS + Logs",
            "group": "io",
            "description": "Emit final result, stream TTS, and write audit logs.",
            "file_refs": [
                "backend/router/chat_router.py",
                "backend/main.py",
                "backend/app/tts.py",
            ],
            "lane": 8,
            "order": 1,
            "enabled": True,
            "badges": ["socketio", "tts", "audit"],
        },
    ],
    "edges": [
        {
            "id": "e_ingress_stt",
            "source": "ingress",
            "target": "stt",
            "label": "if audio",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_ingress_session",
            "source": "ingress",
            "target": "session",
            "label": "text/session_id",
            "enabled": True,
            "conditional": False,
        },
        {
            "id": "e_stt_session",
            "source": "stt",
            "target": "session",
            "label": "transcribed text",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_session_prompt",
            "source": "session",
            "target": "prompt",
            "label": "history + summary",
            "enabled": True,
            "conditional": False,
        },
        {
            "id": "e_prompt_llm1",
            "source": "prompt",
            "target": "llm_primary",
            "label": "full_prompt",
            "enabled": True,
            "conditional": False,
        },
        {
            "id": "e_llm1_gate",
            "source": "llm_primary",
            "target": "rag_gate",
            "label": "route decision",
            "enabled": True,
            "conditional": False,
        },
        {
            "id": "e_gate_retriever",
            "source": "rag_gate",
            "target": "retriever",
            "label": "enter RAG branch",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_gate_answer",
            "source": "rag_gate",
            "target": "answer_post",
            "label": "direct answer path",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_retriever_llm2",
            "source": "retriever",
            "target": "llm_rag",
            "label": "context prompt",
            "enabled": True,
            "conditional": False,
        },
        {
            "id": "e_llm2_answer",
            "source": "llm_rag",
            "target": "answer_post",
            "label": "rag answer",
            "enabled": True,
            "conditional": False,
        },
        {
            "id": "e_llm2_faq",
            "source": "llm_rag",
            "target": "faq_learn",
            "label": "auto learn",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_faq_answer",
            "source": "faq_learn",
            "target": "answer_post",
            "label": "cache update ack",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_answer_pose",
            "source": "answer_post",
            "target": "pose",
            "label": "pose inference",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_answer_output",
            "source": "answer_post",
            "target": "output",
            "label": "emit directly",
            "enabled": True,
            "conditional": True,
        },
        {
            "id": "e_pose_output",
            "source": "pose",
            "target": "output",
            "label": "emit + motion",
            "enabled": True,
            "conditional": False,
        },
    ],
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


def _to_str_list(value: Any, max_items: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        result.append(text)
        if len(result) >= max_items:
            break
    return result


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sanitize_node(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    fallback_id = f"node_{index + 1}"
    node_id = _normalize_id(raw.get("id"), fallback_id)
    lane = max(0, min(40, _int_or_default(raw.get("lane"), index)))
    order = max(0, min(40, _int_or_default(raw.get("order"), 0)))
    node: Dict[str, Any] = {
        "id": node_id,
        "title": str(raw.get("title") or node_id),
        "group": str(raw.get("group") or "node"),
        "description": str(raw.get("description") or ""),
        "file_refs": _to_str_list(raw.get("file_refs"), max_items=40),
        "lane": lane,
        "order": order,
        "enabled": bool(raw.get("enabled", True)),
        "badges": _to_str_list(raw.get("badges"), max_items=24),
    }
    if "x" in raw:
        try:
            node["x"] = float(raw.get("x"))
        except (TypeError, ValueError):
            pass
    if "y" in raw:
        try:
            node["y"] = float(raw.get("y"))
        except (TypeError, ValueError):
            pass
    return node


def _sanitize_edge(raw: Dict[str, Any], index: int, node_ids: set[str]) -> Optional[Dict[str, Any]]:
    fallback_id = f"edge_{index + 1}"
    edge_id = _normalize_id(raw.get("id"), fallback_id)
    source = _normalize_id(raw.get("source"), "")
    target = _normalize_id(raw.get("target"), "")

    if source not in node_ids or target not in node_ids:
        return None

    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "label": str(raw.get("label") or ""),
        "enabled": bool(raw.get("enabled", True)),
        "conditional": bool(raw.get("conditional", False)),
    }


def _sanitize_model(raw_model: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = _deep_merge(DEFAULT_GRAPH_MODEL, raw_model or {})
    meta = merged.get("meta", {})
    model = {
        "meta": {
            "title": str(meta.get("title") or "REG-01 Runtime Flow"),
            "description": str(meta.get("description") or ""),
        },
        "nodes": [],
        "edges": [],
    }

    used_node_ids: set[str] = set()
    raw_nodes = merged.get("nodes", [])
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raw_nodes = DEFAULT_GRAPH_MODEL["nodes"]

    for idx, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            continue
        node = _sanitize_node(raw, idx)
        base_id = node["id"]
        if base_id in used_node_ids:
            suffix = 2
            while f"{base_id}_{suffix}" in used_node_ids:
                suffix += 1
            node["id"] = f"{base_id}_{suffix}"
        used_node_ids.add(node["id"])
        model["nodes"].append(node)

    if not model["nodes"]:
        model["nodes"] = copy.deepcopy(DEFAULT_GRAPH_MODEL["nodes"])
        used_node_ids = {node["id"] for node in model["nodes"]}

    used_edge_ids: set[str] = set()
    raw_edges = merged.get("edges", [])
    if not isinstance(raw_edges, list):
        raw_edges = []

    for idx, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            continue
        edge = _sanitize_edge(raw, idx, used_node_ids)
        if not edge:
            continue
        base_id = edge["id"]
        if base_id in used_edge_ids:
            suffix = 2
            while f"{base_id}_{suffix}" in used_edge_ids:
                suffix += 1
            edge["id"] = f"{base_id}_{suffix}"
        used_edge_ids.add(edge["id"])
        model["edges"].append(edge)

    return model


def _default_state() -> Dict[str, Any]:
    return {
        "revision": 1,
        "updated_at": _now_iso(),
        "updated_by": "system",
        "model": copy.deepcopy(DEFAULT_GRAPH_MODEL),
    }


def _write_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(GRAPH_MODEL_FILE), exist_ok=True)
    temp_path = f"{GRAPH_MODEL_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, GRAPH_MODEL_FILE)


def _snapshot_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "revision": int(state.get("revision", 0)),
        "updated_at": str(state.get("updated_at") or _now_iso()),
        "updated_by": str(state.get("updated_by") or "system"),
        "model": _sanitize_model(state.get("model") if isinstance(state.get("model"), dict) else {}),
    }


def _load_history_uncached() -> Dict[str, Any]:
    if not os.path.exists(GRAPH_MODEL_HISTORY_FILE):
        return {"items": []}
    try:
        with open(GRAPH_MODEL_HISTORY_FILE, "r", encoding="utf-8") as f:
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
        if len(clean) >= GRAPH_MODEL_HISTORY_MAX_ITEMS:
            break
    return {"items": clean}


def _write_history(history: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(GRAPH_MODEL_HISTORY_FILE), exist_ok=True)
    temp_file = f"{GRAPH_MODEL_HISTORY_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, GRAPH_MODEL_HISTORY_FILE)


def _append_history_entry(state: Dict[str, Any]) -> None:
    snapshot = _snapshot_from_state(state)
    history = _load_history_uncached()
    items = history.get("items", [])
    if not isinstance(items, list):
        items = []

    items = [item for item in items if int(item.get("revision", -1)) != snapshot["revision"]]
    items.append(snapshot)
    items.sort(key=lambda item: int(item.get("revision", 0)))
    history["items"] = items[-GRAPH_MODEL_HISTORY_MAX_ITEMS:]
    _write_history(history)


def _load_state_uncached() -> Dict[str, Any]:
    if not os.path.exists(GRAPH_MODEL_FILE):
        state = _default_state()
        _write_state(state)
        _append_history_entry(state)
        return state

    try:
        with open(GRAPH_MODEL_FILE, "r", encoding="utf-8") as f:
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
    state["model"] = _sanitize_model(state.get("model", {}))
    return state


def get_graph_model_state() -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    with _lock:
        mtime = os.path.getmtime(GRAPH_MODEL_FILE) if os.path.exists(GRAPH_MODEL_FILE) else None
        if _cache_state is not None and _cache_mtime == mtime:
            return copy.deepcopy(_cache_state)

        state = _load_state_uncached()
        _cache_state = state
        _cache_mtime = os.path.getmtime(GRAPH_MODEL_FILE) if os.path.exists(GRAPH_MODEL_FILE) else None
        return copy.deepcopy(state)


def save_graph_model(raw_model: Dict[str, Any], updated_by: str = "dev") -> Dict[str, Any]:
    global _cache_state, _cache_mtime
    with _lock:
        current = _load_state_uncached()
        new_state = {
            "revision": int(current.get("revision", 0)) + 1,
            "updated_at": _now_iso(),
            "updated_by": updated_by or "dev",
            "model": _sanitize_model(raw_model),
        }
        _write_state(new_state)
        _append_history_entry(new_state)
        _cache_state = new_state
        _cache_mtime = os.path.getmtime(GRAPH_MODEL_FILE) if os.path.exists(GRAPH_MODEL_FILE) else None
        return copy.deepcopy(new_state)


def reset_graph_model(updated_by: str = "dev") -> Dict[str, Any]:
    return save_graph_model(copy.deepcopy(DEFAULT_GRAPH_MODEL), updated_by=updated_by or "dev")


def get_effective_graph_model(override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    active = get_graph_model_state().get("model", {})
    if override:
        active = _deep_merge(active, override)
    return _sanitize_model(active)


def _apply_runtime_rules(model: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    rag_mode = cfg["rag"]["mode"]
    rag_enabled = rag_mode != "never"
    pose_enabled = bool(cfg["pose"]["enabled"])
    faq_auto_learn = bool(cfg["faq"]["auto_learn"])
    summary_enabled = bool(cfg["memory"]["enable_summary"])

    nodes = copy.deepcopy(model.get("nodes", []))
    edges = copy.deepcopy(model.get("edges", []))

    node_by_id = {node["id"]: node for node in nodes}
    edge_by_id = {edge["id"]: edge for edge in edges}

    def patch_node(node_id: str, **kwargs: Any) -> None:
        node = node_by_id.get(node_id)
        if not node:
            return
        node.update(kwargs)

    def patch_edge(edge_id: str, **kwargs: Any) -> None:
        edge = edge_by_id.get(edge_id)
        if not edge:
            return
        edge.update(kwargs)

    patch_node(
        "session",
        badges=[
            f"summary={'on' if summary_enabled else 'off'}",
            f"recent={cfg['memory']['recent_messages']}",
        ],
    )
    patch_node("rag_gate", enabled=rag_enabled, badges=[f"mode={rag_mode}", f"top_k={cfg['rag']['top_k']}"])
    patch_node(
        "retriever",
        enabled=rag_enabled,
        badges=[
            f"hybrid={'on' if cfg['rag']['use_hybrid'] else 'off'}",
            f"rerank={'on' if cfg['rag']['use_llm_rerank'] else 'off'}",
            f"intent={'on' if cfg['rag']['use_intent_analysis'] else 'off'}",
        ],
    )
    patch_node("llm_rag", enabled=rag_enabled)
    patch_node("faq_learn", enabled=rag_enabled and faq_auto_learn, badges=[f"auto_learn={'on' if faq_auto_learn else 'off'}"])
    patch_node("pose", enabled=pose_enabled, badges=[f"enabled={'on' if pose_enabled else 'off'}"])

    patch_edge("e_gate_retriever", enabled=rag_enabled)
    patch_edge("e_retriever_llm2", enabled=rag_enabled)
    patch_edge("e_llm2_answer", enabled=rag_enabled)
    patch_edge("e_llm2_faq", enabled=rag_enabled and faq_auto_learn)
    patch_edge("e_faq_answer", enabled=rag_enabled and faq_auto_learn)
    patch_edge("e_answer_pose", enabled=pose_enabled)
    patch_edge("e_answer_output", enabled=not pose_enabled)
    patch_edge("e_pose_output", enabled=pose_enabled)

    meta = copy.deepcopy(model.get("meta", {}))
    meta["mode"] = rag_mode
    return {
        "meta": meta,
        "nodes": nodes,
        "edges": edges,
    }


def build_flow_graph(
    config_override: Optional[Dict[str, Any]] = None,
    model_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = get_effective_flow_config(config_override or {})
    model = get_effective_graph_model(model_override or {})
    runtime = _apply_runtime_rules(model, cfg)
    model_state = get_graph_model_state()

    return {
        "meta": runtime["meta"],
        "nodes": runtime["nodes"],
        "edges": runtime["edges"],
        "config_snapshot": cfg,
        "model_revision": model_state.get("revision"),
        "model_updated_at": model_state.get("updated_at"),
        "model_updated_by": model_state.get("updated_by"),
    }


def list_graph_model_history(limit: int = 40) -> Dict[str, Any]:
    capped = max(1, min(GRAPH_MODEL_HISTORY_MAX_ITEMS, int(limit)))
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


def rollback_graph_model_revision(revision: int, updated_by: str = "dev-rollback") -> Dict[str, Any]:
    target = None
    target_revision = int(revision)
    with _lock:
        history = _load_history_uncached()
        for item in history.get("items", []):
            if int(item.get("revision", -1)) == target_revision:
                target = copy.deepcopy(item)
                break

    if not target:
        raise ValueError(f"Graph model revision not found: {target_revision}")

    return save_graph_model(target.get("model", {}), updated_by=updated_by or "dev-rollback")
