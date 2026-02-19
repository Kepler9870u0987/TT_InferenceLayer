"""Custom Prometheus metrics for LLM Inference Layer.

These metrics are exposed at /metrics endpoint and should be scraped by Prometheus.
Alert rules should be configured for:
- validation_failures_total (high error rate)
- unknown_topic_ratio (high UNKNOWNTOPIC ratio indicates drift or poor coverage)
- dlq_entries_total (increasing DLQ entries require manual review)
- retries_total (high retry rate indicates model instability)
"""

from prometheus_client import Counter, Gauge, Histogram

# === Validation Metrics ===

validation_failures_total = Counter(
    "validation_failures_total",
    "Total validation failures by stage and error type",
    ["stage", "error_type"],
)
"""
Validation failures counter by stage and error type.

Labels:
- stage: stage1 (JSON parse), stage2 (schema), stage3 (business rules), stage4 (quality)
- error_type: json_parse_error, schema_validation_error, business_rule_violation, etc.

Alert thresholds:
- WARN: rate > 5% of total requests
- CRITICAL: rate > 15% of total requests
"""

# === Retry Metrics ===

retries_total = Counter(
    "retries_total",
    "Total retry attempts by strategy and outcome",
    ["strategy", "success"],
)
"""
Retry attempts counter by strategy and success/failure.

Labels:
- strategy: standard (exponential backoff), shrink (reduced payload), fallback (alternate model)
- success: true (retry succeeded), false (retry failed)

Alert thresholds:
- WARN: retry rate > 10% of total requests
- CRITICAL: retry rate > 30% of total requests
"""

# === DLQ (Dead Letter Queue) Metrics ===

dlq_entries_total = Counter(
    "dlq_entries_total",
    "Total entries added to DLQ by reason",
    ["reason"],
)
"""
DLQ entries counter by failure reason.

Labels:
- reason: retry_exhausted, validation_failed, llm_error, timeout, etc.

Alert thresholds:
- WARN: any DLQ entry (requires manual review)
- CRITICAL: DLQ entry rate > 1% of total requests
"""

# === Topic Distribution Metrics ===

topic_distribution_total = Counter(
    "topic_distribution_total",
    "Total topic classifications by topic label",
    ["topic"],
)
"""
Topic distribution counter by topic label.

Labels:
- topic: FATTURAZIONE, ASSISTENZATECNICA, RECLAMO, CONTRATTO, UNKNOWNTOPIC, etc.

Used to calculate unknown_topic_ratio and detect distribution drift.
"""

unknown_topic_ratio = Gauge(
    "unknown_topic_ratio",
    "Ratio of UNKNOWNTOPIC to total topics (sliding window)",
)
"""
Ratio of UNKNOWNTOPIC classifications to total topics.

Calculation: count(UNKNOWNTOPIC) / count(all topics) over sliding window.
High ratio indicates:
- Poor dictionary coverage
- Emerging topics not in taxonomy
- Model drift

Alert thresholds:
- WARN: ratio > 0.2 (20% unknown)
- CRITICAL: ratio > 0.4 (40% unknown)
"""

# === LLM Performance Metrics ===

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM generation latency in seconds",
    ["model", "success"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)
"""
LLM generation latency histogram.

Labels:
- model: Model name (e.g., qwen2.5:7b, llama3.1:8b)
- success: true (generation succeeded), false (generation failed)

Buckets optimized for LLM inference (0.5s to 120s).

Alert thresholds:
- WARN: p95 > 30s
- CRITICAL: p95 > 60s
"""

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens consumed by model and type",
    ["model", "token_type"],
)
"""
Token consumption counter.

Labels:
- model: Model name
- token_type: prompt (input tokens), completion (output tokens)

Used for cost estimation and capacity planning.
"""

# === Dictionary Collision Metrics ===

dictionary_collision_total = Counter(
    "dictionary_collision_total",
    "Dictionary version collisions (request vs expected)",
    ["expected_version", "received_version"],
)
"""
Dictionary version collision counter.

Labels:
- expected_version: Expected dictionary_version (from settings)
- received_version: Received dictionary_version (from request)

High collision rate indicates:
- Misaligned upstream/downstream pipeline versions
- Stale requests being processed

Alert thresholds:
- WARN: collision rate > 1% of total requests
"""
