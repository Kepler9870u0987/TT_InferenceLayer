"""
Output data models for LLM Inference Layer.

These models define the structured output returned by the LLM and validated
by the multi-stage validation pipeline. They must conform to the strict
JSON Schema (email_triage_v2).
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

from inference_layer.models.enums import TopicsEnum, SentimentEnum, PriorityEnum
from inference_layer.models.pipeline_version import PipelineVersion


class KeywordInText(BaseModel):
    """
    A keyword selected by the LLM from the candidate list, anchored to the text.
    
    CRITICAL: candidateid MUST exist in the input candidate_keywords list.
    The LLM is NOT allowed to invent keywords.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    candidateid: str = Field(
        ...,
        description="Candidate ID from input list - MUST NOT be invented"
    )
    lemma: str = Field(..., description="Lemmatized form of the keyword")
    count: int = Field(..., ge=1, description="Number of occurrences in the email")
    spans: Optional[list[tuple[int, int]]] = Field(
        default=None,
        description="Optional: positions in text where keyword appears [(start, end), ...]"
    )


class EvidenceItem(BaseModel):
    """
    A short quote from the email text supporting a topic classification.
    
    The quote MUST be present in the canonical body text (verified by evidence_presence_check).
    """
    
    model_config = ConfigDict(extra="forbid")
    
    quote: str = Field(
        ...,
        max_length=200,
        description="Short text excerpt supporting the topic (≤200 chars)"
    )
    span: Optional[tuple[int, int]] = Field(
        default=None,
        description="Optional: (start, end) position of quote in body_text_canonical"
    )


class TopicResult(BaseModel):
    """
    A single topic classification with anchored keywords and evidence.
    
    Each email can have 1-5 topics. At least one topic is required (use UNKNOWNTOPIC if needed).
    """
    
    model_config = ConfigDict(extra="forbid")
    
    labelid: TopicsEnum = Field(..., description="Topic label from closed taxonomy")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence")
    keywordsintext: list[KeywordInText] = Field(
        ...,
        min_length=1,
        max_length=15,
        description="Keywords selected from candidates (1-15 per topic)"
    )
    evidence: list[EvidenceItem] = Field(
        ...,
        min_length=1,
        max_length=2,
        description="Supporting quotes from email text (1-2 per topic)"
    )


class SentimentResult(BaseModel):
    """Sentiment classification (single-label)."""
    
    model_config = ConfigDict(extra="forbid")
    
    value: SentimentEnum = Field(..., description="Sentiment label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence")


class PriorityResult(BaseModel):
    """
    Priority classification with audit signals.
    
    Signals are short phrases explaining why this priority was assigned.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    value: PriorityEnum = Field(..., description="Priority label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence")
    signals: list[str] = Field(
        ...,
        max_length=6,
        description="Short phrases explaining priority (max 6)"
    )


class EmailTriageResponse(BaseModel):
    """
    Complete structured output from the LLM.
    
    This is the direct output that must conform to JSON Schema email_triage_v2.
    It undergoes multi-stage validation before being accepted.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    dictionaryversion: int = Field(
        ...,
        ge=1,
        description="Dictionary version - must match input dictionary_version"
    )
    sentiment: SentimentResult = Field(..., description="Sentiment classification")
    priority: PriorityResult = Field(..., description="Priority classification")
    topics: list[TopicResult] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Multi-label topic classification (1-5 topics)"
    )


class TriageResult(BaseModel):
    """
    Complete triage result including output, metadata, validation warnings, and audit trail.
    
    This is the final result saved to the database and returned to the API caller.
    """
    
    model_config = ConfigDict(extra="allow")  # Allow additional fields for extensibility
    
    # Core classification output
    triage_response: EmailTriageResponse = Field(..., description="Structured LLM output")
    
    # Audit trail
    pipeline_version: PipelineVersion = Field(..., description="Complete version snapshot for reproducibility")
    request_uid: str = Field(..., description="Link to original email (EmailDocument.uid)")
    
    # Validation & processing metadata
    validation_warnings: list[str] = Field(
        default_factory=list,
        description="Quality warnings from stage 4 validation (non-blocking)"
    )
    retries_used: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts before success"
    )
    processing_duration_ms: float = Field(..., ge=0.0, description="Total processing time")
    
    # Timestamps
    created_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp when result was created"
    )
