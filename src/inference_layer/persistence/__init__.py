"""
Redis persistence layer.

- redis_client.py: Redis connection pooling for sync and async contexts
- repository.py: Repository pattern for triage results and DLQ entries

Storage Strategy:
- Results stored as JSON with TTL (default 24h)
- DLQ entries stored in Redis List (capped at 10k entries)
- Task ID -> Request UID mapping for Celery task lookups
- Timestamp index for recent results queries
"""

from inference_layer.persistence.redis_client import (
    RedisClient,
    get_redis_client,
    get_async_redis_client,
)
from inference_layer.persistence.repository import (
    TriageRepository,
    AsyncTriageRepository,
)

__all__ = [
    "RedisClient",
    "get_redis_client",
    "get_async_redis_client",
    "TriageRepository",
    "AsyncTriageRepository",
]
