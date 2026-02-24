import sys
import os
import logging
import asyncio
import uvicorn
from dotenv import load_dotenv

# Path Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from backend.main import asgi_app
from app.config import HOST, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ----------------------------------------------------------------------------- #
# PENDING QUEUE CHECK (async — ย้ายไปทำที่ main.py startup เพราะต้องใช้ Redis)
# ----------------------------------------------------------------------------- #
# Queue recovery ตรวจสอบอัตโนมัติที่ main.py startup_event()
# ถ้า env _QUEUE_RECOVERY_ACTION=prompt → ถาม console
# ถ้า env _QUEUE_RECOVERY_ACTION=process → ประมวลผลอัตโนมัติ
# default → ไม่ทำอะไร

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        # Avoid Proactor event loop shutdown issues on Windows.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # ส่ง recovery action ผ่าน env (default: auto-check at startup)
    os.environ.setdefault("_QUEUE_RECOVERY_ACTION", "process")

    logging.info("Starting REG-01 Backend...")

    # Run ASGI Server ONLY
    logging.info(f"Server running at {HOST}:{PORT}")
    uvicorn.run(
        asgi_app,
        host=HOST,
        port=PORT,
        workers=1,
        reload=False,
    )
