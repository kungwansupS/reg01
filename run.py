import sys
import os
import logging
import uvicorn
from dotenv import load_dotenv

# Path Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from backend.main import asgi_app
from backend.app.config import HOST, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    logging.info("🚀 Starting REG-01 Backend...")

    # Run ASGI Server ONLY
    logging.info(f"📡 Server running at {HOST}:{PORT}")
    uvicorn.run(
        asgi_app,
        host=HOST,
        port=PORT,
        workers=1,
        reload=False,
    )
