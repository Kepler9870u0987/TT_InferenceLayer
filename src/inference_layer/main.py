"""
FastAPI application entry point for LLM Inference Layer.
"""

from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from inference_layer.api.error_handlers import EXCEPTION_HANDLERS
from inference_layer.api.middleware import RequestTracingMiddleware
from inference_layer.api.routes_async import router as async_router
from inference_layer.api.routes_sync import router as sync_router
from inference_layer.config import settings
from inference_layer.logging_config import configure_logging

# Configure structured logging before any other imports
configure_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)
logger = structlog.get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="LLM Inference Layer",
    description="Email triage and classification service with structured LLM outputs",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Request tracing middleware (must be first for request_id in all logs)
app.add_middleware(RequestTracingMiddleware)

# CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
for exc_class, handler in EXCEPTION_HANDLERS.items():
    app.add_exception_handler(exc_class, handler)

# Include routers
app.include_router(sync_router, tags=["sync"])
app.include_router(async_router, prefix="/triage", tags=["async"])


# Startup event
@app.on_event("startup")
async def startup():
    """Application startup - verify services and resources."""
    logger.info(
        "Application startup",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        ollama_base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
    )
    
    # Test Ollama connection
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                logger.info("Ollama connection successful")
            else:
                logger.warning("Ollama returned non-200 status", status_code=response.status_code)
    except Exception as e:
        logger.error("Ollama connection failed", exc_info=e)
    
    # Verify JSON Schema exists
    schema_path = Path(settings.JSON_SCHEMA_PATH)
    if schema_path.exists():
        logger.info("JSON Schema loaded", path=str(schema_path))
    else:
        logger.error("JSON Schema not found", path=str(schema_path))
    
    # Verify prompt templates exist
    templates_dir = Path(settings.PROMPT_TEMPLATES_DIR)
    if templates_dir.exists():
        logger.info("Prompt templates directory found", path=str(templates_dir))
    else:
        logger.error("Prompt templates directory not found", path=str(templates_dir))
    
    logger.info("Application startup complete")


# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    """Application shutdown - cleanup resources."""
    logger.info("Application shutdown")
    # Resources are managed by FastAPI dependency injection lifecycle
    # LLM client connections are automatically closed
    logger.info("Application shutdown complete")


# Prometheus metrics instrumentation
if settings.PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    """Root endpoint with API documentation links."""
    return {
        "service": "LLM Inference Layer",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "schema": "/schema",
        "metrics": "/metrics" if settings.PROMETHEUS_ENABLED else None,
    }


# Note: /health, /triage endpoints are in routes_sync.py
# Async endpoints (/triage/batch, /triage/task) are in routes_async.py


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "inference_layer.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Only for development
    )
