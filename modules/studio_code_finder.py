#!/usr/bin/env python3
"""
Studio code finder module for identifying and marking studio codes in filenames.

Matches token values against known studio code patterns. When a match is found,
the token type is changed to 'studio_code' and the pattern is updated accordingly.
"""

import re
from typing import Dict, List, Optional, Tuple, Pattern
from .tokenizer import TokenizationResult, Token
from .dictionary_loader import DictionaryLoader


class StudioCodeFinder:
    """Finds and marks studio codes in tokens."""

    def __init__(self):
        """Initialize studio code finder with studio code patterns."""
        self.studio_code_patterns: List[Tuple[Pattern, Dict[str, str]]] = []
        self._load_studio_codes()

    def _load_studio_codes(self) -> None:
        """Load studio codes from parser dictionary."""
        studio_codes = DictionaryLoader.get_section('studio_codes')
        if not studio_codes:
            return

        for studio_code in studio_codes:
            code = studio_code.get('code', '')
            studio = studio_code.get('studio', '')
            if not code or not studio:
                continue

            regex = self._pattern_to_regex(code)
            if not regex:
                continue

            self.studio_code_patterns.append((
                regex,
                {
                    'studio': studio,
                    'pattern': code
                }
            ))

    def _pattern_to_regex(self, pattern: str) -> Optional[Pattern]:
        """
        Convert a code pattern with '#' placeholders into a compiled regex.
        '#' characters represent digits; other characters are escaped literally.
        """
        parts: List[str] = []
        i = 0
        length = len(pattern)

        while i < length:
            char = pattern[i]

            # Treat escaped characters as literals (e.g., "\#" -> "#")
            if char == '\\' and i + 1 < length:
                parts.append(re.escape(pattern[i + 1]))
                i += 2
                continue

            # Consecutive # represent digits
            if char == '#':
                j = i
                while j < length and pattern[j] == '#':
                    j += 1
                parts.append(rf"\d{{{j - i}}}")
                i = j
                continue

            # Default: escape literal character
            parts.append(re.escape(char))
            i += 1

        if not parts:
            return None

        regex_str = "^" + "".join(parts) + "$"
        try:
            return re.compile(regex_str, re.IGNORECASE)
        except re.error:
            return None

    def process(self, result: TokenizationResult) -> TokenizationResult:
        """
        Process tokenization result to identify and mark studio code tokens.

        For each token, checks if its value matches a known studio code pattern.
        When a match is found, the token type is changed to 'studio_code' and
        the pattern is updated.

        Args:
            result: TokenizationResult to process

        Returns:
            Modified TokenizationResult with studio code tokens marked
        """
        if not result.tokens or not result.pattern:
            return result

        # Track which tokens are studio codes
        studio_code_matches: Dict[int, Dict[str, str]] = {}  # token_index -> {studio: name, code: value}

        for i, token in enumerate(result.tokens):
            # Skip path tokens and already identified studio tokens
            if token.type in ['path', 'studio']:
                continue

            # Check if token matches a studio code pattern
            studio_code_info = self._match_studio_code(token.value)
            if studio_code_info:
                studio_code_matches[i] = studio_code_info

        # If we found studio code matches, update tokens and pattern
        if studio_code_matches:
            result = self._update_tokens_and_pattern(result, studio_code_matches)

        return result

    def _match_studio_code(self, token_value: str) -> Optional[Dict[str, str]]:
        """
        Check if a token value matches a known studio code pattern.

        Args:
            token_value: The token value to check

        Returns:
            Dictionary with studio and code info if match found, None otherwise
        """
        normalized_value = token_value.strip()

        for regex, info in self.studio_code_patterns:
            if regex.match(normalized_value):
                # Preserve the original token value as the code
                return {
                    'studio': info['studio'],
                    'code': token_value
                }

        return None

    def _update_tokens_and_pattern(
        self,
        result: TokenizationResult,
        studio_code_matches: Dict[int, Dict[str, str]]
    ) -> TokenizationResult:
        """
        Update token types and pattern to mark studio code matches.

        Args:
            result: Original TokenizationResult
            studio_code_matches: Mapping of token index to studio code info

        Returns:
            New TokenizationResult with updated tokens and pattern
        """
        # Create new tokens list with studio code matches marked
        new_tokens = []
        real_token_index = 0  # Counter for non-path tokens
        studio_code_count = 0  # Counter for studio code replacements in pattern

        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                new_tokens.append(token)
                continue

            if i in studio_code_matches:
                # Replace with studio code token
                studio_info = studio_code_matches[i]
                new_tokens.append(Token(
                    value=studio_info['code'],
                    type='studio_code',
                    position=token.position
                ))
            else:
                new_tokens.append(token)
            real_token_index += 1

        # Rebuild pattern with studio code replacements
        new_pattern = self._rebuild_pattern(result, studio_code_matches)

        # Set studio metadata if not already populated
        studio_value = result.studio
        if not studio_value:
            # Take the first matched studio name
            first_match = next(iter(studio_code_matches.values()))
            studio_value = first_match.get('studio')

        # Return new result with updated tokens and pattern
        return TokenizationResult(
            original=result.original,
            cleaned=result.cleaned,
            pattern=new_pattern,
            tokens=new_tokens,
            studio=studio_value
        )

    def _rebuild_pattern(
        self,
        result: TokenizationResult,
        studio_code_matches: Dict[int, Dict[str, str]]
    ) -> str:
        """
        Rebuild the pattern, replacing {tokenN} with {studio_code} for studio code matches.

        Args:
            result: Original TokenizationResult with original pattern
            studio_code_matches: Mapping of token index to studio code info

        Returns:
            Updated pattern string
        """
        pattern = result.pattern
        if not pattern:
            return pattern or ""

        # Build a mapping of {tokenN} to replacement for studio code matches
        replacements = {}
        real_token_index = 0

        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                continue

            if i in studio_code_matches:
                replacements[f"{{token{real_token_index}}}"] = "{studio_code}"

            real_token_index += 1

        # Apply replacements to pattern
        for old_pattern, new_pattern_part in replacements.items():
            pattern = pattern.replace(old_pattern, new_pattern_part)

        return pattern


if __name__ == '__main__':
    # Simple test
    finder = StudioCodeFinder()
    print(f"Loaded {len(finder.studio_code_patterns)} studio code patterns")
    for regex, info in finder.studio_code_patterns:
        print(f"  Pattern: {info['pattern']} -> Studio: {info['studio']}")
