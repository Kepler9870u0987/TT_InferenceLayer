# Contributing to LLM Inference Layer

Thank you for your interest in contributing! This document provides guidelines and instructions for developers.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Metrics & Monitoring](#metrics--monitoring)
- [Pull Request Process](#pull-request-process)

---

## Development Setup

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for Ollama, Redis, PostgreSQL)
- **Git**

### Local Installation

```bash
# Clone repository
git clone https://github.com/YOUR_ORG/TT_InferenceLayer.git
cd TT_InferenceLayer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package with development dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import inference_layer; print('✓ Installation successful')"
```

### Start Services

```bash
# Start all services (Ollama, Redis, PostgreSQL)
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings for development:

```env
# Application
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Redis (local)
REDIS_URL=redis://localhost:6379/0

# Disable Prometheus for development (optional)
PROMETHEUS_ENABLED=False
```

---

## Code Style

### Tools

We use automated formatters and linters:

- **Ruff** — Fast Python linter (replaces flake8, isort, etc.)
- **Black** — Opinionated code formatter
- **Mypy** — Static type checker

### Running Checks Locally

```bash
# Lint code
ruff check src tests

# Format code (in-place)
black src tests

# Type check
mypy src
```

### Configuration

- **Ruff**: [pyproject.toml](pyproject.toml) `[tool.ruff]`
- **Black**: [pyproject.toml](pyproject.toml) `[tool.black]`
- **Mypy**: [pyproject.toml](pyproject.toml) `[tool.mypy]`

### Code Style Guidelines

- **Docstrings**: Use Google-style docstrings for all public functions/classes
- **Type hints**: Required for function signatures
- **Logging**: Use `structlog.get_logger(__name__)` (never `logging.getLogger`)
- **Line length**: 88 characters (Black default)
- **Import order**: Automatic via Ruff

---

## Testing

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures (email, candidates, settings)
├── fixtures/                # JSON test   fixtures
├── unit/                    # Unit tests (no external services)
│   ├── conftest.py          # Unit test mocks
│   ├── api/
│   ├── llm/
│   ├── retry/
│   ├── validation/
│   └── ...
└── integration/             # Integration tests (require Ollama, Redis)
    ├── conftest.py          # Service health checks
    ├── api/
    ├── llm/
    └── ...
```

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests (fast, no services needed)
pytest tests/unit -v

# Run only integration tests (slow, requires Ollama + Redis)
pytest tests/integration -v -m integration

# Run with coverage
pytest --cov=inference_layer --cov-report=html

# Run specific test file
pytest tests/unit/validation/test_stage1_json_parse.py -v

# Run specific test function
pytest tests/unit/validation/test_stage1_json_parse.py::test_parse_valid_json -v
```

### Writing Tests

#### Unit Tests

Use mocks from `tests/unit/conftest.py`:

```python
def test_something(mock_ollama_client, mock_redis):
    """Test with mocked dependencies."""
    # Use mocks instead of real services
    result = my_function(mock_ollama_client, mock_redis)
    assert result == expected
```

#### Integration Tests

Use service check fixtures from `tests/integration/conftest.py`:

```python
@pytest.mark.integration
def test_integration(check_ollama, real_ollama_client):
    """Integration test with real Ollama."""
    # Requires Ollama running locally
    result = real_ollama_client.generate(request)
    assert result.content
```

#### Using Shared Fixtures

```python
def test_email_parsing(sample_triage_request):
    """Test using shared email fixture."""
    # sample_triage_request comes from tests/conftest.py
    assert sample_triage_request.email.uid
    assert len(sample_triage_request.candidate_keywords) > 0
```

### Test Markers

- `@pytest.mark.unit` — Unit test (default)
- `@pytest.mark.integration` — Integration test (requires services)
- `@pytest.mark.slow` — Slow test (> 5 seconds)

To run tests excluding slow/integration:

```bash
pytest -m "not slow and not integration"
```

---

## CI/CD Pipeline

### GitHub Actions Workflows

#### 1. **CI Pipeline** ([.github/workflows/ci.yml](.github/workflows/ci.yml))

Runs on every push and PR to `main`/`develop`:

**Jobs**:
1. **Lint & Type Check** — Ruff, Black, Mypy
2. **Unit Tests** — pytest with Redis service
3. **Integration Tests** — pytest with Ollama + Redis (PR/main only)
4. **Build Docker Images** — Validate Dockerfiles

**Status Badges**:
```markdown
[![CI](https://github.com/YOUR_ORG/TT_InferenceLayer/workflows/CI%20Pipeline/badge.svg)](https://github.com/YOUR_ORG/TT_InferenceLayer/actions)
```

#### 2. **Release Workflow** ([.github/workflows/release.yml](.github/workflows/release.yml))

Triggers on version tags (`v*.*.*`):

- Creates GitHub Release with auto-generated notes
- Optionally builds and pushes Docker images to registry

**Creating a Release**:

```bash
# Tag version
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# GitHub Actions will automatically create release
```

### Coverage Reports

- Coverage automatically uploaded to [Codecov](https://codecov.io)
- View reports at: `https://codecov.io/gh/YOUR_ORG/TT_InferenceLayer`
- Target coverage: **85%** (configured in [.codecov.yml](.codecov.yml))

---

## Metrics & Monitoring

### Prometheus Metrics

Custom metrics exposed at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `validation_failures_total` | Counter | Validation failures by stage/error type |
| `retries_total` | Counter | Retry attempts by strategy/success |
| `dlq_entries_total` | Counter | DLQ entries by reason |
| `topic_distribution_total` | Counter | Topic classifications by label |
| `unknown_topic_ratio` | Gauge | Ratio of UNKNOWNTOPIC to total topics |
| `llm_latency_seconds` | Histogram | LLM generation latency |
| `llm_tokens_total` | Counter | Token consumption by model/type |

See [src/inference_layer/monitoring/metrics.py](src/inference_layer/monitoring/metrics.py) for full documentation.

### Structured Logging

All modules use `structlog` for structured logging:

```python
import structlog

logger = structlog.get_logger(__name__)

# Log with structured context
logger.info(
    "Validation completed",
    request_uid=request.email.uid,
    warnings_count=len(warnings),
    duration_ms=duration_ms,
)
```

**Log Output** (development):
```
2026-02-19T10:30:45.123456 [info     ] Validation completed    request_uid=test_123 warnings_count=2 duration_ms=1234
```

**Log Output** (production, JSON):
```json
{"event": "Validation completed", "level": "info", "timestamp": "2026-02-19T10:30:45.123456", "request_uid": "test_123", "warnings_count": 2, "duration_ms": 1234}
```

### Request Tracing

Every request gets a unique `request_id` (UUID):

- Added via `RequestTracingMiddleware`
- Bound to structlog context (appears in all logs for that request)
- Returned in `X-Request-ID` response header

---

## Pull Request Process

### Before Submitting

1. **Branch from `develop`**:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Write tests** for new code (aim for >85% coverage)

3. **Run checks locally**:
   ```bash
   # Lint & format
   ruff check src tests
   black src tests
   
   # Type check
   mypy src
   
   # Tests
   pytest tests/unit -v
   ```

4. **Commit with descriptive messages**:
   ```bash
   git commit -m "feat: Add validation for XYZ"
   ```

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `test:` — Adding/updating tests
- `refactor:` — Code change (no feature/fix)
- `chore:` — Build/tooling changes

Examples:
```
feat: Add support for fallback LLM models
fix: Handle empty candidate list in prompt builder
docs: Update README with metrics documentation
test: Add integration tests for retry engine
```

### Pull Request Checklist

- [ ] Tests added/updated (unit + integration if applicable)
- [ ] All tests passing locally (`pytest`)
- [ ] Code formatted (`black`) and linted (`ruff`)
- [ ] Type hints added for new functions
- [ ] Docstrings added for public API
- [ ] Metrics added for new operations (if applicable)
- [ ] `IMPLEMENTATION_PROGRESS.md` updated (if completing a phase)
- [ ] PR description explains **what** and **why**

### Review Process

1. **CI must pass** (lint, tests, build)
2. **Code review** by at least one maintainer
3. **Coverage maintained** (no decrease >2%)
4. **Merge to `develop`** (squash merge preferred)

### Release to Production

1. **Merge `develop` → `main`** (after testing)
2. **Tag release**: `git tag -a v0.2.0 -m "Release v0.2.0"`
3. **Push tag**: `git push origin v0.2.0`
4. **GitHub Actions creates release** automatically

---

## Questions or Issues?

- **Bug reports**: Open a GitHub Issue
- **Feature requests**: Open a GitHub Discussion
- **Questions**: Ask in GitHub Discussions or Slack

Thank you for contributing! 🚀
