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
    ตรวจสอบสถานะของ Ollama และติดตั้งโมเดลอัตโนมัติ
    """
    if LLM_PROVIDER != "local":
        return

    # 1. ตรวจสอบว่ามีโปรแกรม Ollama ในเครื่องหรือไม่ (ป้องกัน WinError 2)
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        logger.error("❌ ไม่พบโปรแกรม 'ollama' ใน System PATH โปรดติดตั้งจาก https://ollama.com")
        return

    base_url_only = LOCAL_BASE_URL.replace("/v1", "")
    
    # 2. ตรวจสอบว่า Service เปิดอยู่หรือไม่
    try:
        with httpx.Client() as client:
            client.get(base_url_only, timeout=2.0)
    except Exception:
        logger.info("🚀 กำลังเริ่มต้น Ollama Service...")
        try:
            if os.name == 'nt': # Windows
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else: # Linux/Mac
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # รอ Service เริ่มทำงาน (สูงสุด 10 วินาที)
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

    # 3. ตรวจสอบและดาวน์โหลดโมเดลอัตโนมัติ
    try:
        with httpx.Client(timeout=10.0) as client:
            tags_response = client.get(f"{base_url_only}/api/tags")
            models = [m['name'] for m in tags_response.json().get('models', [])]
            
            target_model = LOCAL_MODEL_NAME
            if target_model not in models and f"{target_model}:latest" not in models:
                logger.info(f"📥 กำลังติดตั้งโมเดล {target_model} อัตโนมัติ (โปรดรอสักครู่)...")
                subprocess.run(["ollama", "pull", target_model], shell=(os.name == 'nt'), check=True)
                logger.info(f"✅ ติดตั้งโมเดล {target_model} สำเร็จ")
    except Exception as e:
        logger.warning(f"⚠️ การ Pull โมเดลขัดข้อง: {e}")

def get_llm_model():
    """
    สร้างและคืนค่า Client ของ LLM ตาม Provider ที่เลือก
    """
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("❌ ไม่พบ GEMINI_API_KEY ใน Environment Variables")
        return genai.Client(api_key=GEMINI_API_KEY)

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("❌ ไม่พบ OPENAI_API_KEY")
        return openai.OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

    elif LLM_PROVIDER == "local":
        # ตรวจสอบความพร้อมก่อนสร้าง Client
        ensure_local_llm_ready()
        return openai.OpenAI(
            api_key=LOCAL_API_KEY,
            base_url=LOCAL_BASE_URL
        )
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

def log_llm_usage(response, context="", model_name=None):
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
        elif LLM_PROVIDER in ["openai", "local"]:
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens
    except Exception as e:
        print(f"⚠️ Error reading usage logs: {e}")

    print(f"🔢 {LLM_PROVIDER.capitalize()} usage ({context}) - Total: {total_tokens}")