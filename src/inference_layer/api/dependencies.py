"""
FastAPI dependency injection for LLM inference layer.

Provides singleton instances of expensive resources (LLM client, prompt builder)
and factory functions for pipeline components.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from inference_layer.config import Settings, settings
from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.ollama_client import OllamaClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.retry.engine import RetryEngine
from inference_layer.validation.pipeline import ValidationPipeline


@lru_cache()
def get_settings() -> Settings:
    """
    Get settings singleton.
    
    Returns:
        Settings instance
    """
    return settings


@lru_cache()
def get_llm_client(settings: Settings = Depends(get_settings)) -> BaseLLMClient:
    """
    Get singleton LLM client with connection pooling.
    
    Uses @lru_cache to ensure only one client instance is created.
    The client maintains an internal connection pool for efficiency.
    
    Args:
        settings: Application settings (injected)
    
    Returns:
        OllamaClient instance
    """
    return OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        timeout=settings.OLLAMA_TIMEOUT,
        max_retries=2,  # Connection-level retries (retry engine handles validation retries)
    )


@lru_cache()
def get_prompt_builder(settings: Settings = Depends(get_settings)) -> PromptBuilder:
    """
    Get singleton prompt builder.
    
    Loads Jinja2 templates once and reuses them across requests.
    
    Args:
        settings: Application settings (injected)
    
    Returns:
        PromptBuilder instance
    """
    return PromptBuilder(
        templates_dir=Path(settings.PROMPT_TEMPLATES_DIR),
        schema_path=Path(settings.JSON_SCHEMA_PATH),
        top_n_candidates=settings.TOP_N_CANDIDATES,
        body_limit=settings.BODY_LIMIT,
        shrink_top_n=settings.SHRINK_TOP_N,
        shrink_body_limit=settings.SHRINK_BODY_LIMIT,
        enable_pii_redaction=settings.ENABLE_PII_REDACTION,
    )


@lru_cache()
def get_validation_pipeline(settings: Settings = Depends(get_settings)) -> ValidationPipeline:
    """
    Get singleton validation pipeline.
    
    Loads JSON Schema once and reuses it across requests.
    
    Args:
        settings: Application settings (injected)
    
    Returns:
        ValidationPipeline instance
    """
    return ValidationPipeline(settings)


def get_retry_engine(
    llm_client: BaseLLMClient = Depends(get_llm_client),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    validation_pipeline: ValidationPipeline = Depends(get_validation_pipeline),
    settings: Settings = Depends(get_settings),
) -> RetryEngine:
    """
    Create retry engine with injected dependencies.
    
    Note: RetryEngine is NOT cached because it's lightweight and stateless.
    All heavy resources (client, builder, pipeline) are singletons.
    
    Args:
        llm_client: LLM client singleton (injected)
        prompt_builder: Prompt builder singleton (injected)
        validation_pipeline: Validation pipeline singleton (injected)
        settings: Application settings (injected)
    
    Returns:
        RetryEngine instance
    """
    return RetryEngine(
        llm_client=llm_client,
        prompt_builder=prompt_builder,
        validation_pipeline=validation_pipeline,
        settings=settings,
    )
