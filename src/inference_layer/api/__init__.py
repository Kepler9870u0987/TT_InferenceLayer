"""
FastAPI API routes and endpoints.

- routes_sync.py: Synchronous endpoints (POST /triage, GET /health, GET /schema)
- routes_async.py: Asynchronous endpoints (POST /triage/batch, GET /triage/task/{id})
- dependencies.py: Dependency injection for LLM client, validator, etc.
"""
