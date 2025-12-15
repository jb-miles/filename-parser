#!/usr/bin/env python3
"""
Final-stage title behavior and pattern placeholder checks.
"""

from yansa import FilenameParser


def test_unlabeled_leading_number_kept_in_title_and_pattern():
    parser = FilenameParser()
    result = parser.parse("[Crunchboy] 23 cm entre les jambes (movie)")

    assert result.sequence is None
    assert result.title == "23 cm entre les jambes"
    assert result.pattern == "[{studio}] {title}"

