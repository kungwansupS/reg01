qa_cache = {}

import tiktoken
from app.config import LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL_NAME, OPENAI_API_KEY, OPENAI_MODEL_NAME
from google import genai # เปลี่ยนจาก google.generativeai
import openai

ENCODING = tiktoken.encoding_for_model("gpt-3.5-turbo") # ใช้ชื่อ model string ตรงๆ กัน error ถ้าตัวแปร config ไม่มี
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
    max_prompt_tokens = 1000
    truncated_dialogue = full_dialogue
    while count_tokens(prompt_header + truncated_dialogue) > max_prompt_tokens:
        lines = truncated_dialogue.splitlines()[1:]
        truncated_dialogue = "\n".join(lines)

    prompt = prompt_header + truncated_dialogue

    if LLM_PROVIDER == "gemini":
        # อัปเดต: ใช้ Client ของ google-genai
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY missing")
            return "(ไม่สามารถสรุปได้: ไม่มี API KEY)"

        client = genai.Client(api_key=GEMINI_API_KEY)
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            result = response.text.strip() if response.text else ""
            token_used = count_tokens(result)
            print(f"[Gemini] summary used {token_used} tokens.")
            return result
        except Exception as e:
            print(f"❌ Gemini Error: {e}")
            return "(Error summarization)"

    elif LLM_PROVIDER == "openai":
        openai.api_key = OPENAI_API_KEY
        try:
            response = openai.chat.completions.create( # อัปเดต syntax openai ล่าสุดเผื่อไว้
                model=OPENAI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": f"สรุปใจความสำคัญของบทสนทนาให้อยู่ภายใต้ {MAX_OUTPUT_TOKENS} token"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            result = response.choices[0].message.content.strip()
            # Usage access อาจต่างกันไปตาม version openai แต่โดยรวมใช้ attribute
            # print(f"[OpenAI] usage: {response.usage}")
            return result
        except Exception as e:
            print(f"❌ OpenAI Error: {e}")
            return "(Error summarization)"

    return "(ไม่สามารถสรุปได้: ไม่รู้จัก LLM_PROVIDER)"