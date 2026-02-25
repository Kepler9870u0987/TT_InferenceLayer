"""
Keyword Enrichment: Back-fill optional KeywordInText fields from CandidateKeyword.

After Stage 3 validates that every candidateid in the LLM response exists in
the input candidates, this step merges the candidate data into the response –
filling in lemma, count, term, source and embeddingscore if the LLM omitted them.

This is purely additive (no existing LLM values are overwritten) and removes the
need for any downstream code to perform the same lookup.
"""

import structlog

from ..models.input_models import CandidateKeyword, TriageRequest
from ..models.output_models import EmailTriageResponse, KeywordInText, TopicResult

logger = structlog.get_logger(__name__)


def build_candidate_map(
    candidate_keywords: list[CandidateKeyword],
) -> dict[str, CandidateKeyword]:
    """
    Build a lookup dict from candidateid → CandidateKeyword.

    Input models use ``candidate_id`` (with underscore); output models use
    ``candidateid`` (no underscore).  We normalise here so callers don't
    have to worry about the naming asymmetry.

    Args:
        candidate_keywords: List of CandidateKeyword from the TriageRequest.

    Returns:
        Dict keyed by candidate_id string.
    """
    return {ck.candidate_id: ck for ck in candidate_keywords}


def enrich_keyword(
    keyword: KeywordInText,
    candidate: CandidateKeyword,
) -> KeywordInText:
    """
    Return a new KeywordInText with optional fields back-filled from *candidate*.

    LLM-supplied values take precedence; missing values are taken from the
    deterministic candidate.

    Args:
        keyword: Original KeywordInText from the LLM response.
        candidate: Matching CandidateKeyword from the input list.

    Returns:
        Enriched KeywordInText (new object, original is unchanged).
    """
    return keyword.model_copy(
        update={
            "lemma": keyword.lemma if keyword.lemma is not None else candidate.lemma,
            "count": keyword.count if keyword.count is not None else candidate.count,
            "term": candidate.term,          # always from candidate (ground truth)
            "source": candidate.source,      # always from candidate
            "embeddingscore": candidate.score,
        }
    )


def enrich_keywords_in_topic(
    topic: TopicResult,
    candidate_map: dict[str, CandidateKeyword],
) -> tuple[TopicResult, list[str]]:
    """
    Return a new TopicResult with all KeywordInText objects enriched.

    Args:
        topic: Original TopicResult.
        candidate_map: Lookup built by :func:`build_candidate_map`.

    Returns:
        Tuple of (enriched TopicResult, list of warning strings).
        Warnings are generated when a candidateid is not in the map (should
        have been caught by Stage 3, but we handle gracefully).
    """
    warnings: list[str] = []
    enriched_keywords: list[KeywordInText] = []

    for kw in topic.keywordsintext:
        candidate = candidate_map.get(kw.candidateid)
        if candidate is None:
            # Stage 3 should have caught this; emit a warning and keep as-is
            warnings.append(
                f"enrich_keywords: candidateid '{kw.candidateid}' not found in "
                f"candidate map (topic '{topic.labelid}') – skipping enrichment"
            )
            enriched_keywords.append(kw)
        else:
            enriched_keywords.append(enrich_keyword(kw, candidate))

    enriched_topic = topic.model_copy(update={"keywordsintext": enriched_keywords})
    return enriched_topic, warnings


def enrich_response_keywords(
    response: EmailTriageResponse,
    request: TriageRequest,
) -> tuple[EmailTriageResponse, list[str]]:
    """
    Enrich all KeywordInText objects in the full response.

    Iterates over every topic and back-fills lemma / count / term / source /
    embeddingscore from the matching CandidateKeyword.

    Args:
        response: Validated EmailTriageResponse (post Stage-3).
        request: Original TriageRequest (contains candidate_keywords).

    Returns:
        Tuple of (enriched EmailTriageResponse, accumulated warning strings).
    """
    candidate_map = build_candidate_map(request.candidate_keywords)
    all_warnings: list[str] = []
    enriched_topics: list[TopicResult] = []

    for topic in response.topics:
        enriched_topic, topic_warnings = enrich_keywords_in_topic(topic, candidate_map)
        enriched_topics.append(enriched_topic)
        all_warnings.extend(topic_warnings)

    enriched_response = response.model_copy(update={"topics": enriched_topics})

    if all_warnings:
        logger.warning(
            "Keyword enrichment produced warnings",
            warnings=all_warnings,
        )
    else:
        logger.debug(
            "Keyword enrichment completed successfully",
            topics=len(enriched_topics),
        )

    return enriched_response, all_warnings
