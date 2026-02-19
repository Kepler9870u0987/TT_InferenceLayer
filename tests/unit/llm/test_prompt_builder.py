"""Unit tests for PromptBuilder."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.models.input_models import (
    TriageRequest, EmailDocument, CandidateKeyword, PiiEntity,
    InputPipelineVersion
)


@pytest.fixture
def sample_email_document():
    """Sample email document for testing."""
    return EmailDocument(
        uid="test-123",
        uidvalidity="12345",
        mailbox="inbox",
        message_id="<test@example.com>",
        fetched_at=datetime(2026, 2, 19, 10, 0, 0),
        size=1024,
        from_addr_redacted="customer@example.com",
        to_addrs_redacted=["support@company.com"],
        subject_canonical="Richiesta informazioni contratto",
        date_parsed="2026-02-18T15:30:00Z",
        headers_canonical={"Subject": "Richiesta informazioni contratto"},
        body_text_canonical="Buongiorno, vorrei ricevere informazioni sul contratto. Cordiali saluti.",
        body_html_canonical="",
        body_original_hash="abc123hash",
        pii_entities=[
            PiiEntity(
                type="EMAIL", original_hash="abc123", redacted="customer@example.com",
                span_start=50, span_end=70, confidence=0.95, detection_method="regex"
            )
        ],
        removed_sections=[],
        pipeline_version=InputPipelineVersion(
            parser_version="1.0.0",
            canonicalization_version="1.0.0",
            ner_model_version="1.0.0",
            pii_redaction_version="1.0.0"
        ),
        processing_timestamp=datetime(2026, 2, 19, 10, 0, 0),
        processing_duration_ms=100
    )


@pytest.fixture
def sample_candidates():
    """Sample candidate keywords."""
    return [
        CandidateKeyword(
            candidate_id="kw_001",
            term="contratto",
            lemma="contratto",
            count=3,
            source="body",
            score=8.5
        ),
        CandidateKeyword(
            candidate_id="kw_002",
            term="informazioni",
            lemma="informare",
            count=2,
            source="body",
            score=7.2
        ),
    ]


@pytest.fixture
def triage_request(sample_email_document, sample_candidates):
    """Sample triage request."""
    return TriageRequest(
        email=sample_email_document,
        candidate_keywords=sample_candidates,
        dictionary_version=1,
        config_overrides=None
    )


@pytest.fixture
def prompt_builder(tmp_path):
    """Create prompt builder with test templates."""
    # Create temporary templates
    templates_dir = tmp_path / "prompts"
    templates_dir.mkdir()
    
    # System prompt
    system_prompt = """You are an AI assistant for email classification.
Follow the JSON schema strictly."""
    (templates_dir / "system_prompt.txt").write_text(system_prompt, encoding="utf-8")
    
    # User prompt template
    user_template = """DICTIONARY VERSION: {{ dictionary_version }}

EMAIL TO ANALYZE:
Subject: {{ subject }}
From: {{ from_addr }}
{{ body }}

ALLOWED TOPICS:
{% for topic in allowed_topics -%}
- {{ topic }}
{% endfor %}

CANDIDATE KEYWORDS:
{% for candidate in candidate_keywords -%}
- ID: {{ candidate.candidate_id }} | Term: "{{ candidate.term }}"
{% endfor %}
"""
    (templates_dir / "user_prompt_template.txt").write_text(user_template, encoding="utf-8")
    
    # Create minimal JSON schema
    schema_path = tmp_path / "schema.json"
    schema = {"type": "object", "properties": {"dictionaryversion": {"type": "integer"}}}
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    
    return PromptBuilder(
        templates_dir=templates_dir,
        schema_path=schema_path,
        body_truncation_limit=100,
        shrink_body_limit=50,
        candidate_top_n=10,
        shrink_top_n=5,
        redact_for_llm=False,
        default_model="test-model",
        default_temperature=0.1,
        default_max_tokens=100
    )


class TestPromptBuilder:
    """Test PromptBuilder functionality."""
    
    def test_build_system_prompt(self, prompt_builder):
        """Should render system prompt."""
        result = prompt_builder.build_system_prompt()
        assert "AI assistant" in result
        assert "JSON schema" in result
    
    def test_build_user_prompt_normal_mode(self, prompt_builder, triage_request):
        """Should build user prompt in normal mode."""
        user_prompt, metadata = prompt_builder.build_user_prompt(
            triage_request, shrink_mode=False
        )
        
        # Check content
        assert "DICTIONARY VERSION: 1" in user_prompt
        assert "Richiesta informazioni contratto" in user_prompt
        assert "customer@example.com" in user_prompt
        assert "kw_001" in user_prompt
        assert "contratto" in user_prompt
        
        # Check metadata
        assert metadata["shrink_mode"] is False
        assert metadata["candidates_count"] == 2
        assert not metadata["truncation_applied"]  # Body is short
    
    def test_build_user_prompt_shrink_mode(self, prompt_builder, triage_request):
        """Should use shrink limits in shrink mode."""
        user_prompt, metadata = prompt_builder.build_user_prompt(
            triage_request, shrink_mode=True
        )
        
        assert metadata["shrink_mode"] is True
        # Body should be truncated to 50 chars in shrink mode
        assert metadata["truncated_body_length"] <= 50
    
    def test_build_user_prompt_truncates_long_body(self, prompt_builder, triage_request):
        """Should truncate body exceeding limit."""
        # Make body very long
        triage_request.email.body_text_canonical = "A" * 200 + ". " + "B" * 200
        
        user_prompt, metadata = prompt_builder.build_user_prompt(
            triage_request, shrink_mode=False
        )
        
        assert metadata["truncation_applied"]
        assert metadata["truncated_body_length"] <= 100
    
    def test_build_full_request(self, prompt_builder, triage_request):
        """Should build complete LLMGenerationRequest."""
        llm_request, metadata = prompt_builder.build_full_request(triage_request)
        
        # Check LLMGenerationRequest fields
        assert llm_request.model == "test-model"
        assert llm_request.temperature == 0.1
        assert llm_request.max_tokens == 100
        assert llm_request.stream is False
        assert llm_request.format_schema is not None
        
        # Check prompt contains both system and user
        assert "AI assistant" in llm_request.prompt
        assert "DICTIONARY VERSION" in llm_request.prompt
        
        # Check metadata
        assert metadata["model"] == "test-model"
        assert metadata["schema_included"]
        assert metadata["full_prompt_length"] > 0
    
    def test_pii_redaction_when_enabled(self, prompt_builder, triage_request):
        """Should apply PII redaction when enabled."""
        prompt_builder.redact_for_llm = True
        
        user_prompt, metadata = prompt_builder.build_user_prompt(triage_request)
        
        assert metadata["pii_redaction_applied"]
        # Email in body should be redacted (if span is correct)
        # This test might need adjustment based on actual PII span positions
    
    def test_top_n_candidate_selection(self, prompt_builder, triage_request):
        """Should limit candidates to top-N."""
        # Add many candidates
        for i in range(20):
            triage_request.candidate_keywords.append(
                CandidateKeyword(
                    candidate_id=f"kw_{i:03d}",
                    term=f"term{i}",
                    lemma=f"lemma{i}",
                    count=1,
                    source="body",
                    score=float(i)
                )
            )
        
        user_prompt, metadata = prompt_builder.build_user_prompt(
            triage_request, shrink_mode=False
        )
        
        # Should limit to top 10 (normal mode)
        assert metadata["candidates_count"] == 10
        
        # Shrink mode should limit to 5
        user_prompt_shrink, metadata_shrink = prompt_builder.build_user_prompt(
            triage_request, shrink_mode=True
        )
        assert metadata_shrink["candidates_count"] == 5
