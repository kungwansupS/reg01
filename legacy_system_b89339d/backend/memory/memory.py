"""
Memory Module — v3 (Sliding Window + Extractive Summary)

สถาปัตยกรรม v3 ใช้ sliding window แทน LLM summarization
ฟังก์ชัน LLM-based summary ยังคงไว้สำหรับ backward compatibility
แต่ ask_llm() ไม่เรียกใช้แล้ว
"""
import tiktoken
import asyncio
import logging
from app.config import LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL_NAME, OPENAI_API_KEY, OPENAI_MODEL_NAME
from app.utils.llm.llm_model import get_llm_model
import openai

logger = logging.getLogger("Memory")

# Try import google genai เพื่อความปลอดภัยกรณีไม่ได้ลง lib
try:
    from google import genai
except ImportError:
    genai = None

qa_cache = {}

# ใช้ encoding ของ gpt-3.5 เป็นมาตรฐานกลาง
try:
    ENCODING = tiktoken.encoding_for_model("gpt-3.5-turbo")
except:
    ENCODING = tiktoken.get_encoding("cl100k_base")

MAX_OUTPUT_TOKENS = 300

def count_tokens(text):
    return len(ENCODING.encode(text))


def extractive_summary(history, max_chars: int = 800) -> str:
    """
    Extractive summary — ไม่ต้องเรียก LLM เลย
    แค่ดึงคู่ Q/A ล่าสุดที่สำคัญ (ไม่ใช่ทักทาย/ขอบคุณ)
    ใช้เป็น fallback แทน LLM summarization
    """
    if not history:
        return ""

    import re
    casual_pattern = re.compile(
        r"^(สวัสดี|หวัดดี|ดี|ขอบคุณ|บาย|hi|hello|thanks|bye)\b",
        re.IGNORECASE,
    )

    pairs = []
    i = 0
    while i < len(history) - 1:
        if history[i].get("role") == "user" and history[i + 1].get("role") == "model":
            q = history[i]["parts"][0]["text"].strip()
            a = history[i + 1]["parts"][0]["text"].strip()
            if not casual_pattern.match(q) and len(q) > 5:
                pairs.append(f"ถาม: {q[:200]}\nตอบ: {a[:300]}")
            i += 2
        else:
            i += 1

    if not pairs:
        return ""

    result = "\n---\n".join(pairs[-3:])
    if len(result) > max_chars:
        result = result[:max_chars] + "..."
    return result

async def summarize_chat_history_async(history):
    """
    ✅ Async version of summarize_chat_history
    สรุปบทสนทนาสำหรับระบบภายใน ไม่แสดงให้ user เห็น
    """
    if not history:
        return ""

    full_dialogue = ""
    for msg in history:
        role = "ผู้ใช้" if msg["role"] == "user" else "AI"
        text = msg["parts"][0]["text"]
        full_dialogue += f"{role}: {text}\n"

    # ✅ เปลี่ยน prompt ให้ชัดเจนว่าเป็น internal summary
    prompt_header = f"""
คุณเป็น AI assistant ที่ทำหน้าที่สรุปบทสนทนาสำหรับระบบภายใน (Internal Use Only)

สรุปบทสนทนาต่อไปนี้ให้กระชับและเข้าใจง่าย:
- จำกัดความยาวไม่เกิน {MAX_OUTPUT_TOKENS} tokens
- เขียนเป็นภาษาไทยแบบสั้นๆ กระชับ
- ไม่ต้องใส่หัวข้อหรือ markdown
- ไม่ต้องบอกว่าเป็นการสรุป เขียนเป็นประโยคปกติ

ตัวอย่าง output ที่ถูกต้อง:
"ผู้ใช้ถามเกี่ยวกับวันเปิดเทอม AI ตอบว่าเปิดวันที่ 23 มิถุนายน 2568"

ตัวอย่าง output ที่ผิด (ห้ามทำ):
"*สรุปบทสนทนา (≤ 300 token)*
- ผู้ใช้สอบถาม..."

บทสนทนา:
"""
    # ลด max_prompt_tokens ลงเพื่อประหยัดและกัน error
    max_prompt_tokens = 1000
    truncated_dialogue = full_dialogue
    while count_tokens(prompt_header + truncated_dialogue) > max_prompt_tokens:
        lines = truncated_dialogue.splitlines()[1:]
        truncated_dialogue = "\n".join(lines)

    prompt = prompt_header + truncated_dialogue

    try:
        # เรียกใช้ Model Client กลาง
        model = get_llm_model()

        if LLM_PROVIDER == "gemini":
            if genai is None:
                return "(Error: google-genai library not installed)"

            # ✅ ใช้ sync API สำหรับ Gemini
            response = await asyncio.to_thread(
                model.models.generate_content,
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            result = response.text.strip() if response.text else ""
            
            # ✅ ตรวจสอบและลบ markdown/formatting ที่ไม่ต้องการ
            result = clean_summary(result)
            
            logger.debug(f"[Gemini] Summary generated: {len(result)} chars")
            return result

        elif LLM_PROVIDER in ["openai", "local"]:
            # ✅ ใช้ await สำหรับ AsyncOpenAI
            response = await model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": f"สรุปบทสนทนาให้กระชับภายใต้ {MAX_OUTPUT_TOKENS} tokens เขียนเป็นประโยคปกติ ไม่ใส่หัวข้อ ไม่ใส่ bullet points ไม่ใส่ markdown"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            result = response.choices[0].message.content.strip()
            
            # ✅ ตรวจสอบและลบ markdown/formatting ที่ไม่ต้องการ
            result = clean_summary(result)
            
            logger.debug(f"[{LLM_PROVIDER.upper()}] Summary generated: {len(result)} chars")
            return result

    except Exception as e:
        logger.error(f"❌ Summarize Error: {e}")
        return ""

    return ""

def clean_summary(text: str) -> str:
    """
    ✅ ทำความสะอาด summary ลบ markdown และ formatting ที่ไม่ต้องการ
    """
    import re
    
    # ลบ markdown headers
    text = re.sub(r'#+\s*', '', text)
    
    # ลบ bullet points
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    
    # ลบหัวข้อแบบ **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # ลบส่วนที่บอกว่าเป็น summary
    text = re.sub(r'\*?สรุป.*?token.*?\*?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(≤\s*\d+\s*token\)', '', text, flags=re.IGNORECASE)
    
    # ลบบรรทัดว่างซ้ำซ้อน
    text = re.sub(r'\n\s*\n', '\n', text)
    
    # ลบช่องว่างด้านหน้าและหลัง
    text = text.strip()
    
    return text

def summarize_chat_history(history):
    """
    ✅ Sync wrapper สำหรับ backward compatibility
    """
    try:
        # ✅ ตรวจสอบว่ามี event loop หรือไม่
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # ถ้า loop กำลังรันอยู่ ใช้ asyncio.create_task
            # แต่เนื่องจากเป็น sync function เราต้องสร้าง task ใหม่
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, summarize_chat_history_async(history))
                return future.result()
        else:
            # ถ้าไม่มี loop รัน ให้สร้างใหม่
            return asyncio.run(summarize_chat_history_async(history))
    except RuntimeError:
        # ถ้าไม่มี event loop เลย
        return asyncio.run(summarize_chat_history_async(history))