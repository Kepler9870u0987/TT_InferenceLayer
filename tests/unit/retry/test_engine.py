"""
Unit tests for RetryEngine.

Tests the orchestration of retry strategies and metadata tracking.
"""

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
from inference_layer.models.llm_models import LLMGenerationResponse
from inference_layer.models.output_models import (
    EmailTriageResponse,
    EvidenceItem,
    KeywordInText,
    PriorityResult,
    SentimentResult,
    TopicResult,
)
from inference_layer.retry.engine import RetryEngine
from inference_layer.retry.exceptions import RetryExhausted
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
        usage_tokens=150,
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=500,
    )


def create_mock_validated_response() -> EmailTriageResponse:
    """Create a mock validated EmailTriageResponse."""
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


def create_mock_prompt_builder() -> MagicMock:
    """Create a properly configured mock PromptBuilder."""
    mock_builder = MagicMock(spec=PromptBuilder)
    mock_builder.default_temperature = 0.1
    mock_builder.default_max_tokens = 2048
    mock_builder.default_model = "test_model"
    mock_builder.body_truncation_limit = 8000
    mock_builder.json_schema = {}
    return mock_builder


# ============================================================================
# RetryEngine Initialization Tests
# ============================================================================


def test_retry_engine_initialization():
    """Test RetryEngine initializes with correct strategies."""
    settings = Settings()
    settings.MAX_RETRIES = 3
    settings.FALLBACK_MODELS = ["model_a", "model_b"]

    mock_client = MagicMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = MagicMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Verify 3 strategies initialized
    assert len(engine.strategies) == 3
    assert engine.strategies[0][0] == "standard"
    assert engine.strategies[1][0] == "shrink"
    assert engine.strategies[2][0] == "fallback"

    # Verify max attempts per strategy
    assert engine.strategies[0][2] == 3  # standard: MAX_RETRIES
    assert engine.strategies[1][2] == 2  # shrink: hardcoded 2
    assert engine.strategies[2][2] == 2  # fallback: len(FALLBACK_MODELS)


# ============================================================================
# Success Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_retry_engine_success_first_attempt():
    """Test RetryEngine succeeds on first attempt (standard strategy)."""
    settings = Settings()
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_builder.default_temperature = 0.1
    mock_builder.default_max_tokens = 2048
    mock_builder.default_model = "test_model"
    mock_builder.body_truncation_limit = 8000
    mock_builder.json_schema = {}
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock strategy execute to succeed immediately
    with patch.object(
        engine.strategies[0][1],
        "execute",
        new=AsyncMock(
            return_value=(
                create_mock_validated_response(),
                create_mock_llm_response(),
                [],
            )
        ),
    ):
        request = create_test_request()
        response, metadata, warnings = await engine.execute_with_retry(request)

        # Verify success
        assert response is not None
        assert metadata.total_attempts == 1
        assert metadata.final_strategy == "standard"
        assert metadata.strategies_used == ["standard"]
        assert len(metadata.validation_failures) == 0
        assert warnings == []


@pytest.mark.asyncio
async def test_retry_engine_success_second_attempt():
    """Test RetryEngine succeeds on second attempt after validation failure."""
    settings = Settings()
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock strategy to fail once, then succeed
    call_count = 0

    async def mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise JSONParseError("Invalid JSON", "bad json content")
        return (create_mock_validated_response(), create_mock_llm_response(), [])

    with patch.object(engine.strategies[0][1], "execute", new=mock_execute):
        request = create_test_request()
        response, metadata, warnings = await engine.execute_with_retry(request)

        # Verify success on 2nd attempt
        assert response is not None
        assert metadata.total_attempts == 2
        assert metadata.final_strategy == "standard"
        assert len(metadata.validation_failures) == 1
        assert metadata.validation_failures[0]["content_snippet"] == "bad json"


@pytest.mark.asyncio
async def test_retry_engine_escalates_to_shrink():
    """Test RetryEngine escalates to shrink strategy after standard exhausted."""
    settings = Settings()
    settings.MAX_RETRIES = 2
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock standard strategy to always fail
    async def standard_fail(*args, **kwargs):
        raise SchemaValidationError("Schema error", {"validation_errors": []})

    # Mock shrink strategy to succeed
    async def shrink_succeed(*args, **kwargs):
        return (create_mock_validated_response(), create_mock_llm_response(), [])

    with patch.object(
        engine.strategies[0][1], "execute", new=standard_fail
    ), patch.object(engine.strategies[1][1], "execute", new=shrink_succeed):
        request = create_test_request()
        response, metadata, warnings = await engine.execute_with_retry(request)

        # Verify escalation to shrink
        assert response is not None
        assert metadata.final_strategy == "shrink"
        assert metadata.strategies_used == ["standard", "shrink"]
        assert metadata.total_attempts == 3  # 2 standard + 1 shrink
        assert len(metadata.validation_failures) == 2  # 2 failures from standard


@pytest.mark.asyncio
async def test_retry_engine_escalates_to_fallback():
    """Test RetryEngine escalates to fallback after standard and shrink exhausted."""
    settings = Settings()
    settings.MAX_RETRIES = 2
    settings.FALLBACK_MODELS = ["fallback_model"]
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock standard and shrink to always fail
    async def always_fail(*args, **kwargs):
        raise BusinessRuleViolation("Invalid candidateid", {})

    # Mock fallback to succeed
    async def fallback_succeed(*args, **kwargs):
        return (create_mock_validated_response(), create_mock_llm_response(), [])

    with patch.object(
        engine.strategies[0][1], "execute", new=always_fail
    ), patch.object(engine.strategies[1][1], "execute", new=always_fail), patch.object(
        engine.strategies[2][1], "execute", new=fallback_succeed
    ):
        request = create_test_request()
        response, metadata, warnings = await engine.execute_with_retry(request)

        # Verify escalation to fallback
        assert response is not None
        assert metadata.final_strategy == "fallback"
        assert metadata.strategies_used == ["standard", "shrink", "fallback"]
        assert metadata.total_attempts == 5  # 2 standard + 2 shrink + 1 fallback


# ============================================================================
# Failure Scenarios (RetryExhausted)
# ============================================================================


@pytest.mark.asyncio
async def test_retry_engine_exhausted_all_strategies():
    """Test RetryEngine raises RetryExhausted when all strategies fail."""
    settings = Settings()
    settings.MAX_RETRIES = 2
    settings.FALLBACK_MODELS = ["fallback_model"]
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock all strategies to always fail
    async def always_fail(*args, **kwargs):
        raise BusinessRuleViolation("Invalid candidateid", {"rule_name": "test"})

    with patch.object(
        engine.strategies[0][1], "execute", new=always_fail
    ), patch.object(engine.strategies[1][1], "execute", new=always_fail), patch.object(
        engine.strategies[2][1], "execute", new=always_fail
    ):
        request = create_test_request()

        # Execute - should raise RetryExhausted
        with pytest.raises(RetryExhausted) as exc_info:
            await engine.execute_with_retry(request)

        # Verify RetryExhausted details
        assert exc_info.value.request == request
        assert exc_info.value.retry_metadata.total_attempts == 5  # 2+2+1
        assert exc_info.value.retry_metadata.strategies_used == [
            "standard",
            "shrink",
            "fallback",
        ]
        assert len(exc_info.value.retry_metadata.validation_failures) == 5
        assert isinstance(exc_info.value.last_error, BusinessRuleViolation)


@pytest.mark.asyncio
async def test_retry_engine_exhausted_metadata():
    """Test RetryExhausted contains complete metadata for DLQ."""
    settings = Settings()
    settings.MAX_RETRIES = 1
    settings.FALLBACK_MODELS = []  # No fallback models
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock strategies to fail with different errors
    standard_call_count = 0

    async def standard_fail(*args, **kwargs):
        nonlocal standard_call_count
        standard_call_count += 1
        raise JSONParseError(f"Parse error {standard_call_count}", "bad content")

    async def shrink_fail(*args, **kwargs):
        raise SchemaValidationError("Schema error", {})

    with patch.object(
        engine.strategies[0][1], "execute", new=standard_fail
    ), patch.object(engine.strategies[1][1], "execute", new=shrink_fail):
        request = create_test_request()

        with pytest.raises(RetryExhausted) as exc_info:
            await engine.execute_with_retry(request)

        metadata = exc_info.value.retry_metadata

        # Verify complete metadata
        assert metadata.total_attempts == 3  # 1 standard + 2 shrink
        assert metadata.strategies_used == ["standard", "shrink"]
        assert metadata.final_strategy == "shrink"
        assert metadata.total_latency_ms > 0
        assert len(metadata.validation_failures) == 3


# ============================================================================
# Metadata Tracking Tests
# ============================================================================


@pytest.mark.asyncio
async def test_retry_engine_tracks_warnings():
    """Test RetryEngine preserves warnings from Stage 4."""
    settings = Settings()
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock strategy to return warnings
    warnings = ["Low confidence: 0.15", "Duplicate topic: CONTRATTO"]

    with patch.object(
        engine.strategies[0][1],
        "execute",
        new=AsyncMock(
            return_value=(
                create_mock_validated_response(),
                create_mock_llm_response(),
                warnings,
            )
        ),
    ):
        request = create_test_request()
        response, metadata, returned_warnings = await engine.execute_with_retry(
            request
        )

        # Verify warnings preserved
        assert returned_warnings == warnings


@pytest.mark.asyncio
async def test_retry_engine_tracks_latency():
    """Test RetryEngine tracks total latency across attempts."""
    settings = Settings()
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    with patch.object(
        engine.strategies[0][1],
        "execute",
        new=AsyncMock(
            return_value=(
                create_mock_validated_response(),
                create_mock_llm_response(),
                [],
            )
        ),
    ):
        request = create_test_request()
        response, metadata, warnings = await engine.execute_with_retry(request)

        # Verify latency tracked
        assert metadata.total_latency_ms > 0
        assert metadata.llm_metadata.latency_ms == 500  # From mock LLM response


@pytest.mark.asyncio
async def test_retry_engine_tracks_attempt_number():
    """Test RetryEngine tracks correct attempt number in metadata."""
    settings = Settings()
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Fail twice, succeed on third attempt
    call_count = 0

    async def mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise JSONParseError(f"Error {call_count}", "bad content")
        return (create_mock_validated_response(), create_mock_llm_response(), [])

    with patch.object(engine.strategies[0][1], "execute", new=mock_execute):
        request = create_test_request()
        response, metadata, warnings = await engine.execute_with_retry(request)

        # Verify attempt number
        assert metadata.total_attempts == 3
        assert metadata.llm_metadata.attempt_number == 3


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_retry_engine_no_fallback_models():
    """Test RetryEngine handles empty FALLBACK_MODELS list gracefully."""
    settings = Settings()
    settings.FALLBACK_MODELS = []
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Verify fallback strategy exists but has max_attempts=1 (since no models)
    assert engine.strategies[2][0] == "fallback"
    assert engine.strategies[2][2] == 1  # max_attempts


@pytest.mark.asyncio
async def test_retry_engine_preserves_error_context():
    """Test RetryEngine preserves error context in validation_failures."""
    settings = Settings()
    settings.MAX_RETRIES = 1
    mock_client = AsyncMock(spec=BaseLLMClient)
    mock_builder = create_mock_prompt_builder()
    mock_validator = AsyncMock(spec=ValidationPipeline)

    engine = RetryEngine(mock_client, mock_builder, mock_validator, settings)

    # Mock to fail with structured error
    async def fail_with_details(*args, **kwargs):
        raise BusinessRuleViolation(
            "Invalid candidateid",
            {
                "rule_name": "candidateid_exists",
                "invalid_value": "fake_id",
                "expected_values": ["hash_001", "hash_002"],
                "field_path": "topics[0].keywordsintext[0].candidateid",
            },
        )

    with patch.object(
        engine.strategies[0][1], "execute", new=fail_with_details
    ), patch.object(engine.strategies[1][1], "execute", new=fail_with_details):
        request = create_test_request()

        with pytest.raises(RetryExhausted) as exc_info:
            await engine.execute_with_retry(request)

        # Verify error details preserved in metadata
        failures = exc_info.value.retry_metadata.validation_failures
        assert len(failures) == 3  # 1 standard + 2 shrink
        assert failures[0]["rule_name"] == "candidateid_exists"
        assert failures[0]["invalid_value"] == "fake_id"
        assert failures[0]["field_path"] == "topics[0].keywordsintext[0].candidateid"
