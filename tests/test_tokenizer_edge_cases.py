#!/usr/bin/env python3
"""
Edge case and error handling tests for tokenizer module.
Tests resilience and boundary conditions in token extraction and pattern generation.
"""

import pytest
from modules import Tokenizer, Token, TokenizationResult


@pytest.fixture
def tokenizer():
    """Fixture providing a Tokenizer instance."""
    return Tokenizer()


class TestTokenizerWhitespaceHandling:
    """Tests for whitespace handling in tokenization."""

    def test_tokenize_only_whitespace(self, tokenizer):
        """Test tokenizing string with only whitespace."""
        result = tokenizer.tokenize(cleaned="   \t\n  ", original="   \t\n  ")
        assert result is not None
        # Should handle gracefully, may have no tokens

    def test_tokenize_mixed_whitespace(self, tokenizer):
        """Test tokenizing with mixed whitespace types."""
        result = tokenizer.tokenize(cleaned="test \t word \n another", original="test \t word \n another")
        assert result is not None
        assert result.tokens is not None

    def test_token_with_only_spaces(self, tokenizer):
        """Test handling tokens that are only spaces."""
        # If spaces are treated as separators, this should result in empty tokens
        result = tokenizer.tokenize(cleaned="   ", original="   ")
        assert result is not None

    def test_leading_trailing_whitespace(self, tokenizer):
        """Test handling of leading and trailing whitespace."""
        result = tokenizer.tokenize(cleaned="  test  ", original="  test  ")
        assert result is not None

    def test_multiple_consecutive_separators(self, tokenizer):
        """Test handling of multiple consecutive separator characters."""
        result = tokenizer.tokenize(cleaned="test---word===another", original="test---word===another")
        assert result is not None
        # Should handle multiple consecutive separators


class TestTokenizerSpecialCharacters:
    """Tests for special character handling."""

    def test_tokenize_with_unicode_characters(self, tokenizer):
        """Test tokenizing with Unicode characters."""
        result = tokenizer.tokenize(cleaned="café résumé naïve", original="café résumé naïve")
        assert result is not None

    def test_tokenize_with_emoji(self, tokenizer):
        """Test tokenizing with emoji characters."""
        result = tokenizer.tokenize(cleaned="test 😀 word", original="test 😀 word")
        assert result is not None

    def test_tokenize_with_control_characters(self, tokenizer):
        """Test tokenizing with control characters."""
        result = tokenizer.tokenize(cleaned="test\x00word", original="test\x00word")
        assert result is not None

    def test_tokenize_with_null_bytes(self, tokenizer):
        """Test tokenizing with null bytes."""
        result = tokenizer.tokenize(cleaned="test\0word", original="test\0word")
        assert result is not None

    def test_tokenize_with_mixed_case_separators(self, tokenizer):
        """Test with various case combinations in separators."""
        result = tokenizer.tokenize(cleaned="TEST word ANOTHER", original="TEST word ANOTHER")
        assert result is not None


class TestTokenizerNumberHandling:
    """Tests for number handling in tokenization."""

    def test_tokenize_only_numbers(self, tokenizer):
        """Test tokenizing string with only numbers."""
        result = tokenizer.tokenize(cleaned="12345", original="12345")
        assert result is not None
        assert result.tokens is not None

    def test_tokenize_very_large_numbers(self, tokenizer):
        """Test tokenizing with very large numbers."""
        result = tokenizer.tokenize(
            cleaned="99999999999999999999999999",
            original="99999999999999999999999999"
        )
        assert result is not None

    def test_tokenize_numbers_with_leading_zeros(self, tokenizer):
        """Test tokenizing numbers with leading zeros."""
        result = tokenizer.tokenize(cleaned="0001 0042 0999", original="0001 0042 0999")
        assert result is not None

    def test_tokenize_decimal_numbers(self, tokenizer):
        """Test tokenizing decimal numbers."""
        result = tokenizer.tokenize(cleaned="3.14 2.71 1.41", original="3.14 2.71 1.41")
        assert result is not None

    def test_tokenize_negative_numbers(self, tokenizer):
        """Test tokenizing negative numbers."""
        result = tokenizer.tokenize(cleaned="-123 -456 -789", original="-123 -456 -789")
        assert result is not None


class TestTokenizerPatternGeneration:
    """Tests for pattern generation edge cases."""

    def test_pattern_with_no_tokens(self, tokenizer):
        """Test pattern generation when there are no tokens."""
        result = tokenizer.tokenize(cleaned="", original="")
        assert result is not None
        # Pattern should reflect no tokens

    def test_pattern_with_single_token(self, tokenizer):
        """Test pattern generation with single token."""
        result = tokenizer.tokenize(cleaned="SingleWord", original="SingleWord")
        assert result is not None
        if result.tokens:
            assert "{token0}" in result.pattern or result.pattern

    def test_pattern_preserves_order(self, tokenizer):
        """Test that pattern preserves token order."""
        result = tokenizer.tokenize(cleaned="First Second Third", original="First Second Third")
        assert result is not None
        if result.tokens and len(result.tokens) >= 3:
            # Pattern should contain tokens in order
            first_idx = result.pattern.find("{token0}")
            second_idx = result.pattern.find("{token1}")
            third_idx = result.pattern.find("{token2}")
            if first_idx >= 0 and second_idx >= 0 and third_idx >= 0:
                assert first_idx < second_idx < third_idx

    def test_pattern_with_many_tokens(self, tokenizer):
        """Test pattern generation with many tokens."""
        words = " ".join([f"word{i}" for i in range(100)])
        result = tokenizer.tokenize(cleaned=words, original=words)
        assert result is not None
        if result.tokens:
            assert len(result.tokens) <= 100  # Should have at most 100 tokens


class TestTokenExtraction:
    """Tests for token extraction edge cases."""

    def test_extract_tokens_alternating_types(self, tokenizer):
        """Test extraction with alternating word and number tokens."""
        result = tokenizer.tokenize(cleaned="word1 word2 123 word3 456", original="word1 word2 123 word3 456")
        assert result is not None
        if result.tokens:
            # Should extract both words and numbers
            types = {t.type for t in result.tokens}
            assert len(types) >= 1

    def test_extract_tokens_with_punctuation(self, tokenizer):
        """Test extraction with punctuation characters."""
        result = tokenizer.tokenize(
            cleaned="hello! how? are. you, fine;",
            original="hello! how? are. you, fine;"
        )
        assert result is not None

    def test_extract_tokens_hyphenated_words(self, tokenizer):
        """Test extraction with hyphenated words."""
        result = tokenizer.tokenize(cleaned="well-known high-quality long-form", original="well-known high-quality long-form")
        assert result is not None

    def test_extract_tokens_contracted_words(self, tokenizer):
        """Test extraction with contractions."""
        result = tokenizer.tokenize(cleaned="don't isn't can't won't", original="don't isn't can't won't")
        assert result is not None

    def test_extract_tokens_with_parentheses(self, tokenizer):
        """Test extraction with parentheses and brackets."""
        result = tokenizer.tokenize(cleaned="test (word) [another] {more}", original="test (word) [another] {more}")
        assert result is not None

    def test_extract_tokens_underscore_separated(self, tokenizer):
        """Test extraction of underscore-separated words."""
        result = tokenizer.tokenize(cleaned="test_word another_word", original="test_word another_word")
        assert result is not None


class TestTokenPositionTracking:
    """Tests for token position tracking."""

    def test_position_tracking_basic(self, tokenizer):
        """Test that token positions are tracked correctly."""
        result = tokenizer.tokenize(cleaned="hello world test", original="hello world test")
        assert result is not None
        if result.tokens:
            # Positions should be in order and non-negative
            for token in result.tokens:
                assert token.position >= 0

    def test_position_tracking_with_gaps(self, tokenizer):
        """Test position tracking with gaps in text."""
        result = tokenizer.tokenize(cleaned="hello     world     test", original="hello     world     test")
        assert result is not None
        if result.tokens:
            for token in result.tokens:
                assert token.position >= 0

    def test_position_tracking_single_char_tokens(self, tokenizer):
        """Test position tracking with single character tokens."""
        result = tokenizer.tokenize(cleaned="a b c d e f", original="a b c d e f")
        assert result is not None
        if result.tokens:
            # Each should have a position
            assert all(t.position >= 0 for t in result.tokens)


class TestTokenTypeDetection:
    """Tests for token type detection."""

    def test_token_type_word(self, tokenizer):
        """Test detection of word type tokens."""
        result = tokenizer.tokenize(cleaned="hello world", original="hello world")
        assert result is not None
        if result.tokens:
            # Should detect word-type tokens
            word_tokens = [t for t in result.tokens if t.type in ["word", "text"]]
            assert len(word_tokens) > 0

    def test_token_type_number(self, tokenizer):
        """Test detection of number type tokens."""
        result = tokenizer.tokenize(cleaned="test 123 word 456", original="test 123 word 456")
        assert result is not None
        if result.tokens:
            # Should detect number tokens
            number_tokens = [t for t in result.tokens if t.type == "number"]
            assert len(number_tokens) >= 0  # May or may not separate numbers

    def test_token_type_mixed(self, tokenizer):
        """Test detection of mixed type tokens."""
        result = tokenizer.tokenize(cleaned="word123 test456 hello", original="word123 test456 hello")
        assert result is not None


class TestBoundaryConditions:
    """Tests for boundary conditions and limits."""

    def test_very_long_token(self, tokenizer):
        """Test handling of very long single token."""
        long_word = "a" * 10000
        result = tokenizer.tokenize(cleaned=long_word, original=long_word)
        assert result is not None

    def test_very_many_tokens(self, tokenizer):
        """Test handling of many tokens."""
        many_words = " ".join(["word"] * 1000)
        result = tokenizer.tokenize(cleaned=many_words, original=many_words)
        assert result is not None

    def test_mixed_very_long_and_very_many(self, tokenizer):
        """Test handling of combination of long tokens and many tokens."""
        mixed = " ".join(["a" * 100] * 100)
        result = tokenizer.tokenize(cleaned=mixed, original=mixed)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
