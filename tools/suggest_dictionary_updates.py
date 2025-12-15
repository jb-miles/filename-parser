#!/usr/bin/env python3
"""Generate dictionary update suggestions from metrics sample mismatches."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Set

ROOT = Path(__file__).resolve().parent.parent


def load_metrics(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_suggestions(mismatches) -> Dict[str, object]:
    missing_studios: Set[str] = set()
    missing_studio_codes: Set[str] = set()
    noisy_groups: Counter[str] = Counter()

    for mismatch in mismatches or []:
        field = mismatch.get("field")
        mtype = mismatch.get("type")
        expected = mismatch.get("expected")
        parsed = mismatch.get("parsed")

        if field == "studio" and mtype == "false_negative" and expected:
            missing_studios.add(str(expected))

        if field == "studio_code" and expected:
            missing_studio_codes.add(str(expected))

        if field == "group" and mtype == "false_positive" and parsed:
            noisy_groups[str(parsed)] += 1

    return {
        "missing_studios": sorted(missing_studios),
        "missing_studio_codes": sorted(missing_studio_codes),
        "noisy_groups": noisy_groups.most_common(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="Path to metrics JSON file")
    parser.add_argument("--output-json", type=Path, help="Optional path to write suggestions JSON")
    args = parser.parse_args()

    data = load_metrics(args.metrics)
    suggestions = collect_suggestions(data.get("sample_mismatches", []))

    print("Suggested additions based on sample mismatches:")
    if suggestions["missing_studios"]:
        print("- Studios to add/alias:", ", ".join(suggestions["missing_studios"]))
    else:
        print("- Studios to add/alias: none")

    if suggestions["missing_studio_codes"]:
        print("- Studio codes to cover:", ", ".join(suggestions["missing_studio_codes"]))
    else:
        print("- Studio codes to cover: none")

    if suggestions["noisy_groups"]:
        print("- Group false positives to consider junk/stopwords:")
        for group, count in suggestions["noisy_groups"]:
            print(f"  * {group} ({count} occurrences)")
    else:
        print("- Group false positives to consider junk/stopwords: none")

    if args.output_json:
        payload = {
            "metrics_file": str(args.metrics),
            **suggestions,
        }
        args.output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Saved suggestions to {args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
