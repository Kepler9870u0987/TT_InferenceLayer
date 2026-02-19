"""
Unit tests for Stage 4: Quality Checks.
"""

import pytest

from inference_layer.models.output_models import (
    EmailTriageResponse,
    TopicResult,
    KeywordInText,
    EvidenceItem,
    SentimentResult,
    PriorityResult,
)
from inference_layer.validation.stage4_quality import Stage4QualityChecks


class TestStage4QualityChecks:
    """Test suite for Stage 4 Quality Checks (warnings only)."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.stage4 = Stage4QualityChecks(min_confidence_threshold=0.2)
    
    def create_minimal_valid_response(self, **overrides):
        """Helper to create minimal valid response with overrides."""
        defaults = {
            "dictionary_version": 1,
            "sentiment": SentimentResult(value="neutral", confidence=0.8),
            "priority": PriorityResult(value="medium", confidence=0.7, signals=["test"]),
            "topics": [
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test evidence")]
                )
            ]
        }
        defaults.update(overrides)
        return EmailTriageResponse(**defaults)
    
    def test_high_quality_response_no_warnings(self):
        """Test that high-quality response produces no warnings."""
        response = self.create_minimal_valid_response()
        warnings = self.stage4.validate(response)
        
        assert warnings == []
    
    def test_low_sentiment_confidence_warning(self):
        """Test that low sentiment confidence produces warning."""
        response = self.create_minimal_valid_response(
            sentiment=SentimentResult(value="neutral", confidence=0.1)  # Below threshold
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("sentiment confidence" in w.lower() for w in warnings)
        assert any("0.100" in w for w in warnings)
    
    def test_low_priority_confidence_warning(self):
        """Test that low priority confidence produces warning."""
        response = self.create_minimal_valid_response(
            priority=PriorityResult(value="medium", confidence=0.15, signals=["test"])
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("priority confidence" in w.lower() for w in warnings)
    
    def test_low_topic_confidence_warning(self):
        """Test that low topic confidence produces warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.05,  # Very low!
                    keywordsintext=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("topic" in w.lower() and "contratto" in w.upper() for w in warnings)
        assert any("0.050" in w for w in warnings)
    
    def test_duplicate_topics_warning(self):
        """Test that duplicate topics produce warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="h1", lemma="test1", count=1)
                    ],
                    evidence=[EvidenceItem(quote="evidence1")]
                ),
                TopicResult(
                    labelid="CONTRATTO",  # Duplicate!
                    confidence=0.8,
                    keywordsintext=[
                        KeywordInText(candidate_id="h2", lemma="test2", count=1)
                    ],
                    evidence=[EvidenceItem(quote="evidence2")]
                ),
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("duplicate topic" in w.lower() and "contratto" in w.upper() for w in warnings)
    
    def test_duplicate_keywords_within_topic_warning(self):
        """Test that duplicate keywords within topic produce warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1),
                        KeywordInText(candidate_id="hash_002", lemma="garanzia", count=1),
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=2),  # Duplicate!
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("duplicate keyword" in w.lower() and "hash_001" in w for w in warnings)
    
    def test_duplicate_evidence_quotes_warning(self):
        """Test that duplicate evidence quotes produce warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="Same quote here"),
                        EvidenceItem(quote="Same quote here"),  # Duplicate!
                    ]
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("duplicate evidence" in w.lower() for w in warnings)
    
    def test_duplicate_evidence_case_insensitive(self):
        """Test that duplicate detection is case-insensitive."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="Test Quote"),
                        EvidenceItem(quote="test quote"),  # Same (case-insensitive)
                    ]
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("duplicate evidence" in w.lower() for w in warnings)
    
    def test_topic_without_keywords_warning(self):
        """Test that topic without keywords produces warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[],  # No keywords!
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("no keywords" in w.lower() for w in warnings)
    
    def test_topic_without_evidence_warning(self):
        """Test that topic without evidence produces warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[]  # No evidence!
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("no evidence" in w.lower() for w in warnings)
    
    def test_priority_without_signals_warning(self):
        """Test that priority without signals produces warning."""
        response = self.create_minimal_valid_response(
            priority=PriorityResult(value="medium", confidence=0.7, signals=[])  # Empty!
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("no signals" in w.lower() for w in warnings)
    
    def test_very_long_evidence_quote_warning(self):
        """Test that very long evidence quote (>180 chars) produces warning."""
        response = self.create_minimal_valid_response(
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="x" * 190)  # 190 chars (max is 200)
                    ]
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("very long" in w.lower() and "190 chars" in w for w in warnings)
    
    def test_multiple_quality_issues_multiple_warnings(self):
        """Test that multiple quality issues produce multiple warnings."""
        response = self.create_minimal_valid_response(
            sentiment=SentimentResult(value="neutral", confidence=0.1),  # Low confidence
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),  # No signals
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.05,  # Low confidence
                    keywordsintext=[],  # No keywords
                    evidence=[]  # No evidence
                )
            ]
        )
        warnings = self.stage4.validate(response)
        
        # Should have multiple warnings
        assert len(warnings) >= 4
        assert any("sentiment" in w.lower() for w in warnings)
        assert any("signals" in w.lower() for w in warnings)
        assert any("keywords" in w.lower() for w in warnings)
        assert any("evidence" in w.lower() for w in warnings)
    
    def test_confidence_exactly_at_threshold_no_warning(self):
        """Test that confidence exactly at threshold produces no warning."""
        response = self.create_minimal_valid_response(
            sentiment=SentimentResult(value="neutral", confidence=0.2)  # Exactly at threshold
        )
        warnings = self.stage4.validate(response)
        
        # Should not warn about sentiment
        assert not any("sentiment" in w.lower() for w in warnings)
    
    def test_custom_confidence_threshold(self):
        """Test that custom confidence threshold is respected."""
        stage4 = Stage4QualityChecks(min_confidence_threshold=0.5)
        
        response = self.create_minimal_valid_response(
            sentiment=SentimentResult(value="neutral", confidence=0.4)  # Below 0.5
        )
        warnings = stage4.validate(response)
        
        assert len(warnings) >= 1
        assert any("sentiment" in w.lower() and "0.400" in w for w in warnings)

