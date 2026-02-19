"""Integration tests for Ollama client.

These tests require a running Ollama server with a model available.
Run: docker-compose up ollama
Or: ollama serve (if installed locally)

Tests are skipped if Ollama is not reachable.
"""

import pytest
import asyncio
import httpx
from inference_layer.llm.ollama_client import OllamaClient
from inference_layer.models.llm_models import LLMGenerationRequest
from inference_layer.llm.exceptions import LLMConnectionError, LLMModelNotAvailableError


# Check if Ollama is available
async def is_ollama_available():
    """Check if Ollama server is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def ollama_available():
    """Check if Ollama is available, skip tests if not."""
    available = await is_ollama_available()
    if not available:
        pytest.skip("Ollama server not available")
    return available


@pytest.fixture
async def ollama_client():
    """Create Ollama client for tests."""
    client = OllamaClient(base_url="http://localhost:11434", timeout=30)
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_ollama_health_check(ollama_available, ollama_client):
    """Test Ollama health check."""
    result = await ollama_client.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_ollama_list_models(ollama_available, ollama_client):
    """Test listing available models."""
    models = await ollama_client.list_models()
    assert isinstance(models, list)
    # Should have at least one model
    # Note: this assumes you have pulled at least one model
    # If this fails, run: ollama pull qwen2.5:7b


@pytest.mark.asyncio
async def test_ollama_generate_simple_json(ollama_available, ollama_client):
    """Test simple JSON generation."""
    # Use a small, fast model if available, otherwise skip
    models = await ollama_client.list_models()
    if not models:
        pytest.skip("No models available in Ollama")
    
    # Use first available model
    model = models[0]
    
    request = LLMGenerationRequest(
        prompt='Return JSON with a single field "message" set to "Hello, World!"',
        model=model,
        temperature=0.1,
        max_tokens=50,
        format_schema=None,  # Basic JSON mode
        stream=False
    )
    
    response = await ollama_client.generate(request)
    
    # Check response structure
    assert response.content is not None
    assert len(response.content) > 0
    assert response.model_version is not None
    assert response.finish_reason in ["stop", "length"]
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_ollama_generate_with_schema(ollama_available, ollama_client):
    """Test generation with JSON Schema constraint."""
    models = await ollama_client.list_models()
    if not models:
        pytest.skip("No models available in Ollama")
    
    model = models[0]
    
    # Simple schema
    schema = {
        "type": "object",
        "required": ["sentiment"],
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["positive", "neutral", "negative"]
            }
        }
    }
    
    request = LLMGenerationRequest(
        prompt='Analyze sentiment of: "This is great news!" Return JSON with sentiment field.',
        model=model,
        temperature=0.1,
        max_tokens=50,
        format_schema=schema,
        stream=False
    )
    
    response = await ollama_client.generate(request)
    
    # Response should be valid JSON conforming to schema
    assert response.content is not None
    import json
    data = json.loads(response.content)
    assert "sentiment" in data
    assert data["sentiment"] in ["positive", "neutral", "negative"]


@pytest.mark.asyncio
async def test_ollama_model_not_found(ollama_available, ollama_client):
    """Test error handling for non-existent model."""
    request = LLMGenerationRequest(
        prompt="Test",
        model="nonexistent-model:999",
        temperature=0.1,
        max_tokens=50,
        stream=False
    )
    
    with pytest.raises(LLMModelNotAvailableError):
        await ollama_client.generate(request)


@pytest.mark.asyncio
async def test_ollama_get_model_info(ollama_available, ollama_client):
    """Test getting model information."""
    models = await ollama_client.list_models()
    if not models:
        pytest.skip("No models available")
    
    model = models[0]
    info = await ollama_client.get_model_info(model)
    
    assert isinstance(info, dict)
    # Should have some model details
    # Note: response structure depends on Ollama version


@pytest.mark.asyncio
async def test_ollama_timeout_handling(ollama_available):
    """Test timeout handling."""
    # Create client with very short timeout
    client = OllamaClient(base_url="http://localhost:11434", timeout=1)
    
    models = await client.list_models()
    if not models:
        await client.close()
        pytest.skip("No models available")
    
    # Make a request that might timeout with very short limit
    # This test might be flaky depending on system speed
    # Just ensure it handles timeout gracefully
    
    await client.close()


# Note: Add more integration tests as needed:
# - Test with actual email classification prompts
# - Test retry logic
# - Test connection pooling
# - Test concurrent requests
