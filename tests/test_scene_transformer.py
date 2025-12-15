#!/usr/bin/env python3
"""
Tests for SceneTransformer and ParsedMetadata conversion logic.
"""

from __future__ import annotations

from modules.scene_transformer import ParsedMetadata, SceneTransformer
from modules.stash_client import Scene, SceneFile
from modules.tokenizer import Token, TokenizationResult


def test_scene_to_filename_defaults_to_basename():
    transformer = SceneTransformer()
    scene = Scene(
        id="1",
        title=None,
        date=None,
        code=None,
        studio=None,
        files=[SceneFile(id="f1", path="/media", basename="Test.mp4", parent_folder_path="/media")],
        performers=[],
        tags=[],
        organized=False,
    )

    assert transformer.scene_to_filename(scene) == "Test.mp4"


def test_scene_to_filename_can_include_parent_path():
    transformer = SceneTransformer()
    transformer.include_path_in_filename = True
    scene = Scene(
        id="1",
        title=None,
        date=None,
        code=None,
        studio=None,
        files=[SceneFile(id="f1", path="/media", basename="Test.mp4", parent_folder_path="/media")],
        performers=[],
        tags=[],
        organized=False,
    )

    assert transformer.scene_to_filename(scene) == "/media/Test.mp4"


def test_parse_result_to_metadata_extracts_date_and_code():
    transformer = SceneTransformer()
    token_result = TokenizationResult(
        original="file",
        cleaned="file",
        tokens=[Token(value="2024-01-01", type="date", position=0)],
        studio="UKNM",
        title="Title",
        studio_code="UKNM-001",
    )

    parsed = transformer.parse_result_to_metadata(token_result)
    assert parsed.studio == "UKNM"
    assert parsed.title == "Title"
    assert parsed.date == "2024-01-01"
    assert parsed.studio_code == "UKNM-001"


def test_metadata_to_update_never_overwrites_when_original_provided():
    transformer = SceneTransformer()
    original = Scene(
        id="1",
        title="Existing Title",
        date="2020-01-01",
        code="EXISTING",
        studio=None,
        files=[],
        performers=[],
        tags=[],
        organized=False,
    )
    parsed = ParsedMetadata(studio="UKNM", title="New Title", date="2024-01-01", studio_code="UKNM-001")

    update = transformer.metadata_to_update(
        scene_id="1",
        parsed=parsed,
        original=original,
        approved_fields=["studio", "title", "date", "studio_code"],
    )

    # Only studio is eligible (original has title/date/code).
    assert update["id"] == "1"
    assert "studio_name" in update
    assert update["studio_name"] == "UKNM"
    assert "title" not in update
    assert "date" not in update
    assert "code" not in update
    assert "organized" not in update

