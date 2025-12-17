import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

# [สำคัญ] เพิ่มบรรทัดนี้เพื่อให้รองรับ Groq หรือ Local LLM
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

print ("LLM Provider: " + LLM_PROVIDER)

PDF_QUICK_USE_FOLDER = os.getenv(
    "PDF_QUICK_USE_FOLDER",
    os.path.join(BASE_DIR, "static/quick_use")
)

PDF_INPUT_FOLDER = os.getenv(
    "PDF_INPUT_FOLDER",
    os.path.join(BASE_DIR, "static/docs")
)

SESSION_DIR = os.getenv(
    "SESSION_DIR",
    os.path.join(BASE_DIR, "../memory/session_storage")
)

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