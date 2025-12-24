import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "verify123")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")

# LLM Settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Infrastructure Settings (Redis)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Folders
PDF_INPUT_FOLDER = os.path.join(BASE_DIR, "app/static/docs")
PDF_QUICK_USE_FOLDER = os.path.join(BASE_DIR, "app/static/quick_use")
SESSION_DIR = os.path.join(BASE_DIR, "memory/session_storage")

# App Settings
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

def debug_list_files(folder_path: str, label: str = "Files"):
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