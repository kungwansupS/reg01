import logging
from langdetect import detect
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
from app.prompt.prompt import context_prompt
from app.prompt.request_prompt import get_request_prompt
from memory.memory import qa_cache, summarize_chat_history
from memory.faq_cache import update_faq, get_faq_answer
from memory.session import get_or_create_history, save_history
from retriever.context_selector import retrieve_top_k_chunks
from app.config import PDF_QUICK_USE_FOLDER, LLM_PROVIDER, OPENAI_MODEL_NAME, GEMINI_MODEL_NAME

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
        faq_context_section = f"""
        [ข้อมูลเพิ่มเติมจาก FAQ]
        คำตอบที่มีบันทึกไว้คือ: "{faq_answer}"
        คำสั่ง: ให้ใช้ข้อมูลนี้เป็นหลักในการตอบ แต่เรียบเรียงใหม่ให้เป็นธรรมชาติในบทบาท "พี่เร็ก"
        """

    # 2. ตรวจสอบ QA Cache (Redis)
    if msg in qa_cache:
        if emit_fn: await emit_fn("ai_status", {"status": "ตอบจากความจำ (cache)"})
        return {"text": qa_cache[msg], "from_faq": False}

    # 3. เตรียม History
    history = get_or_create_history(session_id)
    # เพิ่มข้อความปัจจุบันเข้า History
    history.append({"role": "user", "parts": [{"text": msg}]})

    summary = summarize_chat_history(history[:-10])
    history_text = "\n".join([f"{turn['role']}: {turn['parts'][0]['text']}" for turn in history[-10:]])

    # 4. สร้าง Prompt
    full_prompt = f"{context_prompt}\n\n[Summary]\n{summary}\n\n{faq_context_section}\n\n[Chat]\n{history_text}\n\nพี่เร็กตอบว่า:"

    if emit_fn: await emit_fn("ai_status", {"status": "🔍 กำลังประมวลผล..."})
    model = get_llm_model()

    # 5. เรียก LLM
    try:
        if LLM_PROVIDER == "gemini":
            response = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=full_prompt)
            reply = response.text.strip() if response.text else ""
        else:
            response = model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": full_prompt}]
            )
            reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        reply = "ขออภัยครับ พี่เร็กขัดข้องนิดหน่อย ลองใหม่อีกครั้งนะครับ"

    # 6. ตรวจสอบ RAG
    if "query_request" in reply:
        search_query = reply.split("query_request", 1)[1].strip()
        top_chunks = retrieve_top_k_chunks(search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
        context = "\n\n".join([entry['chunk'] for entry, _ in top_chunks])
        prompt_for_answer = request_prompt.format(question=search_query, context=context)

        if LLM_PROVIDER == "gemini":
            response = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt_for_answer)
            reply = response.text.strip() if response.text else ""
        else:
            response = model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": prompt_for_answer}]
            )
            reply = response.choices[0].message.content.strip()

        if emit_fn: await emit_fn("selected_context", {"text": context[:3000]})
        update_faq(msg, reply)

    # 7. บันทึกผลลัพธ์
    qa_cache[msg] = reply
    history.append({"role": "model", "parts": [{"text": reply}]})
    save_history(session_id, history)

    return {"text": reply, "from_faq": bool(faq_answer)}