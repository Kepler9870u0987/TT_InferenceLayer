"""
Multi-stage validation pipeline (4 stages + verifiers).

- pipeline.py: Orchestrator for all validation stages
- stage1_json_parse.py: JSON parsing (hard fail)
- stage2_schema.py: JSON Schema validation (hard fail)
- stage3_business_rules.py: Business rules (candidateid exists, labelid in enum) (hard fail)
- stage4_quality.py: Quality checks (confidence gating, dedup) (warnings only)
- verifiers.py: Evidence presence, keyword presence, spans coherence checks
"""
