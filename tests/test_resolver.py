#!/usr/bin/env python3
"""Tests for the path/filename resolver telemetry and precedence."""

from modules import PathFilenameResolver, PathParseResult
from modules.tokenizer import TokenizationResult, Token


def make_result(group=None, sources=None, confidences=None):
    return TokenizationResult(
        original="orig",
        cleaned="clean",
        tokens=[Token(value="foo", type="text", position=0)],
        group=group,
        sources=sources,
        confidences=confidences
    )


def test_group_backfills_from_path_when_filename_empty():
    resolver = PathFilenameResolver()
    path_result = PathParseResult(
        original="parent/child/file",
        path="parent/child",
        basename="file",
        segments=["parent", "child"],
        group="child"
    )
    result = make_result(group=None)

    resolved = resolver.resolve(result, path_result)

    assert resolved.group == "child"
    assert resolved.sources["group"] == "path"
    assert resolved.confidences["group"] == resolver.path_confidence


def test_filename_group_wins_on_conflict():
    resolver = PathFilenameResolver()
    path_result = PathParseResult(
        original="parent/child/file",
        path="parent/child",
        basename="file",
        segments=["parent", "child"],
        group="child"
    )
    result = make_result(group="from_filename")

    resolved = resolver.resolve(result, path_result)

    assert resolved.group == "from_filename"
    assert resolved.sources["group"] == "filename"


def test_low_confidence_allows_path_override():
    resolver = PathFilenameResolver(path_confidence=0.6)
    path_result = PathParseResult(
        original="parent/child/file",
        path="parent/child",
        basename="file",
        segments=["parent", "child"],
        group="child"
    )
    result = make_result(group="maybe_wrong", confidences={"group": 0.2})

    resolved = resolver.resolve(result, path_result)

    assert resolved.group == "child"
    assert resolved.sources["group"] == "path"
    assert resolved.confidences["group"] == resolver.path_confidence
