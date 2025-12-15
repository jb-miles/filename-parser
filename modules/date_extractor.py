#!/usr/bin/env python3
"""
Date extraction module for tokenized filenames.
Extracts dates from tokens and converts them to dedicated {date} tokens.
After date extraction, all subsequent tokens are renumbered.
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from .tokenizer import Token, TokenizationResult
from .dictionary_loader import DictionaryLoader


@dataclass
class DateMatch:
    """Represents a date found within a token."""
    date_str: str
    start: int
    end: int
    token_index: int
    normalized_date: Optional[str] = None


class DateExtractor:
    """
    Extract dates from tokens and create dedicated {date} tokens.

    When a date is found in a token:
    - Date becomes {date} in the pattern
    - Remaining text becomes a new numbered token
    - All subsequent tokens are renumbered

    Example:
        Before: token0="20200101 Happy times", token1="Something"
        After:  {date}="20200101", token1="Happy times", token2="Something"
    """

    def __init__(self):
        """Initialize with date patterns from JSON config."""
        self.date_patterns, self.month_names = self._load_date_patterns()

    def _load_date_patterns(self) -> Tuple[List[Tuple[re.Pattern, str]], dict]:
        """
        Load date patterns from date_formats.json.

        Returns:
            Tuple of (compiled_regex, pattern_type) tuples and month name map
        """
        config = DictionaryLoader.load_dictionary('date_formats.json')
        if not config:
            return [], {}

        patterns = []
        month_pattern = config.get('month_pattern', '')
        month_names = config.get('month_names', {})

        for pattern_entry in config.get('patterns', []):
            regex_str = pattern_entry.get('regex', '')
            pattern_type = pattern_entry.get('type', '')

            if not regex_str:
                continue

            # Substitute month pattern placeholder
            regex_str = regex_str.replace('MONTH_PATTERN', month_pattern)

            try:
                compiled = re.compile(regex_str, re.IGNORECASE)
                patterns.append((compiled, pattern_type))
            except re.error:
                continue

        return patterns, month_names

    def process(self, result: TokenizationResult) -> TokenizationResult:
        """
        Process tokenization result to extract dates from tokens.

        Args:
            result: TokenizationResult from tokenizer

        Returns:
            Updated TokenizationResult with dates extracted and tokens renumbered
        """
        # Handle None tokens gracefully
        if result.tokens is None:
            return result

        tokens = result.tokens

        # Find all dates in tokens (excluding path tokens)
        date_matches = self._find_dates_in_tokens(tokens)

        if not date_matches:
            # No dates found, return unchanged
            return result

        # Split tokens where dates were found
        new_tokens = self._split_tokens_with_dates(tokens, date_matches)

        # Update pattern to reflect new token structure
        new_pattern = self._update_pattern(result.pattern, date_matches, tokens)

        return TokenizationResult(
            original=result.original,
            cleaned=result.cleaned,
            pattern=new_pattern,
            tokens=new_tokens,
            studio=result.studio,
            title=result.title,
            sequence=result.sequence,
            group=result.group,
            studio_code=getattr(result, "studio_code", None),
            sources=result.sources,
            confidences=result.confidences
        )

    def _find_dates_in_tokens(self, tokens: List[Token]) -> List[DateMatch]:
        """
        Find all dates within tokens.

        Args:
            tokens: List of tokens to search

        Returns:
            List of DateMatch objects
        """
        matches = []

        # Track index of non-path tokens
        token_idx = 0

        for token in tokens:
            # Skip path tokens
            if token.type == 'path':
                continue

            # Try each date pattern
            for pattern, pattern_type in self.date_patterns:
                match = pattern.search(token.value)
                if match:
                    normalized = self._normalize_date(match, pattern_type)
                    # Found a date - record it
                    matches.append(DateMatch(
                        date_str=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        token_index=token_idx,
                        normalized_date=normalized
                    ))
                    break  # Take first matching pattern only

            token_idx += 1

        return matches

    def _split_tokens_with_dates(self, tokens: List[Token],
                                 date_matches: List[DateMatch]) -> List[Token]:
        """
        Split tokens where dates were found.

        Args:
            tokens: Original token list
            date_matches: List of dates found in tokens

        Returns:
            New token list with dates as separate tokens
        """
        new_tokens = []
        date_match_map = {dm.token_index: dm for dm in date_matches}

        # Track current token index (excluding path)
        token_idx = 0

        for token in tokens:
            # Always keep path tokens as-is
            if token.type == 'path':
                new_tokens.append(token)
                continue

            # Check if this token has a date
            if token_idx in date_match_map:
                date_match = date_match_map[token_idx]
                split_tokens = self._split_token_at_date(token, date_match)
                new_tokens.extend(split_tokens)
            else:
                # No date in this token
                new_tokens.append(token)

            token_idx += 1

        return new_tokens

    def _split_token_at_date(self, token: Token,
                            date_match: DateMatch) -> List[Token]:
        """
        Split a single token into parts around the date.

        Args:
            token: Token containing a date
            date_match: DateMatch with location info

        Returns:
            List of tokens (1-3 items: [before, date, after])
        """
        value = token.value
        start = date_match.start
        end = date_match.end
        date_str = date_match.date_str

        result = []

        # Text before date
        if start > 0:
            before = value[:start].strip()
            if before:
                result.append(Token(
                    value=before,
                    type=token.type,
                    position=token.position
                ))

        # Date itself
        normalized_value = date_match.normalized_date or date_str
        result.append(Token(
            value=normalized_value,
            type='date',
            position=token.position + start
        ))

        # Text after date
        if end < len(value):
            after = value[end:].strip()
            if after:
                result.append(Token(
                    value=after,
                    type=token.type,
                    position=token.position + end
                ))

        return result

    def _normalize_date(self, match: re.Match, pattern_type: str) -> Optional[str]:
        """
        Convert a matched date into ISO 8601 (YYYY-MM-DD) when possible.

        Args:
            match: Regex match containing date components
            pattern_type: Identifier for pattern shape (e.g., iso, us_date)

        Returns:
            ISO 8601 formatted string or None if normalization fails
        """
        try:
            if pattern_type in {'iso', 'compact'}:
                year = match.group('year')
                month = match.group('month')
                day = match.group('day')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

            if pattern_type in {'us_date'}:
                year = match.group('year')
                month = match.group('month')
                day = match.group('day')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

            if pattern_type in {'day_month_year'}:
                year = match.group('year')
                month = self._month_name_to_number(match.group('month_name'))
                day = match.group('day')
                if month:
                    return f"{year}-{month}-{day.zfill(2)}"
                return None

            if pattern_type in {'parenthesized_month_day_year', 'month_day_year'}:
                year = match.group('year')
                month = self._month_name_to_number(match.group('month_name'))
                day = match.group('day')
                if month:
                    return f"{year}-{month}-{day.zfill(2)}"
                return None

            if pattern_type == 'compact_month_name':
                year = match.group('year')
                month = self._month_name_to_number(match.group('month_name'))
                day = match.group('day')
                if month:
                    return f"{year}-{month}-{day.zfill(2)}"
                return None

            if pattern_type == 'year':
                return match.group('year')
        except (IndexError, KeyError, AttributeError):
            return None

        return None

    def _month_name_to_number(self, month_name: Optional[str]) -> Optional[str]:
        """Map textual month to two-digit month number."""
        if not month_name:
            return None
        key = month_name.strip().lower()
        month_num = self.month_names.get(key)
        if month_num:
            return month_num.zfill(2)
        return None

    def _update_pattern(self, pattern: Optional[str], date_matches: List[DateMatch],
                       original_tokens: List[Token]) -> Optional[str]:
        """
        Update pattern to reflect date extraction and token renumbering.

        The date displays as {date} but occupies a token slot. When a token
        splits, all subsequent tokens shift by the number of tokens added.

        Args:
            pattern: Original pattern string
            date_matches: List of dates found
            original_tokens: Original token list

        Returns:
            Updated pattern string
        """
        if not pattern or not date_matches:
            return pattern

        # Build a map of how tokens should be replaced
        token_replacements = {}

        # Track cumulative shift in token numbers
        shift = 0

        # Get count of non-path tokens
        non_path_count = sum(1 for t in original_tokens if t.type != 'path')

        for token_idx in range(non_path_count):
            # Check if this token has a date
            date_match = next((dm for dm in date_matches if dm.token_index == token_idx), None)

            if date_match:
                # This token contains a date
                value = original_tokens[token_idx + (1 if any(t.type == 'path' for t in original_tokens) else 0)].value
                start = date_match.start
                end = date_match.end

                has_before = start > 0 and value[:start].strip()
                has_after = end < len(value) and value[end:].strip()

                if has_before and has_after:
                    # Date in middle: "Happy20200101times" → {token0} {date} {token2}
                    token_replacements[token_idx] = f'{{token{token_idx + shift}}} {{date}} {{token{token_idx + shift + 2}}}'
                    shift += 2  # Original token becomes 3 tokens, net +2
                elif has_before:
                    # Date at end: "Happy 20200101" → {token0} {date}
                    token_replacements[token_idx] = f'{{token{token_idx + shift}}} {{date}}'
                    shift += 1  # Original token becomes 2 tokens, net +1
                elif has_after:
                    # Date at start: "20200101 Happy" → {date} {token1}
                    token_replacements[token_idx] = f'{{date}} {{token{token_idx + shift + 1}}}'
                    shift += 1  # Original token becomes 2 tokens, net +1
                else:
                    # Entire token is date: "20200101" → {date}
                    token_replacements[token_idx] = '{date}'
                    # No shift (still 1 token)
            else:
                # No date in this token - renumber with accumulated shift
                token_replacements[token_idx] = f'{{token{token_idx + shift}}}'

        # Apply replacements (highest to lowest to avoid conflicts)
        result = pattern
        for old_idx in sorted(token_replacements.keys(), reverse=True):
            old_placeholder = f'{{token{old_idx}}}'
            new_placeholder = token_replacements[old_idx]
            result = result.replace(old_placeholder, new_placeholder)

        return result


if __name__ == '__main__':
    # Test the date extractor
    from .tokenizer import Tokenizer

    tokenizer = Tokenizer()
    extractor = DateExtractor()

    test_cases = [
        "20200101 Happy times",
        "[Studio] Movie 20201225",
        "2020-01-01 Scene Name",
        "Scene Name 2020.12.25",
        "[20200101] Title",
        "January 15, 2020 Scene",
        "Scene (Dec 25, 2020)",
    ]

    print("Date Extraction Tests")
    print("=" * 60)

    for test in test_cases:
        result = tokenizer.tokenize(test)
        print(f"\nInput:   {test}")
        tokens_before = result.tokens or []
        print(f"Before:  {result.pattern}")
        print(f"Tokens:  {[t.value for t in tokens_before if t.type != 'path']}")

        result = extractor.process(result)
        tokens_after = result.tokens or []
        print(f"After:   {result.pattern}")
        print(f"Tokens:  {[(t.value, t.type) for t in tokens_after if t.type != 'path']}")
