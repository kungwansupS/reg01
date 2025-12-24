import logging
import asyncio
import openai
from langdetect import detect
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
from app.prompt.prompt import context_prompt
from app.prompt.request_prompt import get_request_prompt
from memory.memory import qa_cache, summarize_chat_history
from memory.faq_cache import update_faq, get_faq_answer
from memory.session import get_or_create_history, save_history
from retriever.context_selector import retrieve_top_k_chunks
from app.config import (
    PDF_QUICK_USE_FOLDER, 
    LLM_PROVIDER, 
    OPENAI_MODEL_NAME, 
    GEMINI_MODEL_NAME,
    LOCAL_MODEL_NAME,
    MAX_CONCURRENT_LLM_CALLS
)

logger = logging.getLogger(__name__)

# Global Semaphore เพื่อจำกัด Concurrency ทั่วทั้ง Application (Web + FB)
llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

async def ask_llm(msg, session_id, emit_fn=None):
    """
    ประมวลผลคำถามด้วย LLM แบบ Async (RAG-Enabled) พร้อมระบบ Global Rate Limit
    """
    # 1. ตรวจสอบเบื้องต้น (นอก Semaphore เพื่อความเร็ว)
    # ตรวจสอบภาษา (รันใน thread เพื่อป้องกันการ block CPU)
    detected_lang = await asyncio.to_thread(detect, msg)
    request_prompt = get_request_prompt(detected_lang)

    # FAQ และ Cache (ถ้ามีใน Cache ไม่ต้องรอคิว Semaphore)
    faq_answer = get_faq_answer(msg)
    faq_context = f"\n[FAQ] {faq_answer}" if faq_answer else ""
    if msg in qa_cache:
        logger.info(f"💡 [Cache Hit]: {msg}")
        return {"text": qa_cache[msg], "from_faq": False}

    # 2. เข้าคิวประมวลผล LLM (Semaphore Control)
    async with llm_semaphore:
        if emit_fn:
            await emit_fn("ai_status", {"status": "🧠 พี่เร็กกำลังประมวลผล..."})

        # History & Memory Management
        history = get_or_create_history(session_id)
        if not (history and history[-1]["parts"][0]["text"] == msg):
            history.append({"role": "user", "parts": [{"text": msg}]})
            await asyncio.to_thread(save_history, session_id, history)

        summary = await asyncio.to_thread(summarize_chat_history, history[:-10])
        history_text = "\n".join([f"{t['role']}: {t['parts'][0]['text']}" for t in history[-10:]])

        full_prompt = f"{context_prompt}\n{summary}{faq_context}\n{history_text}\nถาม: {msg}"

        try:
            model = get_llm_model()
            
            # 3. First LLM Call
            if LLM_PROVIDER == "gemini":
                response = await model.aio.models.generate_content(
                    model=GEMINI_MODEL_NAME, 
                    contents=full_prompt
                )
                reply = response.text.strip()
            else:
                m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                response = await model.chat.completions.create(
                    model=m_name, 
                    messages=[{"role": "user", "content": full_prompt}]
                )
                reply = response.choices[0].message.content.strip()

            log_llm_usage(response, context="First Call")

            # 4. RAG Logic (ถ้าต้องใช้ข้อมูลเพิ่ม)
            if "query_request" in reply:
                search_query = reply.split("query_request", 1)[1].strip()
                if emit_fn:
                    await emit_fn("ai_status", {"status": "🔍 กำลังหาข้อมูลเพิ่มเติมให้นะครับ..."})
                
                top_chunks = await asyncio.to_thread(retrieve_top_k_chunks, search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
                context = "\n\n".join([c['chunk'] for c, _ in top_chunks])
                prompt_rag = request_prompt.format(question=search_query, context=context)

                if LLM_PROVIDER == "gemini":
                    response = await model.aio.models.generate_content(
                        model=GEMINI_MODEL_NAME, 
                        contents=prompt_rag
                    )
                    reply = response.text.strip()
                else:
                    m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                    response = await model.chat.completions.create(
                        model=m_name, 
                        messages=[{"role": "user", "content": prompt_rag}]
                    )
                    reply = response.choices[0].message.content.strip()
                
                log_llm_usage(response, context="RAG Call")

            # บันทึกสถานะผลลัพธ์
            qa_cache[msg] = reply
            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.to_thread(save_history, session_id, history)
            
            return {"text": reply, "from_faq": bool(faq_answer)}

        except Exception as e:
            logger.error(f"❌ LLM Error: {e}")
            return {
                "text": f"❌ พี่เร็กขออภัย ระบบขัดข้องชั่วคราว: {str(e)}", 
                "from_faq": False
            }