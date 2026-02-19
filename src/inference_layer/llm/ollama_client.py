"""
Ollama client implementation for LLM inference.

Communicates with Ollama API using httpx AsyncClient. Supports:
- JSON output format (basic)
- Structured output via JSON Schema (format parameter)
- Connection pooling and retry logic
- Health checks and model introspection
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional
import httpx
import structlog

from inference_layer.llm.base_client import BaseLLMClient
from inference_layer.llm.exceptions import (
    LLMConnectionError,
    LLMGenerationError,
    LLMTimeoutError,
    LLMModelNotAvailableError,
)
from inference_layer.models.llm_models import LLMGenerationRequest, LLMGenerationResponse
from inference_layer.monitoring.metrics import llm_latency_seconds, llm_tokens_total


logger = structlog.get_logger(__name__)


class OllamaClient(BaseLLMClient):
    """
    Ollama-specific LLM client using httpx for async HTTP communication.
    
    API Endpoints:
    - POST /api/generate: Generate completion with optional format constraint
    - GET /api/tags: List available models
    - GET /api/show: Get model details
    
    Features:
    - Structured output via format parameter (JSON Schema)
    - Connection pooling via persistent AsyncClient
    - Automatic retry on network errors with exponential backoff
    - Detailed metadata extraction (tokens, latency, model version)
    """
    
    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        timeout: int = 60,
        max_retries: int = 2,
        connection_limits: Optional[httpx.Limits] = None,
        **kwargs
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL
            timeout: Request timeout in seconds
            max_retries: Connection-level retries for network errors
            connection_limits: httpx connection pool limits (default: 10 max connections)
            **kwargs: Additional config
        """
        super().__init__(base_url, timeout, max_retries, **kwargs)
        
        # Set default connection limits if not provided
        if connection_limits is None:
            connection_limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0
            )
        
        # Create persistent async client for connection pooling
        self._client: Optional[httpx.AsyncClient] = None
        self._connection_limits = connection_limits
        
        logger.info(
            "Ollama client initialized",
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
            connection_limits=str(connection_limits)
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                limits=self._connection_limits,
                follow_redirects=True
            )
            logger.debug("Created new httpx AsyncClient")
        return self._client
    
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """
        Generate completion using Ollama API.
        
        POST /api/generate with payload:
        {
            "model": "qwen2.5:7b",
            "prompt": "...",
            "stream": false,
            "format": <JSON Schema or "json">,
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,
                "top_p": 0.95,
                "seed": 42
            }
        }
        
        Response:
        {
            "model": "qwen2.5:7b",
            "created_at": "2026-02-19T...",
            "response": "...",
            "done": true,
            "total_duration": 5000000000,
            "eval_count": 150,
            "prompt_eval_count": 50
        }
        """
        start_time = time.time()
        
        # Build Ollama-specific payload
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "stream": request.stream,  # Always False for us
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            }
        }
        
        # Add optional parameters
        if request.top_p is not None:
            payload["options"]["top_p"] = request.top_p
        if request.seed is not None:
            payload["options"]["seed"] = request.seed
        if request.stop_sequences:
            payload["options"]["stop"] = request.stop_sequences
        
        # Add format constraint (JSON Schema or "json")
        if request.format_schema:
            # Ollama expects the schema object directly as "format"
            payload["format"] = request.format_schema
            logger.debug("Using structured output with JSON Schema")
        else:
            # Fallback to basic JSON mode
            payload["format"] = "json"
            logger.debug("Using basic JSON format")
        
        logger.info(
            "Sending generation request to Ollama",
            model=request.model,
            prompt_length=len(request.prompt),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            has_schema=bool(request.format_schema)
        )
        
        # Retry loop for network errors
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(
                    "/api/generate",
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # Parse response
                response_data = response.json()
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Extract content
                content = response_data.get("response", "")
                if not content:
                    raise LLMGenerationError(
                        "Empty response from Ollama",
                        details={"response": response_data}
                    )
                
                # Extract metadata
                model_version = response_data.get("model", request.model)
                finish_reason = "stop" if response_data.get("done") else "incomplete"
                
                # Token counts (Ollama provides prompt_eval_count and eval_count)
                prompt_tokens = response_data.get("prompt_eval_count")
                completion_tokens = response_data.get("eval_count")
                total_tokens = None
                if prompt_tokens and completion_tokens:
                    total_tokens = prompt_tokens + completion_tokens
                
                logger.info(
                    "Ollama generation successful",
                    model=model_version,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    finish_reason=finish_reason,
                    attempt=attempt
                )
                
                # Track metrics
                llm_latency_seconds.labels(
                    model=model_version, success="true"
                ).observe(latency_ms / 1000.0)
                
                if prompt_tokens:
                    llm_tokens_total.labels(
                        model=model_version, token_type="prompt"
                    ).inc(prompt_tokens)
                if completion_tokens:
                    llm_tokens_total.labels(
                        model=model_version, token_type="completion"
                    ).inc(completion_tokens)
                
                return LLMGenerationResponse(
                    content=content,
                    model_version=model_version,
                    finish_reason=finish_reason,
                    usage_tokens=total_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    created_at=response_data.get("created_at"),
                    raw_metadata={
                        "total_duration": response_data.get("total_duration"),
                        "load_duration": response_data.get("load_duration"),
                        "eval_duration": response_data.get("eval_duration"),
                    }
                )
                
            except httpx.TimeoutException as e:
                logger.warning(
                    "Ollama request timeout",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    timeout=self.timeout,
                    error=str(e)
                )
                last_error = LLMTimeoutError(
                    f"Request timeout after {self.timeout}s",
                    details={"attempt": attempt, "timeout": self.timeout}
                )
                
                if attempt < self.max_retries:
                    backoff = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                    logger.info(f"Retrying after {backoff}s backoff...")
                    await asyncio.sleep(backoff)
                    continue
                raise last_error
                
            except httpx.HTTPStatusError as e:
                # HTTP error from server (4xx, 5xx)
                status_code = e.response.status_code
                error_text = e.response.text
                
                logger.error(
                    "Ollama HTTP error",
                    status_code=status_code,
                    error_text=error_text,
                    attempt=attempt
                )
                
                # Check for specific error cases
                if status_code == 404:
                    raise LLMModelNotAvailableError(
                        f"Model not found: {request.model}",
                        details={"model": request.model, "status": status_code}
                    )
                elif status_code >= 500:
                    # Server error - might be retryable
                    last_error = LLMGenerationError(
                        f"Ollama server error: {status_code}",
                        details={"status": status_code, "error": error_text}
                    )
                    if attempt < self.max_retries:
                        backoff = 2 ** attempt
                        logger.info(f"Server error, retrying after {backoff}s...")
                        await asyncio.sleep(backoff)
                        continue
                    raise last_error
                else:
                    # Client error (4xx) - not retryable
                    raise LLMGenerationError(
                        f"Ollama client error: {status_code}",
                        details={"status": status_code, "error": error_text}
                    )
                    
            except (httpx.NetworkError, httpx.ConnectError) as e:
                logger.warning(
                    "Ollama network error",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(e)
                )
                last_error = LLMConnectionError(
                    f"Network error: {str(e)}",
                    details={"attempt": attempt, "error_type": type(e).__name__}
                )
                
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    logger.info(f"Network error, retrying after {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue
                raise last_error
                
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse Ollama response JSON",
                    error=str(e),
                    attempt=attempt
                )
                raise LLMGenerationError(
                    "Invalid JSON response from Ollama",
                    details={"parse_error": str(e)}
                )
                
            except Exception as e:
                logger.error(
                    "Unexpected error in Ollama generation",
                    error=str(e),
                    error_type=type(e).__name__,
                    attempt=attempt
                )
                raise LLMGenerationError(
                    f"Unexpected error: {str(e)}",
                    details={"error_type": type(e).__name__}
                )
        
        # Should not reach here, but for safety
        if last_error:
            raise last_error
        raise LLMGenerationError("Generation failed after all retries")
    
    async def health_check(self) -> bool:
        """
        Check Ollama server health via GET /api/tags.
        
        Returns True if server responds, False otherwise.
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            logger.debug("Ollama health check passed")
            return True
        except Exception as e:
            logger.warning("Ollama health check failed", error=str(e))
            return False
    
    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """
        Get model information via POST /api/show.
        
        Payload: {"name": "qwen2.5:7b"}
        Response: {
            "modelfile": "...",
            "parameters": "...",
            "template": "...",
            "details": {
                "format": "gguf",
                "family": "qwen2",
                "parameter_size": "7.6B",
                "quantization_level": "Q4_0"
            }
        }
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/show",
                json={"name": model_name},
                timeout=10.0
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug("Retrieved model info", model=model_name, info=data.get("details"))
            return data
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotAvailableError(
                    f"Model not found: {model_name}",
                    details={"model": model_name}
                )
            raise LLMConnectionError(
                f"Failed to get model info: {e}",
                details={"model": model_name, "status": e.response.status_code}
            )
        except Exception as e:
            raise LLMConnectionError(
                f"Error getting model info: {str(e)}",
                details={"model": model_name}
            )
    
    async def list_models(self) -> list[str]:
        """
        List all available models via GET /api/tags.
        
        Returns:
            List of model names (e.g., ["qwen2.5:7b", "llama3.1:8b"])
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=10.0)
            response.raise_for_status()
            
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            logger.debug("Listed available models", count=len(models), models=models)
            return models
            
        except Exception as e:
            logger.error("Failed to list models", error=str(e))
            raise LLMConnectionError(
                f"Failed to list models: {str(e)}",
                details={"error": str(e)}
            )
    
    async def close(self):
        """Close the HTTP client connection."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("Closed Ollama client connection")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
