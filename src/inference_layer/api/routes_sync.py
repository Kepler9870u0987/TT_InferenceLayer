"""
Synchronous API routes for immediate triage processing.

These endpoints are suitable for demo, testing, and low-latency single-email triage.
For batch processing, use async routes instead.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, status
from prometheus_client import Counter, Histogram
from redis import Redis

from inference_layer.api.dependencies import (
    get_retry_engine,
    get_settings,
)
from inference_layer.api.models import (
    HealthResponse,
    TriageResponse,
    VersionResponse,
)
from inference_layer.config import Settings
from inference_layer.models.input_models import TriageRequest
from inference_layer.models.output_models import TriageResult
from inference_layer.models.pipeline_version import PipelineVersion
from inference_layer.retry.engine import RetryEngine

logger = logging.getLogger(__name__)

# Prometheus metrics
triage_requests_total = Counter(
    "triage_requests_total",
    "Total triage requests",
    ["endpoint", "status"]
)

triage_duration_seconds = Histogram(
    "triage_duration_seconds",
    "Triage request duration in seconds",
    ["endpoint"]
)

router = APIRouter()


@router.post(
    "/triage",
    response_model=TriageResponse,
    status_code=status.HTTP_200_OK,
    summary="Triage single email (synchronous)",
    description="""
    Process a single email triage request synchronously.
    
    Returns the complete triage result including topics, sentiment, priority,
    and validation warnings. Suitable for demo and testing.
    
    For batch processing or production workloads, use POST /triage/batch instead.
    """,
    responses={
        200: {"description": "Triage completed successfully"},
        400: {"description": "Invalid request format"},
        422: {"description": "Validation failed (invalid LLM response)"},
        503: {"description": "Retry exhausted (all strategies failed)"},
    },
)
async def triage_email(
    request: TriageRequest,
    retry_engine: RetryEngine = Depends(get_retry_engine),
    settings: Settings = Depends(get_settings),
) -> TriageResponse:
    """
    Triage a single email synchronously.
    
    Args:
        request: TriageRequest with email and candidate keywords
        retry_engine: Retry engine instance (injected)
        settings: Application settings (injected)
    
    Returns:
        TriageResponse with validated result and warnings
    """
    start_time = time.time()
    
    try:
        logger.info(
            "Triage request received",
            extra={
                "request_uid": request.email.uid,
                "dictionary_version": request.dictionary_version,
                "candidate_count": len(request.candidate_keywords),
            },
        )
        
        # Execute with retry
        validated_response, retry_metadata, warnings = await retry_engine.execute_with_retry(request)
        
        # Build pipeline version for audit trail
        pipeline_version = PipelineVersion(
            parser_version=request.email.pipeline_version.parser_version,
            canonicalization_version=request.email.pipeline_version.canonicalization_version,
            ner_model_version=request.email.pipeline_version.ner_model_version,
            pii_redaction_version=request.email.pipeline_version.pii_redaction_version,
            dictionary_version=str(request.dictionary_version),
            schema_version=settings.SCHEMA_VERSION,
            model_name=settings.MODEL_NAME,
            temperature=settings.TEMPERATURE,
            top_n_candidates=settings.TOP_N_CANDIDATES,
            body_limit=settings.BODY_LIMIT,
        )
        
        # Build result
        duration_ms = int((time.time() - start_time) * 1000)
        result = TriageResult(
            triage_response=validated_response,
            pipeline_version=pipeline_version,
            request_uid=request.email.uid,
            validation_warnings=warnings,
            retries_used=retry_metadata.total_attempts - 1,  # First attempt is not a retry
            processing_duration_ms=duration_ms,
            created_at=datetime.utcnow(),
        )
        
        logger.info(
            "Triage completed",
            extra={
                "request_uid": request.email.uid,
                "duration_ms": duration_ms,
                "retries": retry_metadata.total_attempts - 1,
                "warnings_count": len(warnings),
                "topics_count": len(validated_response.topics),
            },
        )
        
        # Update metrics
        triage_requests_total.labels(endpoint="triage", status="success").inc()
        triage_duration_seconds.labels(endpoint="triage").observe(time.time() - start_time)
        
        return TriageResponse(
            status="success",
            result=result,
            warnings=warnings,
        )
    
    except Exception as exc:
        # Update metrics
        triage_requests_total.labels(endpoint="triage", status="error").inc()
        
        logger.error(
            "Triage failed",
            extra={
                "request_uid": request.email.uid,
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        
        # Re-raise for exception handlers
        raise


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="""
    Check the health of the inference layer and its dependencies.
    
    Returns status of:
    - Ollama LLM server
    - Redis (for Celery task queue)
    - PostgreSQL (Phase 7 - not yet implemented)
    """,
    responses={
        200: {"description": "All services healthy"},
        503: {"description": "One or more services unhealthy"},
    },
)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """
    Check health of all services.
    
    Args:
        settings: Application settings (injected)
    
    Returns:
        HealthResponse with service statuses
    """
    services = {}
    overall_healthy = True
    
    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                services["ollama"] = "ok"
            else:
                services["ollama"] = f"error (status {response.status_code})"
                overall_healthy = False
    except Exception as e:
        services["ollama"] = f"unreachable ({type(e).__name__})"
        overall_healthy = False
    
    # Check Redis
    try:
        redis_client = Redis.from_url(settings.REDIS_URL, socket_timeout=5)
        redis_client.ping()
        services["redis"] = "ok"
        redis_client.close()
    except Exception as e:
        services["redis"] = f"unreachable ({type(e).__name__})"
        overall_healthy = False
    
    # PostgreSQL check (Phase 7)
    services["postgres"] = "not_configured"
    
    # Determine overall status
    if overall_healthy:
        health_status = "healthy"
        status_code = status.HTTP_200_OK
    elif services["ollama"] == "ok":  # Ollama is critical
        health_status = "degraded"
        status_code = status.HTTP_200_OK
    else:
        health_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    logger.info(
        "Health check",
        extra={"status": health_status, "services": services},
    )
    
    response = HealthResponse(
        status=health_status,
        version="0.1.0",
        services=services,
        timestamp=datetime.utcnow(),
    )
    
    # Return with appropriate status code
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
    )


@router.get(
    "/schema",
    summary="Get JSON Schema for LLM structured output",
    description="""
    Returns the JSON Schema used for LLM structured output validation.
    
    This is the schema defined in `config/schema/email_triage_v2.json`.
    Clients can use this to understand the expected output format.
    """,
    responses={
        200: {
            "description": "JSON Schema",
            "content": {"application/json": {}},
        },
    },
)
async def get_schema(
    settings: Settings = Depends(get_settings),
):
    """
    Return the JSON Schema for triage output.
    
    Args:
        settings: Application settings (injected)
    
    Returns:
        JSON Schema dictionary
    """
    schema_path = Path(settings.JSON_SCHEMA_PATH)
    
    if not schema_path.exists():
        logger.error("JSON Schema file not found", extra={"path": str(schema_path)})
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JSON Schema file not found",
        )
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    
    return schema


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Get pipeline version information",
    description="""
    Returns version information for the inference layer pipeline.
    
    Includes:
    - Application version
    - LLM model name and configuration
    - Dictionary version
    - JSON Schema version
    - Pipeline component versions
    """,
)
async def get_version(
    settings: Settings = Depends(get_settings),
) -> VersionResponse:
    """
    Return pipeline version information.
    
    Args:
        settings: Application settings (injected)
    
    Returns:
        VersionResponse with pipeline configuration
    """
    return VersionResponse(
        inference_layer_version="0.1.0",
        model_name=settings.MODEL_NAME,
        dictionary_version=1,  # TODO: Make configurable
        schema_version=settings.SCHEMA_VERSION,
        pipeline_config={
            "parser": "1.0",
            "canonicalization": "1.0",
            "ner_model": "1.0",
            "pii_redaction": "1.0",
            "temperature": str(settings.TEMPERATURE),
            "top_n_candidates": str(settings.TOP_N_CANDIDATES),
            "body_limit": str(settings.BODY_LIMIT),
        },
    )
