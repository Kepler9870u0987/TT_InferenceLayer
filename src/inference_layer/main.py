"""
FastAPI application entry point for LLM Inference Layer.
"""

import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from inference_layer.api.error_handlers import EXCEPTION_HANDLERS
from inference_layer.api.routes_async import router as async_router
from inference_layer.api.routes_sync import router as sync_router
from inference_layer.config import settings

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="LLM Inference Layer",
    description="Email triage and classification service with structured LLM outputs",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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

# Inlogger.info("Application startup")
    
    # Test Ollama connection
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                logger.info("✓ Ollama connection successful")
            else:
                logger.warning(f"⚠ Ollama returned status {response.status_code}")
    except Exception as e:
        logger.error(f"✗ Ollama connection failed: {e}")
    
    # Verify JSON Schema exists
    schema_path = Path(settings.JSON_SCHEMA_PATH)
    if schema_path.exists():
        logger.info(f"✓ JSON Schema loaded from {schema_path}")
    else:
        logger.error(f"✗ JSON Schema not found at {schema_path}")
    
    # Verify prompt templates exist
    logger.info("Application shutdown")
    # Resources are managed by FastAPI dependency injection lifecycle
    # LLM client connections are automatically closed
    logger.info("Application shutdown complete")logger.info(f"✓ Prompt templates directory found: {templates_dir}")
    else:
        logger.error(f"✗ Prompt templates directory not found: {templates_dir}")
    
    logger.info("Application startup complete")
# Prometheus metrics instrumentation
if settings.PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app)

    "docs": "/docs",
        "health": "/health",
        "schema": "/schema",
        "metrics": "/metrics" if settings.PROMETHEUS_ENABLED else None,
    }


# Note: /health endpoint is now in routes_sync.py with full service checks
        "service": "LLM Inference Layer",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # TODO: Check Ollama connection
    # TODO: Check Redis connection
    # TODO: Check DB connection
    return {
        "status": "healthy",
        "ollama": "unknown",
        "redis": "unknown",
        "database": "unknown",
    }


# Import and include routers (will be created in Phase 5)
# from inference_layer.api.routes_sync import router as sync_router
# from inference_layer.api.routes_async import router as async_router
# app.include_router(sync_router, tags=["sync"])
# app.include_router(async_router, tags=["async"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "inference_layer.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Only for development
    )
