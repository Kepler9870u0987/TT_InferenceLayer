"""
Celery application configuration for async task processing.

This module initializes the Celery app with Redis broker and result backend.
Tasks are defined in triage_tasks.py.
"""

from celery import Celery

from inference_layer.config import settings

# Initialize Celery app
celery_app = Celery(
    "inference_layer",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    # Task execution
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,  # Hard limit (kills task)
    task_soft_time_limit=settings.CELERY_TASK_TIME_LIMIT - 30,  # Soft limit (raises exception)
    
    # Worker settings
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,  # Fetch one task at a time (better for long tasks)
    worker_max_tasks_per_child=100,  # Restart worker after N tasks (prevent memory leaks)
    
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Enable extended result format (with task args)
    
    # Task tracking
    task_track_started=True,  # Update state to STARTED when task begins
    task_acks_late=True,  # Acknowledge task after completion (not before)
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    
    # Retry policy
    task_default_retry_delay=60,  # Wait 60s before retry
    task_max_retries=3,  # Max 3 retries for task-level failures
)

# Auto-discover tasks from tasks module
celery_app.autodiscover_tasks(["inference_layer.tasks"])
