#!/usr/bin/env python3
"""
Performer matcher module for identifying and marking performer tokens in filenames.

Identifies tokens that match performer name patterns, typically two words connected
by "and" or "&" followed by two more words. Uses dictionary checks to filter out
non-performer tokens.
"""

import re
import json
import os
from typing import Dict, List, Optional, Set, Tuple
from .tokenizer import TokenizationResult, Token


class PerformerMatcher:
    """Matches tokens against performer name patterns."""
    
    # Path to parser dictionary relative to this file
    DICTIONARY_PATH = os.path.join(os.path.dirname(__file__), "..", "dictionaries", "parser-dictionary.json")
    
    def __init__(self):
        """Initialize performer matcher with non-performer words."""
        self.non_performer_words: Set[str] = set()
        self._load_non_performer_words()
    
    def _load_non_performer_words(self) -> None:
        """Load words that indicate a token is not a performer list."""
        try:
            with open(self.DICTIONARY_PATH, 'r', encoding='utf-8') as f:
                dictionary = json.load(f)
                non_performer = dictionary.get('non_performer_words', [])
                self.non_performer_words = set(word.lower() for word in non_performer)
        except (FileNotFoundError, json.JSONDecodeError):
            # Default set of common non-performer words if dictionary not available
            self.non_performer_words = {
                'scene', 'movie', 'video', 'clip', 'episode', 'part', 'series',
                'collection', 'compilation', 'best', 'of', 'the', 'in', 'on',
                'at', 'to', 'from', 'with', 'for', 'by', 'de', 'la', 'el',
                'les', 'des', 'et', 'und', 'en', 'y', 'e', 'vs', 'versus',
                'presents', 'features', 'starring', 'with', 'and', 'friends'
            }
    
    def process(self, result: TokenizationResult) -> TokenizationResult:
        """
        Process tokenization result to identify and mark performer tokens.
        
        For each unclaimed token, checks if it matches a performer name pattern.
        When a match is found, the token type is changed to 'performers' and
        the pattern is updated.
        
        Args:
            result: TokenizationResult to process
            
        Returns:
            Modified TokenizationResult with performer tokens marked
        """
        if not result.tokens or not result.pattern:
            return result
        
        # Track which tokens are performers
        performer_matches: Dict[int, str] = {}  # token_index -> original_value
        
        for i, token in enumerate(result.tokens):
            # Skip path tokens and already identified tokens
            if token.type in ['path', 'studio', 'studio_code', 'date']:
                continue

            normalized_value = self._normalize_performer_list(token.value)
            # Check if token matches performer pattern using normalized value
            if self._is_performer_pattern(normalized_value, original_token=token.value):
                performer_matches[i] = normalized_value
        
        # If we found performer matches, update tokens and pattern
        if performer_matches:
            result = self._update_tokens_and_pattern(result, performer_matches)
        
        return result
    
    def _normalize_performer_list(self, token_value: str) -> str:
        """
        Normalize performer list separators to a consistent comma-and-space format.
        """
        value = token_value.strip()
        # Replace "and" (any casing) with comma separator
        value = re.sub(r'\s+(?:and)\s+', ', ', value, flags=re.IGNORECASE)
        # Replace ampersand with comma separator
        value = re.sub(r'\s*&\s*', ', ', value)
        # Ensure single comma with single space on either side where appropriate
        value = re.sub(r'\s*,\s*', ', ', value)
        # Collapse multiple spaces
        value = re.sub(r'\s+', ' ', value)
        # Remove leading/trailing commas and spaces
        value = value.strip(' ,')
        return value
    
    def _is_performer_pattern(self, token_value: str, original_token: Optional[str] = None) -> bool:
        """
        Check if a token value matches any performer name pattern.
        
        Supports various formats:
        - "John Smith & Jane Doe"
        - "John Smith and Jane Doe"
        - "John Smith, Jane Doe"
        - "John, Jane and Bob"
        - "John, Jane & Bob"
        - "John, Jane, Bob and Alice"
        - "John, Jane, Bob, Alice & Tom"
        - Single-word names: "John, Jane and Bob"
        - No spaces after commas: "John,Jane and Bob"
        
        Args:
            token_value: The token value to check
            
        Returns:
            True if the token matches any performer pattern, False otherwise
        """
        # Normalize the token value (strip but keep case for capitalization check)
        value = token_value.strip()
        original_for_validation = original_token if original_token is not None else token_value
        
        # Define patterns in order of specificity (most complex first)
        patterns = [
            # Multiple performers with commas and final "and"
            (r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)(?:\s*,\s*[a-zA-Z]+(?:\s+[a-zA-Z]+)?)*\s+and\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)$', 'and'),
            # Multiple performers with commas and final "&"
            (r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)(?:\s*,\s*[a-zA-Z]+(?:\s+[a-zA-Z]+)?)*\s*&\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)?)$', '&'),
            # Multiple performers with only commas
            (r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)(?:\s*,\s*[a-zA-Z]+(?:\s+[a-zA-Z]+)?)+$', 'comma'),
            # Two performers with "and"
            (r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s+and\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)$', 'and'),
            # Two performers with "&"
            (r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s*&\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)?)$', '&'),
            # Two performers with comma
            (r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s*,\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)?)$', 'comma'),
        ]
        
        # Try each pattern
        for pattern, separator_type in patterns:
            match = re.match(pattern, value, re.IGNORECASE)
            if match:
                # Extract performer names
                performer_names = self._extract_performer_names(match, separator_type, value)
                
                # Validate names
                if self._validate_performer_names(performer_names, original_for_validation):
                    return True
        
        return False
    
    def _extract_performer_names(self, match, separator_type: str, original_value: str) -> List[str]:
        """
        Extract all performer names from a regex match.
        
        Args:
            match: The regex match object
            separator_type: Type of separator ('and', '&', 'comma')
            original_value: Original token value for parsing
            
        Returns:
            List of performer names
        """
        names = []
        
        if separator_type in ['and', '&']:
            # For patterns with final separator, we need to parse the original value
            # to get all names, not just the captured groups
            
            # Check if this is a pattern with commas and final "and" or "&"
            if ',' in original_value:
                # Split on the final "and" or "&" to separate the last name
                parts = re.split(r'\s+(?:and|&)\s+', original_value, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    # First part may contain comma-separated names
                    first_part_names = [name.strip() for name in re.split(r',\s*', parts[0]) if name.strip()]
                    # Second part is the final name
                    final_name = parts[1].strip()
                    names.extend(first_part_names)
                    names.append(final_name)
            else:
                # Simple two-name pattern with "and" or "&"
                # Split on "and" or "&"
                parts = re.split(r'\s+(?:and|&)\s+', original_value, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    # First name and second name
                    first_name = parts[0].strip()
                    second_name = parts[1].strip()
                    names.extend([first_name, second_name])
        else:  # comma
            # For comma-separated, parse all names
            names = [name.strip() for name in re.split(r',\s*', original_value) if name.strip()]
        
        return names
    
    def _validate_performer_names(self, names: List[str], original_token: str) -> bool:
        """
        Validate extracted performer names.
        
        Args:
            names: List of performer names to validate
            original_token: Original token value for capitalization check
            
        Returns:
            True if all names appear to be valid performer names
        """
        # Check if we have at least 2 names
        if len(names) < 2:
            return False
        
        # Split each name into individual words for validation
        all_words = []
        for name in names:
            words = name.split()
            all_words.extend(words)
        
        # Check if any words are in the non-performer dictionary
        for word in all_words:
            if word.lower() in self.non_performer_words:
                return False
        
        # Additional checks to increase confidence
        # Check if words have reasonable length (names are typically 2-20 characters)
        for word in all_words:
            if len(word) < 2 or len(word) > 20:
                return False
        
        # Check capitalization (at least some names should be capitalized)
        original_words = original_token.strip().split()
        capitalized_count = sum(1 for word in original_words if word.istitle() and word not in ['and', '&'])
        
        # If at least half of the name-like words are capitalized, we're confident
        # For very short lists (2-3 names), require at least 1 capitalized
        min_capitalized = max(1, len(names) // 2)
        if capitalized_count >= min_capitalized:
            return True
        
        # If no capitalization but all other checks pass, still accept
        return True
    
    def _update_tokens_and_pattern(
        self,
        result: TokenizationResult,
        performer_matches: Dict[int, str]
    ) -> TokenizationResult:
        """
        Update token types and pattern to mark performer matches.
        
        Args:
            result: Original TokenizationResult
            performer_matches: Mapping of token index to original value
            
        Returns:
            New TokenizationResult with updated tokens and pattern
        """
        # Create new tokens list with performer matches marked
        new_tokens = []
        real_token_index = 0  # Counter for non-path tokens
        
        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                new_tokens.append(token)
                continue
            
            if i in performer_matches:
                # Replace with performers token
                new_tokens.append(Token(
                    value=performer_matches[i],
                    type='performers',
                    position=token.position
                ))
            else:
                new_tokens.append(token)
            real_token_index += 1
        
        # Rebuild pattern with performer replacements
        new_pattern = self._rebuild_pattern(result, performer_matches)
        
        # Return new result with updated tokens and pattern
        return TokenizationResult(
            original=result.original,
            cleaned=result.cleaned,
            pattern=new_pattern,
            tokens=new_tokens,
            studio=result.studio
        )
    
    def _rebuild_pattern(
        self,
        result: TokenizationResult,
        performer_matches: Dict[int, str]
    ) -> str:
        """
        Rebuild the pattern, replacing {tokenN} with {performers} for performer matches.
        
        Args:
            result: Original TokenizationResult with original pattern
            performer_matches: Mapping of token index to original value
            
        Returns:
            Updated pattern string
        """
        pattern = result.pattern or ""
        if not pattern:
            return pattern
        
        # Build a mapping of {tokenN} to replacement for performer matches
        replacements = {}
        real_token_index = 0
        
        for i, token in enumerate(result.tokens or []):
            if token.type == 'path':
                continue
            
            if i in performer_matches:
                replacements[f"{{token{real_token_index}}}"] = "{performers}"
            
            real_token_index += 1
        
        # Apply replacements to pattern
        for old_pattern, new_pattern_part in replacements.items():
            pattern = pattern.replace(old_pattern, new_pattern_part)
        
        return pattern


if __name__ == '__main__':
    # Simple test
    matcher = PerformerMatcher()
    print(f"Loaded {len(matcher.non_performer_words)} non-performer words")
    
    test_cases = [
        "John Doe & Jane Smith",
        "Tom Brown and Mary Jones",
        "Actor Name & Another Name",
        "Movie Scene & Video Clip",  # Should not match (contains non-performer words)
        "One Two & Three Four",
        "A B & C D"
    ]
    
    for test in test_cases:
        is_match = matcher._is_performer_pattern(test)
        print(f"'{test}': {'MATCH' if is_match else 'NO MATCH'}")
