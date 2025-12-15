#!/usr/bin/env python3
"""
Tests for the Stash GraphQL client wrapper.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from modules.stash_client import StashClient


def test_stash_client_initialization_builds_url_and_cookies():
    client = StashClient(
        {
            "Scheme": "http",
            "Port": 9999,
            "SessionCookie": {"Name": "session", "Value": "cookie-value"},
        }
    )

    assert client.url == "http://localhost:9999/graphql"
    assert client.cookies == {"session": "cookie-value"}


def test_call_graphql_success_returns_data():
    client = StashClient({"Scheme": "http", "Port": 9999})
    client.max_retries = 1

    response = Mock()
    response.status_code = 200
    response.json.return_value = {"data": {"findScenes": {"count": 0}}}

    with patch("modules.stash_client.requests.post", return_value=response) as post:
        data = client.call_graphql("query { ping }")
        assert data == {"findScenes": {"count": 0}}
        assert post.call_count == 1


def test_call_graphql_raises_on_graphql_errors():
    client = StashClient({"Scheme": "http", "Port": 9999})
    client.max_retries = 1

    response = Mock()
    response.status_code = 200
    response.json.return_value = {"errors": [{"message": "boom"}]}

    with patch("modules.stash_client.requests.post", return_value=response):
        with pytest.raises(RuntimeError):
            client.call_graphql("query { ping }")

