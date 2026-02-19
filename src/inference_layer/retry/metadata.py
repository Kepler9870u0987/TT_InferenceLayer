"""
Retry metadata tracking.

This module defines the RetryMetadata dataclass that captures the complete
retry history for audit trails and metrics.
"""

from dataclasses import dataclass, field

from inference_layer.models.llm_models import LLMMetadata


@dataclass(frozen=True)
class RetryMetadata:
    """
    Complete retry history and metadata for audit trail.
    
    This frozen dataclass captures all retry attempts, strategies used,
    timing information, and validation failures. It is persisted alongside
    the successful response (or in DLQ for failures) to enable:
    - Audit trails and debugging
    - Metrics and monitoring (retry rates, strategy effectiveness)
    - Post-hoc analysis and model improvement
    
    Attributes:
        total_attempts: Total number of LLM generation attempts made
        strategies_used: List of strategy names attempted (e.g., ["standard", "shrink"])
        final_strategy: Name of strategy that succeeded (or last attempted)
        total_latency_ms: Total time from first attempt to final result (ms)
        llm_metadata: LLM metadata from successful generation
        validation_failures: History of validation errors (list of error.details dicts)
    """

    total_attempts: int
    strategies_used: list[str]
    final_strategy: str
    total_latency_ms: int
    llm_metadata: LLMMetadata
    validation_failures: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate metadata invariants."""
        if self.total_attempts < 1:
            raise ValueError("total_attempts must be >= 1")
        
        if not self.strategies_used:
            raise ValueError("strategies_used must not be empty")
        
        if self.final_strategy not in self.strategies_used:
            raise ValueError(
                f"final_strategy '{self.final_strategy}' must be in strategies_used"
            )
        
        if self.total_latency_ms < 0:
            raise ValueError("total_latency_ms must be >= 0")
