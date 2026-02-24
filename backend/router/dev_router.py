import asyncio
import json
import os
import re
import sys
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_dev
from app.utils.llm.llm import ask_llm
from dev.env_store import get_env_snapshot, list_env_history, save_env_snapshot
from dev.flow_graph import (
    build_flow_graph,
    get_graph_model_state,
    list_graph_model_history,
    reset_graph_model,
    rollback_graph_model_revision,
    save_graph_model,
)
from dev.flow_store import (
    get_effective_flow_config,
    get_flow_state,
    list_flow_history,
    rollback_flow_revision,
    save_flow_config,
)
from dev.local_access import ensure_local_request
from dev.scenario_store import (
    delete_scenario,
    get_scenario,
    list_scenarios,
    save_scenario,
    save_scenario_run,
)
from dev.trace_store import get_trace, list_traces
from memory.faq_cache import (
    delete_faq_entry,
    get_faq_entry,
    list_faq_entries,
    purge_expired_faq_entries,
    save_faq_entry,
)


router = APIRouter(prefix="/api/dev", tags=["dev"])

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(BACKEND_DIR)
ENV_FILE_PATH = os.path.join(BACKEND_DIR, ".env")
DEFAULT_LOG_PATH = os.path.join(WORKSPACE_ROOT, "logs", "user_audit.log")
MAX_FILE_READ_SIZE = 1_500_000
MAX_TREE_ENTRIES = 400
MAX_SEARCH_RESULTS = 300
MAX_SEARCH_FILE_SIZE = 1_500_000
MAX_SYMBOL_RESULTS = 320
MAX_SHELL_OUTPUT_CHARS = 120_000
MAX_SHELL_TIMEOUT_SECONDS = 120
ALLOWED_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
TEXT_SEARCH_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".env",
    ".sql",
    ".xml",
    ".sh",
    ".ps1",
    ".bat",
    ".ini",
    ".cfg",
    ".toml",
}

IGNORED_TREE_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_rel_path(abs_path: str) -> str:
    rel = os.path.relpath(abs_path, WORKSPACE_ROOT)
    if rel in {".", ""}:
        return ""
    return rel.replace("\\", "/")


def _resolve_workspace_path(raw_path: str) -> str:
    raw = (raw_path or "").strip().replace("\\", "/")
    if raw in {"", ".", "/"}:
        candidate = WORKSPACE_ROOT
    else:
        if os.path.isabs(raw):
            raise HTTPException(status_code=400, detail="Absolute paths are not allowed.")
        candidate = os.path.normpath(os.path.join(WORKSPACE_ROOT, raw.lstrip("/")))

    root_real = os.path.normcase(os.path.realpath(WORKSPACE_ROOT))
    candidate_real = os.path.normcase(os.path.realpath(candidate))
    if candidate_real != root_real and not candidate_real.startswith(root_real + os.sep):
        raise HTTPException(status_code=400, detail="Path is outside workspace root.")

    return os.path.realpath(candidate)


def _detect_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".md": "markdown",
        ".env": "dotenv",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sql": "sql",
        ".txt": "text",
        ".xml": "xml",
        ".sh": "shell",
        ".bat": "batch",
        ".ps1": "powershell",
    }
    return mapping.get(ext, "plaintext")


def _tail_file_lines(file_path: str, lines: int) -> list[str]:
    tail: deque[str] = deque(maxlen=lines)
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            tail.append(line.rstrip("\n"))
    return list(tail)


def _normalize_id(value: Any, fallback: str = "") -> str:
    raw = str(value or "").strip().lower()
    chars = []
    for char in raw:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
        elif char in {" ", "."}:
            chars.append("_")
    normalized = "".join(chars).strip("_")
    return normalized or fallback


def _parse_log_line(line: str) -> Dict[str, Any]:
    raw = str(line or "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    return {"raw": raw, "parsed": parsed}


def _matches_log_filters(
    payload: Dict[str, Any],
    platform: str,
    trace_id: str,
    session_id: str,
    contains: str,
) -> bool:
    raw = str(payload.get("raw") or "")
    parsed = payload.get("parsed") if isinstance(payload.get("parsed"), dict) else {}

    if platform:
        if str(parsed.get("platform") or "").lower() != platform.lower():
            return False
    if trace_id:
        if str(parsed.get("trace_id") or "") != trace_id:
            return False
    if session_id:
        if str(parsed.get("session_id") or "") != session_id:
            return False
    if contains:
        hay = raw.lower()
        if contains.lower() not in hay:
            return False
    return True


def _graph_runtime_from_trace(trace: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
    steps = trace.get("steps") if isinstance(trace, dict) else []
    if not isinstance(steps, list):
        steps = []

    known_nodes = {node.get("id") for node in graph.get("nodes", []) if isinstance(node, dict)}
    node_order: list[str] = []
    node_latency: Dict[str, float] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        node_id = str(step.get("node_id") or "").strip()
        if not node_id or node_id not in known_nodes:
            continue
        if node_id not in node_order:
            node_order.append(node_id)
        node_latency[node_id] = round(node_latency.get(node_id, 0.0) + float(step.get("latency_ms") or 0.0), 2)

    edge_pairs = {(edge.get("source"), edge.get("target")): edge.get("id") for edge in graph.get("edges", []) if isinstance(edge, dict)}
    active_edges: list[str] = []
    for idx in range(len(node_order) - 1):
        pair = (node_order[idx], node_order[idx + 1])
        edge_id = edge_pairs.get(pair)
        if edge_id and edge_id not in active_edges:
            active_edges.append(edge_id)

    return {
        "active_nodes": node_order,
        "active_edges": active_edges,
        "node_latency_ms": node_latency,
    }


def _truncate_output(text: str, limit: int = MAX_SHELL_OUTPUT_CHARS) -> tuple[str, bool]:
    value = str(text or "")
    if len(value) <= limit:
        return value, False
    trimmed = len(value) - limit
    return f"{value[:limit]}\n...[truncated {trimmed} chars]", True


def _is_searchable_text_file(file_name: str) -> bool:
    ext = os.path.splitext(file_name)[1].lower()
    if ext in TEXT_SEARCH_EXTENSIONS:
        return True
    if ext == "":
        lowered = file_name.lower()
        return lowered in {"dockerfile", "makefile", "readme"}
    return False


def _decode_body_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _language_match_extension(file_name: str, language: str) -> bool:
    lang = str(language or "").strip().lower()
    if not lang:
        return True
    ext = os.path.splitext(file_name)[1].lower()
    mapping = {
        "python": {".py"},
        "javascript": {".js", ".jsx", ".mjs", ".cjs"},
        "typescript": {".ts", ".tsx"},
        "web": {".html", ".css", ".js", ".jsx", ".ts", ".tsx"},
    }
    allowed = mapping.get(lang)
    if not allowed:
        return True
    return ext in allowed


def _is_definition_line_for_symbol(
    line: str,
    symbol: str,
    extension: str,
    case_sensitive: bool,
) -> bool:
    safe = re.escape(symbol)
    flags = 0 if case_sensitive else re.IGNORECASE

    if extension == ".py":
        patterns = [
            rf"^\s*def\s+{safe}\b",
            rf"^\s*async\s+def\s+{safe}\b",
            rf"^\s*class\s+{safe}\b",
            rf"^\s*{safe}\s*=",
        ]
    elif extension in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        patterns = [
            rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{safe}\b",
            rf"^\s*(?:export\s+)?class\s+{safe}\b",
            rf"^\s*(?:export\s+)?(?:const|let|var)\s+{safe}\b",
            rf"^\s*{safe}\s*=\s*(?:async\s*)?\(",
            rf"^\s*{safe}\s*=\s*(?:async\s*)?function\b",
            rf"^\s*{safe}\s*:\s*function\b",
            rf"^\s*(?:export\s+)?interface\s+{safe}\b",
            rf"^\s*(?:export\s+)?type\s+{safe}\b",
        ]
    else:
        patterns = [
            rf"^\s*{safe}\s*[:=]",
        ]

    return any(re.search(pattern, line, flags=flags) for pattern in patterns)


async def verify_dev_access(
    request: Request,
    claims: dict = Depends(require_dev),
) -> dict:
    ensure_local_request(request)
    return claims


class FlowConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]
    updated_by: Optional[str] = Field(default="dev")


class FlowRollbackRequest(BaseModel):
    revision: int
    updated_by: Optional[str] = Field(default="dev-rollback")


class FlowTestRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None
    config_override: Optional[Dict[str, Any]] = None
    include_debug: bool = True


class EnvRawUpdateRequest(BaseModel):
    content: str
    updated_by: Optional[str] = Field(default="dev")


class EnvRollbackRequest(BaseModel):
    snapshot_id: str = Field(min_length=3, max_length=80)
    updated_by: Optional[str] = Field(default="dev-rollback")


class GraphPreviewRequest(BaseModel):
    config_override: Optional[Dict[str, Any]] = None
    model_override: Optional[Dict[str, Any]] = None


class GraphModelUpdateRequest(BaseModel):
    model: Dict[str, Any]
    updated_by: Optional[str] = Field(default="dev")


class GraphModelResetRequest(BaseModel):
    updated_by: Optional[str] = Field(default="dev")


class GraphModelRollbackRequest(BaseModel):
    revision: int
    updated_by: Optional[str] = Field(default="dev-rollback")


class ScenarioUpsertRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    message: str = Field(min_length=1, max_length=8000)
    config_override: Optional[Dict[str, Any]] = None
    updated_by: Optional[str] = Field(default="dev")


class ScenarioRunRequest(BaseModel):
    session_id: Optional[str] = None
    updated_by: Optional[str] = Field(default="dev")
    include_debug: bool = True


class FaqEntryUpsertRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=40000)
    original_question: Optional[str] = Field(default=None, max_length=4000)
    count: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    time_sensitive: Optional[bool] = None
    ttl_seconds: Optional[int] = Field(default=None, ge=60, le=365 * 86400)
    source: Optional[str] = Field(default="dev-ui", max_length=120)


class FileWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str
    create_dirs: bool = True


class ShellRunRequest(BaseModel):
    command: str = Field(min_length=1, max_length=1200)
    cwd: Optional[str] = Field(default="", max_length=400)
    timeout_seconds: int = Field(default=25, ge=1, le=MAX_SHELL_TIMEOUT_SECONDS)


class HttpProbeRequest(BaseModel):
    method: str = Field(default="GET", max_length=12)
    path: str = Field(default="/api/health", max_length=500)
    query: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    timeout_seconds: int = Field(default=20, ge=1, le=60)


@router.get("/flow", dependencies=[Depends(verify_dev_access)])
async def get_flow_config():
    return get_flow_state()


@router.put("/flow", dependencies=[Depends(verify_dev_access)])
async def update_flow_config(payload: FlowConfigUpdateRequest):
    state = save_flow_config(payload.config, payload.updated_by or "dev")
    return state


@router.get("/flow/history", dependencies=[Depends(verify_dev_access)])
async def get_flow_config_history(limit: int = 40):
    return list_flow_history(limit)


@router.post("/flow/rollback", dependencies=[Depends(verify_dev_access)])
async def rollback_flow_config(payload: FlowRollbackRequest):
    try:
        state = rollback_flow_revision(payload.revision, updated_by=payload.updated_by or "dev-rollback")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return state


@router.post("/test", dependencies=[Depends(verify_dev_access)])
async def test_flow(payload: FlowTestRequest):
    started = time.time()
    session_id = payload.session_id or f"dev_preview_{uuid.uuid4().hex[:12]}"

    flow_config = get_effective_flow_config(payload.config_override or {})
    result = await ask_llm(
        payload.message,
        session_id,
        flow_config=flow_config,
        include_debug=bool(payload.include_debug),
        trace_source="dev_test",
    )

    response_payload = {
        "session_id": session_id,
        "trace_id": result.get("trace_id"),
        "latency_seconds": round(time.time() - started, 2),
        "result": result,
        "effective_config": flow_config,
    }
    return response_payload


@router.get("/graph", dependencies=[Depends(verify_dev_access)])
async def get_runtime_graph():
    return build_flow_graph()


@router.post("/graph/preview", dependencies=[Depends(verify_dev_access)])
async def preview_runtime_graph(payload: GraphPreviewRequest):
    return build_flow_graph(payload.config_override or {}, payload.model_override or {})


@router.get("/graph/model", dependencies=[Depends(verify_dev_access)])
async def get_graph_model():
    return get_graph_model_state()


@router.put("/graph/model", dependencies=[Depends(verify_dev_access)])
async def update_graph_model(payload: GraphModelUpdateRequest):
    return save_graph_model(payload.model, updated_by=payload.updated_by or "dev")


@router.post("/graph/model/reset", dependencies=[Depends(verify_dev_access)])
async def reset_graph_model_api(payload: GraphModelResetRequest):
    return reset_graph_model(updated_by=payload.updated_by or "dev")


@router.get("/graph/model/history", dependencies=[Depends(verify_dev_access)])
async def get_graph_model_history(limit: int = 40):
    return list_graph_model_history(limit)


@router.post("/graph/model/rollback", dependencies=[Depends(verify_dev_access)])
async def rollback_graph_model(payload: GraphModelRollbackRequest):
    try:
        state = rollback_graph_model_revision(payload.revision, updated_by=payload.updated_by or "dev-rollback")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return state


@router.get("/traces", dependencies=[Depends(verify_dev_access)])
async def get_traces(limit: int = 80, session_id: str = "", status: str = ""):
    return {
        "items": list_traces(limit=limit, session_id=session_id or None, status=status or None),
    }


@router.get("/traces/{trace_id}", dependencies=[Depends(verify_dev_access)])
async def get_trace_by_id(trace_id: str):
    trace = get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
    return trace


@router.get("/traces/{trace_id}/graph", dependencies=[Depends(verify_dev_access)])
async def get_trace_graph(trace_id: str):
    trace = get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")

    flow_override = trace.get("flow_config_snapshot") if isinstance(trace.get("flow_config_snapshot"), dict) else {}
    graph = build_flow_graph(config_override=flow_override)
    runtime = _graph_runtime_from_trace(trace, graph)

    return {
        "trace_id": trace.get("trace_id"),
        "status": trace.get("status"),
        "started_at": trace.get("started_at"),
        "ended_at": trace.get("ended_at"),
        "latency_ms": trace.get("latency_ms"),
        "active_nodes": runtime["active_nodes"],
        "active_edges": runtime["active_edges"],
        "node_latency_ms": runtime["node_latency_ms"],
        "graph_revision": graph.get("model_revision"),
    }


@router.get("/connections", dependencies=[Depends(verify_dev_access)])
async def get_connections():
    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower() or "unknown"
    openai_key = bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY2")
        or os.getenv("OPENAI_API_KEY_BACKUP")
        or os.getenv("OPENAI_API_KEYS")
    )
    gemini_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    fb_token = bool(os.getenv("FB_PAGE_ACCESS_TOKEN"))

    vector_db_path = os.path.join(WORKSPACE_ROOT, "data", "db", "chroma_data", "chroma.sqlite3")
    database_url = os.getenv("DATABASE_URL", "")
    flow_file = os.path.join(BACKEND_DIR, "dev", "flow_config.json")
    graph_file = os.path.join(BACKEND_DIR, "dev", "flow_graph_model.json")

    def status_for_file(path: str) -> str:
        return "ok" if os.path.exists(path) else "missing"

    if llm_provider == "openai":
        llm_status = "configured" if openai_key else "missing_api_key"
    elif llm_provider == "gemini":
        llm_status = "configured" if gemini_key else "missing_api_key"
    elif llm_provider in {"local", "ollama"}:
        llm_status = "configured"
    else:
        llm_status = "unknown_provider"

    nodes = [
        {"id": "dev_ui", "title": "Dev Console UI", "kind": "frontend", "status": "ok", "path": "frontend-next/src/app/dev/page.tsx"},
        {"id": "backend_api", "title": "FastAPI Backend", "kind": "service", "status": "ok", "path": "backend/main.py"},
        {"id": "socketio", "title": "Socket.IO Gateway", "kind": "service", "status": "ok", "path": "backend/main.py"},
        {"id": "llm", "title": f"LLM Provider ({llm_provider})", "kind": "external", "status": llm_status},
        {"id": "vector_db", "title": "Vector DB (Chroma)", "kind": "storage", "status": status_for_file(vector_db_path), "path": _to_rel_path(vector_db_path)},
        {"id": "session_db", "title": "Session DB (PostgreSQL + SQLAlchemy)", "kind": "storage", "status": "configured" if database_url else "missing"},
        {"id": "redis", "title": "Redis (FAQ Cache + Queue)", "kind": "storage", "status": "configured" if os.getenv("REDIS_URL") else "default"},
        {"id": "flow_store", "title": "Flow Config Store", "kind": "storage", "status": status_for_file(flow_file), "path": _to_rel_path(flow_file)},
        {"id": "graph_store", "title": "Graph Model Store", "kind": "storage", "status": status_for_file(graph_file), "path": _to_rel_path(graph_file)},
        {"id": "audit_log", "title": "Audit Log", "kind": "storage", "status": status_for_file(DEFAULT_LOG_PATH), "path": _to_rel_path(DEFAULT_LOG_PATH)},
        {"id": "facebook_api", "title": "Facebook Graph API", "kind": "external", "status": "configured" if fb_token else "disabled"},
    ]

    edges = [
        {"id": "e1", "source": "dev_ui", "target": "backend_api", "label": "/api/dev/*"},
        {"id": "e2", "source": "backend_api", "target": "socketio", "label": "real-time emit"},
        {"id": "e3", "source": "backend_api", "target": "llm", "label": "ask_llm"},
        {"id": "e4", "source": "backend_api", "target": "vector_db", "label": "retriever search"},
        {"id": "e5", "source": "backend_api", "target": "session_db", "label": "session history"},
        {"id": "e6", "source": "backend_api", "target": "flow_store", "label": "flow config"},
        {"id": "e7", "source": "backend_api", "target": "graph_store", "label": "graph model"},
        {"id": "e8", "source": "backend_api", "target": "audit_log", "label": "write_audit_log"},
        {"id": "e8b", "source": "backend_api", "target": "redis", "label": "FAQ cache + queue persist"},
        {"id": "e9", "source": "backend_api", "target": "facebook_api", "label": "send messenger", "enabled": fb_token},
    ]

    return {
        "generated_at": _now_iso(),
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/routes", dependencies=[Depends(verify_dev_access)])
async def get_route_map(request: Request):
    items: list[Dict[str, Any]] = []
    for route in request.app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue

        methods = sorted(
            method for method in (getattr(route, "methods", set()) or set()) if method not in {"HEAD", "OPTIONS"}
        )
        tags = list(getattr(route, "tags", []) or [])
        endpoint = getattr(route, "endpoint", None)
        endpoint_name = ""
        if endpoint:
            endpoint_name = f"{getattr(endpoint, '__module__', '')}.{getattr(endpoint, '__name__', '')}".strip(".")

        items.append(
            {
                "path": str(path),
                "name": str(getattr(route, "name", "") or ""),
                "methods": methods,
                "tags": tags,
                "endpoint": endpoint_name,
            }
        )

    items.sort(key=lambda row: (row.get("path", ""), ",".join(row.get("methods", []))))
    return {
        "generated_at": _now_iso(),
        "count": len(items),
        "items": items,
    }


@router.post("/http/probe", dependencies=[Depends(verify_dev_access)])
async def probe_http_endpoint(request: Request, payload: HttpProbeRequest):
    method = str(payload.method or "GET").strip().upper()
    if method not in ALLOWED_HTTP_METHODS:
        raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")

    raw_path = str(payload.path or "/").strip() or "/"
    if not raw_path.startswith("/"):
        raw_path = f"/{raw_path}"
    if len(raw_path) > 500:
        raise HTTPException(status_code=400, detail="Path is too long.")
    if raw_path.rstrip("/") == "/api/dev/http/probe":
        raise HTTPException(status_code=400, detail="Self probe is not allowed.")

    headers: Dict[str, str] = {}
    for key, value in (payload.headers or {}).items():
        header_name = str(key or "").strip()
        if not header_name:
            continue
        headers[header_name] = str(value or "")

    request_kwargs: Dict[str, Any] = {}
    if payload.body is not None:
        if isinstance(payload.body, (dict, list)):
            request_kwargs["json"] = payload.body
        else:
            request_kwargs["content"] = str(payload.body)

    timeout = httpx.Timeout(timeout=float(payload.timeout_seconds))
    started = time.perf_counter()
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dev.local", timeout=timeout) as client:
        response = await client.request(
            method,
            raw_path,
            params=payload.query or {},
            headers=headers,
            **request_kwargs,
        )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    content_type = str(response.headers.get("content-type") or "")
    is_json = "application/json" in content_type.lower()
    body_text_raw = _decode_body_bytes(response.content or b"")
    body_text, body_truncated = _truncate_output(body_text_raw)
    body_json: Any = None
    if is_json:
        try:
            body_json = response.json()
        except Exception:
            body_json = None

    response_headers = {str(k): str(v) for k, v in response.headers.items()}

    return {
        "method": method,
        "path": raw_path,
        "status_code": int(response.status_code),
        "reason_phrase": str(response.reason_phrase or ""),
        "latency_ms": latency_ms,
        "content_type": content_type,
        "headers": response_headers,
        "is_json": is_json,
        "body_json": body_json,
        "body_text": body_text,
        "body_truncated": body_truncated,
    }


@router.post("/shell/run", dependencies=[Depends(verify_dev_access)])
async def run_shell_command(payload: ShellRunRequest):
    command = str(payload.command or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command is required.")

    resolved_cwd = _resolve_workspace_path(payload.cwd or "")
    timeout_seconds = max(1, min(MAX_SHELL_TIMEOUT_SECONDS, int(payload.timeout_seconds)))
    started = time.perf_counter()

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=resolved_cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Cannot start process: {exc}") from exc

    timed_out = False
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        timed_out = True
        process.kill()
        stdout_raw, stderr_raw = await process.communicate()

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    stdout_text, stdout_truncated = _truncate_output(_decode_body_bytes(stdout_raw or b""))
    stderr_text, stderr_truncated = _truncate_output(_decode_body_bytes(stderr_raw or b""))

    return {
        "command": command,
        "cwd": _to_rel_path(resolved_cwd),
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": int(process.returncode) if process.returncode is not None else -1,
        "latency_ms": latency_ms,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


@router.get("/fs/search", dependencies=[Depends(verify_dev_access)])
async def search_workspace_files(
    q: str,
    path: str = "",
    case_sensitive: bool = False,
    regex: bool = False,
    max_results: int = 120,
    max_files: int = 1500,
):
    query = str(q or "").strip()
    if len(query) < 1:
        raise HTTPException(status_code=400, detail="Query is required.")

    root_dir = _resolve_workspace_path(path or "")
    if not os.path.isdir(root_dir):
        raise HTTPException(status_code=400, detail="Path is not a directory.")

    cap_results = max(1, min(MAX_SEARCH_RESULTS, int(max_results)))
    cap_files = max(20, min(10_000, int(max_files)))

    if regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(query, flags)
        except re.error as exc:
            raise HTTPException(status_code=400, detail=f"Invalid regex: {exc}") from exc
    else:
        compiled = None
        query_cmp = query if case_sensitive else query.lower()

    items: list[Dict[str, Any]] = []
    scanned_files = 0
    scanned_lines = 0
    scanned_bytes = 0
    reached_file_limit = False
    reached_result_limit = False

    for current_root, dir_names, file_names in os.walk(root_dir):
        dir_names[:] = [name for name in dir_names if name not in IGNORED_TREE_NAMES]
        if reached_result_limit or reached_file_limit:
            break

        for file_name in file_names:
            if file_name in IGNORED_TREE_NAMES:
                continue
            if not _is_searchable_text_file(file_name):
                continue

            abs_path = os.path.join(current_root, file_name)
            scanned_files += 1
            if scanned_files > cap_files:
                reached_file_limit = True
                break

            try:
                file_size = int(os.path.getsize(abs_path))
            except OSError:
                continue
            if file_size > MAX_SEARCH_FILE_SIZE:
                continue
            scanned_bytes += file_size

            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as file_obj:
                    for line_no, raw_line in enumerate(file_obj, start=1):
                        scanned_lines += 1
                        line = raw_line.rstrip("\n")
                        match_column = -1

                        if compiled is not None:
                            match = compiled.search(line)
                            if match:
                                match_column = int(match.start())
                        else:
                            haystack = line if case_sensitive else line.lower()
                            match_column = haystack.find(query_cmp)

                        if match_column < 0:
                            continue

                        items.append(
                            {
                                "path": _to_rel_path(abs_path),
                                "line": line_no,
                                "column": match_column + 1,
                                "preview": line[:500],
                            }
                        )
                        if len(items) >= cap_results:
                            reached_result_limit = True
                            break
            except OSError:
                continue

            if reached_result_limit:
                break

    return {
        "query": query,
        "root": _to_rel_path(root_dir),
        "case_sensitive": bool(case_sensitive),
        "regex": bool(regex),
        "scanned_files": scanned_files,
        "scanned_lines": scanned_lines,
        "scanned_bytes": scanned_bytes,
        "reached_file_limit": reached_file_limit,
        "reached_result_limit": reached_result_limit,
        "matched": len(items),
        "items": items,
    }


@router.get("/fs/symbol", dependencies=[Depends(verify_dev_access)])
async def find_symbol_in_workspace(
    symbol: str,
    path: str = "",
    language: str = "",
    case_sensitive: bool = True,
    max_results: int = 160,
    max_files: int = 1500,
):
    symbol_name = str(symbol or "").strip()
    if len(symbol_name) < 1:
        raise HTTPException(status_code=400, detail="Symbol is required.")

    root_dir = _resolve_workspace_path(path or "")
    if not os.path.isdir(root_dir):
        raise HTTPException(status_code=400, detail="Path is not a directory.")

    cap_results = max(1, min(MAX_SYMBOL_RESULTS, int(max_results)))
    cap_files = max(20, min(10_000, int(max_files)))
    flags = 0 if case_sensitive else re.IGNORECASE
    symbol_word = re.compile(rf"\b{re.escape(symbol_name)}\b", flags=flags)

    definitions: list[Dict[str, Any]] = []
    references: list[Dict[str, Any]] = []
    scanned_files = 0
    scanned_lines = 0
    scanned_bytes = 0
    reached_file_limit = False
    reached_result_limit = False

    for current_root, dir_names, file_names in os.walk(root_dir):
        dir_names[:] = [name for name in dir_names if name not in IGNORED_TREE_NAMES]
        if reached_result_limit or reached_file_limit:
            break

        for file_name in file_names:
            if file_name in IGNORED_TREE_NAMES:
                continue
            if not _is_searchable_text_file(file_name):
                continue
            if not _language_match_extension(file_name, language):
                continue

            abs_path = os.path.join(current_root, file_name)
            scanned_files += 1
            if scanned_files > cap_files:
                reached_file_limit = True
                break

            try:
                file_size = int(os.path.getsize(abs_path))
            except OSError:
                continue
            if file_size > MAX_SEARCH_FILE_SIZE:
                continue
            scanned_bytes += file_size
            extension = os.path.splitext(file_name)[1].lower()

            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as file_obj:
                    for line_no, raw_line in enumerate(file_obj, start=1):
                        scanned_lines += 1
                        line = raw_line.rstrip("\n")
                        match = symbol_word.search(line)
                        if not match:
                            continue

                        is_definition = _is_definition_line_for_symbol(
                            line=line,
                            symbol=symbol_name,
                            extension=extension,
                            case_sensitive=case_sensitive,
                        )
                        item = {
                            "kind": "definition" if is_definition else "reference",
                            "path": _to_rel_path(abs_path),
                            "line": line_no,
                            "column": int(match.start()) + 1,
                            "preview": line[:500],
                        }
                        if is_definition:
                            definitions.append(item)
                        else:
                            references.append(item)

                        if len(definitions) + len(references) >= cap_results:
                            reached_result_limit = True
                            break
            except OSError:
                continue

            if reached_result_limit:
                break

    items = (definitions + references)[:cap_results]
    return {
        "symbol": symbol_name,
        "language": str(language or "").strip().lower(),
        "root": _to_rel_path(root_dir),
        "case_sensitive": bool(case_sensitive),
        "scanned_files": scanned_files,
        "scanned_lines": scanned_lines,
        "scanned_bytes": scanned_bytes,
        "reached_file_limit": reached_file_limit,
        "reached_result_limit": reached_result_limit,
        "definitions": len(definitions),
        "references": len(references),
        "matched": len(items),
        "items": items,
    }


@router.get("/logs/search", dependencies=[Depends(verify_dev_access)])
async def search_logs(
    path: str = "logs/user_audit.log",
    limit: int = 120,
    scan_lines: int = 2400,
    platform: str = "",
    trace_id: str = "",
    session_id: str = "",
    contains: str = "",
):
    resolved = _resolve_workspace_path(path or "")
    if os.path.normcase(resolved) == os.path.normcase(os.path.realpath(WORKSPACE_ROOT)):
        resolved = DEFAULT_LOG_PATH

    if not os.path.exists(resolved):
        return {
            "path": _to_rel_path(resolved),
            "exists": False,
            "scanned": 0,
            "matched": 0,
            "items": [],
        }
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=400, detail="Path is not a file.")

    capped_scan = max(100, min(10_000, int(scan_lines)))
    capped_limit = max(1, min(500, int(limit)))
    lines = _tail_file_lines(resolved, capped_scan)

    matched: list[Dict[str, Any]] = []
    total = len(lines)
    start_line_number = max(1, total - len(lines) + 1)
    for idx, line in enumerate(lines):
        payload = _parse_log_line(line)
        if not _matches_log_filters(payload, platform, trace_id, session_id, contains):
            continue

        item = {
            "line_no": start_line_number + idx,
            "raw": payload["raw"],
            "parsed": payload["parsed"],
        }
        matched.append(item)
        if len(matched) >= capped_limit:
            break

    return {
        "path": _to_rel_path(resolved),
        "exists": True,
        "scanned": len(lines),
        "matched": len(matched),
        "items": matched,
    }


@router.get("/scenarios", dependencies=[Depends(verify_dev_access)])
async def get_scenario_list(limit: int = 200):
    return {"items": list_scenarios(limit)}


@router.get("/scenarios/{scenario_id}", dependencies=[Depends(verify_dev_access)])
async def get_scenario_item(scenario_id: str):
    item = get_scenario(scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")
    return item


@router.post("/scenarios", dependencies=[Depends(verify_dev_access)])
async def create_or_update_scenario(payload: ScenarioUpsertRequest):
    raw = {
        "id": payload.id,
        "name": payload.name,
        "description": payload.description,
        "message": payload.message,
        "config_override": payload.config_override or {},
    }
    item = save_scenario(raw, updated_by=payload.updated_by or "dev")
    return {"item": item}


@router.put("/scenarios/{scenario_id}", dependencies=[Depends(verify_dev_access)])
async def update_scenario_item(scenario_id: str, payload: ScenarioUpsertRequest):
    raw = {
        "id": scenario_id,
        "name": payload.name,
        "description": payload.description,
        "message": payload.message,
        "config_override": payload.config_override or {},
    }
    item = save_scenario(raw, updated_by=payload.updated_by or "dev")
    return {"item": item}


@router.delete("/scenarios/{scenario_id}", dependencies=[Depends(verify_dev_access)])
async def delete_scenario_item(scenario_id: str):
    try:
        result = delete_scenario(scenario_id, updated_by="dev")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/scenarios/{scenario_id}/run", dependencies=[Depends(verify_dev_access)])
async def run_scenario(scenario_id: str, payload: ScenarioRunRequest):
    item = get_scenario(scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    started = time.time()
    run_session_id = payload.session_id or f"scenario_{_normalize_id(scenario_id, 'unknown')}_{uuid.uuid4().hex[:10]}"
    flow_cfg = get_effective_flow_config(item.get("config_override") or {})
    result = await ask_llm(
        item.get("message") or "",
        run_session_id,
        flow_config=flow_cfg,
        include_debug=bool(payload.include_debug),
        trace_source="dev_scenario",
    )
    latency_ms = round((time.time() - started) * 1000, 2)
    tokens_total = int((result.get("tokens") or {}).get("total_tokens", 0))
    updated = save_scenario_run(
        scenario_id=scenario_id,
        trace_id=str(result.get("trace_id") or ""),
        latency_ms=latency_ms,
        output_text=str(result.get("text") or ""),
        tokens_total=tokens_total,
        updated_by=payload.updated_by or "dev",
    )

    return {
        "scenario": updated,
        "session_id": run_session_id,
        "latency_ms": latency_ms,
        "trace_id": result.get("trace_id"),
        "result": result,
        "effective_config": flow_cfg,
    }


@router.get("/faq", dependencies=[Depends(verify_dev_access)])
async def list_faq_items(
    limit: int = 300,
    query: str = "",
    include_expired: bool = False,
):
    return await list_faq_entries(limit=limit, query=query, include_expired=bool(include_expired))


@router.get("/faq/entry", dependencies=[Depends(verify_dev_access)])
async def get_faq_item(question: str):
    item = await get_faq_entry(question)
    if not item:
        raise HTTPException(status_code=404, detail=f"FAQ entry not found: {question}")
    return item


@router.put("/faq/entry", dependencies=[Depends(verify_dev_access)])
async def upsert_faq_item(payload: FaqEntryUpsertRequest):
    try:
        item = await save_faq_entry(
            question=payload.question,
            answer=payload.answer,
            original_question=payload.original_question,
            count=payload.count,
            time_sensitive=payload.time_sensitive,
            ttl_seconds=payload.ttl_seconds,
            source=payload.source or "dev-ui",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.delete("/faq/entry", dependencies=[Depends(verify_dev_access)])
async def remove_faq_item(question: str):
    try:
        result = await delete_faq_entry(question)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/faq/purge-expired", dependencies=[Depends(verify_dev_access)])
async def purge_faq_expired():
    return await purge_expired_faq_entries()


@router.get("/fs/tree", dependencies=[Depends(verify_dev_access)])
async def get_workspace_tree(
    path: str = "",
    max_entries: int = 200,
    include_hidden: bool = True,
):
    resolved_dir = _resolve_workspace_path(path)
    if not os.path.isdir(resolved_dir):
        raise HTTPException(status_code=400, detail="Path is not a directory.")

    capped = max(20, min(MAX_TREE_ENTRIES, int(max_entries)))
    items = []

    try:
        for entry in os.scandir(resolved_dir):
            name = entry.name
            if name in IGNORED_TREE_NAMES:
                continue
            if not include_hidden and name.startswith("."):
                continue

            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue

            try:
                stat = entry.stat(follow_symlinks=False)
                modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                size = int(stat.st_size)
            except OSError:
                modified_at = None
                size = None

            items.append(
                {
                    "name": name,
                    "path": _to_rel_path(entry.path),
                    "type": "dir" if is_dir else "file",
                    "extension": "" if is_dir else os.path.splitext(name)[1].lower(),
                    "size": None if is_dir else size,
                    "modified_at": modified_at,
                }
            )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Unable to read directory: {exc}") from exc

    items.sort(key=lambda item: (item["type"] != "dir", item["name"].lower()))
    truncated = len(items) > capped
    if truncated:
        items = items[:capped]

    parent = None
    if os.path.normcase(os.path.realpath(resolved_dir)) != os.path.normcase(os.path.realpath(WORKSPACE_ROOT)):
        parent = _to_rel_path(os.path.dirname(resolved_dir))

    return {
        "workspace_root": _to_rel_path(WORKSPACE_ROOT),
        "path": _to_rel_path(resolved_dir),
        "parent": parent,
        "items": items,
        "truncated": truncated,
    }


@router.get("/fs/read", dependencies=[Depends(verify_dev_access)])
async def read_workspace_file(path: str):
    resolved = _resolve_workspace_path(path)
    if not os.path.exists(resolved):
        raise HTTPException(status_code=404, detail="File not found.")
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=400, detail="Path is not a file.")

    file_size = os.path.getsize(resolved)
    if file_size > MAX_FILE_READ_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large to open in dev editor ({file_size} bytes).",
        )

    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    modified_at = datetime.fromtimestamp(os.path.getmtime(resolved), tz=timezone.utc).isoformat()
    return {
        "path": _to_rel_path(resolved),
        "size": file_size,
        "modified_at": modified_at,
        "language": _detect_language(resolved),
        "content": content,
    }


@router.put("/fs/write", dependencies=[Depends(verify_dev_access)])
async def write_workspace_file(payload: FileWriteRequest):
    resolved = _resolve_workspace_path(payload.path)
    if os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail="Target path is a directory.")

    target_dir = os.path.dirname(resolved)
    if payload.create_dirs:
        os.makedirs(target_dir, exist_ok=True)
    elif not os.path.isdir(target_dir):
        raise HTTPException(status_code=400, detail="Target directory does not exist.")

    backup_path = None
    if os.path.exists(resolved):
        backup_path = f"{resolved}.bak"
        with open(resolved, "r", encoding="utf-8", errors="replace") as src:
            existing = src.read()
        with open(backup_path, "w", encoding="utf-8") as bak:
            bak.write(existing)

    normalized = payload.content.replace("\r\n", "\n")
    with open(resolved, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)

    modified_at = datetime.fromtimestamp(os.path.getmtime(resolved), tz=timezone.utc).isoformat()
    return {
        "status": "saved",
        "path": _to_rel_path(resolved),
        "backup_path": _to_rel_path(backup_path) if backup_path else None,
        "size": len(normalized),
        "modified_at": modified_at,
    }


@router.get("/runtime/summary", dependencies=[Depends(verify_dev_access)])
async def get_runtime_summary():
    flow_state = get_flow_state()
    flow_cfg = flow_state.get("config", {})

    return {
        "time_utc": _now_iso(),
        "pid": os.getpid(),
        "python_version": sys.version.split()[0],
        "workspace_root": WORKSPACE_ROOT,
        "backend_dir": BACKEND_DIR,
        "local_only": True,
        "flow": {
            "revision": flow_state.get("revision"),
            "updated_at": flow_state.get("updated_at"),
            "updated_by": flow_state.get("updated_by"),
            "rag_mode": flow_cfg.get("rag", {}).get("mode"),
            "memory_recent_messages": flow_cfg.get("memory", {}).get("recent_messages"),
            "pose_enabled": flow_cfg.get("pose", {}).get("enabled"),
        },
        "env": {
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", ""),
            "OPENAI_MODEL_NAME": os.getenv("OPENAI_MODEL_NAME", ""),
            "GEMINI_MODEL_NAME": os.getenv("GEMINI_MODEL_NAME", ""),
            "LOCAL_MODEL_NAME": os.getenv("LOCAL_MODEL_NAME", ""),
        },
        "traces": {
            "recent_count": len(list_traces(limit=20)),
        },
    }


@router.get("/logs/tail", dependencies=[Depends(verify_dev_access)])
async def get_log_tail(path: str = "logs/user_audit.log", lines: int = 120):
    resolved = _resolve_workspace_path(path or "")
    if os.path.normcase(resolved) == os.path.normcase(os.path.realpath(WORKSPACE_ROOT)):
        resolved = DEFAULT_LOG_PATH

    if not os.path.exists(resolved):
        return {
            "path": _to_rel_path(resolved),
            "exists": False,
            "line_count": 0,
            "lines": [],
        }
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=400, detail="Path is not a file.")

    capped = max(10, min(500, int(lines)))
    tail = _tail_file_lines(resolved, capped)
    return {
        "path": _to_rel_path(resolved),
        "exists": True,
        "line_count": len(tail),
        "lines": tail,
    }


@router.get("/env/raw", dependencies=[Depends(verify_dev_access)])
async def get_env_raw():
    if not os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("")

    with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "path": ENV_FILE_PATH,
        "content": content,
    }


@router.put("/env/raw", dependencies=[Depends(verify_dev_access)])
async def update_env_raw(payload: EnvRawUpdateRequest):
    os.makedirs(os.path.dirname(ENV_FILE_PATH), exist_ok=True)

    backup_path = f"{ENV_FILE_PATH}.bak"
    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as src:
            existing = src.read()
        with open(backup_path, "w", encoding="utf-8") as bak:
            bak.write(existing)

    normalized = payload.content.replace("\r\n", "\n")
    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(normalized)

    snapshot = save_env_snapshot(normalized, updated_by=payload.updated_by or "dev")

    # Reload environment variables in current process.
    load_dotenv(ENV_FILE_PATH, override=True)

    return {
        "status": "saved",
        "path": ENV_FILE_PATH,
        "backup_path": backup_path,
        "size": len(normalized),
        "snapshot_id": snapshot.get("id"),
    }


@router.get("/env/history", dependencies=[Depends(verify_dev_access)])
async def get_env_history(limit: int = 40):
    return list_env_history(limit)


@router.get("/env/history/{snapshot_id}", dependencies=[Depends(verify_dev_access)])
async def get_env_history_snapshot(snapshot_id: str):
    snapshot = get_env_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Env snapshot not found: {snapshot_id}")
    return snapshot


@router.post("/env/rollback", dependencies=[Depends(verify_dev_access)])
async def rollback_env(payload: EnvRollbackRequest):
    snapshot = get_env_snapshot(payload.snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Env snapshot not found: {payload.snapshot_id}")

    backup_path = f"{ENV_FILE_PATH}.bak"
    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as src:
            with open(backup_path, "w", encoding="utf-8") as bak:
                bak.write(src.read())

    content = str(snapshot.get("content") or "")
    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content.replace("\r\n", "\n"))

    save_env_snapshot(content, updated_by=payload.updated_by or "dev-rollback")
    load_dotenv(ENV_FILE_PATH, override=True)

    return {
        "status": "rolled_back",
        "path": ENV_FILE_PATH,
        "backup_path": backup_path,
        "snapshot_id": snapshot.get("id"),
        "size": len(content),
    }
