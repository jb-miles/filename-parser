#!/usr/bin/env python3
"""
Scene data transformer for converting between Stash and yansa.py formats.

This module:
- Extracts a filename (or path+filename) from a Stash Scene object for parsing.
- Converts yansa.py TokenizationResult into structured ParsedMetadata.
- Compares parsed vs existing metadata for UI/review purposes.
- Produces a Stash update payload for approved fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .stash_client import Scene, SceneFile
from .tokenizer import TokenizationResult


@dataclass
class ParsedMetadata:
    """Metadata parsed from a filename."""

    studio: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    studio_code: Optional[str] = None
    sequence: Optional[Dict[str, Any]] = None
    group: Optional[str] = None
    confidence: Dict[str, float] = field(default_factory=dict)


class SceneTransformer:
    """Transforms scene data between Stash and yansa.py formats."""

    def __init__(self) -> None:
        self.prefer_first_file = True
        self.include_path_in_filename = False
        self.mark_organized = False  # Phase 1 default: keep scenes unorganized

    def scene_to_filename(self, scene: Scene) -> Optional[str]:
        if not scene.files:
            return None

        file = scene.files[0] if self.prefer_first_file else self._select_best_file(scene.files)
        if self.include_path_in_filename and file.parent_folder_path:
            return f"{file.parent_folder_path}/{file.basename}"
        return file.basename

    def scenes_to_filenames(self, scenes: List[Scene]) -> List[Tuple[str, str]]:
        result: List[Tuple[str, str]] = []
        for scene in scenes:
            filename = self.scene_to_filename(scene)
            if filename:
                result.append((scene.id, filename))
        return result

    def parse_result_to_metadata(self, result: TokenizationResult) -> ParsedMetadata:
        return ParsedMetadata(
            studio=result.studio,
            title=result.title,
            date=self._extract_date(result),
            studio_code=getattr(result, "studio_code", None),
            sequence=result.sequence,
            group=result.group,
            confidence=self._calculate_confidence(result),
        )

    def compare_metadata(self, parsed: ParsedMetadata, original: Scene) -> Dict[str, Dict[str, Any]]:
        comparison: Dict[str, Dict[str, Any]] = {}

        comparison["studio"] = self._compare_field(
            parsed.studio,
            original.studio.name if original.studio else None,
            "studio",
        )
        comparison["title"] = self._compare_field(parsed.title, original.title, "title")
        comparison["date"] = self._compare_field(parsed.date, original.date, "date")
        comparison["studio_code"] = self._compare_field(parsed.studio_code, original.code, "studio_code")

        return comparison

    def metadata_to_update(
        self,
        scene_id: str,
        parsed: ParsedMetadata,
        original: Optional[Scene] = None,
        approved_fields: Optional[List[str]] = None,
        *,
        mark_organized: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Convert parsed metadata to a Stash SceneUpdateInput-ish dict.

        Notes:
        - Studio is output as `studio_name` (not `studio_id`) and must be
          resolved by the caller via StashClient.
        - If `original` is provided, fields that already have values are never
          included (defense-in-depth).
        """
        update: Dict[str, Any] = {"id": scene_id}

        if approved_fields is None:
            approved_fields = [
                field_name
                for field_name in ("studio", "title", "date", "studio_code")
                if getattr(parsed, field_name) is not None
            ]

        def original_has_value(field_name: str) -> bool:
            if original is None:
                return False
            if field_name == "studio":
                return original.studio is not None
            if field_name == "title":
                return bool((original.title or "").strip())
            if field_name == "date":
                return bool((original.date or "").strip())
            if field_name == "studio_code":
                return bool((original.code or "").strip())
            return False

        for field_name in approved_fields:
            if original_has_value(field_name):
                continue

            if field_name == "studio" and parsed.studio:
                update["studio_name"] = parsed.studio
            elif field_name == "title" and parsed.title:
                update["title"] = parsed.title
            elif field_name == "date" and parsed.date:
                update["date"] = parsed.date
            elif field_name == "studio_code" and parsed.studio_code:
                update["code"] = parsed.studio_code

        resolved_mark_organized = self.mark_organized if mark_organized is None else mark_organized
        if resolved_mark_organized and self._should_mark_organized(parsed, approved_fields):
            update["organized"] = True

        return update

    def _select_best_file(self, files: List[SceneFile]) -> SceneFile:
        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}
        video_files = [
            file
            for file in files
            if any(file.basename.lower().endswith(ext) for ext in video_extensions)
        ]
        if video_files:
            return min(video_files, key=lambda f: len(f.basename))
        return files[0]

    def _extract_date(self, result: TokenizationResult) -> Optional[str]:
        for token in result.tokens or []:
            if token.type == "date":
                return token.value
        return None

    def _calculate_confidence(self, result: TokenizationResult) -> Dict[str, float]:
        if getattr(result, "confidences", None):
            return dict(result.confidences or {})

        confidence: Dict[str, float] = {}
        if result.studio:
            confidence["studio"] = 0.9
        if result.title:
            confidence["title"] = 0.7
        if getattr(result, "studio_code", None):
            confidence["studio_code"] = 0.8
        if self._extract_date(result):
            confidence["date"] = 0.8
        return confidence

    def _compare_field(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str],
        field_name: str,
    ) -> Dict[str, Any]:
        if parsed_value is None and original_value is None:
            return {"status": "no_change", "parsed": None, "original": None, "confidence": 1.0}

        if parsed_value is None:
            return {"status": "no_data", "parsed": None, "original": original_value, "confidence": 0.0}

        if original_value is None:
            return {"status": "new_data", "parsed": parsed_value, "original": None, "confidence": 0.8}

        parsed_clean = self._normalize_for_comparison(parsed_value, field_name)
        original_clean = self._normalize_for_comparison(original_value, field_name)

        if parsed_clean == original_clean:
            return {"status": "match", "parsed": parsed_value, "original": original_value, "confidence": 1.0}

        similarity = self._calculate_similarity(parsed_clean, original_clean)
        if similarity > 0.9:
            status = "minor_diff"
        elif similarity > 0.5:
            status = "major_diff"
        else:
            status = "conflict"

        return {
            "status": status,
            "parsed": parsed_value,
            "original": original_value,
            "similarity": similarity,
            "confidence": similarity,
        }

    def _normalize_for_comparison(self, value: str, field_name: str) -> str:
        normalized = (value or "").strip().lower()
        if field_name == "studio":
            normalized = normalized.replace(" studio", "").replace(" productions", "")
        elif field_name == "title":
            normalized = normalized.replace("_", " ").replace("-", " ")
        return normalized

    def _calculate_similarity(self, str1: str, str2: str) -> float:
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

    def _should_mark_organized(self, parsed: ParsedMetadata, approved_fields: List[str]) -> bool:
        has_studio = "studio" in approved_fields and parsed.studio is not None
        has_title = "title" in approved_fields and parsed.title is not None
        has_date = "date" in approved_fields and parsed.date is not None
        has_code = "studio_code" in approved_fields and parsed.studio_code is not None
        return (has_studio and has_title) or (has_studio and (has_date or has_code))

