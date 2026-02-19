"""
Custom exceptions for the LLM client layer.

These exceptions provide structured error handling for LLM operations,
allowing the retry engine and validation pipeline to distinguish between
different failure modes and apply appropriate recovery strategies.
"""


class LLMClientError(Exception):
    """
    Base exception for all LLM client errors.
    
    All LLM-specific exceptions inherit from this to allow catching
    any LLM-related error with a single except clause.
    """
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LLMConnectionError(LLMClientError):
    """
    Raised when unable to connect to the LLM inference server.
    
    Includes network errors, timeouts, DNS failures, etc.
    This error type triggers network-level retries with backoff.
    """
    pass


class LLMGenerationError(LLMClientError):
    """
    Raised when the LLM server returns an error during generation.
    
    Examples:
    - Model not found
    - GPU out of memory
    - Invalid parameters
    - Generation interrupted
    
    This error type may trigger fallback to alternative model.
    """
    pass


class LLMSchemaViolationError(LLMClientError):
    """
    Raised when LLM output doesn't conform to the requested schema.
    
    This is specific to structured output modes where we expect the LLM
    to follow a JSON Schema. If the server claims to support schema
    enforcement but returns non-conforming output, this is raised.
    
    This error type triggers validation retry (possibly with shrunk request).
    """
    pass


class LLMRateLimitError(LLMClientError):
    """
    Raised when the LLM server rate-limits the request.
    
    For future use with external API providers (OpenAI, Anthropic, etc.)
    that have rate limits. Currently not used with self-hosted Ollama.
    
    This error type triggers exponential backoff retry.
    """
    pass


class LLMTimeoutError(LLMConnectionError):
    """
    Raised when the LLM generation exceeds the timeout threshold.
    
    Separate from generic connection errors to allow specific handling
    (e.g., retry with shorter body/fewer candidates).
    """
    pass


class LLMModelNotAvailableError(LLMGenerationError):
    """
    Raised when the requested model is not available on the server.
    
    This error type triggers immediate fallback to alternative model
    without retrying the same model.
    """
    pass
