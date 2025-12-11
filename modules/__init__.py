"""
Filename parser modules package.

This package contains the core processing modules:
- pre_tokenizer: Early token removal and filename cleaning
- tokenizer: Token extraction and pattern recognition
- date_extractor: Date extraction and normalization
- trimmer: String trimming utilities
- studio_matcher: Studio name matching
- studio_code_finder: Studio code identification
- performer_matcher: Performer name pattern matching
"""

# Explicit imports make the public API clear and prevent namespace pollution
from .tokenizer import Tokenizer, TokenizationResult, Token
from .pre_tokenizer import (
    PreTokenizer,
    PreTokenizationResult,
    RemovedToken,
    EarlyRemovalCategory
)
from .date_extractor import DateExtractor, DateMatch
from .studio_matcher import StudioMatcher
from .studio_code_finder import StudioCodeFinder
from .performer_matcher import PerformerMatcher

__all__ = [
    'Tokenizer',
    'TokenizationResult',
    'Token',
    'PreTokenizer',
    'PreTokenizationResult',
    'RemovedToken',
    'EarlyRemovalCategory',
    'DateExtractor',
    'DateMatch',
    'StudioMatcher',
    'StudioCodeFinder',
    'PerformerMatcher',
]
