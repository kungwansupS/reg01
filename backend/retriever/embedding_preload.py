from typing import List, Dict, Any
import os
import threading

# Optional embedding index (SAFE)
try:
    from backend.retriever import embedding_index
except Exception:
    embedding_index = None

# -----------------------------
# Internal State
# -----------------------------
__LOCK = threading.Lock()

# -----------------------------
# Utilities
# -----------------------------
def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _chunk_text(text: str, max_chars: int = 500) -> List[str]:
    """
    Deterministic text chunking by character length.
    """
    if not text or max_chars <= 0:
        return []

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + max_chars, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end

    return chunks


# -----------------------------
# Public API
# -----------------------------
def build_documents_from_quick_use(
    base_dir: str,
    max_chars_per_chunk: int = 500,
) -> List[Dict[str, str]]:
    """
    Scan quick_use directory and build embedding documents.

    Output format:
    [
        {"id": "file_chunkIndex", "text": "chunk text"},
        ...
    ]
    """
    documents: List[Dict[str, str]] = []

    if not base_dir or not os.path.isdir(base_dir):
        return documents

    for root, _, files in os.walk(base_dir):
        for name in files:
            if not name.lower().endswith(".txt"):
                continue

            file_path = os.path.join(root, name)
            rel_path = os.path.relpath(file_path, base_dir)

            text = _read_text_file(file_path)
            if not text:
                continue

            chunks = _chunk_text(text, max_chars=max_chars_per_chunk)
            for idx, chunk in enumerate(chunks, start=1):
                documents.append(
                    {
                        "id": f"{rel_path.replace(os.sep, '_')}_{idx}",
                        "text": chunk,
                    }
                )

    return documents


def preload_embeddings(
    quick_use_dir: str,
    model_name: str = "google/embeddinggemma-300m",
    max_chars_per_chunk: int = 500,
) -> bool:
    """
    Preload embeddings into embedding_index.

    Safety:
    - NEVER raises exception
    - Returns False on any failure
    - Does nothing if embedding_index unavailable
    """
    if embedding_index is None:
        return False

    with __LOCK:
        try:
            docs = build_documents_from_quick_use(
                base_dir=quick_use_dir,
                max_chars_per_chunk=max_chars_per_chunk,
            )
            if not docs:
                return False

            return embedding_index.initialize(
                documents=docs,
                model_name=model_name,
            )
        except Exception:
            return False


# -----------------------------
# Diagnostics (SAFE)
# -----------------------------
def info() -> Dict[str, Any]:
    """
    Diagnostic information.
    """
    return {
        "module": "embedding_preload",
        "embedding_index_available": embedding_index is not None,
    }