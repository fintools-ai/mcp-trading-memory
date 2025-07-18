"""Fixed Redis client wrapper for trading memory storage."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
    RedisError,
)

from src.config import settings


class FixedRedisClient:
    """Fixed async Redis client wrapper with proper event loop handling."""
    
    def __init__(self):
        """Initialize Redis client."""
        self.logger = logging.getLogger(__name__)
        self._client: Optional[redis.Redis] = None
        self._pool: Optional[ConnectionPool] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_healthy = False
        self._last_health_check = 0.0
        self._connection_lock = asyncio.Lock()
    
    async def _ensure_connection(self) -> None:
        """Ensure Redis connection is established and healthy."""
        async with self._connection_lock:
            if self._client is None or not self._is_healthy:
                await self._create_connection()
    
    async def _create_connection(self) -> None:
        """Create a fresh Redis connection."""
        try:
            # Clean up existing connection
            if self._client:
                try:
                    await self._client.aclose()
                except Exception:
                    pass
            
            if self._pool:
                try:
                    await self._pool.aclose()
                except Exception:
                    pass
            
            # Create new connection pool with proper settings
            self._pool = ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=settings.REDIS_DECODE_RESPONSES,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_CONNECTION_TIMEOUT,
                socket_keepalive=settings.REDIS_SOCKET_KEEPALIVE,
                socket_keepalive_options=settings.REDIS_SOCKET_KEEPALIVE_OPTIONS,
                retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
                # Important: Let Redis create connections within the current event loop
                connection_class=redis.Connection,
            )
            
            # Create Redis client with pool
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection immediately
            await self._client.ping()
            self._is_healthy = True
            self._last_health_check = time.time()
            
            self.logger.info(
                f"Redis connection established: {settings.REDIS_HOST}:{settings.REDIS_PORT} "
                f"(db={settings.REDIS_DB}, max_connections={settings.REDIS_MAX_CONNECTIONS})"
            )
            
        except Exception as e:
            self._is_healthy = False
            self.logger.error(
                f"Failed to create Redis connection: {e}",
                exc_info=True
            )
            raise
    
    async def initialize(self) -> None:
        """Initialize Redis connection with connection pooling."""
        await self._ensure_connection()
        
        # Start health check task if not already running
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def close(self) -> None:
        """Close Redis connection and cleanup resources."""
        await self._cleanup()
        self.logger.info("Redis connection closed")
    
    async def _cleanup(self) -> None:
        """Clean up Redis resources."""
        # Cancel health check task
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close client
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
        
        # Close pool
        if self._pool:
            try:
                await self._pool.aclose()
            except Exception:
                pass
            self._pool = None
        
        self._is_healthy = False
    
    async def _perform_health_check(self) -> bool:
        """Perform health check on Redis connection."""
        try:
            if not self._client:
                return False
            
            start_time = time.time()
            await self._client.ping()
            response_time = time.time() - start_time
            
            self._is_healthy = True
            self._last_health_check = time.time()
            
            self.logger.debug(f"Redis health check passed in {round(response_time * 1000, 2)}ms")
            return True
            
        except Exception as e:
            self._is_healthy = False
            self.logger.warning(f"Redis health check failed: {e}")
            return False
    
    async def _health_check_loop(self) -> None:
        """Background task for periodic health checks."""
        while True:
            try:
                await asyncio.sleep(settings.REDIS_HEALTH_CHECK_INTERVAL)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}", exc_info=True)
    
    async def _execute_with_retry(self, operation_func, *args, **kwargs) -> Any:
        """Execute Redis operation with retry and auto-reconnection."""
        last_exception = None
        
        for attempt in range(settings.REDIS_MAX_RETRIES + 1):
            try:
                # Ensure connection is healthy
                await self._ensure_connection()
                
                # Execute the operation
                return await operation_func(*args, **kwargs)
                
            except (RedisConnectionError, RedisTimeoutError, RuntimeError) as e:
                last_exception = e
                self._is_healthy = False
                
                # Don't retry on last attempt
                if attempt == settings.REDIS_MAX_RETRIES:
                    break
                
                # Calculate delay with exponential backoff
                delay = settings.REDIS_RETRY_DELAY * (
                    settings.REDIS_BACKOFF_FACTOR ** attempt
                )
                
                self.logger.warning(
                    f"Redis operation failed (attempt {attempt + 1}/{settings.REDIS_MAX_RETRIES + 1}), "
                    f"retrying in {delay}s: {e}"
                )
                
                await asyncio.sleep(delay)
            
            except Exception as e:
                # For other exceptions, don't retry
                last_exception = e
                break
        
        # If we get here, all retries failed
        self.logger.error(f"Redis operation failed after {settings.REDIS_MAX_RETRIES + 1} attempts: {last_exception}")
        raise last_exception
    
    @property
    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        return self._is_healthy
    
    @property
    def last_health_check(self) -> float:
        """Get timestamp of last health check."""
        return self._last_health_check
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON data from Redis."""
        async def _get_operation():
            await self._ensure_connection()
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        
        try:
            return await self._execute_with_retry(_get_operation)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON for key '{key}': {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get data from Redis for key '{key}': {e}")
            raise
    
    async def set_json(
        self,
        key: str,
        value: Dict[str, Any],
        ex: Optional[int] = None,
    ) -> bool:
        """Set JSON data in Redis."""
        async def _set_operation():
            await self._ensure_connection()
            data = json.dumps(value, default=str)  # Handle datetime serialization
            result = await self._client.set(key, data, ex=ex)
            return bool(result)
        
        try:
            return await self._execute_with_retry(_set_operation)
        except Exception as e:
            self.logger.error(f"Failed to set data in Redis for key '{key}': {e}")
            raise
    
    async def get_list(self, key: str, start: int = 0, end: int = -1) -> List[Dict[str, Any]]:
        """Get list data from Redis."""
        async def _get_list_operation():
            await self._ensure_connection()
            data = await self._client.lrange(key, start, end)
            return [json.loads(item) for item in data]
        
        try:
            return await self._execute_with_retry(_get_list_operation)
        except Exception as e:
            self.logger.error(f"Failed to get list from Redis for key '{key}': {e}")
            raise
    
    async def push_to_list(
        self,
        key: str,
        value: Dict[str, Any],
        max_length: Optional[int] = None,
    ) -> int:
        """Push data to Redis list."""
        async def _push_operation():
            await self._ensure_connection()
            data = json.dumps(value, default=str)
            pipe = self._client.pipeline()
            pipe.lpush(key, data)
            if max_length:
                pipe.ltrim(key, 0, max_length - 1)
            results = await pipe.execute()
            return results[0]
        
        try:
            return await self._execute_with_retry(_push_operation)
        except Exception as e:
            self.logger.error(f"Failed to push to list in Redis for key '{key}': {e}")
            raise
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        async def _exists_operation():
            await self._ensure_connection()
            return bool(await self._client.exists(key))
        
        try:
            return await self._execute_with_retry(_exists_operation)
        except Exception as e:
            self.logger.error(f"Failed to check key existence for '{key}': {e}")
            raise
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        async def _delete_operation():
            await self._ensure_connection()
            result = await self._client.delete(key)
            return bool(result)
        
        try:
            return await self._execute_with_retry(_delete_operation)
        except Exception as e:
            self.logger.error(f"Failed to delete key '{key}': {e}")
            raise
    
    async def set_expiry(self, key: str, seconds: int) -> bool:
        """Set expiry time for a key."""
        async def _expire_operation():
            await self._ensure_connection()
            return bool(await self._client.expire(key, seconds))
        
        try:
            return await self._execute_with_retry(_expire_operation)
        except Exception as e:
            self.logger.error(f"Failed to set expiry for key '{key}': {e}")
            raise
    
    async def get_multiple_keys(self, keys: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple JSON values from Redis efficiently."""
        async def _mget_operation():
            await self._ensure_connection()
            if not keys:
                return {}
            
            values = await self._client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to decode JSON for key '{key}'")
                        result[key] = None
                else:
                    result[key] = None
            
            return result
        
        try:
            return await self._execute_with_retry(_mget_operation)
        except Exception as e:
            self.logger.error(f"Failed to get multiple keys from Redis: {e}")
            raise
    
    async def atomic_transaction(self, operations: List[tuple]) -> List[Any]:
        """Execute multiple operations atomically using Redis transaction."""
        async def _transaction_operation():
            await self._ensure_connection()
            pipe = self._client.pipeline()
            
            # Queue all operations
            for op_name, args, kwargs in operations:
                if hasattr(pipe, op_name):
                    getattr(pipe, op_name)(*args, **kwargs)
                else:
                    raise ValueError(f"Unsupported operation: {op_name}")
            
            return await pipe.execute()
        
        try:
            return await self._execute_with_retry(_transaction_operation)
        except Exception as e:
            self.logger.error(f"Failed to execute atomic transaction: {e}")
            raise