import json
import logging
import anyio
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis-backed async cache with memory-fallback for resiliency."""
    def __init__(self):
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.redis: Optional[aioredis.Redis] = None
        self.memory_store = {}
        self.is_connected = False
        self._connect_in_progress = False
        self._connection_failed = False

    async def connect(self) -> None:
        """Initializes the Redis connection client pool."""
        if self.is_connected or self._connect_in_progress or self._connection_failed:
            return
            
        self._connect_in_progress = True
        try:
            url = f"redis://{self.host}:{self.port}/1"
            logger.info(f"Connecting to Redis cache at {url}")
            self.redis = aioredis.from_url(
                url, 
                encoding="utf-8", 
                decode_responses=True,
                socket_connect_timeout=0.5
            )
            # Ping to verify
            await self.redis.ping()
            self.is_connected = True
            logger.info("Successfully connected to Redis cache backend.")
        except Exception as e:
            self.is_connected = False
            self._connection_failed = True
            self.redis = None
            logger.warning(
                f"Redis cache connection failed: {str(e)}. "
                "Falling back to local in-memory storage for resiliency."
            )
        finally:
            self._connect_in_progress = False

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves a value from the cache."""
        if not self.is_connected:
            await self.connect()
            
        if self.is_connected and self.redis:
            try:
                val = await self.redis.get(key)
                if val is not None:
                    return json.loads(val)
            except Exception as e:
                logger.warning(f"Error fetching from Redis: {str(e)}. Falling back to in-memory.")
                
        # In-memory fallback
        mem_item = self.memory_store.get(key)
        if mem_item:
            val, expire_time = mem_item
            if expire_time is None or anyio.current_time() < expire_time:
                return json.loads(json.dumps(val))
            else:
                # Expired
                self.memory_store.pop(key, None)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Saves a value in the cache with a Time-to-Live (TTL) configuration."""
        if not self.is_connected:
            await self.connect()
            
        serialized = json.dumps(value)
        if self.is_connected and self.redis:
            try:
                await self.redis.set(key, serialized, ex=ttl)
                return True
            except Exception as e:
                logger.warning(f"Error saving to Redis: {str(e)}. Falling back to in-memory.")
                
        # In-memory fallback
        expire_time = anyio.current_time() + ttl if ttl else None
        self.memory_store[key] = (value, expire_time)
        return True

    async def invalidate(self, key: str) -> bool:
        """Explicitly deletes a key from cache."""
        if not self.is_connected:
            await self.connect()
            
        self.memory_store.pop(key, None)
        if self.is_connected and self.redis:
            try:
                await self.redis.delete(key)
                return True
            except Exception as e:
                logger.warning(f"Error deleting key from Redis: {str(e)}")
        return True

    async def invalidate_pattern(self, pattern: str) -> bool:
        """Deletes all cached keys matching a specific regex/wildcard pattern."""
        if not self.is_connected:
            await self.connect()
            
        # Invalidate in-memory matching keys
        matching_mem_keys = [k for k in self.memory_store.keys() if pattern.replace("*", "") in k]
        for k in matching_mem_keys:
            self.memory_store.pop(k, None)
            
        if self.is_connected and self.redis:
            try:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
                return True
            except Exception as e:
                logger.warning(f"Error deleting pattern from Redis: {str(e)}")
        return True

    async def clear(self) -> None:
        """Wipes the cache clean."""
        self.memory_store.clear()
        if self.is_connected and self.redis:
            try:
                await self.redis.flushdb()
            except Exception as e:
                logger.warning(f"Error clearing Redis: {str(e)}")

# Global Cache Instantiation
cache_client = RedisCache()

def run_async_as_sync(coro):
    """Utility to run an async coroutine inside a synchronous caller safely."""
    import asyncio
    import threading
    from concurrent.futures import Future

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

    if loop and loop.is_running():
        try:
            import nest_asyncio
            nest_asyncio.apply(loop)
            return loop.run_until_complete(coro)
        except Exception:
            pass

        future = Future()

        def start_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                res = new_loop.run_until_complete(coro)
                future.set_result(res)
            except Exception as e:
                future.set_exception(e)
            finally:
                new_loop.close()

        t = threading.Thread(target=start_loop, daemon=True)
        t.start()
        t.join()
        return future.result()
    else:
        if loop is None:
            return asyncio.run(coro)
        return loop.run_until_complete(coro)

