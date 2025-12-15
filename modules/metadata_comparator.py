#!/usr/bin/env python3
"""
Metadata comparator for comparing parsed and existing scene metadata.

This module provides field-by-field comparison between yansa.py parsed
metadata (ParsedMetadata) and existing Stash metadata (Scene), including:
- string normalization
- similarity scoring (Levenshtein)
- conflict classification (minor/major/conflict)
- per-field recommendations (accept/keep/manual review)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .scene_transformer import ParsedMetadata
from .stash_client import Scene


@dataclass
class FieldComparison:
    field_name: str
    parsed_value: Optional[str]
    original_value: Optional[str]
    status: str
    similarity: float
    confidence: float
    recommendation: str
    reason: Optional[str] = None


@dataclass
class ComparisonResult:
    scene_id: str
    field_comparisons: Dict[str, FieldComparison]
    overall_status: str
    auto_approve: bool
    requires_review: bool


class MetadataComparator:
    def __init__(self) -> None:
        self.confidence_threshold = 0.8
        self.similarity_thresholds = {
            "exact_match": 1.0,
            "minor_diff": 0.9,
            "major_diff": 0.5,
        }
        self.field_weights = {
            "studio": 0.3,
            "title": 0.3,
            "date": 0.2,
            "studio_code": 0.2,
        }

    def compare_scene_metadata(
        self,
        parsed: ParsedMetadata,
        original: Scene,
        config: Optional[Dict[str, Any]] = None,
    ) -> ComparisonResult:
        if config:
            self._update_config(config)

        field_comparisons: Dict[str, FieldComparison] = {
            "studio": self._compare_studio(
                parsed.studio,
                original.studio.name if original.studio else None,
                parsed.confidence.get("studio"),
            ),
            "title": self._compare_title(parsed.title, original.title, parsed.confidence.get("title")),
            "date": self._compare_date(parsed.date, original.date, parsed.confidence.get("date")),
            "studio_code": self._compare_studio_code(
                parsed.studio_code,
                original.code,
                parsed.confidence.get("studio_code"),
            ),
        }

        overall_status, auto_approve, requires_review = self._determine_overall_status(field_comparisons)

        return ComparisonResult(
            scene_id=original.id,
            field_comparisons=field_comparisons,
            overall_status=overall_status,
            auto_approve=auto_approve,
            requires_review=requires_review,
        )

    def _compare_studio(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str],
        confidence: Optional[float],
    ) -> FieldComparison:
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name="studio",
                parsed_value=None,
                original_value=None,
                status="no_change",
                similarity=1.0,
                confidence=1.0,
                recommendation="accept_parsed",
                reason="Both values are empty",
            )

        if parsed_value is None:
            return FieldComparison(
                field_name="studio",
                parsed_value=None,
                original_value=original_value,
                status="no_data",
                similarity=0.0,
                confidence=0.0,
                recommendation="keep_original",
                reason="No parsed studio available",
            )

        if original_value is None:
            conf = 0.9 if confidence is None else confidence
            return FieldComparison(
                field_name="studio",
                parsed_value=parsed_value,
                original_value=None,
                status="new_data",
                similarity=1.0,
                confidence=conf,
                recommendation="accept_parsed" if conf >= self.confidence_threshold else "manual_review",
                reason="New studio data where original was empty",
            )

        parsed_clean = self._normalize_studio_name(parsed_value)
        original_clean = self._normalize_studio_name(original_value)
        similarity = self._calculate_string_similarity(parsed_clean, original_clean)

        if similarity >= self.similarity_thresholds["exact_match"]:
            status, recommendation, reason = "match", "keep_original", "Studio names match exactly"
        elif similarity >= self.similarity_thresholds["minor_diff"]:
            status = "minor_diff"
            recommendation = "accept_parsed" if len(parsed_value) > len(original_value) else "keep_original"
            reason = "Studio names are very similar"
        elif similarity >= self.similarity_thresholds["major_diff"]:
            status, recommendation, reason = "major_diff", "manual_review", "Studio names have significant differences"
        else:
            status, recommendation, reason = "conflict", "manual_review", "Studio names are completely different"

        base_conf = 0.9 if confidence is None else confidence
        return FieldComparison(
            field_name="studio",
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
            confidence=min(base_conf, similarity),
            recommendation=recommendation,
            reason=reason,
        )

    def _compare_title(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str],
        confidence: Optional[float],
    ) -> FieldComparison:
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name="title",
                parsed_value=None,
                original_value=None,
                status="no_change",
                similarity=1.0,
                confidence=1.0,
                recommendation="accept_parsed",
                reason="Both values are empty",
            )

        if parsed_value is None:
            return FieldComparison(
                field_name="title",
                parsed_value=None,
                original_value=original_value,
                status="no_data",
                similarity=0.0,
                confidence=0.0,
                recommendation="keep_original",
                reason="No parsed title available",
            )

        if original_value is None:
            conf = 0.7 if confidence is None else confidence
            return FieldComparison(
                field_name="title",
                parsed_value=parsed_value,
                original_value=None,
                status="new_data",
                similarity=1.0,
                confidence=conf,
                recommendation="accept_parsed" if conf >= self.confidence_threshold else "manual_review",
                reason="New title data where original was empty",
            )

        parsed_clean = self._normalize_title(parsed_value)
        original_clean = self._normalize_title(original_value)
        similarity = self._calculate_string_similarity(parsed_clean, original_clean)

        if similarity >= self.similarity_thresholds["exact_match"]:
            status, recommendation, reason = "match", "keep_original", "Titles match exactly"
        elif similarity >= self.similarity_thresholds["minor_diff"]:
            status = "minor_diff"
            recommendation = "accept_parsed" if len(parsed_value) > len(original_value) else "keep_original"
            reason = "Titles are very similar"
        elif similarity >= self.similarity_thresholds["major_diff"]:
            status, recommendation, reason = "major_diff", "manual_review", "Titles have significant differences"
        else:
            status, recommendation, reason = "conflict", "manual_review", "Titles are completely different"

        base_conf = 0.7 if confidence is None else confidence
        return FieldComparison(
            field_name="title",
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
            confidence=min(base_conf, similarity),
            recommendation=recommendation,
            reason=reason,
        )

    def _compare_date(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str],
        confidence: Optional[float],
    ) -> FieldComparison:
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name="date",
                parsed_value=None,
                original_value=None,
                status="no_change",
                similarity=1.0,
                confidence=1.0,
                recommendation="accept_parsed",
                reason="Both values are empty",
            )

        if parsed_value is None:
            return FieldComparison(
                field_name="date",
                parsed_value=None,
                original_value=original_value,
                status="no_data",
                similarity=0.0,
                confidence=0.0,
                recommendation="keep_original",
                reason="No parsed date available",
            )

        if original_value is None:
            conf = 0.8 if confidence is None else confidence
            return FieldComparison(
                field_name="date",
                parsed_value=parsed_value,
                original_value=None,
                status="new_data",
                similarity=1.0,
                confidence=conf,
                recommendation="accept_parsed" if conf >= self.confidence_threshold else "manual_review",
                reason="New date data where original was empty",
            )

        parsed_date = self._parse_date(parsed_value)
        original_date = self._parse_date(original_value)

        if parsed_date is None or original_date is None:
            similarity = self._calculate_string_similarity(parsed_value, original_value)
            status = "conflict" if similarity < 0.8 else "major_diff"
            recommendation = "manual_review"
            reason = "Date format could not be normalized"
        else:
            if parsed_date == original_date:
                status, similarity, recommendation, reason = "match", 1.0, "keep_original", "Dates match exactly"
            else:
                days_diff = abs((parsed_date - original_date).days)
                if days_diff <= 1:
                    status, similarity, recommendation, reason = "minor_diff", 0.95, "accept_parsed", "Dates differ by 1 day or less"
                elif days_diff <= 7:
                    status, similarity, recommendation, reason = "major_diff", 0.8, "manual_review", "Dates differ by less than a week"
                else:
                    status, similarity, recommendation, reason = "conflict", 0.3, "manual_review", "Dates differ by more than a week"

        base_conf = 0.8 if confidence is None else confidence
        effective_conf = 0.0 if parsed_date is None else min(base_conf, similarity)
        return FieldComparison(
            field_name="date",
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
            confidence=effective_conf,
            recommendation=recommendation,
            reason=reason,
        )

    def _compare_studio_code(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str],
        confidence: Optional[float],
    ) -> FieldComparison:
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name="studio_code",
                parsed_value=None,
                original_value=None,
                status="no_change",
                similarity=1.0,
                confidence=1.0,
                recommendation="accept_parsed",
                reason="Both values are empty",
            )

        if parsed_value is None:
            return FieldComparison(
                field_name="studio_code",
                parsed_value=None,
                original_value=original_value,
                status="no_data",
                similarity=0.0,
                confidence=0.0,
                recommendation="keep_original",
                reason="No parsed studio code available",
            )

        if original_value is None:
            conf = 0.8 if confidence is None else confidence
            return FieldComparison(
                field_name="studio_code",
                parsed_value=parsed_value,
                original_value=None,
                status="new_data",
                similarity=1.0,
                confidence=conf,
                recommendation="accept_parsed" if conf >= self.confidence_threshold else "manual_review",
                reason="New studio code data where original was empty",
            )

        parsed_clean = re.sub(r"\s+", "", parsed_value.upper())
        original_clean = re.sub(r"\s+", "", original_value.upper())
        similarity = self._calculate_string_similarity(parsed_clean, original_clean)

        if similarity >= self.similarity_thresholds["exact_match"]:
            status, recommendation, reason = "match", "keep_original", "Studio codes match exactly"
        elif similarity >= self.similarity_thresholds["minor_diff"]:
            status = "minor_diff"
            recommendation = "accept_parsed" if len(parsed_value) > len(original_value) else "keep_original"
            reason = "Studio codes are very similar"
        elif similarity >= self.similarity_thresholds["major_diff"]:
            status, recommendation, reason = "major_diff", "manual_review", "Studio codes have significant differences"
        else:
            status, recommendation, reason = "conflict", "manual_review", "Studio codes are completely different"

        base_conf = 0.8 if confidence is None else confidence
        return FieldComparison(
            field_name="studio_code",
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
            confidence=min(base_conf, similarity),
            recommendation=recommendation,
            reason=reason,
        )

    def _determine_overall_status(self, field_comparisons: Dict[str, FieldComparison]) -> Tuple[str, bool, bool]:
        has_major_conflicts = False
        has_minor_conflicts = False
        has_new_data = False

        for comparison in field_comparisons.values():
            if comparison.status in {"major_diff", "conflict"}:
                has_major_conflicts = True
            elif comparison.status == "minor_diff":
                has_minor_conflicts = True
            elif comparison.status == "new_data":
                has_new_data = True

        if has_major_conflicts:
            return "major_conflicts", False, True
        if has_minor_conflicts:
            # Minor diffs still generally deserve review.
            return "minor_conflicts", False, True

        # If we only add new data (or nothing changes), we can auto-approve.
        overall_status = "no_conflicts"
        auto_approve = True
        requires_review = False
        if not has_new_data:
            # All fields match/no_change/no_data.
            auto_approve = True
            requires_review = False
        return overall_status, auto_approve, requires_review

    def _normalize_studio_name(self, name: str) -> str:
        if not name:
            return ""
        normalized = name.lower()
        normalized = re.sub(r"\b(studio|productions|entertainment)\b", "", normalized)
        normalized = re.sub(r"[^a-z0-9]", "", normalized)
        return normalized.strip()

    def _normalize_title(self, title: str) -> str:
        if not title:
            return ""
        normalized = re.sub(r"\s+", " ", title.lower().strip())
        normalized = re.sub(r"[^\w\s]", "", normalized)
        return normalized

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y",
            "%m-%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        if str1 == str2:
            return 1.0
        len1, len2 = len(str1), len(str2)
        if len1 == 0:
            return 0.0 if len2 > 0 else 1.0
        if len2 == 0:
            return 0.0

        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if str1[i - 1] == str2[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost,
                )

        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)

    def _update_config(self, config: Dict[str, Any]) -> None:
        if "confidence_threshold" in config:
            self.confidence_threshold = float(config["confidence_threshold"])
        if "similarity_thresholds" in config:
            self.similarity_thresholds.update(config["similarity_thresholds"])
        if "field_weights" in config:
            self.field_weights.update(config["field_weights"])

