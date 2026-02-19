# Development Guide

This guide helps you get started with developing the LLM Inference Layer.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd TT_InferenceLayer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
pip install -r requirements-dev.txt
```

### 2. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# For local development, set:
# OLLAMA_BASE_URL=http://localhost:11434
# DATABASE_URL=postgresql+asyncpg://llm_user:llm_pass@localhost:5432/llm_inference
# REDIS_URL=redis://localhost:6379/0
```

### 3. Start Services with Docker Compose

```bash
# Start all services (PostgreSQL, Redis, Ollama)
docker-compose up -d postgres redis ollama

# Wait for Ollama to be ready, then pull a model
docker exec -it llm_ollama ollama pull qwen2.5:7b

# Verify services are running
docker-compose ps
```

### 4. Run the Application

#### Development Mode (Hot Reload)

```bash
# Run FastAPI with auto-reload
uvicorn inference_layer.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, run Celery worker
celery -A inference_layer.tasks.celery_app worker --loglevel=info
```

#### Docker Mode (Full Stack)

```bash
# Start all services including API and worker
docker-compose up -d

# View logs
docker-compose logs -f api worker

# Access API at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Running Tests

### Unit Tests

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run specific test module
python -m pytest tests/unit/validation/ -v

# Run with coverage
python -m pytest tests/unit/ --cov=src/inference_layer --cov-report=html
```

### Integration Tests

```bash
# Requires running Ollama instance
# Start Ollama:
docker-compose up -d ollama

# Pull test model
docker exec -it llm_ollama ollama pull qwen2.5:7b

# Run integration tests
python -m pytest tests/integration/ -v

# Skip integration tests (if services not available)
python -m pytest tests/ -m "not integration"
```

### All Tests

```bash
# Run entire test suite
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=src/inference_layer --cov-report=html --cov-report=term
```

## Project Structure

```
TT_InferenceLayer/
├── src/inference_layer/       # Main application code
│   ├── api/                   # FastAPI routes and dependencies
│   ├── llm/                   # LLM client abstraction
│   ├── models/                # Pydantic data models
│   ├── validation/            # Multi-stage validation pipeline
│   ├── retry/                 # Retry strategies (standard, shrink, fallback)
│   ├── pii/                   # PII redaction utilities
│   ├── persistence/           # Redis storage (results, DLQ)
│   ├── tasks/                 # Celery tasks
│   ├── monitoring/            # Prometheus metrics
│   └── main.py                # FastAPI application entry point
├── tests/                     # Test suite
│   ├── unit/                  # Unit tests (no external dependencies)
│   ├── integration/           # Integration tests (require services)
│   └── fixtures/              # Test fixtures and sample data
├── config/                    # Configuration files
│   ├── prompts/               # Jinja2 prompt templates
│   └── schema/                # JSON Schema for LLM output
├── docker/                    # Docker configurations
│   ├── Dockerfile             # API container
│   └── Dockerfile.worker      # Celery worker container
├── docker-compose.yml         # Multi-service orchestration
├── pyproject.toml             # Python dependencies and metadata
├── .env.example               # Example environment variables
└── README.md                  # User-facing documentation
```

## Development Workflow

### 1. Code Style and Linting

```bash
# Format code with black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Type checking with mypy
mypy src/

# Linting with flake8
flake8 src/ tests/
```

### 2. Making Changes

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and add tests
3. Run tests: `python -m pytest tests/`
4. Run linters and formatters
5. Commit changes: `git commit -m "feat: your feature description"`
6. Push and create pull request

### 3. Testing Your Changes

#### Test Single Email Triage

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_email.json
```

#### Test Batch Processing

```bash
curl -X POST http://localhost:8000/triage/batch \
  -H "Content-Type: application/json" \
  -d '{"requests": [...]}'
```

#### Check Task Status

```bash
curl http://localhost:8000/triage/task/{task_id}
```

## Debugging

### Enable Debug Logging

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Access Logs

```bash
# API logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f worker

# Ollama logs
docker-compose logs -f ollama
```

### Common Issues

#### 1. Ollama Connection Error

**Symptom**: `ConnectionError: Failed to connect to Ollama`

**Solution**:
```bash
# Check if Ollama is running
docker-compose ps ollama

# Check Ollama health
curl http://localhost:11434/api/tags

# Pull model if missing
docker exec -it llm_ollama ollama pull qwen2.5:7b
```

#### 2. Redis Connection Error

**Symptom**: `redis.exceptions.ConnectionError`

**Solution**:
```bash
# Check if Redis is running
docker-compose ps redis

# Test connection
redis-cli -h localhost ping
```

#### 3. Test Failures

**Symptom**: Tests fail with "Settings unhashable"

**Solution**: This was fixed in the recent update. Make sure you have the latest code where dependency injection functions don't use `Depends(get_settings)` in `@lru_cache()` decorated functions.

## Adding New Features

### 1. Add New Validation Stage

1. Create file: `src/inference_layer/validation/stage5_yourcheck.py`
2. Implement stage class with `async def validate()` method
3. Add to pipeline in `validation/pipeline.py`
4. Add tests in `tests/unit/validation/test_stage5_yourcheck.py`

### 2. Add New Retry Strategy

1. Create strategy in `src/inference_layer/retry/strategies.py`
2. Implement `RetryStrategy` protocol
3. Add to `RetryEngine` escalation chain in `retry/engine.py`
4. Add tests in `tests/unit/retry/test_strategies.py`

### 3. Add New API Endpoint

1. Add route in `src/inference_layer/api/routes_sync.py` or `routes_async.py`
2. Add request/response models in `api/models.py`
3. Add dependency injection if needed in `api/dependencies.py`
4. Add tests in `tests/integration/api/test_api_integration.py`

## Performance Optimization

### 1. LLM Optimization

- Use smaller models for faster inference (e.g., `mistral:7b` instead of `llama3.1:70b`)
- Reduce `BODY_TRUNCATION_LIMIT` if emails are too long
- Reduce `CANDIDATE_TOP_N` to send fewer keywords to LLM

### 2. Scaling

```yaml
# In docker-compose.yml, increase worker replicas
worker:
  deploy:
    replicas: 4  # Run 4 worker instances
```

### 3. Caching

- Singleton pattern used for expensive resources (LLM client, prompt builder)
- JSON Schema loaded once and cached
- Connection pooling for Redis and HTTP clients

## Monitoring

### Prometheus Metrics

Access metrics at: `http://localhost:8000/metrics`

Key metrics:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `validation_failures_total` - Validation stage failures
- `retry_attempts_total` - Retry strategy usage

### Health Checks

```bash
# Overall health
curl http://localhost:8000/health

# Ollama health
curl http://localhost:11434/api/tags

# Redis health
redis-cli ping
```

## Contributing

1. Follow the existing code style (Black, isort, type hints)
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass: `pytest tests/`
5. Create meaningful commit messages (Conventional Commits style)

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ollama Documentation](https://ollama.ai/docs)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Celery Documentation](https://docs.celeryproject.org/)

## Support

For issues and questions:
- Check [IMPLEMENTATION_PROGRESS.md](./IMPLEMENTATION_PROGRESS.md) for current status
- Review [doc/LLM_Layer_Consolidato_v2v3_chat_SUPER_DETAILED.md](./doc/LLM_Layer_Consolidato_v2v3_chat_SUPER_DETAILED.md) for architecture details
- Create an issue in the repository
