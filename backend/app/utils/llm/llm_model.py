import os
import openai
from google import genai
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME, OPENAI_API_KEY, OPENAI_MODEL_NAME, LLM_PROVIDER

openai.api_key = OPENAI_API_KEY

def get_llm_model():
    if LLM_PROVIDER == "gemini":
        # อัปเดต: คืนค่าเป็น Client ของ google-genai
        if not GEMINI_API_KEY:
            raise ValueError("❌ ไม่พบ GEMINI_API_KEY ใน Environment Variables")
        return genai.Client(api_key=GEMINI_API_KEY)
    elif LLM_PROVIDER == "openai":
        return openai
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

def log_llm_usage(response, context="", model_name=None):
    if LLM_PROVIDER == "gemini":
        # อัปเดต: การดึง usage จาก response ของ SDK ใหม่ (ถ้ามี)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            # ตรวจสอบ attribute ที่ถูกต้องของ SDK ใหม่ (อาจแตกต่างกันไปตามเวอร์ชันย่อย)
            prompt_tokens = getattr(usage, "prompt_token_count", 0)
            completion_tokens = getattr(usage, "candidates_token_count", 0)
            total_tokens = getattr(usage, "total_token_count", 0)
        else:
            # กรณีไม่มีข้อมูล usage ให้แสดงเป็น 0
            prompt_tokens = completion_tokens = total_tokens = 0

    elif LLM_PROVIDER == "openai":
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
        else:
            prompt_tokens = completion_tokens = total_tokens = 0

    else:
        prompt_tokens = completion_tokens = total_tokens = 0

    print(
        f"🔢 {LLM_PROVIDER.capitalize()} token usage ({context}) - "
        f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}"
    )