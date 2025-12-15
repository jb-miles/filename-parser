# Metadata Comparator Implementation

## Overview

This document provides implementation for comparing parsed metadata with existing Stash metadata to detect conflicts and provide resolution recommendations.

## File: `modules/metadata_comparator.py`

```python
#!/usr/bin/env python3
"""
Metadata comparator for comparing parsed and existing scene metadata.

This module provides intelligent comparison between yansa.py parsed metadata
and existing Stash metadata, with conflict detection and resolution
recommendations.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from modules.scene_transformer import ParsedMetadata
from modules.stash_client import Scene


@dataclass
class FieldComparison:
    """Result of comparing a single field."""
    field_name: str
    parsed_value: Optional[str]
    original_value: Optional[str]
    status: str  # 'match', 'minor_diff', 'major_diff', 'conflict', 'new_data', 'no_change'
    similarity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    recommendation: str  # 'accept_parsed', 'keep_original', 'manual_review'
    reason: Optional[str] = None


@dataclass
class ComparisonResult:
    """Complete comparison result for a scene."""
    scene_id: str
    field_comparisons: Dict[str, FieldComparison]
    overall_status: str  # 'no_conflicts', 'minor_conflicts', 'major_conflicts'
    auto_approve: bool  # Whether changes can be auto-approved
    requires_review: bool  # Whether manual review is recommended


class MetadataComparator:
    """
    Compares parsed metadata with existing Stash metadata.
    
    Provides intelligent conflict detection, similarity scoring,
    and resolution recommendations for each metadata field.
    """

    def __init__(self):
        """Initialize comparator with default configuration."""
        self.confidence_threshold = 0.8
        self.similarity_thresholds = {
            'exact_match': 1.0,
            'minor_diff': 0.9,
            'major_diff': 0.5
        }
        
        # Field-specific weights for overall comparison
        self.field_weights = {
            'studio': 0.3,
            'title': 0.3,
            'date': 0.2,
            'studio_code': 0.2
        }

    def compare_scene_metadata(
        self,
        parsed: ParsedMetadata,
        original: Scene,
        config: Optional[Dict[str, Any]] = None
    ) -> ComparisonResult:
        """
        Compare parsed metadata with original scene metadata.
        
        Args:
            parsed: ParsedMetadata from yansa.py
            original: Original Scene from Stash
            config: Optional comparison configuration
            
        Returns:
            Complete comparison result
        """
        # Update config if provided
        if config:
            self._update_config(config)
        
        # Compare each field
        field_comparisons = {}
        
        # Compare studio
        field_comparisons['studio'] = self._compare_studio(
            parsed.studio,
            original.studio.name if original.studio else None
        )
        
        # Compare title
        field_comparisons['title'] = self._compare_title(
            parsed.title,
            original.title
        )
        
        # Compare date
        field_comparisons['date'] = self._compare_date(
            parsed.date,
            original.date
        )
        
        # Compare studio code
        field_comparisons['studio_code'] = self._compare_studio_code(
            parsed.studio_code,
            original.code
        )
        
        # Determine overall status
        overall_status, auto_approve, requires_review = self._determine_overall_status(
            field_comparisons
        )
        
        return ComparisonResult(
            scene_id=original.id,
            field_comparisons=field_comparisons,
            overall_status=overall_status,
            auto_approve=auto_approve,
            requires_review=requires_review
        )

    def _compare_studio(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str]
    ) -> FieldComparison:
        """
        Compare studio names with intelligent matching.
        
        Args:
            parsed_value: Parsed studio name
            original_value: Original studio name
            
        Returns:
            Studio comparison result
        """
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name='studio',
                parsed_value=None,
                original_value=None,
                status='no_change',
                similarity=1.0,
                confidence=1.0,
                recommendation='accept_parsed',
                reason='Both values are empty'
            )
        
        if parsed_value is None:
            return FieldComparison(
                field_name='studio',
                parsed_value=None,
                original_value=original_value,
                status='no_data',
                similarity=0.0,
                confidence=0.0,
                recommendation='keep_original',
                reason='No parsed studio available'
            )
        
        if original_value is None:
            return FieldComparison(
                field_name='studio',
                parsed_value=parsed_value,
                original_value=None,
                status='new_data',
                similarity=1.0,
                confidence=0.9,
                recommendation='accept_parsed',
                reason='New studio data where original was empty'
            )
        
        # Normalize for comparison
        parsed_clean = self._normalize_studio_name(parsed_value)
        original_clean = self._normalize_studio_name(original_value)
        
        # Calculate similarity
        similarity = self._calculate_string_similarity(parsed_clean, original_clean)
        
        # Determine status and recommendation
        if similarity >= self.similarity_thresholds['exact_match']:
            status = 'match'
            recommendation = 'keep_original'
            reason = 'Studio names match exactly'
        elif similarity >= self.similarity_thresholds['minor_diff']:
            status = 'minor_diff'
            recommendation = 'accept_parsed' if len(parsed_value) > len(original_value) else 'keep_original'
            reason = 'Studio names are very similar'
        elif similarity >= self.similarity_thresholds['major_diff']:
            status = 'major_diff'
            recommendation = 'manual_review'
            reason = 'Studio names have significant differences'
        else:
            status = 'conflict'
            recommendation = 'manual_review'
            reason = 'Studio names are completely different'
        
        return FieldComparison(
            field_name='studio',
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
                confidence=min(0.9, similarity),
            recommendation=recommendation,
            reason=reason
        )

    def _compare_title(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str]
    ) -> FieldComparison:
        """
        Compare titles with normalization.
        
        Args:
            parsed_value: Parsed title
            original_value: Original title
            
        Returns:
            Title comparison result
        """
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name='title',
                parsed_value=None,
                original_value=None,
                status='no_change',
                similarity=1.0,
                confidence=1.0,
                recommendation='accept_parsed',
                reason='Both values are empty'
            )
        
        if parsed_value is None:
            return FieldComparison(
                field_name='title',
                parsed_value=None,
                original_value=original_value,
                status='no_data',
                similarity=0.0,
                confidence=0.0,
                recommendation='keep_original',
                reason='No parsed title available'
            )
        
        if original_value is None:
            return FieldComparison(
                field_name='title',
                parsed_value=parsed_value,
                original_value=None,
                status='new_data',
                similarity=1.0,
                confidence=0.7,
                recommendation='accept_parsed',
                reason='New title data where original was empty'
            )
        
        # Normalize for comparison
        parsed_clean = self._normalize_title(parsed_value)
        original_clean = self._normalize_title(original_value)
        
        # Calculate similarity
        similarity = self._calculate_string_similarity(parsed_clean, original_clean)
        
        # Determine status and recommendation
        if similarity >= self.similarity_thresholds['exact_match']:
            status = 'match'
            recommendation = 'keep_original'
            reason = 'Titles match exactly'
        elif similarity >= self.similarity_thresholds['minor_diff']:
            status = 'minor_diff'
            recommendation = 'accept_parsed' if len(parsed_value) > len(original_value) else 'keep_original'
            reason = 'Titles are very similar'
        elif similarity >= self.similarity_thresholds['major_diff']:
            status = 'major_diff'
            recommendation = 'manual_review'
            reason = 'Titles have significant differences'
        else:
            status = 'conflict'
            recommendation = 'manual_review'
            reason = 'Titles are completely different'
        
        return FieldComparison(
            field_name='title',
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
            confidence=min(0.7, similarity),
            recommendation=recommendation,
            reason=reason
        )

    def _compare_date(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str]
    ) -> FieldComparison:
        """
        Compare dates with format normalization.
        
        Args:
            parsed_value: Parsed date
            original_value: Original date
            
        Returns:
            Date comparison result
        """
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name='date',
                parsed_value=None,
                original_value=None,
                status='no_change',
                similarity=1.0,
                confidence=1.0,
                recommendation='accept_parsed',
                reason='Both values are empty'
            )
        
        if parsed_value is None:
            return FieldComparison(
                field_name='date',
                parsed_value=None,
                original_value=original_value,
                status='no_data',
                similarity=0.0,
                confidence=0.0,
                recommendation='keep_original',
                reason='No parsed date available'
            )
        
        if original_value is None:
            return FieldComparison(
                field_name='date',
                parsed_value=parsed_value,
                original_value=None,
                status='new_data',
                similarity=1.0,
                confidence=0.8,
                recommendation='accept_parsed',
                reason='New date data where original was empty'
            )
        
        # Parse dates to normalized format
        parsed_date = self._parse_date(parsed_value)
        original_date = self._parse_date(original_value)
        
        if parsed_date is None or original_date is None:
            # Fallback to string comparison
            similarity = self._calculate_string_similarity(parsed_value, original_value)
            status = 'conflict' if similarity < 0.8 else 'major_diff'
            recommendation = 'manual_review'
            reason = 'Date format could not be normalized'
        else:
            # Compare normalized dates
            if parsed_date == original_date:
                status = 'match'
                similarity = 1.0
                recommendation = 'keep_original'
                reason = 'Dates match exactly'
            else:
                # Calculate date difference
                days_diff = abs((parsed_date - original_date).days)
                
                if days_diff <= 1:
                    status = 'minor_diff'
                    similarity = 0.95
                    recommendation = 'accept_parsed'
                    reason = 'Dates differ by 1 day or less'
                elif days_diff <= 7:
                    status = 'major_diff'
                    similarity = 0.8
                    recommendation = 'manual_review'
                    reason = 'Dates differ by less than a week'
                else:
                    status = 'conflict'
                    similarity = 0.3
                    recommendation = 'manual_review'
                    reason = 'Dates differ by more than a week'
        
        return FieldComparison(
            field_name='date',
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity if 'similarity' in locals() else 0.0,
            confidence=0.8 if parsed_date else 0.0,
            recommendation=recommendation,
            reason=reason
        )

    def _compare_studio_code(
        self,
        parsed_value: Optional[str],
        original_value: Optional[str]
    ) -> FieldComparison:
        """
        Compare studio codes with pattern matching.
        
        Args:
            parsed_value: Parsed studio code
            original_value: Original studio code
            
        Returns:
            Studio code comparison result
        """
        if parsed_value is None and original_value is None:
            return FieldComparison(
                field_name='studio_code',
                parsed_value=None,
                original_value=None,
                status='no_change',
                similarity=1.0,
                confidence=1.0,
                recommendation='accept_parsed',
                reason='Both values are empty'
            )
        
        if parsed_value is None:
            return FieldComparison(
                field_name='studio_code',
                parsed_value=None,
                original_value=original_value,
                status='no_data',
                similarity=0.0,
                confidence=0.0,
                recommendation='keep_original',
                reason='No parsed studio code available'
            )
        
        if original_value is None:
            return FieldComparison(
                field_name='studio_code',
                parsed_value=parsed_value,
                original_value=None,
                status='new_data',
                similarity=1.0,
                confidence=0.8,
                recommendation='accept_parsed',
                reason='New studio code data where original was empty'
            )
        
        # Normalize codes (remove spaces, uppercase)
        parsed_clean = re.sub(r'\s+', '', parsed_value.upper())
        original_clean = re.sub(r'\s+', '', original_value.upper())
        
        # Calculate similarity
        similarity = self._calculate_string_similarity(parsed_clean, original_clean)
        
        # Determine status and recommendation
        if similarity >= self.similarity_thresholds['exact_match']:
            status = 'match'
            recommendation = 'keep_original'
            reason = 'Studio codes match exactly'
        elif similarity >= self.similarity_thresholds['minor_diff']:
            status = 'minor_diff'
            recommendation = 'accept_parsed' if len(parsed_value) > len(original_value) else 'keep_original'
            reason = 'Studio codes are very similar'
        elif similarity >= self.similarity_thresholds['major_diff']:
            status = 'major_diff'
            recommendation = 'manual_review'
            reason = 'Studio codes have significant differences'
        else:
            status = 'conflict'
            recommendation = 'manual_review'
            reason = 'Studio codes are completely different'
        
        return FieldComparison(
            field_name='studio_code',
            parsed_value=parsed_value,
            original_value=original_value,
            status=status,
            similarity=similarity,
            confidence=min(0.8, similarity),
            recommendation=recommendation,
            reason=reason
        )

    def _determine_overall_status(
        self,
        field_comparisons: Dict[str, FieldComparison]
    ) -> Tuple[str, bool, bool]:
        """
        Determine overall comparison status from field comparisons.
        
        Args:
            field_comparisons: Dictionary of field comparison results
            
        Returns:
            Tuple of (overall_status, auto_approve, requires_review)
        """
        has_major_conflicts = False
        has_minor_conflicts = False
        has_new_data = False
        
        for comparison in field_comparisons.values():
            if comparison.status in ['major_diff', 'conflict']:
                has_major_conflicts = True
            elif comparison.status == 'minor_diff':
                has_minor_conflicts = True
            elif comparison.status == 'new_data':
                has_new_data = True
        
        # Determine overall status
        if has_major_conflicts:
            overall_status = 'major_conflicts'
            auto_approve = False
            requires_review = True
        elif has_minor_conflicts:
            overall_status = 'minor_conflicts'
            auto_approve = not has_new_data  # Auto-approve if no new data
            requires_review = True
        elif has_new_data:
            overall_status = 'no_conflicts'
            auto_approve = True
            requires_review = False
        else:
            overall_status = 'no_conflicts'
            auto_approve = True
            requires_review = False
        
        return overall_status, auto_approve, requires_review

    def _normalize_studio_name(self, name: str) -> str:
        """
        Normalize studio name for comparison.
        
        Args:
            name: Studio name to normalize
            
        Returns:
            Normalized studio name
        """
        if not name:
            return ""
        
        # Remove common suffixes/prefixes
        normalized = name.lower()
        normalized = re.sub(r'\b(studio|productions|entertainment)\b', '', normalized)
        normalized = re.sub(r'[^a-z0-9]', '', normalized)
        
        return normalized.strip()

    def _normalize_title(self, title: str) -> str:
        """
        Normalize title for comparison.
        
        Args:
            title: Title to normalize
            
        Returns:
            Normalized title
        """
        if not title:
            return ""
        
        # Normalize whitespace and case
        normalized = re.sub(r'\s+', ' ', title.lower().strip())
        
        # Remove common punctuation for comparison
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Datetime object or None if parsing fails
        """
        if not date_str:
            return None
        
        # Common date formats
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%m/%d/%Y',
            '%d-%m-%Y',
            '%d.%m.%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y',
            '%m-%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None

    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using Levenshtein distance.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if str1 == str2:
            return 1.0
        
        len1, len2 = len(str1), len(str2)
        if len1 == 0:
            return 0.0 if len2 > 0 else 1.0
        if len2 == 0:
            return 0.0
        
        # Initialize matrix for Levenshtein distance
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

    def _update_config(self, config: Dict[str, Any]) -> None:
        """
        Update comparator configuration.
        
        Args:
            config: New configuration values
        """
        if 'confidence_threshold' in config:
            self.confidence_threshold = config['confidence_threshold']
        
        if 'similarity_thresholds' in config:
            self.similarity_thresholds.update(config['similarity_thresholds'])
        
        if 'field_weights' in config:
            self.field_weights.update(config['field_weights'])


if __name__ == '__main__':
    # Example usage
    from modules.stash_client import Scene, SceneStudio
    
    # Create mock data
    parsed = ParsedMetadata(
        studio="UKNM",
        title="AJ Alexander & Brent Taylor",
        date="2024-01-15",
        studio_code="UKNM-001"
    )
    
    original = Scene(
        id="8447",
        title="AJ Alexander & Brent Taylor",
        date="2024-01-14",
        code="UKNM001",
        studio=SceneStudio(id="1", name="UKNM"),
        files=[],
        performers=[],
        tags=[],
        organized=False
    )
    
    comparator = MetadataComparator()
    result = comparator.compare_scene_metadata(parsed, original)
    
    print(f"Overall status: {result.overall_status}")
    print(f"Auto approve: {result.auto_approve}")
    print(f"Requires review: {result.requires_review}")
    
    for field, comparison in result.field_comparisons.items():
        print(f"\n{field}:")
        print(f"  Status: {comparison.status}")
        print(f"  Similarity: {comparison.similarity:.2f}")
        print(f"  Recommendation: {comparison.recommendation}")
        print(f"  Reason: {comparison.reason}")
```

## Key Features

### 1. Field-Specific Comparison
- **Studio**: Intelligent name normalization and matching
- **Title**: Text normalization and similarity scoring
- **Date**: Format parsing and chronological comparison
- **Studio Code**: Pattern normalization and exact matching

### 2. Conflict Classification
- **no_change**: Values are identical
- **new_data**: Parsed value where original is empty
- **match**: Values match after normalization
- **minor_diff**: Small differences (>90% similarity)
- **major_diff**: Significant differences (50-90% similarity)
- **conflict**: Completely different values (<50% similarity)

### 3. Resolution Recommendations
- **accept_parsed**: Use parsed value
- **keep_original**: Keep existing value
- **manual_review**: Requires user decision

### 4. Overall Status Determination
- **no_conflicts**: No issues found
- **minor_conflicts**: Only minor differences
- **major_conflicts**: Significant conflicts present

### 5. Intelligent Normalization
- Studio name suffix/prefix removal
- Title punctuation and whitespace normalization
- Date format parsing and standardization
- Studio code pattern matching

## Configuration Options

```python
config = {
    'confidence_threshold': 0.8,  # Minimum confidence for auto-approval
    'similarity_thresholds': {
        'exact_match': 1.0,
        'minor_diff': 0.9,
        'major_diff': 0.5
    },
    'field_weights': {
        'studio': 0.3,
        'title': 0.3,
        'date': 0.2,
        'studio_code': 0.2
    }
}
```

## Integration Example

```python
# Initialize comparator
comparator = MetadataComparator()

# Compare parsed metadata with original
result = comparator.compare_scene_metadata(parsed, original)

# Check if auto-approval is recommended
if result.auto_approve:
    # Apply changes automatically
    update_data = transformer.metadata_to_update(
        result.scene_id,
        parsed,
        result.field_comparisons
    )
    stash.update_scene_metadata(**update_data)
else:
    # Show review interface
    show_review_interface(result)
```

This comparator provides intelligent conflict detection and resolution recommendations, enabling automated processing when safe and manual review when needed.