#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cyrillic Remover Tool

This script removes Cyrillic characters from text files in several modes.
It processes all .txt files in a given directory, and for each file,
it creates a new version with Cyrillic characters or parts of lines removed.

The processed files are saved to an output directory, preserving the original filenames.
"""

import argparse
import sys
from pathlib import Path
import time

from littletools_core.utils import (
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


def is_cyrillic(char: str) -> bool:
    """
    Checks if a character is in the Cyrillic Unicode blocks.
    
    Args:
        char: The character to check.
    
    Returns:
        True if the character is Cyrillic, False otherwise.
    """
    return '\u0400' <= char <= '\u04FF' or '\u0500' <= char <= '\u052F'


def remove_all_cyrillic(text: str) -> str:
    """
    Mode 1: Removes all Cyrillic characters from a string.
    
    Args:
        text: The input string.
        
    Returns:
        A new string with all Cyrillic characters removed.
    """
    return ''.join(char for char in text if not is_cyrillic(char))


def remove_from_first_cyrillic(text: str) -> str:
    """
    Mode 2: For each line, removes text from the first Cyrillic character onward.
    
    Args:
        text: The input string containing one or more lines.
        
    Returns:
        The processed string with parts of lines removed.
    """
    processed_lines = []
    for line in text.splitlines():
        first_cyrillic_index = -1
        for i, char in enumerate(line):
            if is_cyrillic(char):
                first_cyrillic_index = i
                break
        
        if first_cyrillic_index != -1:
            processed_lines.append(line[:first_cyrillic_index])
        else:
            processed_lines.append(line)
    return "\n".join(processed_lines)


def remove_to_last_cyrillic(text: str) -> str:
    """
    Mode 3: For each line, removes text from the start to the last Cyrillic character.
    
    Args:
        text: The input string containing one or more lines.
        
    Returns:
        The processed string with parts of lines removed.
    """
    processed_lines = []
    for line in text.splitlines():
        last_cyrillic_index = -1
        for i, char in enumerate(line):
            if is_cyrillic(char):
                last_cyrillic_index = i
        
        if last_cyrillic_index != -1:
            processed_lines.append(line[last_cyrillic_index + 1:])
        else:
            processed_lines.append(line)
    return "\n".join(processed_lines)


def process_file(file_path: Path, output_dir: Path, overwrite: bool, mode: int):
    """
    Processes a single text file to remove Cyrillic characters based on the selected mode.

    Args:
        file_path: The path to the input text file.
        output_dir: The directory where the processed file will be saved.
        overwrite: A boolean indicating whether to overwrite existing files.
        mode: An integer (1, 2, or 3) specifying the removal mode.

    Returns:
        A string indicating the status of the operation ('processed', 'skipped', 'error').
    """
    output_path = output_dir / file_path.name
    
    if check_file_exists_with_overwrite(output_path, overwrite):
        return "skipped"

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        cleaned_content = ""
        if mode == 1:
            cleaned_content = remove_all_cyrillic(content)
        elif mode == 2:
            cleaned_content = remove_from_first_cyrillic(content)
        elif mode == 3:
            cleaned_content = remove_to_last_cyrillic(content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        print_status(f"Successfully processed (mode {mode}): {file_path.name}", "success")
        return "processed"
        
    except Exception as e:
        print_status(f"Error processing file {file_path.name}: {e}", "error")
        return "error"

def main():
    """
    Main function to run the Cyrillic remover script.
    """
    parser = argparse.ArgumentParser(
        description="Removes Cyrillic characters from .txt files using different modes.",
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
        "-m", "--mode",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help=(
            "Removal mode:\n"
            "1: Remove all Cyrillic characters (default).\n"
            "2: Remove from the first Cyrillic character to the end of the line.\n"
            "3: Remove from the start to the last Cyrillic character."
        )
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
        status = process_file(file_path, output_dir, args.overwrite, args.mode)
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