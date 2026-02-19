"""
Stage 4: Quality Checks.

Non-blocking quality checks that produce warnings:
- Low confidence topics/sentiment/priority
- Duplicate topics, keywords, evidence
- Incomplete data (topics without keywords/evidence)

Unlike Stages 1-3, these do NOT raise exceptions - they accumulate warnings.
"""

import structlog

from ..models.output_models import EmailTriageResponse

logger = structlog.get_logger(__name__)


class Stage4QualityChecks:
    """
    Stage 4 validator: Quality checks (non-blocking warnings).
    
    Returns list of warning strings instead of raising exceptions.
    """
    
    def __init__(self, min_confidence_threshold: float = 0.2):
        """
        Initialize quality checker.
        
        Args:
            min_confidence_threshold: Warn if topic/sentiment/priority confidence below this
        """
        self.min_confidence_threshold = min_confidence_threshold
    
    def validate(self, response: EmailTriageResponse) -> list[str]:
        """
        Run quality checks and accumulate warnings.
        
        Args:
            response: Validated EmailTriageResponse
            
        Returns:
            List of warning messages (empty if no quality issues)
        """
        warnings: list[str] = []
        
        # Check 1: Low confidence warnings
        warnings.extend(self._check_low_confidence(response))
        
        # Check 2: Duplicate detection
        warnings.extend(self._check_duplicates(response))
        
        # Check 3: Completeness checks
        warnings.extend(self._check_completeness(response))
        
        if warnings:
            logger.info(f"Stage 4: Generated {len(warnings)} quality warning(s)")
        else:
            logger.debug("Stage 4: No quality issues detected")
        
        return warnings
    
    def _check_low_confidence(self, response: EmailTriageResponse) -> list[str]:
        """
        Check for low confidence scores.
        
        Args:
            response: LLM response
            
        Returns:
            List of warnings for low confidence values
        """
        warnings: list[str] = []
        
        # Check sentiment confidence
        if response.sentiment.confidence < self.min_confidence_threshold:
            warnings.append(
                f"Low sentiment confidence: {response.sentiment.confidence:.3f} "
                f"(threshold: {self.min_confidence_threshold})"
            )
        
        # Check priority confidence
        if response.priority.confidence < self.min_confidence_threshold:
            warnings.append(
                f"Low priority confidence: {response.priority.confidence:.3f} "
                f"(threshold: {self.min_confidence_threshold})"
            )
        
        # Check topic confidences
        for i, topic in enumerate(response.topics):
            if topic.confidence < self.min_confidence_threshold:
                warnings.append(
                    f"Low confidence for topic '{topic.labelid}' at index {i}: "
                    f"{topic.confidence:.3f} (threshold: {self.min_confidence_threshold})"
                )
        
        return warnings
    
    def _check_duplicates(self, response: EmailTriageResponse) -> list[str]:
        """
        Check for duplicate topics, keywords, and evidence.
        
        Args:
            response: LLM response
            
        Returns:
            List of warnings for duplicates found
        """
        warnings: list[str] = []
        
        # Check duplicate topics (same labelid)
        topic_labels = [topic.labelid for topic in response.topics]
        seen_labels = set()
        for i, label in enumerate(topic_labels):
            if label in seen_labels:
                warnings.append(f"Duplicate topic '{label}' at index {i}")
            seen_labels.add(label)
        
        # Check duplicate keywords within each topic
        for topic_idx, topic in enumerate(response.topics):
            candidateids = [kw.candidate_id for kw in topic.keywordsintext]
            seen_ids = set()
            for kw_idx, cid in enumerate(candidateids):
                if cid in seen_ids:
                    warnings.append(
                        f"Duplicate keyword candidateid '{cid}' in topic '{topic.labelid}' "
                        f"(topic index {topic_idx}, keyword index {kw_idx})"
                    )
                seen_ids.add(cid)
        
        # Check duplicate evidence quotes within each topic
        for topic_idx, topic in enumerate(response.topics):
            quotes = [ev.quote for ev in topic.evidence]
            seen_quotes = set()
            for ev_idx, quote in enumerate(quotes):
                # Normalize for comparison (lowercase, strip whitespace)
                normalized = quote.lower().strip()
                if normalized in seen_quotes:
                    warnings.append(
                        f"Duplicate evidence quote in topic '{topic.labelid}' "
                        f"(topic index {topic_idx}, evidence index {ev_idx})"
                    )
                seen_quotes.add(normalized)
        
        return warnings
    
    def _check_completeness(self, response: EmailTriageResponse) -> list[str]:
        """
        Check for incomplete or suspicious data.
        
        Args:
            response: LLM response
            
        Returns:
            List of warnings for completeness issues
        """
        warnings: list[str] = []
        
        # Check topics without keywords
        for i, topic in enumerate(response.topics):
            if not topic.keywordsintext:
                warnings.append(
                    f"Topic '{topic.labelid}' at index {i} has no keywords"
                )
        
        # Check topics without evidence
        for i, topic in enumerate(response.topics):
            if not topic.evidence:
                warnings.append(
                    f"Topic '{topic.labelid}' at index {i} has no evidence"
                )
        
        # Check priority signals completeness
        if not response.priority.signals:
            warnings.append("Priority has no signals (expected 1-6 signals)")
        
        # Check for suspiciously long quotes (approaching max length)
        for topic_idx, topic in enumerate(response.topics):
            for ev_idx, evidence in enumerate(topic.evidence):
                if len(evidence.quote) > 180:  # Warn if > 180 chars (max is 200)
                    warnings.append(
                        f"Evidence quote is very long ({len(evidence.quote)} chars) "
                        f"in topic '{topic.labelid}' (topic index {topic_idx}, "
                        f"evidence index {ev_idx})"
                    )
        
        return warnings

