#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LittleTools Core Utilities

This module provides shared functionality for all tools in the LittleTools project.
It centralizes common operations to reduce code duplication and improve maintainability.

Features:
    - Signal handling for graceful interruption (Ctrl+C)
    - Safe file deletion (sends files to recycle bin/trash)
    - File and directory operations
    - Console output formatting and utilities
    - Cross-platform compatibility helpers

Usage:
    from littletools_core.utils import (
        setup_signal_handler, safe_delete, ensure_dir_exists,
        print_separator, clear_screen_if_compact
    )
"""

# * NOTE: The implementation below is migrated from the former ``little_tools_utils``
#   module without functional changes.

import os
import sys
import signal
import platform
import shutil
from pathlib import Path
from typing import List, Optional, Union, Callable
import send2trash  # * For safe file deletion to recycle bin
import time

# * Better Comments:
# * Important
# ! Warning
# ? Question
# TODO:

# * Global variables for signal handling
_interrupted = False
_cleanup_functions: List[Callable] = []


def is_interrupted() -> bool:
    """Check if the program has been interrupted by a signal."""
    return _interrupted


def register_cleanup_function(func: Callable) -> None:
    """Register a cleanup function to be called when the program is interrupted."""
    global _cleanup_functions
    _cleanup_functions.append(func)


def _signal_handler(signum, frame):  # noqa: D401
    """Handle interrupt signals gracefully (e.g., Ctrl+C)."""
    global _interrupted
    _interrupted = True

    print("\n\n! Operation interrupted by user. Cleaning up...")

    # * Execute all registered cleanup functions
    for cleanup_func in _cleanup_functions:
        try:
            cleanup_func()
        except Exception as e:  # noqa: BLE001
            print(f"! Warning: Cleanup function failed: {e}")

    sys.exit(0)


def setup_signal_handler() -> None:
    """Set up signal handler for graceful interruption."""
    signal.signal(signal.SIGINT, _signal_handler)


def safe_delete(file_path: Union[str, Path]) -> bool:
    """Safely delete a file by sending it to the recycle bin/trash."""
    try:
        file_path = Path(file_path)
        if file_path.exists():
            send2trash.send2trash(str(file_path))
            print(f"* File moved to recycle bin: {file_path.name}")
            return True
        print(f"! Warning: File not found: {file_path}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"! Error deleting file {file_path}: {e}")
        return False


def ensure_dir_exists(dir_path: Union[str, Path]) -> bool:
    """Create directory if it doesn't exist."""
    try:
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"! Error creating directory {dir_path}: {e}")
        return False


def get_files_by_extension(directory: Union[str, Path], extensions: List[str]) -> List[Path]:
    """Return all files with specified extensions from a directory."""
    try:
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            return []

        files: List[Path] = []
        for ext in extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            files.extend(directory.glob(f"*{ext.lower()}"))
            files.extend(directory.glob(f"*{ext.upper()}"))

        return sorted(list(set(files)))  # Remove duplicates and sort
    except Exception as e:  # noqa: BLE001
        print(f"! Error scanning directory {directory}: {e}")
        return []


def check_file_exists_with_overwrite(output_path: Union[str, Path], overwrite: bool = False) -> bool:
    """Check if output file exists and handle based on overwrite flag."""
    output_path = Path(output_path)
    if output_path.exists():
        if overwrite:
            print(f"* File exists, will overwrite: {output_path.name}")
            return False
        print(f"* File exists, skipping: {output_path.name}")
        return True
    return False


def clean_partial_output(output_path: Union[str, Path], max_attempts: int = 3) -> bool:
    """Delete a partially processed output file using safe deletion."""
    output_path = Path(output_path)
    if not output_path.exists():
        return False

    for attempt in range(max_attempts):
        try:
            if safe_delete(output_path):
                return True
        except Exception as e:  # noqa: BLE001
            if attempt < max_attempts - 1:
                time.sleep(1)
            else:
                print(f"! Failed to delete partial file after {max_attempts} attempts: {e}")
    return False


def print_separator(char: str = "═", length: int = 50) -> None:
    """Print a separator line for better console readability."""
    print("\n" + char * length + "\n")


def print_file_info(filename: str, current: int, total: int, extra_info: str = "") -> None:
    """Print information about the file being processed."""
    extra = f" ({extra_info})" if extra_info else ""
    print(f"[{current}/{total}] {filename}{extra}")


def print_status(message: str, status_type: str = "info") -> None:
    """Print a status message with appropriate formatting."""
    prefixes = {
        "info": "*",
        "success": "✓",
        "warning": "!",
        "error": "!",
    }
    prefix = prefixes.get(status_type, "*")
    print(f"{prefix} {message}")


def clear_screen_if_compact(is_compact: bool) -> None:
    """Clear the terminal screen if compact mode is enabled."""
    if is_compact:
        os.system('cls' if platform.system() == "Windows" else 'clear')


def format_duration(seconds: float) -> str:
    """Format seconds to HH:MM:SS or MM:SS."""
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def get_platform_info() -> dict:
    """Return information about the current platform."""
    system = platform.system()
    return {
        "system": system,
        "is_windows": system == "Windows",
        "is_linux": system == "Linux",
        "is_macos": system == "Darwin",
        "architecture": platform.architecture()[0],
        "python_version": platform.python_version(),
    }


def check_command_available(command: str) -> bool:
    """Return True if a command is available in PATH."""
    return shutil.which(command) is not None


def create_backup_name(file_path: Union[str, Path], suffix: str = "_backup") -> Path:
    """Create a backup filename by adding a suffix before the extension."""
    file_path = Path(file_path)
    return file_path.parent / f"{file_path.stem}{suffix}{file_path.suffix}"


class BatchTimeEstimator:
    """Estimate remaining time for a batch process based on workload."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.total_workload: float = 0.0
        self.workload_processed: float = 0.0
        self.items_processed: int = 0

    def start(self) -> None:
        """Start the master timer for the batch process."""
        self.start_time = time.time()

    def add_item(self, workload: float) -> None:
        """Add an item's workload to the total."""
        if workload > 0:
            self.total_workload += workload

    def update(self, workload_done: float) -> None:
        """Update the estimator with the workload just completed."""
        if workload_done > 0:
            self.workload_processed += workload_done
        self.items_processed += 1

    def get_eta_str(self) -> str:
        """Return formatted ETA or 'N/A' if not enough info."""
        if (
            self.start_time is None
            or self.items_processed == 0
            or self.workload_processed <= 0
        ):
            return "N/A"

        elapsed_time = time.time() - self.start_time
        if elapsed_time <= 0:
            return "N/A"
        processing_rate = self.workload_processed / elapsed_time
        if processing_rate <= 0:
            return "N/A"

        remaining_workload = self.total_workload - self.workload_processed
        estimated_seconds = remaining_workload / processing_rate
        return format_duration(estimated_seconds)


# * Export commonly used functions for easy importing
__all__ = [
    "is_interrupted",
    "register_cleanup_function",
    "setup_signal_handler",
    "safe_delete",
    "ensure_dir_exists",
    "get_files_by_extension",
    "check_file_exists_with_overwrite",
    "clean_partial_output",
    "print_separator",
    "print_file_info",
    "print_status",
    "clear_screen_if_compact",
    "format_duration",
    "get_platform_info",
    "check_command_available",
    "create_backup_name",
    "BatchTimeEstimator",
] 