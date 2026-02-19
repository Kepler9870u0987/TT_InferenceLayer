"""
API-specific request and response models for FastAPI endpoints.

These models wrap the core domain models (TriageRequest, TriageResult)
with API-specific metadata and status information.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from inference_layer.models.output_models import TriageResult


class TriageResponse(BaseModel):
    """Response for synchronous triage endpoint."""
    
    status: str = Field(
        description="Request status",
        examples=["success", "failed"]
    )
    result: TriageResult = Field(
        description="Triage result with validated LLM response"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Validation warnings (non-critical issues)"
    )


class BatchSubmitRequest(BaseModel):
    """Request for batch triage submission."""
    
    requests: list[dict] = Field(
        description="List of TriageRequest objects as dicts",
        min_length=1,
        max_length=100  # Soft limit to prevent worker overload
    )


class BatchSubmitResponse(BaseModel):
    """Response for batch submission endpoint."""
    
    batch_id: str = Field(
        description="Unique batch identifier (UUID)"
    )
    task_count: int = Field(
        description="Number of tasks submitted",
        ge=0
    )
    task_ids: list[str] = Field(
        description="List of Celery task IDs for tracking"
    )
    submitted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Batch submission timestamp (UTC)"
    )


class TaskStatusResponse(BaseModel):
    """Response for task status check endpoint."""
    
    task_id: str = Field(
        description="Celery task ID"
    )
    status: str = Field(
        description="Task state: PENDING, STARTED, SUCCESS, FAILURE, RETRY",
        examples=["PENDING", "STARTED", "SUCCESS", "FAILURE", "RETRY"]
    )
    result: Optional[TriageResult] = Field(
        default=None,
        description="Triage result (present only if status=SUCCESS)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message (present only if status=FAILURE)"
    )
    traceback: Optional[str] = Field(
        default=None,
        description="Full traceback (present only if status=FAILURE and debug enabled)"
    )


class HealthResponse(BaseModel):
    """Response for health check endpoint."""
    
    status: str = Field(
        description="Overall health status",
        examples=["healthy", "degraded", "unhealthy"]
    )
    version: str = Field(
        description="Inference layer version",
        examples=["0.1.0"]
    )
    services: dict[str, str] = Field(
        description="Service-specific health status",
        examples=[{"ollama": "ok", "redis": "ok", "postgres": "not_configured"}]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp (UTC)"
    )


class VersionResponse(BaseModel):
    """Response for version info endpoint."""
    
    inference_layer_version: str = Field(
        description="Application version"
    )
    model_name: str = Field(
        description="LLM model name (e.g., 'qwen2.5:7b')"
    )
    dictionary_version: int = Field(
        description="Current dictionary version"
    )
    schema_version: str = Field(
        description="JSON Schema version"
    )
    pipeline_config: dict[str, str] = Field(
        description="Pipeline component versions",
        examples=[{
            "parser": "1.0",
            "canonicalization": "1.0",
            "ner_model": "1.0",
            "pii_redaction": "1.0"
        }]
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""
    
    error: str = Field(
        description="Error code or type",
        examples=["validation_failed", "retry_exhausted", "internal_error"]
    )
    message: str = Field(
        description="Human-readable error message"
    )
    details: Optional[dict] = Field(
        default=None,
        description="Additional error details (e.g., validation failures)"
    )
    request_uid: Optional[str] = Field(
        default=None,
        description="Request UID for tracing (if available)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp (UTC)"
    )
