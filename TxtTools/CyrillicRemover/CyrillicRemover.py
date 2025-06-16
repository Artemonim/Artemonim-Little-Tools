#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cyrillic Remover Tool

This script removes Cyrillic characters from text files.
It processes all .txt files in a given directory, and for each file,
it creates a new version with all Cyrillic letters removed.

The processed files are saved to an output directory, preserving the original filenames.
"""

import argparse
import sys
from pathlib import Path
import time

# * Add the project root to the path to allow importing from little_tools_utils
# ! We need to go up three levels from TxtTools/CyrillicRemover/
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from little_tools_utils import (
    setup_signal_handler,
    is_interrupted,
    get_files_by_extension,
    ensure_dir_exists,
    check_file_exists_with_overwrite,
    print_separator,
    print_file_info,
    print_status,
    format_duration
)

# --- Configuration ---
DEFAULT_OUTPUT_FOLDER = "0-OUTPUT-0/CyrillicRemoved"
SUPPORTED_EXTENSIONS = [".txt"]

def remove_cyrillic(text: str) -> str:
    """
    Removes Cyrillic characters from a string.

    This function iterates over each character in the input string and
    builds a new string containing only non-Cyrillic characters.
    It covers the main Cyrillic block (U+0400–U+04FF) and the
    Cyrillic Supplement block (U+0500–U+052F).

    Args:
        text: The input string.

    Returns:
        A new string with Cyrillic characters removed.
    """
    # Exclude characters in the Cyrillic Unicode blocks
    return ''.join(
        char for char in text
        if not ('\u0400' <= char <= '\u04FF' or '\u0500' <= char <= '\u052F')
    )

def process_file(file_path: Path, output_dir: Path, overwrite: bool):
    """
    Processes a single text file to remove Cyrillic characters.

    Args:
        file_path: The path to the input text file.
        output_dir: The directory where the processed file will be saved.
        overwrite: A boolean indicating whether to overwrite existing files.

    Returns:
        A string indicating the status of the operation ('processed', 'skipped', 'error').
    """
    output_path = output_dir / file_path.name
    
    if check_file_exists_with_overwrite(output_path, overwrite):
        return "skipped"

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        cleaned_content = remove_cyrillic(content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        print_status(f"Successfully removed Cyrillic from: {file_path.name}", "success")
        return "processed"
        
    except Exception as e:
        print_status(f"Error processing file {file_path.name}: {e}", "error")
        return "error"

def main():
    """
    Main function to run the Cyrillic remover script.
    """
    parser = argparse.ArgumentParser(
        description="Removes Cyrillic characters from .txt files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_path",
        type=str,
        nargs='?',
        default="0-INPUT-0",
        help="Path to a single .txt file or a directory containing .txt files.\n(default: 0-INPUT-0)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=DEFAULT_OUTPUT_FOLDER,
        help=f"Output directory for processed files.\n(default: {DEFAULT_OUTPUT_FOLDER})"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in the output directory."
    )
    
    args = parser.parse_args()
    
    # * Setup graceful interruption handling
    setup_signal_handler()
    
    input_path = Path(args.input_path)
    output_dir = Path(args.output)
    
    if not input_path.exists():
        print_status(f"Input path does not exist: {input_path}", "error")
        sys.exit(1)

    files_to_process = []
    if input_path.is_dir():
        print_status(f"Scanning directory: {input_path}")
        files_to_process = get_files_by_extension(input_path, SUPPORTED_EXTENSIONS)
    elif input_path.is_file():
        if input_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files_to_process.append(input_path)
        else:
            print_status(f"Input file is not a supported text file: {input_path.name}", "error")
            sys.exit(1)

    if not files_to_process:
        print_status("No text files found to process.", "warning")
        sys.exit(0)

    if not ensure_dir_exists(output_dir):
        print_status(f"Could not create output directory: {output_dir}", "error")
        sys.exit(1)

    print_separator()
    print(f"Found {len(files_to_process)} text file(s) to process.")
    print(f"Output will be saved to: {output_dir}")
    print_separator()

    stats = {"processed": 0, "skipped": 0, "errors": 0, "total": len(files_to_process)}
    start_time = time.monotonic()
    
    for i, file_path in enumerate(files_to_process):
        if is_interrupted():
            break
            
        print_file_info(file_path.name, i + 1, len(files_to_process))
        status = process_file(file_path, output_dir, args.overwrite)
        if status in stats:
            stats[status] += 1

    print_separator()
    duration = time.monotonic() - start_time
    print("Processing complete.")
    print(f"Total files: {stats['total']}")
    print(f"Processed: {stats['processed']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    print(f"Total time: {format_duration(duration)}")
    print_separator()


if __name__ == "__main__":
    main() 