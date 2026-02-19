"""
Retry engine with 4-level fallback strategy.

This module implements the main RetryEngine that orchestrates retry
strategies to handle LLM validation failures. It provides a single
entry point for executing LLM requests with automatic retry/fallback.

Retry Policy (4 levels):
    1. Standard Retry: Exponential backoff (up to MAX_RETRIES)
    2. Shrink Request: Reduced input (fewer candidates, shorter body)
    3. Fallback Model: Alternative LLM model
    4. DLQ Routing: Manual review (raises RetryExhausted)

Usage:
    engine = RetryEngine(llm_client, prompt_builder, validation_pipeline, settings)
    response, metadata, warnings = await engine.execute_with_retry(request)
"""

import structlog
import time

from typing import TYPE_CHECKING

from inference_layer.config import Settings
from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.models.input_models import TriageRequest
from inference_layer.models.llm_models import LLMMetadata
from inference_layer.models.output_models import EmailTriageResponse
from inference_layer.retry.exceptions import RetryExhausted
from inference_layer.retry.metadata import RetryMetadata
from inference_layer.retry.strategies import (
    FallbackModelStrategy,
    RetryStrategy,
    ShrinkRetryStrategy,
    StandardRetryStrategy,
)
from inference_layer.validation.exceptions import ValidationError
from inference_layer.validation.pipeline import ValidationPipeline

if TYPE_CHECKING:
    from typing import Any

logger = structlog.get_logger(__name__)


class RetryEngine:
    """
    Retry engine with 4-level fallback strategy.
    
    Orchestrates retry strategies to handle validation failures:
    1. StandardRetryStrategy: Up to MAX_RETRIES with exponential backoff
    2. ShrinkRetryStrategy: Reduced input (fewer candidates, shorter body)
    3. FallbackModelStrategy: Alternative LLM model
    4. Raise RetryExhausted: DLQ routing for manual review
    
    The engine tracks complete retry history (attempts, strategies, latency,
    validation failures) for audit trails and metrics.
    
    Attributes:
        llm_client: LLM client for generation
        prompt_builder: Prompt builder for constructing prompts
        validation_pipeline: Validation pipeline for validating responses
        settings: Application settings
        strategies: List of retry strategies (ordered)
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        prompt_builder: PromptBuilder,
        validation_pipeline: ValidationPipeline,
        settings: Settings,
    ):
        """
        Initialize retry engine.
        
        Args:
            llm_client: LLM client for generation
            prompt_builder: Prompt builder for constructing prompts
            validation_pipeline: Validation pipeline for validating responses
            settings: Application settings
        """
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.validation_pipeline = validation_pipeline
        self.settings = settings

        # Initialize retry strategies (ordered by escalation level)
        # Type: list[tuple[strategy_name, strategy_instance, max_attempts]]
        standard_strat: RetryStrategy = StandardRetryStrategy(settings)
        shrink_strat: RetryStrategy = ShrinkRetryStrategy(settings)
        fallback_strat: RetryStrategy = FallbackModelStrategy(settings, settings.FALLBACK_MODELS)
        
        self.strategies: list[tuple[str, RetryStrategy, int]] = [
            ("standard", standard_strat, settings.MAX_RETRIES),
            ("shrink", shrink_strat, 2),  # Fewer retries after escalation
            ("fallback", fallback_strat, len(settings.FALLBACK_MODELS) if settings.FALLBACK_MODELS else 1),
        ]

        logger.info(
            "RetryEngine initialized",
            extra={
                "max_retries": settings.MAX_RETRIES,
                "backoff_base": settings.RETRY_BACKOFF_BASE,
                "shrink_top_n": settings.SHRINK_TOP_N,
                "shrink_body_limit": settings.SHRINK_BODY_LIMIT,
                "fallback_models": settings.FALLBACK_MODELS,
                "strategies_count": len(self.strategies),
            },
        )

    async def execute_with_retry(
        self, request: TriageRequest
    ) -> tuple[EmailTriageResponse, RetryMetadata, list[str]]:
        """
        Execute LLM request with full retry/fallback policy.
        
        Orchestrates all retry strategies in sequence. If a strategy succeeds,
        returns immediately with validated response and metadata. If all
        strategies fail, raises RetryExhausted for DLQ routing.
        
        Args:
            request: Original TriageRequest
        
        Returns:
            Tuple of (validated response, retry metadata, warnings)
        
        Raises:
            RetryExhausted: All retry strategies exhausted, needs DLQ routing
        """
        start_time_ms = int(time.time() * 1000)
        total_attempts = 0
        strategies_used: list[str] = []
        validation_failures: list[dict] = []
        last_error: ValidationError | None = None

        logger.info(
            "Starting retry engine execution",
            extra={
                "email_uid": request.email.uid,
                "dictionary_version": request.dictionary_version,
                "candidates_count": len(request.candidate_keywords),
            },
        )

        # Try each strategy in sequence
        for strategy_name, strategy_instance, max_attempts in self.strategies:
            if strategy_name not in strategies_used:
                strategies_used.append(strategy_name)

            logger.info(
                f"Attempting strategy: {strategy_name}",
                extra={
                    "strategy": strategy_name,
                    "max_attempts": max_attempts,
                    "total_attempts_so_far": total_attempts,
                },
            )

            # Try strategy up to max_attempts
            for attempt in range(1, max_attempts + 1):
                total_attempts += 1

                try:
                    # Execute strategy
                    validated_response, llm_response, warnings = await strategy_instance.execute(
                        request=request,
                        client=self.llm_client,
                        prompt_builder=self.prompt_builder,
                        validator=self.validation_pipeline,
                        error=last_error,
                        attempt=attempt,
                    )

                    # Success! Build metadata and return
                    end_time_ms = int(time.time() * 1000)
                    total_latency_ms = end_time_ms - start_time_ms

                    # Build LLM metadata
                    llm_metadata = LLMMetadata(
                        model=llm_response.model_version.split(":")[0] if ":" in llm_response.model_version else llm_response.model_version,
                        model_version=llm_response.model_version,
                        temperature=self.prompt_builder.default_temperature,
                        tokens_used=llm_response.usage_tokens,
                        latency_ms=llm_response.latency_ms,
                        attempt_number=total_attempts,
                        finish_reason=llm_response.finish_reason,
                        truncation_applied=len(request.email.body_text_canonical) > self.prompt_builder.body_truncation_limit,
                        candidates_count=len(request.candidate_keywords),
                    )

                    retry_metadata = RetryMetadata(
                        total_attempts=total_attempts,
                        strategies_used=strategies_used,
                        final_strategy=strategy_name,
                        total_latency_ms=total_latency_ms,
                        llm_metadata=llm_metadata,
                        validation_failures=validation_failures,
                    )

                    logger.info(
                        "Retry engine succeeded",
                        extra={
                            "strategy": strategy_name,
                            "total_attempts": total_attempts,
                            "total_latency_ms": total_latency_ms,
                            "warnings_count": len(warnings),
                        },
                    )

                    return validated_response, retry_metadata, warnings

                except ValidationError as e:
                    # Validation failed - log and retry
                    last_error = e
                    validation_failures.append(e.details)

                    logger.warning(
                        f"Validation failed on attempt {total_attempts}",
                        extra={
                            "strategy": strategy_name,
                            "attempt": attempt,
                            "total_attempts": total_attempts,
                            "error_type": type(e).__name__,
                            "error_details": e.details,
                        },
                    )

                    # If not last attempt for this strategy, continue retry loop
                    if attempt < max_attempts:
                        logger.info(
                            f"Retrying with same strategy (attempt {attempt + 1}/{max_attempts})",
                            extra={"strategy": strategy_name, "next_attempt": attempt + 1},
                        )
                        continue

                    # Last attempt for this strategy - will escalate to next strategy
                    logger.warning(
                        f"Strategy exhausted: {strategy_name} (after {max_attempts} attempts)",
                        extra={
                            "strategy": strategy_name,
                            "attempts_used": max_attempts,
                            "escalating": True,
                        },
                    )
                    break  # Break attempt loop, move to next strategy

        # All strategies exhausted - raise RetryExhausted for DLQ routing
        end_time_ms = int(time.time() * 1000)
        total_latency_ms = end_time_ms - start_time_ms

        # Build final metadata (even though we failed)
        llm_metadata = LLMMetadata(
            model="unknown",
            model_version="unknown",  # Failed before successful generation
            temperature=self.prompt_builder.default_temperature,
            tokens_used=None,
            latency_ms=total_latency_ms,
            attempt_number=total_attempts,
            finish_reason="error",
            truncation_applied=False,  # Unknown, since we failed
            candidates_count=len(request.candidate_keywords),
        )

        retry_metadata = RetryMetadata(
            total_attempts=total_attempts,
            strategies_used=strategies_used,
            final_strategy=strategies_used[-1] if strategies_used else "none",
            total_latency_ms=total_latency_ms,
            llm_metadata=llm_metadata,
            validation_failures=validation_failures,
        )

        logger.error(
            "All retry strategies exhausted, routing to DLQ",
            extra={
                "total_attempts": total_attempts,
                "strategies_tried": strategies_used,
                "total_latency_ms": total_latency_ms,
                "validation_failures_count": len(validation_failures),
                "final_error_type": type(last_error).__name__ if last_error else "unknown",
            },
        )

        raise RetryExhausted(
            request=request,
            retry_metadata=retry_metadata,
            last_error=last_error if last_error else ValidationError("Unknown error", {}),
        )
