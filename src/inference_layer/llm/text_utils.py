"""
Text processing utilities for the LLM layer.

Provides intelligent truncation and PII span adjustment functions
to prepare email text for LLM consumption while preserving semantic
coherence and maintaining PII entity tracking.
"""

import re
from typing import Optional


def truncate_at_sentence_boundary(text: str, max_chars: int) -> str:
    """
    Truncate text at the nearest sentence boundary before max_chars.
    
    Preserves complete sentences to maintain semantic coherence for the LLM.
    Looks for sentence-ending punctuation (. ! ?) followed by whitespace or end.
    
    Args:
        text: Text to truncate
        max_chars: Maximum character count
        
    Returns:
        Truncated text ending at a sentence boundary, or hard-truncated if
        no sentence boundary found within the limit.
        
    Examples:
        >>> truncate_at_sentence_boundary("Hello. World. Test.", 15)
        "Hello. World."
        >>> truncate_at_sentence_boundary("No period here", 10)
        "No period "
    """
    if len(text) <= max_chars:
        return text
    
    # Look for sentence boundaries: . ! ? followed by space/newline or at end
    # Search within the first max_chars characters
    truncated_segment = text[:max_chars]
    
    # Find all sentence-ending positions (punctuation + whitespace/end)
    # Pattern: sentence-ending punctuation followed by space/newline/end
    sentence_end_pattern = r'[.!?](?:\s|$)'
    matches = list(re.finditer(sentence_end_pattern, truncated_segment))
    
    if matches:
        # Take the last sentence boundary found
        last_match = matches[-1]
        # Include the punctuation, exclude trailing whitespace
        cutoff = last_match.end()
        # If the match ends with whitespace, don't include it
        if truncated_segment[cutoff - 1:cutoff].isspace():
            cutoff -= 1
        return text[:cutoff]
    
    # No sentence boundary found - hard truncate at max_chars
    # Try to at least avoid cutting a word in half
    # Look for last space before max_chars
    last_space = truncated_segment.rfind(' ')
    if last_space > max_chars * 0.8:  # At least 80% of desired length
        return text[:last_space]
    
    # No good word boundary either - hard cut
    return text[:max_chars]


def adjust_pii_spans_after_truncation(
    pii_entities: list,
    truncated_length: int,
    original_text: str,
    truncated_text: str
) -> list:
    """
    Filter and adjust PII entities after text truncation.
    
    Removes entities that fall completely outside the truncated text.
    Adjusts entities that are partially truncated (though this should be rare
    with sentence boundary truncation).
    
    Args:
        pii_entities: List of PII entity objects with 'span' attribute [start, end]
        truncated_length: Length of truncated text
        original_text: Original text before truncation (for validation)
        truncated_text: Text after truncation
        
    Returns:
        Filtered list of PII entities that are fully or partially within
        the truncated text. Partially cut entities are adjusted to fit.
        
    Note:
        With sentence-boundary truncation, partial cuts should be rare.
        Most PII entities will be either fully included or fully excluded.
    """
    if not pii_entities:
        return []
    
    adjusted_entities = []
    
    for entity in pii_entities:
        # Each entity has a 'span' attribute: [start, end]
        # Using hasattr to be defensive (duck typing)
        if not hasattr(entity, 'span') or not entity.span:
            # Skip entities without valid span
            continue
            
        start, end = entity.span
        
        # Entity completely before truncation point - keep as is
        if end <= truncated_length:
            adjusted_entities.append(entity)
            continue
        
        # Entity starts after truncation point - exclude
        if start >= truncated_length:
            continue
        
        # Entity straddles truncation boundary (start < truncated_length < end)
        # This is rare with sentence boundary truncation but handle it
        # Adjust the entity's end to match truncation point
        # Note: We create a copy with adjusted span, not mutate original
        try:
            # Try to create a copy with updated span
            # This assumes entity is a Pydantic model or has model_copy
            if hasattr(entity, 'model_copy'):
                adjusted_entity = entity.model_copy(update={'span': [start, truncated_length]})
                adjusted_entities.append(adjusted_entity)
            else:
                # Fallback: just include original (better than losing it)
                adjusted_entities.append(entity)
        except Exception:
            # If copy fails, include original entity
            # This is defensive - validation layer will catch issues
            adjusted_entities.append(entity)
    
    return adjusted_entities


def count_tokens_approximate(text: str) -> int:
    """
    Rough approximation of token count for text.
    
    Uses simple heuristic: ~4 characters per token for English,
    ~3 characters per token for Italian (more inflection).
    
    This is NOT accurate but sufficient for pre-flight checks
    (e.g., ensuring we're not sending 20K tokens to a 4K context model).
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Approximate token count
        
    Note:
        For accurate counts, need tokenizer from the specific model.
        This is just a sanity check.
    """
    # Very rough heuristic: Italian has more inflection than English
    # so words tend to be longer but semantic density is similar
    # Use conservative estimate: 3.5 chars per token
    return max(1, len(text) // 3)
