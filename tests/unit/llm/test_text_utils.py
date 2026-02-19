"""Unit tests for text utilities (truncation, PII span adjustment)."""

import pytest
from inference_layer.llm.text_utils import (
    truncate_at_sentence_boundary,
    adjust_pii_spans_after_truncation,
    count_tokens_approximate
)
from inference_layer.models.input_models import PiiEntity


class TestTruncateAtSentenceBoundary:
    """Test sentence boundary truncation."""
    
    def test_no_truncation_needed(self):
        """Text shorter than limit should not be truncated."""
        text = "Hello world."
        result = truncate_at_sentence_boundary(text, max_chars=100)
        assert result == text
    
    def test_truncates_at_sentence_end(self):
        """Should truncate after last complete sentence."""
        text = "First sentence. Second sentence. Third sentence."
        result = truncate_at_sentence_boundary(text, max_chars=35)
        # Should keep "First sentence. Second sentence."
        assert result == "First sentence. Second sentence."
    
    def test_truncates_at_exclamation(self):
        """Should recognize exclamation mark as sentence boundary."""
        text = "Great news! More text here. Even more."
        result = truncate_at_sentence_boundary(text, max_chars=20)
        assert result == "Great news!"
    
    def test_truncates_at_question(self):
        """Should recognize question mark as sentence boundary."""
        text = "What is this? This is a test. More text."
        result = truncate_at_sentence_boundary(text, max_chars=18)
        assert result == "What is this?"
    
    def test_no_sentence_boundary_hard_truncate(self):
        """If no sentence boundary, should hard truncate at word."""
        text = "NoPeriodsHereJustALongRun"
        result = truncate_at_sentence_boundary(text, max_chars=10)
        # Should truncate somewhere near 10 chars
        assert len(result) <= 10
    
    def test_italian_text(self):
        """Should work with Italian text."""
        text = "Questa è una prova. Il contratto è pronto. Attendo risposta."
        result = truncate_at_sentence_boundary(text, max_chars=45)
        assert result == "Questa è una prova. Il contratto è pronto."
    
    def test_empty_text(self):
        """Empty text should return empty."""
        result = truncate_at_sentence_boundary("", max_chars=100)
        assert result == ""


class TestAdjustPiiSpansAfterTruncation:
    """Test PII span adjustment after truncation."""
    
    def test_entities_within_truncation(self):
        """Entities fully within truncated text should be kept."""
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc123", redacted="user@example.com",
                span_start=10, span_end=25, confidence=0.95, detection_method="regex"
            ),
            PiiEntity(
                type="NAME", original_hash="def456", redacted="Mario Rossi",
                span_start=30, span_end=45, confidence=0.90, detection_method="ner"
            ),
        ]
        result = adjust_pii_spans_after_truncation(
            pii_entities=entities,
            truncated_length=50,
            original_text="x" * 100,
            truncated_text="x" * 50
        )
        assert len(result) == 2
        assert result[0].span_start == 10
        assert result[0].span_end == 25
        assert result[1].span_start == 30
        assert result[1].span_end == 45
    
    def test_entities_after_truncation_excluded(self):
        """Entities completely after truncation point should be excluded."""
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc123", redacted="user@example.com",
                span_start=10, span_end=25, confidence=0.95, detection_method="regex"
            ),
            PiiEntity(
                type="NAME", original_hash="def456", redacted="Mario Rossi",
                span_start=60, span_end=75, confidence=0.90, detection_method="ner"
            ),
        ]
        result = adjust_pii_spans_after_truncation(
            pii_entities=entities,
            truncated_length=50,
            original_text="x" * 100,
            truncated_text="x" * 50
        )
        assert len(result) == 1
        assert result[0].type == "EMAIL"
    
    def test_entity_straddles_boundary(self):
        """Entity straddling truncation boundary should be adjusted."""
        entities = [
            PiiEntity(
                type="EMAIL", original_hash="abc123", redacted="user@example.com",
                span_start=40, span_end=60, confidence=0.95, detection_method="regex"
            ),
        ]
        result = adjust_pii_spans_after_truncation(
            pii_entities=entities,
            truncated_length=50,
            original_text="x" * 100,
            truncated_text="x" * 50
        )
        assert len(result) == 1
        # Span should be adjusted to span_start=40, span_end=50
        assert result[0].span_start == 40
        assert result[0].span_end == 50
    
    def test_empty_entities_list(self):
        """Empty entity list should return empty."""
        result = adjust_pii_spans_after_truncation(
            pii_entities=[],
            truncated_length=50,
            original_text="x" * 100,
            truncated_text="x" * 50
        )
        assert result == []


class TestCountTokensApproximate:
    """Test approximate token counting."""
    
    def test_english_text(self):
        """English text should be roughly 4 chars per token."""
        text = "This is a test sentence with multiple words."
        tokens = count_tokens_approximate(text)
        # ~45 chars / 3 = 15 tokens (very rough)
        assert 10 < tokens < 20
    
    def test_italian_text(self):
        """Italian text should also work reasonably."""
        text = "Questo è un testo di prova con diverse parole italiane."
        tokens = count_tokens_approximate(text)
        # Should be > 0
        assert tokens > 0
    
    def test_empty_text(self):
        """Empty text should return 1 (minimum)."""
        tokens = count_tokens_approximate("")
        assert tokens == 1
