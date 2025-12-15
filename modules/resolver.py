#!/usr/bin/env python3
"""
Resolver for merging path-derived metadata with filename-derived metadata.

Rules:
- Filename wins on conflict.
- Path backfills when filename is empty or marked low-confidence.
- Telemetry is recorded per field (source + confidence).
"""

from typing import Optional, Tuple, Dict
from .tokenizer import TokenizationResult
from .path_parser import PathParseResult


class PathFilenameResolver:
    """Merge path and filename signals with explicit precedence and telemetry."""

    def __init__(self, path_confidence: float = 0.6):
        self.path_confidence = path_confidence

    def _choose(
        self,
        field: str,
        filename_val,
        path_val=None,
        confidences: Optional[Dict[str, float]] = None
    ) -> Tuple[Optional[object], Optional[str], float]:
        """Apply precedence/low-confidence fallback."""
        filename_conf = (confidences or {}).get(field, 1.0)

        has_filename = filename_val not in (None, "")
        has_path = path_val not in (None, "")

        if has_filename:
            if has_path and filename_conf < self.path_confidence:
                return path_val, "path", self.path_confidence
            return filename_val, "filename", filename_conf

        if has_path:
            return path_val, "path", self.path_confidence

        return None, None, 0.0

    def resolve(self, result: TokenizationResult, path_result: PathParseResult) -> TokenizationResult:
        """Attach telemetry and apply path fallback."""
        sources = dict(result.sources or {})
        confidences = dict(result.confidences or {})

        # Studio
        result.studio, studio_source, studio_conf = self._choose(
            "studio", result.studio, None, confidences
        )
        if studio_source:
            sources["studio"] = studio_source
            confidences["studio"] = studio_conf

        # Performers
        result.performers, perf_source, perf_conf = self._choose(
            "performers", getattr(result, "performers", None), None, confidences
        )
        if perf_source:
            sources["performers"] = perf_source
            confidences["performers"] = perf_conf

        # Date
        result.date, date_source, date_conf = self._choose(
            "date", getattr(result, "date", None), None, confidences
        )
        if date_source:
            sources["date"] = date_source
            confidences["date"] = date_conf

        # Studio code
        result.studio_code, code_source, code_conf = self._choose(
            "studio_code", getattr(result, "studio_code", None), None, confidences
        )
        if code_source:
            sources["studio_code"] = code_source
            confidences["studio_code"] = code_conf

        # Sequence
        result.sequence, seq_source, seq_conf = self._choose(
            "sequence", result.sequence, None, confidences
        )
        if seq_source:
            sources["sequence"] = seq_source
            confidences["sequence"] = seq_conf

        # Title
        result.title, title_source, title_conf = self._choose(
            "title", result.title, None, confidences
        )
        if title_source:
            sources["title"] = title_source
            confidences["title"] = title_conf

        # Group (path backfill available)
        result.group, group_source, group_conf = self._choose(
            "group", result.group, path_result.group, confidences
        )
        if group_source:
            sources["group"] = group_source
            confidences["group"] = group_conf

        result.sources = sources
        result.confidences = confidences
        return result
