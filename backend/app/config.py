import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# LLM Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

print(f"✅ Config Loaded: Provider={LLM_PROVIDER}, Model={GEMINI_MODEL_NAME}")

# Directories
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

# Vector DB Config
QDRANT_PATH = os.getenv(
    "QDRANT_PATH",
    os.path.join(BASE_DIR, "../qdrant_data")
)

# Ensure directories exist
os.makedirs(PDF_QUICK_USE_FOLDER, exist_ok=True)
os.makedirs(QDRANT_PATH, exist_ok=True)

# Server Config
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")