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
from queue_manager import LLMRequestQueue, format_pending_summary, format_detailed_list
from queue_manager.persistence import load_pending_items, clear_persisted, DEFAULT_PERSIST_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ----------------------------------------------------------------------------- #
# PENDING QUEUE CHECK (ก่อนเปิด server)
# ----------------------------------------------------------------------------- #
def check_and_prompt_pending_queue():
    """
    ตรวจสอบคิวค้างจากการรัน server ครั้งก่อน
    ถ้ามี → แสดงรายการและถามผู้ดูแลระบบ

    Returns:
        "process" — ต้องการประมวลผลคิวค้าง
        "clear"   — ต้องการล้างทิ้ง
        None      — ไม่มีคิวค้าง
    """
    # Resolve path relative to backend dir
    persist_path = os.path.join(BACKEND_DIR, DEFAULT_PERSIST_PATH)
    state = load_pending_items(persist_path)

    if not state:
        return None

    # แสดง summary
    print(format_pending_summary(state, max_display=20))

    while True:
        try:
            choice = input("  กรุณาเลือก [1/2/3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  → ล้างคิวทิ้ง (default)")
            return "clear"

        if choice == "1":
            print("\n  ✅ จะประมวลผลคิวค้างหลังเปิด server...")
            return "process"
        elif choice == "2":
            clear_persisted(persist_path)
            print("\n  🗑️ ล้างคิวค้างเรียบร้อยแล้ว")
            return "clear"
        elif choice == "3":
            print(format_detailed_list(state))
            # กลับไปถามอีกครั้ง
            print("\n  เลือกการดำเนินการ:")
            print("    [1] ประมวลผลคิวค้าง")
            print("    [2] ล้างคิวทิ้งทั้งหมด")
            continue
        else:
            print("  ⚠️ กรุณาเลือก 1, 2, หรือ 3")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        # Avoid Proactor event loop shutdown issues on Windows.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # ── ตรวจสอบคิวค้าง ──
    recovery_decision = check_and_prompt_pending_queue()

    # ส่งผลการตัดสินใจไปยัง main.py ผ่าน environment variable
    if recovery_decision == "process":
        os.environ["_QUEUE_RECOVERY_ACTION"] = "process"
    else:
        os.environ["_QUEUE_RECOVERY_ACTION"] = "none"

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
