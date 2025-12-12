#!/usr/bin/env python3
"""
Title extractor module for extracting meaningful titles from unlabeled tokens.

The title is what's leftover after all other parsing is done, if there's anything left.
It must be meaningful data - at least one proper word. Numbers, alphanumeric strings,
or symbols alone don't cut it, but words will.

Also extracts trailing numbers as "title number" sequence indicators.
"""

import re
from typing import Optional, Tuple
from .tokenizer import TokenizationResult


class TitleExtractor:
    """Extractor for titles from unlabeled tokens."""

    def is_meaningful_title(self, text: str) -> bool:
        """
        Check if text contains at least one proper word (not just numbers/symbols).

        A meaningful title must have at least one word with 2+ letters.

        Args:
            text: Text to check

        Returns:
            True if text contains meaningful words
        """
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
        return len(words) > 0

    def extract_title_number(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Extract trailing number from title if present.

        Returns (cleaned_title, number) or (original_title, None)

        Args:
            text: Title text to process

        Returns:
            Tuple of (cleaned title, title number or None)
        """
        # Look for a loose number at the end: "Some Title 3" -> ("Some Title", 3)
        match = re.search(r'^(.+?)\s+(\d+)$', text.strip())
        if match:
            title_part = match.group(1).strip()
            number = int(match.group(2))
            # Make sure the title part is still meaningful
            if self.is_meaningful_title(title_part):
                return (title_part, number)

        return (text, None)

    def process(self, result: TokenizationResult) -> TokenizationResult:
        """
        Extract title from unlabeled tokens.

        Collects all tokens that haven't been labeled by other extractors,
        combines them, validates they're meaningful, and optionally extracts
        a trailing number as a title sequence indicator.

        Args:
            result: TokenizationResult from previous processing

        Returns:
            Updated TokenizationResult with title and possibly title number in sequence
        """
        if not result.tokens:
            return result

        # Collect unlabeled tokens (excluding path)
        unlabeled_tokens = []
        labeled_types = {'path', 'date', 'studio', 'studio_code', 'performers', 'sequence'}

        for token in result.tokens:
            if token.type not in labeled_types and token.value.strip():
                unlabeled_tokens.append(token.value)

        # Extract title from unlabeled tokens
        if unlabeled_tokens:
            # Join unlabeled tokens to form potential title
            potential_title = ' '.join(unlabeled_tokens)

            # Check if it's meaningful
            if self.is_meaningful_title(potential_title):
                # Try to extract trailing number
                cleaned_title, title_num = self.extract_title_number(potential_title)

                # Store title
                result.title = cleaned_title

                # If we found a title number, add it to sequence
                if title_num is not None:
                    if result.sequence is None:
                        result.sequence = {}
                    result.sequence['title'] = title_num

                # Mark tokens as title type
                for token in result.tokens:
                    if token.type not in labeled_types and token.value.strip():
                        token.type = 'title'

        return result
