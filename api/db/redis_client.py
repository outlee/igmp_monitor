import redis.asyncio as aioredis
from config import REDIS_URL

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
