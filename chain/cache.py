"""
chain/cache.py — Redis wrapper with in-memory dict fallback.
No app.* imports.
"""
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

_redis_client = None
_memory_store: dict = {}


def _get_redis():
    """Return a redis.asyncio client, or None if not configured."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    from chain.config import settings
    if not settings.REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
        )
        return _redis_client
    except Exception as exc:
        logger.warning("[cache] Redis init failed — using in-memory fallback: %s", exc)
        return None


async def cache_get(key: str) -> Optional[str]:
    r = _get_redis()
    if r:
        try:
            return await r.get(key)
        except Exception:
            pass
    return _memory_store.get(key)


async def cache_set(key: str, value: str, ttl: int = 300) -> None:
    r = _get_redis()
    if r:
        try:
            await r.setex(key, ttl, value)
            return
        except Exception:
            pass
    _memory_store[key] = value


async def cache_publish(channel: str, message: str) -> None:
    r = _get_redis()
    if r:
        try:
            await r.publish(channel, message)
        except Exception:
            pass


async def cache_delete(key: str) -> None:
    r = _get_redis()
    if r:
        try:
            await r.delete(key)
            return
        except Exception:
            pass
    _memory_store.pop(key, None)
