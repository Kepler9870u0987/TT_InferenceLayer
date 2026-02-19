"""
Stage 1: JSON Parse Validation.

Parse raw LLM response content (string) into Python dict.
This is a hard-fail stage: malformed JSON triggers retry.
"""

import json
import structlog

from inference_layer.monitoring.metrics import validation_failures_total
from .exceptions import JSONParseError

logger = structlog.get_logger(__name__)


class Stage1JSONParse:
    """
    Stage 1 validator: Parse JSON string to dict.
    
    Raises JSONParseError on malformed JSON (hard fail).
    """
    
    def validate(self, content: str) -> dict:
        """
        Parse JSON content from LLM response.
        
        Args:
            content: Raw JSON string from LLM response
            
        Returns:
            Parsed dict representation
            
        Raises:
            JSONParseError: If content is not valid JSON
        """
        if not content or not content.strip():
            validation_failures_total.labels(
                stage="stage1", error_type="empty_content"
            ).inc()
            raise JSONParseError(
                "LLM response content is empty or whitespace-only",
                raw_content=content,
                parse_error="Empty content"
            )
        
        try:
            parsed = json.loads(content)
            
            if not isinstance(parsed, dict):
                validation_failures_total.labels(
                    stage="stage1", error_type="not_json_object"
                ).inc()
                raise JSONParseError(
                    f"LLM response is not a JSON object (got {type(parsed).__name__})",
                    raw_content=content,
                    parse_error=f"Expected dict, got {type(parsed).__name__}"
                )
            
            logger.debug(f"Stage 1: Successfully parsed JSON with {len(parsed)} top-level keys")
            return parsed
            
        except json.JSONDecodeError as e:
            validation_failures_total.labels(
                stage="stage1", error_type="json_decode_error"
            ).inc()
            raise JSONParseError(
                f"Failed to parse LLM response as JSON: {e.msg}",
                raw_content=content,
                parse_error=f"{e.msg} at line {e.lineno} col {e.colno}"
            ) from e
        except JSONParseError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Catch any other unexpected errors
            validation_failures_total.labels(
                stage="stage1", error_type="unexpected_error"
            ).inc()
            raise JSONParseError(
                f"Unexpected error during JSON parsing: {str(e)}",
                raw_content=content,
                parse_error=str(e)
            ) from e
