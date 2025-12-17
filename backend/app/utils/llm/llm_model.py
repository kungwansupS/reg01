import os
import openai
from google import genai
from app.config import (
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    LLM_PROVIDER,
    OPENAI_BASE_URL
)

def get_llm_model():
    """
    สร้างและคืนค่า Client ของ LLM ตาม Provider ที่เลือก
    """
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("❌ ไม่พบ GEMINI_API_KEY ใน Environment Variables")
        # คืนค่าเป็น Client ของ Google GenAI SDK (ใหม่)
        return genai.Client(api_key=GEMINI_API_KEY)

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("❌ ไม่พบ OPENAI_API_KEY (สำหรับ OpenAI หรือ Groq)")

        # [สำคัญ] สร้าง Client โดยระบุ base_url เพื่อให้ชี้ไปที่ Groq ได้
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

    try:
        if LLM_PROVIDER == "gemini":
            # การดึง usage ของ Google GenAI SDK ใหม่
            usage = getattr(response, "usage_metadata", None)
            if usage:
                prompt_tokens = usage.prompt_token_count
                completion_tokens = usage.candidates_token_count
                total_tokens = usage.total_token_count

        elif LLM_PROVIDER == "openai":
            # การดึง usage ของ OpenAI / Groq
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens
    except Exception as e:
        print(f"⚠️ Error reading usage logs: {e}")

    print(
        f"🔢 {LLM_PROVIDER.capitalize()} token usage ({context}) - "
        f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}"
    )