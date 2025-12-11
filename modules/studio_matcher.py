#!/usr/bin/env python3
"""
Studio matcher module for identifying and marking studio tokens in filenames.

Matches token values against known studios and their aliases from the studios
dictionary. When a match is found, the token type is changed to 'studio' and
the pattern is updated accordingly.
"""

import json
import os
import re
from typing import Dict, List, Set, Optional, Tuple
from .tokenizer import TokenizationResult, Token


class StudioMatcher:
    """Matches tokens against known studios and their aliases."""

    # Path to studios dictionary relative to this file
    STUDIOS_PATH = os.path.join(os.path.dirname(__file__), "..", "dictionaries", "studios.json")

    def __init__(self):
        """Initialize studio matcher with studios dictionary."""
        self.studios: Dict[str, str] = {}  # Lower-case name/alias -> canonical name
        self.canonical_names: Set[str] = set()  # Original canonical names for reference
        self._load_studios()

    def _load_studios(self) -> None:
        """Load studios dictionary and build lookup structure."""
        try:
            with open(self.STUDIOS_PATH, 'r', encoding='utf-8') as f:
                studios_list = json.load(f)

            for studio in studios_list:
                canonical_name = studio.get('canonical_name', '')
                if not canonical_name:
                    continue

                # Add canonical name (case-insensitive)
                self.studios[canonical_name.lower()] = canonical_name
                self.canonical_names.add(canonical_name)

                # Add aliases if present
                aliases = studio.get('aliases', [])
                if isinstance(aliases, str):
                    # If it's a JSON string, parse it
                    try:
                        aliases = json.loads(aliases)
                    except json.JSONDecodeError:
                        aliases = []

                if isinstance(aliases, list):
                    for alias in aliases:
                        if alias:
                            self.studios[alias.lower()] = canonical_name

                # Add abbreviations if present
                abbrs = studio.get('abbr', [])
                if isinstance(abbrs, str):
                    # If it's a JSON string, parse it
                    try:
                        abbrs = json.loads(abbrs)
                    except json.JSONDecodeError:
                        abbrs = []

                if isinstance(abbrs, list):
                    for abbr in abbrs:
                        if abbr:
                            self.studios[abbr.lower()] = canonical_name

        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def process(self, result: TokenizationResult) -> TokenizationResult:
        """
        Process tokenization result to identify and mark studio tokens.

        For each token, checks if its value matches a known studio or alias
        (case-insensitive exact match). When a match is found, the token type
        is changed to 'studio' and the pattern is updated.

        Args:
            result: TokenizationResult to process

        Returns:
            Modified TokenizationResult with studio tokens marked
        """
        if not result.tokens or not result.pattern:
            return result

        # Track which tokens are studios
        studio_matches: Dict[int, str] = {}  # token_index -> canonical_name

        for i, token in enumerate(result.tokens):
            # Skip path tokens
            if token.type == 'path':
                continue

            # Check if token matches a studio (case-insensitive)
            token_lower = token.value.lower()
            if token_lower in self.studios:
                canonical_name = self.studios[token_lower]
                studio_matches[i] = canonical_name

        # If we found studio matches, update tokens and pattern
        if studio_matches:
            result = self._update_tokens_and_pattern(result, studio_matches)

        return result

    def _update_tokens_and_pattern(
        self,
        result: TokenizationResult,
        studio_matches: Dict[int, str]
    ) -> TokenizationResult:
        """
        Update token types and pattern to mark studio matches.

        Args:
            result: Original TokenizationResult
            studio_matches: Mapping of token index to canonical studio name

        Returns:
            New TokenizationResult with updated tokens and pattern
        """
        # Create new tokens list with studio matches marked
        new_tokens = []
        real_token_index = 0  # Counter for non-path tokens
        studio_count = 0  # Counter for studio replacements in pattern

        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                new_tokens.append(token)
                continue

            if i in studio_matches:
                # Replace with studio token
                new_tokens.append(Token(
                    value=studio_matches[i],
                    type='studio',
                    position=token.position
                ))
            else:
                new_tokens.append(token)
            real_token_index += 1

        # Rebuild pattern with studio replacements
        new_pattern = self._rebuild_pattern(result, studio_matches)

        # Set studio metadata if not already populated
        studio_value = result.studio or next(iter(studio_matches.values()))

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
        studio_matches: Dict[int, str]
    ) -> str:
        """
        Rebuild the pattern, replacing {tokenN} with {studio} for studio matches.

        Args:
            result: Original TokenizationResult with original pattern
            studio_matches: Mapping of token index to canonical studio name

        Returns:
            Updated pattern string
        """
        pattern = result.pattern or ""
        if not pattern:
            return pattern

        # Build a mapping of {tokenN} to replacement for studio matches
        replacements = {}
        real_token_index = 0

        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                continue

            if i in studio_matches:
                replacements[f"{{token{real_token_index}}}"] = "{studio}"

            real_token_index += 1

        # Apply replacements to pattern
        for old_pattern, new_pattern_part in replacements.items():
            pattern = pattern.replace(old_pattern, new_pattern_part)

        return pattern


if __name__ == '__main__':
    # Simple test
    matcher = StudioMatcher()
    print(f"Loaded {len(matcher.studios)} studio names/aliases")
    print(f"Total unique studios: {len(matcher.canonical_names)}")
