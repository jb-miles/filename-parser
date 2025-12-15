#!/usr/bin/env python3
"""
Tests for MetadataComparator comparison behaviour.
"""

from __future__ import annotations

from modules.metadata_comparator import MetadataComparator
from modules.scene_transformer import ParsedMetadata
from modules.stash_client import Scene, SceneStudio


def test_compare_scene_metadata_new_data_is_auto_approvable():
    comparator = MetadataComparator()
    parsed = ParsedMetadata(
        studio="UKNM",
        title="AJ Alexander & Brent Taylor",
        date="2024-01-15",
        studio_code="UKNM-001",
        confidence={"studio": 0.9, "title": 0.9, "date": 0.9, "studio_code": 0.9},
    )
    original = Scene(
        id="8447",
        title=None,
        date=None,
        code=None,
        studio=None,
        files=[],
        performers=[],
        tags=[],
        organized=False,
    )

    result = comparator.compare_scene_metadata(parsed, original)
    assert result.overall_status == "no_conflicts"
    assert result.auto_approve is True
    assert result.requires_review is False
    assert result.field_comparisons["studio"].status == "new_data"


def test_compare_scene_metadata_conflict_requires_review():
    comparator = MetadataComparator()
    parsed = ParsedMetadata(
        studio="Studio A",
        title="Title A",
        date="2024-01-15",
        studio_code="AAA-001",
        confidence={"studio": 0.9, "title": 0.9, "date": 0.9, "studio_code": 0.9},
    )
    original = Scene(
        id="1",
        title="Completely different",
        date="2020-01-01",
        code="ZZZ-999",
        studio=SceneStudio(id="10", name="Studio Z"),
        files=[],
        performers=[],
        tags=[],
        organized=False,
    )

    result = comparator.compare_scene_metadata(parsed, original)
    assert result.requires_review is True
    assert result.auto_approve is False
    assert result.overall_status in {"minor_conflicts", "major_conflicts"}

