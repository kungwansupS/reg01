from typing import List, Dict, Any
import hashlib
import threading

# Optional modules (ALL SAFE)
try:
    from backend.retriever import hybrid_retriever
except Exception:
    hybrid_retriever = None

try:
    from backend.retriever import context_assembler
except Exception:
    context_assembler = None


# -----------------------------
# Internal Cache (Thread-safe)
# -----------------------------
__LOCK = threading.Lock()
__CACHE: Dict[str, Dict[str, Any]] = {}
__CACHE_MAX = 128


# -----------------------------
# Utilities
# -----------------------------
def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Dict[str, Any]:
    with __LOCK:
        return __CACHE.get(key, {})


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    with __LOCK:
        if len(__CACHE) >= __CACHE_MAX:
            # deterministic eviction: oldest key
            oldest = next(iter(__CACHE.keys()))
            __CACHE.pop(oldest, None)
        __CACHE[key] = value


# -----------------------------
# Public API (SAFE ENTRY POINT)
# -----------------------------
def retrieve_context(
    query: str,
    top_k: int = 3,
    max_chars: int = 3000,
) -> Dict[str, Any]:
    """
    Unified retrieval entry point.

    Output format (ALWAYS):
    {
        "context": str,
        "citations": list,
        "meta": {
            "cached": bool,
            "retriever": str
        }
    }

    Safety Guarantees:
    - NEVER raises exception
    - Returns empty context on failure
    - Deterministic behavior
    """
    if not query or not isinstance(query, str):
        return {
            "context": "",
            "citations": [],
            "meta": {
                "cached": False,
                "retriever": "none",
            },
        }

    key = _hash_query(query)

    # 1) Cache lookup
    cached = _cache_get(key)
    if cached:
        return {
            "context": cached.get("context", ""),
            "citations": cached.get("citations", []),
            "meta": {
                "cached": True,
                "retriever": cached.get("retriever", "unknown"),
            },
        }

    # 2) Retrieval
    retrieved_docs: List[Dict[str, Any]] = []

    try:
        if hybrid_retriever is not None:
            retrieved_docs = hybrid_retriever.hybrid_search(
                query=query,
                top_k=top_k,
            )
    except Exception:
        retrieved_docs = []

    # 3) Context assembly
    try:
        if context_assembler is not None:
            assembled = context_assembler.assemble_context(
                retrieved_docs=retrieved_docs,
                max_chars=max_chars,
            )
        else:
            assembled = {
                "context": "",
                "citations": [],
            }
    except Exception:
        assembled = {
            "context": "",
            "citations": [],
        }

    result = {
        "context": assembled.get("context", ""),
        "citations": assembled.get("citations", []),
        "meta": {
            "cached": False,
            "retriever": "hybrid" if retrieved_docs else "none",
        },
    }

    # 4) Cache store (only if meaningful)
    if result["context"]:
        _cache_set(
            key,
            {
                "context": result["context"],
                "citations": result["citations"],
                "retriever": result["meta"]["retriever"],
            },
        )

    return result


# -----------------------------
# Diagnostics (SAFE)
# -----------------------------
def info() -> Dict[str, Any]:
    """
    Diagnostic information.
    """
    return {
        "module": "retrieval_engine",
        "cache_size": len(__CACHE),
        "cache_max": __CACHE_MAX,
        "hybrid_available": hybrid_retriever is not None,
        "assembler_available": context_assembler is not None,
    }