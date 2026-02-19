"""
Input data models for LLM Inference Layer.

These models represent the canonicalized email document received from the
upstream preprocessing layer, plus candidate keywords and request configuration.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class PiiEntity(BaseModel):
    """
    PII entity detected and annotated in the email text.
    
    NOTE: PII are NOT redacted in the input body by default - they are only
    annotated. Redaction happens on-the-fly if REDACT_FOR_LLM=true or before storage.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    type: str = Field(..., description="PII type (CF, PHONE_IT, EMAIL, NAME, ORG, etc.)")
    original_hash: str = Field(..., description="Hash of original PII value")
    redacted: str = Field(..., description="The detected PII value (for matching)")
    span_start: int = Field(..., ge=0, description="Start position in body text")
    span_end: int = Field(..., ge=0, description="End position in body text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    detection_method: str = Field(..., description="Method used to detect PII (regex, ner, etc.)")


class RemovedSection(BaseModel):
    """Section removed during canonicalization (quotes, signatures, disclaimers)."""
    
    model_config = ConfigDict(extra="forbid")
    
    type: str = Field(..., description="Type of removed section (quote_standard, signature_separator, etc.)")
    span_start: int = Field(..., ge=0)
    span_end: int = Field(..., ge=0)
    content_preview: str = Field(..., description="Preview of removed content")
    confidence: float = Field(..., ge=0.0, le=1.0)


class InputPipelineVersion(BaseModel):
    """
    Pipeline version information from upstream preprocessing layer.
    
    These versions are incorporated into the full PipelineVersion for audit.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    parser_version: str
    canonicalization_version: str
    ner_model_version: str
    pii_redaction_version: str


class EmailDocument(BaseModel):
    """
    Canonicalized email document from preprocessing layer.
    
    This is the input to the LLM inference layer. The body_text_canonical
    field contains the cleaned text (with PII annotations, not redacted).
    """
    
    model_config = ConfigDict(extra="forbid")
    
    # Email metadata
    uid: str = Field(..., description="IMAP UID or unique identifier")
    uidvalidity: Optional[str] = Field(None, description="IMAP UIDVALIDITY")
    mailbox: str = Field(..., description="Source mailbox (e.g., INBOX)")
    message_id: str = Field(..., description="RFC5322 Message-ID header")
    fetched_at: datetime = Field(..., description="Timestamp when email was fetched")
    size: int = Field(..., ge=0, description="Email size in bytes")
    
    # Email headers (canonical)
    from_addr_redacted: str = Field(..., description="From address (may be redacted)")
    to_addrs_redacted: list[str] = Field(..., description="To addresses (may be redacted)")
    subject_canonical: str = Field(..., description="Canonicalized subject line")
    date_parsed: str = Field(..., description="Parsed email date")
    headers_canonical: dict[str, Any] = Field(..., description="Canonical headers dict")
    
    # Email body (canonical, NOT redacted by default)
    body_text_canonical: str = Field(..., description="Cleaned body text (PII annotated, not redacted)")
    body_html_canonical: str = Field(default="", description="HTML body if available")
    body_original_hash: str = Field(..., description="Hash of original body for integrity check")
    
    # Removed sections (quotes, signatures)
    removed_sections: list[RemovedSection] = Field(
        default_factory=list,
        description="Sections removed during canonicalization"
    )
    
    # PII annotations (NOT redacted in body text)
    pii_entities: list[PiiEntity] = Field(
        default_factory=list,
        description="PII entities detected and annotated (not redacted in body)"
    )
    
    # Upstream pipeline version
    pipeline_version: InputPipelineVersion = Field(..., description="Preprocessing pipeline version")
    
    # Processing metadata
    processing_timestamp: datetime = Field(..., description="When preprocessing was completed")
    processing_duration_ms: int = Field(..., ge=0, description="Preprocessing duration in milliseconds")


class CandidateKeyword(BaseModel):
    """
    Candidate keyword generated deterministically from email text.
    
    The LLM MUST select keywords only from this list (no invention allowed).
    Each keyword has a stable candidate_id that links back to the dictionary.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    candidate_id: str = Field(
        ...,
        description="Stable hash ID: stableid(source, term). Used to prevent keyword invention."
    )
    term: str = Field(..., description="Original term as it appears in text")
    lemma: str = Field(..., description="Lemmatized form of the term")
    count: int = Field(..., ge=1, description="Frequency count in the email")
    source: str = Field(..., description="Source of the keyword (subject, body, etc.)")
    score: float = Field(..., ge=0.0, description="Composite score (frequency + semantic relevance)")


class TriageRequest(BaseModel):
    """
    Complete triage request: email + candidate keywords + configuration.
    
    This is the top-level request sent to the /triage endpoint.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    email: EmailDocument = Field(..., description="Canonicalized email document")
    candidate_keywords: list[CandidateKeyword] = Field(
        ...,
        min_length=1,
        description="Deterministically generated candidate keywords (top-N)"
    )
    dictionary_version: int = Field(
        ...,
        ge=1,
        description="Dictionary version (frozen during batch processing)"
    )
    config_overrides: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional config overrides (body_truncation_limit, top_n, etc.)"
    )
