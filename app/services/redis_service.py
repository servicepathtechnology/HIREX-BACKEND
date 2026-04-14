"""Redis Service for caching and sorted sets."""

import json
from typing import Optional, Dict, List, Any
import redis.asyncio as redis
from app.core.config import settings


class RedisService:
    """Async Redis client wrapper."""

    def __init__(self):
        self.redis = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self.redis.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        """Set key-value with optional expiration."""
        await self.redis.set(key, value, ex=ex)

    async def setex(self, key: str, seconds: int, value: str):
        """Set key-value with expiration."""
        await self.redis.setex(key, seconds, value)

    async def delete(self, *keys: str):
        """Delete one or more keys."""
        if keys:
            await self.redis.delete(*keys)

    async def zadd(self, key: str, mapping: Dict[str, float]):
        """Add members to sorted set."""
        await self.redis.zadd(key, mapping)

    async def zrevrank(self, key: str, member: str) -> Optional[int]:
        """Get rank of member in sorted set (descending order)."""
        return await self.redis.zrevrank(key, member)

    async def zrevrange(
        self,
        key: str,
        start: int,
        end: int,
        withscores: bool = False
    ) -> List[Any]:
        """Get range from sorted set in descending order."""
        return await self.redis.zrevrange(key, start, end, withscores=withscores)

    async def zcard(self, key: str) -> int:
        """Get number of members in sorted set."""
        return await self.redis.zcard(key)

    async def expire(self, key: str, seconds: int):
        """Set expiration on key."""
        await self.redis.expire(key, seconds)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.redis.exists(key) > 0

    async def hset(self, name: str, key: str, value: str):
        """Set hash field."""
        await self.redis.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field."""
        return await self.redis.hget(name, key)

    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields."""
        return await self.redis.hgetall(name)

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()
