"""
Unit tests for LLM Inference Layer.

Test individual components in isolation:
- Data models (serialization, validation, constraints)
- Prompt builder (truncation, top-N, formatting)
- Validation stages (each stage with positive/negative cases)
- Verifiers (evidence presence, keyword presence, spans coherence)
- Retry engine (escalation logic)
- PII redactor
"""
