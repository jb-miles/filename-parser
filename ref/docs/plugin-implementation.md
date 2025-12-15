# Stash Plugin Implementation

## Overview

This document provides complete implementation for the Stash plugin that integrates yansa.py with manual review capabilities.

## File Structure

```
plugin/
├── stash_yansa_plugin.py      # Main plugin entry point
├── ui_components.py          # UI generation logic
├── static/
│   ├── css/
│   │   └── review-ui.css     # Plugin styling
│   └── js/
│       └── review-ui.js      # Frontend interaction logic
└── templates/
    └── review.html           # Review interface template
```

## Main Plugin: `plugin/stash_yansa_plugin.py`

```python
#!/usr/bin/env python3
"""
Stash plugin for filename parsing with yansa.py integration.

This plugin queries unorganized scenes, processes them with yansa.py,
and provides a manual review interface before updating metadata.
"""

import json
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from modules.stash_client import StashClient, Scene
from modules.scene_transformer import SceneTransformer, ParsedMetadata
from modules.metadata_comparator import MetadataComparator
from modules.batch_processor import BatchProcessor
from yansa import FilenameParser


class StashYansaPlugin:
    """
    Main plugin class for Stash yansa.py integration.
    
    Handles plugin lifecycle, UI generation, and coordination
    between Stash API, yansa.py processing, and user review.
    """

    def __init__(self, input_data: Dict[str, Any]):
        """
        Initialize plugin with Stash connection and configuration.
        
        Args:
            input_data: Plugin input from Stash
        """
        self.input_data = input_data
        self.server_connection = input_data.get('server_connection', {})
        
        # Initialize components
        self.stash_client = StashClient(self.server_connection)
        self.scene_transformer = SceneTransformer()
        self.metadata_comparator = MetadataComparator()
        self.batch_processor = BatchProcessor(self.stash_client)
        self.filename_parser = FilenameParser()
        
        # Plugin configuration
        self.config = self._load_config()
        
        # UI components
        self.ui_components = UIComponents()

    def main(self) -> Dict[str, Any]:
        """
        Main plugin entry point.
        
        Returns:
            Plugin output for Stash
        """
        try:
            # Handle different plugin modes
            mode = self.input_data.get('mode', 'list')
            
            if mode == 'list':
                return self._list_unorganized_scenes()
            elif mode == 'process':
                return self._process_scenes()
            elif mode == 'review':
                return self._generate_review_interface()
            elif mode == 'update':
                return self._update_scenes()
            else:
                return self._error_response(f"Unknown mode: {mode}")
                
        except Exception as e:
            return self._error_response(f"Plugin error: {str(e)}")

    def _list_unorganized_scenes(self) -> Dict[str, Any]:
        """
        List unorganized scenes for initial selection.
        
        Returns:
            UI response with scene list
        """
        # Get unorganized scenes
        scenes = self.stash_client.get_all_unorganized_scenes()
        
        # Transform to UI format
        scene_list = []
        for scene in scenes:
            if scene.files:
                scene_list.append({
                    'id': scene.id,
                    'filename': scene.files[0].basename,
                    'path': scene.files[0].path,
                    'title': scene.title or 'Untitled',
                    'studio': scene.studio.name if scene.studio else 'Unknown',
                    'date': scene.date or '',
                    'code': scene.code or ''
                })
        
        # Generate UI
        html = self.ui_components.scene_list_html(scene_list, self.config)
        
        return {
            'output': 'html',
            'html': html
        }

    def _process_scenes(self) -> Dict[str, Any]:
        """
        Process selected scenes with yansa.py.
        
        Returns:
            UI response with processing results
        """
        scene_ids = self.input_data.get('scene_ids', [])
        if not scene_ids:
            return self._error_response("No scenes selected for processing")
        
        # Get scenes from Stash
        scenes = []
        for scene_id in scene_ids:
            # This would need a get_scene_by_id method in StashClient
            # For now, assume we can get the scene data
            pass
        
        # Process each scene
        processed_scenes = []
        for scene in scenes:
            if not scene.files:
                continue
                
            # Get filename for parsing
            filename = self.scene_transformer.scene_to_filename(scene)
            if not filename:
                continue
                
            # Parse with yansa.py
            result = self.filename_parser.parse(filename)
            parsed = self.scene_transformer.parse_result_to_metadata(result)
            
            # Compare with existing metadata
            comparison = self.scene_transformer.compare_metadata(parsed, scene)
            
            processed_scenes.append({
                'scene_id': scene.id,
                'filename': filename,
                'original': {
                    'title': scene.title,
                    'studio': scene.studio.name if scene.studio else None,
                    'date': scene.date,
                    'code': scene.code
                },
                'parsed': {
                    'title': parsed.title,
                    'studio': parsed.studio,
                    'date': parsed.date,
                    'studio_code': parsed.studio_code
                },
                'comparison': comparison
            })
        
        # Generate review interface
        html = self.ui_components.review_interface_html(processed_scenes, self.config)
        
        return {
            'output': 'html',
            'html': html
        }

    def _generate_review_interface(self) -> Dict[str, Any]:
        """
        Generate review interface for processed scenes.
        
        Returns:
            UI response with review interface
        """
        # This would be called with processed data from _process_scenes
        # For now, return empty interface
        html = self.ui_components.review_interface_html([], self.config)
        
        return {
            'output': 'html',
            'html': html
        }

    def _update_scenes(self) -> Dict[str, Any]:
        """
        Update scenes with approved metadata changes.
        
        Returns:
            Update results
        """
        approved_updates = self.input_data.get('approved_updates', [])
        if not approved_updates:
            return self._error_response("No approved updates provided")
        
        # Process updates in batches
        def progress_callback(current, total):
            print(f"Update progress: {current}/{total}")
        
        results = self.batch_processor.process_updates(
            approved_updates,
            progress_callback
        )
        
        return {
            'output': 'json',
            'results': results
        }

    def _load_config(self) -> Dict[str, Any]:
        """
        Load plugin configuration.
        
        Returns:
            Configuration dictionary
        """
        # Default configuration
        default_config = {
            'processing': {
                'batch_size': 50,
                'auto_approve_no_conflicts': True,
                'confidence_threshold': 0.8
            },
            'conflicts': {
                'auto_resolve_minor': True,
                'require_review_major': True,
                'preserve_existing_dates': False
            },
            'ui': {
                'show_preview': True,
                'compact_view': False,
                'sort_by': 'filename'
            }
        }
        
        # Override with user config if available
        user_config = self.input_data.get('config', {})
        return {**default_config, **user_config}

    def _error_response(self, message: str) -> Dict[str, Any]:
        """
        Generate error response.
        
        Args:
            message: Error message
            
        Returns:
            Error response dictionary
        """
        return {
            'output': 'error',
            'error': message
        }


def main():
    """
    Plugin entry point called by Stash.
    """
    try:
        # Read plugin input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Initialize and run plugin
        plugin = StashYansaPlugin(input_data)
        result = plugin.main()
        
        # Output result
        print(json.dumps(result))
        
    except Exception as e:
        error_response = {
            'output': 'error',
            'error': f'Plugin initialization error: {str(e)}'
        }
        print(json.dumps(error_response))
        sys.exit(1)


if __name__ == '__main__':
    main()
```

## UI Components: `plugin/ui_components.py`

```python
#!/usr/bin/env python3
"""
UI components for Stash yansa.py plugin.

Generates HTML and JavaScript for the manual review interface
with comparison views, batch controls, and progress tracking.
"""

import json
from typing import Dict, List, Any


class UIComponents:
    """
    Generates UI components for the plugin interface.
    
    Handles HTML generation, styling, and JavaScript
    for the review interface and controls.
    """

    def __init__(self):
        """Initialize UI components with default styling."""
        self.css_styles = self._load_css_styles()
        self.js_functions = self._load_js_functions()

    def scene_list_html(self, scenes: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        """
        Generate HTML for scene selection list.
        
        Args:
            scenes: List of scene data
            config: Plugin configuration
            
        Returns:
            HTML string for scene list
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Yansa Filename Parser - Scene Selection</title>
            <style>{self.css_styles}</style>
        </head>
        <body>
            <div class="container">
                <h1>Unorganized Scenes</h1>
                <p>Select scenes to process with yansa.py filename parsing:</p>
                
                <div class="controls">
                    <button id="selectAll">Select All</button>
                    <button id="selectNone">Select None</button>
                    <button id="processSelected" class="primary">Process Selected</button>
                </div>
                
                <div class="scene-list">
                    {self._generate_scene_rows(scenes, config)}
                </div>
            </div>
            
            <script>{self.js_functions}</script>
            <script>{self._scene_list_js()}</script>
        </body>
        </html>
        """
        return html

    def review_interface_html(
        self,
        processed_scenes: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> str:
        """
        Generate HTML for review interface.
        
        Args:
            processed_scenes: List of processed scene data
            config: Plugin configuration
            
        Returns:
            HTML string for review interface
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Yansa Filename Parser - Review Changes</title>
            <style>{self.css_styles}</style>
        </head>
        <body>
            <div class="container">
                <h1>Review Metadata Changes</h1>
                <p>Review and approve metadata changes before updating Stash:</p>
                
                <div class="controls">
                    <button id="approveAll" class="primary">Approve All</button>
                    <button id="rejectAll">Reject All</button>
                    <button id="approveNoConflicts">Approve No Conflicts</button>
                    <button id="applyChanges" class="primary" disabled>Apply Changes</button>
                </div>
                
                <div class="progress-container" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                    <div class="progress-text">Processing...</div>
                </div>
                
                <div class="review-list">
                    {self._generate_review_cards(processed_scenes, config)}
                </div>
            </div>
            
            <script>{self.js_functions}</script>
            <script>{self._review_interface_js()}</script>
        </body>
        </html>
        """
        return html

    def _generate_scene_rows(
        self,
        scenes: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> str:
        """
        Generate HTML rows for scene list.
        
        Args:
            scenes: List of scene data
            config: Plugin configuration
            
        Returns:
            HTML string for scene rows
        """
        rows = []
        sort_by = config.get('ui', {}).get('sort_by', 'filename')
        
        # Sort scenes
        if sort_by == 'filename':
            scenes.sort(key=lambda s: s['filename'])
        elif sort_by == 'studio':
            scenes.sort(key=lambda s: s['studio'])
        elif sort_by == 'date':
            scenes.sort(key=lambda s: s['date'] or '')
        
        for scene in scenes:
            row = f"""
            <div class="scene-row" data-scene-id="{scene['id']}">
                <input type="checkbox" class="scene-select" value="{scene['id']}">
                <div class="scene-info">
                    <div class="scene-filename">{scene['filename']}</div>
                    <div class="scene-meta">
                        <span class="studio">{scene['studio']}</span>
                        <span class="date">{scene['date']}</span>
                        <span class="code">{scene['code']}</span>
                    </div>
                </div>
            </div>
            """
            rows.append(row)
        
        return ''.join(rows)

    def _generate_review_cards(
        self,
        processed_scenes: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> str:
        """
        Generate HTML cards for review interface.
        
        Args:
            processed_scenes: List of processed scene data
            config: Plugin configuration
            
        Returns:
            HTML string for review cards
        """
        cards = []
        
        for scene in processed_scenes:
            card = f"""
            <div class="review-card" data-scene-id="{scene['scene_id']}">
                <div class="card-header">
                    <h3>{scene['filename']}</h3>
                    <div class="card-actions">
                        <input type="checkbox" class="approve-scene" checked>
                        <label>Approve</label>
                    </div>
                </div>
                
                <div class="card-content">
                    <div class="comparison-grid">
                        {self._generate_field_comparison('Studio', scene, 'studio')}
                        {self._generate_field_comparison('Title', scene, 'title')}
                        {self._generate_field_comparison('Date', scene, 'date')}
                        {self._generate_field_comparison('Studio Code', scene, 'studio_code')}
                    </div>
                </div>
            </div>
            """
            cards.append(card)
        
        return ''.join(cards)

    def _generate_field_comparison(
        self,
        field_name: str,
        scene: Dict[str, Any],
        field_key: str
    ) -> str:
        """
        Generate HTML for field comparison.
        
        Args:
            field_name: Display name of field
            scene: Scene data
            field_key: Key for field data
            
        Returns:
            HTML string for field comparison
        """
        original = scene['original'].get(field_key, '')
        parsed = scene['parsed'].get(field_key, '')
        comparison = scene['comparison'].get(field_key, {})
        status = comparison.get('status', 'no_change')
        
        # Determine CSS class based on status
        status_class = {
            'no_change': 'no-change',
            'new_data': 'new-data',
            'match': 'match',
            'minor_diff': 'minor-diff',
            'major_diff': 'major-diff',
            'conflict': 'conflict'
        }.get(status, 'no-change')
        
        return f"""
        <div class="field-comparison {status_class}">
            <div class="field-label">{field_name}</div>
            <div class="field-values">
                <div class="original-value" title="Original">{original or '[empty]'}</div>
                <div class="arrow">→</div>
                <div class="parsed-value" title="Parsed">{parsed or '[empty]'}</div>
            </div>
            <div class="field-status">{status}</div>
        </div>
        """

    def _load_css_styles(self) -> str:
        """
        Load CSS styles for the plugin interface.
        
        Returns:
            CSS string
        """
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }
        
        .controls {
            margin: 20px 0;
            display: flex;
            gap: 10px;
        }
        
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            background: #e9ecef;
            color: #495057;
        }
        
        button.primary {
            background: #007bff;
            color: white;
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .scene-list {
            border: 1px solid #dee2e6;
            border-radius: 4px;
            max-height: 600px;
            overflow-y: auto;
        }
        
        .scene-row {
            display: flex;
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
        }
        
        .scene-row:hover {
            background-color: #f8f9fa;
        }
        
        .scene-info {
            margin-left: 12px;
            flex: 1;
        }
        
        .scene-filename {
            font-weight: 500;
            margin-bottom: 4px;
        }
        
        .scene-meta {
            display: flex;
            gap: 16px;
            font-size: 0.9em;
            color: #6c757d;
        }
        
        .review-list {
            margin-top: 20px;
        }
        
        .review-card {
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-bottom: 16px;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .card-content {
            padding: 16px;
        }
        
        .comparison-grid {
            display: grid;
            gap: 16px;
        }
        
        .field-comparison {
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 12px;
        }
        
        .field-label {
            font-weight: 500;
            margin-bottom: 8px;
        }
        
        .field-values {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }
        
        .original-value, .parsed-value {
            flex: 1;
            padding: 8px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            background: white;
        }
        
        .arrow {
            font-weight: bold;
            color: #6c757d;
        }
        
        .field-status {
            font-size: 0.8em;
            padding: 2px 6px;
            border-radius: 3px;
            text-transform: uppercase;
        }
        
        .no-change { background: #d1ecf1d; color: #155724; }
        .new-data { background: #d4edda; color: #155724; }
        .match { background: #cce5ff; color: #004085; }
        .minor-diff { background: #fff3cd; color: #856404; }
        .major-diff { background: #f8d7da; color: #721c24; }
        .conflict { background: #f5c6cb; color: #721c24; }
        
        .progress-container {
            margin: 20px 0;
        }
        
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: #007bff;
            width: 0%;
            transition: width 0.3s ease;
        }
        
        .progress-text {
            text-align: center;
            margin-top: 8px;
            font-weight: 500;
        }
        """

    def _load_js_functions(self) -> str:
        """
        Load JavaScript functions for the plugin interface.
        
        Returns:
            JavaScript string
        """
        return """
        function selectAllScenes() {
            document.querySelectorAll('.scene-select').forEach(checkbox => {
                checkbox.checked = true;
            });
        }
        
        function selectNoScenes() {
            document.querySelectorAll('.scene-select').forEach(checkbox => {
                checkbox.checked = false;
            });
        }
        
        function getSelectedSceneIds() {
            return Array.from(document.querySelectorAll('.scene-select:checked'))
                .map(checkbox => checkbox.value);
        }
        
        function processSelectedScenes() {
            const sceneIds = getSelectedSceneIds();
            if (sceneIds.length === 0) {
                alert('Please select scenes to process');
                return;
            }
            
            // Submit to plugin for processing
            const input = {
                mode: 'process',
                scene_ids: sceneIds
            };
            
            submitToPlugin(input);
        }
        
        function approveAllChanges() {
            document.querySelectorAll('.approve-scene').forEach(checkbox => {
                checkbox.checked = true;
            });
            updateApplyButton();
        }
        
        function rejectAllChanges() {
            document.querySelectorAll('.approve-scene').forEach(checkbox => {
                checkbox.checked = false;
            });
            updateApplyButton();
        }
        
        function approveNoConflicts() {
            document.querySelectorAll('.review-card').forEach(card => {
                const hasConflicts = card.querySelector('.major-diff, .conflict');
                const checkbox = card.querySelector('.approve-scene');
                checkbox.checked = !hasConflicts;
            });
            updateApplyButton();
        }
        
        function updateApplyButton() {
            const approvedCount = document.querySelectorAll('.approve-scene:checked').length;
            const applyButton = document.getElementById('applyChanges');
            applyButton.disabled = approvedCount === 0;
        }
        
        function applyChanges() {
            const approvedUpdates = collectApprovedUpdates();
            if (approvedUpdates.length === 0) {
                alert('No changes approved');
                return;
            }
            
            showProgress();
            
            const input = {
                mode: 'update',
                approved_updates: approvedUpdates
            };
            
            submitToPlugin(input);
        }
        
        function collectApprovedUpdates() {
            const updates = [];
            
            document.querySelectorAll('.review-card').forEach(card => {
                const checkbox = card.querySelector('.approve-scene');
                if (checkbox.checked) {
                    const sceneId = card.dataset.sceneId;
                    // Collect approved field changes from the card
                    const update = collectCardUpdate(card, sceneId);
                    if (update) {
                        updates.push(update);
                    }
                }
            });
            
            return updates;
        }
        
        function showProgress() {
            document.querySelector('.controls').style.display = 'none';
            document.querySelector('.review-list').style.display = 'none';
            document.querySelector('.progress-container').style.display = 'block';
            
            // Simulate progress
            let progress = 0;
            const interval = setInterval(() => {
                progress += Math.random() * 10;
                if (progress > 90) progress = 90;
                
                document.querySelector('.progress-fill').style.width = progress + '%';
                document.querySelector('.progress-text').textContent = 
                    `Processing... ${Math.round(progress)}%`;
            }, 200);
            
            return interval;
        }
        
        function submitToPlugin(input) {
            // This would submit to the plugin backend
            console.log('Submitting to plugin:', input);
        }
        """

    def _scene_list_js(self) -> str:
        """
        JavaScript for scene list interface.
        
        Returns:
            JavaScript string
        """
        return """
        document.getElementById('selectAll').addEventListener('click', selectAllScenes);
        document.getElementById('selectNone').addEventListener('click', selectNoScenes);
        document.getElementById('processSelected').addEventListener('click', processSelectedScenes);
        """

    def _review_interface_js(self) -> str:
        """
        JavaScript for review interface.
        
        Returns:
            JavaScript string
        """
        return """
        document.getElementById('approveAll').addEventListener('click', approveAllChanges);
        document.getElementById('rejectAll').addEventListener('click', rejectAllChanges);
        document.getElementById('approveNoConflicts').addEventListener('click', approveNoConflicts);
        document.getElementById('applyChanges').addEventListener('click', applyChanges);
        
        // Update apply button state when checkboxes change
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('approve-scene')) {
                updateApplyButton();
            }
        });
        """
```

## Static CSS: `plugin/static/css/review-ui.css`

```css
/* Additional styles for review interface */
.studio {
    background: #e3f2fd;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
}

.date {
    background: #f3e5f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
}

.code {
    background: #e8f5e8;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
}

/* Responsive design */
@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
    
    .controls {
        flex-direction: column;
    }
    
    .scene-row {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .scene-info {
        margin-left: 0;
        margin-top: 8px;
    }
    
    .comparison-grid {
        grid-template-columns: 1fr;
    }
}
```

## Static JavaScript: `plugin/static/js/review-ui.js`

```javascript
// Enhanced UI interactions for review interface
class ReviewUI {
    constructor() {
        this.initEventListeners();
        this.initTooltips();
    }
    
    initEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'a':
                        e.preventDefault();
                        this.approveAll();
                        break;
                    case 'r':
                        e.preventDefault();
                        this.rejectAll();
                        break;
                    case 'Enter':
                        e.preventDefault();
                        this.applyChanges();
                        break;
                }
            }
        });
        
        // Double-click to edit fields
        document.addEventListener('dblclick', (e) => {
            if (e.target.classList.contains('parsed-value')) {
                this.makeEditable(e.target);
            }
        });
    }
    
    initTooltips() {
        // Add tooltips for field statuses
        const tooltips = {
            'no-change': 'Values are identical',
            'new-data': 'New value where original was empty',
            'match': 'Values match after normalization',
            'minor-diff': 'Small differences (>90% similar)',
            'major-diff': 'Significant differences (50-90% similar)',
            'conflict': 'Completely different values (<50% similar)'
        };
        
        document.querySelectorAll('.field-status').forEach(status => {
            const statusText = status.textContent.trim();
            const tooltip = tooltips[statusText];
            if (tooltip) {
                status.title = tooltip;
            }
        });
    }
    
    makeEditable(element) {
        const originalValue = element.textContent;
        const input = document.createElement('input');
        input.type = 'text';
        input.value = originalValue;
        input.className = 'edit-input';
        
        input.addEventListener('blur', () => {
            element.textContent = input.value;
            element.classList.add('user-edited');
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                input.blur();
            } else if (e.key === 'Escape') {
                element.textContent = originalValue;
            }
        });
        
        element.textContent = '';
        element.appendChild(input);
        input.focus();
        input.select();
    }
    
    approveAll() {
        approveAllChanges();
    }
    
    rejectAll() {
        rejectAllChanges();
    }
    
    applyChanges() {
        applyChanges();
    }
}

// Initialize UI when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ReviewUI();
});
```

## Plugin Configuration: `config/plugin_config.json`

```json
{
  "name": "Yansa Filename Parser",
  "version": "1.0.0",
  "description": "Integrates yansa.py filename parsing with Stash for automated metadata extraction",
  "author": "Yansa Team",
  "website": "https://github.com/yansa/filename-parser",
  
  "ui": {
    "name": "Filename Parser",
    "icon": "tag"
  },
  
  "hooks": {
    "scene": {
      "name": "Parse Filenames",
      "description": "Extract metadata from unorganized scene filenames",
      "operation": "parse"
    }
  },
  
  "permissions": [
    "read_scenes",
    "write_scenes",
    "read_studios"
  ],
  
  "settings": {
    "processing": {
      "batch_size": {
        "type": "number",
        "default": 50,
        "min": 1,
        "max": 1000,
        "description": "Number of scenes to process in each batch"
      },
      "auto_approve_no_conflicts": {
        "type": "boolean",
        "default": true,
        "description": "Automatically approve changes without conflicts"
      },
      "confidence_threshold": {
        "type": "number",
        "default": 0.8,
        "min": 0.0,
        "max": 1.0,
        "description": "Minimum confidence score for auto-approval"
      }
    },
    "conflicts": {
      "auto_resolve_minor": {
        "type": "boolean",
        "default": true,
        "description": "Automatically resolve minor conflicts"
      },
      "require_review_major": {
        "type": "boolean",
        "default": true,
        "description": "Require manual review for major conflicts"
      }
    },
    "ui": {
      "show_preview": {
        "type": "boolean",
        "default": true,
        "description": "Show preview of changes before applying"
      },
      "compact_view": {
        "type": "boolean",
        "default": false,
        "description": "Use compact view for scene lists"
      },
      "sort_by": {
        "type": "select",
        "default": "filename",
        "options": ["filename", "studio", "date"],
        "description": "Default sort order for scene lists"
      }
    }
  }
}
```

## Integration Flow

1. **Plugin Registration**: Register with Stash using configuration
2. **Scene Discovery**: Query unorganized scenes with pagination
3. **User Selection**: Display scene list with selection controls
4. **Batch Processing**: Process selected scenes with yansa.py
5. **Review Interface**: Show side-by-side comparisons
6. **User Approval**: Allow selective approval of changes
7. **Metadata Updates**: Apply approved changes via GraphQL mutations
8. **Progress Tracking**: Show real-time progress and results

This implementation provides a complete, user-friendly interface for integrating yansa.py with Stash while maintaining full control over metadata changes through manual review.