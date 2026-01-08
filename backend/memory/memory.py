import tiktoken
import asyncio
from app.config import LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL_NAME, OPENAI_API_KEY, OPENAI_MODEL_NAME
from app.utils.llm.llm_model import get_llm_model
import openai

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

async def summarize_chat_history_async(history):
    """
    ✅ Async version of summarize_chat_history
    """
    if not history:
        return ""

    full_dialogue = ""
    for msg in history:
        role = "ผู้ใช้" if msg["role"] == "user" else "AI"
        text = msg["parts"][0]["text"]
        full_dialogue += f"{role}: {text}\n"

    prompt_header = f"""
สรุปบทสนทนาให้กระชับ โดยจำกัดความยาวของผลลัพธ์ไม่เกิน {MAX_OUTPUT_TOKENS} token:
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
            print(f"[Gemini] summary done.")
            return result

        elif LLM_PROVIDER in ["openai", "local"]:
            # ✅ ใช้ await สำหรับ AsyncOpenAI
            response = await model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": f"สรุปใจความสำคัญของบทสนทนาให้อยู่ภายใต้ {MAX_OUTPUT_TOKENS} token"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            result = response.choices[0].message.content.strip()
            print(f"[{LLM_PROVIDER.upper()}] summary done.")
            return result

    except Exception as e:
        print(f"❌ Summarize Error: {e}")
        return "(ไม่สามารถสรุปได้)"

    return "(ไม่สามารถสรุปได้: ไม่รู้จัก LLM_PROVIDER)"

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