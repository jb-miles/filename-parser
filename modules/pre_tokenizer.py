#!/usr/bin/env python3
"""
Pre-tokenization module for filename processing.
Handles early removal of tokens from filenames.
"""

import re
import json
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from .trimmer import Trimmer
from .dictionary_loader import DictionaryLoader


@dataclass
class RemovedToken:
    """Represents a token that was removed from the filename."""
    value: str
    category: str
    position: int
    confidence: float


@dataclass
class PreTokenizationResult:
    """Result of pre-tokenization processing on a filename."""
    original: str
    cleaned: str
    removed_tokens: List[RemovedToken]
    
    def to_json(self) -> str:
        """Convert result to JSON format."""
        removed_tokens_data = [
            {
                "value": token.value,
                "category": token.category,
                "position": token.position,
                "confidence": token.confidence
            }
            for token in self.removed_tokens
        ]
        
        json_data = {
            "original": self.original,
            "cleaned": self.cleaned,
            "removed_tokens": removed_tokens_data
        }
        return json.dumps(json_data)


@dataclass
class EarlyRemovalCategory:
    """Defines a category of tokens to remove during pre-tokenization."""
    name: str
    description: str
    pattern: re.Pattern
    position: str  # "end", "start", "anywhere", "before_extension"
    confidence: float
    semantic_role: str  # "technical", "quality", "source", "category", "format"


class PreTokenizer:
    """Pre-tokenizer for extracting metadata from adult film filenames."""

    def __init__(self, dictionary_path: Optional[str] = None):
        # If no path provided, Trimmer will use its default path
        self.trimmer = Trimmer(dictionary_path)
        config = DictionaryLoader.load_dictionary('parser-dictionary.json') or {}
        self.extensions = [ext.lower() for ext in config.get('extensions', [])]
        self.early_removal_categories = self._default_early_removal_categories()

    def process(self, filename: str) -> PreTokenizationResult:
        """Process filename by removing early removal tokens."""
        path_obj = Path(filename)
        basename = path_obj.name

        result = PreTokenizationResult(
            original=filename,
            cleaned=basename,
            removed_tokens=[]
        )

        # Step 1: Process categories in order of confidence (highest first)
        for category in sorted(self.early_removal_categories, key=lambda c: c.confidence, reverse=True):
            result = self._apply_category_removal(result, category)

        # Step 2: Apply trimming at the end
        result = self._apply_trimming(result)
        
        # Step 3: Replace defined strings with dash
        result = self._apply_string_replacement(result)
        
        # Step 4: Handle whitespace (underscores)
        result = self._apply_whitespace_handling(result)

        # Step 5: Strip a single known extension using pathlib (no removed token)
        result.cleaned = self._strip_known_extension(result.cleaned)

        # Final pass: trim leftover wrapping/punctuation after extension stripping
        result.cleaned = self.trimmer.trim(result.cleaned)

        return result

    def _apply_category_removal(self, result: PreTokenizationResult, category: EarlyRemovalCategory) -> PreTokenizationResult:
        """Apply a single early removal category."""
        cleaned = result.cleaned
        removed = []

        # Find all matches
        for match in category.pattern.finditer(cleaned):
            # Extract the quality marker (group 1 if it exists, else full match)
            if match.lastindex and match.lastindex >= 1:
                # Pattern has capture groups, use group 1
                start, end = match.span(1)
                value = match.group(1)
            else:
                # No capture groups, use full match
                start, end = match.span()
                value = match.group()

            # Record what we removed
            removed.append(RemovedToken(
                value=value,
                category=category.name,
                position=start,
                confidence=category.confidence
            ))

            # Remove the matched text
            cleaned = cleaned[:start] + cleaned[end:]

        # Update result
        result.cleaned = cleaned.strip()
        result.removed_tokens.extend(removed)
        return result

    def _apply_trimming(self, result: PreTokenizationResult) -> PreTokenizationResult:
        """Apply trimming to remove specified patterns from beginning and end using Trimmer."""
        result.cleaned = self.trimmer.trim(result.cleaned)
        return result

    def _apply_string_replacement(self, result: PreTokenizationResult) -> PreTokenizationResult:
        """Replace defined strings with dash, ensuring proper spacing only for newly added dashes."""
        # Normalize Unicode characters first
        cleaned = unicodedata.normalize('NFC', result.cleaned)
        
        # Replace common problematic characters
        replacements = {
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
            '\u2013': '-',  # En dash
            '\u2014': '--', # Em dash
            '\u2026': '...', # Horizontal ellipsis
            '\u00a0': ' ',  # Non-breaking space
            '\u200b': '',   # Zero-width space
            '\u200e': '',   # Left-to-right mark
            '\u200f': '',   # Right-to-left mark
        }
        
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)

        # Load replacement strings from config
        config = DictionaryLoader.load_dictionary('parser-dictionary.json') or {}
        replace_strings = config.get('replace_with_dash', [])
        
        # Replace each string with dash anywhere it appears
        for replace_str in replace_strings:
            # Escape special regex characters in the replacement string
            escaped_str = re.escape(replace_str)
            
            # Pattern to replace the string with dash anywhere it appears
            pattern = re.compile(escaped_str)
            
            # Replace all occurrences with a dash with proper spacing
            # We handle spacing here to avoid affecting pre-existing dashes
            cleaned = pattern.sub(' - ', cleaned)
        
        # Clean up any consecutive dashes that might have been created
        cleaned = re.sub(r'\s*-\s*-\s*', ' - ', cleaned)
        
        # Clean up any double spaces that might have been created
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        result.cleaned = cleaned
        return result

    def _apply_whitespace_handling(self, result: PreTokenizationResult) -> PreTokenizationResult:
        """Handle underscores by replacing with space or removing based on context."""
        cleaned = result.cleaned
        review_flag_added = False
        
        # Pattern to find underscores
        # We'll use a regex with lookahead and lookbehind to check for spaces
        # Pattern 1: Underscore with space on either side - just remove underscore and add review flag
        # Pattern 2: Underscore without adjacent spaces - replace with space
        
        # First, handle underscores with spaces on either side (remove them and add review flag)
        def remove_adjacent_underscore(match):
            nonlocal review_flag_added
            review_flag_added = True
            return ''  # Remove the underscore
        
        # Pattern for underscores with spaces on either side
        cleaned = re.sub(r'(?<=\s)_(?=\s)|(?<=\s)_|_(?=\s)', remove_adjacent_underscore, cleaned)
        
        # Then, handle underscores without adjacent spaces (replace with space)
        cleaned = re.sub(r'(?<!\s)_(?!\s)', ' ', cleaned)
        
        # Update result
        result.cleaned = cleaned
        
        # Add review flag if any underscores were removed (had adjacent spaces)
        if review_flag_added:
            # Add a removed token to indicate review flag
            result.removed_tokens.append(RemovedToken(
                value="REVIEW_FLAG",
                category="whitespace_handling",
                position=0,
                confidence=1.0
            ))
        
        return result

    def _strip_known_extension(self, text: str) -> str:
        """Remove the final suffix if it matches a known extension."""
        path_obj = Path(text)
        suffix = path_obj.suffix.lower().lstrip(".")
        if suffix and suffix in self.extensions:
            return path_obj.stem
        return text

    def _default_early_removal_categories(self) -> List[EarlyRemovalCategory]:
        """Define default early removal detection rules by loading from JSON config.

        Processing order:
        1. Resolution markers (remove 480p, 720p, etc. with touching rule)
        2. Quality markers (remove HQ, UHD, etc.)
        3. Source markers (remove DVD-rip, etc.)
        4. Format markers (remove 3D-SBS, etc.)
        5. Misc markers (remove original size, etc.)
        """

        categories = []

        # Load configuration from JSON file
        config = DictionaryLoader.load_dictionary('parser-dictionary.json') or {}

        # STEP 1: Resolution markers (remove only when NOT touching letters/numbers)
        resolution_markers = config.get('resolution_markers', [])

        for marker in resolution_markers:
            # Escape special regex characters
            escaped = re.escape(marker)

            # Pattern: (?<![a-zA-Z0-9])MARKER(?![a-zA-Z0-9])
            # Only match if NOT touching any letter or number on either side
            pattern = re.compile(rf'(?<![a-zA-Z0-9])({escaped})(?![a-zA-Z0-9])')

            categories.append(EarlyRemovalCategory(
                name=f"resolution_{marker}",
                description=f"Remove '{marker}' when not touching letters/numbers",
                pattern=pattern,
                position="anywhere",
                confidence=0.95,
                semantic_role="quality"
            ))

        # STEP 3: Quality markers (remove only when NOT touching letters/numbers)
        quality_markers = config.get('quality_markers', [])
        for marker in quality_markers:
            escaped = re.escape(marker)
            pattern = re.compile(rf'(?<![a-zA-Z0-9])({escaped})(?![a-zA-Z0-9])')
            categories.append(EarlyRemovalCategory(
                name=f"quality_{marker}",
                description=f"Remove '{marker}' when not touching letters/numbers",
                pattern=pattern,
                position="anywhere",
                confidence=0.9,
                semantic_role="quality"
            ))

        # STEP 4: Source markers (remove only when NOT touching letters/numbers)
        source_markers = config.get('source_markers', [])
        for marker in source_markers:
            escaped = re.escape(marker)
            pattern = re.compile(rf'(?<![a-zA-Z0-9])({escaped})(?![a-zA-Z0-9])')
            categories.append(EarlyRemovalCategory(
                name=f"source_{marker}",
                description=f"Remove '{marker}' when not touching letters/numbers",
                pattern=pattern,
                position="anywhere",
                confidence=0.85,
                semantic_role="source"
            ))

        # STEP 5: Format markers (remove only when NOT touching letters/numbers)
        format_markers = config.get('format_markers', [])
        for marker in format_markers:
            escaped = re.escape(marker)
            pattern = re.compile(rf'(?<![a-zA-Z0-9])({escaped})(?![a-zA-Z0-9])')
            categories.append(EarlyRemovalCategory(
                name=f"format_{marker}",
                description=f"Remove '{marker}' when not touching letters/numbers",
                pattern=pattern,
                position="anywhere",
                confidence=0.8,
                semantic_role="format"
            ))

        # STEP 6: Misc markers (remove only when NOT touching letters/numbers)
        misc_markers = config.get('misc_markers', [])
        for marker in misc_markers:
            escaped = re.escape(marker)
            pattern = re.compile(rf'(?<![a-zA-Z0-9])({escaped})(?![a-zA-Z0-9])')
            categories.append(EarlyRemovalCategory(
                name=f"misc_{marker}",
                description=f"Remove '{marker}' when not touching letters/numbers",
                pattern=pattern,
                position="anywhere",
                confidence=0.75,
                semantic_role="misc"
            ))

        return categories


if __name__ == '__main__':
    pass
