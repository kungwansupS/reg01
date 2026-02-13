import logging
import asyncio
from langdetect import detect
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
from app.utils.token_counter import get_token_usage, format_token_usage, count_tokens
from app.prompt.prompt import context_prompt
from app.prompt.request_prompt import get_request_prompt
from memory.memory import qa_cache, summarize_chat_history
from memory.faq_cache import update_faq, get_faq_answer, encode_text
from memory.session import get_or_create_history, save_history
from retriever.context_selector import retrieve_top_k_chunks
from app.config import (
    PDF_QUICK_USE_FOLDER, 
    LLM_PROVIDER, 
    OPENAI_MODEL_NAME, 
    GEMINI_MODEL_NAME,
    GEMINI_FALLBACK_MODELS,
    GEMINI_MAX_RETRIES,
    GEMINI_RETRY_BASE_SECONDS,
    LOCAL_MODEL_NAME,
    MAX_CONCURRENT_LLM_CALLS
)

logger = logging.getLogger(__name__)
llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

def _is_retryable_gemini_error(error_text: str) -> bool:
    text = (error_text or "").upper()
    retry_markers = [
        "503",
        "UNAVAILABLE",
        "429",
        "RESOURCE_EXHAUSTED",
        "DEADLINE_EXCEEDED",
        "TIMEOUT",
    ]
    return any(marker in text for marker in retry_markers)

def _is_model_switch_gemini_error(error_text: str) -> bool:
    text = (error_text or "").upper()
    switch_markers = [
        "404",
        "NOT_FOUND",
        "PERMISSION_DENIED",
        "NOT SUPPORTED",
        "NOT AVAILABLE",
    ]
    return any(marker in text for marker in switch_markers)

def _build_gemini_candidates() -> list:
    seen = set()
    candidates = [GEMINI_MODEL_NAME] + list(GEMINI_FALLBACK_MODELS)
    ordered = []
    for candidate in candidates:
        model_name = (candidate or "").strip()
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        ordered.append(model_name)
    return ordered

async def _gemini_generate_with_fallback(model_client, prompt: str, stage: str):
    candidates = _build_gemini_candidates()
    last_error = None

    for model_name in candidates:
        for attempt in range(GEMINI_MAX_RETRIES + 1):
            try:
                response = await asyncio.to_thread(
                    model_client.models.generate_content,
                    model=model_name,
                    contents=prompt
                )
                reply_text = (response.text or "").strip()
                if not reply_text:
                    raise RuntimeError("Gemini returned empty response")
                return model_name, reply_text
            except Exception as exc:
                last_error = exc
                error_text = str(exc)
                is_retryable = _is_retryable_gemini_error(error_text)
                has_retry = attempt < GEMINI_MAX_RETRIES

                if is_retryable and has_retry:
                    delay = GEMINI_RETRY_BASE_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Gemini {stage}] {model_name} retry "
                        f"{attempt + 1}/{GEMINI_MAX_RETRIES} in {delay:.1f}s: {exc}"
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.warning(f"[Gemini {stage}] {model_name} failed: {exc}")

                if _is_model_switch_gemini_error(error_text) or is_retryable:
                    break

                break

    raise RuntimeError(f"Gemini failed for all candidate models: {last_error}")

async def ask_llm(msg, session_id, emit_fn=None):
    """
    Main LLM function with accurate token tracking
    Returns: {
        "text": str,
        "from_faq": bool,
        "tokens": dict  # NEW: token usage info
    }
    """
    # 1. ตรวจสอบภาษา
    try:
        detected_lang = await asyncio.to_thread(detect, msg)
    except:
        detected_lang = "th"
    request_prompt = get_request_prompt(detected_lang)

    # 2. ตรวจสอบ FAQ (ค้นหาด้วย Semantic Search ใน Thread)
    # faq_answer = await asyncio.to_thread(get_faq_answer, msg)
    # if faq_answer:
    #     logger.info(f"🎯 [FAQ Hit]: {msg}")
    #     # Count tokens for FAQ response
    #     model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else OPENAI_MODEL_NAME
    #     completion_tokens = count_tokens(faq_answer, model_name)
        
    #     return {
    #         "text": faq_answer, 
    #         "from_faq": True,
    #         "tokens": {
    #             "prompt_tokens": 0,
    #             "completion_tokens": completion_tokens,
    #             "total_tokens": completion_tokens,
    #             "cached": True
    #         }
    #     }

    # 3. เข้าคิวประมวลผล LLM
    async with llm_semaphore:
        if emit_fn:
            await emit_fn("ai_status", {"status": "🧠 พี่เร็กกำลังประมวลผล..."})

        history = get_or_create_history(session_id)
        if not (history and history[-1]["parts"][0]["text"] == msg):
            history.append({"role": "user", "parts": [{"text": msg}]})
            await asyncio.to_thread(save_history, session_id, history)

        summary = await asyncio.to_thread(summarize_chat_history, history[:-10])
        history_text = "\n".join([f"{t['role']}: {t['parts'][0]['text']}" for t in history[-10:]])

        full_prompt = f"{context_prompt(msg)}\n{summary}\n{history_text}\nถาม: {msg}"

        # Initialize token tracking
        total_token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached": False
        }

        try:
            model = get_llm_model()
            
            # Step 1: คุยกับ LLM ครั้งแรก
            if LLM_PROVIDER == "gemini":
                gemini_model_used, reply = await _gemini_generate_with_fallback(
                    model,
                    full_prompt,
                    "Call 1"
                )

                prompt_tokens = count_tokens(full_prompt, gemini_model_used)
                completion_tokens = count_tokens(reply, gemini_model_used)

                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }

                total_token_usage["prompt_tokens"] += prompt_tokens
                total_token_usage["completion_tokens"] += completion_tokens
                total_token_usage["total_tokens"] += usage["total_tokens"]

                logger.info(
                    f"📊 [Gemini Call 1 - {gemini_model_used}] "
                    f"{format_token_usage(usage)}"
                )

            else:
                m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                response = await model.chat.completions.create(
                    model=m_name, 
                    messages=[{"role": "user", "content": full_prompt}]
                )
                reply = response.choices[0].message.content.strip()
                
                # Track tokens
                usage = get_token_usage(response, LLM_PROVIDER, m_name)
                total_token_usage["prompt_tokens"] += usage["prompt_tokens"]
                total_token_usage["completion_tokens"] += usage["completion_tokens"]
                total_token_usage["total_tokens"] += usage["total_tokens"]
                
                logger.info(f"📊 [{LLM_PROVIDER.upper()} Call 1] {format_token_usage(usage)}")

            # Step 2: ถ้าต้องใช้ RAG (AI จะตอบด้วย keyword 'query_request')
            if "query_request" in reply:
                search_query = reply.split("query_request", 1)[1].strip()
                print ("=====msg=====\n"+ msg +"\n=====msg=====")
                print ("=====query=====\n"+ search_query +"\n=====query=====")
                if emit_fn:
                    await emit_fn("ai_status", {"status": "🔍 กำลังหาข้อมูลจากระเบียบการให้นะครับ..."})
                
                top_chunks = await asyncio.to_thread(retrieve_top_k_chunks, search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
                context = "\n\n".join([c['chunk'] for c, _ in top_chunks])
                print ("=====context=====\n"+ context +"\n=====context=====")
                prompt_rag = request_prompt(question=msg, search_query=search_query, context=context)

                # Call LLM ครั้งที่ 2 ด้วยข้อมูลที่หามาได้
                if LLM_PROVIDER == "gemini":
                    gemini_rag_model, reply = await _gemini_generate_with_fallback(
                        model,
                        prompt_rag,
                        "Call 2 RAG"
                    )

                    prompt_tokens_rag = count_tokens(prompt_rag, gemini_rag_model)
                    completion_tokens_rag = count_tokens(reply, gemini_rag_model)

                    usage_rag = {
                        "prompt_tokens": prompt_tokens_rag,
                        "completion_tokens": completion_tokens_rag,
                        "total_tokens": prompt_tokens_rag + completion_tokens_rag
                    }

                    total_token_usage["prompt_tokens"] += prompt_tokens_rag
                    total_token_usage["completion_tokens"] += completion_tokens_rag
                    total_token_usage["total_tokens"] += usage_rag["total_tokens"]

                    logger.info(
                        f"📊 [Gemini Call 2 RAG - {gemini_rag_model}] "
                        f"{format_token_usage(usage_rag)}"
                    )

                else:
                    response_rag = await model.chat.completions.create(
                        model=m_name, 
                        messages=[{"role": "user", "content": prompt_rag}]
                    )
                    reply = response_rag.choices[0].message.content.strip()
                    
                    # Track tokens
                    usage_rag = get_token_usage(response_rag, LLM_PROVIDER, m_name)
                    total_token_usage["prompt_tokens"] += usage_rag["prompt_tokens"]
                    total_token_usage["completion_tokens"] += usage_rag["completion_tokens"]
                    total_token_usage["total_tokens"] += usage_rag["total_tokens"]
                    
                    logger.info(f"📊 [{LLM_PROVIDER.upper()} Call 2 RAG] {format_token_usage(usage_rag)}")
                
                # [SELF-LEARNING]: บันทึกคำตอบที่มีคุณภาพลง FAQ อัตโนมัติ
                if len(reply) > 20 and "ไม่พบข้อมูล" not in reply:
                    await asyncio.to_thread(update_faq, msg, reply)

            # Log total usage
            logger.info(f"📊 [Total Token Usage] {format_token_usage(total_token_usage)}")

            # บันทึกประวัติ
            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.to_thread(save_history, session_id, history)
            
            return {
                "text": reply, 
                "from_faq": False,
                "tokens": total_token_usage
            }

        except Exception as e:
            logger.error(f"❌ LLM Error: {e}")
            
            # Return error with minimal token count
            error_message = "พี่เร็กขออภัย ระบบขัดข้องชั่วคราวครับ"
            return {
                "text": error_message, 
                "from_faq": False,
                "tokens": {
                    "prompt_tokens": 0,
                    "completion_tokens": count_tokens(error_message),
                    "total_tokens": count_tokens(error_message),
                    "error": True
                }
            }
