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
│   Redis     │◀────────────────────────────│   Redis    │
│   Broker    │                             │ Persistence│
└─────────────┘                             └────────────┘
```

**Components**:
- **FastAPI**: HTTP API, synchronous and asynchronous endpoints
- **Ollama** (demo/MVP): Local LLM inference with structured output
- **SGLang** (future): Production inference server with guided decoding
- **Celery**: Async task queue for batch processing
- **Redis**: Broker, result backend, persistence layer, and DLQ storage

---

## 📋 Prerequisites

- **Docker** & **Docker Compose** (recommended) OR:
  - Python 3.11+
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

### Service Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check (all services) |
| `/schema` | GET | JSON Schema for LLM output |
| `/version` | GET | Pipeline version info |
| `/triage` | POST | Synchronous triage (single email) |
| `/triage/batch` | POST | Submit batch (async) |
| `/triage/task/{task_id}` | GET | Check task status |
| `/triage/result/{task_id}` | GET | Get task result |
| `/docs` | GET | Swagger UI |
| `/metrics` | GET | Prometheus metrics |

### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "ollama": "ok",
    "redis": "ok",
    "postgres": "not_configured"
  },
  "timestamp": "2026-02-19T10:30:00Z"
}
```

### 2. Synchronous Triage (Single Email)

**Use case**: Demo, testing, low-latency single emails

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "uid": "email_001",
      "mailbox": "INBOX",
      "message_id": "<test@example.com>",
      "fetched_at": "2026-02-19T10:00:00Z",
      "size": 1500,
      "from_addr_redacted": "cliente@example.com",
      "to_addrs_redacted": ["support@company.com"],
      "subject_canonical": "Richiesta informazioni contratto",
      "date_parsed": "Wed, 19 Feb 2026 10:00:00 +0000",
      "headers_canonical": {},
      "body_text_canonical": "Buongiorno, vorrei avere informazioni sul contratto di assistenza tecnica stipulato il mese scorso.",
      "body_original_hash": "abc123def456",
      "pii_entities": [],
      "removed_sections": [],
      "pipeline_version": {
        "parser_version": "1.0",
        "canonicalization_version": "1.0",
        "ner_model_version": "1.0",
        "pii_redaction_version": "1.0"
      },
      "processing_timestamp": "2026-02-19T10:00:05Z",
      "processing_duration_ms": 50
    },
    "candidate_keywords": [
      {
        "candidate_id": "hash_contratto",
        "term": "contratto",
        "lemma": "contratto",
        "count": 1,
        "source": "body",
        "score": 0.95
      },
      {
        "candidate_id": "hash_assistenza",
        "term": "assistenza tecnica",
        "lemma": "assistenza tecnica",
        "count": 1,
        "source": "body",
        "score": 0.88
      }
    ],
    "dictionary_version": 1
  }'
```

**Response**:
```json
{
  "status": "success",
  "result": {
    "triage_response": {
      "dictionaryversion": 1,
      "sentiment": {
        "value": "neutral",
        "confidence": 0.85
      },
      "priority": {
        "value": "medium",
        "confidence": 0.72,
        "signals": ["contratto", "richiesta"]
      },
      "topics": [
        {
          "labelid": "CONTRATTO",
          "confidence": 0.91,
          "keywordsintext": [
            {
              "candidateid": "hash_contratto",
              "lemma": "contratto",
              "count": 1
            }
          ],
          "evidence": [
            {
              "quote": "informazioni sul contratto di assistenza tecnica"
            }
          ]
        },
        {
          "labelid": "ASSISTENZATECNICA",
          "confidence": 0.87,
          "keywordsintext": [
            {
              "candidateid": "hash_assistenza",
              "lemma": "assistenza tecnica",
              "count": 1
            }
          ],
          "evidence": [
            {
              "quote": "assistenza tecnica stipulato"
            }
          ]
        }
      ]
    },
    "pipeline_version": {
      "parser_version": "1.0",
      "canonicalization_version": "1.0",
      "ner_model_version": "1.0",
      "pii_redaction_version": "1.0",
      "dictionary_version": "1",
      "schema_version": "2.0",
      "model_name": "qwen2.5:7b",
      "temperature": "0.1",
      "top_n_candidates": "100",
      "body_limit": "8000"
    },
    "request_uid": "email_001",
    "validation_warnings": [],
    "retries_used": 0,
    "processing_duration_ms": 1523,
    "created_at": "2026-02-19T10:00:07Z"
  },
  "warnings": []
}
```

### 3. Asynchronous Batch Triage

**Use case**: Production batch processing

#### Step 1: Submit Batch

```bash
curl -X POST http://localhost:8000/triage/batch \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"email": {...}, "candidate_keywords": [...], "dictionary_version": 1},
      {"email": {...}, "candidate_keywords": [...], "dictionary_version": 1}
    ]
  }'
```

**Response**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_count": 2,
  "task_ids": [
    "abc123-task-id-1",
    "def456-task-id-2"
  ],
  "submitted_at": "2026-02-19T10:05:00Z"
}
```

#### Step 2: Check Task Status

```bash
curl http://localhost:8000/triage/task/abc123-task-id-1
```

**Response (PENDING)**:
```json
{
  "task_id": "abc123-task-id-1",
  "status": "PENDING"
}
```

**Response (SUCCESS)**:
```json
{
  "task_id": "abc123-task-id-1",
  "status": "SUCCESS",
  "result": {
    "triage_response": {...},
    "pipeline_version": {...},
    "request_uid": "email_001",
    "validation_warnings": [],
    "retries_used": 0,
    "processing_duration_ms": 1523,
    "created_at": "2026-02-19T10:05:03Z"
  }
}
```

**Response (FAILURE)**:
```json
{
  "task_id": "abc123-task-id-1",
  "status": "FAILURE",
  "error": "RetryExhausted: Unable to process after 3 retry attempts"
}
```

#### Step 3: Get Task Result (Blocking)

```bash
curl http://localhost:8000/triage/result/abc123-task-id-1
```

**Returns**: `200` with result (if SUCCESS), `202` (if still processing), `404` (if not found), `500` (if failed)

### 4. Get JSON Schema

```bash
curl http://localhost:8000/schema
```

**Returns**: Complete JSON Schema used for LLM structured output validation

### 5. Get Version Info

```bash
curl http://localhost:8000/version
```

**Response**:
```json
{
  "inference_layer_version": "0.1.0",
  "model_name": "qwen2.5:7b",
  "dictionary_version": 1,
  "schema_version": "2.0",
  "pipeline_config": {
    "parser": "1.0",
    "canonicalization": "1.0",
    "ner_model": "1.0",
    "pii_redaction": "1.0",
    "temperature": "0.1",
    "top_n_candidates": "100",
    "body_limit": "8000"
  }
}
```

### Error Responses

| Status Code | Error Type | Description |
|-------------|-----------|-------------|
| `400` | Bad Request | Invalid request format |
| `422` | Validation Error | LLM response validation failed |
| `502` | Bad Gateway | Ollama connection failed |
| `503` | Service Unavailable | Retry exhausted (DLQ) |
| `504` | Gateway Timeout | LLM timeout |

**Example Error Response**:
```json
{
  "error": "validation_failed",
  "message": "Stage 3: Business rule violation",
  "details": {
    "stage": "stage3_business_rules",
    "rule_name": "candidateid_exists",
    "field_path": "topics[0].keywordsintext[0].candidateid",
    "invalid_value": "invented_id_123",
    "expected_values": ["hash_contratto", "hash_assistenza"]
  },
  "timestamp": "2026-02-19T10:10:00Z"
}
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

- [x] **Phase 0**: Scaffolding (directory structure, Docker, config)
- [x] **Phase 1**: Data Models (Pydantic v2, enums, input/output models, JSON Schema)
- [x] **Phase 2**: LLM Client + Prompt Builder (OllamaClient, PromptBuilder, PII redactor)
- [x] **Phase 3**: Multi-Stage Validation (4-stage pipeline, verifiers, exceptions)
- [x] **Phase 4**: Retry Engine + Fallback (4-level retry, metadata tracking, DLQ logging)
- [x] **Phase 5**: API (FastAPI + Celery) — **✓ COMPLETED**
  - ✓ Synchronous endpoints (`/triage`, `/health`, `/schema`, `/version`)
  - ✓ Asynchronous endpoints (`/triage/batch`, `/triage/task/{id}`, `/triage/result/{id}`)
  - ✓ Celery tasks (`triage_email`, `triage_batch`)
  - ✓ Exception handlers (structured error responses)
  - ✓ Dependency injection (singleton LLM client, prompt builder)
  - ✓ Prometheus metrics instrumentation
  - ✓ Unit tests (dependencies, models)
  - ✓ Integration tests (TestClient, health checks)
- [ ] **Phase 6**: PII Redaction (on-the-fly for LLM, configurable)
- [x] **Phase 7**: Persistence (Redis-based, DLQ storage, repository pattern)
- [ ] **Phase 8**: Configuration & Docker (finalize Dockerfiles, healthchecks)
- [ ] **Phase 9**: Tests (comprehensive unit + integration coverage ≥85%)
- [ ] **Phase 10**: Logging, Metrics, CI (structured logging, Grafana dashboards, GitHub Actions)

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
