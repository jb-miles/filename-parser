#!/usr/bin/env python3
"""
Filename parser for adult film scenes with early removal token processing.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
try:
    from .modules import (
        PreTokenizer,
        PreTokenizationResult,
        Tokenizer,
        TokenizationResult,
        Token,
        DateExtractor,
        StudioMatcher,
        StudioCodeFinder,
        PerformerMatcher,
        SequenceExtractor,
        TitleExtractor,
        # PathParser,  # Disabled - not working on paths yet
        # PathParseResult,  # Disabled - not working on paths yet
        # PathFilenameResolver  # Disabled - not working on paths yet
    )
    from .modules.dictionary_loader import DictionaryLoader
except ImportError:
    from modules import (
        PreTokenizer,
        PreTokenizationResult,
        Tokenizer,
        TokenizationResult,
        Token,
        DateExtractor,
        StudioMatcher,
        StudioCodeFinder,
        PerformerMatcher,
        SequenceExtractor,
        TitleExtractor,
        # PathParser,  # Disabled - not working on paths yet
        # PathParseResult,  # Disabled - not working on paths yet
        # PathFilenameResolver  # Disabled - not working on paths yet
    )
    from modules.dictionary_loader import DictionaryLoader


class FilenameParser:
    """Parser for extracting metadata from adult film filenames."""

    def __init__(self):
        # Preload all dictionaries into cache to avoid redundant file I/O
        # across multiple modules. Modules will use cached versions.
        DictionaryLoader.preload_all()

        self.pre_tokenizer = PreTokenizer()
        # self.path_parser = PathParser()  # Disabled - not working on paths yet
        self.tokenizer = Tokenizer()
        self.date_extractor = DateExtractor()
        self.studio_matcher = StudioMatcher()
        self.studio_code_finder = StudioCodeFinder()
        self.performer_matcher = PerformerMatcher()
        self.sequence_extractor = SequenceExtractor()
        self.title_extractor = TitleExtractor()
        # self.resolver = PathFilenameResolver()  # Disabled - not working on paths yet

    def pre_tokenize(self, filename: Union[str, Path]) -> PreTokenizationResult:
        """Process basename (stem) before tokenization by removing early removal tokens."""
        return self.pre_tokenizer.process(str(filename))

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

    def match_studios(self, token_result: TokenizationResult) -> TokenizationResult:
        """Match tokens against known studios and mark studio tokens."""
        return self.studio_matcher.process(token_result)

    def match_studios_dash_fallback(self, token_result: TokenizationResult) -> TokenizationResult:
        """Fallback studio matching for tokens with internal dashes."""
        return self.studio_matcher.process_dash_fallback(token_result)

    def match_studios_partial_fallback(self, token_result: TokenizationResult) -> TokenizationResult:
        """Fallback studio matching for partial/substring matches within tokens."""
        return self.studio_matcher.process_partial_match_fallback(token_result)

    def find_studio_codes(self, token_result: TokenizationResult) -> TokenizationResult:
        """Find and mark studio codes in tokens."""
        return self.studio_code_finder.process(token_result)
    
    def match_performers(self, token_result: TokenizationResult) -> TokenizationResult:
        """Match tokens against performer name patterns and mark performer tokens."""
        return self.performer_matcher.process(token_result)

    def extract_sequences(self, token_result: TokenizationResult) -> TokenizationResult:
        """Extract sequence information (part, scene, episode, volume) and group."""
        return self.sequence_extractor.process(token_result)

    def extract_title(self, token_result: TokenizationResult) -> TokenizationResult:
        """Extract title from remaining unlabeled tokens."""
        return self.title_extractor.process(token_result)

    def parse(self, filename: Union[str, Path]) -> TokenizationResult:
        """
        Full parsing pipeline.

        Pipeline order:
        1. Pre-tokenize (remove quality markers, extensions, etc.)
        2. Tokenize (extract tokens and pattern)
        3. Extract dates
        4. Match studios
        4.5. Match studios (dash fallback) - only if no studio found yet
        4.75. Match studios (partial fallback) - only if no studio found yet
        5. Find studio codes
        6. Match performers
        7. Extract sequences and group (must come before title)
        8. Extract title (comes last, uses leftovers)

        Args:
            filename: Filename (stem only, no paths) to parse

        Returns:
            TokenizationResult with all fields extracted
        """
        # Extract stem from Path object if needed
        path_obj = Path(filename)
        stem = path_obj.stem

        # PATH PROCESSING DISABLED - Not working on paths yet
        # # Normalize path input and split into parent + stem
        # path_obj = Path(filename)
        # parent_str = None if str(path_obj.parent) in ("", ".") else path_obj.parent.as_posix()
        #
        # # Parse path independently (parent dirs only)
        # path_result: PathParseResult = self.path_parser.parse(parent_str)

        # Step 1: Pre-tokenization on stem only (remove quality markers, extensions, etc.)
        pre_result = self.pre_tokenize(stem)

        # Step 2: Tokenization (extract tokens and pattern)
        token_result = self.tokenize(pre_result)

        # PATH PROCESSING DISABLED - Not working on paths yet
        # # Attach normalized path token up front so downstream modules can skip path safely
        # if path_result.path:
        #     path_token = Token(value=path_result.path, type='path', position=0)
        #     token_result.tokens = [path_token] + (token_result.tokens or [])

        # Preserve original input for traceability
        token_result.original = pre_result.original

        # Step 3: Date extraction (extract dates and renumber tokens)
        final_result = self.extract_dates(token_result)

        # Step 4: Studio matching (identify and mark studio tokens)
        final_result = self.match_studios(final_result)

        # Step 4.5: Studio matching with dash fallback (only if no studio found yet)
        final_result = self.match_studios_dash_fallback(final_result)

        # Step 4.75: Studio matching with partial fallback (only if no studio found yet)
        final_result = self.match_studios_partial_fallback(final_result)

        # Step 5: Studio code finding (identify and mark studio code tokens)
        final_result = self.find_studio_codes(final_result)

        # Step 6: Performer matching (identify and mark performer tokens)
        final_result = self.match_performers(final_result)

        # Step 7: Sequence extraction (identify part/scene/episode/volume and extract group)
        final_result = self.extract_sequences(final_result)

        # Step 8: Title extraction (extract from remaining unlabeled tokens)
        final_result = self.extract_title(final_result)

        # PATH PROCESSING DISABLED - Not working on paths yet
        # # Step 9: Resolve path vs filename signals (telemetry + fallback)
        # final_result = self.resolver.resolve(final_result, path_result)

        return final_result



if __name__ == '__main__':
    pass
