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

    # ------------------------------------------------------------------
    # 1. ตรวจสอบ FAQ ก่อน (เพื่อเตรียม Context)
    # ------------------------------------------------------------------
    faq_answer = get_faq_answer(msg)
    faq_context_section = ""

    if faq_answer:
        print(f"🎯 พบข้อมูลใน FAQ: {faq_answer[:50]}...")
        if emit_fn:
            await emit_fn("ai_status", {"status": "กำลังดึงความรู้จาก FAQ..."})

        # สร้าง Context Section สำหรับ FAQ เพื่อป้อนให้ LLM
        faq_context_section = f"""
        [ข้อมูลเพิ่มเติมจากฐานข้อมูล FAQ (คำถามที่พบบ่อย)]
        ระบบพบว่าคำถามของผู้ใช้มีความคล้ายคลึงกับคำถามในฐานข้อมูล
        ข้อมูลคำตอบที่มีบันทึกไว้คือ: "{faq_answer}"
        
        คำสั่ง: ให้ใช้ข้อมูลจาก "ข้อมูลคำตอบที่มีบันทึกไว้" ด้านบนนี้ เป็นข้อมูลหลักในการตอบคำถาม
        แต่ห้ามตอบห้วนๆ ให้เรียบเรียงประโยคใหม่ให้เป็นธรรมชาติ เข้ากับบทบาท "พี่เร็ก" และเข้ากับบริบทการสนทนาปัจจุบัน
        """

    # ------------------------------------------------------------------
    # 2. ตรวจสอบ QA Cache (Memory Cache - Exact Match)
    # ------------------------------------------------------------------
    if msg in qa_cache:
        logger.info("🧠 ดึงคำตอบจาก cache")
        if emit_fn:
            await emit_fn("ai_status", {"status": "ตอบจากความจำ (cache)"} )

        # [จุดที่แก้ไข] Return เป็น Dictionary เสมอ เพื่อไม่ให้ main.py error
        return {
            "text": qa_cache[msg],
            "from_faq": False
        }

    # ------------------------------------------------------------------
    # 3. เตรียม History และ Context
    # ------------------------------------------------------------------
    history = get_or_create_history(session_id)
    if not (history and history[-1]["role"] == "user" and history[-1]["parts"][0]["text"] == msg):
        history.append({"role": "user", "parts": [{"text": msg}]})
        save_history(session_id, history)

    summary = summarize_chat_history(history[:-10])
    history_text = "\n".join([
        f"{turn['role']}: {turn['parts'][0]['text']}" for turn in history[-10:]
    ])

    # ------------------------------------------------------------------
    # 4. สร้าง Full Prompt (รวม FAQ Context ถ้ามี)
    # ------------------------------------------------------------------
    full_prompt = f"""
        {context_prompt}

        [สรุปข้อมูลจากบทสนทนาเดิม (Memory ย่อ)]
        {summary}

        {faq_context_section}

        [บทสนทนา 10 ข้อความล่าสุด]
        {history_text}

        ตอนนี้พี่เร็กต้องตอบข้อความล่าสุดที่ผู้ใช้พูด คือ: \"{msg}\"
        พี่เร็กควรตอบอย่างเหมาะสม โดยคำนึงถึงข้อมูลข้างต้นด้วย
    """

    if emit_fn:
        await emit_fn("ai_status", {"status": "🔍 กำลังประมวลผล..."})

    model = get_llm_model()

    # ------------------------------------------------------------------
    # 5. เรียกใช้งาน LLM
    # ------------------------------------------------------------------
    if LLM_PROVIDER == "gemini":
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

    log_llm_usage(response, context="ask_llm - generate")

    # ------------------------------------------------------------------
    # 6. ตรวจสอบ RAG หรือตอบกลับ
    # ------------------------------------------------------------------
    if "query_request" in reply:
        logger.debug(reply)
        search_query = reply.split("query_request", 1)[1].strip()
        logger.info(f"🔎 คำค้น: {search_query}")

        top_chunks = retrieve_top_k_chunks(search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
        context = "\n\n===================\n\n".join([entry['chunk'] for entry, _ in top_chunks])
        prompt_for_answer = request_prompt.format(question=search_query, context=context)

        if LLM_PROVIDER == "gemini":
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
        qa_cache[msg] = reply

    # ------------------------------------------------------------------
    # 7. บันทึกและส่งคืนค่า
    # ------------------------------------------------------------------
    history.append({"role": "model", "parts": [{"text": reply}]})
    save_history(session_id, history)

    return {
        "text": reply,
        "from_faq": bool(faq_answer)
    }