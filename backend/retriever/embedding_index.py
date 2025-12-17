from typing import List, Dict, Optional, Any
import os
import threading

# -----------------------------
# Internal State (Isolated)
# -----------------------------
__LOCK = threading.Lock()
__INDEX_READY = False
__DOCS: List[Dict[str, Any]] = []
__EMBEDDER = None
__EMBEDDING_DIM = None


# -----------------------------
# Public API (SAFE, OPTIONAL)
# -----------------------------
def is_ready() -> bool:
    """
    Check whether the embedding index has been initialized.
    Safe to call at any time.
    """
    return __INDEX_READY


def size() -> int:
    """
    Return number of indexed documents.
    Safe to call at any time.
    """
    return len(__DOCS)


def initialize(
    documents: Optional[List[Dict[str, str]]] = None,
    model_name: str = "google/embeddinggemma-300m",
) -> bool:
    """
    Initialize embedding index.
    This function is SAFE:
    - Does nothing if dependencies are missing.
    - Returns False instead of raising errors.
    - Does NOT auto-run on import.

    documents format:
    [
        {"id": "doc_id", "text": "content"},
        ...
    ]
    """
    global __INDEX_READY, __DOCS, __EMBEDDER, __EMBEDDING_DIM

    if documents is None or not isinstance(documents, list):
        return False

    with __LOCK:
        if __INDEX_READY:
            return True

        try:
            # Lazy import to avoid hard dependency
            from transformers import AutoTokenizer, AutoModel
            import torch
        except Exception:
            # Dependency not available → safe failure
            return False

        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name)
            model.eval()

            def _embed(text: str):
                inputs = tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                )
                with torch.no_grad():
                    outputs = model(**inputs)
                vec = outputs.last_hidden_state.mean(dim=1)
                return vec

            # Build index
            indexed_docs: List[Dict[str, Any]] = []
            dim = None

            for d in documents:
                if not isinstance(d, dict):
                    continue
                text = d.get("text")
                doc_id = d.get("id")
                if not text or not doc_id:
                    continue

                vec = _embed(text)
                if dim is None:
                    dim = int(vec.shape[-1])

                indexed_docs.append(
                    {
                        "id": doc_id,
                        "text": text,
                        "vector": vec,
                    }
                )

            __DOCS = indexed_docs
            __EMBEDDER = _embed
            __EMBEDDING_DIM = dim
            __INDEX_READY = True
            return True

        except Exception:
            # Any unexpected failure → rollback to safe state
            __DOCS = []
            __EMBEDDER = None
            __EMBEDDING_DIM = None
            __INDEX_READY = False
            return False


def search(
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Semantic search over embedded documents.

    Safety guarantees:
    - Never raises exceptions.
    - Returns empty list if index not ready.
    - Does NOT mutate state.
    """
    if not __INDEX_READY:
        return []

    if not query or not isinstance(query, str):
        return []

    try:
        import torch
        from torch.nn.functional import cosine_similarity
    except Exception:
        return []

    try:
        q_vec = __EMBEDDER(query)

        scored: List[Dict[str, Any]] = []
        for d in __DOCS:
            score = cosine_similarity(q_vec, d["vector"]).item()
            scored.append(
                {
                    "id": d["id"],
                    "text": d["text"],
                    "score": score,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: max(1, int(top_k))]

    except Exception:
        return []


# -----------------------------
# Diagnostic (Optional, Safe)
# -----------------------------
def info() -> Dict[str, Any]:
    """
    Return internal diagnostic info.
    Safe for logging/debugging.
    """
    return {
        "ready": __INDEX_READY,
        "documents": len(__DOCS),
        "embedding_dim": __EMBEDDING_DIM,
    }