#!/usr/bin/env python3
"""
Evaluation harness for filename parser.

Provides two modes:
- blind: Coverage-first metrics without reference labels
- reference: Accuracy metrics vs expected labels

Outputs:
- Excel workbook with parsed results
- JSON metrics file for automation
"""

import sys
import os
import argparse
import json
import ast
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Set
from collections import Counter

# Add parent directory to path to import parser modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import FilenameParser
from modules import PreTokenizer
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


@dataclass
class ParsedRow:
    """Represents a single parsed filename with all extracted fields."""
    input: str
    removed: str
    path: Optional[str]
    filename_cleaned: str
    path_pattern: Optional[str]
    filename_pattern: str
    studio: Optional[str]
    title: Optional[str]
    performers: Optional[str]
    date: Optional[str]
    studio_code: Optional[str]
    sequence: Optional[Dict[str, Any]]
    group: Optional[str]
    unlabeled_path_tokens: Optional[Set[str]]
    unlabeled_filename_tokens: Optional[Set[str]]
    match_stats: Dict[str, Any]

    def to_excel_row(self) -> List[Any]:
        """Convert to Excel row maintaining column order."""
        return [
            self.input,
            self.removed,
            self.path if self.path else "",
            self.filename_cleaned,
            self.path_pattern if self.path_pattern else "",
            self.filename_pattern,
            self.studio if self.studio else "",
            self.title if self.title else "",
            self.performers if self.performers else "",
            self.date if self.date else "",
            self.studio_code if self.studio_code else "",
            json.dumps(self.sequence) if self.sequence else "",
            self.group if self.group else "",
            str(self.unlabeled_path_tokens) if self.unlabeled_path_tokens else "",
            str(self.unlabeled_filename_tokens) if self.unlabeled_filename_tokens else "",
            json.dumps(self.match_stats),
        ]

    @staticmethod
    def get_headers() -> List[str]:
        """Get Excel column headers in proper order."""
        return [
            "input",
            "removed",
            "path",
            "filename_cleaned",
            "path_pattern",
            "filename_pattern",
            "studio",
            "title",
            "performers",
            "date",
            "studio_code",
            "sequence",
            "group",
            "unlabeled_path_tokens",
            "unlabeled_filename_tokens",
            "match_stats",
        ]


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Evaluate filename parser with coverage or reference metrics'
    )
    parser.add_argument(
        '--mode',
        choices=['blind', 'reference'],
        default='blind',
        help='Evaluation mode: blind (coverage) or reference (vs labels)'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Input file containing filenames (one per line) or Excel reference'
    )
    parser.add_argument(
        '--baseline',
        help='Baseline metrics JSON for comparison (reference mode)'
    )
    parser.add_argument(
        '--output-excel',
        help='Output Excel file path (default: metrics/MODE-YYYYMMDD-HHMMSS.xlsx)'
    )
    parser.add_argument(
        '--output-json',
        help='Output JSON metrics file (default: metrics/MODE-YYYYMMDD-HHMMSS.json)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of files to process'
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=10,
        help='Number of mismatch samples to capture (reference mode)'
    )
    parser.add_argument(
        '--no-write',
        action='store_true',
        help='Dry-run mode: skip writing output files'
    )
    parser.add_argument(
        '--skip-excel',
        action='store_true',
        help='Skip Excel output for faster CI runs'
    )

    return parser.parse_args()


def read_input_file(filepath: str, limit: Optional[int] = None,
                   sheet_name: Optional[str] = None) -> List[str]:
    """
    Read input file and return list of filenames.
    Handles text files and Excel files.
    """
    filenames = []

    # Check if it's an Excel file
    if filepath.endswith('.xlsx'):
        wb = load_workbook(filepath, read_only=True)
        try:
            ws = None
            if sheet_name:
                if sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                else:
                    raise ValueError(f"Could not find '{sheet_name}' sheet in Excel file. Sheets present: {wb.sheetnames}")
            else:
                ws = wb.active

            if ws is None:
                raise ValueError("Excel file has no usable worksheet")

            # Find the 'input' column (assuming first row is header)
            headers = [cell.value for cell in ws[1]]
            input_col_idx = None
            for idx, header in enumerate(headers, 1):
                normalized_header = str(header).strip().lower() if header is not None else ""
                if normalized_header == 'input':
                    input_col_idx = idx
                    break

            if input_col_idx is None:
                raise ValueError("Could not find 'input' column in Excel file")

            # Read filenames from the input column
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[input_col_idx - 1]:
                    filenames.append(str(row[input_col_idx - 1]))
                    if limit and len(filenames) >= limit:
                        break
        finally:
            wb.close()
    else:
        # Text file - read line by line
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if line and line not in ['exceptions', 'sacrifice']:
                    filenames.append(line)
                    if limit and len(filenames) >= limit:
                        break

    return filenames


def parse_filename(parser: FilenameParser, filename: str) -> ParsedRow:
    """
    Parse a single filename and return a ParsedRow.

    This transforms the parser's output into the 16-column schema.
    The parser now handles all extraction logic (title, sequence, group, etc.).
    """
    # Run full parsing pipeline
    result = parser.parse(filename)
    tokens = result.tokens or []

    # Get pre-tokenization result for removed tokens
    pre_result = parser.pre_tokenize(filename)
    removed_str = ' | '.join([f"{t.value}({t.category})" for t in pre_result.removed_tokens])

    # Extract path and non-path tokens
    path_token = None
    filename_tokens = []
    for token in tokens:
        if token.type == 'path':
            path_token = token
        else:
            filename_tokens.append(token)

    # Build patterns
    path_pattern = None
    if path_token:
        # TODO: Build path pattern from path tokens
        path_pattern = None  # Placeholder for now

    # Build filename pattern from tokens
    pattern_parts = []
    for token in filename_tokens:
        if token.type in ['date', 'studio', 'studio_code', 'performers', 'sequence', 'title']:
            pattern_parts.append(f"{{{token.type}}}")
        else:
            pattern_parts.append("{text}")
    filename_pattern = " ".join(pattern_parts) if pattern_parts else ""

    # Extract labeled fields from parser result
    studio = result.studio
    title = result.title
    sequence = result.sequence
    group = result.group

    # Collect performers and dates from tokens
    performers = []
    date = None
    studio_code = None

    for token in tokens:
        if token.type == 'performers':
            performers.append(token.value)
        elif token.type == 'date':
            date = token.value
        elif token.type == 'studio_code':
            studio_code = token.value

    # Calculate unlabeled tokens
    unlabeled_path_tokens = set()
    unlabeled_filename_tokens = set()

    labeled_types = {'path', 'date', 'studio', 'studio_code', 'performers', 'sequence', 'title'}
    for token in filename_tokens:
        if token.type not in labeled_types and token.value.strip():
            unlabeled_filename_tokens.add(token.value)

    # Calculate match stats
    total_filename_tokens = len(filename_tokens)
    matched_tokens = sum(1 for t in filename_tokens if t.type in labeled_types)
    match_rate = matched_tokens / total_filename_tokens if total_filename_tokens > 0 else 0.0

    match_stats = {
        "path_tokens": 1 if path_token else 0,
        "filename_tokens": total_filename_tokens,
        "matched_tokens": matched_tokens,
        "match_rate": round(match_rate, 4)
    }

    return ParsedRow(
        input=filename,
        removed=removed_str,
        path=path_token.value if path_token else None,
        filename_cleaned=result.cleaned,
        path_pattern=path_pattern,
        filename_pattern=filename_pattern,
        studio=studio,
        title=title,
        performers=', '.join(performers) if performers else None,
        date=date,
        studio_code=studio_code,
        sequence=sequence,
        group=group,
        unlabeled_path_tokens=unlabeled_path_tokens if unlabeled_path_tokens else None,
        unlabeled_filename_tokens=unlabeled_filename_tokens if unlabeled_filename_tokens else None,
        match_stats=match_stats
    )


def calculate_blind_metrics(rows: List[ParsedRow]) -> Dict[str, Any]:
    """
    Calculate coverage metrics for blind mode.

    Metrics include:
    - Field coverage (% of rows with each field populated)
    - Pattern histogram (top 20 patterns)
    - Anomalies (unmapped studios, unclassified tokens, etc.)
    """
    total_rows = len(rows)

    # Field coverage
    field_coverage = {
        'studio': sum(1 for r in rows if r.studio) / total_rows,
        'performers': sum(1 for r in rows if r.performers) / total_rows,
        'date': sum(1 for r in rows if r.date) / total_rows,
        'studio_code': sum(1 for r in rows if r.studio_code) / total_rows,
        'title': sum(1 for r in rows if r.title) / total_rows,
        'sequence': sum(1 for r in rows if r.sequence) / total_rows,
        'group': sum(1 for r in rows if r.group) / total_rows,
    }

    # Overall match rate
    avg_match_rate = sum(r.match_stats['match_rate'] for r in rows) / total_rows

    # Pattern histogram
    patterns = [r.filename_pattern for r in rows if r.filename_pattern]
    pattern_histogram = Counter(patterns).most_common(20)

    # Anomalies
    anomalies = {
        'rows_with_unlabeled_tokens': sum(1 for r in rows if r.unlabeled_filename_tokens),
        'total_unlabeled_tokens': sum(len(r.unlabeled_filename_tokens) for r in rows if r.unlabeled_filename_tokens),
    }

    return {
        'mode': 'blind',
        'total_rows': total_rows,
        'field_coverage': field_coverage,
        'avg_match_rate': round(avg_match_rate, 4),
        'pattern_histogram': [{'pattern': p, 'count': c} for p, c in pattern_histogram],
        'anomalies': anomalies,
        'timestamp': datetime.now().isoformat()
    }


def load_reference_data(filepath: str, sheet_name: str = "Reference") -> List[ParsedRow]:
    """
    Load reference data from Excel file.

    Expects the same 16-column schema as our output.
    """
    wb = load_workbook(filepath, read_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Could not find '{sheet_name}' sheet in Excel file. Sheets present: {wb.sheetnames}")

        ws = wb[sheet_name]
        if ws is None:
            raise ValueError(f"Excel file has no '{sheet_name}' worksheet")

        # Get headers
        headers = [cell.value for cell in ws[1]]

        # Validate headers match our schema
        expected_headers = ParsedRow.get_headers()
        if headers != expected_headers:
            raise ValueError(f"Reference file headers don't match schema.\nExpected: {expected_headers}\nGot: {headers}")

        # Load rows
        reference_rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            # Convert cell values to appropriate types
            def to_str(val) -> str:
                return str(val) if val is not None else ""

            def to_str_or_none(val) -> Optional[str]:
                return str(val) if val is not None else None

            # Parse the row into ParsedRow
            parsed_row = ParsedRow(
                input=to_str(row[0]),
                removed=to_str(row[1]),
                path=to_str_or_none(row[2]),
                filename_cleaned=to_str(row[3]),
                path_pattern=to_str_or_none(row[4]),
                filename_pattern=to_str(row[5]),
                studio=to_str_or_none(row[6]),
                title=to_str_or_none(row[7]),
                performers=to_str_or_none(row[8]),
                date=to_str_or_none(row[9]),
                studio_code=to_str_or_none(row[10]),
                sequence=json.loads(str(row[11])) if row[11] else None,
                group=to_str_or_none(row[12]),
                unlabeled_path_tokens=ast.literal_eval(str(row[13])) if row[13] else None,
                unlabeled_filename_tokens=ast.literal_eval(str(row[14])) if row[14] else None,
                match_stats=json.loads(str(row[15])) if row[15] else {}
            )
            reference_rows.append(parsed_row)
    finally:
        wb.close()
    return reference_rows


def calculate_reference_metrics(rows: List[ParsedRow], reference_rows: List[ParsedRow], samples: int = 10) -> Dict[str, Any]:
    """
    Calculate comprehensive metrics for reference mode.

    Compare parsed results against reference labels and provide clear, separated metrics.
    """
    total_rows = len(rows)

    if len(reference_rows) != total_rows:
        raise ValueError(f"Row count mismatch: {total_rows} parsed vs {len(reference_rows)} reference")

    # Per-field metrics
    field_metrics = {}
    mismatches = []  # Store sample mismatches
    total_field_errors = 0
    files_with_any_errors = set()
    
    # Token metrics
    total_tokens = 0
    matched_tokens = 0

    for field in ['studio', 'performers', 'date', 'studio_code', 'title', 'sequence', 'group']:
        correct = 0
        false_positives = []  # We said X, reference said None
        false_negatives = []  # We said None, reference said X
        incorrect = []  # Both non-None but different

        for i in range(total_rows):
            parsed_val = getattr(rows[i], field)
            ref_val = getattr(reference_rows[i], field)

            if parsed_val == ref_val:
                correct += 1
            else:
                # Track mismatch
                mismatch_info = {
                    'input': rows[i].input,
                    'field': field,
                    'parsed': parsed_val,
                    'expected': ref_val
                }
                files_with_any_errors.add(i)

                if parsed_val is not None and ref_val is None:
                    false_positives.append(mismatch_info)
                elif parsed_val is None and ref_val is not None:
                    false_negatives.append(mismatch_info)
                else:
                    incorrect.append(mismatch_info)

        # Calculate field errors
        field_errors = len(false_positives) + len(false_negatives) + len(incorrect)
        total_field_errors += field_errors
        
        # Calculate percentage correct
        percentage_correct = (correct / total_rows) * 100 if total_rows > 0 else 0.0

        field_metrics[field] = {
            'correct': correct,
            'errors': field_errors,
            'percentage_correct': round(percentage_correct, 1),
            'false_positives': len(false_positives),
            'false_negatives': len(false_negatives),
            'incorrect': len(incorrect)
        }

        # Add sample mismatches (up to specified limit)
        if false_positives:
            mismatches.extend(false_positives[:samples])
        if false_negatives:
            mismatches.extend(false_negatives[:samples])
        if incorrect:
            mismatches.extend(incorrect[:samples])

    # Calculate token metrics
    for row in rows:
        total_tokens += row.match_stats.get('filename_tokens', 0) + row.match_stats.get('path_tokens', 0)
        matched_tokens += row.match_stats.get('matched_tokens', 0)

    token_match_rate = matched_tokens / total_tokens if total_tokens > 0 else 0.0

    # Calculate field-level metrics
    total_field_comparisons = total_rows * 7  # 7 fields
    total_correct_fields = sum(m['correct'] for m in field_metrics.values())
    field_accuracy = total_correct_fields / total_field_comparisons if total_field_comparisons > 0 else 0.0
    field_error_rate = total_field_errors / total_field_comparisons if total_field_comparisons > 0 else 0.0

    # Calculate file-level metrics
    files_perfectly_parsed = total_rows - len(files_with_any_errors)
    perfect_match_rate = files_perfectly_parsed / total_rows if total_rows > 0 else 0.0

    return {
        'mode': 'reference',
        'summary': {
            'total_files': total_rows,
            'total_field_errors': total_field_errors,
            'files_with_any_errors': len(files_with_any_errors),
            'files_perfectly_parsed': files_perfectly_parsed
        },
        'token_metrics': {
            'total_tokens': total_tokens,
            'matched_tokens': matched_tokens,
            'token_match_rate': round(token_match_rate, 3)
        },
        'field_metrics': {
            'total_field_comparisons': total_field_comparisons,
            'correct_field_matches': total_correct_fields,
            'field_accuracy': round(field_accuracy, 3),
            'field_error_rate': round(field_error_rate, 3)
        },
        'file_metrics': {
            'perfect_match_rate': round(perfect_match_rate, 3),
            'error_free_rate': round(perfect_match_rate, 3)
        },
        'field_breakdown': field_metrics,
        'sample_mismatches': mismatches[:samples * 3],  # Limit total samples
        'timestamp': datetime.now().isoformat()
    }


def create_diff_rows(parsed_rows: List[ParsedRow], reference_rows: List[ParsedRow]) -> List[ParsedRow]:
    """
    Create diff rows showing differences between parsed and reference.

    For cells that differ, format as: {"expected": <ref>, "returned": <parsed>}
    For cells that match, keep the agreed value.
    """
    diff_rows = []

    for i in range(len(parsed_rows)):
        parsed = parsed_rows[i]
        reference = reference_rows[i]

        # Create diff row
        diff = ParsedRow(
            input=parsed.input,  # Always use parsed input
            removed=parsed.removed if parsed.removed == reference.removed else f'{{"expected": "{reference.removed}", "returned": "{parsed.removed}"}}',
            path=parsed.path if parsed.path == reference.path else reference.path,  # Use reference if they differ
            filename_cleaned=parsed.filename_cleaned if parsed.filename_cleaned == reference.filename_cleaned else f'{{"expected": "{reference.filename_cleaned}", "returned": "{parsed.filename_cleaned}"}}',
            path_pattern=parsed.path_pattern if parsed.path_pattern == reference.path_pattern else reference.path_pattern,
            filename_pattern=parsed.filename_pattern if parsed.filename_pattern == reference.filename_pattern else f'{{"expected": "{reference.filename_pattern}", "returned": "{parsed.filename_pattern}"}}',
            studio=parsed.studio if parsed.studio == reference.studio else f'{{"expected": "{reference.studio}", "returned": "{parsed.studio}"}}',
            title=parsed.title if parsed.title == reference.title else f'{{"expected": "{reference.title}", "returned": "{parsed.title}"}}',
            performers=parsed.performers if parsed.performers == reference.performers else f'{{"expected": "{reference.performers}", "returned": "{parsed.performers}"}}',
            date=parsed.date if parsed.date == reference.date else f'{{"expected": "{reference.date}", "returned": "{parsed.date}"}}',
            studio_code=parsed.studio_code if parsed.studio_code == reference.studio_code else f'{{"expected": "{reference.studio_code}", "returned": "{parsed.studio_code}"}}',
            sequence=parsed.sequence if parsed.sequence == reference.sequence else {"expected": reference.sequence, "returned": parsed.sequence},
            group=parsed.group if parsed.group == reference.group else f'{{"expected": "{reference.group}", "returned": "{parsed.group}"}}',
            unlabeled_path_tokens=parsed.unlabeled_path_tokens if parsed.unlabeled_path_tokens == reference.unlabeled_path_tokens else reference.unlabeled_path_tokens,
            unlabeled_filename_tokens=parsed.unlabeled_filename_tokens if parsed.unlabeled_filename_tokens == reference.unlabeled_filename_tokens else reference.unlabeled_filename_tokens,
            match_stats=parsed.match_stats
        )

        diff_rows.append(diff)

    return diff_rows


def is_discrepancy_value(value: Any) -> bool:
    """Check if a cell value represents a discrepancy."""
    if value is None:
        return False
    value_str = str(value)
    # Check if the value contains the discrepancy format
    return '{"expected":' in value_str or '"expected":' in value_str


def write_excel_sheet(ws, rows: List[ParsedRow], sheet_name: str, highlight_discrepancies: bool = False):
    """Helper to write a single sheet with data."""
    ws.title = sheet_name

    # Write header
    headers = ParsedRow.get_headers()
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)

    # Define yellow fill for discrepancies
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

    # Write data rows
    for row_idx, row in enumerate(rows, 2):
        excel_row = row.to_excel_row()
        for col_idx, value in enumerate(excel_row, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)

            # Highlight discrepancies in yellow if enabled
            if highlight_discrepancies and is_discrepancy_value(value):
                cell.fill = yellow_fill

    # Auto-adjust column widths
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        max_length = len(headers[col_idx - 1])

        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))

        ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

    # Add table formatting
    if len(rows) > 0:
        last_col = get_column_letter(len(headers))
        data_range = f"A1:{last_col}{len(rows) + 1}"

        # Use unique table name based on sheet name
        table_name = sheet_name.replace(" ", "") + "Table"
        table = Table(displayName=table_name, ref=data_range)
        style = TableStyleInfo(
            name='TableStyleMedium9',
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False
        )
        table.tableStyleInfo = style
        ws.add_table(table)


def write_excel_output(rows: List[ParsedRow], output_path: str, mode: str,
                       reference_rows: Optional[List[ParsedRow]] = None,
                       diff_rows: Optional[List[ParsedRow]] = None):
    """
    Write parsed results to Excel workbook.

    For blind mode: single sheet with results
    For reference mode: three sheets (Reference, Results, Diff)
    In reference mode, discrepancies in the Diff sheet are highlighted in yellow.
    """
    wb = Workbook()

    if mode == 'blind':
        # Single sheet for blind mode
        ws = wb.active
        if ws:
            write_excel_sheet(ws, rows, "Filename Parser Results")
    else:
        # Three sheets for reference mode
        if reference_rows and diff_rows:
            # Sheet 1: Reference
            ws_ref = wb.active
            if ws_ref:
                write_excel_sheet(ws_ref, reference_rows, "Reference")

            # Sheet 2: Results
            ws_results = wb.create_sheet("Results")
            write_excel_sheet(ws_results, rows, "Results")

            # Sheet 3: Diff (with yellow highlighting for discrepancies)
            ws_diff = wb.create_sheet("Diff")
            write_excel_sheet(ws_diff, diff_rows, "Diff", highlight_discrepancies=True)

    wb.save(output_path)


def write_json_metrics(metrics: Dict[str, Any], output_path: str):
    """Write metrics to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)


def main():
    """Main evaluation harness entry point."""
    args = parse_arguments()

    # Generate default output paths if not specified
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if not args.output_excel:
        args.output_excel = f"metrics/{args.mode}-{timestamp}.xlsx"
    if not args.output_json:
        args.output_json = f"metrics/{args.mode}-{timestamp}.json"

    print(f"=== Filename Parser Evaluation ({args.mode} mode) ===")
    print(f"Input: {args.input}")
    if not args.no_write:
        if not args.skip_excel:
            print(f"Excel output: {args.output_excel}")
        print(f"JSON output: {args.output_json}")

    # Read input filenames
    print("\nReading input...")
    reference_sheet_name = "Reference" if args.mode == 'reference' else None
    filenames = read_input_file(args.input, args.limit, sheet_name=reference_sheet_name)
    print(f"Found {len(filenames)} filenames to process")

    # Initialize parser
    parser = FilenameParser()

    # Parse all filenames
    print("\nParsing filenames...")
    rows = []
    for idx, filename in enumerate(filenames, 1):
        if idx % 100 == 0:
            print(f"  Processed {idx}/{len(filenames)}...")

        row = parse_filename(parser, filename)
        rows.append(row)

    print(f"Completed parsing {len(rows)} filenames")

    # Calculate metrics
    print(f"\nCalculating {args.mode} mode metrics...")
    reference_rows = None
    diff_rows = None

    if args.mode == 'blind':
        metrics = calculate_blind_metrics(rows)
    else:
        # Reference mode: load reference data and calculate diff
        print(f"Loading reference data from {args.input}...")
        reference_rows = load_reference_data(args.input, sheet_name="Reference")

        print(f"Comparing {len(rows)} parsed rows vs {len(reference_rows)} reference rows...")
        metrics = calculate_reference_metrics(rows, reference_rows, args.samples)

        # Create diff rows
        diff_rows = create_diff_rows(rows, reference_rows)

    # Print summary
    print("\n=== Metrics Summary ===")
    if args.mode == 'blind':
        print(f"Total rows: {metrics['total_rows']}")
        print(f"Average match rate: {metrics['avg_match_rate']:.2%}")
        print("\nField coverage:")
        for field, coverage in metrics['field_coverage'].items():
            print(f"  {field}: {coverage:.2%}")
        print(f"\nTop 5 patterns:")
        for item in metrics['pattern_histogram'][:5]:
            print(f"  {item['pattern']}: {item['count']} occurrences")
    else:
        # Reference mode summary
        summary = metrics['summary']
        token_metrics = metrics['token_metrics']
        field_metrics_summary = metrics['field_metrics']
        file_metrics = metrics['file_metrics']
        
        print(f"=== SUMMARY ===")
        print(f"Total files: {summary['total_files']}")
        print(f"Files with any errors: {summary['files_with_any_errors']}")
        print(f"Files perfectly parsed: {summary['files_perfectly_parsed']}")
        print(f"Total field errors: {summary['total_field_errors']}")
        
        print(f"\n=== TOKEN METRICS ===")
        print(f"Total tokens: {token_metrics['total_tokens']}")
        print(f"Matched tokens: {token_metrics['matched_tokens']}")
        print(f"Token match rate: {token_metrics['token_match_rate']:.1%}")
        
        print(f"\n=== FIELD METRICS ===")
        print(f"Total field comparisons: {field_metrics_summary['total_field_comparisons']}")
        print(f"Correct field matches: {field_metrics_summary['correct_field_matches']}")
        print(f"Field accuracy: {field_metrics_summary['field_accuracy']:.1%}")
        print(f"Field error rate: {field_metrics_summary['field_error_rate']:.1%}")
        
        print(f"\n=== FILE METRICS ===")
        print(f"Perfect match rate: {file_metrics['perfect_match_rate']:.1%}")
        print(f"Error-free rate: {file_metrics['error_free_rate']:.1%}")
        
        print(f"\n=== FIELD BREAKDOWN ===")
        for field, field_data in metrics['field_breakdown'].items():
            print(f"  {field}:")
            print(f"    Correct: {field_data['correct']}/{summary['total_files']}")
            print(f"    Errors: {field_data['errors']}")
            print(f"    Percentage correct: {field_data['percentage_correct']:.1f}%")

        if metrics.get('sample_mismatches'):
            print(f"\n=== SAMPLE MISMATCHES ===")
            print(f"Showing up to {args.samples} per field:")
            for mismatch in metrics['sample_mismatches'][:5]:
                print(f"  {mismatch['field']}: {mismatch['input'][:50]}...")
                print(f"    Expected: {mismatch['expected']}")
                print(f"    Parsed: {mismatch['parsed']}")

    # Write outputs
    if not args.no_write:
        if not args.skip_excel:
            print(f"\nWriting Excel output to {args.output_excel}...")
            write_excel_output(rows, args.output_excel, args.mode,
                             reference_rows=reference_rows,
                             diff_rows=diff_rows)

        print(f"Writing JSON metrics to {args.output_json}...")
        write_json_metrics(metrics, args.output_json)

        print("\n✓ Evaluation complete!")
    else:
        print("\n✓ Dry-run complete (no files written)")


if __name__ == '__main__':
    main()
