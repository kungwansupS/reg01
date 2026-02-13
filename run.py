import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv

# Path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from backend.main import asgi_app
from backend.core.settings import load_settings

settings = load_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    logging.info("[INFO] Starting REG-01 Backend...")
    logging.info("[INFO] Server running at %s:%s", settings.host, settings.port)
    uvicorn.run(
        asgi_app,
        host=settings.host,
        port=settings.port,
        workers=1,
        reload=False,
    )
