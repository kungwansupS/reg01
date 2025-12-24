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

    faq_answer = get_faq_answer(msg)
    faq_context_section = f"\n[FAQ] {faq_answer}" if faq_answer else ""

    if msg in qa_cache:
        return {"text": qa_cache[msg], "from_faq": False}

    history = get_or_create_history(session_id)
    if not (history and history[-1]["parts"][0]["text"] == msg):
        history.append({"role": "user", "parts": [{"text": msg}]})
        save_history(session_id, history)

    summary = summarize_chat_history(history[:-10])
    history_text = "\n".join([f"{t['role']}: {t['parts'][0]['text']}" for t in history[-10:]])

    full_prompt = f"{context_prompt}\n{summary}\n{faq_context_section}\n{history_text}\nถาม: {msg}"

    try:
        model = get_llm_model()
        
        if LLM_PROVIDER == "gemini":
            response = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=full_prompt)
            reply = response.text.strip()
        else:
            m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
            response = model.chat.completions.create(model=m_name, messages=[{"role": "user", "content": full_prompt}])
            reply = response.choices[0].message.content.strip()

        if "query_request" in reply:
            search_query = reply.split("query_request", 1)[1].strip()
            top_chunks = await asyncio.to_thread(retrieve_top_k_chunks, search_query, k=5, folder=PDF_QUICK_USE_FOLDER)
            context = "\n\n".join([c['chunk'] for c, _ in top_chunks])
            prompt_rag = request_prompt.format(question=search_query, context=context)

            if LLM_PROVIDER == "gemini":
                response = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt_rag)
                reply = response.text.strip()
            else:
                m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                response = model.chat.completions.create(model=m_name, messages=[{"role": "user", "content": prompt_rag}])
                reply = response.choices[0].message.content.strip()

        qa_cache[msg] = reply
        history.append({"role": "model", "parts": [{"text": reply}]})
        save_history(session_id, history)
        return {"text": reply, "from_faq": bool(faq_answer)}

    except Exception as e:
        logger.error(f"❌ LLM Error: {e}")
        return {"text": f"❌ ระบบขัดข้อง: {str(e)}", "from_faq": False}