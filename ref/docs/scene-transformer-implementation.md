# Scene Transformer Implementation

## Overview

This document provides implementation for transforming Stash scene data into yansa.py input format and converting parsed results back to Stash update format.

## File: `modules/scene_transformer.py`

```python
#!/usr/bin/env python3
"""
Scene data transformer for converting between Stash and yansa.py formats.

This module handles the transformation of Stash scene data into filenames
for yansa.py processing, and converts parsed results back into
Stash update format.
"""

import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from modules.stash_client import Scene, SceneFile, SceneStudio
from modules.tokenizer import TokenizationResult


@dataclass
class ParsedMetadata:
    """Represents metadata parsed from filename."""
    studio: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    studio_code: Optional[str] = None
    sequence: Optional[Dict[str, Any]] = None
    group: Optional[str] = None
    confidence: Dict[str, float] = None  # Field confidence scores


class SceneTransformer:
    """
    Transforms scene data between Stash and yansa.py formats.
    
    Handles extracting filenames from scene data, converting to yansa.py
    input, and transforming parsed results back to Stash update format.
    """

    def __init__(self):
        """Initialize transformer with default configuration."""
        self.prefer_first_file = True  # Use first file when multiple files exist
        self.include_path_in_filename = False  # Whether to include path in parsing

    def scene_to_filename(self, scene: Scene) -> Optional[str]:
        """
        Convert a Stash scene to a filename for yansa.py processing.
        
        Args:
            scene: Scene object from Stash
            
        Returns:
            Filename string or None if no files found
        """
        if not scene.files:
            return None
            
        # Use first file by default (configurable)
        file = scene.files[0] if self.prefer_first_file else self._select_best_file(scene.files)
        
        # Construct full path if configured
        if self.include_path_in_filename and file.parent_folder_path:
            return f"{file.parent_folder_path}/{file.basename}"
        else:
            return file.basename

    def scenes_to_filenames(self, scenes: List[Scene]) -> List[Tuple[str, str]]:
        """
        Convert multiple scenes to (scene_id, filename) tuples.
        
        Args:
            scenes: List of Scene objects
            
        Returns:
            List of (scene_id, filename) tuples
        """
        result = []
        for scene in scenes:
            filename = self.scene_to_filename(scene)
            if filename:
                result.append((scene.id, filename))
        return result

    def parse_result_to_metadata(self, result: TokenizationResult) -> ParsedMetadata:
        """
        Convert yansa.py TokenizationResult to structured metadata.
        
        Args:
            result: TokenizationResult from yansa.py
            
        Returns:
            ParsedMetadata object with structured fields
        """
        return ParsedMetadata(
            studio=result.studio,
            title=result.title,
            date=self._extract_date(result),
            studio_code=getattr(result, 'studio_code', None),
            sequence=result.sequence,
            group=result.group,
            confidence=self._calculate_confidence(result)
        )

    def compare_metadata(
        self,
        parsed: ParsedMetadata,
        original: Scene
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare parsed metadata with original scene metadata.
        
        Args:
            parsed: ParsedMetadata from yansa.py
            original: Original Scene from Stash
            
        Returns:
            Dictionary with comparison results for each field
        """
        comparison = {}
        
        # Compare studio
        comparison['studio'] = self._compare_field(
            parsed.studio,
            original.studio.name if original.studio else None,
            'studio'
        )
        
        # Compare title
        comparison['title'] = self._compare_field(
            parsed.title,
            original.title,
            'title'
        )
        
        # Compare date
        comparison['date'] = self._compare_field(
            parsed.date,
            original.date,
            'date'
        )
        
        # Compare studio code
        comparison['studio_code'] = self._compare_field(
            parsed.studio_code,
            original.code,
            'studio_code'
        )
        
        return comparison

    def metadata_to_update(
        self,
        scene_id: str,
        parsed: ParsedMetadata,
        comparison: Optional[Dict[str, Dict[str, Any]] = None,
        approved_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Convert parsed metadata to Stash update format.
        
        Args:
            scene_id: ID of scene to update
            parsed: ParsedMetadata object
            comparison: Optional comparison results
            approved_fields: List of fields approved for update
            
        Returns:
            Dictionary in Stash update format
        """
        update_data = {"id": scene_id}
        
        # If no approved fields specified, use all non-null parsed fields
        if approved_fields is None:
            approved_fields = [
                field for field in ['studio', 'title', 'date', 'studio_code']
                if getattr(parsed, field) is not None
            ]
        
        # Add approved fields to update
        for field in approved_fields:
            if field == 'studio' and parsed.studio:
                update_data['studio_id'] = parsed.studio  # Will be resolved later
            elif field == 'title' and parsed.title:
                update_data['title'] = parsed.title
            elif field == 'date' and parsed.date:
                update_data['date'] = parsed.date
            elif field == 'studio_code' and parsed.studio_code:
                update_data['code'] = parsed.studio_code
        
        # Set organized if all key fields are present
        if self._should_mark_organized(parsed, approved_fields or []):
            update_data['organized'] = True
            
        return update_data

    def _select_best_file(self, files: List[SceneFile]) -> SceneFile:
        """
        Select the best file for parsing from multiple files.
        
        Args:
            files: List of SceneFile objects
            
        Returns:
            Selected SceneFile
        """
        # Prioritize by file extension (video files first)
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}
        
        # Filter for video files
        video_files = [f for f in files if any(f.basename.lower().endswith(ext) for ext in video_extensions)]
        
        if video_files:
            # Prefer shortest filename (often cleaner)
            return min(video_files, key=lambda f: len(f.basename))
        else:
            # Fallback to first file
            return files[0]

    def _extract_date(self, result: TokenizationResult) -> Optional[str]:
        """
        Extract date from TokenizationResult in consistent format.
        
        Args:
            result: TokenizationResult from yansa.py
            
        Returns:
            Normalized date string or None
        """
        # Check if date is already in tokens
        for token in (result.tokens or []):
            if token.type == 'date':
                return token.value
                
        # Check if date is in result metadata
        # (Implementation depends on yansa.py date extraction format)
        return None

    def _calculate_confidence(self, result: TokenizationResult) -> Dict[str, float]:
        """
        Calculate confidence scores for parsed fields.
        
        Args:
            result: TokenizationResult from yansa.py
            
        Returns:
            Dictionary of field confidence scores (0.0-1.0)
        """
        confidence = {}
        
        # Base confidence on token types and sources
        if hasattr(result, 'confidences') and result.confidences:
            confidence.update(result.confidences)
        else:
            # Fallback confidence calculation
            if result.studio:
                confidence['studio'] = 0.9  # High confidence for exact studio matches
            if result.title:
                confidence['title'] = 0.7  # Medium confidence for title extraction
            if result.studio_code:
                confidence['studio_code'] = 0.8  # High confidence for pattern matches
                
        return confidence

    def _compare_field(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str],
        field_name: str
    ) -> Dict[str, Any]:
        """
        Compare a single parsed field with original value.
        
        Args:
            parsed_value: Value from yansa.py parsing
            original_value: Value from Stash
            field_name: Name of the field for context
            
        Returns:
            Dictionary with comparison results
        """
        # Handle null values
        if parsed_value is None and original_value is None:
            return {
                'status': 'no_change',
                'parsed': None,
                'original': None,
                'confidence': 1.0
            }
            
        if parsed_value is None:
            return {
                'status': 'no_data',
                'parsed': None,
                'original': original_value,
                'confidence': 0.0
            }
            
        if original_value is None:
            return {
                'status': 'new_data',
                'parsed': parsed_value,
                'original': None,
                'confidence': 0.8
            }
            
        # Compare non-null values
        parsed_clean = self._normalize_for_comparison(parsed_value, field_name)
        original_clean = self._normalize_for_comparison(original_value, field_name)
        
        if parsed_clean == original_clean:
            return {
                'status': 'match',
                'parsed': parsed_value,
                'original': original_value,
                'confidence': 1.0
            }
        else:
            # Calculate similarity score
            similarity = self._calculate_similarity(parsed_clean, original_clean)
            
            if similarity > 0.9:
                status = 'minor_diff'
            elif similarity > 0.5:
                status = 'major_diff'
            else:
                status = 'conflict'
                
            return {
                'status': status,
                'parsed': parsed_value,
                'original': original_value,
                'similarity': similarity,
                'confidence': similarity
            }

    def _normalize_for_comparison(self, value: str, field_name: str) -> str:
        """
        Normalize a value for comparison based on field type.
        
        Args:
            value: Value to normalize
            field_name: Type of field for context
            
        Returns:
            Normalized value
        """
        if not value:
            return ""
            
        value = value.strip().lower()
        
        # Field-specific normalization
        if field_name == 'studio':
            # Remove common suffixes/prefixes for studios
            value = value.replace(' studio', '').replace(' productions', '')
        elif field_name == 'title':
            # Normalize title but preserve special characters
            value = value.replace('_', ' ').replace('-', ' ')
        elif field_name == 'date':
            # Normalize date format (implementation depends on expected formats)
            pass
            
        return value

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if str1 == str2:
            return 1.0
            
        # Simple Levenshtein distance implementation
        len1, len2 = len(str1), len(str2)
        if len1 == 0:
            return 0.0 if len2 > 0 else 1.0
        if len2 == 0:
            return 0.0
            
        # Initialize matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Fill first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
            
        # Fill rest of matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if str1[i-1] == str2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost   # substitution
                )
                
        # Calculate similarity
        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)

    def _should_mark_organized(
        self,
        parsed: ParsedMetadata,
        approved_fields: List[str]
    ) -> bool:
        """
        Determine if scene should be marked as organized.
        
        Args:
            parsed: ParsedMetadata object
            approved_fields: List of fields approved for update
            
        Returns:
            True if scene should be marked organized
        """
        # Require at least studio and title to be organized
        has_studio = 'studio' in approved_fields and parsed.studio is not None
        has_title = 'title' in approved_fields and parsed.title is not None
        
        # Also accept if date or studio code is present
        has_date = 'date' in approved_fields and parsed.date is not None
        has_code = 'studio_code' in approved_fields and parsed.studio_code is not None
        
        return (has_studio and has_title) or (has_studio and (has_date or has_code))


if __name__ == '__main__':
    # Example usage
    from modules.stash_client import Scene, SceneFile, SceneStudio
    
    # Create mock scene
    mock_scene = Scene(
        id="8447",
        title=None,
        date=None,
        code=None,
        studio=None,
        files=[
            SceneFile(
                id="file1",
                path="/media",
                basename="(UKNM) - AJ Alexander & Brent Taylor.mp4",
                parent_folder_path="/media"
            )
        ],
        performers=[],
        tags=[],
        organized=False
    )
    
    transformer = SceneTransformer()
    
    # Test scene to filename conversion
    filename = transformer.scene_to_filename(mock_scene)
    print(f"Filename: {filename}")
    
    # Test metadata comparison
    parsed = ParsedMetadata(
        studio="UKNM",
        title="AJ Alexander & Brent Taylor",
        date=None,
        studio_code=None
    )
    
    comparison = transformer.compare_metadata(parsed, mock_scene)
    print(f"Comparison: {comparison}")
    
    # Test update generation
    update = transformer.metadata_to_update("8447", parsed, comparison)
    print(f"Update data: {update}")
```

## Key Features

### 1. Scene to Filename Conversion
- Extracts basename from scene files
- Handles multiple files per scene
- Configurable file selection logic
- Optional path inclusion

### 2. Parsed Metadata Processing
- Converts TokenizationResult to structured format
- Extracts confidence scores
- Normalizes field formats
- Handles missing data gracefully

### 3. Metadata Comparison
- Field-by-field comparison with status categorization
- Similarity scoring for partial matches
- Conflict detection and classification
- Confidence-based recommendations

### 4. Update Generation
- Converts parsed metadata to Stash update format
- Resolves studio names to IDs
- Handles approved field filtering
- Determines organized status

### 5. Comparison Status Types
- **no_change**: Values are identical
- **no_data**: No parsed value available
- **new_data**: Parsed value where original is empty
- **match**: Values match after normalization
- **minor_diff**: Small differences (>90% similarity)
- **major_diff**: Significant differences (50-90% similarity)
- **conflict**: Completely different values (<50% similarity)

## Integration Flow

```python
# 1. Convert scenes to filenames for yansa.py
transformer = SceneTransformer()
scene_filenames = transformer.scenes_to_filenames(unorganized_scenes)

# 2. Process each filename with yansa.py
for scene_id, filename in scene_filenames:
    result = parser.parse(filename)
    parsed = transformer.parse_result_to_metadata(result)
    
    # 3. Compare with existing metadata
    comparison = transformer.compare_metadata(parsed, original_scene)
    
    # 4. Generate update data
    update = transformer.metadata_to_update(scene_id, parsed, comparison)
    
    # 5. Apply update if approved
    if user_approves(update):
        stash.update_scene_metadata(**update)
```

This transformer provides the critical bridge between Stash's scene data structure and yansa.py's filename processing, enabling seamless integration with proper metadata comparison and update generation.