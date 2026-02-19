"""Shared test fixtures and configuration for all tests.

This conftest.py provides common fixtures used across unit and integration tests.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from inference_layer.config import Settings
from inference_layer.models.input_models import (
    CandidateKeyword,
    EmailDocument,
    InputPipelineVersion,
    TriageRequest,
)
from inference_layer.models.pipeline_version import PipelineVersion


@pytest.fixture
def test_settings() -> Settings:
    """Test settings with safe defaults for local testing.
    
    Override specific settings in individual tests as needed:
        def test_something(test_settings):
            test_settings.OLLAMA_BASE_URL = "http://custom:11434"
    """
    return Settings(
        # === Application ===
        APP_NAME="LLM Inference Layer (Test)",
        APP_VERSION="0.1.0",
        DEBUG=True,
        LOG_LEVEL="DEBUG",
        ENVIRONMENT="development",
        
        # === Ollama ===
        OLLAMA_BASE_URL="http://localhost:11434",
        OLLAMA_MODEL="qwen2.5:7b",
        OLLAMA_TIMEOUT=60,
        FALLBACK_MODELS=[],
        
        # === Redis ===
        REDIS_URL="redis://localhost:6379/0",
        REDIS_MAX_CONNECTIONS=10,
        
        # === Database ===
        DATABASE_URL="sqlite+aiosqlite:///:memory:",  # In-memory for tests
        
        # === Validation ===
        JSON_SCHEMA_PATH="config/schema/email_triage_v2.json",
        PROMPT_TEMPLATES_DIR="config/prompts",
        
        # === Feature Flags ===
        ENABLE_ASYNC_API=True,
        ENABLE_BATCH_API=True,
        PROMETHEUS_ENABLED=False,  # Disable metrics in tests unless explicitly needed
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_email_data(fixtures_dir: Path) -> Dict[str, Any]:
    """Load sample email fixture as dict.
    
    Returns raw dict suitable for EmailDocument(**sample_email_data).
    """
    with open(fixtures_dir / "sample_email.json") as f:
        return json.load(f)


@pytest.fixture
def sample_candidates_data(fixtures_dir: Path) -> list[Dict[str, Any]]:
    """Load sample candidates fixture as list of dicts.
    
    Returns raw list suitable for [CandidateKeyword(**c) for c in sample_candidates_data].
    """
    with open(fixtures_dir / "sample_candidates.json") as f:
        return json.load(f)


@pytest.fixture
def sample_email_doc(sample_email_data: Dict[str, Any]) -> EmailDocument:
    """Parsed EmailDocument instance from sample fixture."""
    return EmailDocument(**sample_email_data)


@pytest.fixture
def sample_candidates(sample_candidates_data: list[Dict[str, Any]]) -> list[CandidateKeyword]:
    """Parsed list of CandidateKeyword instances from sample fixture."""
    return [CandidateKeyword(**c) for c in sample_candidates_data]


@pytest.fixture
def sample_triage_request(
    sample_email_doc: EmailDocument,
    sample_candidates: list[CandidateKeyword]
) -> TriageRequest:
    """Complete TriageRequest with sample email and candidates."""
    return TriageRequest(
        email=sample_email_doc,
        candidate_keywords=sample_candidates,
        dictionary_version=1,
        config_overrides=None,
    )


@pytest.fixture
def create_test_email_doc():
    """Factory fixture to create EmailDocument with custom body text.
    
    Usage:
        def test_something(create_test_email_doc):
            email = create_test_email_doc(body_text="Custom email text")
    """
    def _create(
        body_text: str = "Test email body",
        uid: str = "test_uid_123",
        subject: str = "Test Subject",
    ) -> EmailDocument:
        return EmailDocument(
            uid=uid,
            mailbox="INBOX",
            message_id=f"<{uid}@example.com>",
            fetched_at=datetime.now(),
            size=len(body_text),
            from_addr_redacted="sender@example.com",
            to_addrs_redacted=["recipient@example.com"],
            subject_canonical=subject,
            date_parsed="Thu, 1 Jan 2026 12:00:00 +0000",
            headers_canonical={},
            body_text_canonical=body_text,
            body_original_hash="test_hash_abc123",
            pii_entities=[],
            removed_sections=[],
            pipeline_version=InputPipelineVersion(
                parser_version="1.0",
                canonicalization_version="1.0",
                ner_model_version="1.0",
                pii_redaction_version="1.0",
            ),
            processing_timestamp=datetime.now(),
            processing_duration_ms=100,
        )
    
    return _create


@pytest.fixture
def create_test_candidate():
    """Factory fixture to create CandidateKeyword with custom values.
    
    Usage:
        def test_something(create_test_candidate):
            candidate = create_test_candidate(term="fattura", lemma="fattura")
    """
    def _create(
        candidate_id: str = "hash_test_001",
        term: str = "test",
        lemma: str = "test",
        count: int = 1,
        source: str = "body",
        score: float = 0.5,
    ) -> CandidateKeyword:
        return CandidateKeyword(
            candidate_id=candidate_id,
            term=term,
            lemma=lemma,
            count=count,
            source=source,
            score=score,
        )
    
    return _create


@pytest.fixture
def pipeline_version() -> PipelineVersion:
    """Standard PipelineVersion for tests."""
    return PipelineVersion(
        dictionary_version=1,
        inference_layer_version="0.1.0",
        schema_version="email_triage_v2",
        model_version="qwen2.5:7b",
        pii_redaction_version="none",
        prompt_templates_version="1.0",
    )


@pytest.fixture
def valid_llm_response_data(fixtures_dir: Path) -> Dict[str, Any]:
    """Load valid LLM response fixture as dict."""
    with open(fixtures_dir / "valid_llm_response.json") as f:
        return json.load(f)
