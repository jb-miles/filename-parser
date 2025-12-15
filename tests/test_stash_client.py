#!/usr/bin/env python3
"""
Tests for the Stash GraphQL client wrapper.
"""

from __future__ import annotations

from unittest.mock import patch

from modules.stash_client import StashClient


def test_stash_client_initialization_builds_url_and_conn():
    class FakeStashInterface:
        def __init__(self, conn):
            self.conn = conn

        def call_GQL(self, query, variables):
            raise AssertionError("call_GQL should not be invoked in this test")

    with patch("modules.stash_client.StashInterface", FakeStashInterface):
        client = StashClient(
            {
                "Scheme": "http",
                "Port": 9999,
                "SessionCookie": {"Name": "session", "Value": "cookie-value"},
            }
        )

        assert client.url == "http://localhost:9999/graphql"
        assert client.stash.conn["scheme"] == "http"
        assert client.stash.conn["host"] == "localhost"
        assert client.stash.conn["port"] == 9999
        assert client.stash.conn["SessionCookie"] == {"Name": "session", "Value": "cookie-value"}


def test_call_graphql_delegates_to_stash_interface():
    class FakeStashInterface:
        def __init__(self, conn):
            self.conn = conn
            self.calls = []

        def call_GQL(self, query, variables):
            self.calls.append((query, variables))
            return {"findScenes": {"count": 0}}

    with patch("modules.stash_client.StashInterface", FakeStashInterface):
        client = StashClient({"Scheme": "http", "Port": 9999})
        data = client.call_graphql("query { ping }")
        assert data == {"findScenes": {"count": 0}}
        assert client.stash.calls == [("query { ping }", {})]
