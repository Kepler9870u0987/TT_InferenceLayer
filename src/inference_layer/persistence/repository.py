"""
Repository pattern for Redis-based persistence.

Provides CRUD operations for triage results and DLQ entries using Redis.

Storage Strategy:
- Results: Hash per result, key = "triage:result:{request_uid}"
- Task mapping: Hash "triage:task:{task_id}" -> request_uid
- DLQ entries: List "triage:dlq" with JSON entries
- Index by timestamp: Sorted set "triage:results:index" (score = timestamp)
- TTL: Configurable per result type
"""

import json
import structlog
from datetime import datetime
from typing import Optional

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from inference_layer.config import Settings
from inference_layer.models.output_models import TriageResult
from inference_layer.retry.exceptions import RetryExhausted

logger = structlog.get_logger(__name__)


class TriageRepository:
    """
    Repository for triage results and DLQ entries.
    
    Uses Redis for persistence with optional TTL for auto-cleanup.
    """
    
    # Redis key prefixes
    RESULT_PREFIX = "triage:result:"
    TASK_PREFIX = "triage:task:"
    DLQ_KEY = "triage:dlq"
    RESULTS_INDEX = "triage:results:index"
    
    def __init__(self, redis_client: Redis, settings: Settings):
        """
        Initialize repository.
        
        Args:
            redis_client: Redis client instance
            settings: Application settings
        """
        self.redis = redis_client
        self.settings = settings
        self.result_ttl = settings.RESULT_TTL_SECONDS if hasattr(settings, 'RESULT_TTL_SECONDS') else 86400  # 24h default
    
    def save_result(self, result: TriageResult, task_id: Optional[str] = None) -> bool:
        """
        Save triage result to Redis.
        
        Args:
            result: TriageResult to save
            task_id: Optional Celery task ID for mapping
        
        Returns:
            True if saved successfully
        """
        try:
            # Serialize result to JSON
            result_json = result.model_dump_json()
            result_key = f"{self.RESULT_PREFIX}{result.request_uid}"
            
            # Save result with TTL
            self.redis.setex(
                name=result_key,
                time=self.result_ttl,
                value=result_json
            )
            
            # Add to timestamp index for queries
            if result.created_at:
                timestamp = datetime.fromisoformat(result.created_at).timestamp() if isinstance(result.created_at, str) else result.created_at.timestamp()
                self.redis.zadd(
                    self.RESULTS_INDEX,
                    {result.request_uid: timestamp}
                )
            
            # Map task_id to request_uid if provided
            if task_id:
                task_key = f"{self.TASK_PREFIX}{task_id}"
                self.redis.setex(
                    name=task_key,
                    time=self.result_ttl,
                    value=result.request_uid
                )
            
            logger.info(
                "Saved triage result",
                extra={
                    "request_uid": result.request_uid,
                    "task_id": task_id,
                    "ttl": self.result_ttl
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to save triage result",
                extra={"request_uid": result.request_uid, "error": str(e)},
                exc_info=True
            )
            return False
    
    def get_result(self, request_uid: str) -> Optional[TriageResult]:
        """
        Retrieve triage result by request UID.
        
        Args:
            request_uid: Request UID
        
        Returns:
            TriageResult if found, None otherwise
        """
        try:
            result_key = f"{self.RESULT_PREFIX}{request_uid}"
            result_json = self.redis.get(result_key)
            
            if result_json is None:
                logger.debug("Result not found", extra={"request_uid": request_uid})
                return None
            
            # Deserialize from JSON
            result = TriageResult.model_validate_json(result_json)
            
            logger.debug("Retrieved result", extra={"request_uid": request_uid})
            return result
        
        except Exception as e:
            logger.error(
                "Failed to retrieve result",
                extra={"request_uid": request_uid, "error": str(e)},
                exc_info=True
            )
            return None
    
    def get_result_by_task_id(self, task_id: str) -> Optional[TriageResult]:
        """
        Retrieve triage result by Celery task ID.
        
        Args:
            task_id: Celery task ID
        
        Returns:
            TriageResult if found, None otherwise
        """
        try:
            # Get request_uid from task mapping
            task_key = f"{self.TASK_PREFIX}{task_id}"
            request_uid = self.redis.get(task_key)
            
            if request_uid is None:
                logger.debug("Task mapping not found", extra={"task_id": task_id})
                return None
            
            # Get result by request_uid
            return self.get_result(request_uid)
        
        except Exception as e:
            logger.error(
                "Failed to retrieve result by task_id",
                extra={"task_id": task_id, "error": str(e)},
                exc_info=True
            )
            return None
    
    def delete_result(self, request_uid: str) -> bool:
        """
        Delete triage result.
        
        Args:
            request_uid: Request UID
        
        Returns:
            True if deleted
        """
        try:
            result_key = f"{self.RESULT_PREFIX}{request_uid}"
            deleted = self.redis.delete(result_key)
            
            # Remove from index
            self.redis.zrem(self.RESULTS_INDEX, request_uid)
            
            logger.info(
                "Deleted result" if deleted else "Result not found for deletion",
                extra={"request_uid": request_uid}
            )
            
            return bool(deleted)
        
        except Exception as e:
            logger.error(
                "Failed to delete result",
                extra={"request_uid": request_uid, "error": str(e)},
                exc_info=True
            )
            return False
    
    def save_to_dlq(self, exception: RetryExhausted) -> bool:
        """
        Save failed request to Dead Letter Queue.
        
        Args:
            exception: RetryExhausted exception with complete context
        
        Returns:
            True if saved successfully
        """
        try:
            # Build DLQ entry
            dlq_entry = {
                "request_uid": exception.request.email.uid,
                "timestamp": datetime.utcnow().isoformat(),
                "total_attempts": exception.retry_metadata.total_attempts,
                "strategies_used": exception.retry_metadata.strategies_used,
                "total_latency_ms": exception.retry_metadata.total_latency_ms,
                "validation_failures": exception.retry_metadata.validation_failures,
                "last_error": str(exception.last_error),
                "last_error_type": type(exception.last_error).__name__,
                # Include original request for manual review
                "request": exception.request.model_dump(mode="json"),
            }
            
            # Serialize to JSON
            dlq_json = json.dumps(dlq_entry)
            
            # Push to DLQ list (LPUSH = prepend, newest first)
            self.redis.lpush(self.DLQ_KEY, dlq_json)
            
            # Trim to max size (keep last 10000 entries)
            self.redis.ltrim(self.DLQ_KEY, 0, 9999)
            
            logger.error(
                "Saved to DLQ",
                extra={
                    "request_uid": exception.request.email.uid,
                    "total_attempts": exception.retry_metadata.total_attempts,
                    "last_error": str(exception.last_error)
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to save to DLQ",
                extra={"error": str(e)},
                exc_info=True
            )
            return False
    
    def get_dlq_entries(self, limit: int = 100) -> list[dict]:
        """
        Retrieve DLQ entries for manual review.
        
        Args:
            limit: Maximum number of entries to retrieve
        
        Returns:
            List of DLQ entries (newest first)
        """
        try:
            # Get entries from list (LRANGE 0 limit-1)
            entries_json = self.redis.lrange(self.DLQ_KEY, 0, limit - 1)
            
            # Deserialize
            entries = [json.loads(entry) for entry in entries_json]
            
            logger.info("Retrieved DLQ entries", extra={"count": len(entries)})
            return entries
        
        except Exception as e:
            logger.error(
                "Failed to retrieve DLQ entries",
                extra={"error": str(e)},
                exc_info=True
            )
            return []
    
    def get_recent_results(self, limit: int = 100) -> list[TriageResult]:
        """
        Get recent results ordered by timestamp.
        
        Args:
            limit: Maximum number of results
        
        Returns:
            List of TriageResult (newest first)
        """
        try:
            # Get recent request_uids from sorted set (reverse order = newest first)
            request_uids = self.redis.zrevrange(self.RESULTS_INDEX, 0, limit - 1)
            
            # Fetch results
            results = []
            for uid in request_uids:
                result = self.get_result(uid)
                if result:
                    results.append(result)
            
            logger.info("Retrieved recent results", extra={"count": len(results)})
            return results
        
        except Exception as e:
            logger.error(
                "Failed to retrieve recent results",
                extra={"error": str(e)},
                exc_info=True
            )
            return []
    
    def get_stats(self) -> dict:
        """
        Get repository statistics.
        
        Returns:
            Dict with stats (total results, DLQ size, etc.)
        """
        try:
            total_results = self.redis.zcard(self.RESULTS_INDEX)
            dlq_size = self.redis.llen(self.DLQ_KEY)
            
            return {
                "total_results": total_results,
                "dlq_size": dlq_size,
                "result_ttl_seconds": self.result_ttl,
            }
        
        except Exception as e:
            logger.error("Failed to get stats", extra={"error": str(e)})
            return {
                "total_results": -1,
                "dlq_size": -1,
                "error": str(e)
            }


class AsyncTriageRepository:
    """
    Async version of TriageRepository for FastAPI endpoints.
    
    Same functionality as TriageRepository but uses async Redis client.
    """
    
    RESULT_PREFIX = "triage:result:"
    TASK_PREFIX = "triage:task:"
    DLQ_KEY = "triage:dlq"
    RESULTS_INDEX = "triage:results:index"
    
    def __init__(self, redis_client: AsyncRedis, settings: Settings):
        """
        Initialize async repository.
        
        Args:
            redis_client: AsyncRedis client instance
            settings: Application settings
        """
        self.redis = redis_client
        self.settings = settings
        self.result_ttl = settings.RESULT_TTL_SECONDS if hasattr(settings, 'RESULT_TTL_SECONDS') else 86400
    
    async def save_result(self, result: TriageResult, task_id: Optional[str] = None) -> bool:
        """Save triage result (async version)."""
        try:
            result_json = result.model_dump_json()
            result_key = f"{self.RESULT_PREFIX}{result.request_uid}"
            
            await self.redis.setex(
                name=result_key,
                time=self.result_ttl,
                value=result_json
            )
            
            if result.created_at:
                timestamp = datetime.fromisoformat(result.created_at).timestamp() if isinstance(result.created_at, str) else result.created_at.timestamp()
                await self.redis.zadd(
                    self.RESULTS_INDEX,
                    {result.request_uid: timestamp}
                )
            
            if task_id:
                task_key = f"{self.TASK_PREFIX}{task_id}"
                await self.redis.setex(
                    name=task_key,
                    time=self.result_ttl,
                    value=result.request_uid
                )
            
            logger.info(
                "Saved triage result (async)",
                extra={"request_uid": result.request_uid, "task_id": task_id}
            )
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to save result (async)",
                extra={"request_uid": result.request_uid, "error": str(e)},
                exc_info=True
            )
            return False
    
    async def get_result(self, request_uid: str) -> Optional[TriageResult]:
        """Retrieve result by UID (async version)."""
        try:
            result_key = f"{self.RESULT_PREFIX}{request_uid}"
            result_json = await self.redis.get(result_key)
            
            if result_json is None:
                return None
            
            result = TriageResult.model_validate_json(result_json)
            logger.debug("Retrieved result (async)", extra={"request_uid": request_uid})
            return result
        
        except Exception as e:
            logger.error(
                "Failed to retrieve result (async)",
                extra={"request_uid": request_uid, "error": str(e)},
                exc_info=True
            )
            return None
    
    async def get_result_by_task_id(self, task_id: str) -> Optional[TriageResult]:
        """Retrieve result by task ID (async version)."""
        try:
            task_key = f"{self.TASK_PREFIX}{task_id}"
            request_uid = await self.redis.get(task_key)
            
            if request_uid is None:
                return None
            
            return await self.get_result(request_uid)
        
        except Exception as e:
            logger.error(
                "Failed to retrieve result by task_id (async)",
                extra={"task_id": task_id, "error": str(e)},
                exc_info=True
            )
            return None
    
    async def get_stats(self) -> dict:
        """Get repository statistics (async version)."""
        try:
            total_results = await self.redis.zcard(self.RESULTS_INDEX)
            dlq_size = await self.redis.llen(self.DLQ_KEY)
            
            return {
                "total_results": total_results,
                "dlq_size": dlq_size,
                "result_ttl_seconds": self.result_ttl,
            }
        
        except Exception as e:
            logger.error("Failed to get stats (async)", extra={"error": str(e)})
            return {
                "total_results": -1,
                "dlq_size": -1,
                "error": str(e)
            }
