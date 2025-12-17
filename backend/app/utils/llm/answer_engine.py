from typing import Dict, Any
import threading

# Optional dependencies (ALL SAFE)
try:
    from backend.retriever import retrieval_engine
except Exception:
    retrieval_engine = None

try:
    from backend.app.utils.llm import llm
except Exception:
    llm = None


# -----------------------------
# Internal State
# -----------------------------
__LOCK = threading.Lock()

# -----------------------------
# Strict System Prompt (2026-style)
# -----------------------------
SYSTEM_PROMPT = (
    "คุณเป็นเจ้าหน้าที่ทะเบียน\n"
    "ตอบคำถามโดยอ้างอิงจากข้อมูลที่ให้เท่านั้น\n"
    "ห้ามเดา ห้ามเพิ่มข้อมูลนอกเหนือจากเอกสาร\n"
    "ถ้าไม่พบข้อมูล ให้ตอบว่า \"ไม่พบข้อมูลในเอกสาร\"\n"
)

# -----------------------------
# Public API (SAFE)
# -----------------------------
def answer_question(
    question: str,
    top_k: int = 3,
    max_chars: int = 3000,
) -> Dict[str, Any]:
    """
    Generate answer using STRICT prompt and retrieved context.

    Output format (ALWAYS):
    {
        "answer": str,
        "citations": list,
        "meta": {
            "used_llm": bool,
            "cached_context": bool
        }
    }

    Safety:
    - NEVER raises exception
    - Deterministic behavior
    """
    if not question or not isinstance(question, str):
        return {
            "answer": "ไม่พบข้อมูลในเอกสาร",
            "citations": [],
            "meta": {
                "used_llm": False,
                "cached_context": False,
            },
        }

    # 1) Retrieve context (Phase 4)
    context_result = {
        "context": "",
        "citations": [],
        "meta": {"cached": False},
    }

    if retrieval_engine is not None:
        try:
            context_result = retrieval_engine.retrieve_context(
                query=question,
                top_k=top_k,
                max_chars=max_chars,
            )
        except Exception:
            pass

    context_text = context_result.get("context", "")
    citations = context_result.get("citations", [])
    cached_context = bool(context_result.get("meta", {}).get("cached"))

    # If no context → deterministic fallback
    if not context_text:
        return {
            "answer": "ไม่พบข้อมูลในเอกสาร",
            "citations": [],
            "meta": {
                "used_llm": False,
                "cached_context": cached_context,
            },
        }

    # 2) Build strict prompt
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"ข้อมูล:\n{context_text}\n\n"
        f"คำถาม:\n{question}\n\n"
        f"คำตอบ:"
    )

    # 3) Call LLM (SAFE)
    if llm is None or not hasattr(llm, "ask"):
        return {
            "answer": "ไม่พบข้อมูลในเอกสาร",
            "citations": citations,
            "meta": {
                "used_llm": False,
                "cached_context": cached_context,
            },
        }

    try:
        with __LOCK:
            response = llm.ask(prompt)
            answer_text = str(response).strip()
            if not answer_text:
                answer_text = "ไม่พบข้อมูลในเอกสาร"
    except Exception:
        answer_text = "ไม่พบข้อมูลในเอกสาร"

    return {
        "answer": answer_text,
        "citations": citations,
        "meta": {
            "used_llm": True,
            "cached_context": cached_context,
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
        "module": "answer_engine",
        "strict_prompt": True,
        "llm_available": llm is not None,
        "retrieval_available": retrieval_engine is not None,
    }