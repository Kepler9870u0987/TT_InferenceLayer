"""
Unit tests for retry strategies.

Tests StandardRetryStrategy, ShrinkRetryStrategy, and FallbackModelStrategy
with mocked dependencies (LLM client, validation pipeline).
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inference_layer.config import Settings
from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.models.input_models import (
    CandidateKeyword,
    EmailDocument,
    InputPipelineVersion,
    TriageRequest,
)
from inference_layer.models.llm_models import (
    LLMGenerationRequest,
    LLMGenerationResponse,
)
from inference_layer.models.output_models import EmailTriageResponse
from inference_layer.retry.strategies import (
    FallbackModelStrategy,
    ShrinkRetryStrategy,
    StandardRetryStrategy,
)
from inference_layer.validation.exceptions import (
    BusinessRuleViolation,
    JSONParseError,
    SchemaValidationError,
)
from inference_layer.validation.pipeline import ValidationPipeline


# Test fixtures
def create_test_email() -> EmailDocument:
    """Helper to create minimal EmailDocument for testing."""
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
        body_text_canonical="This is a test email body about contratto fattura.",
        body_original_hash="test_hash",
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


def create_test_request() -> TriageRequest:
    """Helper to create minimal TriageRequest for testing."""
    email = create_test_email()
    candidates = [
        CandidateKeyword(
            candidate_id="hash_001",
            term="contratto",
            lemma="contratto",
            count=1,
            source="body",
            score=0.9,
        ),
        CandidateKeyword(
            candidate_id="hash_002",
            term="fattura",
            lemma="fattura",
            count=1,
            source="body",
            score=0.8,
        ),
    ]
    return TriageRequest(
        email=email, candidate_keywords=candidates, dictionary_version=1
    )


def create_mock_llm_response() -> LLMGenerationResponse:
    """Create a mock LLM response."""
    return LLMGenerationResponse(
        content='{"dictionaryversion": 1, "sentiment": {"value": "neutral", "confidence": 0.8}, "priority": {"value": "medium", "confidence": 0.7, "signals": []}, "topics": [{"labelid": "CONTRATTO", "confidence": 0.9, "keywordsintext": [{"candidateid": "hash_001", "lemma": "contratto", "count": 1}], "evidence": [{"quote": "contratto"}]}]}',
        model_version="test_model:1.0",
        finish_reason="stop",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=500,
    )


def create_mock_validated_response() -> EmailTriageResponse:
    """Create a mock validated EmailTriageResponse."""
    from inference_layer.models.output_models import (
        EvidenceItem,
        KeywordInText,
        PriorityResult,
        SentimentResult,
        TopicResult,
    )

    return EmailTriageResponse(
        dictionaryversion=1,
        sentiment=SentimentResult(value="neutral", confidence=0.8),
        priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
        topics=[
            TopicResult(
                labelid="CONTRATTO",
                confidence=0.9,
                keywordsintext=[
                    KeywordInText(candidateid="hash_001", lemma="contratto", count=1)
                ],
                evidence=[EvidenceItem(quote="contratto")],
            )
        ],
    )


# ============================================================================
# StandardRetryStrategy Tests
# ============================================================================


@pytest.mark.asyncio
async def test_standard_retry_success_first_attempt():
    """Test StandardRetryStrategy succeeds on first attempt."""
    settings = Settings()
    strategy = StandardRetryStrategy(settings)

    # Mock dependencies
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "test_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {"candidates_count": 2})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()

    # Execute
    validated_response, llm_response, warnings = await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=None,
        attempt=1,
    )

    # Verify
    assert validated_response is not None
    assert llm_response is not None
    assert warnings == []
    mock_client.generate.assert_called_once()
    mock_validator.validate.assert_called_once()
    mock_builder.build_user_prompt.assert_called_once_with(request, shrink_mode=False)


@pytest.mark.asyncio
async def test_standard_retry_success_second_attempt():
    """Test StandardRetryStrategy succeeds on second attempt after backoff."""
    settings = Settings()
    strategy = StandardRetryStrategy(settings)

    # Mock dependencies
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "test_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()
    previous_error = JSONParseError("Invalid JSON", {"content_snippet": "bad json"})

    # Execute on attempt 2 (backoff should be applied)
    start_time = asyncio.get_event_loop().time()
    validated_response, llm_response, warnings = await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=previous_error,
        attempt=2,
    )
    elapsed_time = asyncio.get_event_loop().time() - start_time

    # Verify backoff applied (2^2 = 4 seconds)
    assert elapsed_time >= 4.0
    assert validated_response is not None


@pytest.mark.asyncio
async def test_standard_retry_validation_failure():
    """Test StandardRetryStrategy raises ValidationError on failure."""
    settings = Settings()
    strategy = StandardRetryStrategy(settings)

    # Mock dependencies
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "test_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        side_effect=BusinessRuleViolation(
            "Invalid candidateid",
            {
                "rule_name": "candidateid_exists",
                "invalid_value": "fake_id",
                "expected_values": ["hash_001", "hash_002"],
                "field_path": "topics[0].keywordsintext[0].candidateid",
            },
        )
    )

    request = create_test_request()

    # Execute - should raise ValidationError
    with pytest.raises(BusinessRuleViolation) as exc_info:
        await strategy.execute(
            request=request,
            client=mock_client,
            prompt_builder=mock_builder,
            validator=mock_validator,
            error=None,
            attempt=1,
        )

    assert "Invalid candidateid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_standard_retry_no_backoff_first_attempt():
    """Test StandardRetryStrategy skips backoff on first attempt."""
    settings = Settings()
    strategy = StandardRetryStrategy(settings)

    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "test_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()

    # Execute on attempt 1 (no backoff)
    start_time = asyncio.get_event_loop().time()
    await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=None,
        attempt=1,
    )
    elapsed_time = asyncio.get_event_loop().time() - start_time

    # Verify no significant delay (< 0.5 seconds tolerance for async overhead)
    assert elapsed_time < 0.5


# ============================================================================
# ShrinkRetryStrategy Tests
# ============================================================================


@pytest.mark.asyncio
async def test_shrink_retry_uses_shrink_mode():
    """Test ShrinkRetryStrategy uses shrink_mode=True."""
    settings = Settings()
    strategy = ShrinkRetryStrategy(settings)

    # Mock dependencies
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "test_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = (
        "User prompt (shrunk)",
        {"candidates_count": 25, "body_length": 2000, "shrink_mode": True},
    )
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()

    # Execute
    validated_response, llm_response, warnings = await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=None,
        attempt=1,
    )

    # Verify shrink_mode=True was called
    mock_builder.build_user_prompt.assert_called_once_with(request, shrink_mode=True)
    assert validated_response is not None


@pytest.mark.asyncio
async def test_shrink_retry_fewer_max_retries():
    """Test ShrinkRetryStrategy has fewer max retries (2 vs 3)."""
    settings = Settings()
    strategy = ShrinkRetryStrategy(settings)

    # Verify max_retries is 2 (not settings.MAX_RETRIES which is 3)
    assert strategy.max_retries == 2


# ============================================================================
# FallbackModelStrategy Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fallback_model_success():
    """Test FallbackModelStrategy switches to fallback model."""
    settings = Settings()
    fallback_models = ["llama3.1:8b", "mistral:7b"]
    strategy = FallbackModelStrategy(settings, fallback_models)

    # Mock dependencies
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "primary_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()

    # Execute
    validated_response, llm_response, warnings = await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=None,
        attempt=1,
    )

    # Verify fallback model was used in LLMGenerationRequest
    assert mock_client.generate.called
    generate_call_args = mock_client.generate.call_args[0][0]
    assert isinstance(generate_call_args, LLMGenerationRequest)
    assert generate_call_args.model == "llama3.1:8b"  # First fallback model


@pytest.mark.asyncio
async def test_fallback_model_cycles_through_models():
    """Test FallbackModelStrategy cycles through fallback models."""
    settings = Settings()
    fallback_models = ["model_a", "model_b", "model_c"]
    strategy = FallbackModelStrategy(settings, fallback_models)

    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "primary_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()

    # Execute 3 times to cycle through all models
    for expected_model in fallback_models:
        await strategy.execute(
            request=request,
            client=mock_client,
            prompt_builder=mock_builder,
            validator=mock_validator,
            error=None,
            attempt=1,
        )

        # Verify correct model was used
        generate_call_args = mock_client.generate.call_args[0][0]
        assert generate_call_args.model == expected_model


@pytest.mark.asyncio
async def test_fallback_model_no_models_configured():
    """Test FallbackModelStrategy raises when no fallback models configured."""
    settings = Settings()
    fallback_models = []  # Empty list
    strategy = FallbackModelStrategy(settings, fallback_models)

    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = MagicMock(spec=PromptBuilder)
    mock_validator = AsyncMock(spec=ValidationPipeline)

    request = create_test_request()
    previous_error = SchemaValidationError(
        "Schema validation failed", {"validation_errors": []}
    )

    # Execute - should raise ValueError
    with pytest.raises(ValueError, match="No fallback models configured"):
        await strategy.execute(
            request=request,
            client=mock_client,
            prompt_builder=mock_builder,
            validator=mock_validator,
            error=previous_error,
            attempt=1,
        )


@pytest.mark.asyncio
async def test_fallback_model_reraises_error_if_no_models():
    """Test FallbackModelStrategy re-raises previous error if no models."""
    settings = Settings()
    fallback_models = []
    strategy = FallbackModelStrategy(settings, fallback_models)

    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = MagicMock(spec=PromptBuilder)
    mock_validator = AsyncMock(spec=ValidationPipeline)

    request = create_test_request()
    previous_error = BusinessRuleViolation("Test error", {})

    # Execute - should re-raise previous ValidationError
    with pytest.raises(BusinessRuleViolation, match="Test error"):
        await strategy.execute(
            request=request,
            client=mock_client,
            prompt_builder=mock_builder,
            validator=mock_validator,
            error=previous_error,
            attempt=1,
        )


# ============================================================================
# Exponential Backoff Timing Tests
# ============================================================================


@pytest.mark.asyncio
async def test_exponential_backoff_timing():
    """Test exponential backoff timing across multiple attempts."""
    settings = Settings()
    settings.RETRY_BACKOFF_BASE = 2.0
    strategy = StandardRetryStrategy(settings)

    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_client.model = "test_model"
    mock_client.generate = AsyncMock(return_value=create_mock_llm_response())

    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.get_system_prompt.return_value = "System prompt"
    mock_builder.build_user_prompt.return_value = ("User prompt", {})
    mock_builder.temperature = 0.1
    mock_builder.max_tokens = 2048
    mock_builder.json_schema = {}

    mock_validator = AsyncMock(spec=ValidationPipeline)
    mock_validator.validate = AsyncMock(
        return_value=(create_mock_validated_response(), [])
    )

    request = create_test_request()
    error = JSONParseError("Test error", {})

    # Test backoff on attempt 2: 2^2 = 4s
    start_time = asyncio.get_event_loop().time()
    await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=error,
        attempt=2,
    )
    elapsed = asyncio.get_event_loop().time() - start_time
    assert 3.9 <= elapsed <= 4.5  # Allow 0.1s tolerance

    # Test backoff on attempt 3: 2^3 = 8s
    start_time = asyncio.get_event_loop().time()
    await strategy.execute(
        request=request,
        client=mock_client,
        prompt_builder=mock_builder,
        validator=mock_validator,
        error=error,
        attempt=3,
    )
    elapsed = asyncio.get_event_loop().time() - start_time
    assert 7.9 <= elapsed <= 8.5  # Allow 0.1s tolerance
