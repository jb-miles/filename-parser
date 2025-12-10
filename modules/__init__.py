"""
Filename parser modules package.

This package contains the core processing modules:
- pre_tokenizer: Early token removal and filename cleaning
- tokenizer: Token extraction and pattern recognition
- date_extractor: Date extraction and normalization
- trimmer: String trimming utilities
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
]
