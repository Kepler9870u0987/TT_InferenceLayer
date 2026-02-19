"""
Integration tests for FastAPI application.

These tests use TestClient to test the full API without requiring
running services (mocked dependencies).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from inference_layer.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns service info."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "LLM Inference Layer"
    assert data["version"] == "0.1.0"
    assert data["status"] == "running"
    assert "docs" in data
    assert "health" in data


def test_schema_endpoint():
    """Test schema endpoint returns JSON Schema."""
    response = client.get("/schema")
    
    assert response.status_code == 200
    schema = response.json()
    
    # Verify it's the email triage schema
    assert "name" in schema
    assert schema["name"] == "emailtriagev2"
    assert "schema" in schema
    assert "properties" in schema["schema"]


def test_version_endpoint():
    """Test version endpoint returns pipeline info."""
    response = client.get("/version")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "inference_layer_version" in data
    assert "model_name" in data
    assert "dictionary_version" in data
    assert "schema_version" in data
    assert "pipeline_config" in data


def test_health_endpoint():
    """Test health check endpoint."""
    # Note: This will check real services if they're running
    response = client.get("/health")
    
    # Accept both 200 (healthy) and 503 (unhealthy) as valid responses
    assert response.status_code in [200, 503]
    data = response.json()
    
    assert "status" in data
    assert "version" in data
    assert "services" in data
    assert "timestamp" in data
    
    # Services should be checked
    assert "ollama" in data["services"]
    assert "redis" in data["services"]


def test_triage_endpoint_invalid_request():
    """Test triage endpoint with invalid request."""
    # Send invalid request (missing required fields)
    response = client.post(
        "/triage",
        json={"invalid": "request"}
    )
    
    # Should return 400 (bad request) or 422 (validation error)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data


def test_batch_endpoint_invalid_request():
    """Test batch endpoint with invalid request."""
    # Send invalid request (missing requests field)
    response = client.post(
        "/triage/batch",
        json={"invalid": "request"}
    )
    
    # Should return 400 or 422
    assert response.status_code in [400, 422]


def test_batch_endpoint_empty_list():
    """Test batch endpoint with empty request list."""
    response = client.post(
        "/triage/batch",
        json={"requests": []}
    )
    
    # Should return 400 or 422 (empty list not allowed)
    assert response.status_code in [400, 422]


def test_batch_endpoint_too_many_requests():
    """Test batch endpoint with too many requests."""
    # Create 101 dummy requests (exceeds limit of 100)
    requests = [{"dummy": "request"}] * 101
    
    response = client.post(
        "/triage/batch",
        json={"requests": requests}
    )
    
    # Should return 400 (batch too large)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "exceeds maximum" in data["detail"].lower()


def test_task_status_nonexistent_task():
    """Test task status endpoint with non-existent task ID."""
    response = client.get("/triage/task/nonexistent_task_id")
    
    # Should return 404 (task not found)
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_task_result_nonexistent_task():
    """Test task result endpoint with non-existent task ID."""
    response = client.get("/triage/result/nonexistent_task_id")
    
    # Should return 404 (task not found)
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_api_documentation():
    """Test that OpenAPI documentation is accessible."""
    # Test Swagger UI
    response = client.get("/docs")
    assert response.status_code == 200
    
    # Test ReDoc
    response = client.get("/redoc")
    assert response.status_code == 200
    
    # Test OpenAPI JSON
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi_spec = response.json()
    assert "openapi" in openapi_spec
    assert "info" in openapi_spec
    assert "paths" in openapi_spec


def test_prometheus_metrics():
    """Test that Prometheus metrics are exposed."""
    response = client.get("/metrics")
    
    # Metrics should be accessible
    assert response.status_code == 200
    
    # Should return Prometheus text format
    assert response.headers["content-type"].startswith("text/plain")
    
    # Should contain some metrics
    metrics_text = response.text
    assert len(metrics_text) > 0


@pytest.mark.skipif(
    True,  # Skip by default (requires running Ollama + Redis)
    reason="Requires running Ollama and Redis services"
)
def test_triage_endpoint_full_integration():
    """
    Full integration test for triage endpoint.
    
    This test requires:
    - Ollama running with a model loaded
    - Redis running
    - Valid test email data
    
    Run separately with: pytest -k test_triage_endpoint_full_integration --no-skip
    """
    # Create a minimal valid request
    request_data = {
        "email": {
            "uid": "test_integration",
            "mailbox": "INBOX",
            "message_id": "<test@example.com>",
            "fetched_at": datetime.utcnow().isoformat(),
            "size": 1000,
            "from_addr_redacted": "test@example.com",
            "to_addrs_redacted": ["support@example.com"],
            "subject_canonical": "Test Subject",
            "date_parsed": "Thu, 1 Jan 2026 12:00:00 +0000",
            "headers_canonical": {},
            "body_text_canonical": "Vorrei informazioni sul contratto.",
            "body_original_hash": "test_hash",
            "pii_entities": [],
            "removed_sections": [],
            "pipeline_version": {
                "parser_version": "1.0",
                "canonicalization_version": "1.0",
                "ner_model_version": "1.0",
                "pii_redaction_version": "1.0"
            },
            "processing_timestamp": datetime.utcnow().isoformat(),
            "processing_duration_ms": 100
        },
        "candidate_keywords": [
            {
                "candidate_id": "hash_contratto",
                "term": "contratto",
                "lemma": "contratto",
                "count": 1,
                "source": "body",
                "score": 0.9
            }
        ],
        "dictionary_version": 1
    }
    
    response = client.post("/triage", json=request_data)
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert data["status"] == "success"
    assert "result" in data
    assert "warnings" in data
    
    result = data["result"]
    assert "triage_response" in result
    assert "pipeline_version" in result
    assert "request_uid" in result
