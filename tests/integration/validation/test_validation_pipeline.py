"""
Integration tests for Validation Pipeline.

Tests the full validation pipeline with real fixtures, exercising all stages
and verifiers together.
"""

import json
import pytest
from pathlib import Path

from inference_layer.config import Settings
from inference_layer.models.input_models import (
    EmailDocument,
    CandidateKeyword,
    TriageRequest,
    PiiEntity,
    RemovedSection,
)
from inference_layer.models.llm_models import LLMGenerationResponse, LLMMetadata
from inference_layer.validation import (
    ValidationPipeline,
    ValidationError,
    JSONParseError,
    SchemaValidationError,
    BusinessRuleViolation,
)


class TestValidationPipelineIntegration:
    """Integration tests for full validation pipeline."""
    
    @pytest.fixture
    def settings(self):
        """Create settings for validation pipeline."""
        return Settings()
    
    @pytest.fixture
    def pipeline(self, settings):
        """Create validation pipeline instance."""
        return ValidationPipeline(settings)
    
    @pytest.fixture
    def sample_email_doc(self):
        """Load sample email document from fixture."""
        fixture_path = Path("tests/fixtures/sample_email.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Convert to EmailDocument
        return EmailDocument(
            subject=data["subject_canonical"],
            from_address=data["from_addr_redacted"],
            body_text_canonical=data["body_text_canonical"],
            pii_entities=[
                PiiEntity(
                    type=pii["type"],
                    original_hash=pii["original_hash"],
                    redacted=pii["redacted"],
                    span_start=pii["span_start"],
                    span_end=pii["span_end"],
                    confidence=pii["confidence"],
                    detection_method=pii["detection_method"]
                )
                for pii in data.get("pii_entities", [])
            ],
            removed_sections=[
                RemovedSection(
                    type=sec["type"],
                    span_start=sec["span_start"],
                    span_end=sec["span_end"],
                    content_preview=sec["content_preview"],
                    confidence=sec["confidence"]
                )
                for sec in data.get("removed_sections", [])
            ]
        )
    
    @pytest.fixture
    def sample_candidates(self):
        """Load sample candidate keywords from fixture."""
        fixture_path = Path("tests/fixtures/sample_candidates.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return [
            CandidateKeyword(
                candidate_id=c["candidate_id"],
                term=c["term"],
                lemma=c["lemma"],
                count=c["count"],
                source=c["source"],
                score=c["score"]
            )
            for c in data
        ]
    
    @pytest.fixture
    def sample_request(self, sample_email_doc, sample_candidates):
        """Create sample TriageRequest."""
        return TriageRequest(
            email_document=sample_email_doc,
            candidate_keywords=sample_candidates,
            dictionary_version=1
        )
    
    @pytest.fixture
    def valid_llm_response_content(self):
        """Load valid LLM response JSON string from fixture."""
        fixture_path = Path("tests/fixtures/valid_llm_response.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()
    
    @pytest.fixture
    def valid_llm_response(self, valid_llm_response_content):
        """Create LLMGenerationResponse with valid content."""
        return LLMGenerationResponse(
            content=valid_llm_response_content,
            metadata=LLMMetadata(
                model="llama3.2:3b",
                total_duration_ms=1234,
                load_duration_ms=100,
                eval_count=200,
                prompt_eval_count=50
            )
        )
    
    @pytest.mark.asyncio
    async def test_valid_response_full_pipeline_success(
        self,
        pipeline,
        valid_llm_response,
        sample_request
    ):
        """Test that valid response passes through entire pipeline successfully."""
        response, warnings = await pipeline.validate(valid_llm_response, sample_request)
        
        # Should return EmailTriageResponse
        assert response is not None
        assert response.dictionary_version == 1
        assert response.sentiment.value == "neutral"
        assert response.priority.value == "medium"
        assert len(response.topics) == 2
        
        # May have some warnings (non-blocking quality checks)
        # but should not raise exceptions
        assert isinstance(warnings, list)
    
    @pytest.mark.asyncio
    async def test_malformed_json_raises_stage1_error(
        self,
        pipeline,
        sample_request
    ):
        """Test that malformed JSON raises JSONParseError (Stage 1)."""
        malformed_response = LLMGenerationResponse(
            content='{"dictionaryversion": 1, "topics": [',  # Incomplete JSON
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        with pytest.raises(JSONParseError) as exc_info:
            await pipeline.validate(malformed_response, sample_request)
        
        assert "Failed to parse" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_schema_violation_raises_stage2_error(
        self,
        pipeline,
        sample_request
    ):
        """Test that JSON Schema violation raises SchemaValidationError (Stage 2)."""
        # Missing required "sentiment" field
        invalid_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 1,
                "priority": {
                    "value": "medium",
                    "confidence": 0.7,
                    "signals": []
                },
                # Missing "sentiment" (required)
                "topics": [
                    {
                        "labelid": "CONTRATTO",
                        "confidence": 0.9,
                        "keywordsintext": [
                            {"candidateid": "hash_001_contratto", "lemma": "contratto", "count": 1}
                        ],
                        "evidence": [{"quote": "test"}]
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        with pytest.raises(SchemaValidationError) as exc_info:
            await pipeline.validate(invalid_response, sample_request)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_dictionary_version_mismatch_raises_stage3_error(
        self,
        pipeline,
        sample_request
    ):
        """Test that dictionary version mismatch raises BusinessRuleViolation (Stage 3)."""
        invalid_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 999,  # Mismatch!
                "sentiment": {"value": "neutral", "confidence": 0.8},
                "priority": {"value": "medium", "confidence": 0.7, "signals": []},
                "topics": [
                    {
                        "labelid": "CONTRATTO",
                        "confidence": 0.9,
                        "keywordsintext": [
                            {"candidateid": "hash_001_contratto", "lemma": "contratto", "count": 1}
                        ],
                        "evidence": [{"quote": "test"}]
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            await pipeline.validate(invalid_response, sample_request)
        
        assert "version mismatch" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_invented_candidateid_raises_stage3_error(
        self,
        pipeline,
        sample_request
    ):
        """Test that invented candidateid raises BusinessRuleViolation (Stage 3)."""
        invalid_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 1,
                "sentiment": {"value": "neutral", "confidence": 0.8},
                "priority": {"value": "medium", "confidence": 0.7, "signals": []},
                "topics": [
                    {
                        "labelid": "CONTRATTO",
                        "confidence": 0.9,
                        "keywordsintext": [
                            {"candidateid": "hash_INVENTED_ID", "lemma": "invented", "count": 1}
                        ],
                        "evidence": [{"quote": "test"}]
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            await pipeline.validate(invalid_response, sample_request)
        
        assert "not found in input candidates" in str(exc_info.value)
        assert "invented" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_invalid_topic_label_raises_stage3_error(
        self,
        pipeline,
        sample_request
    ):
        """Test that invalid topic label raises BusinessRuleViolation (Stage 3)."""
        invalid_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 1,
                "sentiment": {"value": "neutral", "confidence": 0.8},
                "priority": {"value": "medium", "confidence": 0.7, "signals": []},
                "topics": [
                    {
                        "labelid": "INVALID_TOPIC_NOT_IN_ENUM",
                        "confidence": 0.9,
                        "keywordsintext": [
                            {"candidateid": "hash_001_contratto", "lemma": "contratto", "count": 1}
                        ],
                        "evidence": [{"quote": "test"}]
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            await pipeline.validate(invalid_response, sample_request)
        
        assert "not in TopicsEnum" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_low_confidence_produces_stage4_warning(
        self,
        pipeline,
        sample_request
    ):
        """Test that low confidence produces Stage 4 warning (non-blocking)."""
        low_confidence_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 1,
                "sentiment": {"value": "neutral", "confidence": 0.1},  # Very low!
                "priority": {"value": "medium", "confidence": 0.7, "signals": ["test"]},
                "topics": [
                    {
                        "labelid": "CONTRATTO",
                        "confidence": 0.9,
                        "keywordsintext": [
                            {"candidateid": "hash_001_contratto", "lemma": "contratto", "count": 1}
                        ],
                        "evidence": [{"quote": "informazioni contratto"}]
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        response, warnings = await pipeline.validate(low_confidence_response, sample_request)
        
        # Should still succeed (warnings only)
        assert response is not None
        assert len(warnings) >= 1
        assert any("sentiment confidence" in w.lower() for w in warnings)
    
    @pytest.mark.asyncio
    async def test_evidence_not_in_text_produces_verifier_warning(
        self,
        pipeline,
        sample_request
    ):
        """Test that evidence not in email text produces verifier warning (if enabled)."""
        fabricated_evidence_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 1,
                "sentiment": {"value": "neutral", "confidence": 0.8},
                "priority": {"value": "medium", "confidence": 0.7, "signals": ["test"]},
                "topics": [
                    {
                        "labelid": "CONTRATTO",
                        "confidence": 0.9,
                        "keywordsintext": [
                            {"candidateid": "hash_001_contratto", "lemma": "contratto", "count": 1}
                        ],
                        "evidence": [
                            {"quote": "This quote does not exist in the email at all"}
                        ]
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        response, warnings = await pipeline.validate(fabricated_evidence_response, sample_request)
        
        # Should still succeed (warnings only)
        assert response is not None
        # If evidence presence check is enabled, should have warning
        if pipeline.settings.ENABLE_EVIDENCE_PRESENCE_CHECK:
            assert len(warnings) >= 1
            assert any("not found in email text" in w for w in warnings)
    
    @pytest.mark.asyncio
    async def test_all_stages_and_verifiers_log_correctly(
        self,
        pipeline,
        valid_llm_response,
        sample_request,
        caplog
    ):
        """Test that all stages and verifiers log their execution."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        response, warnings = await pipeline.validate(valid_llm_response, sample_request)
        
        # Check that stages logged execution
        assert any("Stage 1" in record.message for record in caplog.records)
        assert any("Stage 2" in record.message for record in caplog.records)
        assert any("Stage 3" in record.message for record in caplog.records)
        assert any("Stage 4" in record.message for record in caplog.records)
        assert any("verifiers" in record.message.lower() for record in caplog.records)
    
    @pytest.mark.asyncio
    async def test_pipeline_with_disabled_verifiers(
        self,
        sample_request,
        valid_llm_response
    ):
        """Test that pipeline works with verifiers disabled."""
        # Create settings with verifiers disabled
        settings = Settings(
            ENABLE_EVIDENCE_PRESENCE_CHECK=False,
            ENABLE_KEYWORD_PRESENCE_CHECK=False
        )
        pipeline = ValidationPipeline(settings)
        
        # Should still work, just with fewer verifiers
        response, warnings = await pipeline.validate(valid_llm_response, sample_request)
        
        assert response is not None
        # Span coherence verifier always runs, but evidence/keyword may not
        assert isinstance(warnings, list)
    
    @pytest.mark.asyncio
    async def test_pipeline_accumulates_multiple_warnings(
        self,
        pipeline,
        sample_request
    ):
        """Test that pipeline accumulates multiple warnings from different sources."""
        # Create response with multiple quality issues
        multi_issue_response = LLMGenerationResponse(
            content=json.dumps({
                "dictionaryversion": 1,
                "sentiment": {"value": "neutral", "confidence": 0.1},  # Low confidence
                "priority": {"value": "medium", "confidence": 0.15, "signals": []},  # Low + empty signals
                "topics": [
                    {
                        "labelid": "CONTRATTO",
                        "confidence": 0.05,  # Very low!
                        "keywordsintext": [
                            {"candidateid": "hash_001_contratto", "lemma": "contratto", "count": 1}
                        ],
                        "evidence": [{"quote": "This fabricated quote"}]  # Not in text
                    }
                ]
            }),
            metadata=LLMMetadata(
                model="test",
                total_duration_ms=100,
                load_duration_ms=10,
                eval_count=10,
                prompt_eval_count=5
            )
        )
        
        response, warnings = await pipeline.validate(multi_issue_response, sample_request)
        
        # Should accumulate warnings from Stage 4 + verifiers
        assert len(warnings) >= 3
        assert any("sentiment" in w.lower() for w in warnings)
        assert any("priority" in w.lower() for w in warnings)
        assert any("topic" in w.lower() and "confidence" in w.lower() for w in warnings)
