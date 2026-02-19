"""
Retry strategies for handling LLM validation failures.

This module implements the Strategy Pattern for retry escalation.
Each strategy represents a different approach to handling validation
failures, allowing the retry engine to escalate through progressively
more aggressive recovery tactics.

Retry Strategy Chain:
    1. StandardRetryStrategy: Retry with exponential backoff (up to MAX_RETRIES)
    2. ShrinkRetryStrategy: Retry with reduced input (fewer candidates, shorter body)
    3. FallbackModelStrategy: Retry with alternative LLM model
    4. If all fail: Raise RetryExhausted for DLQ routing
"""

import asyncio
import structlog
from typing import Protocol

from inference_layer.config import Settings
from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.exceptions import (
    LLMModelNotAvailableError,
    LLMTimeoutError,
)
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.models.input_models import TriageRequest
from inference_layer.models.llm_models import (
    LLMGenerationRequest,
    LLMGenerationResponse,
)
from inference_layer.models.output_models import EmailTriageResponse
from inference_layer.validation.exceptions import ValidationError
from inference_layer.validation.pipeline import ValidationPipeline

logger = structlog.get_logger(__name__)


class RetryStrategy(Protocol):
    """
    Protocol for retry strategies.
    
    Each strategy implements a single `execute` method that attempts
    to recover from a validation failure using a specific approach
    (e.g., retry with backoff, shrink input, switch model).
    
    Strategies are chained by the RetryEngine: if one strategy fails
    after its max attempts, the engine escalates to the next strategy.
    """

    async def execute(
        self,
        request: TriageRequest,
        client: BaseLLMClient,
        prompt_builder: PromptBuilder,
        validator: ValidationPipeline,
        error: ValidationError | None,
        attempt: int,
    ) -> tuple[EmailTriageResponse, LLMGenerationResponse, list[str]]:
        """
        Execute retry strategy.
        
        Args:
            request: Original TriageRequest
            client: LLM client for generation
            prompt_builder: Prompt builder for constructing prompts
            validator: Validation pipeline for validating responses
            error: Previous validation error (None on first attempt)
            attempt: Current attempt number (1-indexed)
        
        Returns:
            Tuple of (validated response, LLM generation response, warnings)
        
        Raises:
            ValidationError: If validation fails after strategy exhausted
        """
        ...


class StandardRetryStrategy:
    """
    Standard retry with exponential backoff.
    
    This strategy simply retries the same request with exponential backoff
    between attempts (2^attempt seconds). It does not modify the input.
    
    Use case: Transient LLM failures (hallucinations, non-determinism)
    """

    def __init__(self, settings: Settings):
        """
        Initialize standard retry strategy.
        
        Args:
            settings: Application settings (for MAX_RETRIES, RETRY_BACKOFF_BASE)
        """
        self.max_retries = settings.MAX_RETRIES
        self.backoff_base = settings.RETRY_BACKOFF_BASE
        self.name = "standard"

    async def execute(
        self,
        request: TriageRequest,
        client: BaseLLMClient,
        prompt_builder: PromptBuilder,
        validator: ValidationPipeline,
        error: ValidationError | None,
        attempt: int,
    ) -> tuple[EmailTriageResponse, LLMGenerationResponse, list[str]]:
        """
        Execute standard retry with exponential backoff.
        
        Raises:
            ValidationError: If all retries exhausted
        """
        logger.info(
            f"StandardRetryStrategy starting attempt {attempt}/{self.max_retries}",
            extra={
                "strategy": self.name,
                "attempt": attempt,
                "max_retries": self.max_retries,
                "previous_error": type(error).__name__ if error else None,
            },
        )

        # Apply exponential backoff (skip on first attempt)
        if attempt > 1 and error:
            backoff_seconds = self.backoff_base ** attempt
            logger.info(
                f"Applying exponential backoff: {backoff_seconds}s",
                extra={"strategy": self.name, "attempt": attempt, "backoff_seconds": backoff_seconds},
            )
            await asyncio.sleep(backoff_seconds)

        # Build prompt (normal mode, not shrink)
        system_prompt = prompt_builder.build_system_prompt()
        user_prompt, prompt_metadata = prompt_builder.build_user_prompt(
            request, shrink_mode=False
        )
        
        # Combine system + user prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Create LLM request
        llm_request = LLMGenerationRequest(
            prompt=full_prompt,
            model=prompt_builder.default_model,
            temperature=prompt_builder.default_temperature,
            max_tokens=prompt_builder.default_max_tokens,
            format_schema=prompt_builder.json_schema,
        )

        # Generate response
        llm_response = await client.generate(llm_request)

        # Validate response
        validated_response, warnings = await validator.validate(llm_response, request)

        logger.info(
            f"StandardRetryStrategy succeeded on attempt {attempt}",
            extra={
                "strategy": self.name,
                "attempt": attempt,
                "warnings_count": len(warnings),
            },
        )

        return validated_response, llm_response, warnings


class ShrinkRetryStrategy:
    """
    Retry with reduced input (shrink mode).
    
    This strategy retries with a smaller input:
    - Fewer candidate keywords (SHRINK_TOP_N instead of CANDIDATE_TOP_N)
    - Shorter body text (SHRINK_BODY_LIMIT instead of BODY_TRUNCATION_LIMIT)
    
    Use case: Input too large/complex causes validation failures or timeouts
    """

    def __init__(self, settings: Settings):
        """
        Initialize shrink retry strategy.
        
        Args:
            settings: Application settings (for shrink limits)
        """
        self.max_retries = 2  # Fewer retries for shrink (already escalated)
        self.backoff_base = settings.RETRY_BACKOFF_BASE
        self.name = "shrink"

    async def execute(
        self,
        request: TriageRequest,
        client: BaseLLMClient,
        prompt_builder: PromptBuilder,
        validator: ValidationPipeline,
        error: ValidationError | None,
        attempt: int,
    ) -> tuple[EmailTriageResponse, LLMGenerationResponse, list[str]]:
        """
        Execute shrink retry with reduced input.
        
        Raises:
            ValidationError: If all shrink retries exhausted
        """
        logger.warning(
            f"ShrinkRetryStrategy starting attempt {attempt}/{self.max_retries} (input reduction mode)",
            extra={
                "strategy": self.name,
                "attempt": attempt,
                "max_retries": self.max_retries,
                "previous_error": type(error).__name__ if error else None,
            },
        )

        # Apply exponential backoff (skip on first shrink attempt)
        if attempt > 1 and error:
            backoff_seconds = self.backoff_base ** attempt
            logger.info(
                f"Applying exponential backoff: {backoff_seconds}s",
                extra={"strategy": self.name, "attempt": attempt, "backoff_seconds": backoff_seconds},
            )
            await asyncio.sleep(backoff_seconds)

        # Build prompt in SHRINK MODE
        system_prompt = prompt_builder.build_system_prompt()
        user_prompt, prompt_metadata = prompt_builder.build_user_prompt(
            request, shrink_mode=True  # Key difference from standard retry
        )
        
        # Combine system + user prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        logger.info(
            "Shrink mode applied",
            extra={
                "strategy": self.name,
                "shrink_mode": True,
                "candidates_count": prompt_metadata.get("candidates_count", 0),
                "body_length": prompt_metadata.get("body_length", 0),
            },
        )

        # Create LLM request
        llm_request = LLMGenerationRequest(
            prompt=full_prompt,
            model=prompt_builder.default_model,
            temperature=prompt_builder.default_temperature,
            max_tokens=prompt_builder.default_max_tokens,
            format_schema=prompt_builder.json_schema,
        )

        # Generate response
        llm_response = await client.generate(llm_request)

        # Validate response
        validated_response, warnings = await validator.validate(llm_response, request)

        logger.info(
            f"ShrinkRetryStrategy succeeded on attempt {attempt}",
            extra={
                "strategy": self.name,
                "attempt": attempt,
                "warnings_count": len(warnings),
            },
        )

        return validated_response, llm_response, warnings


class FallbackModelStrategy:
    """
    Retry with alternative LLM model.
    
    This strategy switches to a fallback model from the configured
    FALLBACK_MODELS list. It cycles through all available fallback
    models before giving up.
    
    Use case: Primary model consistently fails validation (model-specific issue)
    """

    def __init__(self, settings: Settings, fallback_models: list[str]):
        """
        Initialize fallback model strategy.
        
        Args:
            settings: Application settings
            fallback_models: List of fallback model names to try
        """
        self.fallback_models = fallback_models
        self.backoff_base = settings.RETRY_BACKOFF_BASE
        self.name = "fallback"
        self.current_model_index = 0

    async def execute(
        self,
        request: TriageRequest,
        client: BaseLLMClient,
        prompt_builder: PromptBuilder,
        validator: ValidationPipeline,
        error: ValidationError | None,
        attempt: int,
    ) -> tuple[EmailTriageResponse, LLMGenerationResponse, list[str]]:
        """
        Execute fallback model retry.
        
        Raises:
            ValidationError: If all fallback models exhausted
            LLMModelNotAvailableError: If fallback model not available
        """
        if not self.fallback_models:
            logger.error(
                "FallbackModelStrategy called but no fallback models configured",
                extra={"strategy": self.name, "fallback_models": self.fallback_models},
            )
            # Re-raise last error since we can't retry
            if error:
                raise error
            raise ValueError("No fallback models configured")

        # Select fallback model (cycle through list)
        fallback_model = self.fallback_models[self.current_model_index % len(self.fallback_models)]
        self.current_model_index += 1

        logger.warning(
            f"FallbackModelStrategy attempting with model: {fallback_model}",
            extra={
                "strategy": self.name,
                "attempt": attempt,
                "fallback_model": fallback_model,
                "fallback_models_total": len(self.fallback_models),
                "previous_error": type(error).__name__ if error else None,
            },
        )

        # Apply exponential backoff (skip on first fallback attempt)
        if attempt > 1 and error:
            backoff_seconds = self.backoff_base ** attempt
            logger.info(
                f"Applying exponential backoff: {backoff_seconds}s",
                extra={"strategy": self.name, "attempt": attempt, "backoff_seconds": backoff_seconds},
            )
            await asyncio.sleep(backoff_seconds)

        # Build prompt (normal mode)
        system_prompt = prompt_builder.build_system_prompt()
        user_prompt, prompt_metadata = prompt_builder.build_user_prompt(
            request, shrink_mode=False
        )
        
        # Combine system + user prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Create LLM request with FALLBACK MODEL
        llm_request = LLMGenerationRequest(
            prompt=full_prompt,
            model=fallback_model,  # Key difference: use fallback model
            temperature=prompt_builder.default_temperature,
            max_tokens=prompt_builder.default_max_tokens,
            format_schema=prompt_builder.json_schema,
        )

        # Generate response (client may need to switch model internally)
        # Note: OllamaClient accepts model parameter in generate() request
        llm_response = await client.generate(llm_request)

        # Validate response
        validated_response, warnings = await validator.validate(llm_response, request)

        logger.info(
            f"FallbackModelStrategy succeeded with model: {fallback_model}",
            extra={
                "strategy": self.name,
                "attempt": attempt,
                "fallback_model": fallback_model,
                "warnings_count": len(warnings),
            },
        )

        return validated_response, llm_response, warnings
