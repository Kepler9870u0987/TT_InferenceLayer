"""Unit test fixtures (mocks and stubs).

Provides mock objects for testing without external dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from inference_layer.models.llm_models import LLMGenerationResponse, LLMMetadata


@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests (sync)."""
    mock = Mock()
    mock.set = Mock(return_value=True)
    mock.get = Mock(return_value=None)
    mock.lpush = Mock(return_value=1)
    mock.lrange = Mock(return_value=[])
    mock.llen = Mock(return_value=0)
    mock.delete = Mock(return_value=1)
    mock.exists = Mock(return_value=False)
    mock.ttl = Mock(return_value=-1)
    mock.zadd = Mock(return_value=1)
    mock.zrange = Mock(return_value=[])
    return mock


@pytest.fixture
def mock_async_redis():
    """Mock AsyncRedis client for unit tests (async)."""
    mock = AsyncMock()
    mock.set = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.lpush = AsyncMock(return_value=1)
    mock.lrange = AsyncMock(return_value=[])
    mock.llen = AsyncMock(return_value=0)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=False)
    mock.ttl = AsyncMock(return_value=-1)
    mock.zadd = AsyncMock(return_value=1)
    mock.zrange = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_llm_response():
    """Mock LLMGenerationResponse for validation tests."""
    return LLMGenerationResponse(
        content='{"dictionaryversion": 1, "topics": [], "sentiment": {"value": "neutral", "confidence": 0.8}, "priority": {"value": "medium", "confidence": 0.7, "signals": []}}',
        model_version="qwen2.5:7b",
        finish_reason="stop",
        usage_tokens=750,
        prompt_tokens=500,
        completion_tokens=250,
        latency_ms=1500,
        created_at=datetime.now().isoformat(),
        raw_metadata={},
    )


@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient for unit tests."""
    mock = AsyncMock()
    
    # Mock generate method
    mock.generate = AsyncMock(return_value=LLMGenerationResponse(
        content='{"dictionaryversion": 1, "topics": [{"labelid": "FATTURAZIONE", "confidence": 0.9, "keywordsintext": [{"candidateid": "hash_001", "lemma": "fattura", "count": 1}], "evidence": [{"quote": "test quote"}]}], "sentiment": {"value": "neutral", "confidence": 0.8}, "priority": {"value": "medium", "confidence": 0.7, "signals": []}}',
        model_version="qwen2.5:7b",
        finish_reason="stop",
        usage_tokens=750,
        prompt_tokens=500,
        completion_tokens=250,
        latency_ms=1500,
        created_at=datetime.now().isoformat(),
        raw_metadata={},
    ))
    
    # Mock health_check method
    mock.health_check = AsyncMock(return_value=True)
    
    # Mock list_models method
    mock.list_models = AsyncMock(return_value=["qwen2.5:7b", "llama3.1:8b"])
    
    return mock


@pytest.fixture
def mock_validation_pipeline():
    """Mock ValidationPipeline for unit tests."""
    mock = AsyncMock()
    
    # Mock validate method returns (response, warnings)
    from inference_layer.models.output_models import EmailTriageResponse
    
    async def mock_validate(llm_response, request):
        # Return a minimal valid response with no warnings
        import json
        content = json.loads(llm_response.content)
        response = EmailTriageResponse(**content)
        return response, []
    
    mock.validate = AsyncMock(side_effect=mock_validate)
    
    return mock


@pytest.fixture
def mock_prompt_builder():
    """Mock PromptBuilder for unit tests."""
    mock = Mock()
    
    mock.build_system_prompt = Mock(return_value="System prompt")
    mock.build_user_prompt = Mock(return_value=("User prompt", {"candidates_count": 10}))
    mock.default_model = "qwen2.5:7b"
    mock.default_temperature = 0.1
    mock.default_max_tokens = 2048
    mock.json_schema = {"type": "object"}
    
    return mock


@pytest.fixture
def mock_retry_engine():
    """Mock RetryEngine for unit tests."""
    mock = AsyncMock()
    
    from inference_layer.models.output_models import EmailTriageResponse
    from inference_layer.retry.metadata import RetryMetadata
    from inference_layer.models.llm_models import LLMMetadata
    
    async def mock_execute(request):
        # Return minimal valid response, metadata, warnings
        response = EmailTriageResponse(
            dictionaryversion=1,
            topics=[],
            sentiment={"value": "neutral", "confidence": 0.8},
            priority={"value": "medium", "confidence": 0.7, "signals": []},
        )
        metadata = RetryMetadata(
            total_attempts=1,
            strategies_used=["standard"],
            final_strategy="standard",
            total_latency_ms=1500,
            llm_metadata=LLMMetadata(
                model="qwen2.5:7b",
                prompt_token_count=500,
                completion_token_count=250,
                generation_latency_ms=1500,
            ),
            validation_failures=[],
        )
        warnings = []
        return response, metadata, warnings
    
    mock.execute_with_retry = AsyncMock(side_effect=mock_execute)
    
    return mock
