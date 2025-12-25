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

# ========================================================================
# 🗄️ AUTO-INITIALIZE DATABASE
# ========================================================================
print("=" * 70)
print("🗄️  Initializing Database System...")
print("=" * 70)

try:
    from backend.database.connection import init_database, check_database_health
    
    # สร้าง Database Tables
    if init_database():
        print("✅ Database initialized successfully")
    else:
        print("⚠️  Database already exists, skipping initialization")
    
    # ตรวจสอบสุขภาพ Database
    if check_database_health():
        print("✅ Database health check passed")
    else:
        print("❌ Database health check failed")
        sys.exit(1)
        
except ImportError as e:
    print("⚠️  Database module not found, using fallback JSON mode")
    print(f"   Error: {e}")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")
    print("   Continuing with JSON fallback...")

print("=" * 70)

# ========================================================================
# PDF PROCESSING
# ========================================================================
from backend.main import asgi_app
from backend.app.config import HOST, PORT
from backend.pdf_to_txt import process_pdfs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    logging.info("🚀 Starting REG-01 Backend...")

    # Pre-process PDFs
    process_pdfs()

    # Run ASGI Server ONLY
    logging.info(f"📡 Server running at {HOST}:{PORT}")
    uvicorn.run(
        asgi_app,
        host=HOST,
        port=PORT,
        workers=1,
        reload=False,
    )