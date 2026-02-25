"""
Unit tests for span_calculator.py – server-side evidence span computation.
"""

import pytest

from inference_layer.validation.span_calculator import (
    STATUS_EXACT,
    STATUS_FUZZY,
    STATUS_NOT_FOUND,
    compute_span_from_quote,
    enrich_evidence_item,
    enrich_response_spans,
    sha256_text,
)
from inference_layer.models.output_models import EvidenceItem


# ---------------------------------------------------------------------------
# compute_span_from_quote
# ---------------------------------------------------------------------------

class TestComputeSpanFromQuote:
    """Unit tests for the core span-finding function."""

    def test_exact_match_returns_correct_span(self):
        text = "Volevo confermare che i dati sono corretti: Codice Fiscale: RSSMRA80A01H501U"
        quote = "Codice Fiscale: RSSMRA80A01H501U"
        span, status = compute_span_from_quote(quote, text)

        assert status == STATUS_EXACT
        assert span is not None
        assert text[span[0] : span[1]] == quote

    def test_exact_match_start_of_text(self):
        text = "Contratto di fornitura scaduto il 31/01/2026"
        quote = "Contratto di fornitura"
        span, status = compute_span_from_quote(quote, text)

        assert status == STATUS_EXACT
        assert span == (0, len(quote))

    def test_exact_match_end_of_text(self):
        text = "La pratica è stata risolta correttamente."
        quote = "risolta correttamente."
        span, status = compute_span_from_quote(quote, text)

        assert status == STATUS_EXACT
        assert text[span[0] : span[1]] == quote

    def test_case_insensitive_exact_match(self):
        text = "CONTRATTO DI SERVIZIO in scadenza"
        quote = "contratto di servizio"
        span, status = compute_span_from_quote(quote, text)

        # Case-insensitive still yields EXACT status
        assert status == STATUS_EXACT
        assert span is not None
        assert span[0] == 0

    def test_fuzzy_match_extra_whitespace(self):
        body = "Codice  Fiscale non trovato"  # double space
        quote = "Codice Fiscale non trovato"  # single space
        span, status = compute_span_from_quote(quote, body)

        # Should fall back to fuzzy (exact won't find it)
        assert status in (STATUS_FUZZY, STATUS_EXACT)

    def test_not_found_returns_none_status(self):
        text = "Buongiorno, le scrivo riguardo alla fattura."
        quote = "questa frase non esiste nel testo"
        span, status = compute_span_from_quote(quote, text)

        assert status == STATUS_NOT_FOUND
        assert span is None

    def test_empty_quote_returns_not_found(self):
        span, status = compute_span_from_quote("", "qualsiasi testo")
        assert status == STATUS_NOT_FOUND
        assert span is None

    def test_empty_text_returns_not_found(self):
        span, status = compute_span_from_quote("some quote", "")
        assert status == STATUS_NOT_FOUND
        assert span is None

    def test_span_boundaries_are_correct(self):
        """Verify span[0]:span[1] always extracts something similar to the quote."""
        text = "Il contratto è scaduto il mese scorso e richiedo un rinnovo urgente."
        quote = "contratto è scaduto il mese scorso"
        span, status = compute_span_from_quote(quote, text)

        assert status == STATUS_EXACT
        extracted = text[span[0] : span[1]]
        assert extracted == quote

    def test_multiple_occurrences_returns_first(self):
        text = "test test test"
        quote = "test"
        span, status = compute_span_from_quote(quote, text)

        assert status == STATUS_EXACT
        assert span == (0, 4)


# ---------------------------------------------------------------------------
# sha256_text
# ---------------------------------------------------------------------------

class TestSha256Text:
    def test_returns_64_char_hex(self):
        digest = sha256_text("hello world")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_deterministic(self):
        assert sha256_text("fixed input") == sha256_text("fixed input")

    def test_different_inputs_different_digests(self):
        assert sha256_text("abc") != sha256_text("xyz")


# ---------------------------------------------------------------------------
# enrich_evidence_item
# ---------------------------------------------------------------------------

class TestEnrichEvidenceItem:
    def test_exact_match_populates_all_fields(self):
        text = "Vorrei informazioni sul contratto di assistenza."
        text_hash = sha256_text(text)
        quote = "informazioni sul contratto"
        ev = EvidenceItem(quote=quote)

        enriched = enrich_evidence_item(ev, text, text_hash)

        assert enriched.span_status == STATUS_EXACT
        assert enriched.span is not None
        assert text[enriched.span[0] : enriched.span[1]] == quote
        assert enriched.span_llm is None          # LLM provided no span
        assert enriched.text_hash == text_hash

    def test_llm_span_preserved_as_span_llm(self):
        text = "Ho ricevuto la fattura numero 1234."
        text_hash = sha256_text(text)
        ev = EvidenceItem(quote="fattura numero 1234", span=(14, 30))  # LLM guess

        enriched = enrich_evidence_item(ev, text, text_hash)

        # Server always re-computes span; LLM original stays in span_llm
        assert enriched.span_llm == (14, 30)
        assert enriched.span_status in (STATUS_EXACT, STATUS_FUZZY, STATUS_NOT_FOUND)

    def test_not_found_quote_yields_none_span(self):
        text = "Testo completamente diverso."
        text_hash = sha256_text(text)
        ev = EvidenceItem(quote="questa frase non c'è")

        enriched = enrich_evidence_item(ev, text, text_hash)

        assert enriched.span is None
        assert enriched.span_status == STATUS_NOT_FOUND
        assert enriched.text_hash == text_hash

    def test_original_evidence_not_mutated(self):
        text = "Il reclamo è stato registrato."
        ev = EvidenceItem(quote="reclamo è stato")
        enrich_evidence_item(ev, text, sha256_text(text))
        # Original object untouched
        assert ev.span is None
        assert ev.span_status is None


# ---------------------------------------------------------------------------
# enrich_response_spans  (integration via real EmailTriageResponse)
# ---------------------------------------------------------------------------

class TestEnrichResponseSpans:
    """Integration tests using real Pydantic models."""

    def _make_request(self, body_text: str):
        """Create a minimal TriageRequest with the given body text."""
        from datetime import datetime
        from inference_layer.models.input_models import (
            EmailDocument,
            CandidateKeyword,
            TriageRequest,
            InputPipelineVersion,
        )

        email = EmailDocument(
            uid="test_uid",
            mailbox="INBOX",
            message_id="<test@example.com>",
            fetched_at=datetime.now(),
            size=100,
            from_addr_redacted="sender@example.com",
            to_addrs_redacted=["support@example.com"],
            subject_canonical="Test",
            date_parsed="Thu, 1 Jan 2026 12:00:00 +0000",
            headers_canonical={},
            body_text_canonical=body_text,
            body_original_hash="hash",
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
        candidate = CandidateKeyword(
            candidate_id="cid_001",
            term="contratto",
            lemma="contratto",
            count=2,
            source="body",
            score=0.9,
        )
        return TriageRequest(
            email=email,
            candidate_keywords=[candidate],
            dictionary_version=1,
        )

    def _make_response(self, quote: str):
        """Create a minimal EmailTriageResponse with one evidence item."""
        from inference_layer.models.output_models import (
            EmailTriageResponse,
            EvidenceItem,
            KeywordInText,
            PriorityResult,
            SentimentResult,
            TopicResult,
        )

        return EmailTriageResponse(
            dictionaryversion=1,
            sentiment=SentimentResult(value="neutral", confidence=0.8),
            priority=PriorityResult(value="medium", confidence=0.7, signals=["test"]),
            topics=[
                TopicResult(
                    labelid="CONTRATTO",
                    confidence=0.9,
                    keywordsintext=[
                        KeywordInText(candidateid="cid_001"),
                    ],
                    evidence=[EvidenceItem(quote=quote)],
                )
            ],
        )

    def test_exact_match_no_warnings(self):
        body = "Ho bisogno di rinnovare il contratto di assistenza."
        quote = "rinnovare il contratto"
        request = self._make_request(body)
        response = self._make_response(quote)

        enriched, warnings = enrich_response_spans(response, request)

        ev = enriched.topics[0].evidence[0]
        assert ev.span_status == STATUS_EXACT
        assert ev.span is not None
        assert body[ev.span[0] : ev.span[1]] == quote
        assert ev.text_hash == sha256_text(body)
        assert warnings == []

    def test_not_found_generates_warning(self):
        body = "Testo completamente diverso."
        quote = "questa frase non esiste"
        request = self._make_request(body)
        response = self._make_response(quote)

        enriched, warnings = enrich_response_spans(response, request)

        ev = enriched.topics[0].evidence[0]
        assert ev.span_status == STATUS_NOT_FOUND
        assert ev.span is None
        assert len(warnings) == 1
        assert "not found" in warnings[0]

    def test_empty_body_text_all_not_found(self):
        request = self._make_request("")
        response = self._make_response("qualsiasi quote")

        enriched, warnings = enrich_response_spans(response, request)

        ev = enriched.topics[0].evidence[0]
        assert ev.span_status == STATUS_NOT_FOUND
