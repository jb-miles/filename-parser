#!/usr/bin/env python3
"""
Mark a stage as completed and embed reference evaluation metrics in the plan.

Default behavior:
- Runs tools/evaluate.py in reference mode against ref/master.xlsx
- Rounds the key metrics to whole percentages
- Updates ref/docs/COMPREHENSIVE-IMPLEMENTATION-PLAN.md with the command and results
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

DEFAULT_PLAN = Path("ref/docs/COMPREHENSIVE-IMPLEMENTATION-PLAN.md")
DEFAULT_INPUT = Path("ref/master.xlsx")
DEFAULT_EVALUATE = Path("tools/evaluate.py")
METRICS_DIR = Path("metrics")

METRIC_LABELS: Sequence[Tuple[str, str]] = (
    ("parsed_perfect_rate", "Parsed perfect"),
    ("metadata_accuracy_rate", "Metadata accuracy"),
    ("metadata_false_negative_rate", "Metadata false negatives"),
    ("metadata_false_positive_rate", "Metadata false positives"),
    ("pattern_match_rate", "Pattern match"),
)


def relpath(path: Path, root: Path) -> str:
    """Return a repo-relative path when possible for cleaner notes."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mark a stage complete and embed rounded evaluation metrics."
    )
    parser.add_argument("--stage", type=int, required=True, help="Stage number to mark complete.")
    parser.add_argument(
        "--plan-path",
        type=Path,
        default=DEFAULT_PLAN,
        help="Path to the implementation plan markdown file.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Reference Excel file to feed into evaluate.py.",
    )
    parser.add_argument(
        "--evaluate-script",
        type=Path,
        default=DEFAULT_EVALUATE,
        help="Path to evaluate.py.",
    )
    parser.add_argument(
        "--metrics-json",
        type=Path,
        help="Existing metrics JSON to reuse instead of running evaluate.py.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional override for the metrics JSON output path.",
    )
    parser.add_argument(
        "--output-excel",
        type=Path,
        help="Optional override for the metrics Excel output path.",
    )
    parser.add_argument(
        "--skip-excel",
        action="store_true",
        help="Skip writing the Excel artifact when running evaluate.py.",
    )
    return parser.parse_args()


def run_evaluation(
    root: Path,
    evaluate_path: Path,
    input_path: Path,
    output_json: Path | None,
    output_excel: Path | None,
    skip_excel: bool,
) -> Tuple[Path, str]:
    """Run evaluate.py in reference mode and return metrics path + display command."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    metrics_dir = root / METRICS_DIR
    metrics_dir.mkdir(parents=True, exist_ok=True)

    json_path = (root / output_json) if output_json else metrics_dir / f"reference-{timestamp}.json"
    excel_path = (root / output_excel) if output_excel else metrics_dir / f"reference-{timestamp}.xlsx"

    command: List[str] = [
        sys.executable,
        str(evaluate_path),
        "--mode",
        "reference",
        "--input",
        str(input_path),
        "--output-json",
        str(json_path),
    ]
    if not skip_excel:
        command.extend(["--output-excel", str(excel_path)])
    else:
        command.append("--skip-excel")

    subprocess.run(command, check=True, cwd=root)

    display_command = [
        "python",
        relpath(evaluate_path, root),
        "--mode",
        "reference",
        "--input",
        relpath(input_path, root),
        "--output-json",
        relpath(json_path, root),
    ]
    if not skip_excel:
        display_command.extend(["--output-excel", relpath(excel_path, root)])
    else:
        display_command.append("--skip-excel")

    return json_path, shlex.join(display_command)


def load_metrics(metrics_path: Path) -> List[Tuple[str, int]]:
    with metrics_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    key_metrics = data.get("key_metrics")
    if not key_metrics:
        raise ValueError(f"'key_metrics' section missing in {metrics_path}")

    rounded: List[Tuple[str, int]] = []
    for key, label in METRIC_LABELS:
        if key not in key_metrics:
            raise ValueError(f"'{key}' missing from metrics JSON {metrics_path}")
        rounded.append((label, int(round(key_metrics[key]))))
    return rounded


def build_note_lines(metrics: Iterable[Tuple[str, int]], metrics_path: Path, command: str, root: Path) -> List[str]:
    rel_metrics = relpath(metrics_path, root)
    note_lines = [
        "",
        f"> [!NOTE] {command}",
        f"> *from {rel_metrics}:*",
    ]
    for label, value in metrics:
        note_lines.append(f"> \t{label}: {value}%")
    note_lines.append(">")
    note_lines.append("")
    return note_lines


def update_plan_lines(lines: List[str], stage: int, note_lines: List[str], completion_time: str) -> List[str]:
    stage_pattern = re.compile(rf"^- \[[ xX]\] Stage {stage}:(.*)$")
    status_pattern = re.compile(r"^- \[[ xX]\]")
    completed_pattern = re.compile(r"\s*\*completed[^*]*\*")

    for idx, line in enumerate(lines):
        if not stage_pattern.match(line):
            continue

        existing_completed = completed_pattern.search(line)
        completion_text = existing_completed.group(0).strip() if existing_completed else f"*completed {completion_time}*"

        base_line = status_pattern.sub("- [x]", line)
        base_line = completed_pattern.sub("", base_line).rstrip()
        lines[idx] = f"{base_line} {completion_text}".strip()

        note_start = idx + 1
        while note_start < len(lines) and lines[note_start].strip() == "":
            note_start += 1

        note_end = note_start
        while note_end < len(lines) and lines[note_end].lstrip().startswith(">"):
            note_end += 1
        if note_end < len(lines) and lines[note_end].strip() == "":
            note_end += 1

        lines[idx + 1 : note_end] = note_lines
        return lines

    raise ValueError(f"Could not find Stage {stage} in the plan.")


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    plan_path = (root / args.plan_path).resolve()
    input_path = (root / args.input).resolve()
    evaluate_path = (root / args.evaluate_script).resolve()

    if not plan_path.exists():
        raise SystemExit(f"Plan file not found: {plan_path}")
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    if not evaluate_path.exists():
        raise SystemExit(f"evaluate.py not found: {evaluate_path}")

    completion_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    if args.metrics_json:
        metrics_path = (root / args.metrics_json).resolve()
        if not metrics_path.exists():
            raise SystemExit(f"Metrics JSON not found: {metrics_path}")
        command_display = shlex.join(
            [
                "python",
                relpath(evaluate_path, root),
                "--mode",
                "reference",
                "--input",
                relpath(input_path, root),
                "--output-json",
                relpath(metrics_path, root),
            ]
        )
        metrics_json_path = metrics_path
    else:
        metrics_json_path, command_display = run_evaluation(
            root,
            evaluate_path,
            input_path,
            args.output_json,
            args.output_excel,
            args.skip_excel,
        )

    metrics = load_metrics(metrics_json_path)
    note_lines = build_note_lines(metrics, metrics_json_path, command_display, root)

    existing_lines = plan_path.read_text(encoding="utf-8").splitlines()
    updated_lines = update_plan_lines(existing_lines, args.stage, note_lines, completion_time)
    plan_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    print(f"✓ Stage {args.stage} marked complete in {relpath(plan_path, root)}")
    print(f"  Metrics source: {relpath(metrics_json_path, root)}")
    print(f"  Command logged: {command_display}")


if __name__ == "__main__":
    main()
