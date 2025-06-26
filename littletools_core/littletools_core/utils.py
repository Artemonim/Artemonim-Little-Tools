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
from typing import List, Optional, Union, Callable, Dict, Any
import send2trash  # * For safe file deletion to recycle bin
import time
import typer
from rich.console import Console

# * Better Comments:
# * Important
# ! Warning
# ? Question
# TODO:

# * Global variables for signal handling
_interrupted = False
_cleanup_functions: List[Callable] = []

# * Default directories used across all tools
DEFAULT_INPUT_DIR_NAME = "0-INPUT-0"
DEFAULT_OUTPUT_DIR_NAME = "0-OUTPUT-0"


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


def get_files_by_extension(
    directory: Union[str, Path], extensions: List[str]
) -> List[Path]:
    """Return all files with specified extensions from a directory."""
    try:
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            return []

        files: List[Path] = []
        for ext in extensions:
            if not ext.startswith("."):
                ext = "." + ext
            files.extend(directory.glob(f"*{ext.lower()}"))
            files.extend(directory.glob(f"*{ext.upper()}"))

        return sorted(list(set(files)))  # Remove duplicates and sort
    except Exception as e:  # noqa: BLE001
        print(f"! Error scanning directory {directory}: {e}")
        return []


def check_file_exists_with_overwrite(
    output_path: Union[str, Path], overwrite: bool = False
) -> bool:
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
                print(
                    f"! Failed to delete partial file after {max_attempts} attempts: {e}"
                )
    return False


def print_separator(char: str = "═", length: int = 50) -> None:
    """Print a separator line for better console readability."""
    print("\n" + char * length + "\n")


def print_file_info(
    filename: str, current: int, total: int, extra_info: str = ""
) -> None:
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
        os.system("cls" if platform.system() == "Windows" else "clear")


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


def prompt_for_path(
    prompt_message: str,
    default: Optional[Union[str, Path]] = None,
    must_exist: bool = True,
    file_okay: bool = True,
    dir_okay: bool = True,
) -> Path:
    """
    Interactively prompts the user for a path, validates it, and returns it.

    Args:
        prompt_message: The message to display to the user.
        default: An optional default path to suggest.
        must_exist: If True, the path must exist.
        file_okay: If True, the path can be a file.
        dir_okay: If True, the path can be a directory.

    Returns:
        A resolved pathlib.Path object.
    """
    console = Console()
    while True:
        path_str = typer.prompt(
            prompt_message, default=str(default) if default else None
        )
        cleaned_path_str = path_str.strip().strip('"').strip("'")
        if not cleaned_path_str:
            console.print("[red]! Path cannot be empty.[/red]")
            continue

        resolved_path = Path(cleaned_path_str).resolve()

        if must_exist and not resolved_path.exists():
            console.print(
                f"[red]! Path not found: '{resolved_path}'[/red]. Please try again."
            )
            continue

        if not file_okay and resolved_path.is_file():
            console.print(
                f"[red]! Path must be a directory, not a file: '{resolved_path}'[/red]."
            )
            continue

        if not dir_okay and resolved_path.is_dir():
            console.print(
                f"[red]! Path must be a file, not a directory: '{resolved_path}'[/red]."
            )
            continue

        return resolved_path


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


def get_default_io_paths(tool_slug: str = "") -> tuple[Path, Path]:
    """Return default input and output directory Path objects.

    Args:
        tool_slug: Optional sub-directory or suffix to append inside the output directory.

    Returns:
        (input_dir, output_dir)
    """
    cwd = Path.cwd()
    input_dir = cwd / DEFAULT_INPUT_DIR_NAME
    output_dir = cwd / DEFAULT_OUTPUT_DIR_NAME
    if tool_slug:
        output_dir = output_dir / tool_slug
    return input_dir, output_dir


def prompt_for_interactive_settings(
    settings_definitions: List[Dict[str, Any]],
    current_settings: Dict[str, Any],
    title: str = "Settings",
) -> Optional[Dict[str, Any]]:
    """
    Displays a generic interactive menu for configuring a set of options.

    This function provides a reusable, data-driven menu loop that allows users
    to modify settings before proceeding with an operation. It supports
    multiple-choice selections and boolean toggles.

    Args:
        settings_definitions: A list of dictionaries, where each dictionary
            defines a configurable setting for the menu. Each dictionary
            should have the following keys:
            - 'key' (str): The key that corresponds to this setting in the
              `current_settings` dictionary.
            - 'label' (str): The human-readable text to display for this setting.
            - 'type' (str): The type of control. Supported types are:
              - 'choice': Presents a list of options. Requires 'choices'.
              - 'toggle': A simple on/off or true/false switch.
            - 'choices' (Dict[str, str], optional): A dictionary mapping the
              display name of an option to its actual value. Required for
              'type' = 'choice'.
            Example:
            [
                {
                    "key": "quality", "label": "Quality", "type": "choice",
                    "choices": {"High": "10", "Medium": "20"}
                },
                {
                    "key": "overwrite", "label": "Overwrite", "type": "toggle"
                }
            ]
        current_settings: A dictionary containing the initial values for all
            settings defined in `settings_definitions`. The keys must match.
        title: The title to display at the top of the menu.

    Returns:
        A dictionary with the updated settings if the user decides to proceed
        (e.g., by selecting 'Start').
        Returns None if the user chooses to quit or aborts the operation.
    """
    console = Console()

    def _prompt_for_choice(label: str, choices: dict, current_value: str) -> str:
        console.print(f"\n[bold]Select {label}[/bold]")
        choice_map = {str(i + 1): value for i, value in enumerate(choices.values())}
        for i, (name, value) in enumerate(choices.items()):
            indicator = "[bold green]✓[/bold green]" if value == current_value else " "
            console.print(f"  {indicator} [green]{i+1}[/green]. {name}")

        default_idx_str = "1"
        for i, value in enumerate(choices.values()):
            if value == current_value:
                default_idx_str = str(i + 1)
                break

        while True:
            raw_input = typer.prompt("Your choice", default=default_idx_str)
            if raw_input in choice_map:
                return choice_map[raw_input]
            console.print(
                f"[red]Invalid choice. Please enter a number from 1 to {len(choices)}.[/red]"
            )

    while True:
        console.clear()
        console.print(f"[bold underline]{title}[/bold underline]")

        for i, definition in enumerate(settings_definitions, 1):
            key = definition["key"]
            label = definition["label"]
            setting_type = definition["type"]
            current_value = current_settings[key]

            display_value = ""
            if setting_type == "choice":
                choices = definition["choices"]
                display_value = next(
                    (name for name, value in choices.items() if value == current_value),
                    "N/A",
                )
            elif setting_type == "toggle":
                display_value = "On" if current_value else "Off"

            # Special case for codec toggle to make it more explicit
            if key == "codec" and setting_type == "toggle":
                display_value = f"[bold]{'H264' if current_settings['codec'] == 'h264' else 'HEVC'}[/bold] (Toggle)"

            console.print(f" [cyan]{i}.[/cyan] {label:<15} : {display_value}")

        console.print("\n [bold green]S[/bold green]. Start")
        console.print(" [bold red]Q[/bold red]. Quit")

        choice = typer.prompt(
            "\nSelect an option to change, or start/quit", default="S"
        ).lower()

        if choice == "s":
            return current_settings
        elif choice == "q":
            return None

        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(settings_definitions):
                selected_def = settings_definitions[choice_idx]
                key = selected_def["key"]
                setting_type = selected_def["type"]

                if setting_type == "choice":
                    current_settings[key] = _prompt_for_choice(
                        selected_def["label"],
                        selected_def["choices"],
                        current_settings[key],
                    )
                elif setting_type == "toggle":
                    current_settings[key] = not current_settings[key]

                # Special handling for codec toggle
                if key == "codec" and setting_type == "toggle":
                    current_settings[key] = (
                        "h264" if current_settings[key] == "hevc" else "hevc"
                    )

            else:
                console.print(
                    f"[red]! Invalid choice '{choice}'. Please try again.[/red]"
                )
                time.sleep(1.5)
        except ValueError:
            console.print(f"[red]! Invalid input. Please enter a number or S/Q.[/red]")
            time.sleep(1.5)


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
    "prompt_for_path",
    "BatchTimeEstimator",
    "get_default_io_paths",
    "prompt_for_interactive_settings",
]
