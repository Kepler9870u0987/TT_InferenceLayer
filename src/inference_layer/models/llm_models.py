"""
LLM-specific data models for request/response cycle.

These models are internal to the LLM layer and handle the raw communication
with inference servers (Ollama, SGLang, etc.). They are separate from the
business models (EmailTriageResponse) to allow flexibility in the underlying
LLM client implementation.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class LLMGenerationRequest(BaseModel):
    """
    Internal request model for LLM generation.
    
    This is the standardized format sent to any LLM client implementation
    (Ollama, SGLang, etc.). It abstracts away provider-specific details.
    """
    model_config = ConfigDict(frozen=True)
    
    prompt: str = Field(..., description="Complete prompt (system + user combined or formatted)")
    model: str = Field(..., description="Model name/identifier (e.g., 'qwen2.5:7b')")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=2048, ge=1, le=8192, description="Maximum tokens to generate")
    format_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for structured output constraint (Ollama format parameter)"
    )
    stream: bool = Field(default=False, description="Whether to stream response (always False for validation)")
    stop_sequences: Optional[list[str]] = Field(default=None, description="Stop sequences for generation")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")


class LLMGenerationResponse(BaseModel):
    """
    Internal response model from LLM generation.
    
    Contains the raw generated text plus metadata for audit/logging.
    Validation of the content against business rules happens in the validation layer.
    """
    model_config = ConfigDict(frozen=True)
    
    content: str = Field(..., description="Generated text (typically JSON string)")
    model_version: str = Field(..., description="Actual model version used (for audit trail)")
    finish_reason: str = Field(
        ...,
        description="Why generation stopped: 'stop', 'length', 'error', etc."
    )
    usage_tokens: Optional[int] = Field(
        default=None,
        description="Total tokens used (prompt + completion)"
    )
    prompt_tokens: Optional[int] = Field(default=None, description="Tokens in prompt")
    completion_tokens: Optional[int] = Field(default=None, description="Tokens in completion")
    latency_ms: int = Field(..., ge=0, description="Generation latency in milliseconds")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp from server")
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific metadata (for debugging)"
    )


class LLMMetadata(BaseModel):
    """
    Metadata for audit trail in persisted TriageResult.
    
    This is a simplified version of LLMGenerationResponse that gets
    saved with the final result for reproducibility and debugging.
    """
    model: str = Field(..., description="Model name used")
    model_version: str = Field(..., description="Exact model version")
    temperature: float = Field(..., description="Temperature used")
    tokens_used: Optional[int] = Field(default=None, description="Total tokens")
    latency_ms: int = Field(..., description="Latency in milliseconds")
    attempt_number: int = Field(default=1, ge=1, description="Retry attempt number (1 = first try)")
    finish_reason: str = Field(..., description="Generation finish reason")
    truncation_applied: bool = Field(
        default=False,
        description="Whether body was truncated (normal or shrink mode)"
    )
    candidates_count: int = Field(..., ge=0, description="Number of candidate keywords sent to LLM")
