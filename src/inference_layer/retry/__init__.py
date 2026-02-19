"""
Retry engine with fallback policies.

- engine.py: Retry logic with 4 levels:
  1. Standard retry (up to MAX_RETRIES with exponential backoff)
  2. Shrink request (fewer candidates + shorter body)
  3. Fallback model (alternative LLM)
  4. DLQ routing (Dead Letter Queue for human review)
"""
