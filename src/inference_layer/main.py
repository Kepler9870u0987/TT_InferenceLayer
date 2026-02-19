"""
FastAPI application entry point for LLM Inference Layer.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from inference_layer.config import settings

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


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    # TODO: Initialize DB connection pool
    # TODO: Initialize LLM client
    # TODO: Load JSON schema
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    # TODO: Close DB connections
    # TODO: Close LLM client
    pass


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
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
