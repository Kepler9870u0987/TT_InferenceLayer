"""
Validation-specific exceptions for multi-stage validation pipeline.

These exceptions are designed to be caught by the retry engine, which will:
- Retry standard on ValidationError (Stages 1-3 failures)
- Apply shrink strategy if retry fails
- Route to DLQ if all retry strategies exhausted
"""

from typing import Any


class ValidationError(Exception):
    """
    Base exception for all validation errors.
    
    Raised during Stages 1-3 (hard failures that trigger retry).
    """
    
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """
        Initialize validation error.
        
        Args:
            message: Human-readable error description
            details: Structured error data for logging/metrics
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class JSONParseError(ValidationError):
    """
    Stage 1: JSON parsing failed.
    
    Raised when LLM response content is not valid JSON.
    """
    
    def __init__(self, message: str, raw_content: str | None = None, parse_error: str | None = None):
        """
        Initialize JSON parse error.
        
        Args:
            message: Error description
            raw_content: First 500 chars of malformed content (for debugging)
            parse_error: Original json.JSONDecodeError message
        """
        details = {}
        if raw_content:
            # Include first 500 chars for debugging, avoid excessive logging
            details["content_snippet"] = raw_content[:500]
        if parse_error:
            details["parse_error"] = parse_error
        
        super().__init__(message, details)


class SchemaValidationError(ValidationError):
    """
    Stage 2: JSON Schema validation failed.
    
    Raised when parsed JSON doesn't conform to email_triage_v2.json schema.
    """
    
    def __init__(
        self,
        message: str,
        validation_errors: list[str] | None = None,
        schema_path: str | None = None
    ):
        """
        Initialize schema validation error.
        
        Args:
            message: Error description
            validation_errors: List of jsonschema validation error messages
            schema_path: Path to the schema file used for validation
        """
        details = {}
        if validation_errors:
            details["validation_errors"] = validation_errors
        if schema_path:
            details["schema_path"] = schema_path
        
        super().__init__(message, details)


class BusinessRuleViolation(ValidationError):
    """
    Stage 3: Business rules validation failed.
    
    Raised when LLM output violates business constraints:
    - candidateid not in input candidates (invented keyword)
    - labelid not in TopicsEnum (invented topic)
    - dictionaryversion mismatch
    """
    
    def __init__(
        self,
        message: str,
        rule_name: str | None = None,
        invalid_value: Any | None = None,
        expected_values: list[str] | None = None,
        field_path: str | None = None
    ):
        """
        Initialize business rule violation.
        
        Args:
            message: Error description
            rule_name: Name of the violated rule (e.g., "candidateid_exists")
            invalid_value: The invalid value that caused the violation
            expected_values: List of valid values (for enum violations)
            field_path: JSON path to the violating field (e.g., "topics[0].labelid")
        """
        details = {}
        if rule_name:
            details["rule_name"] = rule_name
        if invalid_value is not None:
            details["invalid_value"] = str(invalid_value)
        if expected_values:
            details["expected_values"] = expected_values[:20]  # Limit to first 20
        if field_path:
            details["field_path"] = field_path
        
        super().__init__(message, details)
