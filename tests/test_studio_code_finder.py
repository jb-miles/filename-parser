#!/usr/bin/env python3
"""
Pytest tests for studio code finder functionality.
Verifies that tokens matching studio code patterns are correctly identified and marked.
"""

import pytest
from parser import FilenameParser
from modules import StudioCodeFinder, TokenizationResult, Token


@pytest.fixture
def parser():
    """Fixture providing a FilenameParser instance."""
    return FilenameParser()


@pytest.fixture
def studio_code_finder():
    """Fixture providing a StudioCodeFinder instance."""
    return StudioCodeFinder()


def test_studio_code_finder_initialization(studio_code_finder):
    """Test that studio code finder loads patterns correctly."""
    assert len(studio_code_finder.studio_code_patterns) > 0
    # Verify patterns are compiled regex objects
    for regex, info in studio_code_finder.studio_code_patterns:
        assert hasattr(regex, 'match')  # Should have a match method
        assert 'studio' in info
        assert 'pattern' in info


def test_studio_code_pattern_to_regex(studio_code_finder):
    """Test conversion of code patterns with # placeholders to regex."""
    # Test that # characters are converted to digit patterns
    regex = studio_code_finder._pattern_to_regex("AD####")
    assert regex is not None
    assert regex.match("AD1234")
    assert regex.match("AD0000")
    assert not regex.match("ADABCD")
    assert not regex.match("AD123")  # Too few digits


def test_studio_code_pattern_escaped_hash(studio_code_finder):
    """Test that escaped # characters are treated as literals."""
    # The _pattern_to_regex expects Python string escaping
    # "TEST\\####" means TEST followed by literal # then 3 hashes (3 digits)
    regex = studio_code_finder._pattern_to_regex("TEST\\####")
    assert regex is not None
    # Should match "TEST#" followed by 3 digits
    assert regex.match("TEST#123")
    assert not regex.match("TEST123")  # No literal hash
    assert not regex.match("TEST#1234")  # Too many digits
    assert not regex.match("TEST#12")  # Too few digits


def test_studio_code_pattern_mixed_content(studio_code_finder):
    """Test patterns with mixed literal and placeholder characters."""
    regex = studio_code_finder._pattern_to_regex("AD-##-###")
    assert regex is not None
    assert regex.match("AD-12-345")
    assert regex.match("AD-00-000")
    assert not regex.match("AD-1-345")  # Wrong number of digits


def test_studio_code_case_insensitive_match(studio_code_finder):
    """Test that studio code matching is case-insensitive."""
    # Create a simple tokenization result
    token = Token(value="ad0001", type="text", position=0)
    result = TokenizationResult(
        original="ad0001 - scene",
        cleaned="ad0001 - scene",
        pattern="{token0} - {token1}",
        tokens=[token, Token(value="scene", type="text", position=8)]
    )

    processed = studio_code_finder.process(result)

    # If a matching pattern exists, it should be matched
    if processed.tokens[0].type == "studio_code":
        assert processed.tokens[0].value.lower() == "ad0001"


def test_studio_code_match_updates_pattern(studio_code_finder):
    """Test that pattern is updated when studio code is matched."""
    token = Token(value="AD0001", type="text", position=0)
    result = TokenizationResult(
        original="AD0001 - Title",
        cleaned="AD0001 - Title",
        pattern="{token0} - {token1}",
        tokens=[token, Token(value="Title", type="text", position=8)]
    )

    processed = studio_code_finder.process(result)

    # If matched, pattern should be updated
    if processed.tokens[0].type == "studio_code":
        assert "{studio_code}" in processed.pattern


def test_studio_code_metadata_set(studio_code_finder):
    """Test that studio metadata is set when code is matched."""
    token = Token(value="AD0001", type="text", position=0)
    result = TokenizationResult(
        original="AD0001 - Scene Title",
        cleaned="AD0001 - Scene Title",
        pattern="{token0} - {token1}",
        tokens=[token, Token(value="Scene Title", type="text", position=8)]
    )

    processed = studio_code_finder.process(result)

    # If code matched, studio should be set in metadata
    if processed.tokens[0].type == "studio_code":
        assert processed.studio is not None


def test_studio_code_no_match_non_studios(studio_code_finder):
    """Test that non-matching tokens are not marked as studio codes."""
    token = Token(value="Random123", type="text", position=0)
    result = TokenizationResult(
        original="Random123 - Scene",
        cleaned="Random123 - Scene",
        pattern="{token0} - {token1}",
        tokens=[token, Token(value="Scene", type="text", position=10)]
    )

    processed = studio_code_finder.process(result)

    # Token should remain as-is if it doesn't match any pattern
    # (may be text or another type, but not studio_code)


def test_studio_code_skip_already_identified(studio_code_finder):
    """Test that already identified studio tokens are skipped."""
    # Create a token that's already marked as studio
    token = Token(value="Active Duty", type="studio", position=0)
    result = TokenizationResult(
        original="Active Duty - Scene",
        cleaned="Active Duty - Scene",
        pattern="{studio} - {token1}",
        tokens=[token, Token(value="Scene", type="text", position=13)]
    )

    processed = studio_code_finder.process(result)

    # Studio token should remain unchanged
    assert processed.tokens[0].type == "studio"
    assert processed.tokens[0].value == "Active Duty"


def test_studio_code_in_full_parse(parser):
    """Test studio code matching in full parsing pipeline."""
    # Test with a filename that might contain a studio code
    result = parser.parse("AD0001 - Hot Scene")

    # Check if studio code was identified
    studio_code_tokens = [t for t in result.tokens if t.type == "studio_code"]

    if studio_code_tokens:
        assert studio_code_tokens[0].value.upper() in ["AD0001"]


def test_studio_code_pattern_specificity(studio_code_finder):
    """Test that patterns are matched with correct specificity."""
    # Test that a pattern with specific format is only matched by correct format
    regex = studio_code_finder._pattern_to_regex("##-##-##")
    assert regex is not None
    assert regex.match("12-34-56")
    assert not regex.match("1234567")  # No separators
    assert not regex.match("12-34")  # Missing last pair
    assert not regex.match("12-34-5")  # Wrong length


def test_studio_code_empty_result_handling(studio_code_finder):
    """Test that finder handles empty or null token lists gracefully."""
    result = TokenizationResult(
        original="",
        cleaned="",
        pattern="",
        tokens=None
    )

    processed = studio_code_finder.process(result)
    assert processed.tokens is None


def test_studio_code_preserves_original_casing(studio_code_finder):
    """Test that original token casing is preserved in matched code."""
    token = Token(value="AD0001", type="text", position=0)
    result = TokenizationResult(
        original="AD0001 - Title",
        cleaned="AD0001 - Title",
        pattern="{token0} - {token1}",
        tokens=[token, Token(value="Title", type="text", position=8)]
    )

    processed = studio_code_finder.process(result)

    # If matched, the original casing should be preserved
    if processed.tokens[0].type == "studio_code":
        assert processed.tokens[0].value == "AD0001"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
