qa_cache = {}

import tiktoken
from app.config import LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL_NAME, OPENAI_API_KEY, OPENAI_MODEL_NAME
import google.generativeai as genai
import openai

ENCODING = tiktoken.encoding_for_model(OPENAI_MODEL_NAME)
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
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt)
        result = response.text.strip()
        token_used = count_tokens(result)
        print(f"[Gemini] summary used {token_used} tokens.")
        return result

    elif LLM_PROVIDER == "openai":
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": f"สรุปใจความสำคัญของบทสนทนาให้อยู่ภายใต้ {MAX_OUTPUT_TOKENS} token"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=MAX_OUTPUT_TOKENS
        )
        result = response.choices[0].message["content"].strip()
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        print(f"[OpenAI] prompt: {prompt_tokens} tokens, completion: {completion_tokens} tokens, total: {prompt_tokens + completion_tokens}")
        return result

    return "(ไม่สามารถสรุปได้: ไม่รู้จัก LLM_PROVIDER)"
