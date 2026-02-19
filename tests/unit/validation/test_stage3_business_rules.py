"""
Unit tests for Stage 3: Business Rules Validation.
"""

import pytest
from datetime import datetime

from inference_layer.models.enums import TopicsEnum, SentimentEnum, PriorityEnum
from inference_layer.models.input_models import (
    EmailDocument,
    CandidateKeyword,
    TriageRequest,
    InputPipelineVersion,
)
from inference_layer.models.output_models import (
    EmailTriageResponse,
    TopicResult,
    KeywordInText,
    EvidenceItem,
    SentimentResult,
    PriorityResult,
)
from inference_layer.validation.stage3_business_rules import Stage3BusinessRules
from inference_layer.validation.exceptions import BusinessRuleViolation


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


class TestStage3BusinessRules:
    """Test suite for Stage 3 Business Rules validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.stage3 = Stage3BusinessRules()
        
        # Create sample email document
        self.email_doc = create_test_email_doc(
            "Vorrei informazioni sul contratto e sulla garanzia."
        )
        
        # Create sample candidates
        self.candidates = [
            CandidateKeyword(
                candidate_id="hash_001",
                term="contratto",
                lemma="contratto",
                count=2,
                source="body",
                score=0.95
            ),
            CandidateKeyword(
                candidate_id="hash_002",
                term="garanzia",
                lemma="garanzia",
                count=1,
                source="body",
                score=0.85
            ),
            CandidateKeyword(
                candidate_id="hash_003",
                term="informazioni",
                lemma="informazione",
                count=1,
                source="body",
                score=0.75
            ),
        ]
        
        # Create sample request
        self.request = TriageRequest(
            email=self.email_doc,
            candidate_keywords=self.candidates,
            dictionary_version=42
        )
    
    def test_valid_response_passes(self):
        """Test that valid response passes all business rules."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=["test"]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(
                            candidate_id="hash_001",
                            lemma="contratto",
                            count=2
                        )
                    ],
                    evidence=[
                        EvidenceItem(quote="informazioni sul contratto")
                    ]
                )
            ]
        )
        
        # Should not raise any exception
        self.stage3.validate(response, self.request)
    
    def test_dictionary_version_mismatch_raises_error(self):
        """Test that dictionary version mismatch raises BusinessRuleViolation."""
        response = EmailTriageResponse(
            dictionaryversion=999,  # Mismatch!
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "version mismatch" in str(exc_info.value).lower()
        assert exc_info.value.details["rule_name"] == "dictionary_version_match"
        assert exc_info.value.details["invalid_value"] == "999"
    
    def test_invalid_topic_label_raises_error(self):
        """Test that invalid topic label (not in enum) raises BusinessRuleViolation."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="INVENTED_TOPIC",  # Not in TopicsEnum!
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="test", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "not in TopicsEnum" in str(exc_info.value)
        assert exc_info.value.details["rule_name"] == "topic_label_in_enum"
        assert exc_info.value.details["invalid_value"] == "INVENTED_TOPIC"
        assert "expected_values" in exc_info.value.details
    
    def test_invented_candidateid_raises_error(self):
        """Test that invented candidateid raises BusinessRuleViolation."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(
                            candidate_id="hash_INVENTED",  # Not in input candidates!
                            lemma="invented",
                            count=1
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "not found in input candidates" in str(exc_info.value)
        assert "invented a keyword" in str(exc_info.value)
        assert exc_info.value.details["rule_name"] == "candidateid_exists_in_input"
        assert exc_info.value.details["invalid_value"] == "hash_INVENTED"
    
    def test_multiple_candidateids_one_invalid_raises_error(self):
        """Test that one invalid candidateid among many raises error."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1),
                        KeywordInText(candidate_id="hash_002", lemma="garanzia", count=1),
                        KeywordInText(candidate_id="hash_INVALID", lemma="invalid", count=1),  # Invalid!
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "hash_INVALID" in str(exc_info.value)
        assert "keywordsintext[2]" in exc_info.value.details["field_path"]
    
    def test_multiple_topics_one_invalid_label_raises_error(self):
        """Test that one invalid topic label among many raises error."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test1")]
                ),
                TopicResult(
                    labelid="INVALID_TOPIC",  # Invalid!
                    confidence=0.8,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_002", lemma="garanzia", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test2")]
                ),
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "INVALID_TOPIC" in str(exc_info.value)
        assert "topics[1]" in exc_info.value.details["field_path"]
    
    def test_invalid_sentiment_value_raises_error(self):
        """Test that invalid sentiment value raises BusinessRuleViolation."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="INVALID_SENTIMENT", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "not in SentimentEnum" in str(exc_info.value)
        assert exc_info.value.details["rule_name"] == "sentiment_in_enum"
    
    def test_invalid_priority_value_raises_error(self):
        """Test that invalid priority value raises BusinessRuleViolation."""
        response = EmailTriageResponse(
            dictionaryversion=42,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="INVALID_PRIORITY", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        with pytest.raises(BusinessRuleViolation) as exc_info:
            self.stage3.validate(response, self.request)
        
        assert "not in PriorityEnum" in str(exc_info.value)
        assert exc_info.value.details["rule_name"] == "priority_in_enum"
    
    def test_all_valid_enum_values_pass(self):
        """Test that all valid enum values pass validation."""
        # Test all valid topics
        for topic_enum in TopicsEnum:
            response = EmailTriageResponse(
                dictionaryversion=42,
                sentiment=SentimentResult(value="neutral", confidence=0.8),
                priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
                topics=[
                    TopicResult(
                        labelid=topic_enum.value,
                        confidence=0.9,
                        keywordsintext=[
                            KeywordInText(candidate_id="hash_001", lemma="test", count=1)
                        ],
                        evidence=[EvidenceItem(quote="test")]
                    )
                ]
            )
            # Should not raise
            self.stage3.validate(response, self.request)
        
        # Test all valid sentiments
        for sentiment_enum in SentimentEnum:
            response = EmailTriageResponse(
                dictionaryversion=42,
                sentiment=SentimentResult(value=sentiment_enum.value, confidence=0.8),
                priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
                topics=[
                    TopicResult(
                        labelid="CONTRATTO",
                        confidence=0.9,
                        keywordsintext=[
                            KeywordInText(candidate_id="hash_001", lemma="test", count=1)
                        ],
                        evidence=[EvidenceItem(quote="test")]
                    )
                ]
            )
            # Should not raise
            self.stage3.validate(response, self.request)
        
        # Test all valid priorities
        for priority_enum in PriorityEnum:
            response = EmailTriageResponse(
                dictionaryversion=42,
                sentiment=SentimentResult(value="neutral", confidence=0.8),
                priority=PriorityResult(value=priority_enum.value, confidence=0.7, signals=[]),
                topics=[
                    TopicResult(
                        labelid="CONTRATTO",
                        confidence=0.9,
                        keywordsintext=[
                            KeywordInText(candidate_id="hash_001", lemma="test", count=1)
                        ],
                        evidence=[EvidenceItem(quote="test")]
                    )
                ]
            )
            # Should not raise
            self.stage3.validate(response, self.request)


