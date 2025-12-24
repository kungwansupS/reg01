import os
import json
import logging
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_FILE = os.path.join(BASE_DIR, "cache/faq_cache.json")

MAX_FAQ = 500 # ขยายขนาดคลังความรู้
SIM_THRESHOLD = 0.9

# Load model ครั้งเดียวที่ระดับ Module
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

try:
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        faq_cache = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    faq_cache = {}

def save_faq_cache():
    try:
        os.makedirs(os.path.dirname(FAQ_FILE), exist_ok=True)
        with open(FAQ_FILE, "w", encoding="utf-8") as f:
            json.dump(faq_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save FAQ Error: {e}")

def encode_text(text):
    return model.encode(text, convert_to_tensor=True, show_progress_bar=False)

def get_faq_answer(question):
    if not faq_cache: return None
    
    query_vec = encode_text(question)
    best_match = None
    best_score = SIM_THRESHOLD

    for q in faq_cache:
        # เปรียบเทียบความหมายของประโยค
        score = util.cos_sim(query_vec, encode_text(q)).item()
        if score > best_score:
            best_score = score
            best_match = q

    if best_match:
        faq_cache[best_match]["count"] = faq_cache[best_match].get("count", 0) + 1
        save_faq_cache()
        return faq_cache[best_match]["answer"]
    return None

def update_faq(question, answer):
    """ระบบเรียนรู้: เพิ่มหรืออัปเดตข้อมูลในคลัง FAQ"""
    now = datetime.now().isoformat()
    query_vec = encode_text(question)

    # ตรวจสอบว่ามีคำถามที่ใกล้เคียงกันอยู่แล้วหรือไม่
    for q in faq_cache:
        score = util.cos_sim(query_vec, encode_text(q)).item()
        if score > SIM_THRESHOLD:
            # ถ้ามีแล้ว ให้อัปเดตคำตอบให้ทันสมัยขึ้น
            faq_cache[q]["answer"] = answer
            faq_cache[q]["last_updated"] = now
            save_faq_cache()
            return

    # ถ้าเป็นเรื่องใหม่และคลังเต็ม ให้ลบตัวที่คนใช้น้อยที่สุดออก
    if len(faq_cache) >= MAX_FAQ:
        sorted_faq = sorted(faq_cache.items(), key=lambda x: x[1].get("count", 0))
        del faq_cache[sorted_faq[0][0]]

    faq_cache[question] = {
        "answer": answer,
        "count": 1,
        "last_updated": now,
        "learned": True # ระบุว่าข้อมูลนี้มาจากการเรียนรู้ของ AI
    }
    save_faq_cache()

def get_faq_analytics():
    """สรุปสถิติความรู้ของระบบสำหรับ Admin"""
    total = len(faq_cache)
    top_questions = sorted(faq_cache.items(), key=lambda x: x[1].get("count", 0), reverse=True)[:10]
    learned_count = sum(1 for q in faq_cache.values() if q.get("learned"))
    
    return {
        "total_knowledge_base": total,
        "auto_learned_count": learned_count,
        "top_faqs": [{"question": k, "hits": v["count"]} for k, v in top_questions]
    }