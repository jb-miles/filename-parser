#!/usr/bin/env python3
"""
Pytest tests for tokenization functionality.
These tests verify the tokenization process that follows pre-tokenization.
"""

import pytest
from yansa import FilenameParser
from modules import Token, PreTokenizationResult


@pytest.fixture
def parser():
    """Fixture providing a FilenameParser instance."""
    return FilenameParser()


def test_tokenize_basic(parser):
    """Test basic tokenization functionality."""
    # Create a pre-tokenization result manually
    pre_result = PreTokenizationResult(
        original="Test.Scene.720p.mp4",
        cleaned="Test.Scene.",
        removed_tokens=[]
    )
    
    result = parser.tokenize(pre_result)
    json_result = result.to_json()
    
    # Verify JSON structure
    assert isinstance(json_result, str)
    
    # Parse JSON to verify content
    import json
    parsed = json.loads(json_result)
    
    # Verify the structure
    assert result.original == "Test.Scene.720p.mp4"
    assert result.pattern == "{token0}"
    
    # Verify pattern in JSON
    assert parsed["pattern"] == "{token0}"
    
    # Verify tokens
    assert len(parsed["tokens"]) == 1
    assert parsed["tokens"][0]["value"] == "Test.Scene"
    assert parsed["tokens"][0]["type"] == "text"


def test_tokenize_with_removed_tokens(parser):
    """Test tokenization with removed tokens."""
    # Use actual pre-tokenization
    pre_result = parser.pre_tokenize("Scene.720p.HQ.mp4")
    result = parser.tokenize(pre_result)
    json_result = result.to_json()
    
    # Verify structure
    assert result.original == "Scene.720p.HQ.mp4"
    assert result.pattern == "{token0}"  # Pattern placeholder
    
    # Parse JSON to verify content
    import json
    parsed = json.loads(json_result)
    
    # Verify pattern in JSON
    assert parsed["pattern"] == "{token0}"
    
    # Verify token content
    assert len(parsed["tokens"]) == 1
    assert parsed["tokens"][0]["value"] == "Scene"
    assert parsed["tokens"][0]["type"] == "text"


def test_extract_tokens_words(parser):
    """Test token extraction for words."""
    tokens = parser.tokenizer._extract_tokens("HelloWorld")
    
    assert len(tokens) == 1
    assert tokens[0].value == "HelloWorld"
    assert tokens[0].type == "text"
    assert tokens[0].position == 0
    assert len(tokens[0].value) == 10


def test_extract_tokens_separators(parser):
    """Test token extraction for separators."""
    tokens = parser.tokenizer._extract_tokens("Test.Scene")
    
    assert len(tokens) == 1
    assert tokens[0].value == "Test.Scene"
    assert tokens[0].type == "text"


def test_extract_tokens_numbers(parser):
    """Test token extraction for numbers."""
    tokens = parser.tokenizer._extract_tokens("Test123Scene")
    
    assert len(tokens) == 1
    assert tokens[0].value == "Test123Scene"
    assert tokens[0].type == "text"


def test_extract_tokens_mixed(parser):
    """Test token extraction for mixed content."""
    tokens = parser.tokenizer._extract_tokens("Test.Scene-123_456")
    
    assert len(tokens) == 1
    assert tokens[0].value == "Test.Scene-123_456"
    assert tokens[0].type == "text"


def test_tokenize_empty_string(parser):
    """Test tokenization with empty cleaned string."""
    pre_result = PreTokenizationResult(
        original="Test.mp4",
        cleaned="",
        removed_tokens=[]
    )
    
    result = parser.tokenize(pre_result)
    json_result = result.to_json()
    
    # Should have original and empty pattern
    assert result.original == "Test.mp4"
    assert result.pattern == ""
    
    # Parse JSON to verify content
    import json
    parsed = json.loads(json_result)
    assert parsed["pattern"] == ""
    assert len(parsed["tokens"]) == 0


def test_tokenize_full_workflow(parser):
    """Test the full workflow from filename to tokenization."""
    filename = "Scene.720p.HQ.mp4"
    
    # Pre-tokenize
    pre_result = parser.pre_tokenize(filename)
    
    # Tokenize
    token_result = parser.tokenize(pre_result)
    
    # Verify the full workflow
    assert token_result.original == filename  # original
    
    # Verify pattern
    assert token_result.pattern == "{token0}"  # Pattern placeholder
    
    # Verify tokens were created
    assert len(token_result.tokens) > 0
    assert any(token.type == "text" for token in token_result.tokens)


@pytest.mark.parametrize("filename,expected_patterns", [
    ("Scene.720p.mp4", ["{token0}"]),  # Basic case
    ("Test.Scene.1080p.HD.avi", ["{token0}"]),  # Multiple separators
    ("Movie.mkv", ["{token0}"]),  # Simple case
])
def test_tokenize_pattern_extraction(parser, filename, expected_patterns):
    """Test that patterns are correctly extracted from various filenames."""
    pre_result = parser.pre_tokenize(filename)
    token_result = parser.tokenize(pre_result)
    
    # Pattern should match expected
    assert token_result.pattern in expected_patterns


def test_tokenizer_json_output(parser):
    """Test that tokenizer outputs JSON format with pattern first."""
    pre_result = parser.pre_tokenize("Test.Scene.720p.mp4")
    token_result = parser.tokenize(pre_result)
    json_output = token_result.to_json()
    
    # Parse the JSON to verify structure
    import json
    parsed = json.loads(json_output)
    
    # Verify JSON structure
    assert "pattern" in parsed
    assert "tokens" in parsed
    assert parsed["pattern"] == "{token0}"
    
    # Verify token structure
    assert len(parsed["tokens"]) > 0
    for token in parsed["tokens"]:
        assert "value" in token
        assert "position" in token
        assert "type" in token


def test_path_parser_isolates_basename(parser):
    """Path segments should not bleed into basename tokenization."""
    filename = "parent/child/My Scene 1080p.mp4"

    pre_result = parser.pre_tokenize(filename)
    assert '/' not in pre_result.cleaned
    assert 'My Scene' in pre_result.cleaned

    final_result = parser.parse(filename)
    path_token = next((t for t in final_result.tokens or [] if t.type == 'path'), None)
    assert path_token is None
    assert final_result.cleaned == pre_result.cleaned
    assert final_result.group is None
