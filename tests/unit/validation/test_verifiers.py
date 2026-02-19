"""
Unit tests for Validation Verifiers.
"""

import pytest

from inference_layer.models.input_models import (
    EmailDocument,
    CandidateKeyword,
    TriageRequest,
)
from inference_layer.models.output_models import (
    EmailTriageResponse,
    TopicResult,
    KeywordInText,
    EvidenceItem,
    SentimentResult,
    PriorityResult,
)
from inference_layer.validation.verifiers import (
    EvidencePresenceVerifier,
    KeywordPresenceVerifier,
    SpansCoherenceVerifier,
)


class TestEvidencePresenceVerifier:
    """Test suite for Evidence Presence Verifier."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.verifier = EvidencePresenceVerifier()
        
        self.email_doc = EmailDocument(
            subject="Test",
            from_address="test@example.com",
            body_text_canonical="Vorrei informazioni sul contratto e sulla garanzia del prodotto.",
            pii_entities=[],
            removed_sections=[]
        )
        
        self.request = TriageRequest(
            email_document=self.email_doc,
            candidate_keywords=[],
            dictionary_version=1
        )
    
    def test_evidence_found_in_text_no_warning(self):
        """Test that evidence quote found in text produces no warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="contratto", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="informazioni sul contratto")  # In text!
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert warnings == []
    
    def test_evidence_not_found_warning(self):
        """Test that evidence quote not found in text produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="contratto", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="questo non è nel testo originale")
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("not found in email text" in w for w in warnings)
    
    def test_evidence_case_insensitive_match(self):
        """Test that evidence matching is case-insensitive."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="contratto", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="INFORMAZIONI SUL CONTRATTO")  # Different case
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert warnings == []
    
    def test_evidence_with_valid_span_no_warning(self):
        """Test that evidence with valid span produces no warning."""
        # "Vorrei informazioni sul contratto"
        # Indices: "informazioni sul contratto" is at approximately [7:36]
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="contratto", count=1)
                    ],
                    evidence=[
                        EvidenceItem(
                            quote="informazioni sul contratto",
                            span=[7, 36]
                        )
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert warnings == []
    
    def test_evidence_with_invalid_span_warning(self):
        """Test that evidence with mismatched span produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="contratto", count=1)
                    ],
                    evidence=[
                        EvidenceItem(
                            quote="informazioni sul contratto",
                            span=[0, 5]  # Wrong span!
                        )
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("span" in w.lower() and "does not match" in w for w in warnings)
    
    def test_empty_body_warning(self):
        """Test that empty email body produces warning."""
        empty_email_doc = EmailDocument(
            subject="Test",
            from_address="test@example.com",
            body_text_canonical="",
            pii_entities=[],
            removed_sections=[]
        )
        
        request = TriageRequest(
            email_document=empty_email_doc,
            candidate_keywords=[],
            dictionary_version=1
        )
        
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, request)
        assert len(warnings) >= 1
        assert any("empty" in w.lower() for w in warnings)


class TestKeywordPresenceVerifier:
    """Test suite for Keyword Presence Verifier."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.verifier = KeywordPresenceVerifier()
        
        self.email_doc = EmailDocument(
            subject="Test",
            from_address="test@example.com",
            body_text_canonical="Vorrei informazioni sul contratto e sulla garanzia.",
            pii_entities=[],
            removed_sections=[]
        )
        
        self.candidates = [
            CandidateKeyword(
                candidate_id="hash_001",
                term="contratto",
                lemma="contratto",
                count=1,
                source="body",
                score=0.9
            ),
            CandidateKeyword(
                candidate_id="hash_002",
                term="garanzia",
                lemma="garanzia",
                count=1,
                source="body",
                score=0.8
            ),
            CandidateKeyword(
                candidate_id="hash_003",
                term="assente",
                lemma="assente",
                count=0,
                source="body",
                score=0.1
            ),
        ]
        
        self.request = TriageRequest(
            email_document=self.email_doc,
            candidate_keywords=self.candidates,
            dictionary_version=1
        )
    
    def test_keyword_found_in_text_no_warning(self):
        """Test that keyword found in text produces no warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="hash_001", lemma="contratto", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert warnings == []
    
    def test_keyword_not_found_warning(self):
        """Test that keyword not found in text produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="hash_003", lemma="assente", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("not found in email text" in w for w in warnings)
        assert any("assente" in w for w in warnings)
    
    def test_keyword_case_insensitive_match(self):
        """Test that keyword matching is case-insensitive."""
        # "contratto" appears in lowercase in text
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="hash_001", lemma="CONTRATTO", count=1)
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert warnings == []
    
    def test_keyword_with_valid_spans_no_warning(self):
        """Test that keyword with valid spans produces no warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="hash_001",
                            lemma="contratto",
                            count=1,
                            spans=[[24, 33]]  # Within text bounds
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        # Might have warning about span not matching exact location, but not bounds
        assert not any("out of bounds" in w for w in warnings)
    
    def test_keyword_with_out_of_bounds_span_warning(self):
        """Test that keyword with out-of-bounds span produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="hash_001",
                            lemma="contratto",
                            count=1,
                            spans=[[0, 999]]  # Out of bounds!
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("out of bounds" in w for w in warnings)
    
    def test_keyword_invalid_candidateid_warning(self):
        """Test that keyword with invalid candidateid produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="hash_INVALID",
                            lemma="invalid",
                            count=1
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("not in candidates" in w for w in warnings)


class TestSpansCoherenceVerifier:
    """Test suite for Spans Coherence Verifier."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.verifier = SpansCoherenceVerifier()
        
        self.email_doc = EmailDocument(
            subject="Test",
            from_address="test@example.com",
            body_text_canonical="This is a test email with some content.",  # 41 chars
            pii_entities=[],
            removed_sections=[]
        )
        
        self.request = TriageRequest(
            email_document=self.email_doc,
            candidate_keywords=[],
            dictionary_version=1
        )
    
    def test_valid_spans_no_warning(self):
        """Test that valid spans produce no warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="h1",
                            lemma="test",
                            count=1,
                            spans=[[10, 14], [20, 25]]  # Valid
                        )
                    ],
                    evidence=[
                        EvidenceItem(quote="test", span=[10, 14])
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert warnings == []
    
    def test_span_start_greater_than_end_warning(self):
        """Test that span with start >= end produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="h1",
                            lemma="test",
                            count=1,
                            spans=[[20, 10]]  # start > end!
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("start >= end" in w for w in warnings)
    
    def test_span_negative_start_warning(self):
        """Test that span with negative start produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="h1",
                            lemma="test",
                            count=1,
                            spans=[[-5, 10]]  # Negative start!
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("start < 0" in w for w in warnings)
    
    def test_span_end_exceeds_text_length_warning(self):
        """Test that span with end > text length produces warning."""
        # Text length is 41 chars
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="h1",
                            lemma="test",
                            count=1,
                            spans=[[10, 100]]  # End > 41!
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("end > text length" in w for w in warnings)
    
    def test_span_invalid_format_warning(self):
        """Test that span with invalid format produces warning."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(
                            candidate_id="h1",
                            lemma="test",
                            count=1,
                            spans=[[10, 20, 30]]  # Should be [start, end] not [start, end, extra]
                        )
                    ],
                    evidence=[EvidenceItem(quote="test")]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("invalid span format" in w.lower() for w in warnings)
    
    def test_evidence_span_coherence(self):
        """Test that evidence spans are also checked for coherence."""
        response = EmailTriageResponse(
            dictionary_version=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=[]),
            topics=[
                TopicResult(
                    label_id="CONTRATTO",
                    confidence=0.9,
                    keywords_in_text=[
                        KeywordInText(candidate_id="h1", lemma="test", count=1)
                    ],
                    evidence=[
                        EvidenceItem(quote="test", span=[50, 100])  # Out of bounds!
                    ]
                )
            ]
        )
        
        warnings = self.verifier.verify(response, self.request)
        assert len(warnings) >= 1
        assert any("evidence" in w and ("end > text length" in w or "text length" in w) for w in warnings)
