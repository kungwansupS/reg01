import os
import json
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer, util

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_FILE = os.path.join(BASE_DIR, "cache/faq_cache.json")

MAX_FAQ = 200
SIM_THRESHOLD = 0.9

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

try:
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        faq_cache = json.load(f)
except FileNotFoundError:
    faq_cache = {}

def save_faq_cache():
    os.makedirs(os.path.dirname(FAQ_FILE), exist_ok=True)
    with open(FAQ_FILE, "w", encoding="utf-8") as f:
        json.dump(faq_cache, f, ensure_ascii=False, indent=2)

def encode(text):
    return model.encode(text, convert_to_tensor=True, show_progress_bar=False)

def get_faq_answer(question):
    query_vec = encode(question)
    best_match = None
    best_score = SIM_THRESHOLD

    for q in faq_cache:
        score = util.cos_sim(query_vec, encode(q)).item()
        if score > best_score:
            best_score = score
            best_match = q

    if best_match:
        faq_cache[best_match]["count"] += 1
        save_faq_cache()
        return faq_cache[best_match]["answer"]

    return None

def update_faq(question, answer, days=30):
    now = datetime.utcnow().isoformat()
    query_vec = encode(question)

    for q in faq_cache:
        score = util.cos_sim(query_vec, encode(q)).item()
        if score > SIM_THRESHOLD:
            faq_entry = faq_cache[q]
            faq_entry["count"] += 1

            if faq_entry["answer"] != answer:
                faq_entry["answer"] = answer
                faq_entry["last_updated"] = now

            save_faq_cache()
            return

    if len(faq_cache) >= MAX_FAQ:
        sorted_faq = sorted(faq_cache.items(), key=lambda x: x[1]["count"])
        del faq_cache[sorted_faq[0][0]]

    faq_cache[question] = {
        "answer": answer,
        "count": 1,
        "last_updated": now
    }
    save_faq_cache()

def get_top_faq(limit=100):
    return sorted(faq_cache.items(), key=lambda x: x[1]["count"], reverse=True)[:limit]

def is_faq_outdated(question, days=30):
    entry = faq_cache.get(question)
    if not entry or "last_updated" not in entry:
        return True

    try:
        last = datetime.fromisoformat(entry["last_updated"])
        return datetime.utcnow() - last > timedelta(days=days)
    except Exception:
        return True
