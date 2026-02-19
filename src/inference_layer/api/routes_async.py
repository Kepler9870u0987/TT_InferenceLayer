"""
Asynchronous API routes for batch triage processing.

These endpoints use Celery for task queue management and are suitable
for production batch workloads.
"""

import logging
from datetime import datetime
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status

from inference_layer.api.dependencies import get_async_repository, get_settings
from inference_layer.api.models import (
    BatchSubmitRequest,
    BatchSubmitResponse,
    TaskStatusResponse,
)
from inference_layer.config import Settings
from inference_layer.models.input_models import TriageRequest
from inference_layer.models.output_models import TriageResult
from inference_layer.persistence.repository import AsyncTriageRepository
from inference_layer.tasks.celery_app import celery_app
from inference_layer.tasks.triage_tasks import triage_email_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/batch",
    response_model=BatchSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit batch triage requests (asynchronous)",
    description="""
    Submit a batch of email triage requests for asynchronous processing.
    
    Returns task IDs that can be used to check status and retrieve results.
    Tasks are processed by Celery workers with retry and DLQ handling.
    
    Maximum batch size: 100 requests.
    """,
    responses={
        202: {"description": "Batch submitted successfully"},
        400: {"description": "Invalid request format or batch too large"},
    },
)
async def submit_batch(
    batch_request: BatchSubmitRequest,
    settings: Settings = Depends(get_settings),
) -> BatchSubmitResponse:
    """
    Submit batch of triage requests.
    
    Args:
        batch_request: Batch request with list of TriageRequest dicts
        settings: Application settings (injected)
    
    Returns:
        BatchSubmitResponse with task IDs for tracking
    """
    # Validate batch size
    if len(batch_request.requests) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size exceeds maximum (100 requests)",
        )
    
    logger.info(
        "Batch submission received",
        extra={"batch_size": len(batch_request.requests)},
    )
    
    # Validate each request and convert to dict
    validated_requests = []
    for i, req_dict in enumerate(batch_request.requests):
        try:
            # Parse and validate
            request = TriageRequest.model_validate(req_dict)
            validated_requests.append(request.model_dump(mode="json"))
        except Exception as exc:
            logger.error(
                "Invalid request in batch",
                extra={"index": i, "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid request at index {i}: {str(exc)}",
            )
    
    # Submit tasks
    task_ids = []
    for req_dict in validated_requests:
        result = triage_email_task.delay(req_dict)  # type: ignore[attr-defined]
        task_ids.append(result.id)
    
    # Generate batch ID
    batch_id = str(uuid4())
    
    logger.info(
        "Batch submitted",
        extra={
            "batch_id": batch_id,
            "task_count": len(task_ids),
        },
    )
    
    return BatchSubmitResponse(
        batch_id=batch_id,
        task_count=len(task_ids),
        task_ids=task_ids,
        submitted_at=datetime.utcnow(),
    )


@router.get(
    "/task/{task_id}",
    response_model=TaskStatusResponse,
    summary="Check task status",
    description="""
    Check the status of an async triage task.
    
    Possible states:
    - PENDING: Task is waiting in queue
    - STARTED: Task is being processed
    - SUCCESS: Task completed successfully (result available)
    - FAILURE: Task failed (error available)
    - RETRY: Task is being retried
    """,
    responses={
        200: {"description": "Task status retrieved"},
        404: {"description": "Task not found"},
    },
)
async def get_task_status(
    task_id: str,
    repository: AsyncTriageRepository = Depends(get_async_repository),
) -> TaskStatusResponse:
    """
    Get status of a task.
    
    Args:
        task_id: Celery task ID
    
    Returns:
        TaskStatusResponse with current status and result (if available)
    """
    # Get task result
    async_result = AsyncResult(task_id, app=celery_app)
    
    # Check if task exists
    if async_result.state == "PENDING" and not async_result.info:
        # Task might not exist (PENDING is default state for unknown tasks)
        logger.warning("Task not found", extra={"task_id": task_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    # Build response based on state
    if async_result.state == "SUCCESS":
        # Parse result from Celery
        result_dict = async_result.result
        result = TriageResult.model_validate(result_dict)
        
        logger.info(
            "Task status checked (SUCCESS)",
            extra={"task_id": task_id},
        )
        
        return TaskStatusResponse(
            task_id=task_id,
            status="SUCCESS",
            result=result,
        )
    
    # Check if result is in Redis (Celery result might be expired)
    if async_result.state == "PENDING" and async_result.info is None:
        # Result might be expired from Celery but still in Redis
        result = await repository.get_result_by_task_id(task_id)
        if result:
            logger.info(
                "Task status checked (SUCCESS from Redis fallback)",
                extra={"task_id": task_id},
            )
            return TaskStatusResponse(
                task_id=task_id,
                status="SUCCESS",
                result=result,
            )
        # Otherwise task truly not found - will fall through to general PENDING handler below
    
    elif async_result.state == "FAILURE":
        # Get error info
        error_info = str(async_result.info) if async_result.info else "Unknown error"
        traceback_info = async_result.traceback if hasattr(async_result, "traceback") else None
        
        logger.warning(
            "Task status checked (FAILURE)",
            extra={"task_id": task_id, "error": error_info},
        )
        
        return TaskStatusResponse(
            task_id=task_id,
            status="FAILURE",
            error=error_info,
            traceback=traceback_info,
        )
    
    elif async_result.state == "STARTED":
        logger.info(
            "Task status checked (STARTED)",
            extra={"task_id": task_id},
        )
        
        return TaskStatusResponse(
            task_id=task_id,
            status="STARTED",
        )
    
    elif async_result.state == "RETRY":
        logger.info(
            "Task status checked (RETRY)",
            extra={"task_id": task_id},
        )
        
        return TaskStatusResponse(
            task_id=task_id,
            status="RETRY",
        )
    
    else:  # PENDING or other states
        logger.info(
            "Task status checked (PENDING)",
            extra={"task_id": task_id},
        )
        
        return TaskStatusResponse(
            task_id=task_id,
            status="PENDING",
        )


@router.get(
    "/result/{task_id}",
    response_model=TriageResult,
    summary="Get task result (blocking)",
    description="""
    Get the result of a completed task.
    
    Returns 200 with result if task completed successfully.
    Returns 202 if task is still pending/processing.
    Returns 404 if task not found.
    Returns 500 if task failed.
    """,
    responses={
        200: {"description": "Task result retrieved"},
        202: {"description": "Task still processing"},
        404: {"description": "Task not found"},
        500: {"description": "Task failed"},
    },
)
async def get_task_result(
    task_id: str,
    repository: AsyncTriageRepository = Depends(get_async_repository),
) -> TriageResult:
    """
    Get result of a completed task.
    
    Args:
        task_id: Celery task ID
    
    Returns:
        TriageResult if task completed successfully
    """
    # Get task result
    async_result = AsyncResult(task_id, app=celery_app)
    
    # Check if task exists
    if async_result.state == "PENDING" and not async_result.info:
        # Check Redis fallback before declaring not found
        result = await repository.get_result_by_task_id(task_id)
        if result:
            logger.info(
                "Task result retrieved from Redis (Celery result expired)",
                extra={"task_id": task_id},
            )
            return result
        
        # Task not found
        logger.warning("Task not found", extra={"task_id": task_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    # Check state
    if async_result.state == "SUCCESS":
        # Parse and return result
        result_dict = async_result.result
        result = TriageResult.model_validate(result_dict)
        
        logger.info(
            "Task result retrieved",
            extra={"task_id": task_id},
        )
        
        return result
    
    elif async_result.state in ["PENDING", "STARTED", "RETRY"]:
        # Task still processing
        logger.info(
            "Task still processing",
            extra={"task_id": task_id, "state": async_result.state},
        )
        
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Task still processing (state: {async_result.state})",
        )
    
    else:  # FAILURE or other error states
        # Task failed
        error_info = str(async_result.info) if async_result.info else "Unknown error"
        
        logger.error(
            "Task failed",
            extra={"task_id": task_id, "error": error_info},
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task failed: {error_info}",
        )
