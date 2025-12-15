#!/usr/bin/env python3
"""
Stash plugin for filename parsing with yansa.py integration.

Phase 1 scope (per ref/docs):
- Only proposes updates for: studio, title, date, studio code
- Never overwrites existing Stash values
- Defaults to leaving scenes unorganized

This script is designed to be executed by Stash as a plugin task:
- Reads JSON input from stdin
- Writes JSON output to stdout
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow importing from repo root when plugin is copied/executed standalone.
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(Path(__file__).resolve().parent))

from modules.batch_processor import BatchProcessor  # noqa: E402
from modules.scene_transformer import ParsedMetadata, SceneTransformer  # noqa: E402
from modules.stash_client import Scene, StashClient  # noqa: E402
from yansa import FilenameParser  # noqa: E402

from ui_components import UIComponents  # noqa: E402


class StashYansaPlugin:
    def __init__(self, input_data: Dict[str, Any]):
        self.input_data = input_data
        self.args = input_data.get("args") or {}
        self.server_connection = input_data.get("server_connection") or {}

        self.stash_client = StashClient(self.server_connection)
        self.scene_transformer = SceneTransformer()
        self.batch_processor = BatchProcessor(self.stash_client)
        self.filename_parser = FilenameParser()
        self.ui_components = UIComponents()

        self.config = self._load_config()
        self._apply_config()

    def main(self) -> Dict[str, Any]:
        mode = (self.args.get("mode") or "run").lower()

        try:
            if mode == "run":
                return self._run_enrichment()
            if mode == "list":
                return self._list_unorganized_scenes()
            if mode == "process":
                return self._process_scenes()
            if mode == "update":
                return self._update_scenes()
            return self._error_response(f"Unknown mode: {mode}")
        except Exception as exc:  # noqa: BLE001
            return self._error_response(f"Plugin error: {exc}")

    def _apply_config(self) -> None:
        processing = self.config.get("processing") or {}
        conflicts = self.config.get("conflicts") or {}

        self.batch_processor.batch_size = int(processing.get("batch_size", self.batch_processor.batch_size))
        self.scene_transformer.include_path_in_filename = bool(processing.get("include_path_in_filename", False))
        self.scene_transformer.mark_organized = bool(conflicts.get("mark_organized", False))

    def _load_config(self) -> Dict[str, Any]:
        default_config: Dict[str, Any] = {
            "processing": {
                "batch_size": 50,
                "confidence_threshold": 0.8,
                "auto_apply": True,
                "include_path_in_filename": False,
                "max_scenes": None,  # None = all
            },
            "conflicts": {
                "mark_organized": False,  # Phase 1 default: preserve unorganized status
            },
            "ui": {
                "sort_by": "filename",
            },
        }

        merged = dict(default_config)

        # Optional file-based runtime config.
        # Prefer Stash-provided PluginDir when available, fall back to repo layout.
        file_config: Dict[str, Any] = {}
        runtime_candidates: List[Path] = []
        plugin_dir = self.server_connection.get("PluginDir")
        if plugin_dir:
            runtime_candidates.extend(
                [
                    Path(str(plugin_dir)) / "runtime_config.json",
                    Path(str(plugin_dir)) / "config" / "runtime_config.json",
                ]
            )
        runtime_candidates.append(ROOT / "config" / "runtime_config.json")

        for runtime_path in runtime_candidates:
            try:
                if runtime_path.exists():
                    file_config = json.loads(runtime_path.read_text(encoding="utf-8"))
                    break
            except Exception:
                continue

        user_config = self.args.get("config") or {}

        # Convenience: allow flat overrides in args for common settings.
        processing_overrides: Dict[str, Any] = {}
        for key in ("batch_size", "confidence_threshold", "auto_apply", "include_path_in_filename", "max_scenes"):
            if key in self.args:
                processing_overrides[key] = self.args[key]
        if processing_overrides:
            user_config = {**user_config, "processing": {**(user_config.get("processing") or {}), **processing_overrides}}

        for source in (file_config, user_config):
            for section, values in source.items():
                if isinstance(values, dict) and isinstance(merged.get(section), dict):
                    merged[section] = {**merged[section], **values}
                else:
                    merged[section] = values

        return merged

    def _list_unorganized_scenes(self) -> Dict[str, Any]:
        scenes = self.stash_client.get_all_unorganized_scenes()
        scene_list: List[Dict[str, Any]] = []
        for scene in scenes:
            if not scene.files:
                continue
            scene_list.append(
                {
                    "id": scene.id,
                    "filename": scene.files[0].basename,
                    "path": scene.files[0].path,
                    "title": scene.title or "Untitled",
                    "studio": scene.studio.name if scene.studio else "Unknown",
                    "date": scene.date or "",
                    "code": scene.code or "",
                }
            )

        html = self.ui_components.scene_list_html(scene_list, self.config)
        return {"output": {"type": "html", "html": html}}

    def _process_scenes(self) -> Dict[str, Any]:
        scene_ids = self.args.get("scene_ids") or []
        if not scene_ids:
            return self._error_response("No scenes selected for processing")

        scenes = self.stash_client.get_scenes_by_ids(scene_ids)
        processed = self._process_scene_objects(scenes, threshold=None)
        html = self.ui_components.review_interface_html(processed, self.config)
        return {"output": {"type": "html", "html": html}}

    def _run_enrichment(self) -> Dict[str, Any]:
        processing = self.config.get("processing") or {}
        threshold = float(processing.get("confidence_threshold", 0.8))
        auto_apply = bool(processing.get("auto_apply", True))
        max_scenes = processing.get("max_scenes")

        scenes = self.stash_client.get_all_unorganized_scenes()
        if isinstance(max_scenes, int) and max_scenes > 0:
            scenes = scenes[:max_scenes]

        processed = self._process_scene_objects(scenes, threshold=threshold)
        updates = [p.get("update") for p in processed if p.get("update")]
        updates = [u for u in updates if isinstance(u, dict)]

        if not auto_apply:
            return {
                "output": {
                    "mode": "run",
                    "auto_applied": False,
                    "total_scenes": len(scenes),
                    "candidate_updates": len(updates),
                    "candidates": processed,
                }
            }

        # Apply updates.
        batch_result = self.batch_processor.process_updates(updates)
        return {
            "output": {
                "mode": "run",
                "auto_applied": True,
                "total_scenes": len(scenes),
                "candidate_updates": len(updates),
                "result": batch_result.__dict__,
            }
        }

    def _update_scenes(self) -> Dict[str, Any]:
        approved_updates = self.args.get("approved_updates") or []
        if not approved_updates:
            return self._error_response("No approved updates provided")

        # Two shapes are supported:
        # 1) {"id": "..."} -> re-parse and apply safe (thresholded) updates
        # 2) {"id": "...", "title": "...", ...} -> apply explicit user-approved values
        processing = self.config.get("processing") or {}
        threshold = float(processing.get("confidence_threshold", 0.8))

        update_payloads: List[Dict[str, Any]] = []
        for entry in approved_updates:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue

            scene_id = str(entry["id"])

            explicit_fields = {"title", "date", "code", "studio_id", "studio_name", "organized"}
            is_explicit = any(k in entry for k in explicit_fields)

            scene = self.stash_client.get_scene_by_id(scene_id)
            if not scene:
                continue

            if is_explicit:
                sanitized = self._sanitize_explicit_update(scene, entry)
                if set(sanitized.keys()) > {"id"}:
                    update_payloads.append(sanitized)
                continue

            # id-only: compute safe candidate update (thresholded)
            candidates = self._process_scene_objects([scene], threshold=threshold)
            candidate_update = candidates[0].get("update") if candidates else None
            if candidate_update and set(candidate_update.keys()) > {"id"}:
                update_payloads.append(candidate_update)

        batch_result = self.batch_processor.process_updates(update_payloads)
        return {"output": {"mode": "update", "result": batch_result.__dict__}}

    def _sanitize_explicit_update(self, current: Scene, proposed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure we never overwrite existing metadata fields.

        This is defense-in-depth: even if the UI sends an overwrite, we drop it.
        """
        update: Dict[str, Any] = {"id": current.id}

        if (current.title or "").strip() == "" and "title" in proposed:
            update["title"] = proposed.get("title")

        if (current.date or "").strip() == "" and "date" in proposed:
            update["date"] = proposed.get("date")

        if (current.code or "").strip() == "" and "code" in proposed:
            update["code"] = proposed.get("code")

        if current.studio is None:
            if "studio_id" in proposed:
                update["studio_id"] = proposed.get("studio_id")
            elif "studio_name" in proposed:
                update["studio_name"] = proposed.get("studio_name")

        # Phase 1: default is to preserve unorganized status; allow only if configured.
        if self.scene_transformer.mark_organized and "organized" in proposed:
            update["organized"] = bool(proposed.get("organized"))

        return update

    def _process_scene_objects(self, scenes: List[Scene], threshold: Optional[float]) -> List[Dict[str, Any]]:
        processed_scenes: List[Dict[str, Any]] = []

        for scene in scenes:
            filename = self.scene_transformer.scene_to_filename(scene)
            if not filename:
                continue

            result = self.filename_parser.parse(filename)
            parsed = self.scene_transformer.parse_result_to_metadata(result)
            comparison = self.scene_transformer.compare_metadata(parsed, scene)

            approved_fields = self._select_approved_fields(parsed, scene, threshold)
            update = self.scene_transformer.metadata_to_update(
                scene.id,
                parsed,
                original=scene,
                approved_fields=approved_fields,
            )

            # Remove the update from output if it's a no-op.
            if set(update.keys()) <= {"id"}:
                update = {}

            processed_scenes.append(
                {
                    "scene_id": scene.id,
                    "filename": filename,
                    "original": {
                        "title": scene.title,
                        "studio": scene.studio.name if scene.studio else None,
                        "date": scene.date,
                        "studio_code": scene.code,
                    },
                    "parsed": {
                        "title": parsed.title,
                        "studio": parsed.studio,
                        "date": parsed.date,
                        "studio_code": parsed.studio_code,
                    },
                    "comparison": comparison,
                    "update": update or None,
                }
            )

        return processed_scenes

    def _select_approved_fields(self, parsed: ParsedMetadata, original: Scene, threshold: Optional[float]) -> List[str]:
        """
        Decide which fields are eligible for update.

        Rules (Phase 1):
        - Never overwrite existing original fields
        - If `threshold` is None: return all parsed fields that are missing in original
        - If `threshold` is set: require per-field confidence >= threshold
        """
        approved: List[str] = []

        def passes(field: str) -> bool:
            if threshold is None:
                return True
            return float(parsed.confidence.get(field, 0.0)) >= float(threshold)

        if original.studio is None and parsed.studio and passes("studio"):
            approved.append("studio")
        if (original.title or "").strip() == "" and parsed.title and passes("title"):
            approved.append("title")
        if (original.date or "").strip() == "" and parsed.date and passes("date"):
            approved.append("date")
        if (original.code or "").strip() == "" and parsed.studio_code and passes("studio_code"):
            approved.append("studio_code")

        return approved

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {"error": message, "output": None}


def main() -> None:
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
        plugin = StashYansaPlugin(input_data)
        result = plugin.main()
        print(json.dumps(result))
    except Exception as exc:  # noqa: BLE001
        error_response = {"error": f"Plugin initialization error: {exc}", "output": None}
        print(json.dumps(error_response))
        sys.exit(1)


if __name__ == "__main__":
    main()
