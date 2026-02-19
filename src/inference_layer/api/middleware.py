"""FastAPI middleware for request tracing and logging."""

import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID tracing to all requests.
    
    Features:
    - Generates unique request_id (UUID4) for each request
    - Binds request_id to structlog context (appears in all logs)
    - Adds X-Request-ID response header for client correlation
    - Logs request start/end with duration
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with tracing context."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Bind to structlog context (will appear in all subsequent logs)
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )
        
        # Log request start
        logger.info(
            "Request started",
            query_params=dict(request.query_params) if request.query_params else None,
        )
        
        # Process request
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request completion
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request error
            logger.error(
                "Request failed",
                exc_info=exc,
                duration_ms=round(duration_ms, 2),
            )
            
            # Clear context before re-raising
            structlog.contextvars.clear_contextvars()
            raise
        
        finally:
            # Clear context after request (prevent leakage to other requests)
            structlog.contextvars.clear_contextvars()
