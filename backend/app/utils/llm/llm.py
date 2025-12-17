import logging
from langdetect import detect
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
from app.prompt.prompt import context_prompt
from app.prompt.request_prompt import get_request_prompt
from memory.memory import qa_cache, summarize_chat_history
from memory.faq_cache import update_faq, get_faq_answer
from memory.session import get_or_create_history, save_history
from retriever.context_selector import retrieve_top_k_chunks
from app.config import PDF_QUICK_USE_FOLDER, LLM_PROVIDER, OPENAI_MODEL_NAME, GEMINI_MODEL_NAME # เพิ่ม GEMINI_MODEL_NAME

logger = logging.getLogger(__name__)

async def ask_llm(msg, session_id, emit_fn=None):
    detected_lang = detect(msg)
    request_prompt = get_request_prompt(detected_lang)

    if emit_fn:
        await emit_fn("ai_status", {"status": "🧠 กำลังคิด..."})

    faq_answer = get_faq_answer(msg)
    if faq_answer:
        print("🎯 ตอบจาก FAQ Cache")
        if emit_fn:
            await emit_fn("ai_status", {"status": "ตอบจากคำถามยอดฮิต"})
        history = get_or_create_history(session_id)
        history.append({"role": "user", "parts": [{"text": msg}]})
        history.append({"role": "model", "parts": [{"text": faq_answer}]})
        save_history(session_id, history)
        return {
            "text": faq_answer,
            "from_faq": True
        }

    if msg in qa_cache:
        logger.info("🧠 ดึงคำตอบจาก cache")
        if emit_fn:
            await emit_fn("ai_status", {"status": "ตอบจากความจำ (cache)"} )
        return qa_cache[msg]

    history = get_or_create_history(session_id)
    if not (history and history[-1]["role"] == "user" and history[-1]["parts"][0]["text"] == msg):
        history.append({"role": "user", "parts": [{"text": msg}]})
        save_history(session_id, history)

    summary = summarize_chat_history(history[:-10])
    history_text = "\n".join([
        f"{turn['role']}: {turn['parts'][0]['text']}" for turn in history[-10:]
    ])

    full_prompt = f"""
        {context_prompt}

        [สรุปข้อมูลจากบทสนทนาเดิม (Memory ย่อ)]
        {summary}

        [บทสนทนา 10 ข้อความล่าสุด]
        {history_text}

        ตอนนี้พี่เร็กต้องตอบข้อความล่าสุดที่ผู้ใช้พูด คือ: \"{msg}\"
        พี่เร็กควรตอบอย่างเหมาะสม โดยคำนึงถึงข้อมูลข้างต้นด้วย
    """

    if emit_fn:
        await emit_fn("ai_status", {"status": "🔍 กำลังตรวจสอบ..."})

    model = get_llm_model() # ถ้าเป็น Gemini จะได้ client กลับมา

    if LLM_PROVIDER == "gemini":
        # อัปเดต: การเรียกใช้ผ่าน client.models.generate_content
        response = model.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=full_prompt
        )
        reply = response.text.strip() if response.text else ""
    elif LLM_PROVIDER == "openai":
        response = model.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[{"role": "user", "content": full_prompt}],
        )
        reply = response.choices[0].message.content.strip()
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

    log_llm_usage(response, context="ask_llm - classify")

    if "query_request" in reply:
        logger.debug(reply)
        search_query = reply.split("query_request", 1)[1].strip()
        logger.info(f"🔎 คำค้น: {search_query}")

        top_chunks = retrieve_top_k_chunks(search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
        context = "\n\n===================\n\n".join([entry['chunk'] for entry, _ in top_chunks])
        prompt_for_answer = request_prompt.format(question=search_query, context=context)

        if LLM_PROVIDER == "gemini":
            # อัปเดต: การเรียกใช้ผ่าน client.models.generate_content สำหรับ RAG
            response = model.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt_for_answer
            )
            reply = response.text.strip() if response.text else ""
        elif LLM_PROVIDER == "openai":
            response = model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": prompt_for_answer}],
            )
            reply = response.choices[0].message.content.strip()
        else:
            raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

        log_llm_usage(response, context="rag-final-response")

        if emit_fn:
            await emit_fn("selected_context", {
                "text": context[:3000]
            })

        qa_cache[msg] = reply
        update_faq(msg, reply)

    else:
        reply = reply.replace("model:", "").strip()

    history.append({"role": "model", "parts": [{"text": reply}]})
    save_history(session_id, history)

    return {
        "text": reply,
        "from_faq": bool(faq_answer)
    }