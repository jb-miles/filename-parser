#!/usr/bin/env python3
"""
Studio code finder module for identifying and marking studio codes in filenames.

Matches token values against known studio code patterns. When a match is found,
the token type is changed to 'studio_code' and the pattern is updated accordingly.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Pattern
from .tokenizer import TokenizationResult, Token
from .dictionary_loader import DictionaryLoader


class StudioCodeFinder:
    """Finds and marks studio codes in tokens."""

    def __init__(self):
        """Initialize studio code finder with studio code patterns."""
        self.studio_code_patterns: List[Tuple[Pattern, Dict[str, Any]]] = []
        self._load_studio_codes()

    def _load_studio_codes(self) -> None:
        """Load studio-code rules from dedicated JSON file."""
        studio_code_rules = DictionaryLoader.load_dictionary("studio_codes.json")
        if not studio_code_rules or not isinstance(studio_code_rules, list):
            return

        for rule in studio_code_rules:
            if not isinstance(rule, dict):
                continue

            studio = rule.get("studio")
            allow_suffix = bool(rule.get("allow_suffix"))
            normalize = rule.get("normalize") or {}
            relationship = str(rule.get("studio_relationship") or "can_set").strip().lower()
            if relationship not in {"requires", "can_set"}:
                relationship = "can_set"

            patterns = rule.get("code_patterns") or []
            if isinstance(patterns, str):
                patterns = [patterns]
            if not isinstance(patterns, list):
                continue

            for raw_pattern in patterns:
                if not raw_pattern or not isinstance(raw_pattern, str):
                    continue

                pattern = raw_pattern.strip()
                if not pattern:
                    continue

                is_regex = False
                if pattern.lower().startswith("re:"):
                    is_regex = True
                    pattern = pattern[3:]
                    pattern = pattern.strip()
                    if not pattern:
                        continue

                regex = self._pattern_to_regex(
                    pattern,
                    is_regex=is_regex,
                    allow_suffix=allow_suffix,
                )
                if not regex:
                    continue

                self.studio_code_patterns.append(
                    (
                        regex,
                        {
                            "studio": studio,
                            "pattern": raw_pattern,
                            "normalize": normalize,
                            "code_group": int(rule.get("code_group", 1 if allow_suffix else 0) or 0),
                            "studio_relationship": relationship,
                        },
                    )
                )

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
            base_pattern = self._compile_code_pattern(pattern)
            if not base_pattern:
                return None
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
        current_studio = result.studio

        for i, token in enumerate(result.tokens):
            # Skip path tokens and already identified studio tokens
            if token.type in ['path', 'studio']:
                continue

            # Check if token matches a studio code pattern
            studio_code_info = self._match_studio_code(token.value, current_studio=current_studio)
            if studio_code_info:
                studio_code_matches[i] = studio_code_info

        # If we found studio code matches, update tokens and pattern
        if studio_code_matches:
            result = self._update_tokens_and_pattern(result, studio_code_matches)

        return result

    def _match_studio_code(self, token_value: str, *, current_studio: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Check if a token value matches a known studio code pattern.

        Args:
            token_value: The token value to check

        Returns:
            Dictionary with studio and code info if match found, None otherwise
        """
        normalized_value = token_value.strip()
        current_studio_normalized = (current_studio or "").strip().lower()

        for regex, info in self.studio_code_patterns:
            relationship = str(info.get("studio_relationship") or "can_set").strip().lower()
            if relationship == "requires":
                if not current_studio_normalized:
                    continue
                required = (info.get("studio") or "").strip().lower()
                if required and required != current_studio_normalized:
                    continue

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
                    'code': code_value,
                    'code_span': match.span(group_idx),
                }

        return None

    def _normalize_code(self, code_value: str, normalize: Dict[str, bool]) -> str:
        """
        Normalize a raw code value using rules from the dictionary entry.
        """
        code = code_value.strip()
        if not normalize:
            return code

        if normalize.get("normalize_numeric_pair"):
            match = re.match(r"^(\d{3,5})\s+(\d{2})$", code)
            if match:
                prefix, suffix = match.groups()
                return prefix.zfill(5) + suffix

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

    def _compile_code_pattern(self, pattern: str) -> Optional[str]:
        """
        Compile a dictionary "code" pattern into a regex body.

        Supported syntax:
        - '#' placeholders represent digits (consecutive '#' -> exact length)
        - '(###)' denotes an optional digit prefix of variable length 0..N (N = number of '#')
          Example: "(##)### ##" matches "123 45", "1234 56", "12345 67"
        - '\\' escapes the next character as a literal
        """

        def compile_segment(start: int, until: Optional[str] = None) -> Tuple[Optional[str], int, bool, int]:
            parts: List[str] = []
            hashes_only = True
            hashes_count = 0
            i = start
            length = len(pattern)

            while i < length:
                char = pattern[i]

                if until and char == until:
                    return "".join(parts), i + 1, hashes_only, hashes_count

                if char == "\\":
                    if i + 1 >= length:
                        return None, length, False, 0
                    parts.append(re.escape(pattern[i + 1]))
                    hashes_only = False
                    i += 2
                    continue

                if char == "(":
                    inner, new_i, inner_hashes_only, inner_hashes_count = compile_segment(i + 1, until=")")
                    if inner is None:
                        return None, length, False, 0
                    if inner_hashes_only and inner_hashes_count > 0:
                        parts.append(rf"\d{{0,{inner_hashes_count}}}")
                        hashes_count += inner_hashes_count
                    else:
                        parts.append(f"(?:{inner})?")
                        hashes_only = False
                    i = new_i
                    continue

                if char == ")":
                    # Unbalanced ')' outside an optional group: treat as literal.
                    parts.append(re.escape(char))
                    hashes_only = False
                    i += 1
                    continue

                if char == "#":
                    j = i
                    while j < length and pattern[j] == "#":
                        j += 1
                    count = j - i
                    parts.append(rf"\d{{{count}}}")
                    hashes_count += count
                    i = j
                    continue

                parts.append(re.escape(char))
                hashes_only = False
                i += 1

            if until:
                return None, length, False, 0
            return "".join(parts), length, hashes_only, hashes_count

        compiled, _, _, _ = compile_segment(0, until=None)
        return compiled

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
        # Create new tokens list with studio code matches marked, preserving suffix content.
        new_tokens: List[Token] = []
        token_mapping: Dict[int, List[Tuple[int, bool]]] = {}  # old_token_index -> [(new_idx, is_code), ...]
        real_token_index = 0  # Counter for non-path tokens in original

        def next_real_index() -> int:
            return sum(1 for t in new_tokens if t.type != "path")

        for i, token in enumerate(result.tokens or []):
            if token.type == "path":
                new_tokens.append(token)
                continue

            if i in studio_code_matches:
                studio_info = studio_code_matches[i]
                split_info: List[Tuple[int, bool]] = []

                code_value = studio_info.get("code") or ""
                new_idx = next_real_index()
                new_tokens.append(Token(value=str(code_value), type="studio_code", position=token.position))
                split_info.append((new_idx, True))

                remainder = self._extract_suffix_after_code(token.value, studio_info.get("code_span"))
                if remainder:
                    new_idx = next_real_index()
                    new_tokens.append(Token(value=remainder, type="text", position=token.position))
                    split_info.append((new_idx, False))

                token_mapping[real_token_index] = split_info
            else:
                new_idx = next_real_index()
                new_tokens.append(token)
                token_mapping[real_token_index] = [(new_idx, False)]

            real_token_index += 1

        new_pattern = self._rebuild_pattern_after_split(result.pattern, token_mapping)

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

    def _extract_suffix_after_code(self, token_value: str, code_span) -> Optional[str]:
        if not token_value:
            return None

        value = str(token_value)
        if not isinstance(code_span, (tuple, list)) or len(code_span) != 2:
            return None

        _, end = code_span
        if end <= 0 or end >= len(value):
            return None

        remainder = value[end:]
        # Strip common separators between code and the remaining content.
        remainder = re.sub(r"^[^A-Za-z0-9]+", "", remainder)
        remainder = remainder.strip()
        return remainder or None

    def _rebuild_pattern_after_split(
        self,
        pattern: Optional[str],
        token_mapping: Dict[int, List[Tuple[int, bool]]],
    ) -> str:
        if not pattern:
            return pattern or ""

        def replace_placeholder(match: re.Match[str]) -> str:
            old_idx = int(match.group(1))
            new_tokens = token_mapping.get(old_idx)
            if not new_tokens:
                return match.group(0)

            if len(new_tokens) == 1:
                new_idx, is_code = new_tokens[0]
                return "{studio_code}" if is_code else f"{{token{new_idx}}}"

            parts: List[str] = []
            for new_idx, is_code in new_tokens:
                parts.append("{studio_code}" if is_code else f"{{token{new_idx}}}")
            return " ".join(parts)

        return re.sub(r"\{token(\d+)\}", replace_placeholder, pattern)


if __name__ == '__main__':
    # Simple test
    finder = StudioCodeFinder()
    print(f"Loaded {len(finder.studio_code_patterns)} studio code patterns")
    for regex, info in finder.studio_code_patterns:
        print(f"  Pattern: {info['pattern']} -> Studio: {info['studio']}")
