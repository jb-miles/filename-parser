#!/usr/bin/env python3
"""
Test script for filename parser.
Reads filenames from a text file and outputs results to CSV.
"""

import csv
import argparse
import sys
import json
from parser import FilenameParser
from modules import PreTokenizer


def main():
    """Process filenames from input file and write results to CSV."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process filenames and output results to CSV')
    parser.add_argument('input_file', nargs='?', help='Input file containing filenames (one per line)')
    parser.add_argument('output_file', nargs='?', help='Output CSV file')
    parser.add_argument('-p', '--pre-tokenize-only', action='store_true',
                       help='Only perform pre-tokenization and output original, removed, and cleaned')
    
    args = parser.parse_args()
    
    # Configuration
    if args.input_file:
        input_file = args.input_file
        output_file = args.output_file if args.output_file else input_file.replace('.txt', '-results.csv')
    else:
        input_file = "/Users/jbmiles/Documents/sample.txt"
        output_file = "/Users/jbmiles/Documents/sample-results.csv"

    filename_parser = FilenameParser()
    pre_tokenizer = PreTokenizer()

    print(f"Reading from: {input_file}")
    print(f"Writing to: {output_file}")
    if args.pre_tokenize_only:
        print("Mode: Pre-tokenization only")

    # Process filenames
    # Try to detect encoding and handle various input encodings
    import codecs
    import unicodedata
    
    def open_file_with_encoding_detection(filepath, mode='r'):
        """Open file with encoding detection for common encodings."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                return open(filepath, mode, encoding=encoding)
            except UnicodeDecodeError:
                continue
        
        # If all fail, try with errors='replace'
        return open(filepath, mode, encoding='utf-8', errors='replace')
    
    def normalize_unicode_text(text):
        """Normalize Unicode text to handle different character representations."""
        # Normalize to NFC form (canonical decomposition followed by composition)
        # This helps handle cases where the same character might be represented differently
        normalized = unicodedata.normalize('NFC', text)
        
        # Replace common problematic characters
        replacements = {
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
            '\u2013': '-',  # En dash
            '\u2014': '--', # Em dash
            '\u2026': '...', # Horizontal ellipsis
            '\u00a0': ' ',  # Non-breaking space
            '\u200b': '',   # Zero-width space
            '\u200e': '',   # Left-to-right mark
            '\u200f': '',   # Right-to-left mark
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
            
        return normalized
    
    with open_file_with_encoding_detection(input_file) as f_in, \
         open(output_file, 'w', newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out, quoting=csv.QUOTE_ALL)
        
        # We'll determine the header after processing all filenames to find max tokens
        header_written = False
        header = []
        json_keys = []
        all_rows_data = []  # Store all row data to determine max tokens
        
        line_count = 0
        for line in f_in:
            line = line.strip()
            
            # Normalize Unicode characters
            line = normalize_unicode_text(line)

            # Skip empty lines and section markers
            if not line or line in ['exceptions', 'sacrifice']:
                continue

            # Process the filename
            if args.pre_tokenize_only:
                result = pre_tokenizer.process(line)
                json_output = result.to_json()
                json_data = json.loads(json_output)
                
                # If this is the first row, write the header based on JSON keys
                if not header_written:
                    # Use keys from the JSON output plus Original, Cleaned
                    json_keys = list(json_data.keys())
                    header = ['Original'] + json_keys + ['Cleaned']
                    writer.writerow(header)
                    header_written = True
                
                # Prepare the row data
                row_data = {'Original': result.original}
                
                # Add values for each JSON key
                for key in json_keys:
                    if key == 'removed_tokens':
                        # Special handling for removed_tokens array
                        tokens_str = ' | '.join([f"{t['value']}({t['category']})" for t in json_data[key]])
                        row_data[key] = tokens_str
                    else:
                        row_data[key] = str(json_data[key])
                
                # Add the cleaned data
                row_data['Cleaned'] = result.cleaned
                
                # Write the row in the correct column order
                writer.writerow([row_data.get(col, '') for col in header])
            else:
                # Full processing pipeline - use parse() to run all steps
                final_result = filename_parser.parse(line)
                json_output = final_result.to_json()
                json_data = json.loads(json_output)

                # Get removed tokens separately for the "Removed" column
                pre_result = filename_parser.pre_tokenize(line)
                removed_str = ' | '.join([f"{t.value}({t.category})" for t in pre_result.removed_tokens])

                # Store row data for later processing
                row_data = {
                    'Original': final_result.original,
                    'Removed': removed_str,
                    'Cleaned': final_result.cleaned,
                    'path': json_data.get('path', ''),
                    'pattern': json_data.get('pattern', ''),
                    **json_data  # Include all token fields
                }
                all_rows_data.append(row_data)
            line_count += 1
        
        # After processing all rows, determine the header with max tokens
        if not header_written and all_rows_data:
            # Find all token keys across all rows
            all_token_keys = set()
            for row_data in all_rows_data:
                all_token_keys.update(key for key in row_data.keys() if key.startswith('token'))
            
            # Determine the maximum number of tokens
            max_tokens = 0
            if all_token_keys:
                token_numbers = [int(key[5:]) for key in all_token_keys if key[5:].isdigit()]
                max_tokens = max(token_numbers) + 1 if token_numbers else 0
            
            # Create header with Original, Removed, Cleaned, path, pattern, and token0 through tokenN
            header = ['Original', 'Removed', 'Cleaned', 'path', 'pattern']
            for i in range(max_tokens):
                header.append(f"token{i}")
            writer.writerow(header)
            header_written = True
            
            # Write all stored rows
            for row_data in all_rows_data:
                # Ensure all token columns are present
                for col in header:
                    if col.startswith('token') and col not in row_data:
                        row_data[col] = ''
                
                # Write the row in the correct column order
                writer.writerow([row_data.get(col, '') for col in header])

    print(f"Processed {line_count} filenames")
    print(f"Results written to {output_file}")


if __name__ == '__main__':
    main()
