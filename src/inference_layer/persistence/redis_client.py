"""
Redis client with connection pooling for persistence layer.

Uses redis-py with connection pooling for efficient resource usage.
Supports both sync and async operations.
"""

import logging
from typing import Optional

from redis import ConnectionPool, Redis
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.asyncio import Redis as AsyncRedis

from inference_layer.config import Settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client wrapper with connection pooling.
    
    Provides both sync and async Redis clients for different contexts:
    - Sync: For Celery tasks and blocking operations
    - Async: For FastAPI endpoints
    """
    
    _sync_pool: Optional[ConnectionPool] = None
    _async_pool: Optional[AsyncConnectionPool] = None
    
    @classmethod
    def get_sync_client(cls, settings: Settings) -> Redis:
        """
        Get synchronous Redis client with connection pooling.
        
        Args:
            settings: Application settings
        
        Returns:
            Redis client instance
        """
        if cls._sync_pool is None:
            cls._sync_pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,  # Auto-decode bytes to str
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            logger.info("Initialized Redis sync connection pool")
        
        return Redis(connection_pool=cls._sync_pool)
    
    @classmethod
    def get_async_client(cls, settings: Settings) -> AsyncRedis:
        """
        Get asynchronous Redis client with connection pooling.
        
        Args:
            settings: Application settings
        
        Returns:
            AsyncRedis client instance
        """
        if cls._async_pool is None:
            cls._async_pool = AsyncConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            logger.info("Initialized Redis async connection pool")
        
        return AsyncRedis(connection_pool=cls._async_pool)
    
    @classmethod
    async def close_async_pool(cls):
        """Close async connection pool (cleanup on shutdown)."""
        if cls._async_pool is not None:
            await cls._async_pool.disconnect()
            cls._async_pool = None
            logger.info("Closed Redis async connection pool")
    
    @classmethod
    def close_sync_pool(cls):
        """Close sync connection pool (cleanup on shutdown)."""
        if cls._sync_pool is not None:
            cls._sync_pool.disconnect()
            cls._sync_pool = None
            logger.info("Closed Redis sync connection pool")


def get_redis_client(settings: Settings) -> Redis:
    """
    Dependency injection helper for sync Redis client.
    
    Args:
        settings: Application settings
    
    Returns:
        Redis client instance
    """
    return RedisClient.get_sync_client(settings)


async def get_async_redis_client(settings: Settings) -> AsyncRedis:
    """
    Dependency injection helper for async Redis client.
    
    Args:
        settings: Application settings
    
    Returns:
        AsyncRedis client instance
    """
    return RedisClient.get_async_client(settings)
