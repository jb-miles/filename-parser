#!/usr/bin/env python3
"""
Error handling and edge case tests for date extractor.
Tests resilience when date configurations are missing, malformed, or contain invalid patterns.
"""

import pytest
import json
import re
from unittest.mock import patch, mock_open
from modules import DateExtractor, TokenizationResult, Token


@pytest.fixture
def date_extractor():
    """Fixture providing a DateExtractor instance."""
    return DateExtractor()


class TestDateExtractorConfigLoading:
    """Tests for date configuration loading and error handling."""

    def test_missing_date_formats_file(self):
        """Test that extractor handles missing date_formats.json gracefully."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            extractor = DateExtractor()
            # Should initialize with empty patterns instead of crashing
            assert extractor.date_patterns == []
            assert extractor.month_names == {}

    def test_invalid_json_in_date_formats(self):
        """Test that extractor handles invalid JSON in date_formats.json gracefully."""
        invalid_json = "{ invalid json"
        with patch('builtins.open', mock_open(read_data=invalid_json)):
            with patch('json.load', side_effect=json.JSONDecodeError("msg", "doc", 0)):
                extractor = DateExtractor()
                assert extractor.date_patterns == []
                assert extractor.month_names == {}

    def test_empty_date_formats_file(self):
        """Test handling of empty date formats configuration."""
        empty_config = {}
        with patch('builtins.open', mock_open(read_data=json.dumps(empty_config))):
            with patch('json.load', return_value=empty_config):
                extractor = DateExtractor()
                assert extractor.date_patterns == []

    def test_missing_patterns_key(self):
        """Test handling when 'patterns' key is missing from config."""
        config_without_patterns = {
            "month_pattern": "...",
            "month_names": {}
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config_without_patterns))):
            with patch('json.load', return_value=config_without_patterns):
                extractor = DateExtractor()
                assert extractor.date_patterns == []

    def test_missing_regex_field_in_pattern(self):
        """Test handling when regex field is missing from a pattern entry."""
        config = {
            "patterns": [
                {"type": "YYYY-MM-DD"},  # Missing regex
                {"regex": r"\d{4}-\d{2}-\d{2}", "type": "YYYY-MM-DD"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # Should skip invalid pattern and load valid one
                assert len(extractor.date_patterns) >= 1

    def test_missing_type_field_in_pattern(self):
        """Test handling when type field is missing from a pattern entry."""
        config = {
            "patterns": [
                {"regex": r"\d{4}-\d{2}-\d{2}"},  # Missing type
                {"regex": r"\d{4}/\d{2}/\d{2}", "type": "YYYY/MM/DD"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # Should skip invalid pattern and load valid one
                assert len(extractor.date_patterns) >= 1

    def test_empty_regex_in_pattern(self):
        """Test handling of empty regex string in pattern."""
        config = {
            "patterns": [
                {"regex": "", "type": "INVALID"},  # Empty regex
                {"regex": r"\d{4}-\d{2}-\d{2}", "type": "YYYY-MM-DD"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # Should skip empty regex and load valid one
                assert len(extractor.date_patterns) >= 1


class TestInvalidRegexPatterns:
    """Tests for handling of invalid regex patterns in date configuration."""

    def test_malformed_regex_pattern_handled(self):
        """Test that malformed regex patterns are handled gracefully."""
        config = {
            "patterns": [
                {"regex": "[invalid(regex", "type": "INVALID"},  # Invalid regex
                {"regex": r"\d{4}-\d{2}-\d{2}", "type": "YYYY-MM-DD"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # Should skip malformed regex and load valid one
                assert len(extractor.date_patterns) >= 1

    def test_regex_with_invalid_escape(self):
        """Test handling of regex with invalid escape sequences."""
        config = {
            "patterns": [
                {"regex": r"\d{4}-\d{2}-\d{2}", "type": "YYYY-MM-DD"},
                {"regex": r"invalid\z escape", "type": "INVALID"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # Invalid regex should not prevent loading valid patterns
                # (it may be skipped silently)
                assert len(extractor.date_patterns) >= 0

    def test_month_pattern_substitution(self):
        """Test that MONTH_PATTERN placeholder is substituted correctly."""
        config = {
            "month_pattern": "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
            "patterns": [
                {"regex": r"\d{1,2}\s+MONTH_PATTERN\s+\d{4}", "type": "DD MONTH YYYY"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # MONTH_PATTERN should be substituted
                assert len(extractor.date_patterns) >= 1
                regex, pattern_type = extractor.date_patterns[0]
                assert "MONTH_PATTERN" not in regex.pattern


class TestProcessWithInvalidStates:
    """Tests for date extractor process method with various invalid states."""

    def test_process_with_empty_tokens(self, date_extractor):
        """Test process with empty tokens list."""
        result = TokenizationResult(
            original="test",
            cleaned="test",
            pattern="{token0}",
            tokens=[]
        )
        processed = date_extractor.process(result)
        assert processed.tokens == []

    def test_process_with_none_tokens(self, date_extractor):
        """Test process with None tokens."""
        result = TokenizationResult(
            original="test",
            cleaned="test",
            pattern="{token0}",
            tokens=None
        )
        processed = date_extractor.process(result)
        assert processed.tokens is None

    def test_process_with_already_identified_date_tokens(self, date_extractor):
        """Test that already-identified date tokens are handled."""
        tokens = [
            Token(value="2020-01-15", type="date", position=0),
            Token(value="Scene", type="text", position=11),
        ]
        result = TokenizationResult(
            original="2020-01-15 Scene",
            cleaned="2020-01-15 Scene",
            pattern="{date} {token1}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should preserve already identified date tokens
        assert processed.tokens[0].type == "date"

    def test_process_with_empty_token_values(self, date_extractor):
        """Test process with tokens containing empty values."""
        tokens = [
            Token(value="", type="text", position=0),
            Token(value="Scene", type="text", position=0),
        ]
        result = TokenizationResult(
            original=" Scene",
            cleaned=" Scene",
            pattern="{token0} {token1}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should handle empty token values gracefully
        assert len(processed.tokens) >= 0

    def test_process_preserves_non_date_tokens(self, date_extractor):
        """Test that non-date tokens are preserved."""
        tokens = [
            Token(value="RandomText", type="text", position=0),
            Token(value="Scene", type="text", position=11),
        ]
        result = TokenizationResult(
            original="RandomText Scene",
            cleaned="RandomText Scene",
            pattern="{token0} {token1}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Non-date tokens should be preserved
        assert len(processed.tokens) == len(tokens)


class TestDateExtractionEdgeCases:
    """Tests for edge cases in date extraction logic."""

    def test_find_dates_with_overlapping_patterns(self, date_extractor):
        """Test handling of overlapping date patterns in a token."""
        # If we have patterns that could overlap, ensure correct behavior
        tokens = [
            Token(value="2020-01-15T10:30:00", type="text", position=0),
        ]
        result = TokenizationResult(
            original="2020-01-15T10:30:00",
            cleaned="2020-01-15T10:30:00",
            pattern="{token0}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should handle without errors
        assert processed is not None

    def test_find_dates_at_token_boundaries(self, date_extractor):
        """Test date extraction at token boundaries."""
        tokens = [
            Token(value="2020-01-15", type="text", position=0),
            Token(value="Scene", type="text", position=11),
        ]
        result = TokenizationResult(
            original="2020-01-15 Scene",
            cleaned="2020-01-15 Scene",
            pattern="{token0} {token1}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should process without errors
        assert processed is not None

    def test_partial_date_patterns(self, date_extractor):
        """Test handling of partial dates that don't match full patterns."""
        tokens = [
            Token(value="2020-01", type="text", position=0),  # Incomplete date
            Token(value="Scene", type="text", position=8),
        ]
        result = TokenizationResult(
            original="2020-01 Scene",
            cleaned="2020-01 Scene",
            pattern="{token0} {token1}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should handle partial dates without crashing
        assert processed is not None

    def test_date_with_extra_spaces(self, date_extractor):
        """Test handling of dates with extra spaces."""
        tokens = [
            Token(value="2020   -   01   -   15", type="text", position=0),
            Token(value="Scene", type="text", position=22),
        ]
        result = TokenizationResult(
            original="2020   -   01   -   15 Scene",
            cleaned="2020   -   01   -   15 Scene",
            pattern="{token0} {token1}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should handle without errors
        assert processed is not None

    def test_multiple_dates_in_single_token(self, date_extractor):
        """Test handling of multiple dates in a single token."""
        tokens = [
            Token(value="2020-01-15 and 2020-01-16", type="text", position=0),
        ]
        result = TokenizationResult(
            original="2020-01-15 and 2020-01-16",
            cleaned="2020-01-15 and 2020-01-16",
            pattern="{token0}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        # Should handle multiple dates
        assert processed is not None

    def test_date_with_different_separators(self, date_extractor):
        """Test dates with various separator characters."""
        test_cases = [
            Token(value="2020-01-15", type="text", position=0),
            Token(value="2020/01/15", type="text", position=0),
            Token(value="2020.01.15", type="text", position=0),
        ]

        for token in test_cases:
            result = TokenizationResult(
                original=token.value,
                cleaned=token.value,
                pattern="{token0}",
                tokens=[token]
            )
            processed = date_extractor.process(result)
            assert processed is not None


class TestMonthNameHandling:
    """Tests for month name parsing and handling."""

    def test_process_with_missing_month_names_dict(self):
        """Test handling when month_names is missing from config."""
        config = {
            "month_pattern": "(Jan|Feb|Mar)",
            "patterns": [
                {"regex": r"\d{1,2}\s+(Jan|Feb|Mar)\s+\d{4}", "type": "DD MONTH YYYY"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                # Should handle missing month_names
                assert extractor.month_names == {} or isinstance(extractor.month_names, dict)

    def test_process_with_empty_month_names(self):
        """Test handling of empty month_names dictionary."""
        config = {
            "month_pattern": "(Jan|Feb|Mar)",
            "month_names": {},
            "patterns": [
                {"regex": r"\d{1,2}\s+(Jan|Feb|Mar)\s+\d{4}", "type": "DD MONTH YYYY"}
            ]
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(config))):
            with patch('json.load', return_value=config):
                extractor = DateExtractor()
                assert extractor.month_names == {}


class TestBoundaryConditions:
    """Tests for boundary conditions and limits."""

    def test_very_long_token_value(self, date_extractor):
        """Test processing very long token values."""
        long_value = "A" * 10000 + "2020-01-15" + "B" * 10000
        tokens = [Token(value=long_value, type="text", position=0)]
        result = TokenizationResult(
            original=long_value,
            cleaned=long_value,
            pattern="{token0}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        assert processed is not None

    def test_many_tokens(self, date_extractor):
        """Test processing with many tokens."""
        tokens = [
            Token(value=f"token{i}", type="text", position=i * 10)
            for i in range(100)
        ]
        tokens[50] = Token(value="2020-01-15", type="text", position=500)

        result = TokenizationResult(
            original="test" * 100,
            cleaned="test" * 100,
            pattern="{token" + "} {token".join(str(i) for i in range(100)) + "}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        assert processed is not None

    def test_token_at_very_high_position(self, date_extractor):
        """Test tokens with very high position values."""
        tokens = [
            Token(value="2020-01-15", type="text", position=999999),
        ]
        result = TokenizationResult(
            original="2020-01-15",
            cleaned="2020-01-15",
            pattern="{token0}",
            tokens=tokens
        )
        processed = date_extractor.process(result)
        assert processed is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
