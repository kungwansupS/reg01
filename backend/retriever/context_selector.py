# [FILE: backend/retriever/context_selector.py - FULLCODE ONLY]
import os
import threading
import logging
from app.config import PDF_QUICK_USE_FOLDER, debug_list_files
from app.utils.vector_manager import vector_manager

# ตั้งค่า Logging สำหรับการตรวจสอบการทำงาน
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContextSelector")

# ------------------------------------------------------------------
# Global Cache & Lock
# ------------------------------------------------------------------
# เก็บไว้เพื่อรองรับฟังก์ชันการอ่านไฟล์ดิบสำหรับระบบ Ingestion ใน Phase ถัดไป
_chunks_cache = []
_cache_lock = threading.Lock()

def get_file_chunks(folder=PDF_QUICK_USE_FOLDER, separator="===================", force_reload=False):
    """
    ดึงข้อมูล Chunks จากไฟล์ต้นทาง (.txt) พร้อมระบบ Caching 
    ใช้สำหรับการทำ Indexing ลงฐานข้อมูล หรือตรวจสอบเนื้อหาดิบ
    """
    global _chunks_cache
    
    with _cache_lock:
        if _chunks_cache and not force_reload:
            return _chunks_cache

        debug_list_files(folder, "📄 Quick-use TXT files for Indexing")
        new_chunks = []
        
        if not os.path.exists(folder):
            logger.warning(f"⚠️ Folder not found: {folder}")
            return []

        for root, _, files in os.walk(folder):
            for filename in sorted(files):
                if filename.endswith(".txt"):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        parts = content.split(separator)
                        for i, chunk in enumerate(parts):
                            chunk = chunk.strip()
                            if chunk:
                                new_chunks.append({
                                    "chunk": chunk,
                                    "source": filepath,
                                    "index": i
                                })
                    except Exception as e:
                        logger.error(f"❌ Error reading {filename}: {e}")
        
        _chunks_cache = new_chunks
        return _chunks_cache

def retrieve_top_k_chunks(query, k=5, folder=PDF_QUICK_USE_FOLDER):
    """
    ค้นหาข้อมูลที่ใกล้เคียงที่สุดโดยใช้ Vector Database (ChromaDB)
    แทนที่การคำนวณ Dot Product สดแบบเดิม
    
    Args:
        query: ข้อความที่ต้องการค้นหา
        k: จำนวนผลลัพธ์ที่ต้องการ (Top K)
        folder: พารามิเตอร์คงไว้เพื่อความเข้ากันได้ของ Signature (Compatibility)
    """
    try:
        # 1. ค้นหาข้อมูลผ่าน Vector Manager (ChromaDB)
        # ระบบจะทำการแปลง Query เป็น Vector และค้นหาใน Index อัตโนมัติ
        results = vector_manager.search(query, k=k)
        
        if not results:
            logger.info(f"🔍 Search Result: No relevant chunks found for '{query}'")
            return []

        # 2. แปลงรูปแบบผลลัพธ์กลับเป็น (entry, score) เพื่อให้เข้ากับระบบ LLM เดิม
        # โดยที่ entry ต้องมี key 'chunk' และ 'source'
        scored_chunks = []
        for r in results:
            entry = {
                "chunk": r['chunk'],
                "source": r['source'],
                "index": r.get('index', 0) # แถม index เพื่อความสมบูรณ์ของ Metadata
            }
            # r['score'] ใน ChromaDB คือ Distance (ยิ่งน้อยยิ่งใกล้)
            scored_chunks.append((entry, r['score']))
            
        logger.info(f"✅ Retrieved {len(scored_chunks)} chunks from Vector DB")
        return scored_chunks

    except Exception as e:
        logger.error(f"❌ Retrieval Error: {e}")
        # หากเกิดข้อผิดพลาด ให้คืนค่าลิสต์ว่างเพื่อไม่ให้ระบบ LLM พัง (No-Error Policy)
        return []