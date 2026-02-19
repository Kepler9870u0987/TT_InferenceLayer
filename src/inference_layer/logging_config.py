"""Structured logging configuration using structlog.

Provides JSON output for production (parseable by ELK, Loki, CloudWatch)
and pretty console output for development.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def add_app_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to all log events."""
    event_dict["app"] = "llm-inference-layer"
    return event_dict


def configure_logging(log_level: str = "INFO", environment: str = "development") -> None:
    """Configure structlog for structured logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: Environment name (development, production)
    
    In production mode:
        - JSON output for machine parsing
        - ISO timestamps
        - Exception info included
        
    In development mode:
        - Pretty colored console output
        - Human-readable formatting
    """
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)
    
    # Shared processors for all loggers
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
    ]
    
    # Choose renderer based on environment
    is_production = environment.lower() == "production"
    
    if is_production:
        # JSON output for production (parseable by log aggregators)
        shared_processors.append(structlog.processors.format_exc_info)
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Pretty console output for development
        shared_processors.append(structlog.dev.ExceptionPrettyPrinter())
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    
    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging to work with structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level_int)
    
    root_logger = logging.getLogger()
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level_int)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    
    # Log configuration completed
    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging configured",
        log_level=log_level,
        environment=environment,
        renderer="json" if is_production else "console",
    )
