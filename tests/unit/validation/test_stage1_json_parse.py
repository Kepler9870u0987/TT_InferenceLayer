"""
Unit tests for Stage 1: JSON Parse.
"""

import pytest

from inference_layer.validation.stage1_json_parse import Stage1JSONParse
from inference_layer.validation.exceptions import JSONParseError


class TestStage1JSONParse:
    """Test suite for Stage 1 JSON parsing."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.stage1 = Stage1JSONParse()
    
    def test_valid_json_object(self):
        """Test parsing valid JSON object."""
        content = '{"dictionaryversion": 123, "topics": []}'
        result = self.stage1.validate(content)
        
        assert isinstance(result, dict)
        assert result["dictionaryversion"] == 123
        assert result["topics"] == []
    
    def test_valid_json_with_nested_structure(self):
        """Test parsing complex nested JSON."""
        content = '''
        {
            "dictionaryversion": 1,
            "topics": [
                {
                    "labelid": "CONTRATTO",
                    "keywordsintext": [
                        {"candidateid": "hash_001", "lemma": "contratto"}
                    ]
                }
            ]
        }
        '''
        result = self.stage1.validate(content)
        
        assert isinstance(result, dict)
        assert len(result["topics"]) == 1
        assert result["topics"][0]["labelid"] == "CONTRATTO"
    
    def test_empty_string_raises_error(self):
        """Test that empty string raises JSONParseError."""
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate("")
        
        assert "empty or whitespace-only" in str(exc_info.value)
    
    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises JSONParseError."""
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate("   \n\t  ")
        
        assert "empty or whitespace-only" in str(exc_info.value)
    
    def test_malformed_json_raises_error(self):
        """Test that malformed JSON raises JSONParseError."""
        content = '{"dictionaryversion": 123, "topics": ['  # Missing closing brackets
        
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate(content)
        
        assert "Failed to parse" in str(exc_info.value)
        assert exc_info.value.details.get("parse_error")
    
    def test_json_array_not_object_raises_error(self):
        """Test that JSON array (not object) raises JSONParseError."""
        content = '["item1", "item2"]'
        
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate(content)
        
        assert "not a JSON object" in str(exc_info.value)
        assert "list" in str(exc_info.value)
    
    def test_json_string_not_object_raises_error(self):
        """Test that JSON string (not object) raises JSONParseError."""
        content = '"just a string"'
        
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate(content)
        
        assert "not a JSON object" in str(exc_info.value)
    
    def test_json_number_not_object_raises_error(self):
        """Test that JSON number (not object) raises JSONParseError."""
        content = '42'
        
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate(content)
        
        assert "not a JSON object" in str(exc_info.value)
    
    def test_error_includes_content_snippet(self):
        """Test that error includes first 500 chars of malformed content."""
        content = '{"invalid": ' + 'x' * 1000
        
        with pytest.raises(JSONParseError) as exc_info:
            self.stage1.validate(content)
        
        assert "content_snippet" in exc_info.value.details
        # Should be truncated to 500 chars
        assert len(exc_info.value.details["content_snippet"]) == 500
    
    def test_unicode_content(self):
        """Test parsing JSON with unicode characters."""
        content = '{"message": "Contratto con àccenti e émoji 🎉"}'
        result = self.stage1.validate(content)
        
        assert result["message"] == "Contratto con àccenti e émoji 🎉"
    
    def test_json_with_escaped_characters(self):
        """Test parsing JSON with escaped characters."""
        content = r'{"message": "Line with\nnewline and \"quotes\""}'
        result = self.stage1.validate(content)
        
        assert result["message"] == 'Line with\nnewline and "quotes"'
