"""
Integration tests for LLM Inference Layer.

Test components together or against real external services:
- Ollama client (real calls, marked with @pytest.mark.integration)
- Full pipeline (email → prompt → mock LLM → validation → result)
- API endpoints (FastAPI TestClient, sync and async)
- Database operations (with test DB)
- Celery tasks (with test broker)
"""
