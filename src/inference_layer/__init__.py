"""
LLM Inference Layer for Thread Classificator Mail Pipeline.

Transforms canonicalized emails into structured, auditable output containing:
- Topics (multi-label classification)
- Sentiment analysis
- Priority assessment
- Anchored keywords and evidence

Architecture: FastAPI orchestrator + Ollama/SGLang inference + multi-stage validation
"""

__version__ = "0.1.0"
