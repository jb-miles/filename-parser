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
            pattern = studio_code.get('regex') or studio_code.get('code', '')
            if not pattern:
                continue

            allow_suffix = bool(studio_code.get('allow_suffix'))
            regex = self._pattern_to_regex(
                pattern,
                is_regex=bool(studio_code.get('regex')),
                allow_suffix=allow_suffix
            )
            if not regex:
                continue

            self.studio_code_patterns.append((
                regex,
                {
                    'studio': studio_code.get('studio'),
                    'pattern': pattern,
                    'normalize': studio_code.get('normalize') or {},
                    'code_group': studio_code.get('code_group', 1 if allow_suffix else 0)
                }
            ))

    def _pattern_to_regex(
        self,
        pattern: str,
        is_regex: bool = False,
        allow_suffix: bool = False
    ) -> Optional[Pattern]:
        """
        Convert a code pattern with '#' placeholders into a compiled regex.
        '#' characters represent digits; other characters are escaped literally.
        When allow_suffix is True, trailing non-alphanumeric suffixes are permitted
        (e.g., resolution markers), and the base pattern is captured in group 1.
        """
        if is_regex:
            inner = pattern
            if inner.startswith("^"):
                inner = inner[1:]
            if inner.endswith("$"):
                inner = inner[:-1]
            regex_str = rf"^({inner})(?:[^A-Za-z0-9].*)?$" if allow_suffix else f"^{inner}$"
        else:
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

            base_pattern = "".join(parts)
            if allow_suffix:
                regex_str = rf"^({base_pattern})(?:[^A-Za-z0-9].*)?$"
            else:
                regex_str = "^" + base_pattern + "$"

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
            match = regex.match(normalized_value)
            if match:
                group_idx = info.get('code_group', 0) or 0
                try:
                    raw_code = match.group(group_idx)
                except IndexError:
                    raw_code = match.group(0)

                normalized_code = self._normalize_code(raw_code, info.get('normalize') or {})
                code_value = normalized_code or raw_code
                return {
                    'studio': info.get('studio'),
                    'code': code_value
                }

        return None

    def _normalize_code(self, code_value: str, normalize: Dict[str, bool]) -> str:
        """
        Normalize a raw code value using rules from the dictionary entry.
        """
        code = code_value.strip()
        if not normalize:
            return code

        if normalize.get('strip_prefix_letters'):
            code = re.sub(r'^[A-Za-z]+[-_\s]*', '', code)

        if normalize.get('replace_underscores_with_dash'):
            code = code.replace('_', '-').replace(' ', '-')

        if normalize.get('digits_only'):
            code = re.sub(r'\D', '', code)

        if normalize.get('strip_leading_zeros'):
            code = code.lstrip('0') or "0"

        if normalize.get('uppercase'):
            code = code.upper()

        return code

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
            first_match = next((match for match in studio_code_matches.values() if match.get('studio')), None)
            if first_match:
                studio_value = first_match.get('studio')

        studio_code_value = getattr(result, "studio_code", None)
        if not studio_code_value:
            first_match = next(iter(studio_code_matches.values()))
            studio_code_value = first_match.get('code')

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
            studio_code=studio_code_value,
            sources=result.sources,
            confidences=result.confidences
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
