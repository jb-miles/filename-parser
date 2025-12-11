#!/usr/bin/env python3
"""
Tests for date extraction normalization to ISO 8601.
"""

import pytest
from parser import FilenameParser


@pytest.fixture
def parser():
    """Fixture providing a parser instance."""
    return FilenameParser()


@pytest.mark.parametrize(
    "filename,expected_date",
    [
        ("2020-01-15 Happy times", "2020-01-15"),
        ("Scene (Dec 25, 2020)", "2020-12-25"),
        ("01-05-2019 Sample", "2019-01-05"),
        ("15 January 2021 Something", "2021-01-15"),
        ("20200102 Title", "2020-01-02"),
    ],
)
def test_dates_normalize_to_iso(parser, filename, expected_date):
    """Ensure extracted dates are normalized to ISO 8601 format."""
    result = parser.parse(filename)
    date_tokens = [token for token in result.tokens or [] if token.type == "date"]

    assert date_tokens, f"No date token found for '{filename}'"
    assert date_tokens[0].value == expected_date
