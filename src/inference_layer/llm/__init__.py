"""
LLM client abstraction and implementations.

Components:
- BaseLLMClient: Abstract base class for LLM clients
- OllamaClient: Implementation for Ollama inference server
- SGLangClient: Stub for future SGLang implementation
- PromptBuilder: Constructs prompts from TriageRequest
- text_utils: Text processing utilities (truncation, etc.)
- exceptions: LLM-specific exceptions
"""

from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.ollama_client import OllamaClient
from inference_layer.llm.sglang_client import SGLangClient
from inference_layer.llm.prompt_builder import PromptBuilder
from inference_layer.llm.exceptions import (
    LLMClientError,
    LLMConnectionError,
    LLMGenerationError,
    LLMSchemaViolationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMModelNotAvailableError,
)

__all__ = [
    "BaseLLMClient",
    "OllamaClient",
    "SGLangClient",
    "PromptBuilder",
    "LLMClientError",
    "LLMConnectionError",
    "LLMGenerationError",
    "LLMSchemaViolationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMModelNotAvailableError",
]
