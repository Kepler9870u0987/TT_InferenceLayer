"""
Validation Verifiers: Extra checks beyond standard validation.

These verifiers check semantic coherence:
- Evidence quotes actually appear in email text
- Keywords actually appear in email text
- Spans are within text bounds and coherent

Like Stage 4, these produce warnings (not exceptions).
"""

import logging
from typing import Optional

from ..models.input_models import EmailDocument, TriageRequest
from ..models.output_models import EmailTriageResponse

logger = logging.getLogger(__name__)


class EvidencePresenceVerifier:
    """
    Verify that evidence quotes exist in the original email text.
    
    This catches cases where LLM fabricates or hallucinates evidence.
    """
    
    def verify(self, response: EmailTriageResponse, request: TriageRequest) -> list[str]:
        """
        Check if evidence quotes are present in email text.
        
        Args:
            response: LLM response with evidence quotes
            request: Original request with email document
            
        Returns:
            List of warnings for missing evidence
        """
        warnings: list[str] = []
        
        # Get canonical email body text
        email_text = request.email_document.body_text_canonical
        if not email_text:
            warnings.append("Email body_text_canonical is empty, cannot verify evidence presence")
            return warnings
        
        # Normalize text for comparison (case-insensitive)
        email_text_lower = email_text.lower()
        
        for topic_idx, topic in enumerate(response.topics):
            for ev_idx, evidence in enumerate(topic.evidence):
                quote = evidence.quote.strip()
                quote_lower = quote.lower()
                
                # Check if quote appears as substring
                if quote_lower not in email_text_lower:
                    warnings.append(
                        f"Evidence quote not found in email text: '{quote[:100]}...' "
                        f"(topic '{topic.label_id}', topic index {topic_idx}, "
                        f"evidence index {ev_idx})"
                    )
                    continue
                
                # If span is provided, verify it matches the quote
                if evidence.span:
                    span_start, span_end = evidence.span
                    if self._verify_span(email_text, quote, span_start, span_end):
                        logger.debug(
                            f"Evidence span verified: [{span_start}:{span_end}] "
                            f"matches quote in topic '{topic.label_id}'"
                        )
                    else:
                        warnings.append(
                            f"Evidence span [{span_start}:{span_end}] does not match quote "
                            f"in topic '{topic.label_id}' (topic index {topic_idx}, "
                            f"evidence index {ev_idx})"
                        )
        
        return warnings
    
    @staticmethod
    def _verify_span(text: str, quote: str, start: int, end: int) -> bool:
        """
        Verify that span [start:end] in text matches the quote.
        
        Args:
            text: Full email text
            quote: Expected quote string
            start: Start index
            end: End index
            
        Returns:
            True if span matches quote (case-insensitive), False otherwise
        """
        if start < 0 or end > len(text) or start >= end:
            return False
        
        extracted = text[start:end].strip().lower()
        quote_normalized = quote.strip().lower()
        
        return extracted == quote_normalized


class KeywordPresenceVerifier:
    """
    Verify that keywords actually appear in the email text.
    
    This catches cases where LLM selects irrelevant keywords or
    mismatches candidates to email content.
    """
    
    def verify(self, response: EmailTriageResponse, request: TriageRequest) -> list[str]:
        """
        Check if keywords are present in email text.
        
        Args:
            response: LLM response with selected keywords
            request: Original request with email document and candidates
            
        Returns:
            List of warnings for keywords not found in text
        """
        warnings: list[str] = []
        
        # Get canonical email body text
        email_text = request.email_document.body_text_canonical
        if not email_text:
            warnings.append("Email body_text_canonical is empty, cannot verify keyword presence")
            return warnings
        
        # Normalize text for comparison (case-insensitive)
        email_text_lower = email_text.lower()
        
        # Build lookup map from candidateid to keyword info
        candidate_map = {
            candidate.candidate_id: {
                "term": candidate.term,
                "lemma": candidate.lemma
            }
            for candidate in request.candidate_keywords
        }
        
        for topic_idx, topic in enumerate(response.topics):
            for kw_idx, keyword in enumerate(topic.keywords_in_text):
                candidate_id = keyword.candidate_id
                
                # Get term and lemma from candidate
                if candidate_id not in candidate_map:
                    # This should have been caught by Stage 3, but handle gracefully
                    warnings.append(
                        f"Keyword candidateid '{candidate_id}' not in candidates "
                        f"(topic '{topic.label_id}', keyword index {kw_idx})"
                    )
                    continue
                
                candidate_info = candidate_map[candidate_id]
                term = candidate_info["term"].lower()
                lemma = candidate_info["lemma"].lower()
                
                # Check if term or lemma appears in text
                term_found = term in email_text_lower
                lemma_found = lemma in email_text_lower if lemma != term else term_found
                
                if not term_found and not lemma_found:
                    warnings.append(
                        f"Keyword term '{candidate_info['term']}' / lemma '{candidate_info['lemma']}' "
                        f"not found in email text (candidateid: {candidate_id}, "
                        f"topic '{topic.label_id}', keyword index {kw_idx})"
                    )
                    continue
                
                # If spans provided, verify they're within bounds
                if keyword.spans:
                    for span_idx, span in enumerate(keyword.spans):
                        if len(span) != 2:
                            warnings.append(
                                f"Invalid span format for keyword '{candidate_info['term']}': {span} "
                                f"(expected [start, end])"
                            )
                            continue
                        
                        start, end = span
                        if not self._verify_span_bounds(email_text, start, end):
                            warnings.append(
                                f"Keyword span [{start}:{end}] out of bounds for "
                                f"'{candidate_info['term']}' (text length: {len(email_text)})"
                            )
        
        return warnings
    
    @staticmethod
    def _verify_span_bounds(text: str, start: int, end: int) -> bool:
        """
        Verify that span [start:end] is within text bounds.
        
        Args:
            text: Full email text
            start: Start index
            end: End index
            
        Returns:
            True if span is valid, False otherwise
        """
        return 0 <= start < end <= len(text)


class SpansCoherenceVerifier:
    """
    Verify that all span arrays are well-formed and coherent.
    
    Checks:
    - Spans are [start, end] pairs
    - start < end
    - Spans are within text bounds
    """
    
    def verify(self, response: EmailTriageResponse, request: TriageRequest) -> list[str]:
        """
        Check span coherence across all keywords and evidence.
        
        Args:
            response: LLM response with spans
            request: Original request with email document
            
        Returns:
            List of warnings for span issues
        """
        warnings: list[str] = []
        
        email_text = request.email_document.body_text_canonical
        text_length = len(email_text) if email_text else 0
        
        # Check keyword spans
        for topic_idx, topic in enumerate(response.topics):
            for kw_idx, keyword in enumerate(topic.keywords_in_text):
                if keyword.spans:
                    for span_idx, span in enumerate(keyword.spans):
                        warning = self._check_span(
                            span, text_length, 
                            f"keyword '{keyword.lemma}' in topic '{topic.label_id}'"
                        )
                        if warning:
                            warnings.append(warning)
        
        # Check evidence spans
        for topic_idx, topic in enumerate(response.topics):
            for ev_idx, evidence in enumerate(topic.evidence):
                if evidence.span:
                    warning = self._check_span(
                        evidence.span, text_length,
                        f"evidence in topic '{topic.label_id}'"
                    )
                    if warning:
                        warnings.append(warning)
        
        return warnings
    
    @staticmethod
    def _check_span(span: list[int], text_length: int, context: str) -> Optional[str]:
        """
        Check if a single span is coherent.
        
        Args:
            span: [start, end] span array
            text_length: Length of the text being spanned
            context: Description of where this span comes from (for error message)
            
        Returns:
            Warning message if span is invalid, None otherwise
        """
        if not isinstance(span, list) or len(span) != 2:
            return f"Invalid span format for {context}: {span} (expected [start, end])"
        
        start, end = span
        
        if not isinstance(start, int) or not isinstance(end, int):
            return f"Span indices must be integers for {context}: [{start}, {end}]"
        
        if start >= end:
            return f"Span start >= end for {context}: [{start}, {end}]"
        
        if start < 0:
            return f"Span start < 0 for {context}: [{start}, {end}]"
        
        if end > text_length:
            return f"Span end > text length for {context}: [{start}, {end}] (text length: {text_length})"
        
        return None
