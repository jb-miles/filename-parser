#!/usr/bin/env python3
"""
Tokenizer module for extracting structured tokens from filenames.
Handles path extraction, bracket/parenthesis/curly content, and text
segments split on the literal " - " delimiter. Path portions are emitted
as a dedicated path token ahead of other tokens.
"""

import re
import json
import os
from dataclasses import dataclass
from typing import List, Optional
from .trimmer import Trimmer


@dataclass
class Token:
    """Represents a single token extracted from a filename."""
    value: str
    type: str  # 'path', 'bracket', 'parenthesis', 'curly', 'text'
    position: int  # Position in the original string


@dataclass
class TokenizationResult:
    """Result of tokenization processing on a filename."""
    original: str
    cleaned: str
    pattern: Optional[str] = None
    tokens: Optional[List[Token]] = None
    studio: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert result to JSON format."""
        tokens_data = [
            {
                "value": token.value,
                "type": token.type,
                "position": token.position
            }
            for token in (self.tokens or [])
        ]
        
        # Create token dictionary for easy access
        token_dict = {}
        real_idx = 0
        for token in (self.tokens or []):
            if token.type == 'path':
                token_dict["path"] = token.value
                continue
            token_dict[f"token{real_idx}"] = token.value
            real_idx += 1
        
        json_data = {
            "original": self.original,
            "cleaned": self.cleaned,
            "pattern": self.pattern,
            "tokens": tokens_data,
            **token_dict  # Include individual token fields
        }
        if self.studio:
            json_data["studio"] = self.studio
        return json.dumps(json_data)


class Tokenizer:
    """Tokenizer for extracting structured tokens from filenames."""

    # Hardcoded dictionary path relative to this file
    DICTIONARY_PATH = os.path.join(os.path.dirname(__file__), "..", "dictionaries", "parser-dictionary.json")

    def __init__(self):
        """Initialize tokenizer with parser dictionary."""
        self.trimmer = Trimmer()
        self.junk_tokens = []
        try:
            with open(self.DICTIONARY_PATH, 'r', encoding='utf-8') as f:
                dictionary = json.load(f)
                self.junk_tokens = dictionary.get('junk_tokens', [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def tokenize(self, original: str, cleaned: Optional[str] = None) -> TokenizationResult:
        """
        Tokenize a filename to extract structured tokens.
        First split out any content wrapped in brackets, parentheses, or
        curly braces. Then split remaining text segments on the literal
        " - " delimiter. Path information is emitted as a path token.

        After extraction, tokens matching junk_tokens are filtered out and
        labeled as {junk} in the pattern instead of being numbered.

        Args:
            original: The original filename (may include path)
            cleaned: The cleaned filename (optional, uses original if not provided)

        Returns:
            TokenizationResult with extracted tokens and pattern
        """
        # Use original as cleaned if not provided
        if cleaned is None:
            cleaned = original

        # Initialize result
        result = TokenizationResult(
            original=original,
            cleaned=cleaned,
            tokens=[]
        )

        # Step 1: Extract path if present
        filename, path, path_sep = self._extract_path(cleaned)
        path_token = None
        if path:
            path_token = Token(value=path, type='path', position=0)

        # Step 2: Extract all tokens from filename
        all_tokens = self._extract_tokens(filename)

        # Step 3: Mark which tokens are junk
        is_junk = [self._is_junk_token(token.value) for token in all_tokens]

        # Step 4: Generate pattern with {junk} for junk tokens and {tokenN} for real tokens
        pattern = self._generate_pattern(filename, is_junk, path, path_sep)
        result.pattern = pattern

        # Step 5: Filter out junk tokens from the final tokens list
        filtered_tokens = [token for i, token in enumerate(all_tokens) if not is_junk[i]]

        # Step 6: Apply trimming to each token value
        trimmed_tokens = [self._trim_token(token) for token in filtered_tokens]

        # Step 7: Ensure path token appears first if present
        if path_token:
            result.tokens = [path_token] + trimmed_tokens
        else:
            result.tokens = trimmed_tokens

        return result

    def _is_junk_token(self, token_value: str) -> bool:
        """
        Check if a token value is an exact match for a junk token.

        Args:
            token_value: The token value to check

        Returns:
            True if the token is junk, False otherwise
        """
        return token_value in self.junk_tokens

    def _trim_token(self, token: Token) -> Token:
        """
        Apply trimming to a token's value using the Trimmer.

        Args:
            token: Token to trim

        Returns:
            Token with trimmed value
        """
        trimmed_value = self.trimmer.trim(token.value)

        # Return new token with trimmed value
        return Token(
            value=trimmed_value,
            type=token.type,
            position=token.position
        )

    def _extract_path(self, filepath: str) -> tuple[str, Optional[str], Optional[str]]:
        """
        Extract path from filepath.
        
        Returns:
            Tuple of (filename, path, separator) where path/separator are None if not found
        """
        # Check for both forward and back slashes
        # Use the last occurrence to handle paths with mixed separators
        forward_slash_pos = filepath.rfind('/')
        backslash_pos = filepath.rfind('\\')
        
        # Find the rightmost separator
        last_sep = max(forward_slash_pos, backslash_pos)
        
        if last_sep != -1:
            # Path found
            path = filepath[:last_sep]
            filename = filepath[last_sep + 1:]
            sep = filepath[last_sep]
            return filename, path, sep
        else:
            # No path found
            return filepath, None, None
    
    def _extract_tokens(self, filename: str) -> List[Token]:
        """
        Extract tokens from filename in order.
        Bracket/parenthesis/brace content is lifted first, then any remaining
        text is split on dash delimiters that have at least one surrounding
        space (e.g., " -", "- ", or " - ").
        
        Args:
            filename: The filename without path
            
        Returns:
            List of tokens in order of appearance
        """
        tokens = []
        
        # Find bracket/parenthesis/brace segments, plus everything else
        segment_pattern = re.compile(r'\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|[^{}\[\]\(\)]+')
        
        for match in segment_pattern.finditer(filename):
            segment = match.group()
            segment_start = match.start()
            
            if segment.startswith('[') and segment.endswith(']'):
                inner = segment[1:-1]
                inner_stripped = inner.strip()
                if inner_stripped:
                    leading_ws = len(inner) - len(inner.lstrip())
                    tokens.append(Token(
                        value=inner_stripped,
                        type='bracket',
                        position=segment_start + 1 + leading_ws
                    ))
                continue
            
            if segment.startswith('(') and segment.endswith(')'):
                inner = segment[1:-1]
                inner_stripped = inner.strip()
                if inner_stripped:
                    leading_ws = len(inner) - len(inner.lstrip())
                    tokens.append(Token(
                        value=inner_stripped,
                        type='parenthesis',
                        position=segment_start + 1 + leading_ws
                    ))
                continue
            
            if segment.startswith('{') and segment.endswith('}'):
                inner = segment[1:-1]
                inner_stripped = inner.strip()
                if inner_stripped:
                    leading_ws = len(inner) - len(inner.lstrip())
                    tokens.append(Token(
                        value=inner_stripped,
                        type='curly',
                        position=segment_start + 1 + leading_ws
                    ))
                continue
            
            # Plain text segment: split on dash with space on at least one side
            dash_pattern = re.compile(r'(?:\s-\s|\s-|-\s)')
            last_idx = 0
            for dash_match in dash_pattern.finditer(segment):
                part = segment[last_idx:dash_match.start()]
                part_stripped = part.strip()
                if part_stripped:
                    leading_ws = len(part) - len(part.lstrip())
                    tokens.append(Token(
                        value=part_stripped,
                        type='text',
                        position=segment_start + last_idx + leading_ws
                    ))
                last_idx = dash_match.end()
            
            # Trailing segment after last dash (or the whole segment if no dash)
            tail = segment[last_idx:]
            tail_stripped = tail.strip()
            if tail_stripped:
                leading_ws = len(tail) - len(tail.lstrip())
                tokens.append(Token(
                    value=tail_stripped,
                    type='text',
                    position=segment_start + last_idx + leading_ws
                ))
        
        return tokens
    
    def _generate_pattern(self, token_source: str,
                          is_junk: Optional[List[bool]] = None,
                          path: Optional[str] = None,
                          path_sep: Optional[str] = None) -> str:
        """
        Build a structural pattern showing where tokens appeared, preserving
        delimiters/dashes and wrapping for brackets/parentheses/curly braces.

        When is_junk is provided, junk tokens are labeled as {junk} while
        real tokens are numbered {tokenN} sequentially.

        Args:
            token_source: The filename to generate pattern from
            is_junk: Optional list indicating which tokens are junk

        Returns:
            Pattern string with placeholders
        """
        parts: List[str] = []
        all_token_idx = 0  # Index into all_tokens
        real_token_idx = 0  # Counter for non-junk tokens only

        segment_pattern = re.compile(r'\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|[^{}\[\]\(\)]+')
        dash_pattern = re.compile(r'(?:\s-\s|\s-|-\s)')

        for match in segment_pattern.finditer(token_source):
            segment = match.group()

            if segment.startswith('[') and segment.endswith(']'):
                inner = segment[1:-1].strip()
                if inner:  # Only if non-empty
                    if is_junk and all_token_idx < len(is_junk) and is_junk[all_token_idx]:
                        parts.append("[{junk}]")
                    else:
                        parts.append(f"[{{token{real_token_idx}}}]")
                        real_token_idx += 1
                    all_token_idx += 1
                continue

            if segment.startswith('(') and segment.endswith(')'):
                inner = segment[1:-1].strip()
                if inner:  # Only if non-empty
                    if is_junk and all_token_idx < len(is_junk) and is_junk[all_token_idx]:
                        parts.append("({junk})")
                    else:
                        parts.append(f"({{token{real_token_idx}}})")
                        real_token_idx += 1
                    all_token_idx += 1
                continue

            if segment.startswith('{') and segment.endswith('}'):
                inner = segment[1:-1].strip()
                if inner:  # Only if non-empty
                    if is_junk and all_token_idx < len(is_junk) and is_junk[all_token_idx]:
                        parts.append("{{junk}}")
                    else:
                        parts.append(f"{{{{token{real_token_idx}}}}}")
                        real_token_idx += 1
                    all_token_idx += 1
                continue

            # Plain text segment: split on dash with space on at least one side
            last_idx = 0
            for dash_match in dash_pattern.finditer(segment):
                part = segment[last_idx:dash_match.start()]
                if part:
                    stripped = part.strip()
                    if stripped:
                        lead = len(part) - len(part.lstrip())
                        trail = len(part) - len(part.rstrip())
                        if is_junk and all_token_idx < len(is_junk) and is_junk[all_token_idx]:
                            parts.append(" " * lead + "{junk}" + " " * trail)
                        else:
                            parts.append(" " * lead + f"{{token{real_token_idx}}}" + " " * trail)
                            real_token_idx += 1
                        all_token_idx += 1
                    else:
                        parts.append(part)
                parts.append(segment[dash_match.start():dash_match.end()])
                last_idx = dash_match.end()

            tail = segment[last_idx:]
            if tail:
                stripped = tail.strip()
                if stripped:
                    lead = len(tail) - len(tail.lstrip())
                    trail = len(tail) - len(tail.rstrip())
                    if is_junk and all_token_idx < len(is_junk) and is_junk[all_token_idx]:
                        parts.append(" " * lead + "{junk}" + " " * trail)
                    else:
                        parts.append(" " * lead + f"{{token{real_token_idx}}}" + " " * trail)
                        real_token_idx += 1
                    all_token_idx += 1
                else:
                    parts.append(tail)

        base_pattern = "".join(parts).strip()
        if path:
            sep = path_sep or ""
            return f"{{path}}{sep}{base_pattern}"
        return base_pattern


if __name__ == '__main__':
    # Simple test
    tokenizer = Tokenizer()
    test_cases = [
        "/path/to/[Boyview] Happy days (3006).mp4",
        "[Studio] Movie Title (2023)",
        "Simple Movie Name",
        "C:\\Movies\\[Director] Film (Year)",
        "File[With]Brackets(And)Parentheses",
        "Test (parentheses) and [brackets]"
    ]
    
    for test in test_cases:
        result = tokenizer.tokenize(test)
        print(f"Original: {result.original}")
        print(f"Cleaned: {result.cleaned}")
        print(f"Pattern: {result.pattern}")
        for i, token in enumerate(result.tokens or []):
            print(f"  Token {i}: {token.value} ({token.type})")
        print()
