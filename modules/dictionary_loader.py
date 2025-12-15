#!/usr/bin/env python3
"""
Dictionary loader utility for centralized dictionary loading and caching.

Provides a single point of access for loading parser dictionaries with
error handling and optional caching to avoid redundant file reads.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class DictionaryLoader:
    """Centralized dictionary loader with caching support."""

    # Cache for loaded dictionaries to avoid redundant file reads
    _cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def get_dictionary_path(dictionary_name: str = "parser-dictionary.json") -> Path:
        """
        Get the absolute path to a dictionary file.

        Args:
            dictionary_name: Name of the dictionary file

        Returns:
            Absolute path to the dictionary file
        """
        return Path(__file__).resolve().parent.parent / "dictionaries" / dictionary_name

    @classmethod
    def load_dictionary(
        cls,
        dictionary_name: str = "parser-dictionary.json",
        use_cache: bool = True
    ) -> Optional[Any]:
        """
        Load a dictionary from the dictionaries folder.

        Args:
            dictionary_name: Name of the dictionary file to load
            use_cache: Whether to use cached version if available

        Returns:
            Dictionary contents (can be dict, list, or other JSON types), or None if loading fails
        """
        # Check cache first if caching is enabled
        if use_cache and dictionary_name in cls._cache:
            return cls._cache[dictionary_name]

        dictionary_path = cls.get_dictionary_path(dictionary_name)

        try:
            with open(dictionary_path, 'r', encoding='utf-8') as f:
                dictionary = json.load(f)

            # Cache the result if caching is enabled
            if use_cache:
                cls._cache[dictionary_name] = dictionary

            return dictionary

        except (FileNotFoundError, json.JSONDecodeError, IOError):
            return None

    @classmethod
    def get_section(
        cls,
        section_name: str,
        dictionary_name: str = "parser-dictionary.json",
        use_cache: bool = True
    ) -> Any:
        """
        Load a specific section from a dictionary.

        Args:
            section_name: Name of the section to retrieve (e.g., 'studio_codes')
            dictionary_name: Name of the dictionary file
            use_cache: Whether to use cached version if available

        Returns:
            The requested section, or None/empty list if not found
        """
        dictionary = cls.load_dictionary(dictionary_name, use_cache)
        if dictionary is None:
            return None

        return dictionary.get(section_name)

    @classmethod
    def clear_cache(cls, dictionary_name: Optional[str] = None) -> None:
        """
        Clear the dictionary cache.

        Args:
            dictionary_name: Specific dictionary to clear, or None to clear all
        """
        if dictionary_name:
            cls._cache.pop(dictionary_name, None)
        else:
            cls._cache.clear()

    @classmethod
    def preload_all(cls) -> None:
        """
        Preload all dictionaries into cache.

        This is useful when running the full parser pipeline to avoid
        redundant file I/O. When modules are run standalone, they will
        still load dictionaries on-demand if not already cached.
        """
        # List of all dictionaries used by the parser
        dictionaries = [
            "parser-dictionary.json",  # Used by tokenizer, pre_tokenizer, performer_matcher, trimmer, studio_code_finder
            "studios.json",             # Used by studio_matcher
            "studio_aliases.json",      # Used by studio_matcher for normalization
            "performer_aliases.json",   # Used by performer_matcher (future)
            "date_formats.json"         # Used by date_extractor
        ]

        for dictionary_name in dictionaries:
            # Load each dictionary (will be cached automatically)
            cls.load_dictionary(dictionary_name, use_cache=True)
