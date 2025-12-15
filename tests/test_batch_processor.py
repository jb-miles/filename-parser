#!/usr/bin/env python3
"""
Tests for BatchProcessor update preparation and studio resolution.
"""

from __future__ import annotations

from unittest.mock import Mock

from modules.batch_processor import BatchProcessor
from modules.stash_client import SceneStudio


def test_batch_processor_resolves_studio_name_and_bulk_updates():
    stash_client = Mock()
    stash_client.find_studio_by_name.return_value = SceneStudio(id="1", name="UKNM")
    stash_client.bulk_update_scenes.return_value = [{"id": "123"}]

    processor = BatchProcessor(stash_client, batch_size=10)

    updates = [{"id": "123", "studio_name": "UKNM", "title": "My Title"}]
    result = processor.process_updates(updates, dry_run=False)

    assert result.successful_updates == 1
    assert result.failed_updates == 0

    # Ensure the API received a studio_id, not studio_name.
    args, _kwargs = stash_client.bulk_update_scenes.call_args
    sent_updates = args[0]
    assert sent_updates[0]["id"] == "123"
    assert sent_updates[0]["studio_id"] == "1"
    assert "studio_name" not in sent_updates[0]


def test_batch_processor_skips_noop_updates():
    stash_client = Mock()
    stash_client.bulk_update_scenes.return_value = []

    processor = BatchProcessor(stash_client, batch_size=10)
    result = processor.process_updates([{"id": "1"}], dry_run=False)

    assert result.skipped_scenes == 1
    assert result.successful_updates == 0


def test_batch_processor_drops_unresolvable_studio_but_keeps_other_fields():
    stash_client = Mock()
    stash_client.find_studio_by_name.return_value = None
    stash_client.bulk_update_scenes.return_value = [{"id": "123"}]

    processor = BatchProcessor(stash_client, batch_size=10)
    updates = [{"id": "123", "studio_name": "Unknown Studio", "title": "My Title"}]

    result = processor.process_updates(updates, dry_run=False)
    assert result.successful_updates == 1
    assert result.failed_updates == 0

    sent_updates = stash_client.bulk_update_scenes.call_args[0][0]
    assert sent_updates[0] == {"id": "123", "title": "My Title"}
