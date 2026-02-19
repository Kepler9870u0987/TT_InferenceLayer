"""
FastAPI exception handlers for structured error responses.

Maps domain exceptions to appropriate HTTP status codes and formats.
"""

import logging
from datetime import datetime

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from inference_layer.llm.exceptions import (
    LLMConnectionError,
    LLMError,
    LLMTimeoutError,
)
from inference_layer.retry.exceptions import RetryExhausted
from inference_layer.validation.exceptions import (
    BusinessRuleViolation,
    JSONParseError,
    SchemaValidationError,
    ValidationError,
)

logger = logging.getLogger(__name__)


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Handle validation errors (stages 1-3 failures).
    
    Maps to 422 Unprocessable Entity (invalid LLM response).
    
    Args:
        request: FastAPI request
        exc: ValidationError instance
    
    Returns:
        JSON error response
    """
    logger.warning(
        "Validation error",
        extra={
            "error_type": type(exc).__name__,
            "details": exc.details if hasattr(exc, "details") else {},
        },
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_failed",
            "message": str(exc),
            "details": exc.details if hasattr(exc, "details") else {},
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def retry_exhausted_handler(request: Request, exc: RetryExhausted) -> JSONResponse:
    """
    Handle retry exhausted errors (DLQ routing).
    
    Maps to 503 Service Unavailable (temporary failure).
    Logs complete metadata for DLQ processing.
    
    Args:
        request: FastAPI request
        exc: RetryExhausted instance
    
    Returns:
        JSON error response
    """
    # Log to DLQ with complete context
    logger.error(
        "DLQ: Retry exhausted - manual review required",
        extra={
            "request_uid": exc.request.email.uid,
            "total_attempts": exc.retry_metadata.total_attempts,
            "strategies_used": exc.retry_metadata.strategies_used,
            "total_latency_ms": exc.retry_metadata.total_latency_ms,
            "validation_failures": [
                {"attempt": i + 1, "stage": f["stage"], "error": f["error_type"]}
                for i, f in enumerate(exc.retry_metadata.validation_failures)
            ],
            "last_error": str(exc.last_error),
        },
    )
    
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "retry_exhausted",
            "message": "Unable to process request after multiple retry attempts",
            "request_uid": exc.request.email.uid,
            "attempts": exc.retry_metadata.total_attempts,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def llm_connection_error_handler(request: Request, exc: LLMConnectionError) -> JSONResponse:
    """
    Handle LLM connection errors.
    
    Maps to 502 Bad Gateway (upstream service unavailable).
    
    Args:
        request: FastAPI request
        exc: LLMConnectionError instance
    
    Returns:
        JSON error response
    """
    logger.error(
        "LLM connection error",
        extra={"error": str(exc)},
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": "llm_connection_failed",
            "message": "Unable to connect to LLM inference server",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def llm_timeout_error_handler(request: Request, exc: LLMTimeoutError) -> JSONResponse:
    """
    Handle LLM timeout errors.
    
    Maps to 504 Gateway Timeout (upstream service timeout).
    
    Args:
        request: FastAPI request
        exc: LLMTimeoutError instance
    
    Returns:
        JSON error response
    """
    logger.error(
        "LLM timeout error",
        extra={"error": str(exc)},
    )
    
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={
            "error": "llm_timeout",
            "message": "LLM inference server request timed out",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def pydantic_validation_error_handler(
    request: Request, exc: PydanticValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors (invalid request format).
    
    Maps to 400 Bad Request (client error).
    
    Args:
        request: FastAPI request
        exc: Pydantic ValidationError instance
    
    Returns:
        JSON error response
    """
    logger.warning(
        "Invalid request format",
        extra={"errors": exc.errors()},
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "invalid_request",
            "message": "Request validation failed",
            "details": exc.errors(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected errors.
    
    Maps to 500 Internal Server Error.
    
    Args:
        request: FastAPI request
        exc: Exception instance
    
    Returns:
        JSON error response
    """
    logger.exception(
        "Unexpected error",
        extra={"error_type": type(exc).__name__},
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Exception handler mapping for FastAPI app.add_exception_handler()
EXCEPTION_HANDLERS = {
    ValidationError: validation_error_handler,
    JSONParseError: validation_error_handler,
    SchemaValidationError: validation_error_handler,
    BusinessRuleViolation: validation_error_handler,
    RetryExhausted: retry_exhausted_handler,
    LLMConnectionError: llm_connection_error_handler,
    LLMTimeoutError: llm_timeout_error_handler,
    PydanticValidationError: pydantic_validation_error_handler,
    Exception: generic_error_handler,
}
