#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LittleTools Common Utilities

This module provides shared functionality for all tools in the LittleTools project.
It centralizes common operations to reduce code duplication and improve maintainability.

Features:
    - Signal handling for graceful interruption (Ctrl+C)
    - Safe file deletion (sends files to recycle bin/trash)
    - File and directory operations
    - Console output formatting and utilities
    - Cross-platform compatibility helpers

Usage:
    from little_tools_utils import (
        setup_signal_handler, safe_delete, ensure_dir_exists,
        print_separator, clear_screen_if_compact
    )
"""

import os
import sys
import signal
import platform
import shutil
from pathlib import Path
from typing import List, Optional, Union, Callable
import send2trash  # * For safe file deletion to recycle bin

# * Better Comments:
# * Important
# ! Warning
# ? Question
# TODO:

# * Global variables for signal handling
_interrupted = False
_cleanup_functions: List[Callable] = []


def is_interrupted() -> bool:
    """
    Check if the program has been interrupted by a signal.
    
    Returns:
        bool: True if interrupted, False otherwise.
    """
    return _interrupted


def register_cleanup_function(func: Callable) -> None:
    """
    Register a cleanup function to be called when the program is interrupted.
    
    Args:
        func: A callable that will be executed during cleanup.
    """
    global _cleanup_functions
    _cleanup_functions.append(func)


def _signal_handler(signum, frame):
    """
    Handle interrupt signals gracefully.
    
    This function is called when the program receives an interrupt signal
    (e.g., Ctrl+C). It sets the global interrupted flag and calls all
    registered cleanup functions.
    
    Args:
        signum: Signal number.
        frame: Current stack frame.
    """
    global _interrupted
    _interrupted = True
    
    print("\n\n! Operation interrupted by user. Cleaning up...")
    
    # * Execute all registered cleanup functions
    for cleanup_func in _cleanup_functions:
        try:
            cleanup_func()
        except Exception as e:
            print(f"! Warning: Cleanup function failed: {e}")
    
    sys.exit(0)


def setup_signal_handler() -> None:
    """
    Set up signal handler for graceful interruption.
    
    This function configures the program to handle interrupt signals
    (such as Ctrl+C) gracefully by calling the internal signal handler.
    
    Example:
        setup_signal_handler()
        # Your main program logic here
        # If user presses Ctrl+C, cleanup will be performed automatically
    """
    signal.signal(signal.SIGINT, _signal_handler)


def safe_delete(file_path: Union[str, Path]) -> bool:
    """
    Safely delete a file by sending it to the recycle bin/trash.
    
    This function uses the send2trash library to move files to the
    system's recycle bin instead of permanently deleting them.
    
    Args:
        file_path: Path to the file to delete.
        
    Returns:
        bool: True if deletion was successful, False otherwise.
        
    Example:
        if safe_delete("temp_file.txt"):
            print("File moved to recycle bin")
        else:
            print("Failed to delete file")
    """
    try:
        file_path = Path(file_path)
        if file_path.exists():
            send2trash.send2trash(str(file_path))
            print(f"* File moved to recycle bin: {file_path.name}")
            return True
        else:
            print(f"! Warning: File not found: {file_path}")
            return False
    except Exception as e:
        print(f"! Error deleting file {file_path}: {e}")
        return False


def ensure_dir_exists(dir_path: Union[str, Path]) -> bool:
    """
    Create directory if it doesn't exist.
    
    Args:
        dir_path: Path to the directory to create.
        
    Returns:
        bool: True if directory exists or was created successfully, False otherwise.
        
    Example:
        if ensure_dir_exists("output/processed"):
            print("Directory is ready")
    """
    try:
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"! Error creating directory {dir_path}: {e}")
        return False


def get_files_by_extension(directory: Union[str, Path], extensions: List[str]) -> List[Path]:
    """
    Get all files with specified extensions from a directory.
    
    Args:
        directory: Path to the directory to search.
        extensions: List of file extensions to search for (including the dot).
        
    Returns:
        List[Path]: List of matching file paths.
        
    Example:
        audio_files = get_files_by_extension("input/", [".mp3", ".wav", ".flac"])
        for file in audio_files:
            print(f"Found: {file}")
    """
    try:
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            return []
        
        files = []
        for ext in extensions:
            # * Normalize extension format
            if not ext.startswith('.'):
                ext = '.' + ext
            files.extend(directory.glob(f"*{ext.lower()}"))
            files.extend(directory.glob(f"*{ext.upper()}"))
        
        return sorted(list(set(files)))  # Remove duplicates and sort
    except Exception as e:
        print(f"! Error scanning directory {directory}: {e}")
        return []


def check_file_exists_with_overwrite(output_path: Union[str, Path], overwrite: bool = False) -> bool:
    """
    Check if output file exists and handle based on overwrite setting.
    
    Args:
        output_path: Path to the output file.
        overwrite: Whether to overwrite existing files.
        
    Returns:
        bool: True if file should be skipped (exists and no overwrite), False otherwise.
        
    Example:
        if check_file_exists_with_overwrite("output.txt", overwrite=False):
            print("File exists, skipping")
            return
        # Process file...
    """
    output_path = Path(output_path)
    
    if output_path.exists():
        if overwrite:
            print(f"* File exists, will overwrite: {output_path.name}")
            return False
        else:
            print(f"* File exists, skipping: {output_path.name}")
            return True
    return False


def clean_partial_output(output_path: Union[str, Path], max_attempts: int = 3) -> bool:
    """
    Delete a partially processed output file using safe deletion.
    
    Args:
        output_path: Path to the output file.
        max_attempts: Maximum number of deletion attempts.
        
    Returns:
        bool: True if file was deleted, False otherwise.
        
    Example:
        if process_failed:
            clean_partial_output("partial_output.mkv")
    """
    output_path = Path(output_path)
    
    if not output_path.exists():
        return False

    # * Try deletion with retries for locked files
    for attempt in range(max_attempts):
        try:
            if safe_delete(output_path):
                return True
        except Exception as e:
            if attempt < max_attempts - 1:
                import time
                time.sleep(1)  # Wait before retry
            else:
                print(f"! Failed to delete partial file after {max_attempts} attempts: {e}")
    
    return False


def print_separator(char: str = "═", length: int = 50) -> None:
    """
    Print a separator line for better console output readability.
    
    Args:
        char: Character to use for the separator.
        length: Length of the separator line.
        
    Example:
        print_separator()
        print("Section Title")
        print_separator("─", 30)
    """
    print("\n" + char * length + "\n")


def print_file_info(filename: str, current: int, total: int, extra_info: str = "") -> None:
    """
    Print information about the file being processed.
    
    Args:
        filename: Name of the file being processed.
        current: Current file number.
        total: Total number of files to process.
        extra_info: Additional information to display.
        
    Example:
        print_file_info("video.mkv", 3, 10, "normalizing audio")
        # Output: [3/10] video.mkv (normalizing audio)
    """
    extra = f" ({extra_info})" if extra_info else ""
    print(f"[{current}/{total}] {filename}{extra}")


def print_status(message: str, status_type: str = "info") -> None:
    """
    Print a status message with appropriate formatting.
    
    Args:
        message: The message to print.
        status_type: Type of status ("info", "success", "warning", "error").
        
    Example:
        print_status("Processing complete", "success")
        print_status("File not found", "error")
    """
    prefixes = {
        "info": "*",
        "success": "✓",
        "warning": "!",
        "error": "!"
    }
    
    prefix = prefixes.get(status_type, "*")
    print(f"{prefix} {message}")


def clear_screen_if_compact(is_compact: bool) -> None:
    """
    Clear the terminal screen if compact mode is enabled.
    
    Args:
        is_compact: Whether to clear the screen.
        
    Example:
        clear_screen_if_compact(config.get("compact_mode", False))
    """
    if is_compact:
        os.system('cls' if platform.system() == "Windows" else 'clear')


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds.
        
    Returns:
        str: Formatted duration string (HH:MM:SS or MM:SS).
        
    Example:
        print(format_duration(3661))  # Output: "01:01:01"
        print(format_duration(125))   # Output: "02:05"
    """
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"


def get_platform_info() -> dict:
    """
    Get information about the current platform.
    
    Returns:
        dict: Dictionary containing platform information.
        
    Example:
        info = get_platform_info()
        if info["is_windows"]:
            # Windows-specific logic
    """
    system = platform.system()
    return {
        "system": system,
        "is_windows": system == "Windows",
        "is_linux": system == "Linux",
        "is_macos": system == "Darwin",
        "architecture": platform.architecture()[0],
        "python_version": platform.python_version()
    }


def check_command_available(command: str) -> bool:
    """
    Check if a command is available in the system PATH.
    
    Args:
        command: Command name to check.
        
    Returns:
        bool: True if command is available, False otherwise.
        
    Example:
        if check_command_available("ffmpeg"):
            print("FFmpeg is available")
        else:
            print("FFmpeg not found")
    """
    return shutil.which(command) is not None


def create_backup_name(file_path: Union[str, Path], suffix: str = "_backup") -> Path:
    """
    Create a backup filename by adding a suffix before the file extension.
    
    Args:
        file_path: Original file path.
        suffix: Suffix to add to the filename.
        
    Returns:
        Path: New backup file path.
        
    Example:
        backup = create_backup_name("config.json", "_old")
        # Returns: Path("config_old.json")
    """
    file_path = Path(file_path)
    return file_path.parent / f"{file_path.stem}{suffix}{file_path.suffix}"


# * Export commonly used functions for easy importing
__all__ = [
    "is_interrupted", "register_cleanup_function", "setup_signal_handler",
    "safe_delete", "ensure_dir_exists", "get_files_by_extension",
    "check_file_exists_with_overwrite", "clean_partial_output",
    "print_separator", "print_file_info", "print_status",
    "clear_screen_if_compact", "format_duration", "get_platform_info",
    "check_command_available", "create_backup_name"
] 