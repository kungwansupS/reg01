import tiktoken
import redis
import json
import os
import logging
from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, REDIS_URL
from app.utils.llm.llm_model import get_llm_model

logger = logging.getLogger(__name__)

try:
    from google import genai
except ImportError:
    genai = None

# ----------------------------------------------------------------------------- #
# Hybrid QA Cache (Redis with Local Dict Fallback)
# ----------------------------------------------------------------------------- #
class HybridQACache:
    def __init__(self):
        self.local_cache = {}
        try:
            self.r = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            self.r.ping()
            self.use_redis = True
            logger.info("✅ Redis connected: QA Cache enabled.")
        except:
            self.use_redis = False
            logger.warning("⚠️ Redis disconnected: QA Cache using Local Memory.")

    def __contains__(self, key):
        if self.use_redis: return self.r.exists(f"qa_cache:{key}")
        return key in self.local_cache

    def __getitem__(self, key):
        if self.use_redis: return self.r.get(f"qa_cache:{key}")
        return self.local_cache.get(key)

    def __setitem__(self, key, value):
        if self.use_redis:
            self.r.setex(f"qa_cache:{key}", 3600, value)
        else:
            self.local_cache[key] = value

qa_cache = HybridQACache()

# ----------------------------------------------------------------------------- #
# Token & Summarization
# ----------------------------------------------------------------------------- #
try:
    ENCODING = tiktoken.encoding_for_model("gpt-3.5-turbo")
except:
    ENCODING = tiktoken.get_encoding("cl100k_base")

MAX_OUTPUT_TOKENS = 300

def count_tokens(text):
    return len(ENCODING.encode(text))

def summarize_chat_history(history):
    if not history: return ""
    full_dialogue = "".join([f"{'ผู้ใช้' if m['role'] == 'user' else 'AI'}: {m['parts'][0]['text']}\n" for m in history])
    prompt = f"สรุปบทสนทนาให้กระชับ ไม่เกิน {MAX_OUTPUT_TOKENS} token:\n{full_dialogue}"

    try:
        model = get_llm_model()
        if LLM_PROVIDER == "gemini":
            res = model.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
            return res.text.strip() if res.text else ""
        else:
            res = model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "system", "content": "สรุปใจความสำคัญ"}, {"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Summarize Error: {e}")
        return "(ไม่สามารถสรุปได้)"