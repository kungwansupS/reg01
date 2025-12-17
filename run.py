import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

import logging
from backend.main import asgi_app
import uvicorn
from backend.app.config import HOST, PORT
from backend.pdf_to_txt import process_pdfs

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    logging.info("Processing PDFs...")
    process_pdfs()

    logging.info("Starting ASGI server...")
    uvicorn.run(asgi_app, host=HOST, port=PORT, workers=1, reload=False)
