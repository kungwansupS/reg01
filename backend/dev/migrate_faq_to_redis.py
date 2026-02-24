"""
Migration Script: JSON FAQ Cache → Redis
─────────────────────────────────────────
Reads the existing faq_cache.json file and imports all entries into Redis.

Usage:
    cd backend
    python -m dev.migrate_faq_to_redis

Requirements:
    - Redis server running
    - REDIS_URL env var set (or defaults to redis://localhost:6379/0)
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MigrateFAQ")

FAQ_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory", "cache", "faq_cache.json")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def migrate():
    from memory.redis_client import init_redis, close_redis, get_redis
    from memory.faq_cache import (
        REDIS_FAQ_PREFIX,
        REDIS_FAQ_INDEX,
        DEFAULT_TTL_SECONDS,
        _safe_int,
    )

    # Load JSON file
    faq_path = os.path.normpath(FAQ_JSON_PATH)
    if not os.path.exists(faq_path):
        logger.error("FAQ JSON file not found: %s", faq_path)
        return

    with open(faq_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        logger.error("Invalid FAQ file format (expected dict)")
        return

    logger.info("Loaded %d FAQ entries from %s", len(data), faq_path)

    # Connect to Redis
    await init_redis(REDIS_URL)
    r = get_redis()

    imported = 0
    skipped = 0

    for question, entry in data.items():
        if not isinstance(entry, dict):
            skipped += 1
            continue
        answer = str(entry.get("answer") or "").strip()
        if not answer:
            skipped += 1
            continue

        ttl = _safe_int(entry.get("ttl_seconds"), DEFAULT_TTL_SECONDS, 60, 365 * 86400)
        key = f"{REDIS_FAQ_PREFIX}{question}"

        await r.set(key, json.dumps(entry, ensure_ascii=False), ex=ttl)
        await r.sadd(REDIS_FAQ_INDEX, question)
        imported += 1

    logger.info("✅ Migration complete: %d imported, %d skipped", imported, skipped)

    # Verify
    count = await r.scard(REDIS_FAQ_INDEX)
    logger.info("Redis FAQ index now has %d entries", count)

    await close_redis()


if __name__ == "__main__":
    asyncio.run(migrate())
