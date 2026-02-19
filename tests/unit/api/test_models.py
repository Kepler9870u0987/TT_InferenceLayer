"""
Unit tests for API response models.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from inference_layer.api.models import (
    BatchSubmitRequest,
    BatchSubmitResponse,
    ErrorResponse,
    HealthResponse,
    TaskStatusResponse,
    TriageResponse,
    VersionResponse,
)
from inference_layer.models.output_models import TriageResult


def test_triage_response_model():
    """Test TriageResponse model validation."""
    # Create a mock TriageResult (simplified for testing)
    result_dict = {
        "triage_response": {
            "dictionaryversion": 1,
            "sentiment": {"value": "neutral", "confidence": 0.8},
            "priority": {"value": "medium", "confidence": 0.7, "signals": []},
            "topics": [
                {
                    "labelid": "INFOCOMMERCIALI",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "hash_001", "lemma": "info", "count": 1}
                    ],
                    "evidence": [{"quote": "informazioni"}]
                }
            ]
        },
        "pipeline_version": {
            "parser_version": "1.0",
            "canonicalization_version": "1.0",
            "ner_model_version": "1.0",
            "pii_redaction_version": "1.0",
            "dictionary_version": "1",
            "schema_version": "2.0",
            "model_name": "qwen2.5:7b",
            "temperature": "0.1",
            "top_n_candidates": "100",
            "body_limit": "8000"
        },
        "request_uid": "test_uid",
        "validation_warnings": [],
        "retries_used": 0,
        "processing_duration_ms": 1500,
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = TriageResult.model_validate(result_dict)
    
    response = TriageResponse(
        status="success",
        result=result,
        warnings=["test warning"]
    )
    
    assert response.status == "success"
    assert isinstance(response.result, TriageResult)
    assert len(response.warnings) == 1


def test_batch_submit_request_validation():
    """Test BatchSubmitRequest validation."""
    # Valid request
    request = BatchSubmitRequest(requests=[{"email": {}, "candidate_keywords": [], "dictionary_version": 1}])
    assert len(request.requests) == 1
    
    # Empty list should fail
    with pytest.raises(ValidationError):
        BatchSubmitRequest(requests=[])
    
    # Too many requests should fail
    with pytest.raises(ValidationError):
        BatchSubmitRequest(requests=[{}] * 101)


def test_batch_submit_response():
    """Test BatchSubmitResponse model."""
    response = BatchSubmitResponse(
        batch_id="batch_123",
        task_count=5,
        task_ids=["task_1", "task_2", "task_3", "task_4", "task_5"]
    )
    
    assert response.batch_id == "batch_123"
    assert response.task_count == 5
    assert len(response.task_ids) == 5
    assert isinstance(response.submitted_at, datetime)


def test_task_status_response_success():
    """Test TaskStatusResponse for successful task."""
    result_dict = {
        "triage_response": {
            "dictionaryversion": 1,
            "sentiment": {"value": "neutral", "confidence": 0.8},
            "priority": {"value": "medium", "confidence": 0.7, "signals": []},
            "topics": [
                {
                    "labelid": "INFOCOMMERCIALI",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "hash_001", "lemma": "info", "count": 1}
                    ],
                    "evidence": [{"quote": "informazioni"}]
                }
            ]
        },
        "pipeline_version": {
            "parser_version": "1.0",
            "canonicalization_version": "1.0",
            "ner_model_version": "1.0",
            "pii_redaction_version": "1.0",
            "dictionary_version": "1",
            "schema_version": "2.0",
            "model_name": "qwen2.5:7b",
            "temperature": "0.1",
            "top_n_candidates": "100",
            "body_limit": "8000"
        },
        "request_uid": "test_uid",
        "validation_warnings": [],
        "retries_used": 0,
        "processing_duration_ms": 1500,
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = TriageResult.model_validate(result_dict)
    
    response = TaskStatusResponse(
        task_id="task_123",
        status="SUCCESS",
        result=result
    )
    
    assert response.task_id == "task_123"
    assert response.status == "SUCCESS"
    assert response.result is not None
    assert response.error is None


def test_task_status_response_failure():
    """Test TaskStatusResponse for failed task."""
    response = TaskStatusResponse(
        task_id="task_456",
        status="FAILURE",
        error="Validation failed"
    )
    
    assert response.task_id == "task_456"
    assert response.status == "FAILURE"
    assert response.result is None
    assert response.error == "Validation failed"


def test_health_response():
    """Test HealthResponse model."""
    response = HealthResponse(
        status="healthy",
        version="0.1.0",
        services={"ollama": "ok", "redis": "ok", "postgres": "not_configured"}
    )
    
    assert response.status == "healthy"
    assert response.version == "0.1.0"
    assert "ollama" in response.services
    assert isinstance(response.timestamp, datetime)


def test_version_response():
    """Test VersionResponse model."""
    response = VersionResponse(
        inference_layer_version="0.1.0",
        model_name="qwen2.5:7b",
        dictionary_version=1,
        schema_version="2.0",
        pipeline_config={
            "parser": "1.0",
            "temperature": "0.1"
        }
    )
    
    assert response.inference_layer_version == "0.1.0"
    assert response.model_name == "qwen2.5:7b"
    assert response.dictionary_version == 1
    assert "parser" in response.pipeline_config


def test_error_response():
    """Test ErrorResponse model."""
    response = ErrorResponse(
        error="validation_failed",
        message="Request validation failed",
        details={"field": "email", "error": "required"},
        request_uid="test_uid"
    )
    
    assert response.error == "validation_failed"
    assert response.message == "Request validation failed"
    assert response.details is not None
    assert response.request_uid == "test_uid"
    assert isinstance(response.timestamp, datetime)
