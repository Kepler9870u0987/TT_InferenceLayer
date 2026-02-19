"""
PII redaction utilities for protecting sensitive information in LLM prompts.

This module handles on-the-fly PII redaction when sending emails to external
LLM providers or when REDACT_FOR_LLM config is enabled. For self-hosted Ollama,
redaction is typically disabled (default) since there are no privacy concerns.
"""

from typing import List
import structlog

from inference_layer.models.input_models import PiiEntity


logger = structlog.get_logger(__name__)


def redact_pii_for_llm(
    text: str,
    pii_entities: List[PiiEntity],
    redact_enabled: bool = False,
    redact_types: set[str] | None = None
) -> str:
    """
    Redact PII entities from text before sending to LLM.
    
    Replaces PII spans with [REDACTED_<TYPE>] markers. Processes entities
    in reverse order (end to start) to preserve span offsets during replacement.
    
    Args:
        text: Original text with PII
        pii_entities: List of detected PII entities with type and span
        redact_enabled: Whether redaction is enabled (from config.REDACT_FOR_LLM)
        redact_types: Set of PII types to redact (e.g., {'CF', 'PHONE_IT', 'EMAIL', 'NAME'})
                     If None, redacts all types.
                     
    Returns:
        Text with PII redacted, or original text if redaction disabled
        
    Examples:
        >>> entities = [PiiEntity(type='EMAIL', hash='abc123', span=[10, 25], confidence=0.95)]
        >>> redact_pii_for_llm("My email: user@example.com.", entities, redact_enabled=True)
        "My email: [REDACTED_EMAIL]."
        
    Note:
        - If redact_enabled=False, returns text unchanged (default for self-hosted)
        - Overlapping spans: later entities in list take precedence (should not happen if preprocessing is correct)
        - Empty spans: skipped silently
    """
    if not redact_enabled:
        logger.debug("PII redaction disabled, returning original text")
        return text
    
    if not pii_entities:
        logger.debug("No PII entities to redact")
        return text
    
    # Default: redact all types if not specified
    if redact_types is None:
        redact_types = {'CF', 'PHONE_IT', 'EMAIL', 'NAME', 'IBAN', 'VAT', 'ADDRESS'}
    
    # Sort entities by span start position in reverse order (end to start)
    # This preserves offsets as we replace text
    entities_sorted = sorted(
        pii_entities,
        key=lambda e: e.span[0] if e.span and len(e.span) >= 2 else -1,
        reverse=True
    )
    
    redacted_text = text
    redaction_count = 0
    
    for entity in entities_sorted:
        # Skip if entity type not in redact list
        if entity.type not in redact_types:
            continue
        
        # Validate span
        if not entity.span or len(entity.span) < 2:
            logger.warning("Invalid span for PII entity", entity_type=entity.type, span=entity.span)
            continue
        
        start, end = entity.span
        
        # Validate span bounds
        if start < 0 or end > len(redacted_text) or start >= end:
            logger.warning(
                "Out of bounds span for PII entity",
                entity_type=entity.type,
                span=[start, end],
                text_length=len(redacted_text)
            )
            continue
        
        # Create redaction marker
        marker = f"[REDACTED_{entity.type}]"
        
        # Replace the span
        redacted_text = redacted_text[:start] + marker + redacted_text[end:]
        redaction_count += 1
        
        logger.debug(
            "Redacted PII entity",
            entity_type=entity.type,
            span=[start, end],
            original_length=end - start,
            marker=marker
        )
    
    logger.info(
        "PII redaction complete",
        total_entities=len(pii_entities),
        redacted_count=redaction_count,
        original_length=len(text),
        redacted_length=len(redacted_text)
    )
    
    return redacted_text


def redact_pii_in_candidates(
    candidates: list,
    pii_entities: List[PiiEntity],
    body_text: str,
    redact_enabled: bool = False
) -> list:
    """
    Redact PII from candidate keywords if they contain sensitive terms.
    
    This is a secondary defense: candidates should already be sanitized
    by the upstream keyword extraction pipeline, but if a PII term slipped
    through (e.g., email domain, phone fragment), we can catch it here.
    
    Args:
        candidates: List of CandidateKeyword objects
        pii_entities: Detected PII entities from email
        body_text: Full email body text (to check if candidate term overlaps PII span)
        redact_enabled: Whether redaction is enabled
        
    Returns:
        Filtered list of candidates with PII-containing terms removed
        
    Note:
        This is defensive. In production, the keyword extractor should already
        apply PII-aware filtering. This catches edge cases.
    """
    if not redact_enabled or not pii_entities:
        return candidates
    
    # Build set of PII terms (lowercased for matching)
    pii_terms = set()
    for entity in pii_entities:
        if entity.span and len(entity.span) >= 2:
            start, end = entity.span
            if 0 <= start < end <= len(body_text):
                term = body_text[start:end].lower().strip()
                if term:
                    pii_terms.add(term)
    
    if not pii_terms:
        return candidates
    
    # Filter candidates: remove if term/lemma matches a PII term
    filtered = []
    removed_count = 0
    
    for candidate in candidates:
        # Check if candidate term or lemma is a PII term
        term_lower = candidate.term.lower().strip() if hasattr(candidate, 'term') else ""
        lemma_lower = candidate.lemma.lower().strip() if hasattr(candidate, 'lemma') else ""
        
        if term_lower in pii_terms or lemma_lower in pii_terms:
            removed_count += 1
            logger.debug(
                "Removed PII candidate keyword",
                candidate_id=candidate.candidate_id if hasattr(candidate, 'candidate_id') else None,
                term=candidate.term if hasattr(candidate, 'term') else None
            )
            continue
        
        filtered.append(candidate)
    
    if removed_count > 0:
        logger.info(
            "Filtered PII from candidate keywords",
            original_count=len(candidates),
            removed_count=removed_count,
            remaining_count=len(filtered)
        )
    
    return filtered
