#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    --- AUTO-GENERATED DOCSTRING ---
    This docstring is automatically generated by Agent Docstrings.
    Do not modify this block directly.

    Classes/Functions:
    - ProcessingStats (line 74):
      - increment(key: str) -> None (line 86)
      - get_duration() -> float (line 90)
      - update_task_status(task_id: str, status: str) -> None (line 94)
      - remove_task(task_id: str) -> None (line 102)
      - register_process(proc: asyncio.subprocess.Process) -> None (line 110)
      - remove_process(proc: asyncio.subprocess.Process) -> None (line 114)
      - print_summary(elapsed_time: float) -> None (line 119)
      - print_status_line() -> None (line 163)
      - print_stats() -> None (line 171)
      - Functions:
        - get_max_workers(manual_limit: int = DEFAULT_THREAD_LIMIT) -> int (line 189)
        - print_final_stats(stats: Dict[str, int], start_time: float) -> None (line 204)
        - get_mkv_files_from_path(path: str) -> List[str] (line 224)
        - check_output_file_exists(output_path: str, overwrite: bool = False) -> bool (line 246)
        - get_nvenc_video_options(codec: str, quality: str) -> list[str] (line 391)
        - get_video_duration(input_path: str) -> Optional[float] (line 597)
        - get_video_resolution(input_path: str) -> Optional[tuple[int, int]] (line 627)
        - create_output_dir(path: str) -> None (line 811)
        - status_updater(stats: ProcessingStats, stop_event: asyncio.Event) -> None (line 821)
    --- END AUTO-GENERATED DOCSTRING ---
FFMPEG Utilities Module

Common utilities for video processing scripts using ffmpeg.
This module provides shared functionality for:
- Console output formatting
- FFmpeg command construction
- Audio track analysis
- Asynchronous processing management
- Signal handling
- File task management
- Progress reporting
"""

# * Future imports ----------------------------------------------------------------
from __future__ import annotations

# * Standard library imports -------------------------------------------------------
import asyncio
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence

# * Third-party imports -----------------------------------------------------------
from rich.console import Console

# * Local application imports -----------------------------------------------------
from littletools_core.utils import check_file_exists_with_overwrite
from littletools_core.utils import clean_partial_output
from littletools_core.utils import ensure_dir_exists
from littletools_core.utils import format_duration
from littletools_core.utils import print_separator

# * Configuration variables with defaults
DEFAULT_THREAD_LIMIT = 2
AUTO_THREAD_LIMIT_DIVIDER = 3
DEFAULT_TARGET_LOUDNESS = -16.0
DEFAULT_TRUE_PEAK = -1.5
DEFAULT_LOUDNESS_RANGE = 11.0
DEFAULT_OUTPUT_FOLDER = "./normalized"

# * Instantiate a shared Rich console for styled output
console = Console()


class ProcessingStats:
    """Class to track file processing statistics."""

    def __init__(self) -> None:
        """Initialize statistics counters."""
        super().__init__()
        self.stats: Dict[str, int] = defaultdict(int)
        self.start_time = time.monotonic()
        self.interrupted = False
        # * Track active ffmpeg processes (for cancellation)
        self.active_processes: List[asyncio.subprocess.Process] = []

    def increment(self, key: str) -> None:
        """Increment a stat counter."""
        self.stats[key] += 1

    def get_duration(self) -> float:
        """Get the elapsed processing time in seconds."""
        return time.monotonic() - self.start_time

    def update_task_status(self, task_id: str, status: str) -> None:
        """
        Update status for a specific task.

        This is a no-op in the legacy style implementation.
        """
        pass

    def remove_task(self, task_id: str) -> None:
        """
        Remove a task from tracking.

        This is a no-op in the legacy style implementation.
        """
        pass

    def register_process(self, proc: asyncio.subprocess.Process) -> None:
        """Register an active ffmpeg process for tracking."""
        self.active_processes.append(proc)

    def remove_process(self, proc: asyncio.subprocess.Process) -> None:
        """Remove a process from the active processes list."""
        if proc in self.active_processes:
            self.active_processes.remove(proc)

    def print_summary(self, elapsed_time: float) -> None:
        """Print final statistics in a consistent format."""
        processed = self.stats.get("success", 0) + self.stats.get("processed", 0)
        failed = self.stats.get("errors", 0)
        skipped = self.stats.get("skipped", 0)
        total = self.stats.get("total", processed + failed + skipped)

        copied = self.stats.get("copied", 0)
        skipped_copy = self.stats.get("skipped_copy", 0)
        copy_errors = self.stats.get("copy_errors", 0)

        console.print("\n--- [bold]Operation Summary[/bold] ---")
        if total > 0:
            console.print(f"  - Total videos considered: {total}")
        if processed > 0:
            console.print(f"  - [green]Successful conversions[/green]: {processed}")
        if skipped > 0:
            console.print(f"  - [yellow]Skipped conversions[/yellow]:    {skipped}")
        if failed > 0:
            console.print(f"  - [red]Failed conversions[/red]:       {failed}")

        if copied > 0 or skipped_copy > 0 or copy_errors > 0:
            console.print("  --- Non-video files ---")
            if copied > 0:
                console.print(f"  - [blue]Copied[/blue]:      {copied}")
            if skipped_copy > 0:
                console.print(f"  - [yellow]Skipped[/yellow]:     {skipped_copy}")
            if copy_errors > 0:
                console.print(f"  - [red]Errors[/red]:      {copy_errors}")

        if elapsed_time > 0:
            console.print(f"  - Elapsed time: {format_duration(elapsed_time)}")
            # * Show total size delta if recorded
            bytes_in = self.stats.get("bytes_in", 0)
            bytes_out = self.stats.get("bytes_out", 0)
            if bytes_in > 0:
                delta = bytes_out - bytes_in
                delta_mb = delta / (1024 * 1024)
                percent_change = (delta / bytes_in) * 100 if bytes_in != 0 else 0
                sign = "+" if delta > 0 else ""
                console.print(
                    f"  - Total size delta: {sign}{delta_mb:.2f} MB ({sign}{percent_change:.2f}%)"
                )

    def print_status_line(self) -> None:
        """
        Print current status line for all active tasks.

        This is a no-op in the legacy style implementation.
        """
        pass

    def print_stats(self) -> None:
        """Print final statistics."""
        # Print final statistics
        elapsed = self.get_duration()
        processed = self.stats.get("processed", 0)
        failed = self.stats.get("errors", 0)
        skipped = self.stats.get("skipped", 0)
        total = self.stats.get("total", 0)
        print_separator()
        print("ИТОГОВАЯ СТАТИСТИКА:")
        print(f"Всего файлов: {total}")
        print(f"Успешно обработано: {processed}")
        print(f"Пропущено: {skipped}")
        print(f"Ошибок: {failed}")
        print(f"Затраченное время: {format_duration(elapsed)}")
        print_separator()


def get_max_workers(manual_limit: int = DEFAULT_THREAD_LIMIT) -> int:
    """
    Calculate the optimal number of worker threads based on CPU count.

    Args:
        manual_limit: Minimum number of threads to use

    Returns:
        int: Calculated number of worker threads
    """
    cpu_count = os.cpu_count() or manual_limit
    return max(cpu_count // AUTO_THREAD_LIMIT_DIVIDER, manual_limit)


# Console output functions (some now imported from little_tools_utils)
def print_final_stats(stats: Dict[str, int], start_time: float) -> None:
    """
    Prints final processing statistics.

    Args:
        stats: Dictionary containing processing statistics
        start_time: Time when processing started
    """
    duration = time.monotonic() - start_time
    print_separator()
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print(f"Всего файлов: {stats['total']}")
    print(f"Успешно обработано: {stats['processed']}")
    print(f"Пропущено: {stats['skipped']}")
    print(f"Ошибок: {stats['errors']}")
    print(f"Затраченное время: {format_duration(duration)}")
    print_separator()


# File and path handling
def get_mkv_files_from_path(path: str) -> List[str]:
    """
    Get list of MKV files from a path.

    Args:
        path: Directory or file path

    Returns:
        list: List of MKV files to process

    Raises:
        ValueError: If path is not a directory or MKV file
    """
    if os.path.isdir(path):
        return [f for f in os.listdir(path) if f.lower().endswith(".mkv")]
    elif os.path.isfile(path) and path.lower().endswith(".mkv"):
        return [path]
    else:
        raise ValueError(f"{path} не является директорией или MKV файлом")


# File handling functions (now using little_tools_utils)
def check_output_file_exists(output_path: str, overwrite: bool = False) -> bool:
    """
    Check if output file exists and handle based on overwrite setting.

    Args:
        output_path: Path to the output file
        overwrite: Whether to overwrite existing files

    Returns:
        bool: True if file should be skipped, False otherwise
    """
    return check_file_exists_with_overwrite(output_path, overwrite)


# clean_partial_output is now imported from little_tools_utils


# FFmpeg utilities
async def get_audio_tracks(
    input_path: str, verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Get audio track information from media file.

    Args:
        input_path: Path to the input media file
        verbose: Whether to show verbose output

    Returns:
        list: List of audio tracks with metadata

    Raises:
        RuntimeError: If ffprobe fails or JSON parsing fails
    """
    input_path_quoted = str(Path(input_path))  # Proper path handling

    # Use more comprehensive metadata extraction flags
    ffprobe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index,codec_type,codec_name:stream_tags=*:format_tags=*",
        "-of",
        "json",
        input_path_quoted,
    ]

    # Debug: print ffprobe command
    if verbose:
        print(f"! Запрос метаданных аудио: {' '.join(ffprobe_cmd)}")

    ffprobe_proc = await asyncio.create_subprocess_exec(
        *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await ffprobe_proc.communicate()

    if ffprobe_proc.returncode != 0:
        raise RuntimeError(f"FFprobe error: {stderr.decode()}")

    try:
        audio_info: Dict[str, Any] = json.loads(stdout.decode())
        # * Explicitly cast to satisfy static type checkers
        tracks = audio_info.get("streams", [])
        if not isinstance(tracks, list):
            tracks = []

        # Debug: print found tracks
        if verbose:
            for i, track in enumerate(tracks):
                print(f"! Найдена аудиодорожка {i+1}: {track}")

        return tracks
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON parse error: {e}")


def build_loudnorm_filter_complex(
    audio_tracks: List[Dict[str, Any]],
    target_loudness: float = DEFAULT_TARGET_LOUDNESS,
    true_peak: float = DEFAULT_TRUE_PEAK,
    loudness_range: float = DEFAULT_LOUDNESS_RANGE,
) -> str:
    """
    Build ffmpeg filter_complex string for audio normalization.

    Args:
        audio_tracks: List of audio tracks
        target_loudness: Target integrated loudness in LUFS
        true_peak: Maximum true peak in dBTP
        loudness_range: Target loudness range in LU

    Returns:
        str: filter_complex string for ffmpeg
    """
    filter_complex = "".join(
        f"[0:a:{i}]loudnorm=I={target_loudness}:TP={true_peak}:LRA={loudness_range}[a{i}];"
        for i in range(len(audio_tracks))
    )
    return filter_complex.rstrip(";")


def get_metadata_options(
    audio_tracks: List[Dict[str, Any]], verbose: bool = False
) -> List[str]:
    """
    Generate ffmpeg metadata options to preserve audio track titles.

    Args:
        audio_tracks: List of audio tracks with metadata
        verbose: Whether to show verbose output

    Returns:
        list: FFmpeg metadata command arguments
    """
    metadata_options = []
    for i, track in enumerate(audio_tracks):
        # Look for title in different potential locations
        title = None
        if "tags" in track:
            title = track["tags"].get("title")
        if not title and "TAG:title" in track:
            title = track["TAG:title"]
        if not title and "TITLE" in track:
            title = track["TITLE"]

        # Add the title if found
        if title:
            # Escape quotes in title
            title = title.replace('"', '\\"')
            metadata_options.extend([f"-metadata:s:a:{i}", f"title={title}"])

            # Debug: print found title
            if verbose:
                print(f"! Сохранение названия аудиодорожки {i+1}: '{title}'")

    # If no titles were found, print a debug message
    if not metadata_options and verbose:
        print("! Не найдены названия аудиодорожек для сохранения")

    return metadata_options


def get_nvenc_video_options(codec: str, quality: str) -> list[str]:
    """
    Returns a list of recommended FFmpeg options for NVENC encoding.

    These settings are optimized for quality and compatibility based on
    experimental results.

    Args:
        codec: The video codec to use ('hevc' or 'h264').
        quality: The Constant Quality (CQ) value as a string.

    Returns:
        A list of FFmpeg command-line arguments for video encoding.
    """
    # * Base options are shared between H.264 and HEVC for consistency.
    base_options = [
        "-rc",
        "vbr_hq",
        "-cq",
        quality,
        "-spatial_aq",
        "1",
        "-temporal_aq",
        "1",
        "-aq-strength",
        "8",
        "-rc-lookahead",
        "32",
        "-refs",
        "4",
        "-movflags",
        "+faststart",
    ]

    if codec == "h264":
        # * H.264 uses a smaller number of B-frames.
        # * Use new preset system. p5 ('slow') is a good balance of speed/quality.
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-tune",
            "hq",
            "-bf",
            "2",
        ] + base_options

    # * Default to HEVC (h265), which has more advanced options.
    return [
        "-c:v",
        "hevc_nvenc",
        "-preset",
        "p5",
        "-tune",
        "hq",
        "-bf",
        "4",
        "-b_ref_mode",
        "middle",
    ] + base_options


async def run_ffmpeg_command(  # noqa: C901
    cmd: List[str],
    stats: Optional[ProcessingStats] = None,
    stats_key: str = "processed",
    quiet: bool = False,
    output_path: Optional[str] = None,
    file_position: Optional[int] = None,
    file_count: Optional[int] = None,
    filename: Optional[str] = None,
    total_duration: Optional[float] = None,
) -> bool:
    """
    Run an FFmpeg command and handle errors.

    Args:
        cmd: List containing the FFmpeg command and arguments
        stats: Optional ProcessingStats object to update
        stats_key: Key to increment in stats on success
        quiet: Whether to suppress progress output (progress bar still shows)
        output_path: Path to the output file (for cleaning up on cancel)
        file_position: Current file number
        file_count: Total number of files
        filename: Name of the file being processed
        total_duration: Total duration of the media file in seconds (for progress bar).

    Returns:
        bool: True if command succeeded, False otherwise
    """
    cmd = [arg for arg in cmd if arg]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE
        )
        # * Guarantee for type checkers that proc.stderr is not None
        assert proc.stderr is not None
        if stats:
            stats.register_process(proc)

        stderr_output: List[str] = []
        buffer = ""
        time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
        speed_pattern = re.compile(r"speed=\s*(\d+\.?\d*)x")

        file_prefix = ""
        if file_position and file_count and filename:
            file_prefix = f"[{file_position}/{file_count}] {filename} "

        while True:
            # Break loop if process has exited
            if proc.returncode is not None:
                break

            try:
                # Read chunk with a timeout to avoid blocking forever
                chunk = await asyncio.wait_for(proc.stderr.read(1024), timeout=2.0)
                if not chunk:
                    break  # End of stream
            except asyncio.TimeoutError:
                continue  # Check proc.returncode again

            buffer += chunk.decode("utf-8", errors="replace")
            # FFmpeg uses \r to update progress line
            lines = buffer.split("\r")
            buffer = lines.pop()  # Keep potentially incomplete line part in buffer

            for line_text in lines:
                if not line_text:
                    continue

                line_to_log = line_text.strip()
                if line_to_log:
                    stderr_output.append(line_to_log)

                if "time=" in line_text:
                    time_match = time_pattern.search(line_text)
                    speed_match = speed_pattern.search(line_text)

                    if time_match and total_duration and total_duration > 0:
                        hours, minutes, seconds, hundredths = map(
                            int, time_match.groups()
                        )
                        current_seconds = (
                            hours * 3600 + minutes * 60 + seconds + hundredths / 100
                        )
                        speed = (
                            float(speed_match.group(1))
                            if speed_match and float(speed_match.group(1)) > 0
                            else 1.0
                        )
                        progress_percent = (current_seconds / total_duration) * 100
                        eta_seconds = (
                            (total_duration - current_seconds) / speed
                            if speed > 0
                            else 0
                        )

                        bar_length = 30
                        filled_len = int(bar_length * progress_percent / 100)
                        bar = "█" * filled_len + "-" * (bar_length - filled_len)

                        progress_line = (
                            f"\r{file_prefix}{bar} {progress_percent:.1f}% | "
                            f"Speed: {speed:.1f}x | ETA: {format_duration(eta_seconds)}  "
                        )
                        sys.stdout.write(progress_line)
                        sys.stdout.flush()

        await proc.wait()

        sys.stdout.write("\r" + " " * 120 + "\r")
        sys.stdout.flush()

        if proc.returncode == 0:
            if stats:
                stats.increment(stats_key)
            return True
        else:
            if stats and not stats.interrupted:
                stats.increment("errors")
            # * Suppress FFmpeg error log details
            return False

    except asyncio.CancelledError:
        if output_path:
            clean_partial_output(output_path)
        raise
    except Exception as e:
        print(f"\n! Exception while running command for {filename}: {e}")
        if stats and not stats.interrupted:
            stats.increment("errors")
        return False
    finally:
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await proc.wait()
            except ProcessLookupError:
                pass  # Process already finished
        if stats and proc:
            stats.remove_process(proc)


async def get_video_duration(input_path: str) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    ffprobe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0 and stdout:
            return float(stdout.decode().strip())
        else:
            print(
                f"! ffprobe error getting duration for {Path(input_path).name}: {stderr.decode()}"
            )
            return None
    except Exception as e:
        print(f"! Exception getting duration for {Path(input_path).name}: {e}")
        return None


async def get_video_resolution(input_path: str) -> Optional[tuple[int, int]]:
    """Get video resolution (width, height) using ffprobe."""
    ffprobe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        str(input_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0 and stdout:
            res_str = stdout.decode().strip()
            if "x" in res_str:
                width, height = map(int, res_str.split("x"))
                return width, height
            else:
                print(
                    f"! ffprobe returned empty resolution for {Path(input_path).name}"
                )
                return None
        else:
            # ! Don't print error if there's no video stream, it's a valid case for audio-only files.
            if "Stream specifier v:0 matches no streams" not in stderr.decode():
                print(
                    f"! ffprobe error getting resolution for {Path(input_path).name}: {stderr.decode()}"
                )
            return None
    except Exception as e:
        print(f"! Exception getting resolution for {Path(input_path).name}: {e}")
        return None


async def convert_to_compatible_mp4(
    input_path: str, output_dir: str = "temp_videos"
) -> Optional[str]:
    """
    Converts a video file to a standard H.264 MP4 format for compatibility, scaled to 720p.
    """
    input_p = Path(input_path)
    output_p = Path(output_dir)
    # Always recreate output directory to ensure fresh conversion
    if output_p.exists():
        # clean up old temporary videos
        for f in output_p.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
    ensure_dir_exists(output_p)

    # Create a unique name for the temporary file
    temp_filename = f"{input_p.stem}_compatible.mp4"
    output_path = str(output_p / temp_filename)

    console.print(f"[*] Converting '{input_p.name}' to a 720p compatible MP4 format...")

    # FFMPEG command: scale to 720p using lanczos filter
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file
        "-i",
        str(input_path),
        "-vf",
        "scale=1280:720:flags=lanczos",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        output_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode == 0:
            console.print(
                f"[green]✓ Conversion successful. Output: {output_path}[/green]"
            )
            return output_path
        else:
            console.print(f"[red]! Failed to convert video '{input_p.name}'.[/red]")
            console.print(f"[dim]FFmpeg error: {stderr.decode()}[/dim]")
            return None
    except Exception as e:
        console.print(f"[red]! An exception occurred during conversion: {e}[/red]")
        return None


# Async task and signal handling
def setup_signal_handlers(  # noqa: C901
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
    tasks: Sequence[asyncio.Task[Any]],
    stats: Optional[ProcessingStats] = None,
) -> Callable[[], None]:
    """
    Set up signal handlers for graceful shutdown.

    Args:
        loop: Event loop
        stop_event: Event to signal task termination
        tasks: List of tasks to cancel
        stats: Optional ProcessingStats object

    Returns:
        Function to clean up signal handlers
    """

    def signal_handler() -> None:
        """Handle interrupt signals by canceling all tasks."""
        # Clear the status line
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

        if stats:
            stats.interrupted = True

        print("\n! Прерывание: остановка задач...")
        stop_event.set()

        # * First terminate any running ffmpeg processes
        if stats and hasattr(stats, "active_processes"):
            for proc in stats.active_processes[:]:  # Use a copy of the list
                if proc and proc.returncode is None:  # Process is still running
                    try:
                        # On Windows use taskkill to force terminate
                        if platform.system() == "Windows":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                        else:
                            # On Unix/Linux use terminate signal
                            proc.terminate()
                    except Exception:
                        pass  # Ignore errors during termination

        # Give processes a moment to terminate
        time.sleep(0.5)

        # Cancel all tasks
        for task in tasks:
            if not task.done():
                task.cancel()

    # ! Different signal handling for Windows vs Unix
    if platform.system() == "Windows":
        signal.signal(
            signal.SIGINT, lambda *_: loop.call_soon_threadsafe(signal_handler)
        )

        # Return function to remove signal handlers
        def cleanup() -> None:
            signal.signal(signal.SIGINT, signal.SIG_DFL)

    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        # Return function to remove signal handlers
        def cleanup() -> None:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    return cleanup


async def create_output_dir(path: str) -> None:
    """
    Create output directory if it doesn't exist.

    Args:
        path: Directory path to create
    """
    ensure_dir_exists(path)


async def status_updater(stats: ProcessingStats, stop_event: asyncio.Event) -> None:
    """
    Periodically update the status line.

    This function is disabled when using legacy-style direct output.

    Args:
        stats: ProcessingStats object
        stop_event: Event to signal task termination
    """
    try:
        # Simply wait for stop event when using direct output mode
        await stop_event.wait()
    except asyncio.CancelledError:
        pass


# Standard application structure
async def standard_main(
    args: Any,
    process_func: Callable[
        [Any, ProcessingStats, asyncio.Event], Coroutine[Any, Any, None]
    ],
    output_folder: str = DEFAULT_OUTPUT_FOLDER,
) -> ProcessingStats:
    """
    Standard main function for FFmpeg processing applications.

    Args:
        args: Parsed command-line arguments
        process_func: Function to process files, which should accept (args, stats, stop_event)
        output_folder: Default output folder path

    Returns:
        ProcessingStats: Object containing processing statistics
    """
    # Setup
    stats = ProcessingStats()
    output_dir = (
        args.output if hasattr(args, "output") and args.output else output_folder
    )
    await create_output_dir(output_dir)

    # Create task
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    # Pass stop_event to the processing function
    main_task: asyncio.Task[None] = asyncio.create_task(
        process_func(args, stats, stop_event)
    )

    # * Create status updater task
    status_task = asyncio.create_task(status_updater(stats, stop_event))

    # Collect all tasks
    tasks = [main_task, status_task]

    # Setup signal handling
    cleanup_signals = setup_signal_handlers(loop, stop_event, tasks, stats)

    try:
        await main_task
    except asyncio.CancelledError:
        print("\nЗадача отменена")
    finally:
        # Signal status updater to stop
        if not stop_event.is_set():
            stop_event.set()

        # Wait for status updater to stop
        if not status_task.done():
            try:
                await status_task
            except asyncio.CancelledError:
                pass
        # Clean up signal handlers
        cleanup_signals()

    # Print results
    stats.print_stats()
    return stats
