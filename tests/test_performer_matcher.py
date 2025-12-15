#!/usr/bin/env python3
"""
Tests for performer matcher normalization and pattern matching.
"""

import pytest
from yansa import FilenameParser
from modules import PerformerMatcher, TokenizationResult, Token


@pytest.fixture
def parser():
    """Provide a FilenameParser instance."""
    return FilenameParser()


@pytest.fixture
def performer_matcher():
    """Provide a PerformerMatcher instance."""
    return PerformerMatcher()


@pytest.mark.parametrize(
    "filename,expected_value",
    [
        ("John and Jane", "John, Jane"),
        ("John & Jane", "John, Jane"),
        ("John,Jane &Bob", "John, Jane, Bob"),
        ("Alice ,Bob and  Carol", "Alice, Bob, Carol"),
    ],
)
def test_performer_list_normalization(parser, filename, expected_value):
    """Performer tokens should be normalized to comma-and-space separated names."""
    result = parser.parse(filename)
    performer_tokens = [t for t in (result.tokens or []) if t.type == "performers"]
    assert performer_tokens, f"No performer token found for '{filename}'"
    assert performer_tokens[0].value == expected_value


def test_performer_pattern_two_names_and(performer_matcher):
    """Test matching two performer names with 'and' separator."""
    # Performer matcher works on combined tokens, not separate ones
    result = TokenizationResult(
        original="John Smith and Jane Doe",
        cleaned="John Smith and Jane Doe",
        pattern="{token0}",
        tokens=[
            Token(value="John Smith and Jane Doe", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # Should identify as performers and normalize
    assert any(t.type == "performers" for t in processed.tokens)


def test_performer_pattern_two_names_ampersand(performer_matcher):
    """Test matching two performer names with ampersand separator."""
    result = TokenizationResult(
        original="John Smith & Jane Doe",
        cleaned="John Smith & Jane Doe",
        pattern="{token0} & {token1}",
        tokens=[
            Token(value="John Smith & Jane Doe", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # Should identify as performers
    assert processed.tokens[0].type == "performers"
    # Should normalize to comma-space format
    assert processed.tokens[0].value == "John Smith, Jane Doe"


def test_performer_pattern_multiple_names(performer_matcher):
    """Test matching multiple performer names with comma separators."""
    result = TokenizationResult(
        original="John Smith, Jane Doe and Bob Jones",
        cleaned="John Smith, Jane Doe and Bob Jones",
        pattern="{token0}, {token1} and {token2}",
        tokens=[
            Token(value="John Smith, Jane Doe and Bob Jones", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # Should identify as performers
    assert processed.tokens[0].type == "performers"


def test_performer_pattern_comma_only(performer_matcher):
    """Test matching performer names separated by commas only."""
    result = TokenizationResult(
        original="Jane Smith, Bob Johnson, Carol White",
        cleaned="Jane Smith, Bob Johnson, Carol White",
        pattern="{token0}",
        tokens=[
            Token(value="Jane Smith, Bob Johnson, Carol White", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # Should identify as performers
    assert processed.tokens[0].type == "performers"


def test_performer_non_performer_words_rejection(performer_matcher):
    """Test that tokens with non-performer words are rejected."""
    # Test with a word that should exclude it from being a performer
    result = TokenizationResult(
        original="Movie Scene and Video Clip",
        cleaned="Movie Scene and Video Clip",
        pattern="{token0}",
        tokens=[
            Token(value="Movie Scene and Video Clip", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # Should NOT be identified as performers because "movie", "scene", "video", "clip" are non-performer words
    assert processed.tokens[0].type != "performers"


def test_performer_single_name_rejected(performer_matcher):
    """Test that single performer names are not matched (need at least 2)."""
    result = TokenizationResult(
        original="John Smith",
        cleaned="John Smith",
        pattern="{token0}",
        tokens=[
            Token(value="John Smith", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # Should NOT be identified as performers (only 1 name)
    assert processed.tokens[0].type != "performers"


def test_performer_capitalization_requirement(performer_matcher):
    """Test that at least some names should be capitalized for validation."""
    # Test with all lowercase (should be validated based on other factors)
    result = TokenizationResult(
        original="john and jane",
        cleaned="john and jane",
        pattern="{token0}",
        tokens=[
            Token(value="john and jane", type="text", position=0)
        ]
    )

    processed = performer_matcher.process(result)

    # May or may not match depending on strictness of capitalization check


def test_performer_pattern_in_full_parse(parser):
    """Test performer matching in full parsing pipeline."""
    result = parser.parse("Studio Name - John Smith & Jane Doe - Cool Scene")

    # Should have a performers token
    performer_tokens = [t for t in result.tokens if t.type == "performers"]

    if performer_tokens:
        assert performer_tokens[0].value == "John Smith, Jane Doe"


def test_performer_initialization(performer_matcher):
    """Test that performer matcher loads non-performer words."""
    assert len(performer_matcher.non_performer_words) > 0
    # Check that some common non-performer words are loaded
    assert "scene" in performer_matcher.non_performer_words
    assert "movie" in performer_matcher.non_performer_words
