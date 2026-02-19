"""
Pipeline versioning for audit and reproducibility.

PipelineVersion is a frozen dataclass that captures all version identifiers
necessary to reproduce a classification result. It implements the
"deterministic statistical invariant": same versions + same input = same output.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PipelineVersion:
    """
    Immutable version snapshot for audit trail and backtesting.
    
    This captures all component versions involved in the classification pipeline.
    Must be saved alongside every triage result for reproducibility.
    
    Attributes:
        dictionary_version: Version of the keyword dictionary/taxonomy (frozen during batch)
        model_version: LLM model identifier (e.g., "qwen2.5:7b", "llama3.1:8b")
        schema_version: JSON Schema version identifier (e.g., "email_triage_v2")
        inference_layer_version: Version of this inference layer codebase
        parser_version: Version of email parser (from upstream layer)
        canonicalization_version: Version of canonicalization logic (from upstream)
        ner_model_version: NER model version for PII detection (from upstream)
        pii_redaction_version: PII redaction logic version (from upstream)
        stoplist_version: Version of stoplist used in candidate generation (if applicable)
    """
    
    dictionary_version: int
    model_version: str
    schema_version: str
    inference_layer_version: str
    
    # Upstream versions (from preprocessing layer)
    parser_version: Optional[str] = None
    canonicalization_version: Optional[str] = None
    ner_model_version: Optional[str] = None
    pii_redaction_version: Optional[str] = None
    
    # Optional: stoplist/keyword extraction version
    stoplist_version: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "dictionary_version": self.dictionary_version,
            "model_version": self.model_version,
            "schema_version": self.schema_version,
            "inference_layer_version": self.inference_layer_version,
            "parser_version": self.parser_version,
            "canonicalization_version": self.canonicalization_version,
            "ner_model_version": self.ner_model_version,
            "pii_redaction_version": self.pii_redaction_version,
            "stoplist_version": self.stoplist_version,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PipelineVersion":
        """Create from dictionary."""
        return cls(
            dictionary_version=data["dictionary_version"],
            model_version=data["model_version"],
            schema_version=data["schema_version"],
            inference_layer_version=data["inference_layer_version"],
            parser_version=data.get("parser_version"),
            canonicalization_version=data.get("canonicalization_version"),
            ner_model_version=data.get("ner_model_version"),
            pii_redaction_version=data.get("pii_redaction_version"),
            stoplist_version=data.get("stoplist_version"),
        )
    
    def __str__(self) -> str:
        """Human-readable version string."""
        return (
            f"PipelineVersion("
            f"dict={self.dictionary_version}, "
            f"model={self.model_version}, "
            f"schema={self.schema_version}, "
            f"layer={self.inference_layer_version})"
        )
