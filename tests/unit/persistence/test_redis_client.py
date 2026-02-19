"""
Unit tests for Redis client and connection pooling.
"""

import pytest
from unittest.mock import MagicMock, patch

from inference_layer.config import Settings
from inference_layer.persistence.redis_client import RedisClient


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.REDIS_MAX_CONNECTIONS = 50
    return settings


@pytest.fixture(autouse=True)
def reset_pools():
    """Reset connection pools before each test."""
    RedisClient._sync_pool = None
    RedisClient._async_pool = None
    yield
    RedisClient._sync_pool = None
    RedisClient._async_pool = None


def test_get_sync_client_creates_pool(mock_settings):
    """Test that sync client creates connection pool on first call."""
    with patch("inference_layer.persistence.redis_client.ConnectionPool") as mock_pool:
        mock_pool.from_url.return_value = MagicMock()
        
        client1 = RedisClient.get_sync_client(mock_settings)
        client2 = RedisClient.get_sync_client(mock_settings)
        
        # Pool should be created only once
        mock_pool.from_url.assert_called_once_with(
            mock_settings.REDIS_URL,
            max_connections=mock_settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )


def test_get_async_client_creates_pool(mock_settings):
    """Test that async client creates connection pool on first call."""
    with patch("inference_layer.persistence.redis_client.AsyncConnectionPool") as mock_pool:
        mock_pool.from_url.return_value = MagicMock()
        
        client1 = RedisClient.get_async_client(mock_settings)
        client2 = RedisClient.get_async_client(mock_settings)
        
        # Pool should be created only once
        mock_pool.from_url.assert_called_once_with(
            mock_settings.REDIS_URL,
            max_connections=mock_settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )


def test_close_sync_pool():
    """Test closing sync connection pool."""
    mock_pool = MagicMock()
    RedisClient._sync_pool = mock_pool
    
    RedisClient.close_sync_pool()
    
    mock_pool.disconnect.assert_called_once()
    assert RedisClient._sync_pool is None


@pytest.mark.asyncio
async def test_close_async_pool():
    """Test closing async connection pool."""
    mock_pool = MagicMock()
    mock_pool.disconnect = MagicMock(return_value=None)
    RedisClient._async_pool = mock_pool
    
    await RedisClient.close_async_pool()
    
    mock_pool.disconnect.assert_called_once()
    assert RedisClient._async_pool is None
