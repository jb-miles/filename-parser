#!/usr/bin/env python3
"""
Studio matcher module for identifying and marking studio tokens in filenames.

Matches token values against known studios and their aliases from the studios
dictionary. When a match is found, the token type is changed to 'studio' and
the pattern is updated accordingly.
"""

import json
import re
from typing import Dict, List, Set, Optional, Tuple
from .tokenizer import TokenizationResult, Token
from .dictionary_loader import DictionaryLoader


class StudioMatcher:
    """Matches tokens against known studios and their aliases."""

    def __init__(self):
        """Initialize studio matcher with studios dictionary."""
        self.studios: Dict[str, str] = {}  # Lower-case name/alias -> canonical name
        self.canonical_names: Set[str] = set()  # Original canonical names for reference
        self.exact_only_keys: Set[str] = set()  # Studio keys (lowercase) that require exact-only matching
        self._load_studios()

    def _load_studios(self) -> None:
        """
        Load studios dictionary and build lookup structure.

        Supports exact-only marker (^) suffix on canonical names and aliases.
        Example: "Bang^" will only match exact "Bang", not partial matches.
        """
        studios_list = DictionaryLoader.load_dictionary('studios.json')
        if not studios_list:
            return

        for studio in studios_list:
            canonical_name = studio.get('canonical_name', '')
            if not canonical_name:
                continue

            # Check for exact-only marker on canonical name
            exact_only_canonical = canonical_name.endswith('^')
            if exact_only_canonical:
                canonical_name = canonical_name[:-1]  # Strip the ^ marker

            # Add canonical name (case-insensitive)
            canonical_lower = canonical_name.lower()
            self.studios[canonical_lower] = canonical_name
            self.canonical_names.add(canonical_name)

            if exact_only_canonical:
                self.exact_only_keys.add(canonical_lower)

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
                    if not alias:
                        continue

                    # Check for exact-only marker on alias
                    exact_only_alias = alias.endswith('^')
                    if exact_only_alias:
                        alias = alias[:-1]  # Strip the ^ marker

                    alias_lower = alias.lower()
                    self.studios[alias_lower] = canonical_name

                    if exact_only_alias:
                        self.exact_only_keys.add(alias_lower)

            # Add abbreviations if present (deprecated, kept for backward compatibility)
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

        # Apply alias mapping overrides/normalization
        alias_map = DictionaryLoader.load_dictionary('studio_aliases.json') or {}
        if isinstance(alias_map, dict):
            for alias, canonical in alias_map.items():
                if not canonical:
                    continue
                # Track canonical for reference even if not present in base list
                self.canonical_names.add(canonical)
                self.studios[alias.lower()] = canonical

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

    def process_dash_fallback(self, result: TokenizationResult) -> TokenizationResult:
        """
        Fallback studio matching for tokens with internal dashes.

        Only runs if no studio has been found yet. Looks for tokens containing
        internal dashes (e.g., "FalconStudios-Scene" or "Sean-Cody") and checks
        if either part matches a known studio. When found, splits the token
        to preserve all parts.

        Args:
            result: TokenizationResult to process

        Returns:
            Modified TokenizationResult with studio tokens marked if found
        """
        # Skip if we already have a studio
        if result.studio:
            return result

        if not result.tokens or not result.pattern:
            return result

        # Track which tokens need to be split for studio extraction
        # token_index -> (canonical_name, part_index, parts_list)
        tokens_to_split: Dict[int, Tuple[str, int, List[str]]] = {}

        for i, token in enumerate(result.tokens):
            # Skip path tokens and already-labeled tokens
            if token.type == 'path' or token.type != 'text':
                continue

            # Look for internal dashes (dash with no spaces immediately around it)
            # Examples: "FalconStudios-Scene", "Sean-Cody", "Helix-Studios More Text"
            # Pattern: word-word (no space immediately before/after dash)
            if '-' in token.value:
                # Check if this is truly an internal dash (not " - " with spaces)
                if ' - ' in token.value:
                    continue  # This is a spaced delimiter, skip it

                # Split on dash (limit to first dash to preserve rest)
                parts = token.value.split('-', 1)  # Only split on first dash

                # Check each part for studio match
                for part_idx, part in enumerate(parts):
                    # Clean the part (might have extra spaces)
                    part_clean = part.strip()
                    if len(part_clean) < 2:  # Skip very short parts
                        continue

                    part_lower = part_clean.lower()
                    if part_lower in self.studios:
                        canonical_name = self.studios[part_lower]
                        tokens_to_split[i] = (canonical_name, part_idx, parts)
                        break  # Found a match, stop checking other parts

        # If we found studio matches, split tokens and update pattern
        if tokens_to_split:
            result = self._split_tokens_and_update_pattern(result, tokens_to_split)

        return result

    def process_partial_match_fallback(self, result: TokenizationResult) -> TokenizationResult:
        """
        Fallback studio matching for partial/substring matches within tokens.

        Only runs if no studio has been found yet. Looks for tokens that contain
        a known studio name as a substring (e.g., "LetThemWatchScene1" contains
        "LetThemWatch"). When found, splits the token to preserve all parts.

        Args:
            result: TokenizationResult to process

        Returns:
            Modified TokenizationResult with studio tokens marked if found
        """
        # Skip if we already have a studio
        if result.studio:
            return result

        if not result.tokens or not result.pattern:
            return result

        # Track which tokens need to be split for studio extraction
        # token_index -> (canonical_name, start_pos, end_pos)
        tokens_to_split: Dict[int, Tuple[str, int, int]] = {}

        for i, token in enumerate(result.tokens):
            # Skip path tokens and already-labeled tokens
            if token.type == 'path' or token.type != 'text':
                continue

            token_lower = token.value.lower()

            # Find the longest matching studio name within this token
            longest_match = None
            longest_length = 0
            match_start = -1
            match_end = -1

            for studio_key, canonical_name in self.studios.items():
                # Skip very short studio names to avoid false positives
                if len(studio_key) < 3:
                    continue

                # Skip studios marked as exact-only (ending with ^ in dictionary)
                if studio_key in self.exact_only_keys:
                    continue

                # Check if this studio name appears as a substring
                pos = token_lower.find(studio_key)
                if pos != -1:
                    # Found a match - check if it's the longest so far
                    if len(studio_key) > longest_length:
                        longest_match = canonical_name
                        longest_length = len(studio_key)
                        match_start = pos
                        match_end = pos + len(studio_key)

            # If we found a match, record it
            if longest_match:
                tokens_to_split[i] = (longest_match, match_start, match_end)

        # If we found studio matches, split tokens and update pattern
        if tokens_to_split:
            result = self._split_substring_tokens_and_update_pattern(result, tokens_to_split)

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
            studio=studio_value,
            title=result.title,
            sequence=result.sequence,
            group=result.group,
            studio_code=getattr(result, "studio_code", None),
            sources=result.sources,
            confidences=result.confidences
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

    def _split_tokens_and_update_pattern(
        self,
        result: TokenizationResult,
        tokens_to_split: Dict[int, Tuple[str, int, List[str]]]
    ) -> TokenizationResult:
        """
        Split tokens containing studios and update pattern accordingly.

        When a studio is found within a dash-separated token (e.g., "Studio-Scene"),
        this method splits the token into separate parts and updates the pattern
        to preserve all content.

        Args:
            result: Original TokenizationResult
            tokens_to_split: Mapping of token index to (canonical_name, part_index, parts_list)

        Returns:
            New TokenizationResult with split tokens and updated pattern
        """
        new_tokens = []
        token_mapping = {}  # old_token_index -> list of (new_token_index, is_studio)
        real_token_index = 0  # Counter for non-path tokens in original

        # First pass: Build new token list and track mapping
        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                new_tokens.append(token)
                continue

            if i in tokens_to_split:
                canonical_name, studio_part_idx, parts = tokens_to_split[i]
                split_info = []

                # Build new tokens from the split parts
                for part_idx, part in enumerate(parts):
                    part_stripped = part.strip()
                    if not part_stripped:
                        continue

                    # Calculate the new token index (count only non-path tokens)
                    new_idx = sum(1 for t in new_tokens if t.type != 'path')

                    if part_idx == studio_part_idx:
                        # This part is the studio
                        new_tokens.append(Token(
                            value=canonical_name,
                            type='studio',
                            position=token.position
                        ))
                        split_info.append((new_idx, True))  # True = is studio
                    else:
                        # This part is remaining text
                        new_tokens.append(Token(
                            value=part_stripped,
                            type='text',
                            position=token.position
                        ))
                        split_info.append((new_idx, False))  # False = is text

                token_mapping[real_token_index] = split_info
            else:
                # Regular token, just copy it
                new_idx = sum(1 for t in new_tokens if t.type != 'path')
                new_tokens.append(token)
                token_mapping[real_token_index] = [(new_idx, False)]

            real_token_index += 1

        # Second pass: Rebuild pattern using token mapping
        new_pattern = self._rebuild_pattern_after_split(result.pattern, token_mapping)

        # Get studio value from first split
        studio_value = result.studio or next(iter(tokens_to_split.values()))[0]

        # Return new result with split tokens and updated pattern
        return TokenizationResult(
            original=result.original,
            cleaned=result.cleaned,
            pattern=new_pattern,
            tokens=new_tokens,
            studio=studio_value,
            title=result.title,
            sequence=result.sequence,
            group=result.group,
            studio_code=getattr(result, "studio_code", None),
            sources=result.sources,
            confidences=result.confidences
        )

    def _rebuild_pattern_after_split(
        self,
        pattern: str,
        token_mapping: Dict[int, List[Tuple[int, bool]]]
    ) -> str:
        """
        Rebuild pattern after token splitting.

        Args:
            pattern: Original pattern
            token_mapping: Mapping from old token index to list of (new_index, is_studio)

        Returns:
            Updated pattern with correct token references and dash separators
        """
        if not pattern:
            return pattern

        # Build replacement mapping
        replacements = {}
        for old_idx, new_tokens in token_mapping.items():
            old_pattern = f"{{token{old_idx}}}"

            if len(new_tokens) == 1:
                # Single token (not split)
                new_idx, is_studio = new_tokens[0]
                if is_studio:
                    replacements[old_pattern] = "{studio}"
                else:
                    replacements[old_pattern] = f"{{token{new_idx}}}"
            else:
                # Multiple tokens (was split with dash)
                parts = []
                for new_idx, is_studio in new_tokens:
                    if is_studio:
                        parts.append("{studio}")
                    else:
                        parts.append(f"{{token{new_idx}}}")
                replacements[old_pattern] = "-".join(parts)

        # Apply replacements
        for old_pat, new_pat in replacements.items():
            pattern = pattern.replace(old_pat, new_pat)

        return pattern

    def _split_substring_tokens_and_update_pattern(
        self,
        result: TokenizationResult,
        tokens_to_split: Dict[int, Tuple[str, int, int]]
    ) -> TokenizationResult:
        """
        Split tokens containing studios as substrings and update pattern accordingly.

        When a studio is found within a token (e.g., "LetThemWatchScene1"),
        this method splits the token into parts (prefix, studio, suffix) and
        updates the pattern to preserve all content.

        Args:
            result: Original TokenizationResult
            tokens_to_split: Mapping of token index to (canonical_name, start_pos, end_pos)

        Returns:
            New TokenizationResult with split tokens and updated pattern
        """
        new_tokens = []
        token_mapping = {}  # old_token_index -> list of (new_token_index, is_studio)
        real_token_index = 0  # Counter for non-path tokens in original

        # First pass: Build new token list and track mapping
        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                new_tokens.append(token)
                continue

            if i in tokens_to_split:
                canonical_name, start_pos, end_pos = tokens_to_split[i]
                split_info = []

                # Extract parts: prefix, studio, suffix
                prefix = token.value[:start_pos] if start_pos > 0 else ""
                studio_part = token.value[start_pos:end_pos]
                suffix = token.value[end_pos:] if end_pos < len(token.value) else ""

                # Build tokens for non-empty parts
                # Prefix (if exists)
                if prefix.strip():
                    new_idx = sum(1 for t in new_tokens if t.type != 'path')
                    new_tokens.append(Token(
                        value=prefix.strip(),
                        type='text',
                        position=token.position
                    ))
                    split_info.append((new_idx, False))

                # Studio part (always exists if we got here)
                new_idx = sum(1 for t in new_tokens if t.type != 'path')
                new_tokens.append(Token(
                    value=canonical_name,
                    type='studio',
                    position=token.position
                ))
                split_info.append((new_idx, True))

                # Suffix (if exists)
                if suffix.strip():
                    new_idx = sum(1 for t in new_tokens if t.type != 'path')
                    new_tokens.append(Token(
                        value=suffix.strip(),
                        type='text',
                        position=token.position
                    ))
                    split_info.append((new_idx, False))

                token_mapping[real_token_index] = split_info
            else:
                # Regular token, just copy it
                new_idx = sum(1 for t in new_tokens if t.type != 'path')
                new_tokens.append(token)
                token_mapping[real_token_index] = [(new_idx, False)]

            real_token_index += 1

        # Second pass: Rebuild pattern using token mapping
        new_pattern = self._rebuild_pattern_after_substring_split(result.pattern, token_mapping)

        # Get studio value from first split
        studio_value = result.studio or next(iter(tokens_to_split.values()))[0]

        # Return new result with split tokens and updated pattern
        return TokenizationResult(
            original=result.original,
            cleaned=result.cleaned,
            pattern=new_pattern,
            tokens=new_tokens,
            studio=studio_value,
            title=result.title,
            sequence=result.sequence,
            group=result.group,
            studio_code=getattr(result, "studio_code", None),
            sources=result.sources,
            confidences=result.confidences
        )

    def _rebuild_pattern_after_substring_split(
        self,
        pattern: str,
        token_mapping: Dict[int, List[Tuple[int, bool]]]
    ) -> str:
        """
        Rebuild pattern after substring splitting.

        Args:
            pattern: Original pattern
            token_mapping: Mapping from old token index to list of (new_index, is_studio)

        Returns:
            Updated pattern with correct token references (no separators for substrings)
        """
        if not pattern:
            return pattern

        # Build replacement mapping
        replacements = {}
        for old_idx, new_tokens in token_mapping.items():
            old_pattern = f"{{token{old_idx}}}"

            if len(new_tokens) == 1:
                # Single token (not split)
                new_idx, is_studio = new_tokens[0]
                if is_studio:
                    replacements[old_pattern] = "{studio}"
                else:
                    replacements[old_pattern] = f"{{token{new_idx}}}"
            else:
                # Multiple tokens (was split at substring boundaries)
                # No separator needed - parts are concatenated
                parts = []
                for new_idx, is_studio in new_tokens:
                    if is_studio:
                        parts.append("{studio}")
                    else:
                        parts.append(f"{{token{new_idx}}}")
                replacements[old_pattern] = "".join(parts)  # No separator for substring splits

        # Apply replacements
        for old_pat, new_pat in replacements.items():
            pattern = pattern.replace(old_pat, new_pat)

        return pattern


if __name__ == '__main__':
    # Simple test
    matcher = StudioMatcher()
    print(f"Loaded {len(matcher.studios)} studio names/aliases")
    print(f"Total unique studios: {len(matcher.canonical_names)}")
