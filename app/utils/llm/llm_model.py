import os
import openai
import google.generativeai as genai
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME, OPENAI_API_KEY, OPENAI_MODEL_NAME, LLM_PROVIDER

openai.api_key = OPENAI_API_KEY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_llm_model():
    if LLM_PROVIDER == "gemini":
        return genai.GenerativeModel(GEMINI_MODEL_NAME)
    elif LLM_PROVIDER == "openai":
        return openai
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

def log_llm_usage(response, context="", model_name=None):
    if LLM_PROVIDER == "gemini":
        usage = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tokens = usage.prompt_token_count
            completion_tokens = usage.candidates_token_count
            total_tokens = usage.total_token_count
        else:
            print(f"❌ ไม่มี usage metadata ({context})")
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