import os
import subprocess
import time
import logging
import httpx
import openai
import shutil
from google import genai
from app.config import (
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    LLM_PROVIDER,
    OPENAI_BASE_URL,
    LOCAL_API_KEY,
    LOCAL_BASE_URL,
    LOCAL_MODEL_NAME
)

logger = logging.getLogger(__name__)

def ensure_local_llm_ready():
    """
    ตรวจสอบและเตรียมความพร้อมสำหรับ Local LLM (Ollama)
    """
    if LLM_PROVIDER != "local":
        return

    ollama_path = shutil.which("ollama")
    if not ollama_path:
        logger.error("❌ ไม่พบโปรแกรม 'ollama' ใน System PATH")
        return

    base_url_only = LOCAL_BASE_URL.replace("/v1", "")
    
    try:
        with httpx.Client() as client:
            client.get(base_url_only, timeout=2.0)
    except Exception:
        logger.info("🚀 กำลังเริ่มต้น Ollama Service...")
        try:
            if os.name == 'nt': 
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else: 
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            for _ in range(10):
                time.sleep(1)
                try:
                    with httpx.Client() as client:
                        if client.get(base_url_only).status_code == 200:
                            break
                except:
                    continue
        except Exception as e:
            logger.error(f"❌ ไม่สามารถเปิด Ollama อัตโนมัติได้: {e}")
            return

    try:
        with httpx.Client(timeout=10.0) as client:
            tags_response = client.get(f"{base_url_only}/api/tags")
            models = [m['name'] for m in tags_response.json().get('models', [])]
            
            target_model = LOCAL_MODEL_NAME
            if target_model not in models and f"{target_model}:latest" not in models:
                logger.info(f"📥 กำลังติดตั้งโมเดล {target_model} (โปรดรอสักครู่)...")
                subprocess.run(["ollama", "pull", target_model], shell=(os.name == 'nt'), check=True)
                logger.info(f"✅ ติดตั้งโมเดล {target_model} สำเร็จ")
    except Exception as e:
        logger.warning(f"⚠️ การ Pull โมเดลขัดข้อง: {e}")

def get_llm_model():
    """
    สร้างและคืนค่า Client ของ LLM (Async สำหรับ OpenAI/Local, GenAI Client สำหรับ Gemini)
    """
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("❌ ไม่พบ GEMINI_API_KEY")
        # GenAI SDK รองรับ .aio สำหรับการเรียกใช้แบบ asynchronous
        return genai.Client(api_key=GEMINI_API_KEY)

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("❌ ไม่พบ OPENAI_API_KEY")
        return openai.AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

    elif LLM_PROVIDER == "local":
        ensure_local_llm_ready()
        return openai.AsyncOpenAI(
            api_key=LOCAL_API_KEY,
            base_url=LOCAL_BASE_URL
        )
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

def log_llm_usage(response, context="", model_name=None):
    """
    บันทึกการใช้งาน Token ของระบบ
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    try:
        if LLM_PROVIDER == "gemini":
            usage = getattr(response, "usage_metadata", None)
            if usage:
                prompt_tokens = usage.prompt_token_count
                completion_tokens = usage.candidates_token_count
                total_tokens = usage.total_token_count
        else:
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens
    except Exception as e:
        logger.warning(f"⚠️ ไม่สามารถบันทึก Usage Log ได้: {e}")

    logger.info(f"🔢 {LLM_PROVIDER.upper()} Usage ({context}) - Total: {total_tokens} tokens")