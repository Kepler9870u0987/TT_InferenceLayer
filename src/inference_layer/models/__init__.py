"""
Pydantic data models for LLM Inference Layer.

Includes:
- Input models (EmailDocument, CandidateKeyword, TriageRequest)
- Output models (EmailTriageResponse, TopicResult, SentimentResult, etc.)
- Enums (TopicsEnum, SentimentEnum, PriorityEnum)
- PipelineVersion (frozen dataclass for audit/backtesting)
- LLM models (LLMGenerationRequest, LLMGenerationResponse, LLMMetadata)
"""

from inference_layer.models.enums import TopicsEnum, SentimentEnum, PriorityEnum
from inference_layer.models.input_models import (
    PiiEntity,
    RemovedSection,
    EmailDocument,
    CandidateKeyword,
    TriageRequest,
)
from inference_layer.models.output_models import (
    KeywordInText,
    EvidenceItem,
    TopicResult,
    SentimentResult,
    PriorityResult,
    EmailTriageResponse,
    TriageResult,
)
from inference_layer.models.pipeline_version import PipelineVersion
from inference_layer.models.llm_models import (
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMMetadata,
)

__all__ = [
    # Enums
    "TopicsEnum",
    "SentimentEnum",
    "PriorityEnum",
    # Input models
    "PiiEntity",
    "RemovedSection",
    "EmailDocument",
    "CandidateKeyword",
    "TriageRequest",
    # Output models
    "KeywordInText",
    "EvidenceItem",
    "TopicResult",
    "SentimentResult",
    "PriorityResult",
    "EmailTriageResponse",
    "TriageResult",
    # Pipeline version
    "PipelineVersion",
    # LLM models
    "LLMGenerationRequest",
    "LLMGenerationResponse",
    "LLMMetadata",
]
