"""
Filename parser modules package.

This package contains the core processing modules:
- pre_tokenizer: Early token removal and filename cleaning
- tokenizer: Token extraction and pattern recognition
- date_extractor: Date extraction and normalization
- trimmer: String trimming utilities
- path_parser: Path isolation and normalization
 - resolver: Path/basename merge with telemetry
- studio_matcher: Studio name matching
- studio_code_finder: Studio code identification
- performer_matcher: Performer name pattern matching
- sequence_extractor: Sequence information extraction (part, scene, episode, volume)
- title_extractor: Title extraction from remaining tokens
"""

# Explicit imports make the public API clear and prevent namespace pollution
from .tokenizer import Tokenizer, TokenizationResult, Token
from .pre_tokenizer import (
    PreTokenizer,
    PreTokenizationResult,
    RemovedToken,
    EarlyRemovalCategory
)
from .path_parser import PathParser, PathParseResult
from .resolver import PathFilenameResolver
from .date_extractor import DateExtractor, DateMatch
from .studio_matcher import StudioMatcher
from .studio_code_finder import StudioCodeFinder
from .performer_matcher import PerformerMatcher
from .sequence_extractor import SequenceExtractor
from .final_stage_extractor import FinalStageExtractor
from .title_extractor import TitleExtractor

__all__ = [
    'Tokenizer',
    'TokenizationResult',
    'Token',
    'PreTokenizer',
    'PreTokenizationResult',
    'RemovedToken',
    'EarlyRemovalCategory',
    'PathParser',
    'PathParseResult',
    'PathFilenameResolver',
    'DateExtractor',
    'DateMatch',
    'StudioMatcher',
    'StudioCodeFinder',
    'PerformerMatcher',
    'SequenceExtractor',
    'FinalStageExtractor',
    'TitleExtractor',
]
