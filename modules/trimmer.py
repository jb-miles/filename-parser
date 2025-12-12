#!/usr/bin/env python3
"""
Trimmer module for cleaning strings by removing unwanted patterns.
Can be used by both pre_tokenizer and tokenizer.
"""

import json
from typing import List, Optional
from .dictionary_loader import DictionaryLoader


class Trimmer:
    """Trims unwanted patterns from the beginning and end of strings."""

    def __init__(self, dictionary_path: Optional[str] = None):
        """Initialize trimmer with trimming patterns from dictionary.

        Args:
            dictionary_path: Optional path to dictionary file. If None, uses DictionaryLoader.
        """
        self.dictionary_path = dictionary_path
        self.trimming_strings = []
        self._load_trimming_strings()

    def _load_trimming_strings(self):
        """Load trimming strings from parser dictionary."""
        # If custom path provided, use legacy loading
        if self.dictionary_path:
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            for encoding in encodings:
                try:
                    with open(self.dictionary_path, 'r', encoding=encoding) as f:
                        config = json.load(f)
                        self.trimming_strings = config.get('trimming_strings', [])
                        return
                except (UnicodeDecodeError, json.JSONDecodeError, FileNotFoundError):
                    continue
            self.trimming_strings = []
        else:
            # Use DictionaryLoader for default path
            self.trimming_strings = DictionaryLoader.get_section('trimming_strings') or []

    def trim(self, text: str) -> str:
        """
        Trim unwanted patterns from the beginning and end of a string.

        Iteratively removes patterns from trimming_strings until no more
        changes occur. This handles nested patterns like "- - -" -> "-" -> "".

        Args:
            text: String to trim

        Returns:
            Trimmed string

        Example:
            >>> trimmer = Trimmer()
            >>> trimmer.trim("- Studio -")
            "Studio"
            >>> trimmer.trim("___Text___")
            "Text"
            >>> trimmer.trim("...Name...")
            "Name"
        """
        if not text:
            return text

        trimmed = text

        # Keep trimming until no more changes are made
        changed = True
        while changed:
            changed = False

            # Apply trimming from the beginning
            for trim_str in self.trimming_strings:
                if trimmed.startswith(trim_str):
                    trimmed = trimmed[len(trim_str):]
                    changed = True

            # Apply trimming from the end
            for trim_str in self.trimming_strings:
                if trimmed.endswith(trim_str):
                    trimmed = trimmed[:-len(trim_str)]
                    changed = True

        return trimmed

    def trim_all(self, strings: List[str]) -> List[str]:
        """
        Trim multiple strings.

        Args:
            strings: List of strings to trim

        Returns:
            List of trimmed strings

        Example:
            >>> trimmer = Trimmer()
            >>> trimmer.trim_all(["- A -", "- B -", "- C -"])
            ["A", "B", "C"]
        """
        return [self.trim(s) for s in strings]


if __name__ == '__main__':
    # Test the trimmer
    trimmer = Trimmer()

    test_cases = [
        "- Studio -",
        "___Text___",
        "...Name...",
        "- - -Title- - -",
        "Normal",
        "  Spaces  ",
        "()",
        "[]",
        ".- Combo -.",
    ]

    print("Trimmer Test Cases\n" + "="*50)
    for test in test_cases:
        result = trimmer.trim(test)
        print(f'"{test}" → "{result}"')
