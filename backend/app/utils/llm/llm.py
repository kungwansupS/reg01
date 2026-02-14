import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langdetect import detect

from app.config import (
    GEMINI_MODEL_NAME,
    LLM_PROVIDER,
    LOCAL_MODEL_NAME,
    MAX_CONCURRENT_LLM_CALLS,
    OPENAI_MODEL_NAME,
    PDF_QUICK_USE_FOLDER,
)
from app.prompt.prompt import context_prompt
from app.prompt.request_prompt import get_request_prompt
from app.utils.llm.llm_model import get_llm_model
from app.utils.token_counter import count_tokens, format_token_usage, get_token_usage
from dev.flow_store import get_effective_flow_config
from dev.trace_store import record_trace
from memory.faq_cache import update_faq
from memory.memory import summarize_chat_history
from memory.session import get_or_create_history, save_history
from retriever.context_selector import retrieve_top_k_chunks

logger = logging.getLogger(__name__)
llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview_text(text: str, limit: int = 240) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[trimmed {len(value) - limit} chars]"


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
    Main LLM function with token tracking and optional debug tracing.
    Returns:
    {
        "text": str,
        "from_faq": bool,
        "tokens": dict,
        "trace_id": str,
        "debug": dict (optional)
    }
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

    def step_finish(
        step: Dict[str, Any],
        status: str = "ok",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        merged_data = dict(step.get("data") or {})
        if data:
            merged_data.update(data)
        trace_steps.append(
            {
                "node_id": step.get("node_id"),
                "title": step.get("title"),
                "status": status,
                "started_at": step.get("started_at"),
                "ended_at": _now_iso(),
                "latency_ms": round((time.perf_counter() - float(step.get("started_perf") or 0.0)) * 1000, 2),
                "data": merged_data,
            }
        )

    ingress_step = step_start(
        "ingress",
        "Ingress Router",
        {
            "message_chars": len(msg or ""),
            "session_id": session_id,
            "source": trace_source,
        },
    )
    step_finish(ingress_step, "ok")

    detect_step = step_start("prompt", "Language Detect", {"detector": "langdetect"})
    try:
        detected_lang = await asyncio.to_thread(detect, msg)
        step_finish(detect_step, "ok", {"language": detected_lang})
    except Exception as lang_error:
        detected_lang = "th"
        step_finish(detect_step, "warn", {"language": detected_lang, "error": str(lang_error)})

    request_prompt = get_request_prompt(detected_lang)

    async with llm_semaphore:
        await _emit_status(emit_fn, "Processing request...")

        session_step = step_start("session", "Session + Memory")
        history = get_or_create_history(session_id)
        if not (history and history[-1]["parts"][0]["text"] == msg):
            history.append({"role": "user", "parts": [{"text": msg}]})
            await asyncio.to_thread(save_history, session_id, history)

        recent_messages = int(memory_cfg.get("recent_messages", 10))
        old_messages = history[:-recent_messages]
        latest_messages = history[-recent_messages:]

        if memory_cfg.get("enable_summary", True):
            summary = await asyncio.to_thread(summarize_chat_history, old_messages)
        else:
            summary = ""

        history_text = "\n".join([f"{row['role']}: {row['parts'][0]['text']}" for row in latest_messages])
        step_finish(
            session_step,
            "ok",
            {
                "history_total": len(history),
                "recent_messages": len(latest_messages),
                "old_messages": len(old_messages),
                "summary_chars": len(summary),
                "summary_enabled": bool(memory_cfg.get("enable_summary", True)),
            },
        )

        prompt_step = step_start("prompt", "Prompt Builder")
        full_prompt = f"{context_prompt(msg)}\n{summary}\n{history_text}\nQuestion: {msg}"
        extra_instruction = str(prompt_cfg.get("extra_context_instruction") or "").strip()
        if extra_instruction:
            full_prompt += f"\n\n[Developer Instruction]\n{extra_instruction}"

        primary_model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else (
            OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
        )
        step_finish(
            prompt_step,
            "ok",
            {
                "prompt_chars": len(full_prompt),
                "prompt_tokens_est": count_tokens(full_prompt, primary_model_name),
                "extra_instruction_chars": len(extra_instruction),
                "language": detected_lang,
            },
        )

        total_token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached": False,
        }

        rag_debug: Dict[str, Any] = {
            "mode": str(rag_cfg.get("mode", "keyword")).lower(),
            "should_run": False,
            "query": "",
            "retrieved": [],
        }

        try:
            model = get_llm_model()
            llm1_step = step_start("llm_primary", "LLM Call #1", {"provider": LLM_PROVIDER})

            if LLM_PROVIDER == "gemini":
                response = await asyncio.to_thread(
                    model.models.generate_content,
                    model=GEMINI_MODEL_NAME,
                    contents=full_prompt,
                )
                reply = (response.text or "").strip()

                prompt_tokens = count_tokens(full_prompt, GEMINI_MODEL_NAME)
                completion_tokens = count_tokens(reply, GEMINI_MODEL_NAME)
                usage_1 = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                }
                logger.info(f"[Gemini Call 1] {format_token_usage(usage_1)}")
            else:
                model_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                response = await model.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": full_prompt}],
                )
                reply = (response.choices[0].message.content or "").strip()
                usage_1 = get_token_usage(response, LLM_PROVIDER, model_name)
                logger.info(f"[{LLM_PROVIDER.upper()} Call 1] {format_token_usage(usage_1)}")

            total_token_usage["prompt_tokens"] += int(usage_1.get("prompt_tokens", 0))
            total_token_usage["completion_tokens"] += int(usage_1.get("completion_tokens", 0))
            total_token_usage["total_tokens"] += int(usage_1.get("total_tokens", 0))
            step_finish(
                llm1_step,
                "ok",
                {
                    "usage": usage_1,
                    "reply_preview": _preview_text(reply),
                },
            )

            rag_mode = rag_debug["mode"]
            should_run_rag = False
            search_query = ""
            if rag_mode == "always":
                should_run_rag = True
                search_query = msg
            elif rag_mode == "keyword" and "query_request" in reply:
                should_run_rag = True
                search_query = reply.split("query_request", 1)[1].strip()

            rag_debug["should_run"] = should_run_rag
            rag_debug["query"] = search_query or msg
            rag_gate_step = step_start("rag_gate", "RAG Decision Gate")
            step_finish(
                rag_gate_step,
                "ok",
                {
                    "mode": rag_mode,
                    "should_run": should_run_rag,
                    "query": search_query or msg,
                    "top_k": int(rag_cfg.get("top_k", 5)),
                },
            )

            if should_run_rag:
                await _emit_status(emit_fn, "Retrieving context...")
                retrieve_step = step_start("retriever", "Hybrid Retriever")
                top_chunks = await asyncio.to_thread(
                    retrieve_top_k_chunks,
                    search_query or msg,
                    k=int(rag_cfg.get("top_k", 5)),
                    folder=PDF_QUICK_USE_FOLDER,
                    use_hybrid=bool(rag_cfg.get("use_hybrid", True)),
                    use_llm_rerank=bool(rag_cfg.get("use_llm_rerank", True)),
                    use_intent_analysis=bool(rag_cfg.get("use_intent_analysis", True)),
                )

                retrieval_preview = []
                for idx, (chunk_data, score) in enumerate(top_chunks[:8]):
                    retrieval_preview.append(
                        {
                            "rank": idx + 1,
                            "score": round(float(score), 4),
                            "source": chunk_data.get("source", ""),
                            "index": chunk_data.get("index"),
                            "chunk_preview": _preview_text(chunk_data.get("chunk", ""), 240),
                        }
                    )
                rag_debug["retrieved"] = retrieval_preview
                step_finish(
                    retrieve_step,
                    "ok",
                    {
                        "count": len(top_chunks),
                        "preview": retrieval_preview,
                    },
                )

                context = "\n\n".join([chunk["chunk"] for chunk, _ in top_chunks])
                prompt_rag = request_prompt(
                    question=msg,
                    search_query=search_query or msg,
                    context=context,
                )

                llm2_step = step_start("llm_rag", "LLM Call #2 (RAG)")
                if LLM_PROVIDER == "gemini":
                    response_rag = await asyncio.to_thread(
                        model.models.generate_content,
                        model=GEMINI_MODEL_NAME,
                        contents=prompt_rag,
                    )
                    reply = (response_rag.text or "").strip()
                    usage_rag = {
                        "prompt_tokens": count_tokens(prompt_rag, GEMINI_MODEL_NAME),
                        "completion_tokens": count_tokens(reply, GEMINI_MODEL_NAME),
                    }
                    usage_rag["total_tokens"] = usage_rag["prompt_tokens"] + usage_rag["completion_tokens"]
                    logger.info(f"[Gemini Call 2 RAG] {format_token_usage(usage_rag)}")
                else:
                    model_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                    response_rag = await model.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt_rag}],
                    )
                    reply = (response_rag.choices[0].message.content or "").strip()
                    usage_rag = get_token_usage(response_rag, LLM_PROVIDER, model_name)
                    logger.info(f"[{LLM_PROVIDER.upper()} Call 2 RAG] {format_token_usage(usage_rag)}")

                total_token_usage["prompt_tokens"] += int(usage_rag.get("prompt_tokens", 0))
                total_token_usage["completion_tokens"] += int(usage_rag.get("completion_tokens", 0))
                total_token_usage["total_tokens"] += int(usage_rag.get("total_tokens", 0))
                step_finish(
                    llm2_step,
                    "ok",
                    {
                        "usage": usage_rag,
                        "prompt_chars": len(prompt_rag),
                        "reply_preview": _preview_text(reply),
                    },
                )

                faq_step = step_start("faq_learn", "FAQ Auto Learn")
                should_learn_faq = (
                    bool(faq_cfg.get("auto_learn", True))
                    and len(reply) > 20
                    and "ไม่พบข้อมูล" not in reply
                )
                if should_learn_faq:
                    await asyncio.to_thread(update_faq, msg, reply)
                    step_finish(faq_step, "ok", {"updated": True})
                else:
                    step_finish(
                        faq_step,
                        "skipped",
                        {
                            "updated": False,
                            "reason": "auto_learn_off_or_reply_filtered",
                        },
                    )

            post_step = step_start("answer_post", "Answer Post-Process")
            step_finish(
                post_step,
                "ok",
                {
                    "reply_chars": len(reply),
                    "reply_preview": _preview_text(reply),
                },
            )

            output_step = step_start("output", "Output Emit + TTS + Logs")
            step_finish(
                output_step,
                "ok",
                {
                    "tokens_total": total_token_usage["total_tokens"],
                    "tokens_prompt": total_token_usage["prompt_tokens"],
                    "tokens_completion": total_token_usage["completion_tokens"],
                },
            )

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

            output = {
                "text": reply,
                "from_faq": False,
                "tokens": total_token_usage,
                "trace_id": trace_id,
            }
            if include_debug:
                output["debug"] = {
                    "trace_id": trace_id,
                    "detected_language": detected_lang,
                    "rag": rag_debug,
                    "steps": trace_steps,
                    "flow_config_snapshot": active_flow,
                }
            return output

        except Exception as exc:
            logger.error("LLM Error: %s", exc, exc_info=True)
            error_message = "ขออภัย ระบบขัดข้องชั่วคราว"
            error_tokens = {
                "prompt_tokens": 0,
                "completion_tokens": count_tokens(error_message, primary_model_name),
                "total_tokens": count_tokens(error_message, primary_model_name),
                "error": True,
            }

            error_step = step_start("output", "Output Emit + TTS + Logs")
            step_finish(
                error_step,
                "error",
                {
                    "error": str(exc),
                    "reply_preview": error_message,
                },
            )

            trace_meta["status"] = "error"
            trace_meta["error"] = str(exc)
            trace_meta["ended_at"] = _now_iso()
            trace_meta["latency_ms"] = round((time.perf_counter() - trace_started_perf) * 1000, 2)
            trace_meta["tokens"] = error_tokens
            trace_meta["detected_language"] = detected_lang
            trace_meta["rag"] = rag_debug
            record_trace(trace_meta)

            output = {
                "text": error_message,
                "from_faq": False,
                "tokens": error_tokens,
                "trace_id": trace_id,
            }
            if include_debug:
                output["debug"] = {
                    "trace_id": trace_id,
                    "detected_language": detected_lang,
                    "rag": rag_debug,
                    "steps": trace_steps,
                    "flow_config_snapshot": active_flow,
                    "error": str(exc),
                }
            return output
