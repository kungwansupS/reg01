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
    LOCAL_MODEL_NAME
)

logger = logging.getLogger(__name__)

async def ask_llm(msg, session_id, emit_fn=None):
    detected_lang = detect(msg)
    request_prompt = get_request_prompt(detected_lang)

    if emit_fn:
        await emit_fn("ai_status", {"status": "🧠 กำลังคิด..."})

    # 1. ตรวจสอบ FAQ
    faq_answer = get_faq_answer(msg)
    faq_context_section = ""

    if faq_answer:
        if emit_fn:
            await emit_fn("ai_status", {"status": "กำลังดึงความรู้จาก FAQ..."})
        faq_context_section = f"""
        [ข้อมูลเพิ่มเติมจากฐานข้อมูล FAQ]
        คำตอบที่มีบันทึกไว้คือ: "{faq_answer}"
        คำสั่ง: ให้ใช้ข้อมูลนี้เป็นหลักในการตอบ โดยเรียบเรียงให้เป็นธรรมชาติในบทบาท พี่เร็ก
        """

    # 2. ตรวจสอบ QA Cache
    if msg in qa_cache:
        if emit_fn:
            await emit_fn("ai_status", {"status": "ตอบจากความจำ (cache)"})
        return {"text": qa_cache[msg], "from_faq": False}

    # 3. เตรียม History
    history = get_or_create_history(session_id)
    if not (history and history[-1]["role"] == "user" and history[-1]["parts"][0]["text"] == msg):
        history.append({"role": "user", "parts": [{"text": msg}]})
        save_history(session_id, history)

    summary = summarize_chat_history(history[:-10])
    history_text = "\n".join([f"{turn['role']}: {turn['parts'][0]['text']}" for turn in history[-10:]])

    # 4. สร้าง Full Prompt
    full_prompt = f"""
        {context_prompt}
        [สรุปข้อมูลเดิม] {summary}
        {faq_context_section}
        [บทสนทนาล่าสุด] {history_text}
        คำถามปัจจุบัน: \"{msg}\"
    """

    if emit_fn:
        await emit_fn("ai_status", {"status": "🔍 กำลังประมวลผล..."})

    try:
        model = get_llm_model()

        # 5. เรียก LLM ครั้งแรกเพื่อเช็คว่าต้องใช้ RAG หรือไม่
        if LLM_PROVIDER == "gemini":
            response = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=full_prompt)
            reply = response.text.strip() if response.text else ""
            log_llm_usage(response, context="First Call (Gemini)")
        elif LLM_PROVIDER in ["openai", "local"]:
            m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
            response = model.chat.completions.create(
                model=m_name, 
                messages=[{"role": "user", "content": full_prompt}]
            )
            reply = response.choices[0].message.content.strip()
            log_llm_usage(response, context=f"First Call ({LLM_PROVIDER})")

        # 6. ตรวจสอบเงื่อนไข RAG
        if "query_request" in reply:
            search_query = reply.split("query_request", 1)[1].strip()
            logger.info(f"🔎 คำค้น RAG: {search_query}")

            top_chunks = await asyncio.to_thread(
                retrieve_top_k_chunks, search_query, k=5, folder=PDF_QUICK_USE_FOLDER
            )
            
            context = "\n\n===================\n\n".join([entry['chunk'] for entry, _ in top_chunks])
            prompt_for_answer = request_prompt.format(question=search_query, context=context)

            if LLM_PROVIDER == "gemini":
                response = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt_for_answer)
                reply = response.text.strip() if response.text else ""
                log_llm_usage(response, context="RAG Call (Gemini)")
            elif LLM_PROVIDER in ["openai", "local"]:
                m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                response = model.chat.completions.create(
                    model=m_name, 
                    messages=[{"role": "user", "content": prompt_for_answer}]
                )
                reply = response.choices[0].message.content.strip()
                log_llm_usage(response, context=f"RAG Call ({LLM_PROVIDER})")

            if emit_fn:
                await emit_fn("selected_context", {"text": context[:3000]})
            
            qa_cache[msg] = reply
            update_faq(msg, reply)
        else:
            reply = reply.replace("model:", "").strip()
            qa_cache[msg] = reply

        # 7. บันทึกผล
        history.append({"role": "model", "parts": [{"text": reply}]})
        save_history(session_id, history)

        return {"text": reply, "from_faq": bool(faq_answer)}

    except (openai.APIConnectionError, openai.InternalServerError) as e:
        logger.error(f"⚠️ LLM Connection Error: {e}")
        error_msg = f"❌ กำลังตั้งค่าระบบ Local LLM ({LOCAL_MODEL_NAME}) โปรดรอสักครู่และลองใหม่อีกครั้ง หรือตรวจสอบว่า Ollama ติดตั้งแล้ว"
        if emit_fn:
            await emit_fn("ai_status", {"status": "❌ การเชื่อมต่อขัดข้อง"})
        return {"text": error_msg, "from_faq": False}
    except Exception as e:
        logger.error(f"❌ Unexpected Error: {e}")
        return {"text": f"❌ เกิดข้อผิดพลาด: {str(e)}", "from_faq": False}