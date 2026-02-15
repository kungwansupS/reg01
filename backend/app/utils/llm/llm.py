"""
LLM Module — Single-Pass Always-RAG Architecture (v3)

สถาปัตยกรรมใหม่:
  เดิม (v2): 2-5 LLM calls ต่อคำถาม
    - LLM #0: Memory summarization
    - LLM #1: Initial response + query_request decision
    - LLM #2: Intent analysis
    - LLM #3: LLM reranking
    - LLM #4: RAG response

  ใหม่ (v3): 1 LLM call ต่อคำถาม
    1. FAQ lookup (local)
    2. Rule-based intent analysis (local)
    3. Hybrid retrieval + cross-encoder reranking (local)
    4. Build unified prompt with context + sliding window history
    5. Single LLM call → answer

  ผลลัพธ์: ลด token usage 60-80%, ลด latency 50%+
"""
import asyncio
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langdetect import detect

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL_NAME,
    LLM_PROVIDER,
    LOCAL_MODEL_NAME,
    MAX_CONCURRENT_LLM_CALLS,
    OPENAI_MODEL_NAME,
    PDF_QUICK_USE_FOLDER,
)
from app.prompt.prompt import build_unified_prompt, context_prompt
from app.utils.llm.llm_model import get_llm_model
from app.utils.token_counter import count_tokens, format_token_usage, get_token_usage
from dev.flow_store import get_effective_flow_config
from dev.trace_store import record_trace
from memory.faq_cache import get_faq_answer, update_faq
from memory.greeting_cache import get_greeting_response
from memory.session import get_or_create_history, save_history
from retriever.context_selector import retrieve_top_k_chunks
from retriever.intent_analyzer import needs_retrieval

logger = logging.getLogger(__name__)
llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview_text(text: str, limit: int = 240) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[trimmed {len(value) - limit} chars]"


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _looks_out_of_scope_query(query: str) -> bool:
    normalized = _normalize_spaces(query).lower()
    weather_terms = ["อากาศ", "ฝน", "พยากรณ์", "อุณหภูมิ", "weather", "rain", "forecast"]
    return any(term in normalized for term in weather_terms)


def _format_retrieval_fallback(
    chunks: list[tuple[dict, float]],
    max_lines: int = 3,
    max_line_chars: int = 600,
) -> str:
    lines = []
    for chunk_data, _score in chunks[:max_lines]:
        value = _normalize_spaces(chunk_data.get("chunk", ""))
        if not value:
            continue
        if len(value) > max_line_chars:
            value = f"{value[:max_line_chars]}..."
        lines.append(f"- {value}")
    if not lines:
        return ""
    return (
        "ขออภัย ระบบสรุปอัตโนมัติขัดข้องชั่วคราว "
        "จึงแสดงข้อความจากเอกสารที่เกี่ยวข้องโดยตรง:\n"
        + "\n".join(lines)
    )


def _build_sliding_window_history(history: list, max_messages: int = 10) -> str:
    """
    Sliding window memory — ไม่ต้องเรียก LLM summarize
    แค่เอา N ข้อความล่าสุดมาแสดง
    """
    if not history:
        return ""
    recent = history[-max_messages:]
    lines = []
    for row in recent:
        role = row.get("role", "user")
        text = row.get("parts", [{}])[0].get("text", "")
        if not text.strip():
            continue
        label = "ผู้ใช้" if role == "user" else "พี่เร็ก"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


async def _emit_status(emit_fn, text: str) -> None:
    if not emit_fn:
        return
    try:
        await emit_fn("ai_status", {"status": text})
    except Exception:
        logger.debug("emit_fn failed for ai_status", exc_info=True)


async def ask_llm(
    msg: str,
    session_id: str,
    emit_fn=None,
    flow_config: Optional[Dict[str, Any]] = None,
    include_debug: bool = False,
    trace_source: str = "runtime",
):
    """
    Single-Pass Always-RAG Architecture (v3)

    Pipeline:
      1. FAQ lookup (local, instant)
      2. Rule-based retrieval decision (local, instant)
      3. Hybrid retrieval + cross-encoder reranking (local)
      4. Build unified prompt with context + sliding window history
      5. **Single LLM call** → answer
      6. FAQ auto-learn (local)

    Returns: {"text", "from_faq", "tokens", "trace_id", "debug"?}
    """
    active_flow = get_effective_flow_config(flow_config)
    rag_cfg = active_flow.get("rag", {})
    memory_cfg = active_flow.get("memory", {})
    prompt_cfg = active_flow.get("prompt", {})
    faq_cfg = active_flow.get("faq", {})

    trace_id = uuid.uuid4().hex
    trace_started_perf = time.perf_counter()
    trace_steps: list[Dict[str, Any]] = []
    trace_meta: Dict[str, Any] = {
        "trace_id": trace_id,
        "source": trace_source,
        "session_id": session_id,
        "message": str(msg or ""),
        "provider": LLM_PROVIDER,
        "started_at": _now_iso(),
        "status": "ok",
        "steps": trace_steps,
    }

    if include_debug:
        trace_meta["flow_config_snapshot"] = active_flow

    def step_start(node_id: str, title: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "node_id": node_id,
            "title": title,
            "started_perf": time.perf_counter(),
            "started_at": _now_iso(),
            "data": data or {},
        }

    def step_finish(step: Dict[str, Any], status: str = "ok", data: Optional[Dict[str, Any]] = None) -> None:
        merged_data = dict(step.get("data") or {})
        if data:
            merged_data.update(data)
        trace_steps.append({
            "node_id": step.get("node_id"),
            "title": step.get("title"),
            "status": status,
            "started_at": step.get("started_at"),
            "ended_at": _now_iso(),
            "latency_ms": round((time.perf_counter() - float(step.get("started_perf") or 0.0)) * 1000, 2),
            "data": merged_data,
        })

    primary_model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else (
        OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
    )

    # ── Step 0: Ingress ──────────────────────────────────────────────
    ingress_step = step_start("ingress", "Ingress Router", {
        "message_chars": len(msg or ""),
        "session_id": session_id,
        "source": trace_source,
        "architecture": "v3_single_pass",
    })
    step_finish(ingress_step, "ok")

    # ── Step 1: Language Detection ────────────────────────────────────
    detect_step = step_start("lang_detect", "Language Detect", {"detector": "langdetect"})
    try:
        detected_lang = await asyncio.to_thread(detect, msg)
        step_finish(detect_step, "ok", {"language": detected_lang})
    except Exception as lang_error:
        detected_lang = "th"
        step_finish(detect_step, "warn", {"language": detected_lang, "error": str(lang_error)})

    async with llm_semaphore:
        await _emit_status(emit_fn, "Processing request...")

        # ── Step 2: Session + Sliding Window History (no LLM call) ───
        session_step = step_start("session", "Session + Sliding Window")
        history = get_or_create_history(session_id)
        if not (history and history[-1]["parts"][0]["text"] == msg):
            history.append({"role": "user", "parts": [{"text": msg}]})
            await asyncio.to_thread(save_history, session_id, history)

        recent_messages = int(memory_cfg.get("recent_messages", 10))
        history_text = _build_sliding_window_history(history, max_messages=recent_messages)
        step_finish(session_step, "ok", {
            "history_total": len(history),
            "window_size": recent_messages,
            "history_chars": len(history_text),
            "method": "sliding_window",
        })

        # ── Step 3: Token usage tracking ─────────────────────────────
        total_token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached": False,
        }

        rag_debug: Dict[str, Any] = {
            "mode": "always_retrieve",
            "should_run": False,
            "query": msg,
            "retrieved": [],
        }

        # ── Step 4a: Tier 1 — Greeting Cache (exact match, 0 tokens) ──
        greeting_step = step_start("greeting_lookup", "Tier 1: Greeting Cache")
        greeting_reply = get_greeting_response(msg)
        if greeting_reply:
            reply = greeting_reply
            total_token_usage["cached"] = True
            step_finish(greeting_step, "ok", {"hit": True, "tier": 1})
            logger.info("[GREETING HIT] '%s' → instant response (0 tokens)", msg[:40])

            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.to_thread(save_history, session_id, history)

            trace_meta["status"] = "ok"
            trace_meta["ended_at"] = _now_iso()
            trace_meta["latency_ms"] = round((time.perf_counter() - trace_started_perf) * 1000, 2)
            trace_meta["tokens"] = total_token_usage
            trace_meta["detected_language"] = detected_lang
            trace_meta["rag"] = rag_debug
            record_trace(trace_meta)

            output = {"text": reply, "from_faq": True, "tokens": total_token_usage, "trace_id": trace_id}
            if include_debug:
                output["debug"] = {
                    "trace_id": trace_id, "detected_language": detected_lang,
                    "rag": rag_debug, "steps": trace_steps,
                    "flow_config_snapshot": active_flow,
                    "greeting_hit": True, "tier": 1,
                }
            return output
        step_finish(greeting_step, "skipped", {"hit": False})

        # ── Step 4b: Tier 2 — RAG FAQ Cache (exact match, 0 tokens) ──
        faq_lookup_step = step_start("faq_lookup", "Tier 2: RAG FAQ Cache")
        faq_lookup_enabled = bool(faq_cfg.get("lookup_enabled", True))

        faq_hit = None
        if faq_lookup_enabled:
            faq_hit = await asyncio.to_thread(
                get_faq_answer, msg,
                include_meta=True,
            )

        if isinstance(faq_hit, dict) and str(faq_hit.get("answer") or "").strip():
            reply = str(faq_hit["answer"]).strip()
            total_token_usage["cached"] = True
            step_finish(faq_lookup_step, "ok", {
                "hit": True, "tier": 2,
                "matched_question": faq_hit.get("question"),
                "score": faq_hit.get("score"),
                "last_validated": faq_hit.get("last_validated"),
                "ttl_seconds": faq_hit.get("ttl_seconds"),
            })

            logger.info("[FAQ HIT] exact match='%s' (0 tokens)", faq_hit.get("question", "")[:60])
            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.to_thread(save_history, session_id, history)

            trace_meta["status"] = "ok"
            trace_meta["ended_at"] = _now_iso()
            trace_meta["latency_ms"] = round((time.perf_counter() - trace_started_perf) * 1000, 2)
            trace_meta["tokens"] = total_token_usage
            trace_meta["detected_language"] = detected_lang
            trace_meta["rag"] = rag_debug
            record_trace(trace_meta)

            output = {"text": reply, "from_faq": True, "tokens": total_token_usage, "trace_id": trace_id}
            if include_debug:
                output["debug"] = {
                    "trace_id": trace_id, "detected_language": detected_lang,
                    "rag": rag_debug, "steps": trace_steps,
                    "flow_config_snapshot": active_flow, "faq_hit": faq_hit,
                    "tier": 2,
                }
            return output

        step_finish(faq_lookup_step, "skipped", {
            "hit": False, "lookup_enabled": faq_lookup_enabled,
            "reason": "lookup_disabled" if not faq_lookup_enabled else "exact_match_miss",
        })

        # ── Step 5: Retrieval Decision (rule-based, no LLM call) ─────
        should_retrieve = needs_retrieval(msg)
        rag_debug["should_run"] = should_retrieve

        # ── Step 6: Hybrid Retrieval + Cross-Encoder Reranking ───────
        context = ""
        top_chunks = []
        if should_retrieve:
            await _emit_status(emit_fn, "Retrieving context...")
            retrieve_step = step_start("retriever", "Hybrid Retriever + Cross-Encoder")
            try:
                top_chunks = await asyncio.to_thread(
                    retrieve_top_k_chunks, msg,
                    k=int(rag_cfg.get("top_k", 5)),
                    folder=PDF_QUICK_USE_FOLDER,
                    use_hybrid=bool(rag_cfg.get("use_hybrid", True)),
                    use_rerank=True,
                    use_intent_analysis=True,
                )
                retrieval_preview = []
                for idx, (chunk_data, score) in enumerate(top_chunks[:8]):
                    retrieval_preview.append({
                        "rank": idx + 1,
                        "score": round(float(score), 4),
                        "source": chunk_data.get("source", ""),
                        "index": chunk_data.get("index"),
                        "chunk_preview": _preview_text(chunk_data.get("chunk", ""), 240),
                    })
                rag_debug["retrieved"] = retrieval_preview
                context = "\n\n".join([chunk["chunk"] for chunk, _ in top_chunks])
                step_finish(retrieve_step, "ok", {"count": len(top_chunks), "preview": retrieval_preview})
            except Exception as ret_err:
                logger.warning("Retrieval error: %s", ret_err)
                step_finish(retrieve_step, "warn", {"error": str(ret_err)})

        # ── Step 7: Build Unified Prompt (single prompt for everything) ──
        prompt_step = step_start("prompt", "Unified Prompt Builder")
        extra_instruction = str(prompt_cfg.get("extra_context_instruction") or "").strip()

        if should_retrieve and context:
            full_prompt = build_unified_prompt(
                question=msg,
                context=context,
                history_text=history_text,
                detected_lang=detected_lang,
            )
        else:
            full_prompt = context_prompt(msg)
            if history_text:
                full_prompt = f"{full_prompt}\n\nประวัติการสนทนา:\n{history_text}"

        if extra_instruction:
            full_prompt += f"\n\n[Developer Instruction]\n{extra_instruction}"

        step_finish(prompt_step, "ok", {
            "prompt_chars": len(full_prompt),
            "prompt_tokens_est": count_tokens(full_prompt, primary_model_name),
            "has_context": bool(context),
            "language": detected_lang,
        })

        # ── Step 8: Single LLM Call (with retry for rate limits) ─────
        try:
            model = get_llm_model()
            llm_step = step_start("llm_call", "LLM Call (Single Pass)", {"provider": LLM_PROVIDER})

            max_retries = 3
            reply = ""
            usage = {}
            last_error = None
            for attempt in range(max_retries):
                try:
                    if LLM_PROVIDER == "gemini":
                        response = await asyncio.to_thread(
                            model.models.generate_content,
                            model=GEMINI_MODEL_NAME,
                            contents=full_prompt,
                        )
                        reply = (response.text or "").strip()
                        prompt_tokens = count_tokens(full_prompt, GEMINI_MODEL_NAME)
                        completion_tokens = count_tokens(reply, GEMINI_MODEL_NAME)
                        usage = {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        }
                    else:
                        model_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                        response = await model.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": full_prompt}],
                        )
                        reply = (response.choices[0].message.content or "").strip()
                        usage = get_token_usage(response, LLM_PROVIDER, model_name)
                    last_error = None
                    break  # Success
                except Exception as retry_exc:
                    last_error = retry_exc
                    err_msg = str(retry_exc).lower()
                    is_rate_limit = any(t in err_msg for t in ["429", "rate limit", "rate_limit", "too many", "quota"])
                    if is_rate_limit and attempt < max_retries - 1:
                        wait_sec = min(15.0 * (attempt + 1), 30.0)
                        logger.warning(f"Rate limit hit (attempt {attempt+1}/{max_retries}), waiting {wait_sec:.0f}s...")
                        await asyncio.sleep(wait_sec)
                        continue
                    if not is_rate_limit:
                        raise  # Non-rate-limit error: raise immediately
                    # Last attempt + rate limit → fall through to Gemini fallback

            # ── Gemini Fallback: if primary provider rate-limited ─────
            if last_error is not None and LLM_PROVIDER != "gemini" and GEMINI_API_KEY:
                try:
                    from google import genai
                    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                    gemini_model = GEMINI_MODEL_NAME or "gemini-2.0-flash"
                    logger.warning(f"Falling back to Gemini ({gemini_model}) after rate limit...")
                    response = await asyncio.to_thread(
                        gemini_client.models.generate_content,
                        model=gemini_model,
                        contents=full_prompt,
                    )
                    reply = (response.text or "").strip()
                    prompt_tokens = count_tokens(full_prompt, gemini_model)
                    completion_tokens = count_tokens(reply, gemini_model)
                    usage = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "fallback_provider": "gemini",
                    }
                    last_error = None  # Successfully fell back
                except Exception as gemini_exc:
                    logger.error(f"Gemini fallback also failed: {gemini_exc}")
                    raise  # Will trigger the outer except block

            if last_error is not None:
                raise last_error

            total_token_usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
            total_token_usage["completion_tokens"] += int(usage.get("completion_tokens", 0))
            total_token_usage["total_tokens"] += int(usage.get("total_tokens", 0))

            logger.info(f"[LLM Single Pass] {format_token_usage(usage)}")
            step_finish(llm_step, "ok", {"usage": usage, "reply_preview": _preview_text(reply)})

            # ── Step 9: FAQ Auto Learn ───────────────────────────────
            if should_retrieve and top_chunks and bool(faq_cfg.get("auto_learn", True)):
                faq_step = step_start("faq_learn", "FAQ Auto Learn")
                top_score = float(top_chunks[0][1]) if top_chunks else 0.0
                learn_meta = {
                    "source": "rag",
                    "require_retrieval": True,
                    "retrieval_count": len(top_chunks),
                    "retrieval_top_score": top_score,
                    "min_retrieval_score": faq_cfg.get("min_retrieval_score", 0.35),
                    "min_answer_chars": faq_cfg.get("min_answer_chars", 30),
                    "ttl_seconds": 86400,  # 24h TTL, refreshed daily
                }
                faq_update_result = await asyncio.to_thread(update_faq, msg, reply, learn_meta)
                step_finish(
                    faq_step,
                    "ok" if bool(faq_update_result.get("updated")) else "skipped",
                    faq_update_result,
                )

            # ── Step 10: Finalize ────────────────────────────────────
            logger.info(f"[Total Token Usage] {format_token_usage(total_token_usage)}")
            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.to_thread(save_history, session_id, history)

            trace_meta["status"] = "ok"
            trace_meta["ended_at"] = _now_iso()
            trace_meta["latency_ms"] = round((time.perf_counter() - trace_started_perf) * 1000, 2)
            trace_meta["tokens"] = total_token_usage
            trace_meta["detected_language"] = detected_lang
            trace_meta["rag"] = rag_debug
            record_trace(trace_meta)

            output = {"text": reply, "from_faq": False, "tokens": total_token_usage, "trace_id": trace_id}
            if include_debug:
                output["debug"] = {
                    "trace_id": trace_id, "detected_language": detected_lang,
                    "rag": rag_debug, "steps": trace_steps,
                    "flow_config_snapshot": active_flow,
                }
            return output

        except Exception as exc:
            # ── Fallback: deterministic response when LLM fails ──────
            logger.error("LLM Error: %s", exc, exc_info=True)
            fallback_step = step_start("fallback", "Deterministic Fallback", {"error": str(exc)})
            fallback_debug: Dict[str, Any] = {"mode": "generic_error"}
            fallback_message = ""

            try:
                if _looks_out_of_scope_query(msg):
                    fallback_message = "ไม่พบข้อมูลเรื่องนี้ในเอกสารที่ระบบมีอยู่ตอนนี้ครับ"
                    fallback_debug["mode"] = "out_of_scope_guard"
                elif top_chunks:
                    fallback_message = _format_retrieval_fallback(top_chunks)
                    if fallback_message:
                        fallback_debug["mode"] = "retrieval_excerpt"

                if not fallback_message and not _looks_out_of_scope_query(msg):
                    try:
                        fallback_chunks = await asyncio.to_thread(
                            retrieve_top_k_chunks, msg,
                            k=3, folder=PDF_QUICK_USE_FOLDER,
                            use_hybrid=True, use_rerank=False, use_intent_analysis=False,
                        )
                        fallback_message = _format_retrieval_fallback(fallback_chunks)
                        if fallback_message:
                            fallback_debug["mode"] = "retrieval_excerpt"
                    except Exception:
                        pass

                if not fallback_message:
                    fallback_message = "ขออภัยครับ ระบบขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้งนะครับ"
                step_finish(fallback_step, "warn", fallback_debug)
            except Exception as fallback_exc:
                logger.error("Fallback Error: %s", fallback_exc, exc_info=True)
                fallback_message = "ขออภัยครับ ระบบขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้งนะครับ"
                step_finish(fallback_step, "error", {"fallback_error": str(fallback_exc)})

            error_tokens = {
                "prompt_tokens": 0,
                "completion_tokens": count_tokens(fallback_message, primary_model_name),
                "total_tokens": count_tokens(fallback_message, primary_model_name),
                "error": True,
            }

            trace_meta["status"] = "error"
            trace_meta["error"] = str(exc)
            trace_meta["ended_at"] = _now_iso()
            trace_meta["latency_ms"] = round((time.perf_counter() - trace_started_perf) * 1000, 2)
            trace_meta["tokens"] = error_tokens
            trace_meta["detected_language"] = detected_lang
            trace_meta["rag"] = rag_debug
            record_trace(trace_meta)

            output = {"text": fallback_message, "from_faq": False, "tokens": error_tokens, "trace_id": trace_id}
            if include_debug:
                output["debug"] = {
                    "trace_id": trace_id, "detected_language": detected_lang,
                    "rag": rag_debug, "steps": trace_steps,
                    "flow_config_snapshot": active_flow,
                    "error": str(exc), "fallback": fallback_debug,
                }
            return output

