import os
import json
import redis
import logging
from datetime import datetime
from sentence_transformers import SentenceTransformer, util
from app.config import REDIS_URL, FAQ_CACHE_PATH

logger = logging.getLogger(__name__)
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# เชื่อมต่อ Redis
try:
    r_faq = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    r_faq.ping()
    USE_REDIS = True
except:
    USE_REDIS = False

FAQ_REDIS_KEY = "faq_cache_data"
SIM_THRESHOLD = 0.9

def _load_local_faq():
    if os.path.exists(FAQ_CACHE_PATH):
        with open(FAQ_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_local_faq(data):
    os.makedirs(os.path.dirname(FAQ_CACHE_PATH), exist_ok=True)
    with open(FAQ_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_faq_answer(question):
    faq_cache = json.loads(r_faq.get(FAQ_REDIS_KEY)) if USE_REDIS and r_faq.get(FAQ_REDIS_KEY) else _load_local_faq()
    if not faq_cache: return None

    query_vec = model.encode(question, convert_to_tensor=True, show_progress_bar=False)
    best_match, best_score = None, SIM_THRESHOLD

    for q in faq_cache:
        score = util.cos_sim(query_vec, model.encode(q, convert_to_tensor=True, show_progress_bar=False)).item()
        if score > best_score:
            best_score, best_match = score, q

    if best_match:
        faq_cache[best_match]["count"] += 1
        if USE_REDIS: r_faq.set(FAQ_REDIS_KEY, json.dumps(faq_cache, ensure_ascii=False))
        else: _save_local_faq(faq_cache)
        return faq_cache[best_match]["answer"]
    return None

def update_faq(question, answer):
    faq_cache = json.loads(r_faq.get(FAQ_REDIS_KEY)) if USE_REDIS and r_faq.get(FAQ_REDIS_KEY) else _load_local_faq()
    query_vec = model.encode(question, convert_to_tensor=True, show_progress_bar=False)

    for q in faq_cache:
        score = util.cos_sim(query_vec, model.encode(q, convert_to_tensor=True, show_progress_bar=False)).item()
        if score > SIM_THRESHOLD:
            faq_cache[q]["answer"] = answer
            faq_cache[q]["count"] += 1
            if USE_REDIS: r_faq.set(FAQ_REDIS_KEY, json.dumps(faq_cache, ensure_ascii=False))
            else: _save_local_faq(faq_cache)
            return

    faq_cache[question] = {"answer": answer, "count": 1, "last_updated": datetime.utcnow().isoformat()}
    if USE_REDIS: r_faq.set(FAQ_REDIS_KEY, json.dumps(faq_cache, ensure_ascii=False))
    else: _save_local_faq(faq_cache)