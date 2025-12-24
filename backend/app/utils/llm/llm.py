import logging
import asyncio
from langdetect import detect
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
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
    LOCAL_MODEL_NAME,
    MAX_CONCURRENT_LLM_CALLS
)

logger = logging.getLogger(__name__)
llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

async def ask_llm(msg, session_id, emit_fn=None):
    # 1. ตรวจสอบภาษา
    try:
        detected_lang = await asyncio.to_thread(detect, msg)
    except:
        detected_lang = "th"
    request_prompt = get_request_prompt(detected_lang)

    # 2. ตรวจสอบ FAQ (ค้นหาด้วย Semantic Search ใน Thread)
    faq_answer = await asyncio.to_thread(get_faq_answer, msg)
    if faq_answer:
        logger.info(f"🎯 [FAQ Hit]: {msg}")
        return {"text": faq_answer, "from_faq": True}

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

        full_prompt = f"{context_prompt}\n{summary}\n{history_text}\nถาม: {msg}"

        try:
            model = get_llm_model()
            
            # Step 1: คุยกับ LLM ครั้งแรก
            if LLM_PROVIDER == "gemini":
                response = await model.aio.models.generate_content(model=GEMINI_MODEL_NAME, contents=full_prompt)
                reply = response.text.strip()
            else:
                m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                response = await model.chat.completions.create(
                    model=m_name, 
                    messages=[{"role": "user", "content": full_prompt}]
                )
                reply = response.choices[0].message.content.strip()

            # Step 2: ถ้าต้องใช้ RAG (AI จะตอบด้วย keyword 'query_request')
            if "query_request" in reply:
                search_query = reply.split("query_request", 1)[1].strip()
                if emit_fn:
                    await emit_fn("ai_status", {"status": "🔍 กำลังหาข้อมูลจากระเบียบการให้นะครับ..."})
                
                top_chunks = await asyncio.to_thread(retrieve_top_k_chunks, search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
                context = "\n\n".join([c['chunk'] for c, _ in top_chunks])
                prompt_rag = request_prompt.format(question=search_query, context=context)

                # Call LLM ครั้งที่ 2 ด้วยข้อมูลที่หามาได้
                if LLM_PROVIDER == "gemini":
                    response_rag = await model.aio.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt_rag)
                    reply = response_rag.text.strip()
                else:
                    response_rag = await model.chat.completions.create(
                        model=m_name, 
                        messages=[{"role": "user", "content": prompt_rag}]
                    )
                    reply = response_rag.choices[0].message.content.strip()
                
                # [SELF-LEARNING]: บันทึกคำตอบที่มีคุณภาพลง FAQ อัตโนมัติ
                if len(reply) > 20 and "ไม่พบข้อมูล" not in reply:
                    await asyncio.to_thread(update_faq, msg, reply)

            # บันทึกประวัติ
            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.to_thread(save_history, session_id, history)
            
            return {"text": reply, "from_faq": False}

        except Exception as e:
            logger.error(f"❌ LLM Error: {e}")
            return {"text": "พี่เร็กขออภัย ระบบขัดข้องชั่วคราวครับ", "from_faq": False}