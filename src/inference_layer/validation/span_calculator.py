"""
Span Calculator: Server-side computation of quote offsets in the canonical body.

The LLM produces free-text *quotes* as evidence for each topic.  Rather than
trusting the LLM to supply accurate character offsets (it cannot reliably do
so), we compute spans deterministically here using:

1. Exact substring search (``str.find``).
2. Difflib fuzzy match as fallback when the quote contains minor whitespace /
   punctuation differences.

The original LLM span (if present in the response) is preserved in
``EvidenceItem.span_llm`` for audit purposes.  The authoritative span is
stored in ``EvidenceItem.span`` and its quality is recorded in
``EvidenceItem.span_status``.
"""

from __future__ import annotations

import hashlib
import structlog
from difflib import SequenceMatcher
from typing import Optional

from ..models.input_models import TriageRequest
from ..models.output_models import EmailTriageResponse, EvidenceItem, TopicResult

logger = structlog.get_logger(__name__)

# Minimum fuzzy-match ratio to accept a span
FUZZY_MATCH_THRESHOLD = 0.85

# Extra characters added around the quote length when scanning fuzzy windows
FUZZY_WINDOW_EXTRA = 20

# Span status constants
STATUS_EXACT = "exact_match"
STATUS_FUZZY = "fuzzy_match"
STATUS_NOT_FOUND = "not_found"


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of *text* (UTF-8 encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_span_from_quote(
    quote: str,
    text: str,
) -> tuple[Optional[tuple[int, int]], str]:
    """
    Find the character offset of *quote* in *text*.

    Strategy
    --------
    1. Exact case-sensitive search – ``text.find(quote)``.
    2. Exact case-insensitive search using lower-cased copies.
    3. Difflib sliding-window fuzzy match (threshold :data:`FUZZY_MATCH_THRESHOLD`).

    Args:
        quote: The evidence quote string from the LLM.
        text:  The canonical email body text to search in.

    Returns:
        ``(span, status)`` where *span* is ``(start, end)`` or ``None`` if
        not found, and *status* is one of :data:`STATUS_EXACT`,
        :data:`STATUS_FUZZY`, :data:`STATUS_NOT_FOUND`.
    """
    if not quote or not text:
        return None, STATUS_NOT_FOUND

    # 1. Exact match (case-sensitive)
    start = text.find(quote)
    if start != -1:
        return (start, start + len(quote)), STATUS_EXACT

    # 2. Case-insensitive exact match
    text_lower = text.lower()
    quote_lower = quote.lower()
    start = text_lower.find(quote_lower)
    if start != -1:
        return (start, start + len(quote)), STATUS_EXACT

    # 3. Fuzzy sliding-window match
    q_len = len(quote)
    window_size = q_len + FUZZY_WINDOW_EXTRA
    best_ratio = 0.0
    best_span: Optional[tuple[int, int]] = None

    for i in range(max(0, len(text) - q_len + 1)):
        window = text[i : i + window_size]
        ratio = SequenceMatcher(None, quote_lower, window.lower(), autojunk=False).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_span = (i, i + q_len)

    if best_ratio >= FUZZY_MATCH_THRESHOLD and best_span is not None:
        return best_span, STATUS_FUZZY

    return None, STATUS_NOT_FOUND


def enrich_evidence_item(
    evidence: EvidenceItem,
    text: str,
    text_hash: str,
) -> EvidenceItem:
    """
    Return a new :class:`EvidenceItem` with server-computed span fields.

    - ``span``        ← server-computed offset (replaces LLM guess).
    - ``span_llm``    ← original LLM span preserved for audit.
    - ``span_status`` ← quality of the match.
    - ``text_hash``   ← SHA-256 of the text used for reproducibility.

    Args:
        evidence:  Original EvidenceItem from the LLM response.
        text:      Canonical body text to search in.
        text_hash: Pre-computed SHA-256 of *text* (avoid re-hashing per item).

    Returns:
        Enriched EvidenceItem (new object, original unchanged).
    """
    computed_span, status = compute_span_from_quote(evidence.quote, text)

    return evidence.model_copy(
        update={
            "span": computed_span,
            "span_llm": evidence.span,   # preserve whatever the LLM supplied
            "span_status": status,
            "text_hash": text_hash,
        }
    )


def enrich_evidence_in_topic(
    topic: TopicResult,
    text: str,
    text_hash: str,
) -> tuple[TopicResult, list[str]]:
    """
    Return a new TopicResult with all EvidenceItem spans computed server-side.

    Args:
        topic:     Original TopicResult.
        text:      Canonical email body text.
        text_hash: SHA-256 of *text*.

    Returns:
        Tuple of (enriched TopicResult, list of warning strings for not-found quotes).
    """
    warnings: list[str] = []
    enriched_evidence: list[EvidenceItem] = []

    for ev in topic.evidence:
        enriched = enrich_evidence_item(ev, text, text_hash)
        enriched_evidence.append(enriched)

        if enriched.span_status == STATUS_NOT_FOUND:
            warnings.append(
                f"span_calculator: quote not found in text for topic "
                f"'{topic.labelid}': '{ev.quote[:80]}...'"
                if len(ev.quote) > 80
                else f"span_calculator: quote not found in text for topic "
                f"'{topic.labelid}': '{ev.quote}'"
            )

    enriched_topic = topic.model_copy(update={"evidence": enriched_evidence})
    return enriched_topic, warnings


def enrich_response_spans(
    response: EmailTriageResponse,
    request: TriageRequest,
) -> tuple[EmailTriageResponse, list[str]]:
    """
    Compute server-side spans for all evidence items in the full response.

    Args:
        response: Validated (and already keyword-enriched) EmailTriageResponse.
        request:  Original TriageRequest (contains the canonical body text).

    Returns:
        Tuple of (span-enriched EmailTriageResponse, accumulated warning strings).
    """
    text = request.email.body_text_canonical or ""
    text_hash = sha256_text(text) if text else ""

    all_warnings: list[str] = []
    enriched_topics: list[TopicResult] = []

    for topic in response.topics:
        enriched_topic, topic_warnings = enrich_evidence_in_topic(topic, text, text_hash)
        enriched_topics.append(enriched_topic)
        all_warnings.extend(topic_warnings)

    enriched_response = response.model_copy(update={"topics": enriched_topics})

    exact = fuzzy = not_found = 0
    for topic in enriched_response.topics:
        for ev in topic.evidence:
            if ev.span_status == STATUS_EXACT:
                exact += 1
            elif ev.span_status == STATUS_FUZZY:
                fuzzy += 1
            else:
                not_found += 1

    logger.info(
        "Span enrichment completed",
        exact_match=exact,
        fuzzy_match=fuzzy,
        not_found=not_found,
    )

    return enriched_response, all_warnings
