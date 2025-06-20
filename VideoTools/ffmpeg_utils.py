#!/usr/bin/env python3
"""
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

import os
import asyncio
import json
import platform
import time
import sys
import re
from collections import defaultdict
from pathlib import Path
import subprocess
import signal
from typing import Optional

# * Import common utilities
sys.path.append(str(Path(__file__).parent.parent))
from little_tools_utils import (
    print_separator, print_file_info, ensure_dir_exists,
    clean_partial_output, check_file_exists_with_overwrite,
    format_duration
)

# * Configuration variables with defaults
DEFAULT_THREAD_LIMIT = 2
AUTO_THREAD_LIMIT_DIVIDER = 3
DEFAULT_TARGET_LOUDNESS = -16.0
DEFAULT_TRUE_PEAK = -1.5
DEFAULT_LOUDNESS_RANGE = 11.0
DEFAULT_OUTPUT_FOLDER = "./normalized"

class ProcessingStats:
    """Class to track file processing statistics."""
    
    def __init__(self):
        """Initialize statistics counters."""
        self.stats = defaultdict(int)
        self.start_time = time.monotonic()
        self.interrupted = False
        # * Track active ffmpeg processes (for cancellation)
        self.active_processes = []
    
    def increment(self, key):
        """Increment a stat counter."""
        self.stats[key] += 1
    
    def get_duration(self):
        """Get the elapsed processing time in seconds."""
        return time.monotonic() - self.start_time
    
    def update_task_status(self, task_id, status):
        """
        Update status for a specific task.
        
        This is a no-op in the legacy style implementation.
        """
        pass
    
    def remove_task(self, task_id):
        """
        Remove a task from tracking.
        
        This is a no-op in the legacy style implementation.
        """
        pass
    
    def register_process(self, proc):
        """Register an active ffmpeg process for tracking."""
        self.active_processes.append(proc)
    
    def remove_process(self, proc):
        """Remove a process from the active processes list."""
        if proc in self.active_processes:
            self.active_processes.remove(proc)
    
    def print_status_line(self):
        """
        Print current status line for all active tasks.
        
        This is a no-op in the legacy style implementation.
        """
        pass
    
    def print_stats(self):
        """Print final statistics."""
        # Print final statistics
        elapsed = self.get_duration()
        processed = self.stats.get('processed', 0)
        failed = self.stats.get('errors', 0)
        skipped = self.stats.get('skipped', 0)
        total = self.stats.get('total', 0)
        print_separator()
        print("ИТОГОВАЯ СТАТИСТИКА:")
        print(f"Всего файлов: {total}")
        print(f"Успешно обработано: {processed}")
        print(f"Пропущено: {skipped}")
        print(f"Ошибок: {failed}")
        print(f"Затраченное время: {format_duration(elapsed)}")
        print_separator()

def get_max_workers(manual_limit=DEFAULT_THREAD_LIMIT):
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
def print_final_stats(stats, start_time):
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
def get_mkv_files_from_path(path):
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
def check_output_file_exists(output_path, overwrite=False):
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
async def get_audio_tracks(input_path, verbose=False):
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
        "ffprobe", "-v", "error", 
        "-select_streams", "a",
        "-show_entries", "stream=index,codec_type,codec_name:stream_tags=*:format_tags=*", 
        "-of", "json", 
        input_path_quoted
    ]
    
    # Debug: print ffprobe command
    if verbose:
        print(f"! Запрос метаданных аудио: {' '.join(ffprobe_cmd)}")
    
    ffprobe_proc = await asyncio.create_subprocess_exec(
        *ffprobe_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await ffprobe_proc.communicate()
    
    if ffprobe_proc.returncode != 0:
        raise RuntimeError(f"FFprobe error: {stderr.decode()}")

    try:
        audio_info = json.loads(stdout.decode())
        tracks = audio_info.get('streams', [])
        
        # Debug: print found tracks
        if verbose:
            for i, track in enumerate(tracks):
                print(f"! Найдена аудиодорожка {i+1}: {track}")
            
        return tracks
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON parse error: {e}")

def build_loudnorm_filter_complex(audio_tracks, target_loudness=DEFAULT_TARGET_LOUDNESS, 
                                true_peak=DEFAULT_TRUE_PEAK, loudness_range=DEFAULT_LOUDNESS_RANGE):
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
    return filter_complex.rstrip(';')

def get_metadata_options(audio_tracks, verbose=False):
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
        if 'tags' in track:
            title = track['tags'].get('title')
        if not title and 'TAG:title' in track:
            title = track['TAG:title']
        if not title and 'TITLE' in track:
            title = track['TITLE']
            
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

async def run_ffmpeg_command(cmd, stats=None, stats_key="processed", quiet=False, 
                             output_path=None, file_position=None, file_count=None, filename=None,
                             total_duration=None):
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
            *cmd,
            stderr=asyncio.subprocess.PIPE
        )
        if stats:
            stats.register_process(proc)

        stderr_output = []
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
                continue # Check proc.returncode again

            buffer += chunk.decode('utf-8', errors='replace')
            # FFmpeg uses \r to update progress line
            lines = buffer.split('\r')
            buffer = lines.pop() # Keep potentially incomplete line part in buffer

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
                        hours, minutes, seconds, hundredths = map(int, time_match.groups())
                        current_seconds = hours * 3600 + minutes * 60 + seconds + hundredths / 100
                        speed = float(speed_match.group(1)) if speed_match and float(speed_match.group(1)) > 0 else 1.0
                        progress_percent = (current_seconds / total_duration) * 100
                        eta_seconds = (total_duration - current_seconds) / speed if speed > 0 else 0
                        
                        bar_length = 30
                        filled_len = int(bar_length * progress_percent / 100)
                        bar = '█' * filled_len + '-' * (bar_length - filled_len)
                        
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
            print(f"\n--- FFmpeg Error Output for {filename} ---")
            # Print last 15 lines of stderr for diagnosis
            for line in stderr_output[-15:]:
                print(line)
            print("------------------------------------------")
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
                pass # Process already finished
        if stats and proc:
            stats.remove_process(proc)

async def get_video_duration(input_path: str) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path)
    ]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *ffprobe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0 and stdout:
            return float(stdout.decode().strip())
        else:
            print(f"! ffprobe error getting duration for {Path(input_path).name}: {stderr.decode()}")
            return None
    except Exception as e:
        print(f"! Exception getting duration for {Path(input_path).name}: {e}")
        return None

# Async task and signal handling
def setup_signal_handlers(loop, stop_event, tasks, stats=None):
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
    
    def signal_handler():
        """Handle interrupt signals by canceling all tasks."""
        # Clear the status line 
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()
        
        if stats:
            stats.interrupted = True
            
        print("\n! Прерывание: остановка задач...")
        stop_event.set()
        
        # * First terminate any running ffmpeg processes
        if stats and hasattr(stats, 'active_processes'):
            for proc in stats.active_processes[:]:  # Use a copy of the list
                if proc and proc.returncode is None:  # Process is still running
                    try:
                        # On Windows use taskkill to force terminate
                        if platform.system() == 'Windows':
                            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], 
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    if platform.system() == 'Windows':
        signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(signal_handler))
        
        # Return function to remove signal handlers
        def cleanup():
            signal.signal(signal.SIGINT, signal.SIG_DFL)
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
            
        # Return function to remove signal handlers
        def cleanup():
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
    
    return cleanup

async def create_output_dir(path):
    """
    Create output directory if it doesn't exist.
    
    Args:
        path: Directory path to create
    """
    ensure_dir_exists(path)

async def status_updater(stats, stop_event):
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
async def standard_main(args, process_func, output_folder=DEFAULT_OUTPUT_FOLDER):
    """
    Standard main function for FFmpeg processing applications.
    
    Args:
        args: Parsed command-line arguments
        process_func: Function to process files, which should accept (args, stats, stop_event)
        output_folder: Default output folder path
        
    Returns:
        None
    """
    # Setup
    stats = ProcessingStats()
    output_dir = args.output if hasattr(args, 'output') and args.output else output_folder
    await create_output_dir(output_dir)
    
    # Create task
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    # Pass stop_event to the processing function
    main_task = asyncio.create_task(process_func(args, stats, stop_event))
    
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

async def run_tasks_with_semaphore(tasks, stats, stop_event):
    """
    Run tasks with a semaphore to limit concurrency.
    
    Args:
        tasks: A list of awaitable tasks to run.
        stats: ProcessingStats object.
        stop_event: Event to signal task termination.
    """
    # * Force single-file processing for GPU tasks to avoid resource contention.
    limit = 1
    semaphore = asyncio.Semaphore(limit)
    
    print(f"* Concurrency limit set to {limit} to avoid GPU contention.")
    
    async def run_task(task):
        # Wait for the stop event before starting a new task
        if stop_event.is_set():
            return
            
        async with semaphore:
            if not stop_event.is_set():
                try:
                    await task
                except asyncio.CancelledError:
                    pass # Task cancellation is expected on interrupt
    
    # Create a future to await all tasks
    all_tasks_future = asyncio.gather(*(run_task(task) for task in tasks))
    
    try:
        await all_tasks_future
    except asyncio.CancelledError:
        # This is expected if the main task is cancelled.
        # Ensure all sub-tasks are also cancelled.
        all_tasks_future.cancel()
        await asyncio.sleep(0.1) # Give a moment for cancellations to propagate
    finally:
        # Ensure the semaphore is released if main task is cancelled
        # This is handled by context manager, but as a safeguard.
        pass 