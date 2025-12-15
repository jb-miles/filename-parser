#!/usr/bin/env python3
"""
Stash GraphQL API client wrapper using StashAPI (stashapi).

This module provides a small, plugin-friendly interface to Stash's GraphQL API,
with specialized methods for:
- querying unorganized scenes (organized=false)
- fetching scenes by id
- resolving studios by name
- applying scene updates (single and bulk)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from stashapi.stashapp import StashInterface


@dataclass
class SceneFile:
    """Represents a file associated with a scene."""

    id: str
    path: str
    basename: str
    parent_folder_path: Optional[str] = None


@dataclass
class SceneStudio:
    """Represents a studio associated with a scene."""

    id: str
    name: str
    aliases: List[str] = field(default_factory=list)


@dataclass
class ScenePerformer:
    """Represents a performer associated with a scene."""

    id: str
    name: str


@dataclass
class Scene:
    """Represents a scene from Stash."""

    id: str
    title: Optional[str]
    date: Optional[str]
    code: Optional[str]
    studio: Optional[SceneStudio]
    files: List[SceneFile] = field(default_factory=list)
    performers: List[ScenePerformer] = field(default_factory=list)
    tags: List[Dict[str, Any]] = field(default_factory=list)
    organized: bool = False


class StashClient:
    """
    Client for interacting with Stash GraphQL API using stashapp-tools.

    Stash provides the plugin with connection details and a session cookie in
    the plugin input payload. This client wraps the official StashInterface
    for better maintainability and automatic API updates.
    """

    def __init__(self, server_connection: Dict[str, Any], host: str = "localhost"):
        """
        Initialize Stash client from server_connection dict.

        Args:
            server_connection: Connection details from Stash plugin input
            host: Default hostname if not provided in server_connection
        """
        # Build connection dict for StashInterface
        port = server_connection.get("Port", 9999)
        scheme = server_connection.get("Scheme", "http")
        hostname = server_connection.get("Host") or server_connection.get("Hostname") or host

        session_cookie = server_connection.get("SessionCookie") or {}
        api_key = server_connection.get("ApiKey") or ""

        conn = {
            "scheme": scheme,
            "host": hostname,
            "port": port,
            "SessionCookie": session_cookie,
            "ApiKey": api_key,
        }

        # Initialize StashInterface. StashAPI auto-generates fragments via schema introspection.
        self.stash = StashInterface(conn)

        # Legacy properties for backwards compatibility
        self.url = f"{scheme}://{hostname}:{port}/graphql"
        self.max_retries = 3
        self.retry_delay = 1.0
        self.timeout = 30

        # Selection sets used to override the default "...Scene"/"...Studio" fragment in StashAPI.
        self.scene_fragment = """
            id
            title
            date
            code
            organized
            studio {
                id
                name
            }
            files {
                id
                path
                basename
                parent_folder { path }
            }
            performers {
                id
                name
            }
        """
        self.studio_fragment = """
            id
            name
            aliases
        """

    def call_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call GraphQL API directly (for custom queries not covered by StashInterface).

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data dict

        Raises:
            RuntimeError: If query fails after retries
        """
        return self.stash.call_GQL(query, variables or {})

    def find_unorganized_scenes(
        self,
        page: int = 1,
        per_page: int = 50,
        studio_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Find scenes marked as unorganized.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            studio_ids: Optional list of studio IDs to filter by

        Returns:
            Dict with 'findScenes' key containing scenes and count
        """
        scene_filter: Dict[str, Any] = {"organized": False}

        if studio_ids:
            studio_id_ints: List[int] = []
            for studio_id in studio_ids:
                try:
                    studio_id_ints.append(int(studio_id))
                except (TypeError, ValueError):
                    continue
            if studio_id_ints:
                scene_filter["studios"] = {"value": studio_id_ints, "modifier": "INCLUDES"}

        filter_dict = {"page": page, "per_page": per_page, "sort": "title"}

        count, scenes = self.stash.find_scenes(
            f=scene_filter,
            filter=filter_dict,
            fragment=self.scene_fragment,
            get_count=True,
        )
        return {"findScenes": {"count": count, "scenes": scenes}}

    def get_all_unorganized_scenes(
        self,
        studio_ids: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        limit: Optional[int] = None,
    ) -> List[Scene]:
        """
        Get all unorganized scenes with pagination.

        Args:
            studio_ids: Optional list of studio IDs to filter by
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of Scene objects
        """
        all_scenes: List[Scene] = []
        page = 1
        per_page = 100

        while True:
            if limit is not None and limit > 0 and len(all_scenes) >= limit:
                break

            per_page_effective = per_page
            if limit is not None and limit > 0:
                per_page_effective = min(per_page, limit - len(all_scenes))

            result = self.find_unorganized_scenes(page=page, per_page=per_page_effective, studio_ids=studio_ids)
            scenes_data = result.get("findScenes", {}) or {}
            scenes = scenes_data.get("scenes", []) or []
            if not scenes:
                break

            for scene_data in scenes:
                all_scenes.append(self._parse_scene_data(scene_data))
                if limit is not None and limit > 0 and len(all_scenes) >= limit:
                    break

            if progress_callback:
                total = int(scenes_data.get("count") or 0)
                progress_callback(len(all_scenes), total)

            total = int(scenes_data.get("count") or 0)
            if total and len(all_scenes) >= total:
                break

            if limit is not None and limit > 0 and len(all_scenes) >= limit:
                break

            page += 1

        return all_scenes

    def get_scene_by_id(self, scene_id: str) -> Optional[Scene]:
        """
        Fetch a single scene by ID.

        Args:
            scene_id: Scene ID

        Returns:
            Scene object or None if not found
        """
        try:
            scene_data = self.stash.find_scene(int(scene_id), fragment=self.scene_fragment)
            if scene_data:
                return self._parse_scene_data(scene_data)
        except Exception:
            pass

        return None

    def get_scenes_by_ids(self, scene_ids: List[str]) -> List[Scene]:
        """
        Fetch multiple scenes by IDs.

        Args:
            scene_ids: List of scene IDs

        Returns:
            List of Scene objects
        """
        if not scene_ids:
            return []

        ids_as_ints: List[int] = []
        for scene_id in scene_ids:
            try:
                ids_as_ints.append(int(scene_id))
            except (TypeError, ValueError):
                continue

        scene_filter = {"ids": {"value": ids_as_ints, "modifier": "INCLUDES"}}
        filter_dict = {"page": 1, "per_page": len(ids_as_ints)}

        try:
            scenes = self.stash.find_scenes(f=scene_filter, filter=filter_dict, fragment=self.scene_fragment)
            return [self._parse_scene_data(s) for s in scenes]
        except Exception:
            # Fallback to sequential fetching
            result: List[Scene] = []
            for scene_id in scene_ids:
                scene = self.get_scene_by_id(scene_id)
                if scene:
                    result.append(scene)
            return result

    def find_studio_by_name(self, name: str, exact: bool = True) -> Optional[SceneStudio]:
        """
        Find studio by name.

        Args:
            name: Studio name to search for
            exact: Use exact match (EQUALS) vs fuzzy match (INCLUDES)

        Returns:
            SceneStudio object or None if not found
        """
        modifier = "EQUALS" if exact else "INCLUDES"
        studio_filter = {"name": {"value": name, "modifier": modifier}}

        studios = self.stash.find_studios(f=studio_filter, filter={"per_page": 1}, fragment=self.studio_fragment)
        if not studios:
            return None

        studio_data = studios[0]
        return SceneStudio(
            id=str(studio_data["id"]),
            name=studio_data["name"],
            aliases=studio_data.get("aliases") or [],
        )

    def get_all_studios(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[SceneStudio]:
        """
        Fetch all studios from Stash with pagination.

        Args:
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of SceneStudio objects with id, name, and aliases
        """
        all_studios: List[SceneStudio] = []
        page = 1
        per_page = 100

        while True:
            total, studios = self.stash.find_studios(
                filter={"page": page, "per_page": per_page},
                fragment=self.studio_fragment,
                get_count=True,
            )

            if not studios:
                break

            for studio_data in studios:
                all_studios.append(
                    SceneStudio(
                        id=str(studio_data["id"]),
                        name=studio_data["name"],
                        aliases=studio_data.get("aliases") or [],
                    )
                )

            if progress_callback:
                progress_callback(len(all_studios), int(total or 0))

            total_int = int(total or 0)
            if total_int and len(all_studios) >= total_int:
                break

            page += 1

        return all_studios

    def update_scene_metadata(
        self,
        scene_id: str,
        title: Optional[str] = None,
        date: Optional[str] = None,
        code: Optional[str] = None,
        studio_id: Optional[str] = None,
        organized: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update scene metadata.

        Args:
            scene_id: Scene ID to update
            title: New title
            date: New date
            code: New studio code
            studio_id: New studio ID
            organized: New organized status

        Returns:
            Updated scene data or None
        """
        input_data: Dict[str, Any] = {"id": scene_id}
        if title is not None:
            input_data["title"] = title
        if date is not None:
            input_data["date"] = date
        if code is not None:
            input_data["code"] = code
        if studio_id is not None:
            input_data["studio_id"] = studio_id
        if organized is not None:
            input_data["organized"] = organized

        return self.stash.update_scene(input_data)

    def bulk_update_scenes(
        self,
        updates: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        batch_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Bulk update multiple scenes.

        Args:
            updates: List of scene update dicts (each with 'id' and fields to update)
            progress_callback: Optional callback(current, total) for progress updates
            batch_size: Number of updates per batch

        Returns:
            List of updated scene data
        """
        all_results: List[Dict[str, Any]] = []

        for i in range(0, len(updates), batch_size):
            batch = updates[i : i + batch_size]

            # Update scenes one by one (stashapp-tools doesn't have bulk update method)
            for update in batch:
                result = self.stash.update_scene(update)
                if result:
                    all_results.append(result)

            if progress_callback:
                progress_callback(min(i + len(batch), len(updates)), len(updates))

            if i + batch_size < len(updates):
                time.sleep(0.5)

        return all_results

    def _parse_scene_data(self, scene_data: Dict[str, Any]) -> Scene:
        """
        Parse scene data from GraphQL response into Scene object.

        Args:
            scene_data: Raw scene data dict from GraphQL

        Returns:
            Scene object
        """
        studio_data = scene_data.get("studio")
        studio = None
        if studio_data:
            studio = SceneStudio(
                id=str(studio_data["id"]),
                name=studio_data["name"],
                aliases=studio_data.get("aliases") or [],
            )

        files: List[SceneFile] = []
        for file_data in scene_data.get("files") or []:
            parent_folder = file_data.get("parent_folder") or {}
            files.append(
                SceneFile(
                    id=str(file_data["id"]),
                    path=file_data.get("path") or "",
                    basename=file_data.get("basename") or "",
                    parent_folder_path=parent_folder.get("path"),
                )
            )

        performers: List[ScenePerformer] = []
        for performer_data in scene_data.get("performers") or []:
            performers.append(
                ScenePerformer(
                    id=str(performer_data["id"]),
                    name=performer_data.get("name") or "",
                )
            )

        return Scene(
            id=str(scene_data["id"]),
            title=scene_data.get("title"),
            date=scene_data.get("date"),
            code=scene_data.get("code"),
            studio=studio,
            files=files,
            performers=performers,
            tags=scene_data.get("tags") or [],
            organized=bool(scene_data.get("organized") or False),
        )
