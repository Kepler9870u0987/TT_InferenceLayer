"""
Prompt builder for LLM requests.

Responsible for:
- Loading and rendering Jinja2 templates (system + user prompts)
- Truncating email body intelligently (sentence boundary)
- Selecting top-N candidate keywords
- Applying PII redaction on-the-fly if enabled
- Constructing complete LLMGenerationRequest with schema
"""

import json
from pathlib import Path
from typing import Optional, List
from jinja2 import Environment, FileSystemLoader, Template
import structlog

from inference_layer.models.input_models import TriageRequest, CandidateKeyword
from inference_layer.models.llm_models import LLMGenerationRequest
from inference_layer.models.enums import TopicsEnum
from inference_layer.llm.text_utils import truncate_at_sentence_boundary, adjust_pii_spans_after_truncation
from inference_layer.pii.redactor import redact_pii_for_llm, redact_pii_in_candidates


logger = structlog.get_logger(__name__)


class PromptBuilder:
    """
    Build prompts for LLM requests from TriageRequest objects.
    
    Handles:
    - Template rendering (Jinja2)
    - Text truncation (sentence boundary)
    - Top-N candidate selection
    - PII redaction (configurable)
    - JSON Schema inclusion
    """
    
    def __init__(
        self,
        templates_dir: Path,
        schema_path: Path,
        body_truncation_limit: int = 8000,
        shrink_body_limit: int = 4000,
        candidate_top_n: int = 100,
        shrink_top_n: int = 50,
        redact_for_llm: bool = False,
        default_model: str = "qwen2.5:7b",
        default_temperature: float = 0.1,
        default_max_tokens: int = 2048,
    ):
        """
        Initialize prompt builder.
        
        Args:
            templates_dir: Directory containing prompt templates
            schema_path: Path to JSON Schema file (email_triage_v2.json)
            body_truncation_limit: Max body characters (normal mode)
            shrink_body_limit: Max body characters (shrink mode)
            candidate_top_n: Max candidates to send (normal mode)
            shrink_top_n: Max candidates to send (shrink mode)
            redact_for_llm: Whether to redact PII before sending to LLM
            default_model: Default model name
            default_temperature: Default temperature
            default_max_tokens: Default max tokens
        """
        self.templates_dir = Path(templates_dir)
        self.schema_path = Path(schema_path)
        self.body_truncation_limit = body_truncation_limit
        self.shrink_body_limit = shrink_body_limit
        self.candidate_top_n = candidate_top_n
        self.shrink_top_n = shrink_top_n
        self.redact_for_llm = redact_for_llm
        self.default_model = default_model
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        
        # Load Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False  # We're generating prompts, not HTML
        )
        
        # Load templates
        try:
            self.system_template = self.jinja_env.get_template("system_prompt.txt")
            self.user_template = self.jinja_env.get_template("user_prompt_template.txt")
            logger.info("Loaded prompt templates", templates_dir=str(self.templates_dir))
        except Exception as e:
            logger.error("Failed to load prompt templates", error=str(e))
            raise
        
        # Load JSON Schema
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self.json_schema = json.load(f)
            logger.info("Loaded JSON Schema", schema_path=str(self.schema_path))
        except Exception as e:
            logger.error("Failed to load JSON Schema", error=str(e), path=str(self.schema_path))
            raise
        
        logger.info(
            "PromptBuilder initialized",
            body_truncation_limit=body_truncation_limit,
            shrink_body_limit=shrink_body_limit,
            candidate_top_n=candidate_top_n,
            shrink_top_n=shrink_top_n,
            redact_for_llm=redact_for_llm
        )
    
    def build_system_prompt(self) -> str:
        """
        Render system prompt from template.
        
        System prompt is static (no variables).
        
        Returns:
            Rendered system prompt as string
        """
        return self.system_template.render().strip()
    
    def build_user_prompt(
        self,
        request: TriageRequest,
        shrink_mode: bool = False
    ) -> tuple[str, dict]:
        """
        Build user prompt from TriageRequest.
        
        Steps:
        1. Truncate body text (sentence boundary)
        2. Adjust PII spans after truncation
        3. Apply PII redaction if enabled
        4. Select top-N candidates
        5. Render template
        
        Args:
            request: TriageRequest with email and candidates
            shrink_mode: If True, use shrink limits (fewer candidates, shorter body)
            
        Returns:
            Tuple of (rendered_prompt, metadata_dict)
            metadata includes: truncation info, candidates count, redaction applied
        """
        email = request.email
        
        # Determine limits based on mode
        body_limit = self.shrink_body_limit if shrink_mode else self.body_truncation_limit
        top_n = self.shrink_top_n if shrink_mode else self.candidate_top_n
        
        logger.debug(
            "Building user prompt",
            shrink_mode=shrink_mode,
            body_limit=body_limit,
            top_n=top_n,
            original_body_length=len(email.body_text_canonical)
        )
        
        # 1. Truncate body
        original_body = email.body_text_canonical
        truncated_body = truncate_at_sentence_boundary(original_body, body_limit)
        truncation_applied = len(truncated_body) < len(original_body)
        
        # 2. Adjust PII spans after truncation
        adjusted_pii = adjust_pii_spans_after_truncation(
            pii_entities=email.pii_entities or [],
            truncated_length=len(truncated_body),
            original_text=original_body,
            truncated_text=truncated_body
        )
        
        # 3. Apply PII redaction if enabled
        if self.redact_for_llm:
            redacted_body = redact_pii_for_llm(
                text=truncated_body,
                pii_entities=adjusted_pii,
                redact_enabled=True
            )
        else:
            redacted_body = truncated_body
        
        # 4. Select top-N candidates (pre-sorted by score in TriageRequest)
        candidates = request.candidate_keywords[:top_n]
        
        # 5. Redact PII from candidates if enabled
        if self.redact_for_llm and adjusted_pii:
            candidates = redact_pii_in_candidates(
                candidates=candidates,
                pii_entities=adjusted_pii,
                body_text=redacted_body,
                redact_enabled=True
            )
        
        # 6. Prepare template variables
        allowed_topics = [topic.value for topic in TopicsEnum]
        
        # Convert candidates to dict for template
        candidates_dicts = [
            {
                "candidate_id": c.candidate_id,
                "term": c.term,
                "lemma": c.lemma,
                "count": c.count,
                "score": round(c.score, 2) if c.score else 0.0
            }
            for c in candidates
        ]
        
        # 7. Render template
        rendered = self.user_template.render(
            dictionary_version=request.dictionary_version,
            subject=email.subject_canonical or "(no subject)",
            from_addr=email.from_addr_redacted or "(unknown)",
            body=redacted_body,
            allowed_topics=allowed_topics,
            candidate_keywords=candidates_dicts
        ).strip()
        
        # 8. Build metadata
        metadata = {
            "truncation_applied": truncation_applied,
            "original_body_length": len(original_body),
            "truncated_body_length": len(truncated_body),
            "final_body_length": len(redacted_body),
            "pii_redaction_applied": self.redact_for_llm,
            "pii_entities_count": len(adjusted_pii),
            "candidates_count": len(candidates),
            "shrink_mode": shrink_mode
        }
        
        logger.info(
            "User prompt built",
            **metadata,
            prompt_length=len(rendered)
        )
        
        return rendered, metadata
    
    def build_full_request(
        self,
        request: TriageRequest,
        shrink_mode: bool = False,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> tuple[LLMGenerationRequest, dict]:
        """
        Build complete LLMGenerationRequest.
        
        Combines system + user prompts and includes JSON Schema.
        
        Args:
            request: TriageRequest
            shrink_mode: Whether to use shrink limits
            model: Override default model
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            
        Returns:
            Tuple of (LLMGenerationRequest, metadata_dict)
        """
        # Build prompts
        system_prompt = self.build_system_prompt()
        user_prompt, user_metadata = self.build_user_prompt(request, shrink_mode=shrink_mode)
        
        # Combine system + user (format depends on LLM, but default is concatenation)
        # For Ollama, we typically just concatenate since there's one "prompt" field
        # Some models use special tokens like <|system|>, <|user|> but that's model-specific
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Override parameters if provided
        final_model = model or self.default_model
        final_temperature = temperature if temperature is not None else self.default_temperature
        final_max_tokens = max_tokens or self.default_max_tokens
        
        # Build LLMGenerationRequest
        llm_request = LLMGenerationRequest(
            prompt=full_prompt,
            model=final_model,
            temperature=final_temperature,
            max_tokens=final_max_tokens,
            format_schema=self.json_schema,  # Include schema for structured output
            stream=False,  # Always False for validation
        )
        
        # Enhanced metadata
        metadata = {
            **user_metadata,
            "model": final_model,
            "temperature": final_temperature,
            "max_tokens": final_max_tokens,
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt),
            "full_prompt_length": len(full_prompt),
            "schema_included": True
        }
        
        logger.info(
            "Full LLM request built",
            model=final_model,
            temperature=final_temperature,
            max_tokens=final_max_tokens,
            full_prompt_length=len(full_prompt),
            shrink_mode=shrink_mode
        )
        
        return llm_request, metadata
