"""
FastAPI API routes and endpoints.

- routes_sync.py: Synchronous endpoints (POST /triage, GET /health, GET /schema)
- routes_async.py: Asynchronous endpoints (POST /triage/batch, GET /triage/task/{id})
- dependencies.py: Dependency injection for LLM client, validator, etc.
- models.py: API-specific request/response models
- error_handlers.py: Exception handlers for structured error responses
"""

from inference_layer.api import dependencies, error_handlers, models
from inference_layer.api.routes_async import router as async_router
from inference_layer.api.routes_sync import router as sync_router

__all__ = [
    "sync_router",
    "async_router",
    "dependencies",
    "error_handlers",
    "models",
]
