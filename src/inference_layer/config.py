"""
Configuration settings for LLM Inference Layer.

All settings are loaded from environment variables with sensible defaults.
Use .env file for local development (see .env.example).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # === Application ===
    APP_NAME: str = "LLM Inference Layer"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # === Ollama Configuration ===
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"  # Default model, override in .env
    OLLAMA_TIMEOUT: int = 60  # seconds
    FALLBACK_MODELS: list[str] = []  # e.g., ["llama3.1:8b", "mistral:7b"]
    
    # === LLM Generation Parameters ===
    LLM_TEMPERATURE: float = 0.1  # Low for determinism
    LLM_MAX_TOKENS: int = 2048
    LLM_STREAM: bool = False  # Always false for easier validation
    
    # === Input Processing ===
    BODY_TRUNCATION_LIMIT: int = 8000  # chars
    CANDIDATE_TOP_N: int = 100  # Number of candidate keywords to include in prompt
    
    # === Retry & Fallback ===
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_BASE: float = 2.0  # Exponential backoff multiplier
    SHRINK_TOP_N: int = 50  # Reduced top-N for retry with smaller request
    SHRINK_BODY_LIMIT: int = 4000  # Reduced body limit for retry
    
    # === PII Redaction ===
    REDACT_FOR_LLM: bool = False  # True if using external LLM
    REDACT_FOR_STORAGE: bool = True  # Always redact for GDPR-compliant storage
    REDACT_PII_TYPES: list[str] = ["CF", "PHONE_IT", "EMAIL", "NAME"]  # Which PII types to redact
    
    # === Database ===
    DATABASE_URL: str = "postgresql+asyncpg://llm_user:llm_pass@postgres:5432/llm_inference"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # === Redis & Celery ===
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50  # Connection pool size
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    CELERY_TASK_TIME_LIMIT: int = 300  # seconds
    CELERY_WORKER_CONCURRENCY: int = 4
    
    # === Persistence ===
    RESULT_TTL_SECONDS: int = 86400  # 24 hours - how long to keep results in Redis
    
    # === Validation ===
    JSON_SCHEMA_PATH: str = "config/schema/email_triage_v2.json"
    PROMPT_TEMPLATES_DIR: str = "config/prompts"
    MIN_CONFIDENCE_WARNING_THRESHOLD: float = 0.2  # Warn if topic confidence < this
    ENABLE_EVIDENCE_PRESENCE_CHECK: bool = True
    ENABLE_KEYWORD_PRESENCE_CHECK: bool = True
    
    # === Monitoring ===
    PROMETHEUS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    
    # === Pipeline Versioning ===
    DICTIONARY_VERSION: int = 1  # Frozen during batch processing
    INFERENCE_LAYER_VERSION: str = "0.1.0"
    SCHEMA_VERSION: str = "email_triage_v2"
    
    # === Feature Flags ===
    ENABLE_ASYNC_API: bool = True  # Enable Celery-based async endpoints
    ENABLE_BATCH_API: bool = True


# Global settings instance
settings = Settings()
