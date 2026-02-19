# LLM Inference Layer

> **Email triage and classification service with structured LLM outputs**

Transforms canonicalized emails into structured, auditable output containing topics (multi-label), sentiment, priority, and anchored keywords with evidence. Part of the *Thread Classificator Mail* pipeline.

---

## 🎯 Features

- **Structured Output**: JSON Schema strict validation with `additionalProperties: false`
- **Multi-Label Classification**: 1–5 topics from closed taxonomy
- **Sentiment & Priority**: With confidence scores and audit signals
- **Anchored Keywords**: Only from provided candidates (no invention)
- **Multi-Stage Validation**: 4-level pipeline (parse → schema → business rules → quality)
- **Retry & Fallback**: Exponential backoff, request shrinking, model fallback, DLQ
- **PII Handling**: Annotated in input, redacted on-the-fly only when needed
- **Async Processing**: Celery-based batch API with task tracking
- **Audit Trail**: Full `PipelineVersion` tracking for reproducibility

---

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────┐
│   FastAPI   │─────▶│   Ollama/    │─────▶│ Validation │
│ Orchestrator│      │   SGLang     │      │  Pipeline  │
└─────────────┘      └──────────────┘      └────────────┘
       │                                           │
       │                                           ▼
       ▼                                    ┌────────────┐
┌─────────────┐                             │   Retry    │
│   Celery    │                             │   Engine   │
│   Workers   │                             └────────────┘
└─────────────┘                                    │
       │                                           │
       ▼                                           ▼
┌─────────────┐                             ┌────────────┐
│   Redis     │                             │ PostgreSQL │
│   Broker    │                             │    DB      │
└─────────────┘                             └────────────┘
```

**Components**:
- **FastAPI**: HTTP API, synchronous and asynchronous endpoints
- **Ollama** (demo/MVP): Local LLM inference with structured output
- **SGLang** (future): Production inference server with guided decoding
- **Celery**: Async task queue for batch processing
- **Redis**: Broker and result backend
- **PostgreSQL**: Result storage and DLQ

---

## 📋 Prerequisites

- **Docker** & **Docker Compose** (recommended) OR:
  - Python 3.11+
  - PostgreSQL 16+
  - Redis 7+
  - Ollama (with at least one model pulled)

---

## 🚀 Quick Start (Docker)

### 1. Clone and setup environment

```bash
git clone <repository_url>
cd TT_InferenceLayer
cp .env.example .env
# Edit .env to customize configuration
```

### 2. Pull Ollama model

```bash
# Start Ollama container first
docker-compose up -d ollama

# Wait for Ollama to start, then pull a model
docker exec -it llm_ollama ollama pull qwen2.5:7b
# or: llama3.1:8b, mistral:7b, etc.
```

### 3. Start all services

```bash
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### 4. Verify health

```bash
curl http://localhost:8000/health

# Expected output:
# {
#   "status": "healthy",
#   "ollama": "connected",
#   "redis": "connected",
#   "database": "connected"
# }
```

### 5. Run database migrations

```bash
docker-compose exec api alembic upgrade head
```

---

## 🧪 Testing

### Run unit tests

```bash
# Inside container
docker-compose exec api pytest tests/unit/ -v

# Or locally (after pip install -e ".[dev]")
pytest tests/unit/ -v
```

### Run integration tests (requires running services)

```bash
docker-compose exec api pytest tests/integration/ -v --cov
```

### Run all tests with coverage

```bash
docker-compose exec api pytest tests/ -v --cov --cov-report=html
```

---

## 📖 API Usage

### Synchronous Triage (Single Email)

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_request.json
```

**Response**:
```json
{
  "dictionaryversion": 1,
  "sentiment": {"value": "neutral", "confidence": 0.85},
  "priority": {"value": "medium", "confidence": 0.72, "signals": ["contratto", "richiesta"]},
  "topics": [
    {
      "labelid": "CONTRATTO",
      "confidence": 0.91,
      "keywordsintext": [
        {"candidateid": "abc123", "lemma": "contratto", "count": 2}
      ],
      "evidence": [
        {"quote": "Richiesta informazioni contratto n. 2024/ABC/123"}
      ]
    }
  ]
}
```

### Asynchronous Batch Triage

```bash
# Submit batch
curl -X POST http://localhost:8000/triage/batch \
  -H "Content-Type: application/json" \
  -d '{"requests": [...]}'

# Response: {"batch_id": "abc-123", "task_ids": ["task-1", "task-2", ...]}

# Check status
curl http://localhost:8000/triage/task/task-1

# Response:
# {"status": "SUCCESS", "result": {...}}
```

### Get JSON Schema

```bash
curl http://localhost:8000/schema
```

---

## 🔧 Development Setup (Local, No Docker)

### 1. Install dependencies

**Option A: Using pyproject.toml (recommended)**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

**Option B: Using requirements files**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# For development (includes all dependencies)
pip install -r requirements-dev.txt

# For production only
pip install -r requirements.txt
```

### 2. Setup services

- Install and start PostgreSQL
- Install and start Redis
- Install and start Ollama, then pull a model

### 3. Configure environment

```bash
cp .env.example .env
# Edit with local URLs: OLLAMA_BASE_URL=http://localhost:11434, etc.
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start FastAPI

```bash
uvicorn inference_layer.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start Celery worker (separate terminal)

```bash
celery -A inference_layer.tasks.celery_app worker --loglevel=info
```

---

## 📂 Project Structure

```
TT_InferenceLayer/
├── src/
│   └── inference_layer/
│       ├── main.py                  # FastAPI app
│       ├── config.py                # Settings (Pydantic BaseSettings)
│       ├── models/                  # Pydantic data models
│       │   ├── enums.py
│       │   ├── input_models.py
│       │   ├── output_models.py
│       │   └── pipeline_version.py
│       ├── api/                     # API routes
│       │   ├── routes_sync.py
│       │   ├── routes_async.py
│       │   └── dependencies.py
│       ├── llm/                     # LLM client abstraction
│       │   ├── base_client.py
│       │   ├── ollama_client.py
│       │   ├── sglang_client.py (stub)
│       │   └── prompt_builder.py
│       ├── validation/              # Multi-stage validation
│       │   ├── pipeline.py
│       │   ├── stage1_json_parse.py
│       │   ├── stage2_schema.py
│       │   ├── stage3_business_rules.py
│       │   ├── stage4_quality.py
│       │   └── verifiers.py
│       ├── retry/                   # Retry engine
│       │   └── engine.py
│       ├── pii/                     # PII redaction
│       │   └── redactor.py
│       ├── tasks/                   # Celery tasks
│       │   ├── celery_app.py
│       │   └── triage_tasks.py
│       └── persistence/             # Database layer
│           ├── db.py
│           ├── repository.py
│           └── models.py (SQLAlchemy)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config/
│   └── schema/
│       └── email_triage_v2.json     # JSON Schema strict
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.worker
├── doc/
│   └── LLM_Layer_Consolidato_v2v3_chat_SUPER_DETAILED.md
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .gitignore
├── IMPLEMENTATION_PROGRESS.md       # Development tracker
└── README.md
```

---

## 🔐 Security & Compliance

### PII Handling
- **Input**: PII are **annotated** (not redacted) in the canonicalized email from upstream layer
- **LLM calls**: PII redacted on-the-fly only if `REDACT_FOR_LLM=true` (for external LLM providers)
- **Storage**: PII redacted before saving results if `REDACT_FOR_STORAGE=true` (GDPR compliance)
- **Self-hosted Ollama**: No redaction needed (PII stays local)

### Secrets Management
- Never commit `.env` to version control
- Use environment variables for all secrets
- In production, use secret management service (AWS Secrets Manager, Azure Key Vault, etc.)

---

## 📊 Monitoring

### Prometheus Metrics

Exposed at `http://localhost:9090/metrics`:

- `triage_requests_total`: Counter of triage requests
- `triage_duration_seconds`: Histogram of processing time
- `validation_failures_total{stage}`: Counter of validation failures by stage
- `retries_total`: Counter of retry attempts
- `dlq_entries_total`: Counter of Dead Letter Queue entries
- `unknown_topic_ratio`: Gauge of UNKNOWN_TOPIC proportion
- `llm_latency_seconds`: Histogram of LLM call latency

### Grafana Dashboards
(Optional, uncomment services in docker-compose.yml)

Access Grafana at `http://localhost:3000` (admin/admin)

---

## 🛠️ Troubleshooting

### Ollama model not found
```bash
docker exec -it llm_ollama ollama pull qwen2.5:7b
```

### Database connection refused
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres
```

### Celery tasks not processing
```bash
# Check worker logs
docker-compose logs worker

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Validation failures
```bash
# Check validation stage in response
# Stage 1 = JSON parse error
# Stage 2 = Schema validation error
# Stage 3 = Business rule violation (candidateid not found, labelid not in enum)
# Stage 4 = Quality warnings (low confidence, missing evidence)
```

---

## 🗺️ Roadmap

- [x] Phase 0: Scaffolding (directory structure, Docker, config)
- [ ] Phase 1: Data Models (Pydantic v2)
- [ ] Phase 2: LLM Client + Prompt Builder
- [ ] Phase 3: Multi-Stage Validation
- [ ] Phase 4: Retry Engine + Fallback
- [ ] Phase 5: API (FastAPI + Celery)
- [ ] Phase 6: PII Redaction
- [ ] Phase 7: Persistence (PostgreSQL)
- [ ] Phase 8: Configuration & Docker
- [ ] Phase 9: Tests (Unit + Integration)
- [ ] Phase 10: Logging, Metrics, CI

See [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md) for detailed tracker.

---

## 📄 License

Proprietary - All rights reserved.

---

## 🤝 Contributing

(Internal project - contributing guidelines TBD)

---

## 📧 Contact

For questions or issues, contact the TT Team.

---

**Design Documentation**: [doc/LLM_Layer_Consolidato_v2v3_chat_SUPER_DETAILED.md](doc/LLM_Layer_Consolidato_v2v3_chat_SUPER_DETAILED.md)
