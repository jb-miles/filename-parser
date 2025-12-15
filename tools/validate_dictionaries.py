#!/usr/bin/env python3
"""Validate parser dictionaries against JSON Schemas and custom rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
DICTIONARY_DIR = ROOT / "dictionaries"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_with_schema(data, schema_path: Path, label: str) -> List[str]:
    schema = load_json(schema_path)
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

    messages = []
    for error in errors:
        location = " > ".join(str(p) for p in error.absolute_path) or "root"
        messages.append(f"{label}: {location}: {error.message}")
    return messages


def collect_aliases(studios) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for studio in studios or []:
        canonical = studio.get("canonical_name", "").strip()
        if not canonical:
            continue
        lower_canonical = canonical.lower()
        for alias_field in ("aliases", "abbr"):
            aliases = studio.get(alias_field) or []
            if isinstance(aliases, str):
                aliases = [aliases]
            for alias in aliases:
                if not alias:
                    continue
                lower_alias = alias.lower()
                # Only record the first mapping to highlight conflicts separately
                alias_map.setdefault(lower_alias, lower_canonical)
    return alias_map


def check_studios(studios) -> List[str]:
    errors: List[str] = []
    seen: Dict[str, int] = {}
    for idx, studio in enumerate(studios or []):
        name = (studio.get("canonical_name") or "").strip()
        if not name:
            errors.append(f"studios[{idx}]: canonical_name is empty")
            continue
        key = name.lower()
        if key in seen:
            errors.append(
                f"studios[{idx}]: duplicate canonical_name '{name}' also at index {seen[key]}"
            )
        else:
            seen[key] = idx
    # Check for alias conflicts pointing to multiple canonicals
    alias_map = collect_aliases(studios)
    alias_targets: Dict[str, str] = {}
    for alias, canonical in alias_map.items():
        if alias in alias_targets and alias_targets[alias] != canonical:
            errors.append(
                f"studios alias collision: '{alias}' mapped to both '{alias_targets[alias]}' and '{canonical}'"
            )
        else:
            alias_targets[alias] = canonical
    return errors


def check_studio_alias_file(alias_file: Dict[str, str], canonical_names: Dict[str, int]) -> List[str]:
    errors: List[str] = []
    if not isinstance(alias_file, dict):
        return ["studio_aliases.json must be a JSON object mapping alias -> canonical_name"]

    for alias, target in alias_file.items():
        if not alias or not isinstance(alias, str):
            errors.append(f"studio_aliases: invalid alias key '{alias}'")
            continue
        if not target or not isinstance(target, str):
            errors.append(f"studio_aliases: alias '{alias}' has invalid canonical value '{target}'")
            continue
        if target.lower() not in canonical_names:
            errors.append(
                f"studio_aliases: canonical '{target}' for alias '{alias}' not found in studios.json"
            )
    return errors


def check_studio_codes(parser_dict, canonical_names: Dict[str, int]) -> List[str]:
    errors: List[str] = []
    for idx, entry in enumerate(parser_dict.get("studio_codes", []) or []):
        studio = entry.get("studio")
        code = entry.get("code") or entry.get("regex")
        if not code:
            errors.append(f"studio_codes[{idx}]: missing 'code' or 'regex'")
            continue
        if studio and isinstance(studio, str) and studio.lower() not in canonical_names:
            errors.append(
                f"studio_codes[{idx}]: studio '{studio}' not found in studios.json"
            )
    return errors


def main() -> int:
    failures: List[str] = []

    parser_dict_path = DICTIONARY_DIR / "parser-dictionary.json"
    studios_path = DICTIONARY_DIR / "studios.json"
    studio_aliases_path = DICTIONARY_DIR / "studio_aliases.json"

    parser_dict = load_json(parser_dict_path)
    studios = load_json(studios_path)
    studio_aliases = load_json(studio_aliases_path)

    failures.extend(
        validate_with_schema(parser_dict, SCHEMA_DIR / "parser-dictionary.schema.json", "parser-dictionary")
    )
    failures.extend(validate_with_schema(studios, SCHEMA_DIR / "studios.schema.json", "studios"))

    canonical_lookup = {(studio.get("canonical_name") or "").lower(): idx for idx, studio in enumerate(studios or [])}

    failures.extend(check_studios(studios))
    failures.extend(check_studio_codes(parser_dict, canonical_lookup))
    failures.extend(check_studio_alias_file(studio_aliases, canonical_lookup))

    if failures:
        print("Dictionary validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("All dictionaries validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
