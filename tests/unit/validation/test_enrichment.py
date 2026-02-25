"""
Unit tests for enrichment.py – keyword back-filling from CandidateKeyword.
"""

import pytest
from datetime import datetime

from inference_layer.models.enums import TopicsEnum
from inference_layer.models.input_models import (
    CandidateKeyword,
    EmailDocument,
    InputPipelineVersion,
    TriageRequest,
)
from inference_layer.models.output_models import (
    EmailTriageResponse,
    EvidenceItem,
    KeywordInText,
    PriorityResult,
    SentimentResult,
    TopicResult,
)
from inference_layer.validation.enrichment import (
    build_candidate_map,
    enrich_keyword,
    enrich_keywords_in_topic,
    enrich_response_keywords,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candidate(
    candidate_id: str = "cid_001",
    term: str = "contratto",
    lemma: str = "contratto",
    count: int = 3,
    source: str = "body",
    score: float = 0.9,
) -> CandidateKeyword:
    return CandidateKeyword(
        candidate_id=candidate_id,
        term=term,
        lemma=lemma,
        count=count,
        source=source,
        score=score,
    )


def make_keyword(
    candidateid: str = "cid_001",
    lemma: str | None = None,
    count: int | None = None,
) -> KeywordInText:
    return KeywordInText(candidateid=candidateid, lemma=lemma, count=count)


def make_topic(keywords: list[KeywordInText]) -> TopicResult:
    return TopicResult(
        labelid="CONTRATTO",
        confidence=0.9,
        keywordsintext=keywords,
        evidence=[EvidenceItem(quote="contratto di fornitura")],
    )


def make_request(candidates: list[CandidateKeyword]) -> TriageRequest:
    email = EmailDocument(
        uid="uid_test",
        mailbox="INBOX",
        message_id="<test@example.com>",
        fetched_at=datetime.now(),
        size=200,
        from_addr_redacted="a@b.com",
        to_addrs_redacted=["c@d.com"],
        subject_canonical="Subject",
        date_parsed="Thu, 1 Jan 2026 12:00:00 +0000",
        headers_canonical={},
        body_text_canonical="Il contratto è in scadenza.",
        body_original_hash="x",
        pii_entities=[],
        removed_sections=[],
        pipeline_version=InputPipelineVersion(
            parser_version="1.0",
            canonicalization_version="1.0",
            ner_model_version="1.0",
            pii_redaction_version="1.0",
        ),
        processing_timestamp=datetime.now(),
        processing_duration_ms=50,
    )
    return TriageRequest(
        email=email,
        candidate_keywords=candidates,
        dictionary_version=1,
    )


def make_response(topics: list[TopicResult]) -> EmailTriageResponse:
    return EmailTriageResponse(
        dictionaryversion=1,
        sentiment=SentimentResult(value="neutral", confidence=0.8),
        priority=PriorityResult(value="medium", confidence=0.7, signals=["test"]),
        topics=topics,
    )


# ---------------------------------------------------------------------------
# build_candidate_map
# ---------------------------------------------------------------------------

class TestBuildCandidateMap:
    def test_maps_candidate_id_to_candidate(self):
        c1 = make_candidate("cid_001")
        c2 = make_candidate("cid_002", term="garanzia", lemma="garanzia")
        result = build_candidate_map([c1, c2])

        assert "cid_001" in result
        assert "cid_002" in result
        assert result["cid_001"] is c1
        assert result["cid_002"] is c2

    def test_empty_list_returns_empty_dict(self):
        assert build_candidate_map([]) == {}


# ---------------------------------------------------------------------------
# enrich_keyword
# ---------------------------------------------------------------------------

class TestEnrichKeyword:
    def test_missing_lemma_filled_from_candidate(self):
        candidate = make_candidate(lemma="contratto")
        kw = make_keyword(lemma=None)

        enriched = enrich_keyword(kw, candidate)

        assert enriched.lemma == "contratto"

    def test_llm_lemma_preserved_when_present(self):
        candidate = make_candidate(lemma="contratto_candidate")
        kw = make_keyword(lemma="contratto_llm")

        enriched = enrich_keyword(kw, candidate)

        # LLM value wins
        assert enriched.lemma == "contratto_llm"

    def test_missing_count_filled_from_candidate(self):
        candidate = make_candidate(count=5)
        kw = make_keyword(count=None)

        enriched = enrich_keyword(kw, candidate)

        assert enriched.count == 5

    def test_llm_count_preserved_when_present(self):
        candidate = make_candidate(count=5)
        kw = make_keyword(count=2)

        enriched = enrich_keyword(kw, candidate)

        assert enriched.count == 2

    def test_term_source_embeddingscore_always_from_candidate(self):
        candidate = make_candidate(term="contratto_term", source="subject", score=0.88)
        kw = make_keyword()

        enriched = enrich_keyword(kw, candidate)

        assert enriched.term == "contratto_term"
        assert enriched.source == "subject"
        assert enriched.embeddingscore == pytest.approx(0.88)

    def test_original_keyword_not_mutated(self):
        candidate = make_candidate()
        kw = make_keyword(lemma=None, count=None)

        enrich_keyword(kw, candidate)

        # Original unchanged
        assert kw.lemma is None
        assert kw.count is None


# ---------------------------------------------------------------------------
# enrich_keywords_in_topic
# ---------------------------------------------------------------------------

class TestEnrichKeywordsInTopic:
    def test_all_keywords_enriched(self):
        c1 = make_candidate("cid_001", term="contratto", lemma="contratto", count=3)
        c2 = make_candidate("cid_002", term="garanzia", lemma="garanzia", count=1, score=0.75)
        cmap = build_candidate_map([c1, c2])

        kw1 = make_keyword("cid_001")
        kw2 = make_keyword("cid_002")
        topic = make_topic([kw1, kw2])

        enriched_topic, warnings = enrich_keywords_in_topic(topic, cmap)

        assert warnings == []
        assert enriched_topic.keywordsintext[0].term == "contratto"
        assert enriched_topic.keywordsintext[1].term == "garanzia"

    def test_missing_candidateid_generates_warning_and_keeps_keyword(self):
        cmap = build_candidate_map([make_candidate("cid_001")])
        kw_valid = make_keyword("cid_001")
        kw_missing = make_keyword("cid_MISSING")
        topic = make_topic([kw_valid, kw_missing])

        enriched_topic, warnings = enrich_keywords_in_topic(topic, cmap)

        assert len(warnings) == 1
        assert "cid_MISSING" in warnings[0]
        # Missing keyword is kept as-is
        assert enriched_topic.keywordsintext[1].candidateid == "cid_MISSING"
        # Valid keyword is enriched
        assert enriched_topic.keywordsintext[0].term == "contratto"


# ---------------------------------------------------------------------------
# enrich_response_keywords  (full response integration)
# ---------------------------------------------------------------------------

class TestEnrichResponseKeywords:
    def test_response_keywords_enriched_end_to_end(self):
        candidate = make_candidate("cid_001", lemma="contratto", count=2, score=0.95)
        request = make_request([candidate])

        kw = make_keyword("cid_001", lemma=None, count=None)
        topic = make_topic([kw])
        response = make_response([topic])

        enriched_response, warnings = enrich_response_keywords(response, request)

        ek = enriched_response.topics[0].keywordsintext[0]
        assert ek.lemma == "contratto"
        assert ek.count == 2
        assert ek.term == "contratto"
        assert ek.source == "body"
        assert ek.embeddingscore == pytest.approx(0.95)
        assert warnings == []

    def test_multiple_topics_all_enriched(self):
        c1 = make_candidate("cid_001", term="contratto")
        c2 = make_candidate("cid_002", term="garanzia", lemma="garanzia")
        request = make_request([c1, c2])

        t1 = make_topic([make_keyword("cid_001")])
        t2 = TopicResult(
            labelid="GARANZIA",
            confidence=0.8,
            keywordsintext=[make_keyword("cid_002")],
            evidence=[EvidenceItem(quote="garanzia scaduta")],
        )
        response = make_response([t1, t2])

        enriched_response, warnings = enrich_response_keywords(response, request)

        assert enriched_response.topics[0].keywordsintext[0].term == "contratto"
        assert enriched_response.topics[1].keywordsintext[0].term == "garanzia"
        assert warnings == []

    def test_unknown_candidateid_produces_warning(self):
        candidate = make_candidate("cid_001")
        request = make_request([candidate])

        kw_bad = make_keyword("cid_UNKNOWN")
        topic = make_topic([kw_bad])
        response = make_response([topic])

        _, warnings = enrich_response_keywords(response, request)

        assert len(warnings) == 1
        assert "cid_UNKNOWN" in warnings[0]

    def test_original_response_not_mutated(self):
        candidate = make_candidate("cid_001")
        request = make_request([candidate])
        kw = make_keyword("cid_001", lemma=None)
        topic = make_topic([kw])
        response = make_response([topic])

        enrich_response_keywords(response, request)

        # Original model objects unchanged
        assert response.topics[0].keywordsintext[0].lemma is None
