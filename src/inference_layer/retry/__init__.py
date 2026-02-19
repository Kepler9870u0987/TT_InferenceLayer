"""
Retry engine with fallback policies.

This module implements a 4-level retry/fallback strategy for handling
LLM validation failures:

1. **Standard Retry**: Exponential backoff (up to MAX_RETRIES)
2. **Shrink Request**: Reduced input (fewer candidates, shorter body)
3. **Fallback Model**: Alternative LLM model
4. **DLQ Routing**: Manual review (raises RetryExhausted)

The retry engine is model-agnostic and works with any BaseLLMClient
implementation. It tracks complete retry history for audit trails.

Main Components:
    - RetryEngine: Main orchestrator for retry logic
    - RetryStrategy: Protocol for implementing retry strategies
    - RetryMetadata: Immutable history of retry attempts
    - RetryExhausted: Exception raised when all strategies fail

Usage:
    >>> from inference_layer.retry import RetryEngine
    >>> engine = RetryEngine(llm_client, prompt_builder, validator, settings)
    >>> response, metadata, warnings = await engine.execute_with_retry(request)
"""

from inference_layer.retry.engine import RetryEngine
from inference_layer.retry.exceptions import RetryExhausted
from inference_layer.retry.metadata import RetryMetadata
from inference_layer.retry.strategies import (
    FallbackModelStrategy,
    RetryStrategy,
    ShrinkRetryStrategy,
    StandardRetryStrategy,
)

__all__ = [
    "RetryEngine",
    "RetryExhausted",
    "RetryMetadata",
    "RetryStrategy",
    "StandardRetryStrategy",
    "ShrinkRetryStrategy",
    "FallbackModelStrategy",
]
