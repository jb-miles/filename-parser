#!/usr/bin/env python3
"""
Yansa Filename Parser - Adult film metadata extraction and Stash plugin integration.

This module serves dual purposes:
1. Library: FilenameParser class for extracting metadata from adult film filenames
2. Stash Plugin: Integration for enriching Stash scenes with parsed metadata

When run as a standalone script, it operates as a Stash plugin that:
- Reads JSON input from stdin
- Parses scene filenames using early removal token processing
- Proposes metadata updates (studio, title, date, studio code, performers)
- Never overwrites existing Stash values
- Writes JSON output to stdout

Usage as library:
    from yansa import FilenameParser
    parser = FilenameParser()
    result = parser.parse("Scene.Title.2024.01.15.mp4")

Usage as Stash plugin:
    Execute directly via Stash plugin system
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

try:
    import stashapi.log as stash_log
except Exception:  # noqa: BLE001
    stash_log = None

# ============================================================================
# CORE PARSING - Module Imports
# ============================================================================

try:
    # Try relative import first (when used as package)
    from .modules import (
        DateExtractor,
        FinalStageExtractor,
        PerformerMatcher,
        PreTokenizationResult,
        PreTokenizer,
        StudioCodeFinder,
        StudioMatcher,
        Token,
        TokenizationResult,
        Tokenizer,
    )
    from .modules.dictionary_loader import DictionaryLoader
except ImportError:
    # Fall back to direct import (when executed as script)
    from modules import (
        DateExtractor,
        FinalStageExtractor,
        PerformerMatcher,
        PreTokenizationResult,
        PreTokenizer,
        StudioCodeFinder,
        StudioMatcher,
        Token,
        TokenizationResult,
        Tokenizer,
    )
    from modules.dictionary_loader import DictionaryLoader

# ============================================================================
# STASH PLUGIN - Module Imports (conditional for library usage)
# ============================================================================

if TYPE_CHECKING:
    from modules.scene_transformer import SceneTransformer
    from modules.stash_client import Scene, StashClient

try:
    from modules.scene_transformer import SceneTransformer
    from modules.stash_client import Scene, StashClient
    STASH_MODULES_AVAILABLE = True
except ImportError:
    # Allow library usage without Stash dependencies
    STASH_MODULES_AVAILABLE = False

from modules.excel_writer import ExcelSheetData, write_excel_workbook


# ============================================================================
# CORE PARSING - FilenameParser Class
# ============================================================================

class FilenameParser:
    """Parser for extracting metadata from adult film filenames."""

    def __init__(self, stash_studios=None):
        """
        Initialize the filename parser.

        Args:
            stash_studios: Optional list of SceneStudio objects from Stash API.
                          If provided, uses Stash's database for studio matching instead of static JSON.
        """
        # Preload all dictionaries into cache to avoid redundant file I/O
        # across multiple modules. Modules will use cached versions.
        DictionaryLoader.preload_all()

        self.pre_tokenizer = PreTokenizer()
        # self.path_parser = PathParser()  # Disabled - not working on paths yet
        self.tokenizer = Tokenizer()
        self.date_extractor = DateExtractor()
        self.studio_matcher = StudioMatcher(stash_studios=stash_studios)
        self.studio_code_finder = StudioCodeFinder()
        self.performer_matcher = PerformerMatcher()
        self.final_stage_extractor = FinalStageExtractor()
        # self.resolver = PathFilenameResolver()  # Disabled - not working on paths yet

    def pre_tokenize(self, filename: Union[str, Path]) -> PreTokenizationResult:
        """Process basename (stem) before tokenization by removing early removal tokens."""
        return self.pre_tokenizer.process(str(filename))

    def tokenize(self, pre_result: PreTokenizationResult) -> TokenizationResult:
        """Process pre-tokenization result to extract tokens and pattern."""
        # Use the tokenizer to process the cleaned string
        return self.tokenizer.tokenize(
            cleaned=pre_result.cleaned,
            original=pre_result.original
        )

    def extract_dates(self, token_result: TokenizationResult) -> TokenizationResult:
        """Extract dates from tokens and renumber."""
        return self.date_extractor.process(token_result)

    def match_studios(self, token_result: TokenizationResult) -> TokenizationResult:
        """Match tokens against known studios and mark studio tokens."""
        return self.studio_matcher.process(token_result)

    def match_studios_dash_fallback(self, token_result: TokenizationResult) -> TokenizationResult:
        """Fallback studio matching for tokens with internal dashes."""
        return self.studio_matcher.process_dash_fallback(token_result)

    def match_studios_partial_fallback(self, token_result: TokenizationResult) -> TokenizationResult:
        """Fallback studio matching for partial/substring matches within tokens."""
        return self.studio_matcher.process_partial_match_fallback(token_result)

    def find_studio_codes(self, token_result: TokenizationResult) -> TokenizationResult:
        """Find and mark studio codes in tokens."""
        return self.studio_code_finder.process(token_result)

    def match_performers(self, token_result: TokenizationResult) -> TokenizationResult:
        """Match tokens against performer name patterns and mark performer tokens."""
        return self.performer_matcher.process(token_result)

    def finalize_structure(self, token_result: TokenizationResult) -> TokenizationResult:
        """Final stage: extract sequences, group, and title together."""
        return self.final_stage_extractor.process(token_result)

    def parse(self, filename: Union[str, Path], *, existing_studio: Optional[str] = None) -> TokenizationResult:
        """
        Full parsing pipeline.

        Pipeline order:
        1. Pre-tokenize (remove quality markers, extensions, etc.)
        2. Tokenize (extract tokens and pattern)
        3. Extract dates
        4. Match studios
        4.5. Match studios (dash fallback) - only if no studio found yet
        4.75. Match studios (partial fallback) - only if no studio found yet
        5. Find studio codes
        6. Match performers
        7. Final stage: extract sequence, group, and title

        Args:
            filename: Filename or path-like string; directories are ignored (directory-agnostic parsing).
            existing_studio: Optional externally-provided studio name (e.g., already set in Stash).
                             Treated as authoritative context for studio-code rules that require
                             a known studio when the studio is not present in the filename.

        Returns:
            TokenizationResult with all fields extracted
        """
        filename_str = str(filename)

        # Step 1: Pre-tokenization (remove quality markers, extensions, etc.).
        # Directory-agnostic: PreTokenizer strips any parent folders before processing.
        pre_result = self.pre_tokenize(filename_str)

        # Step 2: Tokenization (extract tokens and pattern)
        token_result = self.tokenize(pre_result)

        # PATH PROCESSING DISABLED - Not working on paths yet
        # # Attach normalized path token up front so downstream modules can skip path safely
        # if path_result.path:
        #     path_token = Token(value=path_result.path, type='path', position=0)
        #     token_result.tokens = [path_token] + (token_result.tokens or [])

        # Preserve original input for traceability
        token_result.original = pre_result.original

        # Step 3: Date extraction (extract dates and renumber tokens)
        final_result = self.extract_dates(token_result)

        # Step 4: Studio matching (identify and mark studio tokens)
        final_result = self.match_studios(final_result)

        # Step 4.5: Studio matching with dash fallback (only if no studio found yet)
        final_result = self.match_studios_dash_fallback(final_result)

        # Step 4.75: Studio matching with partial fallback (only if no studio found yet)
        final_result = self.match_studios_partial_fallback(final_result)

        # Optional externally-provided studio value (used for studio_code parsing only).
        # Treat placeholder "unknown" as unset for this purpose.
        existing_value = (str(existing_studio).strip() if existing_studio is not None else "")
        if existing_value:
            current_studio = (final_result.studio or "").strip()
            if not current_studio or current_studio.lower() == "unknown":
                final_result.studio = existing_value

        # Step 5: Studio code finding (identify and mark studio code tokens)
        final_result = self.find_studio_codes(final_result)

        # Step 6: Performer matching (identify and mark performer tokens)
        final_result = self.match_performers(final_result)

        # Step 7: Final stage (sequence, group, title)
        final_result = self.finalize_structure(final_result)

        # PATH PROCESSING DISABLED - Not working on paths yet
        # # Step 9: Resolve path vs filename signals (telemetry + fallback)
        # final_result = self.resolver.resolve(final_result, path_result)

        return final_result


@dataclass
class SceneReportRow:
    """Single row for the Excel report."""

    parent: Optional[str]
    stem: str
    removed: Optional[str]
    pattern: Optional[str]
    studio: Optional[str]
    studio_code: Optional[str]
    title: Optional[str]
    sequence: Optional[str]
    performers: Optional[str]
    date: Optional[str]
    group: Optional[str]
    bold_mask: Optional[List[bool]] = None

    @staticmethod
    def headers() -> List[str]:
        return [
            "parent",
            "stem",
            "removed",
            "pattern",
            "studio",
            "studio_code",
            "title",
            "sequence",
            "performers",
            "date",
            "group",
        ]

    def to_excel_row(self) -> List[str]:
        return [
            self.parent or "",
            self.stem,
            self.removed or "",
            self.pattern or "",
            self.studio or "",
            self.studio_code or "",
            self.title or "",
            self.sequence or "",
            self.performers or "",
            self.date or "",
            self.group or "",
        ]


# ============================================================================
# STASH PLUGIN - Integration Class
# ============================================================================

class StashYansaPlugin:
    """
    Stash plugin integration for yansa filename parsing.

    Phase 1 scope:
    - Only proposes updates for: studio, title, date, studio code, performers
    - Never overwrites existing Stash values
    - Defaults to leaving scenes unorganized

    This class is designed to be executed by Stash as a plugin task:
    - Reads JSON input from stdin
    - Writes JSON output to stdout
    """

    def __init__(self, input_data: Dict[str, Any]):
        if not STASH_MODULES_AVAILABLE:
            raise RuntimeError(
                "Stash plugin modules not available. "
                "Ensure all required modules (batch_processor, scene_transformer, "
                "stash_client, ui_components) are installed."
            )

        self.input_data = input_data
        self.args = input_data.get("args") or {}
        self.server_connection = input_data.get("server_connection") or {}

        self.stash_client = StashClient(self.server_connection)
        self.scene_transformer = SceneTransformer()

        # Fetch studios from Stash database for matching (preferred over static JSON)
        self.stash_studios = self._fetch_stash_studios()
        self.filename_parser = FilenameParser(stash_studios=self.stash_studios)

        self.config = self._load_config()
        self._apply_config()
        self._last_progress_logged = 0

    def main(self) -> Dict[str, Any]:
        """Main entry point for plugin execution."""
        mode = (self.args.get("mode") or "run").lower()

        try:
            if mode in {"run", "report", "list"}:
                return self._generate_excel_report()
            return self._error_response(f"Unknown mode for filename report plugin: {mode}")
        except Exception as exc:  # noqa: BLE001
            return self._error_response(f"Plugin error: {exc}")

    def _fetch_stash_studios(self) -> Optional[List[Any]]:
        """
        Fetch all studios from Stash database.

        Returns:
            List of SceneStudio objects or None if fetch fails
        """
        try:
            return self.stash_client.get_all_studios()
        except Exception as e:
            # If we can't fetch studios from Stash, fall back to static JSON
            self._log_warning(f"Failed to fetch studios from Stash ({e}). Using static JSON fallback.")
            return None

    def _apply_config(self) -> None:
        """Apply configuration settings to processors."""
        processing = self.config.get("processing") or {}
        conflicts = self.config.get("conflicts") or {}

        self.scene_transformer.include_path_in_filename = bool(processing.get("include_path_in_filename", False))
        self.scene_transformer.mark_organized = bool(conflicts.get("mark_organized", False))

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from multiple sources with precedence:
        1. Default config (lowest priority)
        2. File-based runtime config
        3. User-provided args config (highest priority)
        """
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

        # Allow importing from repo root when plugin is copied/executed standalone.
        ROOT = Path(__file__).resolve().parent.parent

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

    def _generate_excel_report(self) -> Dict[str, Any]:
        """Fetch unorganized scenes, parse filenames, and emit an Excel report."""
        processing = self.config.get("processing") or {}
        max_scenes = processing.get("max_scenes")
        max_scenes_int: Optional[int]
        try:
            max_scenes_int = int(max_scenes) if max_scenes is not None else None
            if max_scenes_int is not None and max_scenes_int <= 0:
                max_scenes_int = None
        except (TypeError, ValueError):
            max_scenes_int = None

        self._log("Fetching unorganized scenes from Stash...")
        self._last_progress_logged = 0
        scenes = self.stash_client.get_all_unorganized_scenes(
            progress_callback=self._progress_callback,
            limit=max_scenes_int,
        )
        self._log(f"Fetched {len(scenes)} scenes")

        if max_scenes_int:
            self._log(f"Limiting report to first {len(scenes)} scenes (max_scenes={max_scenes_int})")

        report_rows: List[SceneReportRow] = []
        skipped = 0

        for scene in scenes:
            try:
                row = self._build_report_row(scene)
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                self._log(f"Failed to parse scene {scene.id}: {exc}")
                continue

            if row:
                report_rows.append(row)
            else:
                skipped += 1

        self._log(f"Prepared {len(report_rows)} report rows ({skipped} skipped)")
        headers = SceneReportRow.headers()
        sheet = ExcelSheetData(
            name="Filename Parser Results",
            headers=headers,
            rows=[row.to_excel_row() for row in report_rows],
            bold_cells=[row.bold_mask or [False] * len(headers) for row in report_rows],
        )

        report_path = self._determine_report_path()
        write_excel_workbook(report_path, [sheet])
        self._log(f"Wrote Excel report to {report_path}")

        return {
            "output": {
                "mode": "report",
                "report_path": str(report_path),
                "total_scenes": len(scenes),
                "parsed_rows": len(report_rows),
                "skipped": skipped,
            }
        }

    def _build_report_row(self, scene: Scene) -> Optional[SceneReportRow]:
        """Convert a scene to a report row without overwriting existing metadata."""
        file = self.scene_transformer.select_primary_file(scene)
        if not file or not file.basename:
            return None

        filename = file.basename
        pre_result = self.filename_parser.pre_tokenize(filename)
        existing_studio = scene.studio.name if scene.studio else None
        parse_result = self.filename_parser.parse(filename, existing_studio=existing_studio)

        removed_str = " | ".join(f"{t.value}({t.category})" for t in pre_result.removed_tokens)
        tokens = parse_result.tokens or []
        date_token = next((token.value for token in tokens if token.type == "date"), None)

        def _has_value(value: Optional[str]) -> bool:
            return bool((value or "").strip())

        stash_studio = scene.studio.name if scene.studio else None
        stash_code = scene.code if _has_value(scene.code) else None
        stash_title = scene.title if _has_value(scene.title) else None
        stash_date = scene.date if _has_value(scene.date) else None
        stash_performers = ", ".join(p.name for p in (scene.performers or []) if p.name) if scene.performers else None

        performer_tokens = [token.value for token in tokens if token.type == "performers" and token.value.strip()]
        parsed_performers = ", ".join(performer_tokens) if performer_tokens else None

        studio_value = stash_studio or parse_result.studio
        studio_code_value = stash_code or getattr(parse_result, "studio_code", None)
        title_value = stash_title or parse_result.title
        performers_value = stash_performers or parsed_performers
        date_value = stash_date or date_token

        parent = file.parent_folder_path
        if not parent and file.path:
            parent_candidate = Path(file.path).parent.as_posix()
            parent = "" if parent_candidate == "." else parent_candidate

        sequence_str = json.dumps(parse_result.sequence) if parse_result.sequence else None

        group_value = parse_result.group

        bold_mask = [False] * len(SceneReportRow.headers())
        if stash_studio:
            bold_mask[4] = True
        if stash_code:
            bold_mask[5] = True
        if stash_title:
            bold_mask[6] = True
        if stash_performers:
            bold_mask[8] = True
        if stash_date:
            bold_mask[9] = True

        return SceneReportRow(
            parent=parent,
            stem=Path(filename).stem,
            removed=removed_str or None,
            pattern=parse_result.pattern,
            studio=studio_value,
            studio_code=studio_code_value,
            title=title_value,
            sequence=sequence_str,
            performers=performers_value,
            date=date_value,
            group=group_value,
            bold_mask=bold_mask,
        )

    def _determine_report_path(self) -> Path:
        """Resolve the path for the Excel output, creating directories as needed."""
        explicit_path = self.args.get("report_path")
        if explicit_path:
            path = Path(str(explicit_path))
            path.parent.mkdir(parents=True, exist_ok=True)
            return path

        base_dir = self.args.get("report_dir")
        if base_dir:
            base_path = Path(str(base_dir))
        else:
            plugin_dir = self.server_connection.get("PluginDir")
            if plugin_dir:
                base_path = Path(str(plugin_dir))
            else:
                base_path = Path(__file__).resolve().parent

        reports_dir = base_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"filename-parser-report-{timestamp}.xlsx"
        return reports_dir / filename

    def _progress_callback(self, current: int, total: int) -> None:
        """Log periodic fetch progress."""
        if total:
            if current == total or current - self._last_progress_logged >= 50:
                self._log(f"Fetched {current}/{total} scenes...")
                self._last_progress_logged = current
        else:
            if current - self._last_progress_logged >= 50:
                self._log(f"Fetched {current} scenes...")
                self._last_progress_logged = current

    def _log(self, message: str) -> None:
        """Log an info message via Stash's stderr logging convention."""
        payload = f"[filename-parser] {message}"
        if stash_log:
            stash_log.info(payload)
            return
        sys.stderr.write(payload + "\n")

    def _log_warning(self, message: str) -> None:
        """Log a warning message via Stash's stderr logging convention."""
        payload = f"[filename-parser] {message}"
        if stash_log:
            stash_log.warning(payload)
            return
        sys.stderr.write(payload + "\n")

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Generate error response for plugin output."""
        return {"error": message, "output": None}


# ============================================================================
# PLUGIN EXECUTION - Main Entry Point
# ============================================================================

def run_plugin() -> None:
    """
    Main entry point when executed as a Stash plugin.

    Reads JSON from stdin, processes via StashYansaPlugin, writes JSON to stdout.
    """
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
        plugin = StashYansaPlugin(input_data)
        result = plugin.main()
        print(json.dumps(result))
    except Exception as exc:  # noqa: BLE001
        error_response = {"error": f"Plugin initialization error: {exc}", "output": None}
        print(json.dumps(error_response))
        sys.exit(1)


# ============================================================================
# MAIN - Dual Mode Support
# ============================================================================

if __name__ == '__main__':
    # When executed directly, run as Stash plugin
    # When imported, provides FilenameParser class for library usage
    run_plugin()
