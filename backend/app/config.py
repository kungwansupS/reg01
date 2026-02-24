import os
from dotenv import load_dotenv

# เนเธซเธฅเธ”เธเนเธฒเธเธฒเธเนเธเธฅเน .env
load_dotenv()

# Path เธเธทเนเธเธเธฒเธเธเธญเธเนเธเธฃเน€เธเธเธ•เน
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------- #
# LLM PROVIDER & MODEL CONFIGURATION
# ----------------------------------------------------------------------------- #
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # เธ•เธฑเธงเน€เธฅเธทเธญเธ: gemini, openai, local

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


def _env_bool(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str = "") -> list[str]:
    raw = str(os.getenv(name, default) or "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_int(name: str, default: str) -> int:
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return int(default)

# เนเธชเธ”เธเธชเธ–เธฒเธเธฐเน€เธฃเธดเนเธกเธ•เนเธ
print(f"LLM Provider: {LLM_PROVIDER}")

# ----------------------------------------------------------------------------- #
# RAG & CONTENT FOLDER CONFIGURATION
# ----------------------------------------------------------------------------- #
# เนเธเธฅเน€เธ”เธญเธฃเนเน€เธเนเธ PDF เธ•เนเธเธเธเธฑเธ
PDF_INPUT_FOLDER = os.getenv(
    "PDF_INPUT_FOLDER",
    os.path.join(BASE_DIR, "static/docs")
)

# เนเธเธฅเน€เธ”เธญเธฃเนเน€เธเนเธเนเธเธฅเน .txt เธ—เธตเนเนเธเธฅเธเนเธฅเนเธงเธชเธณเธซเธฃเธฑเธ RAG
PDF_QUICK_USE_FOLDER = os.getenv(
    "PDF_QUICK_USE_FOLDER",
    os.path.join(BASE_DIR, "static/quick_use")
)

# Startup embedding pipeline
RAG_STARTUP_EMBEDDING = _env_bool("RAG_STARTUP_EMBEDDING", "true")
RAG_STARTUP_PROCESS_PDF = _env_bool("RAG_STARTUP_PROCESS_PDF", "true")
RAG_STARTUP_BUILD_HYBRID = _env_bool("RAG_STARTUP_BUILD_HYBRID", "true")

# โ… FIX: เน€เธเธฅเธตเนเธขเธเธเธฒเธ session_storage เน€เธเนเธ sessions เธซเธฃเธทเธญเธ•เธฒเธกเธเธทเนเธญเนเธเธฅเน€เธ”เธญเธฃเนเธเธฃเธดเธ
# เนเธเธฅเน€เธ”เธญเธฃเนเธชเธณเธซเธฃเธฑเธเน€เธเนเธเธเธฃเธฐเธงเธฑเธ•เธดเธเธฒเธฃเธชเธเธ—เธเธฒ (Session Memory)
SESSION_DIR = os.getenv(
    "SESSION_DIR",
    os.path.join(BASE_DIR, "../memory/session_storage")  # เนเธเนเธเธทเนเธญ session_storage
)

# เนเธเธฅเนเน€เธเนเธเธเธฒเธฃเธ•เธฑเนเธเธเนเธฒเธชเธ–เธฒเธเธฐ Bot
BOT_SETTINGS_FILE = os.path.join(BASE_DIR, "../memory/bot_settings.json")

# ----------------------------------------------------------------------------- #
# SERVER & NETWORK CONFIGURATION
# ----------------------------------------------------------------------------- #
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")
ALLOWED_ORIGINS = _env_csv("ALLOWED_ORIGINS", "*")

# ----------------------------------------------------------------------------- #
# RESOURCE CONTROL & SECURITY (PHASE 1 & 2)
# ----------------------------------------------------------------------------- #
# [PHASE 1] เธเธณเธเธฑเธ”เธเธณเธเธงเธเธเธฒเธฃเน€เธฃเธตเธขเธ LLM เธเธฃเนเธญเธกเธเธฑเธ (Global Semaphore)
MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "10"))

# [PHASE 2] เธเธตเธขเนเธชเธณเธซเธฃเธฑเธเธ•เธฃเธงเธเธชเธญเธเธเธงเธฒเธกเธ–เธนเธเธ•เนเธญเธ
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "your-university-sso-secret")

# Web speech API hardening
SPEECH_REQUIRE_API_KEY = _env_bool("SPEECH_REQUIRE_API_KEY", "true")
SPEECH_ALLOWED_API_KEYS = _env_csv("SPEECH_ALLOWED_API_KEYS", "")
SPEECH_RATE_LIMIT_PER_MINUTE = max(1, _env_int("SPEECH_RATE_LIMIT_PER_MINUTE", "30"))

# Audit log hardening
AUDIT_LOG_RETENTION_DAYS = max(1, _env_int("AUDIT_LOG_RETENTION_DAYS", "30"))
AUDIT_LOG_MAX_SIZE_MB = max(1, _env_int("AUDIT_LOG_MAX_SIZE_MB", "20"))

# ----------------------------------------------------------------------------- #
# QUEUE SYSTEM CONFIGURATION (Multi-User Support)
# ----------------------------------------------------------------------------- #
# จำนวน worker สำหรับประมวลผล LLM request พร้อมกัน
QUEUE_NUM_WORKERS = max(1, _env_int("QUEUE_NUM_WORKERS", "10"))
# จำนวน request สูงสุดที่รอในคิว (pending + active)
QUEUE_MAX_SIZE = max(10, _env_int("QUEUE_MAX_SIZE", "200"))
# จำนวน request สูงสุดต่อผู้ใช้ (pending + active)
QUEUE_PER_USER_LIMIT = max(1, _env_int("QUEUE_PER_USER_LIMIT", "3"))
# เวลาสูงสุดที่ request จะรอในคิว (วินาที)
QUEUE_REQUEST_TIMEOUT = max(10, _env_int("QUEUE_REQUEST_TIMEOUT", "120"))
# ระยะเวลาระหว่าง health log (วินาที)
QUEUE_HEALTH_LOG_INTERVAL = max(10, _env_int("QUEUE_HEALTH_LOG_INTERVAL", "60"))

# ----------------------------------------------------------------------------- #
# DATABASE (PostgreSQL)
# ----------------------------------------------------------------------------- #
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/reg01")
DB_POOL_MIN_SIZE = max(1, _env_int("DB_POOL_MIN_SIZE", "2"))
DB_POOL_MAX_SIZE = max(1, _env_int("DB_POOL_MAX_SIZE", "10"))

# ----------------------------------------------------------------------------- #
# REDIS
# ----------------------------------------------------------------------------- #
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ----------------------------------------------------------------------------- #
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------- #
def debug_list_files(folder_path: str, label: str = "Files"):
    """
    เธเธฑเธเธเนเธเธฑเธเธเนเธงเธขเธ•เธฃเธงเธเธชเธญเธเนเธเธฅเนเนเธเนเธเธฅเน€เธ”เธญเธฃเน (เนเธเนเนเธ retriever)
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
