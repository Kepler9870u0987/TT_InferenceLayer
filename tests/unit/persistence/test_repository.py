"""
Unit tests for TriageRepository.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from inference_layer.config import Settings
from inference_layer.models.output_models import (
    TriageResult,
    EmailTriageResponse,
    SentimentResult,
    PriorityResult,
)
from inference_layer.models.enums import SentimentEnum, PriorityEnum
from inference_layer.models.pipeline_version import PipelineVersion
from inference_layer.persistence.repository import TriageRepository
from inference_layer.retry.exceptions import RetryExhausted
from inference_layer.retry.metadata import RetryMetadata
from inference_layer.models.input_models import TriageRequest
from inference_layer.validation.exceptions import ValidationError


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


@pytest.fixture
def mock_settings():
    """Mock settings."""
    settings = MagicMock(spec=Settings)
    settings.RESULT_TTL_SECONDS = 86400
    return settings


@pytest.fixture
def repository(mock_redis, mock_settings):
    """Create repository with mocked Redis."""
    return TriageRepository(mock_redis, mock_settings)


@pytest.fixture
def sample_result():
    """Sample TriageResult for testing."""
    return TriageResult(
        triage_response=EmailTriageResponse(
            dictionaryversion=1,
            topics=[],
            sentiment=SentimentResult(value=SentimentEnum.NEUTRAL, confidence=0.8),
            priority=PriorityResult(
                value=PriorityEnum.P3,
                confidence=0.7,
                signals=["routine inquiry"]
            ),
        ),
        pipeline_version=PipelineVersion(
            dictionary_version=1,
            model_version="qwen2.5:7b",
            schema_version="email_triage_v2",
            inference_layer_version="0.1.0",
            parser_version="1.0.0",
            canonicalization_version="1.0.0",
            ner_model_version="1.0.0",
            pii_redaction_version="1.0.0",
        ),
        request_uid="test-uid-123",
        validation_warnings=[],
        retries_used=0,
        processing_duration_ms=100,
        created_at="2024-01-01T12:00:00",
    )


def test_save_result_success(repository, mock_redis, sample_result):
    """Test saving result to Redis."""
    result = repository.save_result(sample_result, task_id="task-123")
    
    assert result is True
    
    # Should call setex for result
    mock_redis.setex.assert_any_call(
        name="triage:result:test-uid-123",
        time=86400,
        value=sample_result.model_dump_json()
    )
    
    # Should call zadd for index
    mock_redis.zadd.assert_called_once()
    
    # Should call setex for task mapping
    assert mock_redis.setex.call_count == 2


def test_save_result_no_task_id(repository, mock_redis, sample_result):
    """Test saving result without task_id."""
    result = repository.save_result(sample_result)
    
    assert result is True
    
    # Should call setex only once (for result, not for task mapping)
    mock_redis.setex.assert_called_once()


def test_save_result_redis_error(repository, mock_redis, sample_result):
    """Test error handling when Redis fails."""
    mock_redis.setex.side_effect = Exception("Redis error")
    
    result = repository.save_result(sample_result)
    
    assert result is False


def test_get_result_success(repository, mock_redis, sample_result):
    """Test retrieving result from Redis."""
    mock_redis.get.return_value = sample_result.model_dump_json()
    
    result = repository.get_result("test-uid-123")
    
    assert result is not None
    assert result.request_uid == "test-uid-123"
    mock_redis.get.assert_called_once_with("triage:result:test-uid-123")


def test_get_result_not_found(repository, mock_redis):
    """Test retrieving non-existent result."""
    mock_redis.get.return_value = None
    
    result = repository.get_result("nonexistent-uid")
    
    assert result is None


def test_get_result_by_task_id_success(repository, mock_redis, sample_result):
    """Test retrieving result by task ID."""
    mock_redis.get.side_effect = [
        "test-uid-123",  # First call returns request_uid
        sample_result.model_dump_json(),  # Second call returns result
    ]
    
    result = repository.get_result_by_task_id("task-123")
    
    assert result is not None
    assert result.request_uid == "test-uid-123"
    assert mock_redis.get.call_count == 2


def test_delete_result_success(repository, mock_redis):
    """Test deleting result."""
    mock_redis.delete.return_value = 1  # 1 key deleted
    
    result = repository.delete_result("test-uid-123")
    
    assert result is True
    mock_redis.delete.assert_called_once_with("triage:result:test-uid-123")
    mock_redis.zrem.assert_called_once_with("triage:results:index", "test-uid-123")


def test_delete_result_not_found(repository, mock_redis):
    """Test deleting non-existent result."""
    mock_redis.delete.return_value = 0  # 0 keys deleted
    
    result = repository.delete_result("nonexistent-uid")
    
    assert result is False


def test_save_to_dlq_success(repository, mock_redis):
    """Test saving failed request to DLQ."""
    # Create mock RetryExhausted exception
    mock_request = MagicMock(spec=TriageRequest)
    mock_request.email.uid = "failed-uid-123"
    mock_request.model_dump.return_value = {"email": {"uid": "failed-uid-123"}}
    
    mock_metadata = MagicMock(spec=RetryMetadata)
    mock_metadata.total_attempts = 4
    mock_metadata.strategies_used = ["base", "shrink", "fallback"]
    mock_metadata.total_latency_ms = 5000
    mock_metadata.validation_failures = []
    
    exc = RetryExhausted(
        request=mock_request,
        retry_metadata=mock_metadata,
        last_error=ValidationError("Test error"),
    )
    
    result = repository.save_to_dlq(exc)
    
    assert result is True
    mock_redis.lpush.assert_called_once()
    mock_redis.ltrim.assert_called_once_with("triage:dlq", 0, 9999)
    
    # Check DLQ entry structure
    dlq_json = mock_redis.lpush.call_args[0][1]
    dlq_entry = json.loads(dlq_json)
    assert dlq_entry["request_uid"] == "failed-uid-123"
    assert dlq_entry["total_attempts"] == 4
    assert dlq_entry["last_error_type"] == "ValueError"


def test_get_dlq_entries(repository, mock_redis):
    """Test retrieving DLQ entries."""
    dlq_entry = {
        "request_uid": "failed-123",
        "timestamp": "2024-01-01T12:00:00",
        "total_attempts": 4,
    }
    mock_redis.lrange.return_value = [json.dumps(dlq_entry)]
    
    entries = repository.get_dlq_entries(limit=100)
    
    assert len(entries) == 1
    assert entries[0]["request_uid"] == "failed-123"
    mock_redis.lrange.assert_called_once_with("triage:dlq", 0, 99)


def test_get_recent_results(repository, mock_redis, sample_result):
    """Test retrieving recent results."""
    mock_redis.zrevrange.return_value = ["test-uid-123", "test-uid-456"]
    mock_redis.get.side_effect = [
        sample_result.model_dump_json(),
        sample_result.model_dump_json(),
    ]
    
    results = repository.get_recent_results(limit=10)
    
    assert len(results) == 2
    mock_redis.zrevrange.assert_called_once_with("triage:results:index", 0, 9)


def test_get_stats(repository, mock_redis):
    """Test getting repository statistics."""
    mock_redis.zcard.return_value = 100
    mock_redis.llen.return_value = 5
    
    stats = repository.get_stats()
    
    assert stats["total_results"] == 100
    assert stats["dlq_size"] == 5
    assert stats["result_ttl_seconds"] == 86400
