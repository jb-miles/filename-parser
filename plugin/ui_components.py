#!/usr/bin/env python3
"""
UI components for Stash yansa.py plugin.

Stash can render HTML returned from plugin tasks. This module generates simple
HTML views for:
- listing unorganized scenes for selection
- reviewing parsed vs existing metadata

The JavaScript "submitToPlugin" hook is intentionally left as a small adapter
point because Stash plugin UI integration can vary by deployment; the backend
also supports non-interactive operation via `mode: "run"`.
"""

from __future__ import annotations

from typing import Any, Dict, List


class UIComponents:
    def __init__(self) -> None:
        self.css_styles = self._load_css_styles()
        self.js_functions = self._load_js_functions()

    def scene_list_html(self, scenes: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Yansa Filename Parser - Scene Selection</title>
            <style>{self.css_styles}</style>
        </head>
        <body>
            <div class="container">
                <h1>Unorganized Scenes</h1>
                <p>Select scenes to process with yansa.py filename parsing.</p>
                <div class="controls">
                    <button id="selectAll">Select All</button>
                    <button id="selectNone">Select None</button>
                    <button id="processSelected" class="primary">Process Selected</button>
                </div>

                <div class="scene-list">
                    {self._generate_scene_rows(scenes, config)}
                </div>

                <div class="hint">
                    <p><strong>Tip:</strong> If your Stash plugin environment does not support interactive calls back
                    to the plugin task, use <code>mode: "run"</code> to run enrichment non-interactively.</p>
                </div>
            </div>

            <script>{self.js_functions}</script>
            <script>{self._scene_list_js()}</script>
        </body>
        </html>
        """
        return html

    def review_interface_html(self, processed_scenes: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Yansa Filename Parser - Review Changes</title>
            <style>{self.css_styles}</style>
        </head>
        <body>
            <div class="container">
                <h1>Review Metadata Changes</h1>
                <p>Review and approve metadata changes before updating Stash.</p>

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

                <div class="hint">
                    <p><strong>Safety:</strong> The backend always refuses to overwrite existing Stash fields.</p>
                </div>
            </div>

            <script>{self.js_functions}</script>
            <script>{self._review_interface_js()}</script>
        </body>
        </html>
        """
        return html

    def _generate_scene_rows(self, scenes: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        rows: List[str] = []
        sort_by = (config.get("ui") or {}).get("sort_by", "filename")

        if sort_by == "filename":
            scenes.sort(key=lambda s: s.get("filename") or "")
        elif sort_by == "studio":
            scenes.sort(key=lambda s: s.get("studio") or "")
        elif sort_by == "date":
            scenes.sort(key=lambda s: s.get("date") or "")

        for scene in scenes:
            rows.append(
                f"""
                <div class="scene-row" data-scene-id="{scene['id']}">
                    <input type="checkbox" class="scene-select" value="{scene['id']}">
                    <div class="scene-info">
                        <div class="scene-filename">{scene.get('filename') or ''}</div>
                        <div class="scene-meta">
                            <span class="studio">{scene.get('studio') or 'Unknown'}</span>
                            <span class="date">{scene.get('date') or ''}</span>
                            <span class="code">{scene.get('code') or ''}</span>
                        </div>
                    </div>
                </div>
                """
            )

        return "".join(rows)

    def _generate_review_cards(self, processed_scenes: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        cards: List[str] = []
        for scene in processed_scenes:
            cards.append(
                f"""
                <div class="review-card" data-scene-id="{scene['scene_id']}">
                    <div class="card-header">
                        <h3>{scene.get('filename') or ''}</h3>
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
            )
        return "".join(cards)

    def _generate_field_comparison(self, field_name: str, scene: Dict[str, Any], field_key: str) -> str:
        original = (scene.get("original") or {}).get(field_key) or ""
        parsed = (scene.get("parsed") or {}).get(field_key) or ""
        comparison = (scene.get("comparison") or {}).get(field_key) or {}
        status = comparison.get("status", "no_change")

        status_class = {
            "no_change": "no-change",
            "no_data": "no-data",
            "new_data": "new-data",
            "match": "match",
            "minor_diff": "minor-diff",
            "major_diff": "major-diff",
            "conflict": "conflict",
        }.get(status, "no-change")

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
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }

        code { background: #f1f3f5; padding: 0 4px; border-radius: 4px; }

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
            flex-wrap: wrap;
        }

        button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            background: #e9ecef;
            color: #495057;
        }

        button.primary { background: #007bff; color: white; }
        button:disabled { opacity: 0.6; cursor: not-allowed; }

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

        .scene-row:hover { background-color: #f8f9fa; }

        .scene-info { margin-left: 12px; flex: 1; }
        .scene-filename { font-weight: 500; margin-bottom: 4px; }

        .scene-meta {
            display: flex;
            gap: 16px;
            font-size: 0.9em;
            color: #6c757d;
            flex-wrap: wrap;
        }

        .review-list { margin-top: 20px; }

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

        .card-content { padding: 16px; }
        .comparison-grid { display: grid; gap: 16px; }

        .field-comparison {
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 12px;
        }

        .field-label { font-weight: 500; margin-bottom: 8px; }

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
            word-break: break-word;
        }

        .arrow { font-weight: bold; color: #6c757d; }

        .field-status {
            font-size: 0.8em;
            padding: 2px 6px;
            border-radius: 3px;
            text-transform: uppercase;
            display: inline-block;
        }

        .no-data   { background: #e9ecef; color: #495057; }
        .no-change { background: #d1ecf1; color: #0c5460; }
        .new-data  { background: #d4edda; color: #155724; }
        .match     { background: #cce5ff; color: #004085; }
        .minor-diff{ background: #fff3cd; color: #856404; }
        .major-diff{ background: #f8d7da; color: #721c24; }
        .conflict  { background: #f5c6cb; color: #721c24; }

        .progress-container { margin: 20px 0; }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill { height: 100%; background: #007bff; width: 0%; transition: width 0.3s ease; }
        .progress-text { text-align: center; margin-top: 8px; font-weight: 500; }

        .hint { margin-top: 20px; color: #6c757d; font-size: 0.9em; }

        @media (max-width: 768px) {
            .container { padding: 10px; }
            .controls { flex-direction: column; }
            .scene-row { flex-direction: column; align-items: flex-start; }
            .scene-info { margin-left: 0; margin-top: 8px; }
        }
        """

    def _load_js_functions(self) -> str:
        return """
        function selectAllScenes() {
            document.querySelectorAll('.scene-select').forEach(cb => cb.checked = true);
        }

        function selectNoScenes() {
            document.querySelectorAll('.scene-select').forEach(cb => cb.checked = false);
        }

        function getSelectedSceneIds() {
            return Array.from(document.querySelectorAll('.scene-select:checked')).map(cb => cb.value);
        }

        function processSelectedScenes() {
            const sceneIds = getSelectedSceneIds();
            if (sceneIds.length === 0) {
                alert('Please select scenes to process');
                return;
            }
            submitToPlugin({ mode: 'process', scene_ids: sceneIds });
        }

        function approveAllChanges() {
            document.querySelectorAll('.approve-scene').forEach(cb => cb.checked = true);
            updateApplyButton();
        }

        function rejectAllChanges() {
            document.querySelectorAll('.approve-scene').forEach(cb => cb.checked = false);
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
            if (applyButton) applyButton.disabled = approvedCount === 0;
        }

        function applyChanges() {
            const approvedUpdates = collectApprovedUpdates();
            if (approvedUpdates.length === 0) {
                alert('No changes approved');
                return;
            }
            showProgress();
            submitToPlugin({ mode: 'update', approved_updates: approvedUpdates });
        }

        function collectApprovedUpdates() {
            const updates = [];
            document.querySelectorAll('.review-card').forEach(card => {
                const checkbox = card.querySelector('.approve-scene');
                if (!checkbox || !checkbox.checked) return;
                const sceneId = card.dataset.sceneId;
                updates.push({ id: sceneId });
            });
            return updates;
        }

        function showProgress() {
            const controls = document.querySelector('.controls');
            const reviewList = document.querySelector('.review-list');
            const progressContainer = document.querySelector('.progress-container');
            if (controls) controls.style.display = 'none';
            if (reviewList) reviewList.style.display = 'none';
            if (progressContainer) progressContainer.style.display = 'block';
        }

        function submitToPlugin(input) {
            console.log('Plugin submission (implement adapter):', input);
            alert('submitToPlugin is not wired up. Use mode: \"run\" for non-interactive enrichment, or adapt submitToPlugin for your Stash deployment.');
        }
        """

    def _scene_list_js(self) -> str:
        return """
        document.getElementById('selectAll').addEventListener('click', selectAllScenes);
        document.getElementById('selectNone').addEventListener('click', selectNoScenes);
        document.getElementById('processSelected').addEventListener('click', processSelectedScenes);
        """

    def _review_interface_js(self) -> str:
        return """
        document.getElementById('approveAll').addEventListener('click', approveAllChanges);
        document.getElementById('rejectAll').addEventListener('click', rejectAllChanges);
        document.getElementById('approveNoConflicts').addEventListener('click', approveNoConflicts);
        document.getElementById('applyChanges').addEventListener('click', applyChanges);
        document.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('approve-scene')) updateApplyButton();
        });
        updateApplyButton();
        """

