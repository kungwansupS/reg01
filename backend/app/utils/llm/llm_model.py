import os
import subprocess
import time
import logging
import httpx
import openai
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
    ตรวจสอบสถานะของ Ollama และติดตั้งโมเดลอัตโนมัติถ้ายังไม่มี
    """
    if LLM_PROVIDER != "local":
        return

    # 1. ตรวจสอบว่า Ollama Service เปิดอยู่หรือไม่
    # ดึงเฉพาะ Base URL เช่น http://localhost:11434
    base_url_only = LOCAL_BASE_URL.replace("/v1", "")
    
    try:
        with httpx.Client() as client:
            response = client.get(base_url_only)
    except Exception:
        logger.info("🚀 กำลังเริ่มต้น Ollama Service...")
        try:
            # พยายามเปิด Ollama (รองรับทั้ง Windows และ Linux/Mac)
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
        except FileNotFoundError:
            logger.error("❌ ไม่พบคำสั่ง 'ollama' ในเครื่อง โปรดติดตั้ง Ollama ก่อน (https://ollama.com)")
            return

    # 2. ตรวจสอบว่ามีโมเดลอยู่ในเครื่องหรือยัง
    try:
        with httpx.Client(timeout=30.0) as client:
            tags_response = client.get(f"{base_url_only}/api/tags")
            models = [m['name'] for m in tags_response.json().get('models', [])]
            
            # ตรวจสอบชื่อโมเดล (Ollama มักจะใส่ :latest อัตโนมัติถ้าไม่ได้ระบุ)
            target_model = LOCAL_MODEL_NAME
            if target_model not in models and f"{target_model}:latest" not in models:
                logger.info(f"📥 ไม่พบโมเดล {target_model} กำลังดาวน์โหลดอัตโนมัติ (อาจใช้เวลาสักครู่)...")
                # สั่ง pull โมเดลผ่าน subprocess เพื่อให้เห็น progress ใน terminal
                subprocess.run(["ollama", "pull", target_model], check=True)
                logger.info(f"✅ ติดตั้งโมเดล {target_model} เรียบร้อยแล้ว")
    except Exception as e:
        logger.warning(f"⚠️ ไม่สามารถตรวจสอบโมเดลอัตโนมัติได้: {e}")

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
        # ตรวจสอบความพร้อมของ Local LLM ก่อนสร้าง Client
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

    print(
        f"🔢 {LLM_PROVIDER.capitalize()} token usage ({context}) - "
        f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}"
    )