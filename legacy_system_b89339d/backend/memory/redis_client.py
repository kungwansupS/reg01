"""
Redis async client — shared connection for queue persistence & FAQ cache

Usage:
    from memory.redis_client import init_redis, close_redis, get_redis

    # At startup:
    await init_redis("redis://localhost:6379/0")

    # In business logic:
    r = get_redis()
    await r.set("key", "value")

    # At shutdown:
    await close_redis()
"""

import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def init_redis(url: str = "redis://localhost:6379/0"):
    """สร้าง Redis connection — เรียกครั้งเดียวตอน startup"""
    global _redis
    _redis = aioredis.from_url(url, decode_responses=True)
    # Verify connectivity
    await _redis.ping()
    logger.info("✅ Redis connected (%s)", url.split("@")[-1] if "@" in url else url)


async def close_redis():
    """ปิด Redis connection — เรียกตอน shutdown"""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("✅ Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Return the shared Redis instance."""
    if _redis is None:
        raise RuntimeError("Redis not initialized — call init_redis() first")
    return _redis
