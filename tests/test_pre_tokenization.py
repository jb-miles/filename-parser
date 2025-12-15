#!/usr/bin/env python3
"""
Pytest tests for pre-tokenization functionality.
These tests lock down current behavior to prevent regressions.
"""

import pytest
import json
from modules import PreTokenizer


@pytest.fixture
def pre_tokenizer():
    """Fixture providing a PreTokenizer instance."""
    return PreTokenizer()


def test_json_structure(pre_tokenizer):
    """Verify JSON structure contains original, cleaned, and removed_tokens."""
    test_filename = "Test.Scene.720p.HQ.mp4"
    result = pre_tokenizer.process(test_filename)
    json_result = result.to_json()
    
    # Parse JSON to verify structure
    parsed = json.loads(json_result)
    
    # Verify it has correct keys
    assert "original" in parsed
    assert "cleaned" in parsed
    assert "removed_tokens" in parsed
    
    # Verify structure
    assert parsed["original"] == test_filename
    assert isinstance(parsed["cleaned"], str)
    assert isinstance(parsed["removed_tokens"], list)


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("Scene.720p.mp4", "Scene.720p.mp4", "Scene"),
    ("Video.HD.avi", "Video.HD.avi", "Video"),
    ("Movie.mkv", "Movie.mkv", "Movie"),
])
def test_extension_handling(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Extensions are stripped via pathlib stem without explicit removal tokens."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
    
    # Extensions should not be recorded as removed tokens
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    assert not any(val.startswith(".") for val in removed_values)


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("Scene.720p.HQ", "Scene.720p.HQ", "Scene"),
    ("Video.480p.Test", "Video.480p.Test", "Video..Test"),
    ("Movie.1080p", "Movie.1080p", "Movie"),
])
def test_resolution_marker_removal(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test that resolution markers are properly removed."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
    
    # Check that resolution was removed
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    assert any(res in removed_values for res in ["720p", "480p", "1080p"])


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("Scene.HQ.Test", "Scene.HQ.Test", "Scene..Test"),
    ("Video.UHD", "Video.UHD", "Video"),
    ("Movie.HD", "Movie.HD", "Movie"),
])
def test_quality_marker_removal(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test that quality markers are properly removed."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
    
    # Check that quality was removed
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    assert any(qual in removed_values for qual in ["HQ", "UHD", "HD"])


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("Scene.720p.HQ.mp4", "Scene.720p.HQ.mp4", "Scene"),
    ("Video.480p.HD.avi", "Video.480p.HD.avi", "Video"),
])
def test_multiple_marker_removal(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test removal of multiple markers in correct order."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
    
    # Check that multiple markers were removed
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    assert len(removed_values) >= 2


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("JustAScene", "JustAScene", "JustAScene"),
    ("Normal.Video.Name", "Normal.Video.Name", "Normal.Video.Name"),
])
def test_no_markers(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test filenames with no removable markers."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("Scene()", "Scene()", "Scene"),
    ("[]Video", "[]Video", "Video"),
    ("Movie[]", "Movie[]", "Movie"),
    ("Test()[]", "Test()[]", "Test"),
    ("File - - Name", "File - - Name", "File - Name"),
    ("Start()", "Start()", "Start"),
    ("End[]", "End[]", "End"),
    ("()Both[]", "()Both[]", "Both"),
])
def test_string_replacement(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test that defined strings are replaced with dash with proper spacing."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("Scene()720p.HQ.mp4", "Scene()720p.HQ.mp4", "Scene"),
    ("Video[]480p.HD.avi", "Video[]480p.HD.avi", "Video"),
    ("Movie - - 1080p.UHD.mkv", "Movie - - 1080p.UHD.mkv", "Movie"),
])
def test_combined_replacement_and_removal(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test that string replacement works together with marker removal."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
    
    # Check that markers were removed
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    assert len(removed_values) >= 2


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    ("()Start", "()Start", "Start"),
    ("End[]", "End[]", "End"),
    ("()Both[]", "()Both[]", "Both"),
    ("Multiple - - Separators", "Multiple - - Separators", "Multiple - Separators"),
])
def test_edge_cases(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test edge cases for string replacement at beginning and end."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned


@pytest.mark.parametrize("filename,expected_original,expected_cleaned,should_have_review", [
    # Test underscore replacement with spaces (no adjacent spaces) - no review flag
    ("Scene_Name", "Scene_Name", "Scene Name", False),
    ("Video_File_Name", "Video_File_Name", "Video File Name", False),
    ("Movie_Title_Here", "Movie_Title_Here", "Movie Title Here", False),
    # Test underscore removal when adjacent to spaces - review flag added
    ("Scene_ Name", "Scene_ Name", "Scene Name", True),  # Space after underscore
    ("Scene _Name", "Scene _Name", "Scene Name", True),   # Space before underscore
    ("Scene _ Name", "Scene _ Name", "Scene  Name", True),  # Spaces on both sides
    # Test mixed cases
    ("Scene_Name_ Title", "Scene_Name_ Title", "Scene Name Title", True),
    ("Scene _Name_Title", "Scene _Name_Title", "Scene Name Title", True),
    # Test with other processing
    ("Scene_Name.720p.HQ.mp4", "Scene_Name.720p.HQ.mp4", "Scene Name", False),
])
def test_whitespace_handling(pre_tokenizer, filename, expected_original, expected_cleaned, should_have_review):
    """Test that underscores are handled correctly based on context."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
    
    # Check if review flag was added when expected
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    has_review = "REVIEW_FLAG" in removed_values
    assert has_review == should_have_review


@pytest.mark.parametrize("filename,expected_original,expected_cleaned,should_have_review", [
    # Test complex cases with multiple underscore types
    ("Scene_Name_ Title_Here", "Scene_Name_ Title_Here", "Scene Name Title Here", True),
    ("Video _File_ Name _Test", "Video _File_ Name _Test", "Video File Name Test", True),
    # Test with existing processing
    ("Scene_Name.720p.HQ.mp4", "Scene_Name.720p.HQ.mp4", "Scene Name", False),
    ("Video_File_Name.480p.HD.avi", "Video_File_Name.480p.HD.avi", "Video File Name", False),
])
def test_whitespace_handling_combined(pre_tokenizer, filename, expected_original, expected_cleaned, should_have_review):
    """Test whitespace handling combined with other processing steps."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned


def test_apply_category_removal(pre_tokenizer):
    """Test _apply_category_removal method directly."""
    from modules import PreTokenizationResult, EarlyRemovalCategory
    import re
    
    result = PreTokenizationResult(
        original="Scene.720p.HQ.mp4",
        cleaned="Scene.720p.HQ.mp4",
        removed_tokens=[]
    )
    
    category = EarlyRemovalCategory(
        name="test_720p",
        description="Test 720p removal",
        pattern=re.compile(r'(?<![a-zA-Z0-9])(720p)(?![a-zA-Z0-9])'),
        position="anywhere",
        confidence=0.95,
        semantic_role="quality"
    )
    
    result = pre_tokenizer._apply_category_removal(result, category)
    
    assert result.cleaned == "Scene..HQ.mp4"
    assert len(result.removed_tokens) == 1
    assert result.removed_tokens[0].value == "720p"
    assert result.removed_tokens[0].category == "test_720p"


def test_apply_trimming(pre_tokenizer):
    """Test _apply_trimming method directly."""
    from modules import PreTokenizationResult
    
    result = PreTokenizationResult(
        original=" ()Scene.720p.mp4() ",
        cleaned=" ()Scene.720p.mp4() ",
        removed_tokens=[]
    )
    
    result = pre_tokenizer._apply_trimming(result)
    
    assert result.cleaned == "Scene.720p.mp4"


def test_apply_string_replacement(pre_tokenizer):
    """Test _apply_string_replacement method directly."""
    from modules import PreTokenizationResult
    
    result = PreTokenizationResult(
        original="Scene()Test",
        cleaned="Scene()Test",
        removed_tokens=[]
    )
    
    result = pre_tokenizer._apply_string_replacement(result)
    
    assert result.cleaned == "Scene - Test"


def test_apply_whitespace_handling(pre_tokenizer):
    """Test _apply_whitespace_handling method directly."""
    from modules import PreTokenizationResult
    
    # Test underscore replacement
    result = PreTokenizationResult(
        original="Scene_Name_Test",
        cleaned="Scene_Name_Test",
        removed_tokens=[]
    )
    
    result = pre_tokenizer._apply_whitespace_handling(result)
    
    assert result.cleaned == "Scene Name Test"
    assert len(result.removed_tokens) == 0
    
    # Test underscore removal with review flag
    result2 = PreTokenizationResult(
        original="Scene_ Name",
        cleaned="Scene_ Name",
        removed_tokens=[]
    )
    
    result2 = pre_tokenizer._apply_whitespace_handling(result2)
    
    assert result2.cleaned == "Scene Name"
    assert len(result2.removed_tokens) == 1
    assert result2.removed_tokens[0].value == "REVIEW_FLAG"


def test_default_early_removal_categories(pre_tokenizer):
    """Test that default early removal categories are loaded correctly."""
    categories = pre_tokenizer._default_early_removal_categories()
    
    # Check that we have expected number of categories
    assert len(categories) > 0
    
    # Check for specific categories
    category_names = [cat.name for cat in categories]
    assert "resolution_720p" in category_names
    assert "quality_HQ" in category_names
    
    # Check that categories have the expected properties
    for cat in categories:
        assert hasattr(cat, 'name')
        assert hasattr(cat, 'description')
        assert hasattr(cat, 'pattern')
        assert hasattr(cat, 'position')
        assert hasattr(cat, 'confidence')
        assert hasattr(cat, 'semantic_role')
        assert 0 <= cat.confidence <= 1


@pytest.mark.parametrize("filename,expected_cleaned", [
    ("Video\u2013480p.avi", "Video"),  # En dash
    ("Test\u2026File.mp4", "Test...File"),  # Ellipsis
    ("Space\u00a0Here.mp4", "Space Here"),  # Non-breaking space
])
def test_unicode_normalization(pre_tokenizer, filename, expected_cleaned):
    """Test that unicode characters are normalized correctly."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())

    assert parsed["original"] == filename
    assert parsed["cleaned"] == expected_cleaned


def test_empty_and_edge_cases(pre_tokenizer):
    """Test edge cases like empty strings and special inputs."""
    # Empty string
    result = pre_tokenizer.process("")
    parsed = json.loads(result.to_json())
    assert parsed["original"] == ""
    assert parsed["cleaned"] == ""
    assert len(parsed["removed_tokens"]) == 0
    
    # Only extension
    result = pre_tokenizer.process(".mp4")
    parsed = json.loads(result.to_json())
    assert parsed["original"] == ".mp4"
    assert parsed["cleaned"] == "mp4"
    assert len(parsed["removed_tokens"]) == 0
    
    # Only replacement characters
    result = pre_tokenizer.process("()[]")
    parsed = json.loads(result.to_json())
    assert parsed["original"] == "()[]"
    assert parsed["cleaned"] == ""
    assert len(parsed["removed_tokens"]) == 0


def test_removed_token_dataclass():
    """Test RemovedToken dataclass."""
    from modules import RemovedToken
    
    token = RemovedToken(
        value="720p",
        category="resolution",
        position=10,
        confidence=0.95
    )
    
    assert token.value == "720p"
    assert token.category == "resolution"
    assert token.position == 10
    assert token.confidence == 0.95


def test_pre_tokenization_result_dataclass():
    """Test PreTokenizationResult dataclass."""
    from modules import PreTokenizationResult, RemovedToken
    
    removed_token = RemovedToken(
        value="720p",
        category="resolution",
        position=10,
        confidence=1.0
    )
    
    result = PreTokenizationResult(
        original="Scene.720p",
        cleaned="Scene",
        removed_tokens=[removed_token]
    )
    
    assert result.original == "Scene.720p"
    assert result.cleaned == "Scene"
    assert len(result.removed_tokens) == 1
    assert result.removed_tokens[0].value == "720p"
    
    # Test JSON serialization
    json_str = result.to_json()
    parsed = json.loads(json_str)
    assert parsed["original"] == "Scene.720p"
    assert parsed["cleaned"] == "Scene"
    assert len(parsed["removed_tokens"]) == 1
    assert parsed["removed_tokens"][0]["value"] == "720p"


def test_early_removal_category_dataclass():
    """Test EarlyRemovalCategory dataclass."""
    from modules import EarlyRemovalCategory
    import re
    
    category = EarlyRemovalCategory(
        name="test_category",
        description="Test category description",
        pattern=re.compile(r'test'),
        position="anywhere",
        confidence=0.9,
        semantic_role="test"
    )
    
    assert category.name == "test_category"
    assert category.description == "Test category description"
    assert category.pattern.pattern == "test"
    assert category.position == "anywhere"
    assert category.confidence == 0.9
    assert category.semantic_role == "test"
    


def test_whitespace_handling_no_underscores(pre_tokenizer):
    """Test that files without underscores are not affected."""
    filename = "Scene.Name.720p.HQ.mp4"
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == filename
    assert parsed["cleaned"] == "Scene.Name"
    
    # Should not have review flag
    removed_values = [token["value"] for token in parsed["removed_tokens"]]
    assert "REVIEW_FLAG" not in removed_values
    assert len(parsed["removed_tokens"]) == 2


@pytest.mark.parametrize("filename,expected_original,expected_cleaned", [
    (" ()Scene.720p.mp4", " ()Scene.720p.mp4", "Scene"),
    ("Scene.720p.mp4() ", "Scene.720p.mp4() ", "Scene"),
    (" - Scene.720p.mp4", " - Scene.720p.mp4", "Scene"),
    ("Scene.720p.mp4 - ", "Scene.720p.mp4 - ", "Scene"),
    (" ()Scene.720p.mp4() ", " ()Scene.720p.mp4() ", "Scene"),
    (" - Scene.720p.mp4 - ", " - Scene.720p.mp4 - ", "Scene"),
])
def test_trimming(pre_tokenizer, filename, expected_original, expected_cleaned):
    """Test that trimming strings are properly removed from beginning and end."""
    result = pre_tokenizer.process(filename)
    parsed = json.loads(result.to_json())
    
    assert parsed["original"] == expected_original
    assert parsed["cleaned"] == expected_cleaned
