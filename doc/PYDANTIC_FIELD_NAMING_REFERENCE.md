# Pydantic Field Naming Reference

**Document Purpose:** This reference maps Pydantic model field names to avoid test fixture mismatches.

**Created:** 2026-02-19  
**Last Updated:** 2026-02-19

---

## ⚠️ Important Naming Convention

This project uses **INCONSISTENT** field naming conventions across different models:

- **Input models** (`TriageRequest`, `CandidateKeyword`, `EmailDocument`): Use `snake_case`
- **Output models** (`EmailTriageResponse`, `TopicResult`, `KeywordInText`): Use **no underscores**

This is **intentional** due to JSON Schema requirements for the LLM API.

---

## Input Models (src/inference_layer/models/input_models.py)

### EmailDocument
```python
# ✅ CORRECT - Uses snake_case
EmailDocument(
    uid="...",
    mailbox="...",
    message_id="...",
    fetched_at=datetime.now(),
    size=1000,
    from_addr_redacted="...",
    to_addrs_redacted=["..."],
    subject_canonical="...",
    date_parsed="...",
    headers_canonical={},
    body_text_canonical="...",
    body_original_hash="...",
    pii_entities=[],
    removed_sections=[],
    pipeline_version=InputPipelineVersion(...),
    processing_timestamp=datetime.now(),
    processing_duration_ms=100
)
```

### CandidateKeyword
```python
# ✅ CORRECT - Uses snake_case
CandidateKeyword(
    candidate_id="hash_001",        # WITH underscore
    term="contratto",
    lemma="contratto",
    count=1,                         # MUST be >= 1
    source="body",
    score=0.9
)
```

### TriageRequest
```python
# ✅ CORRECT - Uses snake_case
TriageRequest(
    email=email_doc,                # NOT email_document
    candidate_keywords=[...],       # List must have min_length=1
    dictionary_version=1,            # WITH underscore (≠ output model)
    config_overrides=None
)
```

---

## Output Models (src/inference_layer/models/output_models.py)

### KeywordInText
```python
# ✅ CORRECT - NO underscores
KeywordInText(
    candidateid="hash_001",         # NO underscore ❗
    lemma="contratto",
    count=1,
    spans=[[0, 5], [10, 15]]        # Optional list[tuple[int, int]]
)

# ❌ WRONG
KeywordInText(candidate_id="...", ...)  # Will fail validation
```

### EvidenceItem
```python
# ✅ CORRECT
EvidenceItem(
    quote="informazioni sul contratto",
    span=[7, 36]                    # Optional [start, end]
)
```

### TopicResult
```python
# ✅ CORRECT - NO underscores
TopicResult(
    labelid="CONTRATTO",            # NO underscore ❗
    confidence=0.9,
    keywordsintext=[...],           # NO underscores ❗
    evidence=[...]
)

# ❌ WRONG
TopicResult(
    label_id="...",                 # Will fail
    keywords_in_text=[...],         # Will fail
    ...
)
```

### SentimentResult
```python
# ✅ CORRECT
SentimentResult(
    value="neutral",                # Must be SentimentEnum value
    confidence=0.8
)
```

### PriorityResult
```python
# ✅ CORRECT
PriorityResult(
    value="medium",                 # Must be PriorityEnum value
    confidence=0.7,
    signals=["keyword_cta", "urgency_medium"]
)
```

### EmailTriageResponse
```python
# ✅ CORRECT - NO underscores
EmailTriageResponse(
    dictionaryversion=1,            # NO underscore ❗ (≠ input model)
    sentiment=SentimentResult(...),
    priority=PriorityResult(...),
    topics=[TopicResult(...), ...]
)

# ❌ WRONG
EmailTriageResponse(dictionary_version=1, ...)  # Will fail
```

---

## Field Access in Code

### ✅ CORRECT Examples

```python
# Accessing TriageRequest (input model - snake_case)
request.email                        # NOT request.email_document
request.candidate_keywords
request.dictionary_version           # WITH underscore

# Accessing EmailTriageResponse (output model - no underscores)
response.dictionaryversion           # NO underscore
response.topics

# Accessing TopicResult (output model - no underscores)
topic.labelid                        # NO underscore
topic.keywordsintext                 # NO underscores
topic.confidence

# Accessing KeywordInText (output model - no underscores)
keyword.candidateid                  # NO underscore
keyword.lemma
keyword.count

# Accessing CandidateKeyword (input model - snake_case)
candidate.candidate_id               # WITH underscore
candidate.term
```

### ❌ COMMON MISTAKES

```python
# ❌ Wrong - mixing conventions
request.email_document               # Should be: request.email
response.dictionary_version          # Should be: response.dictionaryversion
topic.label_id                       # Should be: topic.labelid
topic.keywords_in_text               # Should be: topic.keywordsintext
keyword.candidate_id                 # Should be: keyword.candidateid (in output)
```

---

## Quick Reference Table

| Model Class          | Field Name             | Convention    | Notes                          |
|----------------------|------------------------|---------------|--------------------------------|
| TriageRequest        | `email`                | snake_case    | NOT `email_document`           |
| TriageRequest        | `dictionary_version`   | snake_case    | WITH underscore                |
| CandidateKeyword     | `candidate_id`         | snake_case    | WITH underscore (input model)  |
| EmailTriageResponse  | `dictionaryversion`    | no_underscore | NO underscore                  |
| TopicResult          | `labelid`              | no_underscore | NO underscore                  |
| TopicResult          | `keywordsintext`       | no_underscore | NO underscores                 |
| KeywordInText        | `candidateid`          | no_underscore | NO underscore (output model)   |
| SentimentResult      | `value`                | snake_case    | Must be enum value             |
| PriorityResult       | `value`                | snake_case    | Must be enum value             |

---

## Test Fixture Helpers

### EmailDocument Helper (Use in ALL tests)
```python
from datetime import datetime
from inference_layer.models.input_models import EmailDocument, InputPipelineVersion

def create_test_email_doc(body_text: str) -> EmailDocument:
    """Helper to create a minimal valid EmailDocument for testing."""
    return EmailDocument(
        uid="test_uid",
        mailbox="INBOX",
        message_id="<test@example.com>",
        fetched_at=datetime.now(),
        size=1000,
        from_addr_redacted="test@example.com",
        to_addrs_redacted=["support@example.com"],
        subject_canonical="Test Subject",
        date_parsed="Thu, 1 Jan 2026 12:00:00 +0000",
        headers_canonical={},
        body_text_canonical=body_text,
        body_original_hash="test_hash",
        pii_entities=[],
        removed_sections=[],
        pipeline_version=InputPipelineVersion(
            parser_version="1.0",
            canonicalization_version="1.0",
            ner_model_version="1.0",
            pii_redaction_version="1.0"
        ),
        processing_timestamp=datetime.now(),
        processing_duration_ms=100
    )
```

---

## Validation

Use this checklist when writing tests:

- [ ] **Input models** use `snake_case` (e.g., `candidate_id`, `dictionary_version`)
- [ ] **Output models** use `no_underscore` (e.g., `candidateid`, `dictionaryversion`)
- [ ] `TriageRequest.email` (NOT `email_document`)
- [ ] `TriageRequest.dictionary_version` (WITH underscore)
- [ ] `EmailTriageResponse.dictionaryversion` (NO underscore)
- [ ] `TopicResult.labelid` (NO underscore)
- [ ] `TopicResult.keywordsintext` (NO underscores)
- [ ] `KeywordInText.candidateid` (NO underscore)
- [ ] `CandidateKeyword.candidate_id` (WITH underscore)
- [ ] `EmailDocument` uses helper function with ALL 16 required fields
- [ ] `CandidateKeyword.count >= 1` (Pydantic validation requirement)

---

## Why This Inconsistency?

The output models (`EmailTriageResponse`, `TopicResult`, `KeywordInText`, etc.) **MUST** match the JSON Schema (`config/schema/email_triage_v2.json`) that the LLM uses for structured generation. The JSON Schema specifies field names without underscores (e.g., `dictionaryversion`, `labelid`, `candidateid`).

The input models follow Python conventions (snake_case) since they're internal Python objects not exposed directly to the LLM.

---

## Related Files

- Input models: `src/inference_layer/models/input_models.py`
- Output models: `src/inference_layer/models/output_models.py`
- JSON Schema: `config/schema/email_triage_v2.json`
- Enums: `src/inference_layer/models/enums.py`

---

**Last Verified:** Phase 3 implementation (2026-02-19)
