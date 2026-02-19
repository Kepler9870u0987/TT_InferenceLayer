# LLM Inference Layer — Implementation Progress Tracker

> **Progetto**: Thread Classificator Mail - LLM Inference Layer  
> **Data inizio**: 2026-02-19  
> **Ultimo aggiornamento**: 2026-02-19  
> **Stato generale**: 🟡 IN PROGRESS (Fase 0, 1, 2, 3 completate - Fase 4 prossima)

---

## Quick Status Overview

| Fase | Stato | Completamento | Note |
|------|-------|---------------|------|
| **Fase 0** — Scaffolding | 🟢 Completed | 100% | Structure, pyproject.toml, Docker, README done |
| **Fase 1** — Data Models | 🟢 Completed | 100% | Enums, input/output models, JSON Schema, fixtures done |
| **Fase 2** — LLM Client | 🟢 Completed | 100% | BaseLLMClient, OllamaClient, PromptBuilder, PII redactor, tests done |
| **Fase 3** — Validation | 🟢 Completed | 100% | 4-stage pipeline, verifiers, 85+ tests, fixtures complete |
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

## Fase 3 — Validazione Multi-Stadio (3–4 giorni) ✅ COMPLETED

### Tasks

- [x] 3.1 — Stage 1: JSON Parse (hard fail)
- [x] 3.2 — Stage 2: JSON Schema validation (hard fail)
- [x] 3.3 — Stage 3: Business rules (candidateid exists, labelid in enum) (hard fail)
- [x] 3.4 — Stage 4: Quality checks (confidence gating, dedup, warnings)
- [x] 3.5 — Verifiers extra (evidence presence, keyword presence, spans coherence)
- [x] 3.6 — Pipeline orchestrator (ValidationPipeline)
- [x] 3.7 — Validation exceptions hierarchy
- [x] 3.8 — ValidationContext dataclass
- [x] 3.9 — Unit tests for all stages and verifiers
- [x] 3.10 — Integration tests for full pipeline
- [x] 3.11 — Invalid test fixtures for failure scenarios
- [x] 3.12 — Update module exports

### Files Created
- `src/inference_layer/validation/exceptions.py` (ValidationError, JSONParseError, SchemaValidationError, BusinessRuleViolation)
- `src/inference_layer/validation/stage1_json_parse.py` (Stage1JSONParse)
- `src/inference_layer/validation/stage2_schema.py` (Stage2SchemaValidation with jsonschema)
- `src/inference_layer/validation/stage3_business_rules.py` (Stage3BusinessRules)
- `src/inference_layer/validation/stage4_quality.py` (Stage4QualityChecks)
- `src/inference_layer/validation/verifiers.py` (EvidencePresenceVerifier, KeywordPresenceVerifier, SpansCoherenceVerifier)
- `src/inference_layer/validation/pipeline.py` (ValidationPipeline orchestrator, ValidationContext)
- `tests/unit/validation/__init__.py`
- `tests/unit/validation/test_stage1_json_parse.py` (13 test cases)
- `tests/unit/validation/test_stage2_schema.py` (15 test cases covering schema violations)
- `tests/unit/validation/test_stage3_business_rules.py` (15 test cases for business rules)
- `tests/unit/validation/test_stage4_quality.py` (17 test cases for quality warnings)
- `tests/unit/validation/test_verifiers.py` (25+ test cases for all verifiers)
- `tests/integration/validation/__init__.py`
- `tests/integration/validation/test_validation_pipeline.py` (15 integration tests for full pipeline)
- `tests/fixtures/invalid_json_response.json` (malformed JSON fixture)
- `tests/fixtures/invalid_schema_response.json` (missing required field)
- `tests/fixtures/invalid_business_rules_response.json` (invented candidateid + invalid topic)
- `tests/fixtures/low_quality_response.json` (low confidence, duplicates, long quotes)

### Notes
- **Stage 1-3 (Hard Fail)**: Raise exceptions that trigger retry engine
  - Stage 1: JSON parsing with detailed error messages
  - Stage 2: JSON Schema validation using jsonschema library with schema caching
  - Stage 3: Business rules enforcement (candidateid exists, labelid in enum, version match, sentiment/priority enums)
- **Stage 4 (Warnings)**: Quality checks accumulate warnings (non-blocking)
  - Low confidence detection (configurable threshold, default 0.2)
  - Duplicate detection (topics, keywords, evidence quotes)
  - Completeness checks (topics without keywords/evidence, empty priority signals)
  - Long quote detection (>180 chars, max is 200)
- **Verifiers (Warnings)**: Semantic coherence checks (configurable)
  - Evidence presence: Verify quotes exist in email text (case-insensitive substring match)
  - Keyword presence: Verify terms/lemmas appear in email text
  - Spans coherence: Validate span arrays are well-formed [start, end] within bounds
- **Pipeline Orchestrator**: Coordinates all stages and verifiers
  - Sequential execution: Stage 1 → Stage 2 → Pydantic parse → Stage 3 → Stage 4 → Verifiers
  - ValidationContext passed through for settings and warnings accumulation
  - Async implementation consistent with LLM client API
  - Configurable verifiers via settings (ENABLE_EVIDENCE_PRESENCE_CHECK, ENABLE_KEYWORD_PRESENCE_CHECK)
  - Returns tuple of (validated EmailTriageResponse, list of warnings)
- **Exception Hierarchy**: Structured for retry engine integration
  - ValidationError (base) with details dict for logging/metrics
  - JSONParseError includes content snippet (500 chars) and parse error details
  - SchemaValidationError includes list of validation errors with field paths
  - BusinessRuleViolation includes rule_name, invalid_value, expected_values, field_path
- **Testing**: Comprehensive coverage
  - 85+ unit test cases covering all stages, verifiers, and edge cases
  - 15 integration tests exercising full pipeline with real fixtures
  - Test fixtures for valid and invalid responses (malformed JSON, schema violations, business rule violations, low quality)
  - Tests verify exceptions are raised correctly, warnings are accumulated, and logging works
- **Configuration**: Validation settings in config.py
  - JSON_SCHEMA_PATH: config/schema/email_triage_v2.json
  - MIN_CONFIDENCE_WARNING_THRESHOLD: 0.2 (warn if topic/sentiment/priority confidence below this)
  - ENABLE_EVIDENCE_PRESENCE_CHECK: True (configurable verifier)
  - ENABLE_KEYWORD_PRESENCE_CHECK: True (configurable verifier)

### Decisions Made
- **Stage-based architecture**: Each stage is independent, testable, follows single responsibility
- **Fail-fast on hard errors**: Stages 1-3 raise exceptions immediately (no partial validation)
- **Accumulate warnings**: Stage 4 + verifiers collect all warnings before returning (for audit trail)
- **ValidationContext pattern**: Clean way to pass request/settings through pipeline without coupling stages
- **Async pipeline**: Consistent with LLM client API, prepares for future async verifiers if needed
- **Schema caching**: Load JSON Schema once and reuse (performance optimization)
- **Configurable verifiers**: Production can tune strictness via config flags (evidence/keyword presence checks optional)
- **Detailed error messages**: All exceptions include field paths, invalid values, expected values for debugging/metrics
- **Case-insensitive matching**: Evidence and keyword presence checks are case-insensitive for robustness

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
11. ✅ Implementare validation pipeline (4 stages + verifiers)
12. ✅ Implementare exceptions hierarchy per validation
13. ✅ Unit tests completi per validation (85+ test cases)
14. ✅ Integration tests per validation pipeline
15. ✅ Invalid test fixtures per failure scenarios
16. 🔄 **CURRENT**: Implementare retry engine con fallback strategies (Phase 4)
17. 🔜 Implementare API FastAPI (endpoints sincroni/asincroni)
18. 🔜 Implementare persistence layer (PostgreSQL + JSONB)

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
| 2026-02-19 | Validation: 4-stage architecture | Separazione responsabilità: parse → schema → business → quality |
| 2026-02-19 | Validation: Stages 1-3 hard fail, Stage 4 warnings | Hard fail su errori strutturali/semantici; warnings su quality issues |
| 2026-02-19 | Validation: jsonschema library per Stage 2 | Standard, ben testato, caching per performance |
| 2026-02-19 | Validation: Verifiers configurabili | Evidence/keyword presence checks optional via config flags |
| 2026-02-19 | Validation: ValidationContext pattern | Clean dependency injection per settings/warnings accumulation |
| 2026-02-19 | Validation: Structured exceptions con details | Include field_path, invalid_value, expected_values per debugging/metrics |
| 2026-02-19 | Validation: Case-insensitive matching | Evidence/keyword presence più robusto (quote text normalization) |

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
