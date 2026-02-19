"""
Stage 2: JSON Schema Validation.

Validate parsed dict against email_triage_v2.json schema.
This is a hard-fail stage: schema violations trigger retry.
"""

import json
import logging
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator

from .exceptions import SchemaValidationError

logger = logging.getLogger(__name__)


class Stage2SchemaValidation:
    """
    Stage 2 validator: Validate against JSON Schema.
    
    Raises SchemaValidationError on schema violations (hard fail).
    """
    
    def __init__(self, schema_path: str):
        """
        Initialize schema validator.
        
        Args:
            schema_path: Path to email_triage_v2.json schema file
        """
        self.schema_path = schema_path
        self._schema: dict | None = None
        self._validator: Draft7Validator | None = None
    
    def _load_schema(self) -> dict:
        """
        Load and cache JSON schema from file.
        
        Returns:
            Loaded schema dict
            
        Raises:
            SchemaValidationError: If schema file cannot be loaded
        """
        if self._schema is not None:
            return self._schema
        
        schema_file = Path(self.schema_path)
        if not schema_file.exists():
            raise SchemaValidationError(
                f"JSON Schema file not found: {self.schema_path}",
                schema_path=self.schema_path
            )
        
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                self._schema = json.load(f)
            
            # Extract the actual schema from the "schema" key if present
            # (Ollama format wraps schema in {"name": "...", "schema": {...}})
            if "schema" in self._schema and isinstance(self._schema["schema"], dict):
                self._schema = self._schema["schema"]
            
            logger.info(f"Loaded JSON Schema from {self.schema_path}")
            return self._schema
            
        except Exception as e:
            raise SchemaValidationError(
                f"Failed to load JSON Schema: {str(e)}",
                schema_path=self.schema_path
            ) from e
    
    def _get_validator(self) -> Draft7Validator:
        """
        Get cached JSON Schema validator.
        
        Returns:
            Draft7Validator instance
        """
        if self._validator is None:
            schema = self._load_schema()
            self._validator = Draft7Validator(schema)
        return self._validator
    
    def validate(self, data: dict) -> None:
        """
        Validate data against JSON Schema.
        
        Args:
            data: Parsed JSON dict to validate
            
        Raises:
            SchemaValidationError: If data doesn't conform to schema
        """
        validator = self._get_validator()
        
        # Collect all validation errors
        errors = list(validator.iter_errors(data))
        
        if errors:
            # Format error messages for logging
            error_messages = []
            for error in errors[:10]:  # Limit to first 10 errors
                path = ".".join(str(p) for p in error.path) if error.path else "root"
                error_messages.append(f"{path}: {error.message}")
            
            raise SchemaValidationError(
                f"JSON Schema validation failed with {len(errors)} error(s)",
                validation_errors=error_messages,
                schema_path=self.schema_path
            )
        
        logger.debug("Stage 2: Successfully validated against JSON Schema")
