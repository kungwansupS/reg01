import os
from typing import Dict, Any

# -----------------------------
# Optional imports (ALL SAFE)
# -----------------------------
try:
    from backend.retriever import retrieval_engine
except Exception:
    retrieval_engine = None

try:
    from backend.app.utils.llm import answer_engine
except Exception:
    answer_engine = None

# Legacy selector (ALWAYS AVAILABLE)
try:
    from backend.retriever import context_selector as legacy_selector
except Exception:
    legacy_selector = None


# -----------------------------
# Switch Control
# -----------------------------
def _use_new_engine() -> bool:
    return os.getenv("USE_RETRIEVAL_ENGINE", "false").lower() == "true"


# -----------------------------
# Public API — DROP-IN STYLE
# -----------------------------
def get_context(query: str) -> Dict[str, Any]:
    """
    Drop-in compatible context retrieval.

    Return format (LEGACY-COMPATIBLE MINIMUM):
    {
        "context": str
    }

    New engine (if enabled) will enrich internally,
    but output remains backward compatible.
    """

    # Safety check
    if not query or not isinstance(query, str):
        return {"context": ""}

    # -------------------------
    # New Engine Path (OPTIONAL)
    # -------------------------
    if _use_new_engine():
        try:
            if retrieval_engine is not None:
                result = retrieval_engine.retrieve_context(query=query)
                return {
                    "context": result.get("context", ""),
                }
        except Exception:
            pass  # HARD FALLBACK

    # -------------------------
    # Legacy Path (DEFAULT)
    # -------------------------
    if legacy_selector is not None and hasattr(legacy_selector, "get_context"):
        try:
            return legacy_selector.get_context(query)
        except Exception:
            pass

    # Absolute fallback
    return {"context": ""}


# -----------------------------
# Optional Full Answer API (NEW)
# -----------------------------
def get_answer(query: str) -> Dict[str, Any]:
    """
    NEW OPTIONAL API:
    Full answer generation using Phase 5 engine.

    Output:
    {
        "answer": str,
        "citations": list,
        "meta": dict
    }
    """
    if not query or not isinstance(query, str):
        return {
            "answer": "ไม่พบข้อมูลในเอกสาร",
            "citations": [],
            "meta": {
                "used_llm": False,
                "cached_context": False,
            },
        }

    if _use_new_engine() and answer_engine is not None:
        try:
            return answer_engine.answer_question(query)
        except Exception:
            pass

    # Fallback: context only, no answer synthesis
    ctx = get_context(query)
    if ctx.get("context"):
        return {
            "answer": ctx.get("context"),
            "citations": [],
            "meta": {
                "used_llm": False,
                "cached_context": False,
            },
        }

    return {
        "answer": "ไม่พบข้อมูลในเอกสาร",
        "citations": [],
        "meta": {
            "used_llm": False,
            "cached_context": False,
        },
    }


# -----------------------------
# Diagnostics (SAFE)
# -----------------------------
def info() -> Dict[str, Any]:
    """
    Diagnostic information.
    """
    return {
        "module": "context_selector_v2",
        "use_new_engine": _use_new_engine(),
        "legacy_available": legacy_selector is not None,
        "retrieval_engine_available": retrieval_engine is not None,
        "answer_engine_available": answer_engine is not None,
    }