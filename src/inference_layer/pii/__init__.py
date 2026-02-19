"""
PII redaction on-the-fly.

- redactor.py: Redact PII from text based on annotated pii_entities
  - Used for external LLM calls (if REDACT_FOR_LLM=true)
  - Used for GDPR-compliant storage (if REDACT_FOR_STORAGE=true)
  - Input body is NOT redacted by default (annotated only)
"""
