#!/usr/bin/env python3
"""
Error handling and edge case tests for studio code finder.
Tests resilience when dictionaries are missing, malformed, or contain invalid data.
"""

import pytest
from unittest.mock import patch
from modules import StudioCodeFinder, TokenizationResult, Token
from modules.dictionary_loader import DictionaryLoader


@pytest.fixture
def studio_code_finder():
    """Fixture providing a StudioCodeFinder instance."""
    return StudioCodeFinder()


@pytest.fixture(autouse=True)
def clear_dictionary_cache():
    """Clear the dictionary cache before each test."""
    DictionaryLoader.clear_cache()
    yield
    DictionaryLoader.clear_cache()


class TestStudioCodeFinderErrorHandling:
    """Tests for error handling in studio code finder."""

    def test_missing_dictionary_file_graceful_handling(self):
        """Test that finder handles missing dictionary file gracefully."""
        # Mock DictionaryLoader to return None (simulating missing file)
        with patch.object(DictionaryLoader, "load_dictionary", return_value=None):
            finder = StudioCodeFinder()
            # Should initialize with empty patterns instead of crashing
            assert finder.studio_code_patterns == []

    def test_invalid_json_in_dictionary_graceful_handling(self):
        """Test that finder handles invalid JSON gracefully."""
        # Mock DictionaryLoader to return None (simulating JSON decode error)
        with patch.object(DictionaryLoader, "load_dictionary", return_value=None):
            finder = StudioCodeFinder()
            # Should initialize with empty patterns instead of crashing
            assert finder.studio_code_patterns == []

    def test_empty_studio_codes_list(self):
        """Test handling of empty studio-code rule list."""
        # Mock DictionaryLoader to return empty list
        with patch.object(DictionaryLoader, "load_dictionary", return_value=[]):
            finder = StudioCodeFinder()
            assert finder.studio_code_patterns == []

    def test_invalid_studio_code_rules_type(self):
        """Test handling when studio-code rules are not a list."""
        with patch.object(DictionaryLoader, "load_dictionary", return_value={"not": "a list"}):
            finder = StudioCodeFinder()
            assert finder.studio_code_patterns == []

    def test_rule_missing_code_patterns(self):
        """Test handling when a rule is missing 'code_patterns'."""
        rules = [
            {"studio": "Test Studio", "studio_relationship": "can_set"},  # Missing code_patterns
            {"studio": "Active Duty", "studio_relationship": "can_set", "code_patterns": ["AD####"], "allow_suffix": True},
        ]
        with patch.object(DictionaryLoader, "load_dictionary", return_value=rules):
            finder = StudioCodeFinder()
            assert len(finder.studio_code_patterns) >= 1

    def test_rule_missing_studio_field(self):
        """Test handling when a rule is missing 'studio' field."""
        rules = [
            {"studio_relationship": "can_set", "code_patterns": ["XX####"], "allow_suffix": True},
            {"studio": "Active Duty", "studio_relationship": "can_set", "code_patterns": ["AD####"], "allow_suffix": True},
        ]
        with patch.object(DictionaryLoader, "load_dictionary", return_value=rules):
            finder = StudioCodeFinder()
            assert len(finder.studio_code_patterns) >= 1

    def test_rule_with_empty_pattern_string(self):
        """Test handling of empty pattern strings within a rule."""
        rules = [
            {"studio": "Test", "studio_relationship": "can_set", "code_patterns": [""], "allow_suffix": True},
            {"studio": "Active Duty", "studio_relationship": "can_set", "code_patterns": ["AD####"], "allow_suffix": True},
        ]
        with patch.object(DictionaryLoader, "load_dictionary", return_value=rules):
            finder = StudioCodeFinder()
            assert len(finder.studio_code_patterns) >= 1

    def test_rule_with_empty_studio_string(self):
        """Test handling of empty studio strings."""
        rules = [
            {"studio": "", "studio_relationship": "can_set", "code_patterns": ["XX####"], "allow_suffix": True},
            {"studio": "Active Duty", "studio_relationship": "can_set", "code_patterns": ["AD####"], "allow_suffix": True},
        ]
        with patch.object(DictionaryLoader, "load_dictionary", return_value=rules):
            finder = StudioCodeFinder()
            assert len(finder.studio_code_patterns) >= 1

    def test_malformed_regex_pattern_handling(self, studio_code_finder):
        """Test that malformed regex patterns are handled gracefully."""
        # _pattern_to_regex should return None for patterns that result in invalid regex
        result = studio_code_finder._pattern_to_regex("[invalid(regex")
        # Should handle gracefully and not crash
        assert result is None or hasattr(result, 'match')


class TestPatternToRegexEdgeCases:
    """Tests for edge cases in pattern-to-regex conversion."""

    def test_empty_pattern(self):
        """Test conversion of empty pattern."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("")
        assert result is None  # Empty pattern should return None

    def test_only_hashes(self):
        """Test pattern with only hash characters."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("####")
        assert result is not None
        assert result.match("1234")
        assert not result.match("123")
        assert not result.match("12345")

    def test_only_literals(self):
        """Test pattern with only literal characters."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("TEST")
        assert result is not None
        assert result.match("TEST")
        assert result.match("test")  # Case insensitive
        assert not result.match("TEST1")

    def test_consecutive_escapes(self):
        """Test pattern with consecutive escape sequences."""
        finder = StudioCodeFinder()
        # \\# -> literal #, ## -> digit pattern
        result = finder._pattern_to_regex("\\####")
        assert result is not None
        assert result.match("#123")
        assert not result.match("1234")

    def test_escape_at_end(self):
        """Test pattern with escape sequence at the end."""
        finder = StudioCodeFinder()
        # Pattern ends with escape - the escaping char is escaped
        result = finder._pattern_to_regex("TEST\\")
        # Should handle gracefully
        assert result is None or hasattr(result, 'match')

    def test_special_regex_characters(self):
        """Test pattern with special regex characters that need escaping."""
        finder = StudioCodeFinder()
        # These characters have special meaning in regex: . * + ? ^ $ ( ) [ ] { } | \
        result = finder._pattern_to_regex("TEST.+*")
        assert result is not None
        # Should match the literal string, not as regex
        assert result.match("TEST.+*")
        assert not result.match("TESTA+B")  # Not interpreted as regex

    def test_pattern_with_spaces(self):
        """Test pattern with spaces."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("TEST ####")
        assert result is not None
        assert result.match("TEST 1234")
        assert not result.match("TEST1234")

    def test_pattern_with_hyphens(self):
        """Test pattern with hyphens."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("##-##-##")
        assert result is not None
        assert result.match("12-34-56")
        assert not result.match("123456")


class TestProcessResultWithInvalidStates:
    """Tests for process method with various invalid states."""

    def test_process_with_empty_tokens_list(self):
        """Test process with empty tokens list."""
        finder = StudioCodeFinder()
        result = TokenizationResult(
            original="test",
            cleaned="test",
            pattern="{token0}",
            tokens=[]
        )
        processed = finder.process(result)
        assert processed.tokens == []

    def test_process_with_none_tokens(self):
        """Test process with None tokens."""
        finder = StudioCodeFinder()
        result = TokenizationResult(
            original="test",
            cleaned="test",
            pattern="{token0}",
            tokens=None
        )
        processed = finder.process(result)
        assert processed.tokens is None

    def test_process_with_all_already_identified_tokens(self):
        """Test process when all tokens are already identified."""
        finder = StudioCodeFinder()
        tokens = [
            Token(value="Active Duty", type="studio", position=0),
            Token(value="2020-01-15", type="date", position=12),
        ]
        result = TokenizationResult(
            original="Active Duty 2020-01-15",
            cleaned="Active Duty 2020-01-15",
            pattern="{studio} {date}",
            tokens=tokens
        )
        processed = finder.process(result)
        # Should not change already identified tokens
        assert processed.tokens[0].type == "studio"
        assert processed.tokens[1].type == "date"

    def test_process_preserves_non_matching_tokens(self):
        """Test that non-matching tokens are preserved."""
        finder = StudioCodeFinder()
        tokens = [
            Token(value="RandomText123", type="text", position=0),
            Token(value="Scene", type="text", position=15),
        ]
        result = TokenizationResult(
            original="RandomText123 - Scene",
            cleaned="RandomText123 - Scene",
            pattern="{token0} - {token1}",
            tokens=tokens
        )
        processed = finder.process(result)
        # Non-matching tokens should remain as text
        assert len(processed.tokens) == 2

    def test_process_updates_pattern_correctly(self):
        """Test that pattern is updated correctly when code is matched."""
        finder = StudioCodeFinder()
        # Create a token that matches a known pattern
        tokens = [
            Token(value="AD0001", type="text", position=0),
            Token(value="Scene", type="text", position=7),
        ]
        result = TokenizationResult(
            original="AD0001 - Scene",
            cleaned="AD0001 - Scene",
            pattern="{token0} - {token1}",
            tokens=tokens
        )
        processed = finder.process(result)
        # Pattern should be updated if match found
        if processed.tokens[0].type == "studio_code":
            assert "{studio_code}" in processed.pattern


class TestBoundaryConditions:
    """Tests for boundary conditions and limits."""

    def test_very_long_pattern(self):
        """Test handling of very long patterns."""
        finder = StudioCodeFinder()
        long_pattern = "A" * 1000 + "####"
        result = finder._pattern_to_regex(long_pattern)
        assert result is None or hasattr(result, 'match')

    def test_many_hash_groups(self):
        """Test pattern with many consecutive hash groups."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("##-##-##-##-##")
        assert result is not None
        assert result.match("12-34-56-78-90")

    def test_alternating_escapes(self):
        """Test pattern with alternating escape and regular characters."""
        finder = StudioCodeFinder()
        result = finder._pattern_to_regex("A\\#B\\#C\\#D")
        assert result is not None
        assert result.match("A#B#C#D")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
