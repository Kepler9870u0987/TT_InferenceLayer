"""
Abstract base client for LLM inference.

Defines the interface that all LLM client implementations (Ollama, SGLang, etc.)
must adhere to. This abstraction allows swapping inference backends without
changing the validation pipeline or API layer.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import structlog

from inference_layer.models.llm_models import LLMGenerationRequest, LLMGenerationResponse


logger = structlog.get_logger(__name__)


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM inference clients.
    
    All concrete implementations (OllamaClient, SGLangClient, etc.) must
    inherit from this and implement the abstract methods.
    
    Responsibilities:
    - Send generation requests to inference server
    - Parse responses into standardized format
    - Handle connection errors and timeouts
    - Provide health check and model info endpoints
    
    Does NOT handle:
    - Prompt construction (that's PromptBuilder's job)
    - Response validation (that's ValidationPipeline's job)
    - Retry logic for validation failures (that's RetryEngine's job)
    
    Connection-level retries (network errors) MAY be handled internally.
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: int = 60,
        max_retries: int = 2,
        **kwargs
    ):
        """
        Initialize base client.
        
        Args:
            base_url: Base URL of LLM inference server (e.g., http://ollama:11434)
            timeout: Request timeout in seconds
            max_retries: Number of connection-level retries for network errors
            **kwargs: Additional provider-specific config
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_config = kwargs
        
        logger.info(
            "Initialized LLM client",
            client_class=self.__class__.__name__,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries
        )
    
    @abstractmethod
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """
        Generate completion from the LLM.
        
        This is the core method that sends a request to the inference server
        and returns the parsed response. Implementations should:
        
        1. Format the request according to provider's API spec
        2. Send HTTP request with timeout and retry on network errors
        3. Parse response and extract metadata (tokens, latency, etc.)
        4. Return LLMGenerationResponse or raise LLMClientError subclass
        
        Args:
            request: Standardized generation request
            
        Returns:
            LLMGenerationResponse with generated text and metadata
            
        Raises:
            LLMConnectionError: Network/timeout errors
            LLMGenerationError: Server-side generation errors
            LLMModelNotAvailableError: Model not found
            LLMTimeoutError: Request exceeded timeout
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the inference server is healthy and reachable.
        
        Should be a lightweight check (e.g., GET /health or /api/tags).
        
        Returns:
            True if server is healthy, False otherwise
            
        Note:
            This should NOT raise exceptions - return False on error.
            Used by health check endpoints and startup validation.
        """
        pass
    
    @abstractmethod
    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """
        Get metadata about a specific model.
        
        Returns information like:
        - Exact version/digest
        - Model size
        - Quantization format
        - Context window size
        - Capabilities (structured output support, etc.)
        
        Args:
            model_name: Name of the model (e.g., "qwen2.5:7b")
            
        Returns:
            Dictionary with model metadata
            
        Raises:
            LLMModelNotAvailableError: Model not found on server
            LLMConnectionError: Unable to reach server
            
        Note:
            Used for PipelineVersion tracking and capability detection.
        """
        pass
    
    async def supports_structured_output(self, model_name: str) -> bool:
        """
        Check if the model supports structured output (JSON Schema constraint).
        
        Default implementation returns True (optimistic). Subclasses can
        override to check actual capabilities.
        
        Args:
            model_name: Name of the model
            
        Returns:
            True if model supports structured output, False otherwise
        """
        logger.debug(
            "Checking structured output support (default: True)",
            model_name=model_name
        )
        return True
    
    async def close(self):
        """
        Close client connections and cleanup resources.
        
        Should be called on shutdown. Default implementation does nothing.
        Subclasses should override if they hold persistent connections.
        """
        logger.debug("Closing LLM client", client_class=self.__class__.__name__)
        pass
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"base_url={self.base_url}, "
            f"timeout={self.timeout}s)"
        )
