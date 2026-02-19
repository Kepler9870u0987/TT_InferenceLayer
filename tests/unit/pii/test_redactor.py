"""Unit tests for PII redaction."""

import pytest
from inference_layer.pii.redactor import redact_pii_for_llm, redact_pii_in_candidates
from inference_layer.models.input_models import PiiEntity, CandidateKeyword


class TestRedactPiiForLlm:
    """Test PII redaction for LLM prompts."""
    
    def test_redaction_disabled(self):
        """When disabled, should return original text."""
        text = "My email is user@example.com and phone is 123-456-7890."
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc", redacted="user@example.com",
                span_start=12, span_end=28, confidence=0.95, detection_method="regex"
            ),
            PiiEntity(
                type="PHONE_IT", original_hash="def", redacted="123-456-7890",
                span_start=42, span_end=54, confidence=0.90, detection_method="regex"
            ),
        ]
        result = redact_pii_for_llm(text, entities, redact_enabled=False)
        assert result == text
    
    def test_redaction_enabled_email(self):
        """Should redact EMAIL when enabled."""
        text = "My email is user@example.com."
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc", redacted="user@example.com",
                span_start=12, span_end=28, confidence=0.95, detection_method="regex"
            ),
        ]
        result = redact_pii_for_llm(text, entities, redact_enabled=True)
        assert result == "My email is [REDACTED_EMAIL]."
    
    def test_redaction_multiple_entities(self):
        """Should redact multiple entities."""
        text = "Contact Mario Rossi at mario@example.com or 339-1234567."
        entities = [
            PiiEntity(
                type="NAME", original_hash="abc", redacted="Mario Rossi",
                span_start=8, span_end=19, confidence=0.95, detection_method="ner"
            ),
            PiiEntity(
                type="EMAIL", original_hash="def", redacted="mario@example.com",
                span_start=23, span_end=40, confidence=0.95, detection_method="regex"
            ),
            PiiEntity(
                type="PHONE_IT", original_hash="ghi", redacted="339-1234567",
                span_start=44, span_end=56, confidence=0.90, detection_method="regex"
            ),
        ]
        result = redact_pii_for_llm(text, entities, redact_enabled=True)
        expected = "Contact [REDACTED_NAME] at [REDACTED_EMAIL] or [REDACTED_PHONE_IT]."
        assert result == expected
    
    def test_redaction_selective_types(self):
        """Should only redact specified types."""
        text = "Mario Rossi email: mario@example.com"
        entities = [
            PiiEntity(
                type="NAME", original_hash="abc", redacted="Mario Rossi",
                span_start=0, span_end=11, confidence=0.95, detection_method="ner"
            ),
            PiiEntity(
                type="EMAIL", original_hash="def", redacted="mario@example.com",
                span_start=19, span_end=36, confidence=0.95, detection_method="regex"
            ),
        ]
        # Only redact EMAIL
        result = redact_pii_for_llm(
            text, entities, redact_enabled=True, redact_types={'EMAIL'}
        )
        assert result == "Mario Rossi email: [REDACTED_EMAIL]"
    
    def test_empty_entities(self):
        """Empty entity list should return original text."""
        text = "No PII here."
        result = redact_pii_for_llm(text, [], redact_enabled=True)
        assert result == text
    
    def test_invalid_span_skipped(self):
        """Invalid spans should be skipped."""
        text = "Test text"
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc", redacted="user@example.com",
                span_start=100, span_end=200, confidence=0.95, detection_method="regex"
            ),  # Out of bounds
        ]
        result = redact_pii_for_llm(text, entities, redact_enabled=True)
        # Should return original (invalid span skipped)
        assert result == text


class TestRedactPiiInCandidates:
    """Test PII filtering in candidate keywords."""
    
    def test_redaction_disabled(self):
        """When disabled, should return all candidates."""
        candidates = [
            CandidateKeyword(
                candidate_id="1", term="contratto", lemma="contratto",
                count=3, source="email", score=8.5
            ),
            CandidateKeyword(
                candidate_id="2", term="user@example.com", lemma="user@example.com",
                count=1, source="email", score=2.0
            ),
        ]
        result = redact_pii_in_candidates(candidates, [], "body", redact_enabled=False)
        assert len(result) == 2
    
    def test_filters_pii_candidates(self):
        """Should filter out PII candidate terms."""
        body = "Contact user@example.com for contratto info."
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc", redacted="user@example.com",
                span_start=8, span_end=24, confidence=0.95, detection_method="regex"
            ),
        ]
        candidates = [
            CandidateKeyword(
                candidate_id="1", term="contratto", lemma="contratto",
                count=3, source="email", score=8.5
            ),
            CandidateKeyword(
                candidate_id="2", term="user@example.com", lemma="user@example.com",
                count=1, source="email", score=2.0
            ),
        ]
        result = redact_pii_in_candidates(
            candidates, entities, body, redact_enabled=True
        )
        # Should only keep "contratto", filter out email
        assert len(result) == 1
        assert result[0].term == "contratto"
    
    def test_empty_pii(self):
        """No PII entities should return all candidates."""
        candidates = [
            CandidateKeyword(
                candidate_id="1", term="contratto", lemma="contratto",
                count=3, source="email", score=8.5
            ),
        ]
        result = redact_pii_in_candidates(candidates, [], "body", redact_enabled=True)
        assert len(result) == 1
