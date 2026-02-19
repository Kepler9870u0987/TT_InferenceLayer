"""Integration test fixtures (service checks and prerequisites).

Provides fixtures for checking if external services are available.
Integration tests are skipped if required services are not running.
"""

import pytest
import httpx
from redis import Redis
from redis.asyncio import Redis as AsyncRedis


@pytest.fixture(scope="session")
def check_ollama():
    """Check if Ollama is available at localhost:11434.
    
    Skips tests if Ollama is not reachable.
    """
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            pytest.skip("Ollama not available (non-200 status)")
    except Exception as e:
        pytest.skip(f"Ollama not available: {e}")


@pytest.fixture(scope="session")
def check_redis():
    """Check if Redis is available at localhost:6379.
    
    Skips tests if Redis is not reachable.
    """
    try:
        client = Redis.from_url("redis://localhost:6379/0")
        client.ping()
        client.close()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture(scope="session")
async def check_async_redis():
    """Check if Redis is available for async operations.
    
    Skips tests if Redis is not reachable.
    """
    try:
        client = AsyncRedis.from_url("redis://localhost:6379/0")
        await client.ping()
        await client.aclose()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
def real_ollama_client(check_ollama):
    """Real OllamaClient instance for integration tests.
    
    Requires Ollama to be running (checked by check_ollama fixture).
    """
    from inference_layer.llm.ollama_client import OllamaClient
    
    return OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        timeout=60,
        max_retries=2,
    )


@pytest.fixture
def real_redis_client(check_redis):
    """Real Redis client instance for integration tests (sync).
    
    Requires Redis to be running (checked by check_redis fixture).
    Uses database 15 (test database).
    """
    client = Redis.from_url("redis://localhost:6379/15")
    
    # Clear test database before test
    client.flushdb()
    
    yield client
    
    # Clear test database after test
    client.flushdb()
    client.close()


@pytest.fixture
async def real_async_redis_client(check_async_redis):
    """Real AsyncRedis client instance for integration tests (async).
    
    Requires Redis to be running (checked by check_async_redis fixture).
    Uses database 15 (test database).
    """
    client = AsyncRedis.from_url("redis://localhost:6379/15")
    
    # Clear test database before test
    await client.flushdb()
    
    yield client
    
    # Clear test database after test
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def integration_settings(test_settings):
    """Settings for integration tests with real services.
    
    Points to localhost services on standard ports.
    """
    test_settings.OLLAMA_BASE_URL = "http://localhost:11434"
    test_settings.OLLAMA_MODEL = "qwen2.5:7b"
    test_settings.REDIS_URL = "redis://localhost:6379/15"  # Test database
    test_settings.PROMETHEUS_ENABLED = False
    
    return test_settings
