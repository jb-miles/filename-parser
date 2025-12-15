#!/usr/bin/env python3
"""
Stash GraphQL API client for querying and updating scene metadata.

This module provides a small Python interface to Stash's GraphQL API, with
specialized methods for:
- querying unorganized scenes (organized=false)
- fetching scenes by id
- resolving studios by name
- applying scene updates (single and bulk)

The plugin uses this client to keep all Stash-specific API logic in one place.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests


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
    aliases: List[str] = field(default_factory=list)


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
    Client for interacting with Stash GraphQL API.

    Stash provides the plugin with connection details and a session cookie in
    the plugin input payload. This client encapsulates authentication,
    pagination, and update mutation helpers.
    """

    def __init__(self, server_connection: Dict[str, Any], host: str = "localhost"):
        self.port = server_connection.get("Port", 9999)
        self.scheme = server_connection.get("Scheme", "http")
        self.host = server_connection.get("Host") or server_connection.get("Hostname") or host
        self.url = f"{self.scheme}://{self.host}:{self.port}/graphql"

        session_cookie = server_connection.get("SessionCookie") or {}
        cookie_name = session_cookie.get("Name") or "session"
        cookie_value = session_cookie.get("Value") or ""
        self.cookies = {cookie_name: cookie_value} if cookie_value else {}

        self.headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Connection": "keep-alive",
            "DNT": "1",
        }

        self.max_retries = 3
        self.retry_delay = 1.0
        self.timeout = 30

    def call_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {"query": query}
        if variables:
            json_data["variables"] = variables

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.url,
                    json=json_data,
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=self.timeout,
                )

                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.content!r}")

                result = response.json()
                if "errors" in result and result["errors"]:
                    raise RuntimeError(f"GraphQL errors: {result['errors']}")

                return result.get("data", {}) or {}
            except Exception as exc:  # noqa: BLE001 - we want to retry any failure here
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))
                    continue
                raise RuntimeError(f"GraphQL query failed after retries: {last_error}") from last_error

        raise RuntimeError("Unreachable: retry loop should have returned or raised")

    def find_unorganized_scenes(
        self,
        page: int = 1,
        per_page: int = 50,
        studio_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        query = """
        query FindUnorganizedScenes($filter: FindFilterType, $scene_filter: SceneFilterType) {
            findScenes(filter: $filter, scene_filter: $scene_filter) {
                count
                scenes {
                    id
                    title
                    date
                    code
                    studio {
                        id
                        name
                        aliases
                    }
                    files {
                        id
                        path
                        basename
                        parent_folder {
                            path
                        }
                    }
                    performers {
                        id
                        name
                        aliases
                    }
                    tags {
                        id
                        name
                    }
                    organized
                }
            }
        }
        """

        variables: Dict[str, Any] = {
            "filter": {"page": page, "per_page": per_page, "sort": "title"},
            "scene_filter": {
                "organized": {"value": False, "modifier": "EQUALS"},
            },
        }

        if studio_ids:
            variables["scene_filter"]["studios"] = {"value": studio_ids, "modifier": "INCLUDES"}

        return self.call_graphql(query, variables)

    def get_all_unorganized_scenes(
        self,
        studio_ids: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Scene]:
        all_scenes: List[Scene] = []
        page = 1
        per_page = 100

        while True:
            result = self.find_unorganized_scenes(page=page, per_page=per_page, studio_ids=studio_ids)
            scenes_data = result.get("findScenes", {}) or {}
            scenes = scenes_data.get("scenes", []) or []
            if not scenes:
                break

            for scene_data in scenes:
                all_scenes.append(self._parse_scene_data(scene_data))

            if progress_callback:
                total = int(scenes_data.get("count") or 0)
                progress_callback(len(all_scenes), total)

            total = int(scenes_data.get("count") or 0)
            if total and len(all_scenes) >= total:
                break

            page += 1

        return all_scenes

    def get_scene_by_id(self, scene_id: str) -> Optional[Scene]:
        """
        Fetch a single scene.

        Stash schemas vary slightly by version; we try a direct `findScene` query
        first, then fall back to `findScenes` with an ID filter.
        """
        # Attempt 1: findScene(id: ID!)
        find_scene_query = """
        query FindScene($id: ID!) {
            findScene(id: $id) {
                id
                title
                date
                code
                studio { id name aliases }
                files {
                    id
                    path
                    basename
                    parent_folder { path }
                }
                performers { id name aliases }
                tags { id name }
                organized
            }
        }
        """

        try:
            data = self.call_graphql(find_scene_query, {"id": scene_id})
            scene_data = data.get("findScene")
            if scene_data:
                return self._parse_scene_data(scene_data)
        except Exception:
            pass

        # Attempt 2: findScenes + ids criterion
        find_scenes_query = """
        query FindScenesById($filter: FindFilterType, $scene_filter: SceneFilterType) {
            findScenes(filter: $filter, scene_filter: $scene_filter) {
                scenes {
                    id
                    title
                    date
                    code
                    studio { id name aliases }
                    files {
                        id
                        path
                        basename
                        parent_folder { path }
                    }
                    performers { id name aliases }
                    tags { id name }
                    organized
                }
            }
        }
        """

        variables = {
            "filter": {"page": 1, "per_page": 1},
            "scene_filter": {"ids": {"value": [scene_id], "modifier": "INCLUDES"}},
        }

        data = self.call_graphql(find_scenes_query, variables)
        scenes = (data.get("findScenes", {}) or {}).get("scenes", []) or []
        if scenes:
            return self._parse_scene_data(scenes[0])

        return None

    def get_scenes_by_ids(self, scene_ids: List[str]) -> List[Scene]:
        """
        Fetch scenes by ids.

        Uses `findScenes` with an ids criterion when available; falls back to
        sequential `get_scene_by_id` calls.
        """
        if not scene_ids:
            return []

        find_scenes_query = """
        query FindScenesByIds($filter: FindFilterType, $scene_filter: SceneFilterType) {
            findScenes(filter: $filter, scene_filter: $scene_filter) {
                scenes {
                    id
                    title
                    date
                    code
                    studio { id name aliases }
                    files {
                        id
                        path
                        basename
                        parent_folder { path }
                    }
                    performers { id name aliases }
                    tags { id name }
                    organized
                }
            }
        }
        """

        variables = {
            "filter": {"page": 1, "per_page": len(scene_ids)},
            "scene_filter": {"ids": {"value": scene_ids, "modifier": "INCLUDES"}},
        }

        try:
            data = self.call_graphql(find_scenes_query, variables)
            scenes = (data.get("findScenes", {}) or {}).get("scenes", []) or []
            return [self._parse_scene_data(s) for s in scenes]
        except Exception:
            result: List[Scene] = []
            for scene_id in scene_ids:
                scene = self.get_scene_by_id(scene_id)
                if scene:
                    result.append(scene)
            return result

    def find_studio_by_name(self, name: str, exact: bool = True) -> Optional[SceneStudio]:
        query = """
        query FindStudios($name: String!, $modifier: CriterionModifier!) {
            findStudios(
                studio_filter: {
                    name: { value: $name, modifier: $modifier }
                }
                filter: { per_page: 1 }
            ) {
                studios { id name aliases }
            }
        }
        """

        variables = {"name": name, "modifier": "EQUALS" if exact else "INCLUDES"}
        result = self.call_graphql(query, variables)
        studios = (result.get("findStudios", {}) or {}).get("studios", []) or []
        if not studios:
            return None

        studio_data = studios[0]
        return SceneStudio(
            id=str(studio_data["id"]),
            name=studio_data["name"],
            aliases=studio_data.get("aliases") or [],
        )

    def update_scene_metadata(
        self,
        scene_id: str,
        title: Optional[str] = None,
        date: Optional[str] = None,
        code: Optional[str] = None,
        studio_id: Optional[str] = None,
        organized: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        query = """
        mutation SceneUpdate($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) {
                id
                title
                date
                code
                studio { id name }
                organized
            }
        }
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

        result = self.call_graphql(query, {"input": input_data})
        return result.get("sceneUpdate")

    def bulk_update_scenes(
        self,
        updates: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        batch_size: int = 20,
    ) -> List[Dict[str, Any]]:
        query = """
        mutation BulkSceneUpdate($updates: [SceneUpdateInput!]!) {
            bulkSceneUpdate(input: $updates) {
                id
                title
                date
                code
                studio { id name }
                organized
            }
        }
        """

        all_results: List[Dict[str, Any]] = []
        for i in range(0, len(updates), batch_size):
            batch = updates[i : i + batch_size]
            result = self.call_graphql(query, {"updates": batch})
            batch_results = result.get("bulkSceneUpdate", []) or []
            all_results.extend(batch_results)

            if progress_callback:
                progress_callback(min(i + len(batch), len(updates)), len(updates))

            if i + batch_size < len(updates):
                time.sleep(0.5)

        return all_results

    def _parse_scene_data(self, scene_data: Dict[str, Any]) -> Scene:
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
                    aliases=performer_data.get("aliases") or [],
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
