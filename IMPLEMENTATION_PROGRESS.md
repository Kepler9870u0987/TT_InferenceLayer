# LLM Inference Layer — Implementation Progress Tracker

> **Progetto**: Thread Classificator Mail - LLM Inference Layer  
> **Data inizio**: 2026-02-19  
> **Ultimo aggiornamento**: 2026-02-19  
> **Stato generale**: 🟡 IN PROGRESS (Fase 0, 1, 2 completate - Fase 3 prossima)

---

## Quick Status Overview

| Fase | Stato | Completamento | Note |
|------|-------|---------------|------|
| **Fase 0** — Scaffolding | 🟢 Completed | 100% | Structure, pyproject.toml, Docker, README done |
| **Fase 1** — Data Models | 🟢 Completed | 100% | Enums, input/output models, JSON Schema, fixtures done |
| **Fase 2** — LLM Client | 🟢 Completed | 100% | BaseLLMClient, OllamaClient, PromptBuilder, PII redactor, tests done |
| **Fase 3** — Validation | ⚪ Not Started | 0% | - |
| **Fase 4** — Retry Engine | ⚪ Not Started | 0% | - |
| **Fase 5** — API FastAPI | ⚪ Not Started | 0% | - |
| **Fase 6** — PII Redaction | ⚪ Not Started | 0% | - |
| **Fase 7** — Persistenza | ⚪ Not Started | 0% | - |
| **Fase 8** — Config & Docker | ⚪ Not Started | 0% | - |
| **Fase 9** — Tests | ⚪ Not Started | 0% | - |
| **Fase 10** — Logging & CI | ⚪ Not Started | 0% | - |

**Legenda**: 🟢 Completed | 🟡 In Progress | ⚪ Not Started | 🔴 Blocked

---

## Fase 0 — Scaffolding Progetto (1–2 giorni) ✅ COMPLETED

### Tasks

- [x] 0.1 — Creare struttura directory completa (src/, tests/, config/, docker/)
- [x] 0.2 — pyproject.toml con dipendenze base
- [x] 0.3 — docker-compose.yml (api, ollama, redis, postgres, worker)
- [x] 0.4 — .env.example con tutte le variabili di config
- [x] 0.5 — README.md con setup e architettura

### Files Created
- `src/inference_layer/__init__.py`
- `src/inference_layer/main.py`
- `src/inference_layer/config.py`
- `src/inference_layer/models/__init__.py`
- `src/inference_layer/api/__init__.py`
- `src/inference_layer/llm/__init__.py`
- `src/inference_layer/validation/__init__.py`
- `src/inference_layer/retry/__init__.py`
- `src/inference_layer/pii/__init__.py`
- `src/inference_layer/tasks/__init__.py`
- `src/inference_layer/persistence/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/fixtures/__init__.py`
- `pyproject.toml`
- `docker-compose.yml`
- `docker/Dockerfile`
- `docker/Dockerfile.worker`
- `.env.example`
- `README.md`

### Notes
- Decisioni: Python 3.11, FastAPI, Pydantic v2, Docker Compose completo
- Candidate keywords arrivano dall'upstream (non generati qui)
- PII NON redattati in input; redaction on-the-fly solo per LLM esterni
- API sia sincrona che asincrona (Celery)

---

## Fase 1 — Data Models (Pydantic v2) (2–3 giorni) ✅ COMPLETED

### Tasks

- [x] 1.1 — Enums (TopicsEnum, SentimentEnum, PriorityEnum)
- [x] 1.2 — Input models (PiiEntity, RemovedSection, EmailDocument, CandidateKeyword, TriageRequest)
- [x] 1.3 — Output models (KeywordInText, EvidenceItem, TopicResult, SentimentResult, PriorityResult, EmailTriageResponse, TriageResult)
- [x] 1.4 — PipelineVersion (frozen dataclass)
- [x] 1.5 — JSON Schema email_triage_v2.json
- [x] 1.6 — Sample fixtures (email, candidates, valid response)

### Files Created
- `src/inference_layer/models/enums.py`
- `src/inference_layer/models/pipeline_version.py`
- `src/inference_layer/models/input_models.py`
- `src/inference_layer/models/output_models.py`
- `config/schema/email_triage_v2.json`
- `tests/fixtures/sample_email.json`
- `tests/fixtures/sample_candidates.json`
- `tests/fixtures/valid_llm_response.json`

### Notes
- Schema strict: additionalProperties=false, min/max vincoli
- Conformità al JSON Schema email_triage_v2

---

## Fase 2 — LLM Client Abstraction + Prompt Builder (3–4 giorni)

### Tasks
---

## Fase 2 — LLM Client Abstraction + Prompt Builder (3–4 giorni) ✅ COMPLETED

### Tasks

- [x] 2.1 — Abstract base client (BaseLLMClient ABC)
- [x] 2.2 — Ollama client implementation (structured output JSON)
- [x] 2.3 — SGLang client stub (per futuro)
- [x] 2.4 — Prompt builder (system + user payload, truncation, top-N)
- [x] 2.5 — Text utilities (truncation, PII span adjustment)
- [x] 2.6 — PII redactor (on-the-fly redaction)
- [x] 2.7 — LLM-specific models (LLMGenerationRequest, LLMGenerationResponse, LLMMetadata)
- [x] 2.8 — LLM exceptions hierarchy
- [x] 2.9 — Prompt templates (Jinja2)
- [x] 2.10 — Unit tests (text_utils, redactor, prompt_builder)
- [x] 2.11 — Integration tests (Ollama client)
- [x] 2.12 — Update config with LLM settings
- [x] 2.13 — Update module exports

### Files Created
- `src/inference_layer/models/llm_models.py` (LLMGenerationRequest, LLMGenerationResponse, LLMMetadata)
- `src/inference_layer/llm/exceptions.py` (LLM exception hierarchy)
- `src/inference_layer/llm/base_client.py` (BaseLLMClient ABC)
- `src/inference_layer/llm/ollama_client.py` (OllamaClient with httpx AsyncClient)
- `src/inference_layer/llm/sglang_client.py` (SGLangClient stub)
- `src/inference_layer/llm/text_utils.py` (truncate_at_sentence_boundary, adjust_pii_spans, count_tokens_approximate)
- `src/inference_layer/llm/prompt_builder.py` (PromptBuilder with Jinja2)
- `src/inference_layer/pii/redactor.py` (redact_pii_for_llm, redact_pii_in_candidates)
- `config/prompts/system_prompt.txt` (System prompt template)
- `config/prompts/user_prompt_template.txt` (User prompt template)
- `tests/unit/llm/test_text_utils.py` (Unit tests for text utilities)
- `tests/unit/llm/test_prompt_builder.py` (Unit tests for prompt builder)
- `tests/unit/pii/test_redactor.py` (Unit tests for PII redaction)
- `tests/integration/llm/test_ollama_integration.py` (Integration tests for Ollama)

### Notes
- **Architecture**: Model-agnostic abstraction with BaseLLMClient ABC
- **Ollama Client**: Async implementation using httpx.AsyncClient with connection pooling
- **Structured Output**: JSON Schema passed via `format` parameter to Ollama
- **Retry Logic**: Built-in connection-level retries (2 attempts) with exponential backoff
- **Prompt Engineering**: Jinja2 templates for maintainability and version control
- **Text Processing**: Sentence-boundary truncation (8000 chars normal, 4000 shrink)
- **Candidate Selection**: Top-N filtering (100 normal, 50 shrink)
- **PII Handling**: On-the-fly redaction (configurable, default OFF for self-hosted Ollama)
- **Temperature**: 0.1 for determinism
- **Testing**: Unit tests for all utilities, integration tests for Ollama (requires running server)

### Decisions Made
- **httpx over ollama package**: Direct HTTP control, no extra dependencies
- **Async-only**: Consistent with FastAPI, better scalability
- **Jinja2 templates**: Prompts as external files for maintainability
- **Sentence boundary truncation**: Preserves semantic coherence over simple char truncation
- **PII redaction configurable**: OFF by default (safe for self-hosted), ready for external LLMs

---

## Fase 3 — Validazione Multi-Stadio (3–4 giorni)

### Tasks

- [ ] 3.1 — Stage 1: JSON Parse
- [ ] 3.2 — Stage 2: JSON Schema validation
- [ ] 3.3 — Stage 3: Business rules (candidateid exists, labelid in enum)
- [ ] 3.4 — Stage 4: Quality checks (confidence gating, dedup, warnings)
- [ ] 3.5 — Verifiers extra (evidence presence, keyword presence, spans coherence)
- [ ] 3.6 — Pipeline orchestrator

### Files Created
- N/A

### Notes
- Hard fail su stage 1/2/3 → retry
- Warnings su stage 4 → salvati ma non bloccanti

---

## Fase 4 — Retry Engine + Fallback (2–3 giorni)

### Tasks

- [ ] 4.1 — Retry standard (max 3 tentativi, backoff esponenziale)
- [ ] 4.2 — Shrink request (meno candidati + body più corto)
- [ ] 4.3 — Fallback modello alternativo
- [ ] 4.4 — DLQ routing + logging

### Files Created
- N/A

### Notes
- Policy a 4 livelli: retry → shrink → fallback → DLQ
- Logging strutturato per audit

---

## Fase 5 — API FastAPI (2–3 giorni)

### Tasks

- [ ] 5.1 — Endpoint sincrono POST /triage
- [ ] 5.2 — Endpoint asincrono POST /triage/batch
- [ ] 5.3 — Endpoint GET /triage/task/{task_id}
- [ ] 5.4 — Health check GET /health
- [ ] 5.5 — Schema endpoint GET /schema
- [ ] 5.6 — Celery tasks (triage_email, triage_batch)
- [ ] 5.7 — Celery app configuration

### Files Created
- N/A

### Notes
- Sincrono per singola email (demo/test rapidi)
- Asincrono per batch (produzione)

---

## Fase 6 — PII Redaction on-the-fly (1–2 giorni)

### Tasks

- [ ] 6.1 — Redactor module (redact_text basato su pii_entities annotate)
- [ ] 6.2 — Redaction per LLM esterni (configurabile)
- [ ] 6.3 — Redaction per persistenza GDPR

### Files Created
- N/A

### Notes
- Input body NON redattato
- Redaction applicata on-the-fly solo quando necessario (LLM esterno / storage)

---

## Fase 7 — Persistenza (2 giorni)

### Tasks

- [ ] 7.1 — Database schema (triage_results, dlq_triage_failures)
- [ ] 7.2 — Repository pattern (save_result, save_to_dlq, get_result)
- [ ] 7.3 — SQLAlchemy async setup

### Files Created
- N/A

### Notes
- PostgreSQL con JSONB per response e pipeline_version
- DLQ table per failure tracking

---

## Fase 8 — Configurazione e Docker (2 giorni)

### Tasks

- [ ] 8.1 — Settings module (Pydantic BaseSettings)
- [ ] 8.2 — Dockerfile (multi-stage build)
- [ ] 8.3 — Dockerfile.worker
- [ ] 8.4 — docker-compose.yml completo con healthchecks

### Files Created
- N/A

### Notes
- Tutte le variabili configurabili via env
- GPU passthrough per Ollama

---

## Fase 9 — Tests (3–4 giorni)

### Tasks

- [ ] 9.1 — Unit tests (models, prompt builder, validators, verifiers, retry)
- [ ] 9.2 — Integration tests (Ollama client, full pipeline, API)
- [ ] 9.3 — Fixtures (sample email, candidates, valid/invalid responses)

### Files Created
- N/A

### Notes
- Target: copertura ≥ 85%
- Integration tests con Ollama in CI se possibile

---

## Fase 10 — Logging, Metriche, CI (2–3 giorni)

### Tasks

- [ ] 10.1 — Structured logging con structlog
- [ ] 10.2 — Metriche Prometheus custom
- [ ] 10.3 — CI pipeline (lint, type check, tests, build)

### Files Created
- N/A

### Notes
- Metriche chiave: validation_failures, retries, dlq_entries, unknown_topic_ratio

---

## Known Issues / Blockers

_Nessun blocker al momento._

---

## Next Steps (Current Sprint)

1. ✅ Creare file di tracking
2. ✅ Completare scaffolding base (directory structure)
3. ✅ pyproject.toml con dipendenze
4. ✅ docker-compose.yml
5. ✅ .env.example e README.md
6. ✅ Implementare data models (enums, input models, output models)
7. ✅ Implementare LLM client abstraction (BaseLLMClient, OllamaClient)
8. ✅ Implementare prompt builder (Jinja2 templates, truncation, top-N)
9. ✅ Implementare PII redactor e text utilities
10. ✅ Unit & integration tests per Fase 2
11. 🔄 **CURRENT**: Implementare validation pipeline (4 stages + verifiers)
12. 🔜 Implementare retry engine con fallback strategies
13. 🔜 Implementare API FastAPI (endpoints sincroni/asincroni)

---

## Decision Log

| Data | Decisione | Rationale |
|------|-----------|-----------|
| 2026-02-19 | Scope: solo layer LLM (no candidate keyword generator) | Candidate keywords arrivano dall'upstream |
| 2026-02-19 | PII: body NON redattato in input | Permette analisi LLM più ricca; redaction on-the-fly solo per LLM esterni/storage |
| 2026-02-19 | API: sincrona + asincrona (Celery) | Sincrona per demo, asincrona per batch produzione |
| 2026-02-19 | Stack: Python 3.11, FastAPI, Pydantic v2, Docker Compose | Coerente con design doc v2/v3 |
| 2026-02-19 | Model: astrazione model-agnostic | Facilita switch Ollama → SGLang in futuro |
| 2026-02-19 | LLM Client: httpx diretto (no ollama package) | Maggiore controllo, no dipendenze extra, facilita debugging |
| 2026-02-19 | Async-only per LLM client | Coerenza con FastAPI async; migliore scalabilità |
| 2026-02-19 | Prompts: Jinja2 templates in config/prompts/ | Manutenibilità, versionamento, sperimentazione facilitata |
| 2026-02-19 | Truncation: sentence boundary | Preserva contesto semantico vs hard truncation |
| 2026-02-19 | Jinja2 dependency added | Per prompt templating (3.1.0+)

---

## References

- [Design Doc](doc/LLM_Layer_Consolidato_v2v3_chat_SUPER_DETAILED.md)
- [JSON Schema](config/schema/email_triage_v2.json) — da creare
- [Sample Input](tests/fixtures/sample_email.json) — da creare

---

**Istruzioni per riprendere dopo interruzione**:
1. Leggere questo file per vedere lo stato attuale
2. Controllare l'ultima sezione "Next Steps" per i task correnti
3. Verificare "Known Issues / Blockers" per problemi aperti
4. Controllare "Decision Log" per contesto decisionale
5. Riprendere dall'ultima task non completata
