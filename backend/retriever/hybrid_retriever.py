from typing import List, Dict, Any, Optional
import threading

# Optional embedding layer (Phase 1)
try:
    from backend.retriever import embedding_index
except Exception:
    embedding_index = None


# -----------------------------
# Internal State
# -----------------------------
__LOCK = threading.Lock()
__KEYWORD_DOCS: List[Dict[str, Any]] = []


# -----------------------------
# Initialization (SAFE)
# -----------------------------
def initialize_keyword_docs(docs: List[Dict[str, str]]) -> bool:
    """
    Initialize keyword documents.
    This does NOT affect existing retrieval logic.
    Safe to call multiple times.
    """
    global __KEYWORD_DOCS

    if not isinstance(docs, list):
        return False

    with __LOCK:
        cleaned: List[Dict[str, Any]] = []
        for d in docs:
            if not isinstance(d, dict):
                continue
            text = d.get("text")
            doc_id = d.get("id")
            if not text or not doc_id:
                continue
            cleaned.append(
                {
                    "id": doc_id,
                    "text": text,
                }
            )
        __KEYWORD_DOCS = cleaned
        return True


# -----------------------------
# Keyword Retrieval (Deterministic)
# -----------------------------
def keyword_search(
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Simple keyword-based retrieval.
    Zero dependency, zero failure.
    """
    if not query or not __KEYWORD_DOCS:
        return []

    scored: List[Dict[str, Any]] = []
    q = query.lower()

    for d in __KEYWORD_DOCS:
        text = d["text"].lower()
        score = sum(1 for w in q.split() if w in text)
        if score > 0:
            scored.append(
                {
                    "id": d["id"],
                    "text": d["text"],
                    "score": float(score),
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: max(1, int(top_k))]


# -----------------------------
# Hybrid Retrieval (SAFE)
# -----------------------------
def hybrid_search(
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval strategy:
    1) Keyword search (always available)
    2) Embedding search (optional, safe fallback)

    NEVER raises exception.
    """
    if not query:
        return []

    # Step 1: keyword results
    keyword_results = keyword_search(query, top_k=top_k)

    # Step 2: embedding results (optional)
    embedding_results: List[Dict[str, Any]] = []

    if (
        embedding_index is not None
        and hasattr(embedding_index, "is_ready")
        and embedding_index.is_ready()
    ):
        try:
            embedding_results = embedding_index.search(
                query=query,
                top_k=top_k,
            )
        except Exception:
            embedding_results = []

    # Step 3: merge & dedupe (keyword-first priority)
    merged: Dict[str, Dict[str, Any]] = {}

    for r in keyword_results:
        merged[r["id"]] = {
            "id": r["id"],
            "text": r["text"],
            "score": r.get("score", 0.0),
            "source": "keyword",
        }

    for r in embedding_results:
        if r["id"] not in merged:
            merged[r["id"]] = {
                "id": r["id"],
                "text": r["text"],
                "score": r.get("score", 0.0),
                "source": "embedding",
            }

    # Step 4: final ranking (score only, source-agnostic)
    results = list(merged.values())
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[: max(1, int(top_k))]


# -----------------------------
# Diagnostics (SAFE)
# -----------------------------
def info() -> Dict[str, Any]:
    """
    Diagnostic information.
    """
    return {
        "keyword_docs": len(__KEYWORD_DOCS),
        "embedding_ready": bool(
            embedding_index is not None
            and hasattr(embedding_index, "is_ready")
            and embedding_index.is_ready()
        ),
    }