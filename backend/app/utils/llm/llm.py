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
from memory.faq_cache import get_faq_answer, update_faq
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


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _looks_out_of_scope_query(query: str) -> bool:
    normalized = _normalize_spaces(query).lower()
    weather_terms = ["อากาศ", "ฝน", "พยากรณ์", "อุณหภูมิ", "weather", "rain", "forecast"]
    return any(term in normalized for term in weather_terms)


def _format_retrieval_fallback(
    chunks: list[tuple[dict, float]],
    max_lines: int = 2,
    max_line_chars: int = 360,
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


def _extract_year_from_query(query: str) -> str:
    m = re.search(r"\b25\d{2}\b", str(query or ""))
    return m.group(0) if m else ""


def _extract_semester_from_query(query: str) -> str:
    text = _normalize_spaces(query).lower()
    if re.search(r"(ภาคเรียนที่|ภาคการศึกษาที่|เทอม)\s*1", text) or re.search(r"1/25\d{2}", text):
        return "1"
    if re.search(r"(ภาคเรียนที่|ภาคการศึกษาที่|เทอม)\s*2", text) or re.search(r"2/25\d{2}", text):
        return "2"
    if re.search(r"(ภาคเรียนที่|ภาคการศึกษาที่|เทอม)\s*3", text) or re.search(r"3/25\d{2}", text):
        return "3"
    return ""


def _build_query_keywords(query: str) -> list[str]:
    normalized = _normalize_spaces(query).lower()
    keywords: list[str] = []
    phrase_map = [
        (["เปิดภาค", "เข้าชั้นเรียน"], ["เปิดภาคการศึกษา", "เข้าชั้นเรียน"]),
        (["ชำระ", "ค่าธรรมเนียม"], ["ชำระเงินค่าธรรมเนียม", "ชำระเงิน", "ค่าธรรมเนียม"]),
        (["สอบกลางภาค"], ["สอบกลางภาค"]),
        (["ไม่ได้รับ w"], ["ไม่ได้รับ w", "ไม่ผ่านเงื่อนไข"]),
        (["ได้รับ w"], ["ได้รับ w"]),
        (["ถอน", "กระบวนวิชา"], ["ถอนกระบวนวิชา", "ถอน"]),
        (["qr"], ["qr code", "23.00", "23:00"]),
        (["บัตรเครดิต"], ["บัตรเครดิต", "กองคลัง", "16.30", "16:30"]),
    ]
    for triggers, mapped in phrase_map:
        if all(trigger in normalized for trigger in triggers):
            keywords.extend(mapped)

    if not keywords:
        rough_tokens = [token for token in re.split(r"[^0-9A-Za-z\u0E00-\u0E7F]+", normalized) if len(token) >= 3]
        keywords.extend(rough_tokens[:8])
    return list(dict.fromkeys(keywords))


def _search_local_text_fallback(query: str, folder: str, max_lines: int = 3) -> list[str]:
    if not os.path.exists(folder):
        return []

    query_text = _normalize_spaces(query)
    query_lower = query_text.lower()
    query_year = _extract_year_from_query(query_text)
    query_semester = _extract_semester_from_query(query_text)
    keywords = _build_query_keywords(query_text)
    date_like_query = any(token in query_lower for token in ["วันไหน", "ช่วงไหน", "กี่โมง", "เปิดภาค", "สอบกลางภาค", "ถอน", "ชำระ"])
    date_detail_pattern = re.compile(
        r"\d{1,2}\s*-\s*\d{1,2}"
        r"|\d{1,2}[:.]\d{2}"
        r"|\d{1,2}\s*(มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)"
    )

    scored_segments: list[tuple[int, str]] = []
    for root, _, files in os.walk(folder):
        for filename in sorted(files):
            if not filename.endswith(".txt"):
                continue
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            content_norm = _normalize_spaces(content)
            if query_year and query_year not in content_norm:
                continue

            segments = re.split(r"(?:=+|\n+)", content)
            for raw in segments:
                segment = _normalize_spaces(raw)
                if len(segment) < 20:
                    continue
                segment_lower = segment.lower()
                if date_like_query and not date_detail_pattern.search(segment):
                    continue
                score = 0
                if query_year and query_year in segment:
                    score += 3
                if query_semester and (
                    f"ภาคการศึกษาที่ {query_semester}" in segment_lower
                    or f"ภาคเรียนที่ {query_semester}" in segment_lower
                    or (query_year and f"{query_semester}/{query_year}" in segment_lower)
                ):
                    score += 3
                for kw in keywords:
                    if kw and kw in segment_lower:
                        score += 2
                if date_like_query and re.search(r"\d{1,2}[:.]\d{2}|\d{1,2}\s*-\s*\d{1,2}", segment):
                    score += 2

                if score >= 4:
                    scored_segments.append((score, segment))

    scored_segments.sort(key=lambda row: (row[0], -len(row[1])), reverse=True)
    result = []
    seen = set()
    for _score, segment in scored_segments:
        key = segment.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(segment)
        if len(result) >= max_lines:
            break
    return result


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

        faq_lookup_step = step_start("faq_lookup", "FAQ Lookup")
        faq_lookup_enabled = bool(faq_cfg.get("lookup_enabled", True))
        faq_block_time_sensitive = bool(faq_cfg.get("block_time_sensitive", True))
        faq_similarity_raw = faq_cfg.get("similarity_threshold", 0.9)
        try:
            faq_similarity = float(faq_similarity_raw)
        except (TypeError, ValueError):
            faq_similarity = 0.9
        faq_similarity = max(0.5, min(0.99, faq_similarity))

        faq_hit = None
        if faq_lookup_enabled:
            faq_hit = await asyncio.to_thread(
                get_faq_answer,
                msg,
                similarity_threshold=faq_similarity,
                include_meta=True,
                allow_time_sensitive=not faq_block_time_sensitive,
                max_age_days=faq_cfg.get("max_age_days"),
            )

        if isinstance(faq_hit, dict) and str(faq_hit.get("answer") or "").strip():
            reply = str(faq_hit.get("answer") or "").strip()
            total_token_usage["cached"] = True
            step_finish(
                faq_lookup_step,
                "ok",
                {
                    "hit": True,
                    "matched_question": faq_hit.get("question"),
                    "score": faq_hit.get("score"),
                    "time_sensitive": faq_hit.get("time_sensitive", False),
                    "ttl_seconds": faq_hit.get("ttl_seconds"),
                },
            )

            post_step = step_start("answer_post", "Answer Post-Process")
            step_finish(
                post_step,
                "ok",
                {
                    "reply_chars": len(reply),
                    "reply_preview": _preview_text(reply),
                    "from_faq": True,
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
                    "cached": True,
                },
            )

            logger.info(
                "[FAQ HIT] matched=%s score=%s",
                faq_hit.get("question"),
                faq_hit.get("score"),
            )
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
                "from_faq": True,
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
                    "faq_hit": faq_hit,
                }
            return output

        step_finish(
            faq_lookup_step,
            "skipped",
            {
                "hit": False,
                "lookup_enabled": faq_lookup_enabled,
                "reason": "lookup_disabled" if not faq_lookup_enabled else "cache_miss_or_filtered",
                "similarity_threshold": faq_similarity,
                "block_time_sensitive": faq_block_time_sensitive,
            },
        )

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
                if bool(faq_cfg.get("auto_learn", True)):
                    top_score = float(top_chunks[0][1]) if top_chunks else 0.0
                    learn_meta = {
                        "source": "rag",
                        "require_retrieval": True,
                        "retrieval_count": len(top_chunks),
                        "retrieval_top_score": top_score,
                        "min_retrieval_score": faq_cfg.get("min_retrieval_score", 0.35),
                        "block_time_sensitive": bool(faq_cfg.get("block_time_sensitive", True)),
                        "max_age_days": faq_cfg.get("max_age_days", 45),
                        "time_sensitive_ttl_hours": faq_cfg.get("time_sensitive_ttl_hours", 6),
                        "min_answer_chars": faq_cfg.get("min_answer_chars", 30),
                    }
                    faq_update_result = await asyncio.to_thread(update_faq, msg, reply, learn_meta)
                    step_finish(
                        faq_step,
                        "ok" if bool(faq_update_result.get("updated")) else "skipped",
                        faq_update_result,
                    )
                else:
                    step_finish(
                        faq_step,
                        "skipped",
                        {
                            "updated": False,
                            "reason": "auto_learn_off",
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
            fallback_step = step_start("fallback", "Deterministic Fallback", {"error": str(exc)})
            fallback_debug: Dict[str, Any] = {"mode": "generic_error"}
            fallback_message = ""
            try:
                if _looks_out_of_scope_query(msg):
                    fallback_message = "ไม่พบข้อมูลเรื่องนี้ในเอกสารที่ระบบมีอยู่ตอนนี้ครับ"
                    fallback_debug["mode"] = "out_of_scope_guard"
                else:
                    local_lines = await asyncio.to_thread(
                        _search_local_text_fallback,
                        msg,
                        PDF_QUICK_USE_FOLDER,
                        2,
                    )
                    if local_lines:
                        fallback_debug["mode"] = "local_text_scan"
                        fallback_debug["local_hits"] = len(local_lines)
                        fallback_message = (
                            "ขออภัย ระบบสรุปอัตโนมัติขัดข้องชั่วคราว "
                            "จึงแสดงข้อความจากเอกสารที่เกี่ยวข้องโดยตรง:\n"
                            + "\n".join([f"- {line}" for line in local_lines])
                        )

                if not fallback_message and not _looks_out_of_scope_query(msg):
                    fallback_chunks = await asyncio.to_thread(
                        retrieve_top_k_chunks,
                        msg,
                        k=max(1, min(3, int(rag_cfg.get("top_k", 5)))),
                        folder=PDF_QUICK_USE_FOLDER,
                        use_hybrid=True,
                        use_llm_rerank=False,
                        use_intent_analysis=False,
                    )
                    fallback_debug["retrieved"] = len(fallback_chunks)
                    fallback_debug["preview"] = [
                        {
                            "rank": idx + 1,
                            "score": round(float(score), 4),
                            "source": row.get("source", ""),
                            "chunk_preview": _preview_text(row.get("chunk", ""), 160),
                        }
                        for idx, (row, score) in enumerate(fallback_chunks[:3])
                    ]
                    fallback_message = _format_retrieval_fallback(fallback_chunks)
                    if fallback_message:
                        fallback_debug["mode"] = "retrieval_excerpt"

                if not fallback_message:
                    fallback_message = "Sorry, the system is temporarily unavailable."
                step_finish(fallback_step, "warn", fallback_debug)
            except Exception as fallback_exc:
                logger.error("Fallback Error: %s", fallback_exc, exc_info=True)
                fallback_message = "Sorry, the system is temporarily unavailable."
                fallback_debug["fallback_error"] = str(fallback_exc)
                step_finish(fallback_step, "error", fallback_debug)

            error_tokens = {
                "prompt_tokens": 0,
                "completion_tokens": count_tokens(fallback_message, primary_model_name),
                "total_tokens": count_tokens(fallback_message, primary_model_name),
                "error": True,
            }

            error_step = step_start("output", "Output Emit + TTS + Logs")
            step_finish(
                error_step,
                "error",
                {
                    "error": str(exc),
                    "reply_preview": fallback_message,
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
                "text": fallback_message,
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
                    "fallback": fallback_debug,
                }
            return output

