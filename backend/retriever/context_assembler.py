from typing import List, Dict, Any
import threading

# -----------------------------
# Internal State
# -----------------------------
__LOCK = threading.Lock()


# -----------------------------
# Public API
# -----------------------------
def assemble_context(
    retrieved_docs: List[Dict[str, Any]],
    max_chars: int = 3000,
) -> Dict[str, Any]:
    """
    Assemble context from retrieved documents.

    Input format (per item):
    {
        "id": "doc_id",
        "text": "content",
        "score": float,
        "source": "keyword" | "embedding"
    }

    Output format:
    {
        "context": "final context string",
        "citations": [
            {"id": "doc_id", "index": 1},
            ...
        ]
    }

    Safety:
    - NEVER raises exception
    - Returns empty context on invalid input
    """
    if not isinstance(retrieved_docs, list) or max_chars <= 0:
        return {
            "context": "",
            "citations": [],
        }

    with __LOCK:
        try:
            used_ids = set()
            citations: List[Dict[str, Any]] = []
            context_parts: List[str] = []
            total_chars = 0
            cite_index = 1

            for d in retrieved_docs:
                if not isinstance(d, dict):
                    continue

                doc_id = d.get("id")
                text = d.get("text")

                if not doc_id or not text:
                    continue

                if doc_id in used_ids:
                    continue

                clean_text = str(text).strip()
                if not clean_text:
                    continue

                # Truncate if exceeding budget
                remaining = max_chars - total_chars
                if remaining <= 0:
                    break

                if len(clean_text) > remaining:
                    clean_text = clean_text[:remaining]

                # Append with citation marker
                block = f"[{cite_index}] {clean_text}"
                context_parts.append(block)

                citations.append(
                    {
                        "id": doc_id,
                        "index": cite_index,
                    }
                )

                used_ids.add(doc_id)
                total_chars += len(block)
                cite_index += 1

            return {
                "context": "\n\n".join(context_parts),
                "citations": citations,
            }

        except Exception:
            return {
                "context": "",
                "citations": [],
            }


# -----------------------------
# Diagnostics (SAFE)
# -----------------------------
def info() -> Dict[str, Any]:
    """
    Diagnostic information.
    """
    return {
        "module": "context_assembler",
        "thread_safe": True,
    }