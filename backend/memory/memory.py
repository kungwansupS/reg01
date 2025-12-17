import tiktoken
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

def summarize_chat_history(history):
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

            response = model.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            result = response.text.strip() if response.text else ""
            print(f"[Gemini] summary done.")
            return result

        elif LLM_PROVIDER == "openai":
            # ใช้ Client ของ OpenAI (รองรับ Groq)
            response = model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": f"สรุปใจความสำคัญของบทสนทนาให้อยู่ภายใต้ {MAX_OUTPUT_TOKENS} token"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            result = response.choices[0].message.content.strip()
            print(f"[Groq/OpenAI] summary done.")
            return result

    except Exception as e:
        print(f"❌ Summarize Error: {e}")
        return "(ไม่สามารถสรุปได้)"

    return "(ไม่สามารถสรุปได้: ไม่รู้จัก LLM_PROVIDER)"