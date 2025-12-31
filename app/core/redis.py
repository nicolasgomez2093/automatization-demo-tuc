import redis.asyncio as redis
from typing import Optional
import json
from app.core.config import settings

# Redis client instance
redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client instance."""
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()


class RedisCache:
    """Redis cache helper with common operations."""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def _get_client(self):
        if not self.client:
            self.client = await get_redis()
        return self.client
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        client = await self._get_client()
        return await client.get(key)
    
    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(self, key: str, value: str, expire: int = 3600):
        """Set value in cache with expiration (default 1 hour)."""
        client = await self._get_client()
        await client.set(key, value, ex=expire)
    
    async def set_json(self, key: str, value: dict, expire: int = 3600):
        """Set JSON value in cache."""
        await self.set(key, json.dumps(value), expire)
    
    async def delete(self, key: str):
        """Delete key from cache."""
        client = await self._get_client()
        await client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = await self._get_client()
        return await client.exists(key) > 0
    
    async def expire(self, key: str, seconds: int):
        """Set expiration on key."""
        client = await self._get_client()
        await client.expire(key, seconds)
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment value."""
        client = await self._get_client()
        return await client.incrby(key, amount)
    
    async def get_pattern(self, pattern: str) -> list:
        """Get all keys matching pattern."""
        client = await self._get_client()
        return await client.keys(pattern)
    
    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        client = await self._get_client()
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)


# Session management
class SessionManager:
    """Manage user sessions in Redis."""
    
    def __init__(self):
        self.cache = RedisCache()
        self.prefix = "session:"
        self.default_expire = 86400  # 24 hours
    
    def _get_key(self, token: str) -> str:
        return f"{self.prefix}{token}"
    
    async def create_session(self, token: str, user_data: dict, expire: int = None):
        """Create a new session."""
        expire = expire or self.default_expire
        await self.cache.set_json(self._get_key(token), user_data, expire)
    
    async def get_session(self, token: str) -> Optional[dict]:
        """Get session data."""
        return await self.cache.get_json(self._get_key(token))
    
    async def delete_session(self, token: str):
        """Delete session."""
        await self.cache.delete(self._get_key(token))
    
    async def refresh_session(self, token: str, expire: int = None):
        """Refresh session expiration."""
        expire = expire or self.default_expire
        await self.cache.expire(self._get_key(token), expire)
    
    async def get_user_sessions(self, user_id: int) -> list:
        """Get all sessions for a user."""
        pattern = f"{self.prefix}*"
        keys = await self.cache.get_pattern(pattern)
        sessions = []
        for key in keys:
            session = await self.cache.get_json(key)
            if session and session.get("user_id") == user_id:
                sessions.append(session)
        return sessions
    
    async def delete_user_sessions(self, user_id: int):
        """Delete all sessions for a user."""
        pattern = f"{self.prefix}*"
        keys = await self.cache.get_pattern(pattern)
        for key in keys:
            session = await self.cache.get_json(key)
            if session and session.get("user_id") == user_id:
                await self.cache.delete(key)


# Cache decorators
def cache_result(key_prefix: str, expire: int = 3600):
    """Decorator to cache function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache = RedisCache()
            # Generate cache key from function args
            cache_key = f"{key_prefix}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached = await cache.get_json(cache_key)
            if cached is not None:
                return cached
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set_json(cache_key, result, expire)
            return result
        return wrapper
    return decorator


# Global instances
cache = RedisCache()
session_manager = SessionManager()
