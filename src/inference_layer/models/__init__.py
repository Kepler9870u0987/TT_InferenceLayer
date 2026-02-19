"""
Pydantic data models for LLM Inference Layer.

Includes:
- Input models (EmailDocument, CandidateKeyword, TriageRequest)
- Output models (EmailTriageResponse, TopicResult, SentimentResult, etc.)
- Enums (TopicsEnum, SentimentEnum, PriorityEnum)
- PipelineVersion (frozen dataclass for audit/backtesting)
"""
