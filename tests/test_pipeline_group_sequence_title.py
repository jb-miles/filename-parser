#!/usr/bin/env python3
"""
End-to-end pipeline checks for group/sequence/title synthesis.
"""

from yansa import FilenameParser


def test_group_sequence_title_synthesized_from_scene_marker():
    parser = FilenameParser()
    filename = (
        "8492_02_1080p Glory Hole Breeders, Scene #02 "
        "(Devil, Enrico Belaggio, James Jones &amp; Tom Ryan)"
    )

    result = parser.parse(filename, existing_studio="Scary Fuckers")

    assert getattr(result, "studio_code", None) == "0849202"
    assert result.group == "Glory Hole Breeders"
    assert result.sequence == {"scene": 2}
    assert result.title == "Glory Hole Breeders, Scene 2"

    performer_tokens = [t.value for t in (result.tokens or []) if t.type == "performers"]
    assert performer_tokens == ["Devil, Enrico Belaggio, James Jones, Tom Ryan"]

