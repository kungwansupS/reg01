import os
import openai
from google import genai
from app.config import (
    GEMINI_API_KEY, GEMINI_MODEL_NAME,
    OPENAI_API_KEY, OPENAI_MODEL_NAME,
    LLM_PROVIDER, OPENAI_BASE_URL # import เพิ่ม
)

def get_llm_model():
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("❌ ไม่พบ GEMINI_API_KEY ใน Environment Variables")
        return genai.Client(api_key=GEMINI_API_KEY)

    elif LLM_PROVIDER == "openai":
        # สร้าง Client โดยระบุ base_url (ทำให้ใช้ได้ทั้ง Groq, DeepSeek, OpenAI)
        if not OPENAI_API_KEY:
            raise ValueError("❌ ไม่พบ OPENAI_API_KEY สำหรับ Groq/OpenAI")

        return openai.OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

def log_llm_usage(response, context="", model_name=None):
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    if LLM_PROVIDER == "gemini":
        usage = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tokens = usage.prompt_token_count
            completion_tokens = usage.candidates_token_count
            total_tokens = usage.total_token_count

    elif LLM_PROVIDER == "openai":
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

    print(
        f"🔢 {LLM_PROVIDER.capitalize()} token usage ({context}) - "
        f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}"
    )