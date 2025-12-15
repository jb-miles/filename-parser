#!/usr/bin/env python3
"""
Batch processor for efficient scene metadata updates.

This module applies approved metadata changes back to Stash using bulk
GraphQL mutations, with validation, progress reporting, and basic performance
metrics.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

from .scene_transformer import ParsedMetadata, SceneTransformer
from .stash_client import Scene, StashClient


@dataclass
class BatchResult:
    total_scenes: int
    successful_updates: int
    failed_updates: int
    skipped_scenes: int
    errors: List[Dict[str, Any]] = field(default_factory=list)
    processing_time: float = 0.0
    scenes_per_second: float = 0.0


@dataclass
class UpdateRequest:
    scene_id: str
    parsed_metadata: ParsedMetadata
    approved_fields: List[str]
    original_scene: Optional[Scene] = None
    comparison_result: Optional[Dict[str, Any]] = None


PreparedUpdate = Dict[str, Any]
UpdateInput = Union[UpdateRequest, PreparedUpdate]


class BatchProcessor:
    def __init__(self, stash_client: StashClient, batch_size: int = 20, max_workers: int = 4) -> None:
        self.stash_client = stash_client
        self.scene_transformer = SceneTransformer()
        self.batch_size = batch_size
        self.max_workers = max_workers

        self.start_time: Optional[float] = None
        self.processed_count = 0
        self.error_count = 0

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self._studio_name_cache: Dict[str, Optional[str]] = {}

    def process_updates(
        self,
        update_requests: Sequence[UpdateInput],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        dry_run: bool = False,
    ) -> BatchResult:
        self.start_time = time.time()
        self.processed_count = 0
        self.error_count = 0

        total_scenes = len(update_requests)
        successful_updates = 0
        failed_updates = 0
        skipped_scenes = 0
        errors: List[Dict[str, Any]] = []

        self.logger.info("Starting batch processing of %s scenes", total_scenes)

        for i in range(0, total_scenes, self.batch_size):
            batch = list(update_requests[i : i + self.batch_size])
            batch_number = i // self.batch_size + 1

            self.logger.info("Processing batch %s (%s scenes)", batch_number, len(batch))

            try:
                batch_results = self._process_batch(batch, dry_run=dry_run)

                successful_updates += batch_results["successful"]
                failed_updates += batch_results["failed"]
                skipped_scenes += batch_results["skipped"]
                errors.extend(batch_results["errors"])

                self.processed_count += len(batch)
                if progress_callback:
                    progress_callback(self.processed_count, total_scenes)

                if not dry_run and i + self.batch_size < total_scenes:
                    time.sleep(0.5)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Batch %s failed: %s", batch_number, str(exc))
                errors.append({"batch_number": batch_number, "error": str(exc), "scene_count": len(batch)})
                failed_updates += len(batch)
                self.processed_count += len(batch)

        processing_time = time.time() - (self.start_time or time.time())
        scenes_per_second = (total_scenes / processing_time) if processing_time > 0 else 0.0

        return BatchResult(
            total_scenes=total_scenes,
            successful_updates=successful_updates,
            failed_updates=failed_updates,
            skipped_scenes=skipped_scenes,
            errors=errors,
            processing_time=processing_time,
            scenes_per_second=scenes_per_second,
        )

    def process_updates_parallel(
        self,
        update_requests: Sequence[UpdateInput],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        dry_run: bool = False,
    ) -> BatchResult:
        self.start_time = time.time()
        total_scenes = len(update_requests)

        batches: List[List[UpdateInput]] = [
            list(update_requests[i : i + self.batch_size]) for i in range(0, total_scenes, self.batch_size)
        ]

        successful_updates = 0
        failed_updates = 0
        skipped_scenes = 0
        errors: List[Dict[str, Any]] = []
        processed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_batch = {executor.submit(self._process_batch, batch, dry_run=dry_run): batch for batch in batches}

            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    batch_result = future.result()
                    successful_updates += batch_result["successful"]
                    failed_updates += batch_result["failed"]
                    skipped_scenes += batch_result["skipped"]
                    errors.extend(batch_result["errors"])
                except Exception as exc:  # noqa: BLE001
                    self.logger.error("Parallel batch failed: %s", str(exc))
                    errors.append({"error": f"Parallel processing failed: {exc}", "type": "parallel", "scene_count": len(batch)})
                    failed_updates += len(batch)

                processed_count += len(batch)
                if progress_callback:
                    progress_callback(processed_count, total_scenes)

        processing_time = time.time() - (self.start_time or time.time())
        scenes_per_second = (total_scenes / processing_time) if processing_time > 0 else 0.0

        return BatchResult(
            total_scenes=total_scenes,
            successful_updates=successful_updates,
            failed_updates=failed_updates,
            skipped_scenes=skipped_scenes,
            errors=errors,
            processing_time=processing_time,
            scenes_per_second=scenes_per_second,
        )

    def _process_batch(self, batch: Sequence[UpdateInput], *, dry_run: bool) -> Dict[str, Any]:
        successful = 0
        failed = 0
        skipped = 0
        errors: List[Dict[str, Any]] = []

        update_data: List[PreparedUpdate] = []

        for item in batch:
            try:
                update = self._prepare_update(item)
                if self._is_noop_update(update):
                    skipped += 1
                    continue

                validation = self._validate_update(update)
                if not validation["valid"]:
                    errors.append({"scene_id": update.get("id"), "error": validation["error"], "type": "validation"})
                    failed += 1
                    continue

                update_data.append(update)
            except Exception as exc:  # noqa: BLE001
                self.error_count += 1
                errors.append(
                    {
                        "scene_id": getattr(item, "scene_id", None) if not isinstance(item, dict) else item.get("id"),
                        "error": f"Update preparation failed: {exc}",
                        "type": "preparation",
                    }
                )
                failed += 1

        if dry_run:
            successful += len(update_data)
            return {"successful": successful, "failed": failed, "skipped": skipped, "errors": errors}

        if not update_data:
            return {"successful": successful, "failed": failed, "skipped": skipped, "errors": errors}

        try:
            api_results = self.stash_client.bulk_update_scenes(update_data)
            for idx, result in enumerate(api_results):
                if result:
                    successful += 1
                else:
                    failed += 1
                    errors.append({"scene_id": update_data[idx].get("id"), "error": "API returned no result", "type": "api"})
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Bulk update failed: %s", str(exc))
            errors.append({"error": f"Bulk update failed: {exc}", "type": "api", "scene_count": len(update_data)})
            failed += len(update_data)

        return {"successful": successful, "failed": failed, "skipped": skipped, "errors": errors}

    def _prepare_update(self, item: UpdateInput) -> PreparedUpdate:
        if isinstance(item, dict):
            update = dict(item)
        else:
            update = self.scene_transformer.metadata_to_update(
                item.scene_id,
                item.parsed_metadata,
                original=item.original_scene,
                approved_fields=item.approved_fields,
            )

        # Resolve studio_name -> studio_id when needed
        if "studio_name" in update and "studio_id" not in update:
            studio_id = self._resolve_studio_id(update["studio_name"])
            if studio_id:
                update["studio_id"] = studio_id

        # Never send studio_name to the API
        update.pop("studio_name", None)

        return update

    def _resolve_studio_id(self, studio_name: str) -> Optional[str]:
        studio_name_key = (studio_name or "").strip()
        if not studio_name_key:
            return None

        if studio_name_key in self._studio_name_cache:
            return self._studio_name_cache[studio_name_key]

        studio = self.stash_client.find_studio_by_name(studio_name_key, exact=True)
        if not studio:
            studio = self.stash_client.find_studio_by_name(studio_name_key, exact=False)

        studio_id = studio.id if studio else None
        self._studio_name_cache[studio_name_key] = studio_id
        return studio_id

    def _is_noop_update(self, update_data: PreparedUpdate) -> bool:
        return set(update_data.keys()) <= {"id"}

    def _validate_update(self, update_data: PreparedUpdate) -> Dict[str, Any]:
        if "id" not in update_data:
            return {"valid": False, "error": "Missing scene ID"}

        # Don't allow empty updates to go to the API.
        if self._is_noop_update(update_data):
            return {"valid": False, "error": "No approved fields to update"}

        if "title" in update_data:
            title = update_data.get("title")
            if title and len(str(title)) > 500:
                return {"valid": False, "error": "Title too long (max 500 characters)"}

        if "date" in update_data:
            date = update_data.get("date")
            if date and not self._is_valid_date(str(date)):
                return {"valid": False, "error": f"Invalid date format: {date}"}

        if "studio_id" in update_data and not update_data.get("studio_id"):
            return {"valid": False, "error": "Studio ID could not be resolved"}

        return {"valid": True}

    def _is_valid_date(self, date_str: str) -> bool:
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                time.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        return False

    def estimate_processing_time(self, scene_count: int) -> Dict[str, Any]:
        scenes_per_second = 2.0
        api_overhead = 0.1
        batch_overhead = 0.5

        processing_time = scene_count / scenes_per_second
        batch_count = (scene_count + self.batch_size - 1) // self.batch_size
        total_overhead = batch_count * (api_overhead + batch_overhead)
        total_time = processing_time + total_overhead

        return {
            "estimated_seconds": total_time,
            "estimated_minutes": total_time / 60,
            "batch_count": batch_count,
            "scenes_per_second": scenes_per_second,
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        if not self.start_time:
            return {"status": "no_processing_started"}

        elapsed_time = time.time() - self.start_time
        current_rate = (self.processed_count / elapsed_time) if elapsed_time > 0 else 0.0

        return {
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "elapsed_time": elapsed_time,
            "current_rate": current_rate,
            "batch_size": self.batch_size,
            "max_workers": self.max_workers,
        }
