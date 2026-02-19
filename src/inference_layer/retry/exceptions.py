"""
Retry engine exceptions.

This module defines exceptions raised by the retry engine when all
retry strategies have been exhausted and the request must be routed
to the Dead Letter Queue (DLQ) for manual review.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inference_layer.models.input_models import TriageRequest
    from inference_layer.retry.metadata import RetryMetadata
    from inference_layer.validation.exceptions import ValidationError


class RetryExhausted(Exception):
    """
    Raised when all retry strategies fail.
    
    This exception signals that the request should be routed to the DLQ
    for manual review. It contains the complete retry history including:
    - Original request
    - Retry metadata (attempts, strategies, latency, failures)
    - Final validation error that caused ultimate failure
    
    Attributes:
        request: Original TriageRequest that failed
        retry_metadata: Complete retry history and metadata
        last_error: Final ValidationError that caused failure
    """

    def __init__(
        self,
        request: "TriageRequest",
        retry_metadata: "RetryMetadata",
        last_error: "ValidationError",
    ) -> None:
        """
        Initialize RetryExhausted exception.
        
        Args:
            request: Original TriageRequest
            retry_metadata: Complete retry metadata
            last_error: Final ValidationError
        """
        self.request = request
        self.retry_metadata = retry_metadata
        self.last_error = last_error
        
        super().__init__(
            f"All retry strategies exhausted after {retry_metadata.total_attempts} attempts. "
            f"Strategies tried: {', '.join(retry_metadata.strategies_used)}. "
            f"Final error: {type(last_error).__name__}"
        )
