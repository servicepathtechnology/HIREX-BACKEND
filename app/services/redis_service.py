"""Redis Service for caching and sorted sets."""

import json
import logging
from typing import Optional, Dict, List, Any
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Async Redis client wrapper with graceful fallback."""

    def __init__(self):
        self._redis = None
        self._available = False
        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._available = True
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}. Running without Redis.")
            self._available = False

    @property
    def redis(self):
        """Get Redis client if available."""
        if not self._available:
            raise RuntimeError("Redis is not available")
        return self._redis
    
    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._available

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._available:
            return None
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        """Set key-value with optional expiration."""
        if not self._available:
            return
        try:
            await self.redis.set(key, value, ex=ex)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    async def setex(self, key: str, seconds: int, value: str):
        """Set key-value with expiration."""
        if not self._available:
            return
        try:
            await self.redis.setex(key, seconds, value)
        except Exception as e:
            logger.warning(f"Redis setex failed: {e}")

    async def delete(self, *keys: str):
        """Delete one or more keys."""
        if not self._available or not keys:
            return
        try:
            await self.redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")

    async def zadd(self, key: str, mapping: Dict[str, float]):
        """Add members to sorted set."""
        if not self._available:
            return
        try:
            await self.redis.zadd(key, mapping)
        except Exception as e:
            logger.warning(f"Redis zadd failed: {e}")

    async def zrevrank(self, key: str, member: str) -> Optional[int]:
        """Get rank of member in sorted set (descending order)."""
        if not self._available:
            return None
        try:
            return await self.redis.zrevrank(key, member)
        except Exception as e:
            logger.warning(f"Redis zrevrank failed: {e}")
            return None

    async def zrevrange(
        self,
        key: str,
        start: int,
        end: int,
        withscores: bool = False
    ) -> List[Any]:
        """Get range from sorted set in descending order."""
        if not self._available:
            return []
        try:
            return await self.redis.zrevrange(key, start, end, withscores=withscores)
        except Exception as e:
            logger.warning(f"Redis zrevrange failed: {e}")
            return []

    async def zcard(self, key: str) -> int:
        """Get number of members in sorted set."""
        if not self._available:
            return 0
        try:
            return await self.redis.zcard(key)
        except Exception as e:
            logger.warning(f"Redis zcard failed: {e}")
            return 0

    async def expire(self, key: str, seconds: int):
        """Set expiration on key."""
        if not self._available:
            return
        try:
            await self.redis.expire(key, seconds)
        except Exception as e:
            logger.warning(f"Redis expire failed: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._available:
            return False
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis exists failed: {e}")
            return False

    async def hset(self, name: str, key: str, value: str):
        """Set hash field."""
        if not self._available:
            return
        try:
            await self.redis.hset(name, key, value)
        except Exception as e:
            logger.warning(f"Redis hset failed: {e}")

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field."""
        if not self._available:
            return None
        try:
            return await self.redis.hget(name, key)
        except Exception as e:
            logger.warning(f"Redis hget failed: {e}")
            return None

    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields."""
        if not self._available:
            return {}
        try:
            return await self.redis.hgetall(name)
        except Exception as e:
            logger.warning(f"Redis hgetall failed: {e}")
            return {}

    async def close(self):
        """Close Redis connection."""
        if self._available and self._redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.warning(f"Redis close failed: {e}")
