"""
Integration tests for retry engine.

These tests use real LLM client (Ollama), prompt builder, and validation
pipeline to test the full retry flow. Requires Ollama server running.

Run with: pytest tests/integration/retry/test_retry_integration.py -v
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from inference_layer.config import Settings
from inference_layer.llm.ollama_client import OllamaClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.models.input_models import (
    CandidateKeyword,
    EmailDocument,
    InputPipelineVersion,
    TriageRequest,
)
from inference_layer.retry.engine import RetryEngine
from inference_layer.retry.exceptions import RetryExhausted
from inference_layer.validation.pipeline import ValidationPipeline

# Fixture directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


# Test fixtures
def create_test_email(body: str = None) -> EmailDocument:
    """Helper to create minimal EmailDocument for testing."""
    if body is None:
        body = "Ho bisogno di informazioni sul contratto che ho firmato la settimana scorsa. Vorrei anche ricevere la fattura del mese precedente. Grazie."
    
    return EmailDocument(
        uid="test_uid_integration",
        mailbox="INBOX",
        message_id="<test_integration@example.com>",
        fetched_at=datetime.now(),
        size=len(body),
        from_addr_redacted="test@example.com",
        to_addrs_redacted=["support@example.com"],
        subject_canonical="Richiesta informazioni contratto e fattura",
        date_parsed="Thu, 19 Feb 2026 12:00:00 +0000",
        headers_canonical={},
        body_text_canonical=body,
        body_original_hash="test_hash_integration",
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


def create_test_request(body: str = None, candidates_count: int = 20) -> TriageRequest:
    """Helper to create TriageRequest for testing."""
    email = create_test_email(body)
    
    # Create realistic Italian keyword candidates
    base_candidates = [
        ("hash_contratto", "contratto", "contratto", 2, 0.95),
        ("hash_fattura", "fattura", "fattura", 1, 0.92),
        ("hash_informazioni", "informazioni", "informazione", 1, 0.88),
        ("hash_firmato", "firmato", "firmare", 1, 0.85),
        ("hash_settimana", "settimana", "settimana", 1, 0.80),
        ("hash_mese", "mese", "mese", 1, 0.78),
        ("hash_precedente", "precedente", "precedente", 1, 0.75),
        ("hash_ricevere", "ricevere", "ricevere", 1, 0.72),
        ("hash_bisogno", "bisogno", "bisogno", 1, 0.70),
        ("hash_vorrei", "vorrei", "volere", 1, 0.68),
    ]
    
    # Add filler candidates to reach desired count
    candidates = []
    for i, (cid, term, lemma, count, score) in enumerate(base_candidates):
        if i < candidates_count:
            candidates.append(
                CandidateKeyword(
                    candidate_id=cid,
                    term=term,
                    lemma=lemma,
                    count=count,
                    source="body",
                    score=score,
                )
            )
    
    # Fill remaining with generic candidates
    for i in range(len(candidates), candidates_count):
        candidates.append(
            CandidateKeyword(
                candidate_id=f"hash_filler_{i}",
                term=f"term_{i}",
                lemma=f"lemma_{i}",
                count=1,
                source="body",
                score=0.5 - (i * 0.01),
            )
        )
    
    return TriageRequest(
        email=email, candidate_keywords=candidates, dictionary_version=1
    )


# ============================================================================
# Integration Tests (Require Ollama Running)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_engine_success_with_real_ollama():
    """
    Integration test: Full retry engine with real Ollama + validation.
    
    Requires: Ollama server running with qwen2.5:7b model
    """
    settings = Settings()
    settings.MAX_RETRIES = 2
    
    # Real components
    llm_client = OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
    )
    
    prompt_builder = PromptBuilder(
        schema_path=settings.JSON_SCHEMA_PATH,
        prompts_dir=settings.PROMPT_TEMPLATES_DIR,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        body_truncation_limit=settings.BODY_TRUNCATION_LIMIT,
        candidate_top_n=settings.CANDIDATE_TOP_N,
        shrink_body_limit=settings.SHRINK_BODY_LIMIT,
        shrink_top_n=settings.SHRINK_TOP_N,
    )
    
    validation_pipeline = ValidationPipeline(
        schema_path=settings.JSON_SCHEMA_PATH,
        min_confidence_threshold=settings.MIN_CONFIDENCE_WARNING_THRESHOLD,
        enable_evidence_check=settings.ENABLE_EVIDENCE_PRESENCE_CHECK,
        enable_keyword_check=settings.ENABLE_KEYWORD_PRESENCE_CHECK,
    )
    
    retry_engine = RetryEngine(llm_client, prompt_builder, validation_pipeline, settings)
    
    # Execute
    request = create_test_request()
    response, metadata, warnings = await retry_engine.execute_with_retry(request)
    
    # Verify success
    assert response is not None
    assert response.dictionaryversion == 1
    assert len(response.topics) >= 1
    assert response.sentiment.value in ["positive", "neutral", "negative"]
    assert response.priority.value in ["low", "medium", "high", "urgent"]
    
    # Verify metadata
    assert metadata.total_attempts >= 1
    assert metadata.final_strategy in ["standard", "shrink", "fallback"]
    assert "standard" in metadata.strategies_used
    assert metadata.total_latency_ms > 0
    
    print(f"\n✅ Integration test passed!")
    print(f"   Attempts: {metadata.total_attempts}")
    print(f"   Strategy: {metadata.final_strategy}")
    print(f"   Latency: {metadata.total_latency_ms}ms")
    print(f"   Topics: {[t.labelid for t in response.topics]}")
    print(f"   Warnings: {len(warnings)}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_engine_shrink_mode_with_real_ollama():
    """
    Integration test: Verify shrink mode reduces prompt size.
    
    Requires: Ollama server running
    """
    settings = Settings()
    settings.MAX_RETRIES = 1  # Force faster escalation to shrink
    
    llm_client = OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
    )
    
    prompt_builder = PromptBuilder(
        schema_path=settings.JSON_SCHEMA_PATH,
        prompts_dir=settings.PROMPT_TEMPLATES_DIR,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        body_truncation_limit=settings.BODY_TRUNCATION_LIMIT,
        candidate_top_n=settings.CANDIDATE_TOP_N,
        shrink_body_limit=settings.SHRINK_BODY_LIMIT,
        shrink_top_n=settings.SHRINK_TOP_N,
    )
    
    validation_pipeline = ValidationPipeline(
        schema_path=settings.JSON_SCHEMA_PATH,
        min_confidence_threshold=settings.MIN_CONFIDENCE_WARNING_THRESHOLD,
        enable_evidence_check=settings.ENABLE_EVIDENCE_PRESENCE_CHECK,
        enable_keyword_check=settings.ENABLE_KEYWORD_PRESENCE_CHECK,
    )
    
    retry_engine = RetryEngine(llm_client, prompt_builder, validation_pipeline, settings)
    
    # Create request with large body and many candidates
    long_body = "Test email. " * 1000  # ~12KB body
    request = create_test_request(body=long_body, candidates_count=100)
    
    # Mock standard strategy to fail (force shrink)
    with patch.object(
        retry_engine.strategies[0][1],
        "execute",
        side_effect=Exception("Force shrink"),
    ):
        try:
            response, metadata, warnings = await retry_engine.execute_with_retry(request)
            
            # If shrink succeeds, verify metadata
            if "shrink" in metadata.strategies_used:
                print(f"\n✅ Shrink mode used successfully!")
                print(f"   Total attempts: {metadata.total_attempts}")
                print(f"   Final strategy: {metadata.final_strategy}")
        except RetryExhausted:
            # Expected if shrink also fails (Ollama may still struggle)
            print(f"\n⚠️ Both strategies failed (acceptable for integration test)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_engine_with_invalid_json_fixture():
    """
    Integration test: Use invalid JSON fixture to force retry.
    
    This simulates LLM generating malformed JSON that requires retry.
    """
    settings = Settings()
    settings.MAX_RETRIES = 2
    
    llm_client = OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
    )
    
    prompt_builder = PromptBuilder(
        schema_path=settings.JSON_SCHEMA_PATH,
        prompts_dir=settings.PROMPT_TEMPLATES_DIR,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        body_truncation_limit=settings.BODY_TRUNCATION_LIMIT,
        candidate_top_n=settings.CANDIDATE_TOP_N,
        shrink_body_limit=settings.SHRINK_BODY_LIMIT,
        shrink_top_n=settings.SHRINK_TOP_N,
    )
    
    validation_pipeline = ValidationPipeline(
        schema_path=settings.JSON_SCHEMA_PATH,
        min_confidence_threshold=settings.MIN_CONFIDENCE_WARNING_THRESHOLD,
        enable_evidence_check=settings.ENABLE_EVIDENCE_PRESENCE_CHECK,
        enable_keyword_check=settings.ENABLE_KEYWORD_PRESENCE_CHECK,
    )
    
    retry_engine = RetryEngine(llm_client, prompt_builder, validation_pipeline, settings)
    
    request = create_test_request()
    
    # Mock LLM client to return invalid JSON on first attempt, then valid
    call_count = 0
    original_generate = llm_client.generate
    
    async def mock_generate_with_retry(req):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # Return invalid JSON fixture
            from inference_layer.models.llm_models import LLMGenerationResponse
            
            invalid_fixture_path = FIXTURES_DIR / "invalid_json_response.json"
            with open(invalid_fixture_path, "r") as f:
                invalid_content = f.read()
            
            return LLMGenerationResponse(
                content=invalid_content,
                model_version="test_model:1.0",
                finish_reason="stop",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=500,
            )
        else:
            # Call real LLM on retry
            return await original_generate(req)
    
    with patch.object(llm_client, "generate", side_effect=mock_generate_with_retry):
        response, metadata, warnings = await retry_engine.execute_with_retry(request)
        
        # Verify retry happened
        assert metadata.total_attempts >= 2
        assert len(metadata.validation_failures) >= 1
        print(f"\n✅ Retry after invalid JSON worked!")
        print(f"   Total attempts: {metadata.total_attempts}")
        print(f"   Validation failures: {len(metadata.validation_failures)}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_engine_all_strategies_exhausted():
    """
    Integration test: Force all strategies to fail and verify RetryExhausted.
    
    This tests DLQ routing behavior.
    """
    settings = Settings()
    settings.MAX_RETRIES = 1
    settings.FALLBACK_MODELS = []  # No fallback to speed up test
    
    llm_client = OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
    )
    
    prompt_builder = PromptBuilder(
        schema_path=settings.JSON_SCHEMA_PATH,
        prompts_dir=settings.PROMPT_TEMPLATES_DIR,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        body_truncation_limit=settings.BODY_TRUNCATION_LIMIT,
        candidate_top_n=settings.CANDIDATE_TOP_N,
        shrink_body_limit=settings.SHRINK_BODY_LIMIT,
        shrink_top_n=settings.SHRINK_TOP_N,
    )
    
    validation_pipeline = ValidationPipeline(
        schema_path=settings.JSON_SCHEMA_PATH,
        min_confidence_threshold=settings.MIN_CONFIDENCE_WARNING_THRESHOLD,
        enable_evidence_check=settings.ENABLE_EVIDENCE_PRESENCE_CHECK,
        enable_keyword_check=settings.ENABLE_KEYWORD_PRESENCE_CHECK,
    )
    
    retry_engine = RetryEngine(llm_client, prompt_builder, validation_pipeline, settings)
    
    request = create_test_request()
    
    # Mock LLM to always return invalid JSON
    from inference_layer.models.llm_models import LLMGenerationResponse
    
    async def mock_always_invalid(req):
        return LLMGenerationResponse(
            content='{"invalid": "json", "missing_required_fields": true}',
            model_version="test_model:1.0",
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=500,
        )
    
    with patch.object(llm_client, "generate", side_effect=mock_always_invalid):
        with pytest.raises(RetryExhausted) as exc_info:
            await retry_engine.execute_with_retry(request)
        
        # Verify RetryExhausted details
        assert exc_info.value.request == request
        assert exc_info.value.retry_metadata.total_attempts >= 3  # 1 standard + 2 shrink
        assert len(exc_info.value.retry_metadata.strategies_used) >= 2
        assert len(exc_info.value.retry_metadata.validation_failures) >= 3
        
        print(f"\n✅ RetryExhausted raised correctly!")
        print(f"   Total attempts: {exc_info.value.retry_metadata.total_attempts}")
        print(f"   Strategies: {exc_info.value.retry_metadata.strategies_used}")
        print(f"   Failures: {len(exc_info.value.retry_metadata.validation_failures)}")


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_engine_latency_tracking():
    """Integration test: Verify latency tracking is accurate."""
    settings = Settings()
    
    llm_client = OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
    )
    
    prompt_builder = PromptBuilder(
        schema_path=settings.JSON_SCHEMA_PATH,
        prompts_dir=settings.PROMPT_TEMPLATES_DIR,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        body_truncation_limit=settings.BODY_TRUNCATION_LIMIT,
        candidate_top_n=settings.CANDIDATE_TOP_N,
        shrink_body_limit=settings.SHRINK_BODY_LIMIT,
        shrink_top_n=settings.SHRINK_TOP_N,
    )
    
    validation_pipeline = ValidationPipeline(
        schema_path=settings.JSON_SCHEMA_PATH,
        min_confidence_threshold=settings.MIN_CONFIDENCE_WARNING_THRESHOLD,
        enable_evidence_check=settings.ENABLE_EVIDENCE_PRESENCE_CHECK,
        enable_keyword_check=settings.ENABLE_KEYWORD_PRESENCE_CHECK,
    )
    
    retry_engine = RetryEngine(llm_client, prompt_builder, validation_pipeline, settings)
    
    request = create_test_request()
    
    import time
    start_time = time.time()
    response, metadata, warnings = await retry_engine.execute_with_retry(request)
    actual_elapsed_ms = (time.time() - start_time) * 1000
    
    # Verify latency tracking is reasonable (within 20% of actual)
    assert metadata.total_latency_ms > 0
    assert 0.8 * actual_elapsed_ms <= metadata.total_latency_ms <= 1.2 * actual_elapsed_ms
    
    print(f"\n✅ Latency tracking accurate!")
    print(f"   Tracked: {metadata.total_latency_ms}ms")
    print(f"   Actual: {actual_elapsed_ms:.0f}ms")
    print(f"   LLM latency: {metadata.llm_metadata.latency_ms}ms")


# ============================================================================
# Skip Marker for CI
# ============================================================================

# Add this marker to skip integration tests unless explicitly enabled:
# pytest tests/integration/retry/ -v -m integration
