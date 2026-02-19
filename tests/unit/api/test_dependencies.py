"""
Unit tests for API dependency injection.
"""

import pytest
from fastapi import Depends

from inference_layer.api.dependencies import (
    get_llm_client,
    get_prompt_builder,
    get_retry_engine,
    get_settings,
    get_validation_pipeline,
)
from inference_layer.config import Settings
from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.retry.engine import RetryEngine
from inference_layer.validation.pipeline import ValidationPipeline


def test_get_settings():
    """Test settings singleton."""
    settings1 = get_settings()
    settings2 = get_settings()
    
    # Should be same instance (cached)
    assert settings1 is settings2
    assert isinstance(settings1, Settings)


def test_get_llm_client():
    """Test LLM client singleton."""
    client1 = get_llm_client()
    client2 = get_llm_client()
    
    # Should be same instance (cached)
    assert client1 is client2
    assert isinstance(client1, BaseLLMClient)


def test_get_prompt_builder():
    """Test prompt builder singleton."""
    builder1 = get_prompt_builder()
    builder2 = get_prompt_builder()
    
    # Should be same instance (cached)
    assert builder1 is builder2
    assert isinstance(builder1, PromptBuilder)


def test_get_validation_pipeline():
    """Test validation pipeline singleton."""
    pipeline1 = get_validation_pipeline()
    pipeline2 = get_validation_pipeline()
    
    # Should be same instance (cached)
    assert pipeline1 is pipeline2
    assert isinstance(pipeline1, ValidationPipeline)


def test_get_retry_engine():
    """Test retry engine factory (not cached)."""
    engine1 = get_retry_engine()
    engine2 = get_retry_engine()
    
    # Should be different instances (not cached)
    # But underlying components should be cached
    assert isinstance(engine1, RetryEngine)
    assert isinstance(engine2, RetryEngine)
    
    # Components should be same (cached)
    assert engine1.llm_client is engine2.llm_client
    assert engine1.prompt_builder is engine2.prompt_builder
    assert engine1.validation_pipeline is engine2.validation_pipeline


def test_dependencies_integration():
    """Test that dependencies work together."""
    settings = get_settings()
    client = get_llm_client()
    builder = get_prompt_builder()
    pipeline = get_validation_pipeline()
    engine = get_retry_engine()
    
    # All should be initialized
    assert settings is not None
    assert client is not None
    assert builder is not None
    assert pipeline is not None
    assert engine is not None
    
    # Engine should use cached components
    assert engine.llm_client is client
    assert engine.prompt_builder is builder
    assert engine.validation_pipeline is pipeline
