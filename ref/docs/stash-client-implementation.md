# Stash Client Implementation

## Overview

This document provides the complete implementation for the Stash GraphQL API client module that will interface with the Stash database to query unorganized scenes and update metadata.

## File: `modules/stash_client.py`

```python
#!/usr/bin/env python3
"""
Stash GraphQL API client for querying and updating scene metadata.

This module provides a Python interface to Stash GraphQL API, with
specialized methods for querying unorganized scenes and updating metadata
based on parsed filename data.
"""

import json
import time
import requests
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass


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
    aliases: List[str] = None


@dataclass
class ScenePerformer:
    """Represents a performer associated with a scene."""
    id: str
    name: str
    aliases: List[str] = None


@dataclass
class Scene:
    """Represents a scene from Stash."""
    id: str
    title: Optional[str]
    date: Optional[str]
    code: Optional[str]
    studio: Optional[SceneStudio]
    files: List[SceneFile]
    performers: List[ScenePerformer]
    tags: List[Dict[str, Any]]
    organized: bool


class StashClient:
    """
    Client for interacting with Stash GraphQL API.
    
    Provides methods for querying scenes, studios, and updating metadata
    with proper authentication and error handling.
    """

    def __init__(self, server_connection: Dict[str, Any]):
        """
        Initialize Stash client with server connection details.
        
        Args:
            server_connection: Connection dict from plugin input
        """
        self.port = server_connection.get('Port', 9999)
        self.scheme = server_connection.get('Scheme', 'http')
        self.url = f"{self.scheme}://localhost:{self.port}/graphql"
        
        # Extract session cookie for authentication
        session_cookie = server_connection.get('SessionCookie', {})
        self.cookies = {
            session_cookie.get('Name', 'session'): session_cookie.get('Value', '')
        } if session_cookie else {}
        
        self.headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Connection": "keep-alive",
            "DNT": "1"
        }
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.timeout = 30  # seconds

    def call_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query with retry logic.
        
        Args:
            query: GraphQL query string
            variables: Optional variables for query
            
        Returns:
            GraphQL response data
            
        Raises:
            Exception: If query fails after retries
        """
        json_data = {'query': query}
        if variables:
            json_data['variables'] = variables
            
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.url,
                    json=json_data,
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'errors' in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    return result.get('data', {})
                else:
                    raise Exception(
                        f"HTTP {response.status_code}: {response.content}"
                    )
                    
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise Exception(f"GraphQL query failed: {last_error}")

    def find_unorganized_scenes(
        self,
        page: int = 1,
        per_page: int = 50,
        studio_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Query for unorganized scenes with pagination.
        
        Args:
            page: Page number (1-indexed)
            per_page: Number of scenes per page (max 1000)
            studio_ids: Optional list of studio IDs to filter by
            
        Returns:
            Dictionary with count and scenes list
        """
        query = """
        query FindUnorganizedScenes(
            $filter: FindFilterType,
            $scene_filter: SceneFilterType
        ) {
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
        
        variables = {
            "filter": {
                "page": page,
                "per_page": per_page,
                "sort": "title"
            },
            "scene_filter": {
                "organized": {
                    "value": False,
                    "modifier": "EQUALS"
                }
            }
        }
        
        if studio_ids:
            variables["scene_filter"]["studios"] = {
                "value": studio_ids,
                "modifier": "INCLUDES"
            }
            
        return self.call_graphql(query, variables)

    def get_all_unorganized_scenes(
        self,
        studio_ids: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Scene]:
        """
        Get all unorganized scenes with pagination.
        
        Args:
            studio_ids: Optional list of studio IDs to filter by
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of all unorganized scenes
        """
        all_scenes = []
        page = 1
        per_page = 100
        
        while True:
            result = self.find_unorganized_scenes(
                page=page,
                per_page=per_page,
                studio_ids=studio_ids
            )
            
            scenes_data = result.get('findScenes', {})
            scenes = scenes_data.get('scenes', [])
            
            if not scenes:
                break
                
            # Convert to Scene objects
            for scene_data in scenes:
                scene = self._parse_scene_data(scene_data)
                all_scenes.append(scene)
                
            # Report progress
            if progress_callback:
                total = scenes_data.get('count', 0)
                progress_callback(len(all_scenes), total)
                
            # Check if we have more pages
            if len(all_scenes) >= scenes_data.get('count', 0):
                break
                
            page += 1
            
        return all_scenes

    def find_studio_by_name(self, name: str, exact: bool = True) -> Optional[SceneStudio]:
        """
        Find a studio by name.
        
        Args:
            name: Studio name to search for
            exact: Use exact matching (True) or fuzzy matching (False)
            
        Returns:
            SceneStudio object or None if not found
        """
        query = """
        query FindStudios($name: String!, $modifier: CriterionModifier!) {
            findStudios(
                studio_filter: {
                    name: {
                        value: $name,
                        modifier: $modifier
                    }
                }
                filter: {
                    per_page: 1
                }
            ) {
                studios {
                    id
                    name
                    aliases
                }
            }
        }
        """
        
        variables = {
            "name": name,
            "modifier": "EQUALS" if exact else "INCLUDES"
        }
        
        result = self.call_graphql(query, variables)
        studios = result.get('findStudios', {}).get('studios', [])
        
        if studios:
            studio_data = studios[0]
            return SceneStudio(
                id=studio_data['id'],
                name=studio_data['name'],
                aliases=studio_data.get('aliases', [])
            )
            
        return None

    def update_scene_metadata(
        self,
        scene_id: str,
        title: Optional[str] = None,
        date: Optional[str] = None,
        code: Optional[str] = None,
        studio_id: Optional[str] = None,
        organized: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update metadata for a single scene.
        
        Args:
            scene_id: ID of scene to update
            title: New title (optional)
            date: New date (optional)
            code: New code (optional)
            studio_id: New studio ID (optional)
            organized: New organized status (optional)
            
        Returns:
            Updated scene data or None if failed
        """
        query = """
        mutation SceneUpdate($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) {
                id
                title
                date
                code
                studio {
                    id
                    name
                }
                organized
            }
        }
        """
        
        # Build input with only provided fields
        input_data = {"id": scene_id}
        
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
            
        variables = {"input": input_data}
        
        result = self.call_graphql(query, variables)
        return result.get('sceneUpdate')

    def bulk_update_scenes(
        self,
        updates: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Update multiple scenes in bulk.
        
        Args:
            updates: List of scene update dictionaries
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of updated scene data
        """
        query = """
        mutation BulkSceneUpdate($updates: [SceneUpdateInput!]!) {
            bulkSceneUpdate(input: $updates) {
                id
                title
                date
                code
                studio {
                    id
                    name
                }
                organized
            }
        }
        """
        
        # Process in batches to avoid request size limits
        batch_size = 20
        all_results = []
        
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            variables = {"updates": batch}
            
            result = self.call_graphql(query, variables)
            batch_results = result.get('bulkSceneUpdate', [])
            all_results.extend(batch_results)
            
            # Report progress
            if progress_callback:
                progress_callback(i + len(batch), len(updates))
                
            # Small delay between batches
            if i + batch_size < len(updates):
                time.sleep(0.5)
                
        return all_results

    def _parse_scene_data(self, scene_data: Dict[str, Any]) -> Scene:
        """
        Parse GraphQL scene data into Scene object.
        
        Args:
            scene_data: Raw scene data from GraphQL
            
        Returns:
            Parsed Scene object
        """
        # Parse studio
        studio = None
        studio_data = scene_data.get('studio')
        if studio_data:
            studio = SceneStudio(
                id=studio_data['id'],
                name=studio_data['name'],
                aliases=studio_data.get('aliases', [])
            )
            
        # Parse files
        files = []
        for file_data in scene_data.get('files', []):
            parent_folder = file_data.get('parent_folder')
            files.append(SceneFile(
                id=file_data['id'],
                path=file_data['path'],
                basename=file_data['basename'],
                parent_folder_path=parent_folder.get('path') if parent_folder else None
            ))
            
        # Parse performers
        performers = []
        for performer_data in scene_data.get('performers', []):
            performers.append(ScenePerformer(
                id=performer_data['id'],
                name=performer_data['name'],
                aliases=performer_data.get('aliases', [])
            ))
            
        return Scene(
            id=scene_data['id'],
            title=scene_data.get('title'),
            date=scene_data.get('date'),
            code=scene_data.get('code'),
            studio=studio,
            files=files,
            performers=performers,
            tags=scene_data.get('tags', []),
            organized=scene_data.get('organized', False)
        )


if __name__ == '__main__':
    # Example usage
    import sys
    
    # Mock server connection for testing
    mock_connection = {
        'Scheme': 'http',
        'Port': 9999,
        'SessionCookie': {
            'Name': 'session',
            'Value': 'test-cookie'
        }
    }
    
    client = StashClient(mock_connection)
    
    # Test querying unorganized scenes
    try:
        scenes = client.get_all_unorganized_scenes()
        print(f"Found {len(scenes)} unorganized scenes")
        
        for scene in scenes[:5]:  # Show first 5
            print(f"Scene {scene.id}: {scene.files[0].basename if scene.files else 'No files'}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
```

## Key Features

### 1. Authentication
- Uses session cookies from plugin input
- Handles missing authentication gracefully
- Configurable timeout and retry logic

### 2. Scene Queries
- `find_unorganized_scenes()`: Paginated query for unorganized scenes
- `get_all_unorganized_scenes()`: Gets all unorganized scenes with progress tracking
- Supports filtering by studio IDs
- Returns structured Scene objects with all metadata

### 3. Studio Queries
- `find_studio_by_name()`: Find studio by exact or fuzzy name match
- Returns SceneStudio objects with ID, name, and aliases

### 4. Metadata Updates
- `update_scene_metadata()`: Update single scene with partial data
- `bulk_update_scenes()`: Batch update multiple scenes efficiently
- Supports updating title, date, code, studio, and organized status

### 5. Error Handling
- Exponential backoff retry logic
- Detailed error messages
- Progress callbacks for long operations

## Usage Example

```python
# Initialize client
stash = StashClient(input_data['server_connection'])

# Get unorganized scenes
def progress(current, total):
    print(f"Progress: {current}/{total} ({current/total*100:.1f}%)")

scenes = stash.get_all_unorganized_scenes(progress_callback=progress)

# Process each scene
for scene in scenes:
    # Get filename from first file
    if scene.files:
        filename = f"{scene.files[0].path}/{scene.files[0].basename}"
        
        # Parse with yansa.py
        result = parser.parse(filename)
        
        # Update if new data found
        if result.studio and not scene.studio:
            studio = stash.find_studio_by_name(result.studio)
            if studio:
                stash.update_scene_metadata(
                    scene_id=scene.id,
                    studio_id=studio.id,
                    organized=True
                )
```

## Integration Points

1. **Plugin Entry**: Initialize with server connection from plugin input
2. **Scene Discovery**: Use `get_all_unorganized_scenes()` to get candidates
3. **Data Transformation**: Extract filenames for yansa.py processing
4. **Metadata Updates**: Use `bulk_update_scenes()` for efficient updates
5. **Error Handling**: Implement callbacks for user feedback

This implementation provides a robust foundation for integrating yansa.py with the Stash API while handling authentication, pagination, and error recovery.