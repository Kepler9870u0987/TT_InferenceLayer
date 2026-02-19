"""
Celery tasks for asynchronous email triage processing.

Tasks accept JSON-serializable dicts and return dicts for compatibility
with Celery's JSON serialization.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

from celery import Task

from inference_layer.config import settings
from inference_layer.llm.ollama_client import OllamaClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.models.input_models import TriageRequest
from inference_layer.models.output_models import TriageResult
from inference_layer.models.pipeline_version import PipelineVersion
from inference_layer.retry.engine import RetryEngine
from inference_layer.retry.exceptions import RetryExhausted
from inference_layer.tasks.celery_app import celery_app
from inference_layer.validation.pipeline import ValidationPipeline

logger = logging.getLogger(__name__)


class TriageTask(Task):
    """
    Base task class with resource initialization.
    
    Initializes heavy resources once per worker process and reuses them
    across task invocations (similar to dependency injection in FastAPI).
    """
    
    _llm_client = None
    _prompt_builder = None
    _validation_pipeline = None
    _retry_engine = None
    
    @property
    def llm_client(self):
        """Get or initialize LLM client (singleton per worker)."""
        if self._llm_client is None:
            self._llm_client = OllamaClient(
                base_url=settings.OLLAMA_BASE_URL,
                timeout=settings.OLLAMA_TIMEOUT,
                max_retries=2,
            )
        return self._llm_client
    
    @property
    def prompt_builder(self):
        """Get or initialize prompt builder (singleton per worker)."""
        if self._prompt_builder is None:
            self._prompt_builder = PromptBuilder(
                templates_dir=Path(settings.PROMPT_TEMPLATES_DIR),
                schema_path=Path(settings.JSON_SCHEMA_PATH),
                top_n_candidates=settings.TOP_N_CANDIDATES,
                body_limit=settings.BODY_LIMIT,
                shrink_top_n=settings.SHRINK_TOP_N,
                shrink_body_limit=settings.SHRINK_BODY_LIMIT,
                enable_pii_redaction=settings.ENABLE_PII_REDACTION,
            )
        return self._prompt_builder
    
    @property
    def validation_pipeline(self):
        """Get or initialize validation pipeline (singleton per worker)."""
        if self._validation_pipeline is None:
            self._validation_pipeline = ValidationPipeline(settings)
        return self._validation_pipeline
    
    @property
    def retry_engine(self):
        """Get or initialize retry engine (singleton per worker)."""
        if self._retry_engine is None:
            self._retry_engine = RetryEngine(
                llm_client=self.llm_client,
                prompt_builder=self.prompt_builder,
                validation_pipeline=self.validation_pipeline,
                settings=settings,
            )
        return self._retry_engine


@celery_app.task(
    bind=True,
    base=TriageTask,
    name="triage_email",
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 min backoff
    max_retries=3,
)
def triage_email_task(self: TriageTask, request_dict: dict) -> dict:
    """
    Async task for single email triage.
    
    Args:
        request_dict: TriageRequest as dict (JSON-serializable)
    
    Returns:
        TriageResult as dict
    
    Raises:
        Exception: Task-level failures (network errors, etc.)
        RetryExhausted: All retry strategies failed (logged to DLQ)
    """
    start_time = time.time()
    
    try:
        # Parse request from dict
        request = TriageRequest.model_validate(request_dict)
        
        logger.info(
            "Celery task started",
            extra={
                "task_id": self.request.id,
                "request_uid": request.email.uid,
                "dictionary_version": request.dictionary_version,
            },
        )
        
        # Execute with retry (async operations require asyncio.run in Celery)
        validated_response, retry_metadata, warnings = asyncio.run(
            self.retry_engine.execute_with_retry(request)
        )
        
        # Build pipeline version
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
            retries_used=retry_metadata.total_attempts - 1,
            processing_duration_ms=duration_ms,
            created_at=datetime.utcnow(),
        )
        
        logger.info(
            "Celery task completed",
            extra={
                "task_id": self.request.id,
                "request_uid": request.email.uid,
                "duration_ms": duration_ms,
                "retries": retry_metadata.total_attempts - 1,
            },
        )
        
        # Return as dict (JSON-serializable)
        return result.model_dump(mode="json")
    
    except RetryExhausted as exc:
        # Log to DLQ (no DB persistence in Phase 5)
        logger.error(
            "DLQ: Retry exhausted in Celery task",
            extra={
                "task_id": self.request.id,
                "request_uid": exc.request.email.uid,
                "total_attempts": exc.retry_metadata.total_attempts,
                "strategies_used": exc.retry_metadata.strategies_used,
                "last_error": str(exc.last_error),
            },
        )
        
        # Don't retry at Celery level (retry engine already exhausted strategies)
        raise
    
    except Exception as exc:
        logger.error(
            "Celery task failed",
            extra={
                "task_id": self.request.id,
                "error_type": type(exc).__name__,
                "retries": self.request.retries,
            },
            exc_info=True,
        )
        
        # Retry at Celery level (transient failures like network issues)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="triage_batch")
def triage_batch_task(requests_dicts: list[dict]) -> dict:
    """
    Submit batch of triage requests as individual tasks.
    
    This is a coordinator task that submits individual triage tasks
    and returns their task IDs for tracking.
    
    Args:
        requests_dicts: List of TriageRequest dicts
    
    Returns:
        Dict with task_ids and count
    """
    logger.info(
        "Batch task started",
        extra={"batch_size": len(requests_dicts)},
    )
    
    # Submit individual tasks
    task_ids = []
    for req_dict in requests_dicts:
        result = triage_email_task.delay(req_dict)
        task_ids.append(result.id)
    
    logger.info(
        "Batch tasks submitted",
        extra={"task_count": len(task_ids)},
    )
    
    return {
        "task_ids": task_ids,
        "count": len(task_ids),
    }
