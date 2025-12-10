#!/usr/bin/env python3
"""
Filename parser for adult film scenes with early removal token processing.
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from modules import (
    PreTokenizer,
    PreTokenizationResult,
    Tokenizer,
    TokenizationResult,
    DateExtractor
)


class FilenameParser:
    """Parser for extracting metadata from adult film filenames."""

    def __init__(self):
        self.pre_tokenizer = PreTokenizer()
        self.tokenizer = Tokenizer()
        self.date_extractor = DateExtractor()

    def pre_tokenize(self, filename: str) -> PreTokenizationResult:
        """Process filename before tokenization by removing early removal tokens."""
        return self.pre_tokenizer.process(filename)

    def tokenize(self, pre_result: PreTokenizationResult) -> TokenizationResult:
        """Process pre-tokenization result to extract tokens and pattern."""
        # Use the tokenizer to process the cleaned string
        return self.tokenizer.tokenize(
            cleaned=pre_result.cleaned,
            original=pre_result.original
        )

    def extract_dates(self, token_result: TokenizationResult) -> TokenizationResult:
        """Extract dates from tokens and renumber."""
        return self.date_extractor.process(token_result)

    def parse(self, filename: str) -> TokenizationResult:
        """
        Full parsing pipeline: pre-tokenize → tokenize → extract dates.

        Args:
            filename: Filename to parse

        Returns:
            TokenizationResult with dates extracted
        """
        # Step 1: Pre-tokenization (remove quality markers, extensions, etc.)
        pre_result = self.pre_tokenize(filename)

        # Step 2: Tokenization (extract tokens and pattern)
        token_result = self.tokenize(pre_result)

        # Step 3: Date extraction (extract dates and renumber tokens)
        final_result = self.extract_dates(token_result)

        return final_result



if __name__ == '__main__':
    pass
