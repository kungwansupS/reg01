# [FILE: backend/app/config.py - FULLCODE ONLY]
import os
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

# Path พื้นฐานของโปรเจกต์
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------- #
# LLM PROVIDER & MODEL CONFIGURATION
# ----------------------------------------------------------------------------- #
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # ตัวเลือก: gemini, openai, local

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Local Model (Ollama/vLLM) Configuration
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "ollama")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "chinda-qwen3-4b")
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")

# แสดงสถานะเริ่มต้น
print(f"🚀 LLM Provider: {LLM_PROVIDER}")

# ----------------------------------------------------------------------------- #
# RAG & CONTENT FOLDER CONFIGURATION
# ----------------------------------------------------------------------------- #
# โฟลเดอร์เก็บ PDF ต้นฉบับ
PDF_INPUT_FOLDER = os.getenv(
    "PDF_INPUT_FOLDER",
    os.path.join(BASE_DIR, "static/docs")
)

# โฟลเดอร์เก็บไฟล์ .txt ที่แปลงแล้วสำหรับ RAG
PDF_QUICK_USE_FOLDER = os.getenv(
    "PDF_QUICK_USE_FOLDER",
    os.path.join(BASE_DIR, "static/quick_use")
)

# ✅ FIX: เปลี่ยนจาก session_storage เป็น sessions หรือตามชื่อโฟลเดอร์จริง
# โฟลเดอร์สำหรับเก็บประวัติการสนทนา (Session Memory)
SESSION_DIR = os.getenv(
    "SESSION_DIR",
    os.path.join(BASE_DIR, "../memory/session_storage")  # ใช้ชื่อ session_storage
)

# ไฟล์เก็บการตั้งค่าสถานะ Bot
BOT_SETTINGS_FILE = os.path.join(BASE_DIR, "../memory/bot_settings.json")

# ----------------------------------------------------------------------------- #
# SERVER & NETWORK CONFIGURATION
# ----------------------------------------------------------------------------- #
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ----------------------------------------------------------------------------- #
# RESOURCE CONTROL & SECURITY (PHASE 1 & 2)
# ----------------------------------------------------------------------------- #
# [PHASE 1] จำกัดจำนวนการเรียก LLM พร้อมกัน (Global Semaphore)
MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "10"))

# [PHASE 2] คีย์สำหรับตรวจสอบความถูกต้อง
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "your-university-sso-secret")

# ----------------------------------------------------------------------------- #
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------- #
def debug_list_files(folder_path: str, label: str = "Files"):
    """
    ฟังก์ชันช่วยตรวจสอบไฟล์ในโฟลเดอร์ (ใช้ใน retriever)
    """
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return

    files = os.listdir(folder_path)
    if not files:
        print(f"{label}: No files found in {folder_path}")
        return

    print(f"{label} ({folder_path}):")
    for f in files:
        print(f"  - {f}")

# ตรวจสอบและแสดงข้อมูล SESSION_DIR
print(f"📁 SESSION_DIR: {SESSION_DIR}")
if os.path.exists(SESSION_DIR):
    file_count = len([f for f in os.listdir(SESSION_DIR) if f.endswith('.json')])
    print(f"✅ Found {file_count} session files")
else:
    print(f"⚠️ SESSION_DIR does not exist, will be created on first use")