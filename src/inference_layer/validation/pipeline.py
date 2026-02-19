"""
Validation Pipeline: Multi-stage validation orchestrator.

Coordinates all 4 validation stages + verifiers:
- Stage 1: JSON Parse (hard fail)
- Stage 2: JSON Schema (hard fail)
- Stage 3: Business Rules (hard fail)
- Stage 4: Quality Checks (warnings)
- Verifiers: Evidence/Keyword/Span presence (warnings)

Stages 1-3 raise exceptions (caught by retry engine).
Stage 4 + verifiers accumulate warnings (non-blocking).
"""

import logging
from dataclasses import dataclass

from pydantic import ValidationError as PydanticValidationError

from ..config import Settings
from ..models.input_models import TriageRequest
from ..models.llm_models import LLMGenerationResponse
from ..models.output_models import EmailTriageResponse
from .exceptions import ValidationError
from .stage1_json_parse import Stage1JSONParse
from .stage2_schema import Stage2SchemaValidation
from .stage3_business_rules import Stage3BusinessRules
from .stage4_quality import Stage4QualityChecks
from .verifiers import (
    EvidencePresenceVerifier,
    KeywordPresenceVerifier,
    SpansCoherenceVerifier,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationContext:
    """
    Context passed through validation pipeline.
    
    Contains original request, settings, and accumulated warnings.
    """
    original_request: TriageRequest
    settings: Settings
    warnings: list[str]


class ValidationPipeline:
    """
    Multi-stage validation pipeline orchestrator.
    
    Validates LLM outputs through 4 stages + verifiers, enforcing hard
    constraints and accumulating quality warnings.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize validation pipeline.
        
        Args:
            settings: Application settings with validation config
        """
        self.settings = settings
        
        # Initialize hard-fail stages (1-3)
        self.stage1 = Stage1JSONParse()
        self.stage2 = Stage2SchemaValidation(settings.JSON_SCHEMA_PATH)
        self.stage3 = Stage3BusinessRules()
        
        # Initialize warning stages (4)
        self.stage4 = Stage4QualityChecks(
            min_confidence_threshold=settings.MIN_CONFIDENCE_WARNING_THRESHOLD
        )
        
        # Initialize verifiers (optional, configurable)
        self.verifiers = []
        if settings.ENABLE_EVIDENCE_PRESENCE_CHECK:
            self.verifiers.append(EvidencePresenceVerifier())
        if settings.ENABLE_KEYWORD_PRESENCE_CHECK:
            self.verifiers.append(KeywordPresenceVerifier())
        # Span coherence always enabled (cheap and useful)
        self.verifiers.append(SpansCoherenceVerifier())
        
        logger.info(
            f"ValidationPipeline initialized with {len(self.verifiers)} verifiers "
            f"(evidence: {settings.ENABLE_EVIDENCE_PRESENCE_CHECK}, "
            f"keyword: {settings.ENABLE_KEYWORD_PRESENCE_CHECK})"
        )
    
    async def validate(
        self,
        llm_response: LLMGenerationResponse,
        request: TriageRequest
    ) -> tuple[EmailTriageResponse, list[str]]:
        """
        Run full validation pipeline on LLM response.
        
        Args:
            llm_response: Raw LLM generation response
            request: Original triage request with email and candidates
            
        Returns:
            Tuple of (validated EmailTriageResponse, list of warning strings)
            
        Raises:
            ValidationError: If any hard validation stage fails (Stages 1-3)
        """
        warnings: list[str] = []
        
        logger.info(
            f"Starting validation pipeline for request with "
            f"{len(request.candidate_keywords)} candidates"
        )
        
        try:
            # Stage 1: Parse JSON (hard fail)
            logger.debug("Stage 1: Parsing JSON...")
            parsed_dict = self.stage1.validate(llm_response.content)
            
            # Stage 2: Validate against JSON Schema (hard fail)
            logger.debug("Stage 2: Validating JSON Schema...")
            self.stage2.validate(parsed_dict)
            
            # Parse dict into Pydantic model (between Stage 2 and 3)
            logger.debug("Parsing dict into EmailTriageResponse model...")
            try:
                response = EmailTriageResponse.model_validate(parsed_dict)
            except PydanticValidationError as e:
                # Convert Pydantic validation error to our ValidationError
                error_messages = [
                    f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                    for err in e.errors()
                ]
                from .exceptions import SchemaValidationError
                raise SchemaValidationError(
                    f"Pydantic model validation failed: {len(e.errors())} error(s)",
                    validation_errors=error_messages
                )
            
            # Stage 3: Business rules (hard fail)
            logger.debug("Stage 3: Validating business rules...")
            self.stage3.validate(response, request)
            
            # Stage 4: Quality checks (warnings only)
            logger.debug("Stage 4: Running quality checks...")
            quality_warnings = self.stage4.validate(response)
            warnings.extend(quality_warnings)
            
            # Run verifiers (warnings only)
            logger.debug(f"Running {len(self.verifiers)} verifiers...")
            for verifier in self.verifiers:
                verifier_warnings = verifier.verify(response, request)
                warnings.extend(verifier_warnings)
            
            # Log summary
            if warnings:
                logger.warning(
                    f"Validation completed with {len(warnings)} warning(s): "
                    f"{warnings[:3]}{'...' if len(warnings) > 3 else ''}"
                )
            else:
                logger.info("Validation completed successfully with no warnings")
            
            return response, warnings
            
        except ValidationError:
            # Re-raise our validation errors for retry engine
            raise
        except Exception as e:
            # Wrap unexpected errors as ValidationError
            logger.exception(f"Unexpected error during validation: {e}")
            raise ValidationError(
                f"Unexpected validation error: {str(e)}",
                details={"error_type": type(e).__name__}
            ) from e
