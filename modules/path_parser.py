#!/usr/bin/env python3
"""
Path parser module to keep directory handling separate from filename parsing.

Splits a filepath into:
- normalized path string ("/" separated)
- basename (filename only, no parent dirs)
- trimmed path segments for downstream use (e.g., group extraction)
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import List, Optional, Union
from .trimmer import Trimmer


@dataclass
class PathParseResult:
    """Structured result of parsing a filepath into path components."""
    original: str
    path: Optional[str]
    basename: str
    segments: List[str]
    separator: str = "/"
    group: Optional[str] = None


class PathParser:
    """Parser that isolates parent directory segments (no filename awareness)."""

    def __init__(self):
        self.trimmer = Trimmer()

    def parse(self, filepath: Union[str, Path, None]) -> PathParseResult:
        """
        Parse a directory path into normalized segments.

        Args:
            filepath: Directory path (not including the filename). Can be None/empty.

        Returns:
            PathParseResult with normalized segments and group (last segment)
        """
        if filepath in (None, "", "."):
            return PathParseResult(
                original=str(filepath or ""),
                path=None,
                basename="",
                segments=[],
                group=None
            )

        # Normalize slashes for consistent downstream handling and support Path-like input
        normalized = str(filepath).replace("\\", "/")
        posix_path = PurePosixPath(normalized)

        parts = [self.trimmer.trim(part) for part in posix_path.parts if part not in ("", "/")]
        parts = [p for p in parts if p]

        if not parts:
            return PathParseResult(
                original=str(filepath),
                path=None,
                basename="",
                segments=[],
                group=None
            )

        path = "/".join(parts)
        group = parts[-1]

        return PathParseResult(
            original=str(filepath),
            path=path,
            basename="",
            segments=parts,
            group=group
        )
