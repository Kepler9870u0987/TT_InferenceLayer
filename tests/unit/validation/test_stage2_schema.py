"""
Unit tests for Stage 2: JSON Schema Validation.
"""

import pytest

from inference_layer.validation.stage2_schema import Stage2SchemaValidation
from inference_layer.validation.exceptions import SchemaValidationError


class TestStage2SchemaValidation:
    """Test suite for Stage 2 JSON Schema validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Use actual schema file from config
        self.stage2 = Stage2SchemaValidation("config/schema/email_triage_v2.json")
    
    def test_valid_minimal_response(self):
        """Test validation of minimal valid response."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": ["response_required"]
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {
                            "candidateid": "hash_001",
                            "lemma": "contratto",
                            "count": 2
                        }
                    ],
                    "evidence": [
                        {
                            "quote": "Vorrei informazioni sul contratto."
                        }
                    ]
                }
            ]
        }
        
        # Should not raise any exception
        self.stage2.validate(data)
    
    def test_missing_required_field_raises_error(self):
        """Test that missing required field raises SchemaValidationError."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            # Missing "priority" (required)
            "topics": []
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
        assert exc_info.value.details.get("validation_errors")
    
    def test_invalid_enum_value_raises_error(self):
        """Test that invalid enum value raises SchemaValidationError."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "INVALID_SENTIMENT",  # Not in enum
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "h1", "lemma": "test", "count": 1}
                    ],
                    "evidence": [{"quote": "test"}]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_additional_properties_raises_error(self):
        """Test that additionalProperties violation raises error."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8,
                "unexpected_field": "should not be here"  # additionalProperties: false
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "h1", "lemma": "test", "count": 1}
                    ],
                    "evidence": [{"quote": "test"}]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_array_min_items_violation_raises_error(self):
        """Test that minItems constraint violation raises error."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": []  # minItems: 1
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_array_max_items_violation_raises_error(self):
        """Test that maxItems constraint violation raises error."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": ["s1", "s2", "s3", "s4", "s5", "s6", "s7"]  # maxItems: 6
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "h1", "lemma": "test", "count": 1}
                    ],
                    "evidence": [{"quote": "test"}]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_confidence_out_of_range_raises_error(self):
        """Test that confidence value outside [0, 1] raises error."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 1.5  # max: 1
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "h1", "lemma": "test", "count": 1}
                    ],
                    "evidence": [{"quote": "test"}]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_evidence_quote_too_long_raises_error(self):
        """Test that evidence quote exceeding maxLength raises error."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "h1", "lemma": "test", "count": 1}
                    ],
                    "evidence": [
                        {
                            "quote": "x" * 201  # maxLength: 200
                        }
                    ]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_invalid_span_format_raises_error(self):
        """Test that invalid span format (not [int, int]) raises error."""
        data = {
            "dictionaryversion": 1,
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {
                            "candidateid": "h1",
                            "lemma": "test",
                            "count": 1,
                            "spans": [[10, 15, 20]]  # Should be [int, int], not [int, int, int]
                        }
                    ],
                    "evidence": [{"quote": "test"}]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_wrong_type_raises_error(self):
        """Test that wrong field type raises SchemaValidationError."""
        data = {
            "dictionaryversion": "not_an_int",  # Should be integer
            "sentiment": {
                "value": "neutral",
                "confidence": 0.8
            },
            "priority": {
                "value": "medium",
                "confidence": 0.7,
                "signals": []
            },
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "confidence": 0.9,
                    "keywordsintext": [
                        {"candidateid": "h1", "lemma": "test", "count": 1}
                    ],
                    "evidence": [{"quote": "test"}]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_schema_file_not_found_raises_error(self):
        """Test that non-existent schema file raises SchemaValidationError."""
        stage2 = Stage2SchemaValidation("nonexistent/schema.json")
        
        with pytest.raises(SchemaValidationError) as exc_info:
            stage2.validate({"test": "data"})
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_multiple_errors_collected(self):
        """Test that multiple validation errors are collected."""
        data = {
            # Missing dictionaryversion
            "sentiment": {
                "value": "INVALID",  # Invalid enum
                "confidence": 2.0  # Out of range
            },
            # Missing priority
            "topics": []  # minItems: 1
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            self.stage2.validate(data)
        
        # Should have collected multiple errors
        assert len(exc_info.value.details.get("validation_errors", [])) > 1
