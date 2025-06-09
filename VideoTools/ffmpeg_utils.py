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
                             output_path=None, file_position=None, file_count=None, filename=None):
    """
    Run an FFmpeg command and handle errors.
    
    Args:
        cmd: List containing the FFmpeg command and arguments
        stats: Optional ProcessingStats object to update
        stats_key: Key to increment in stats on success
        quiet: Whether to suppress progress output
        output_path: Path to the output file (for cleaning up on cancel)
        file_position: Current file number
        file_count: Total number of files
        filename: Name of the file being processed
        
    Returns:
        bool: True if command succeeded, False otherwise
    """
    # Filter empty strings
    cmd = [arg for arg in cmd if arg]
    
    try:
        # Generate a unique task ID if filename is provided
        task_id = f"Task-{file_position}" if file_position else f"Task-{id(cmd)}"
        
        # Update initial status if stats object is provided
        if stats and filename:
            stats.update_task_status(task_id, f"Начало обработки {filename}")
        
        # Start FFmpeg process with pipe for stderr to capture output
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stderr=asyncio.subprocess.PIPE if quiet else None  # Only pipe stderr if in quiet mode
        )
        
        # Register process if stats object is provided
        if stats:
            stats.register_process(proc)
        
        # Process stderr output line by line in quiet mode
        if quiet:
            time_pattern = re.compile(r"time=\s*(\d+:\d+:\d+\.\d+)")
            speed_pattern = re.compile(r"speed=\s*(\d+\.\d+)x")
            
            # Pre-format the permanent part of the progress line
            file_prefix = ""
            if file_position and file_count and filename:
                file_prefix = f"[{file_position}/{file_count}] {filename} "
            
            async for line in proc.stderr:
                line_text = line.decode('utf-8', errors='replace').strip()
                
                # Only process progress lines (lines with "time=")
                if "time=" in line_text:
                    # Extract time and speed
                    time_match = time_pattern.search(line_text)
                    speed_match = speed_pattern.search(line_text)
                    
                    if time_match:
                        timecode = time_match.group(1)
                        speed = speed_match.group(1) if speed_match else "?"
                        
                        # Simple direct output to last terminal line - legacy style
                        # Clear more space (200 chars) to ensure visibility
                        progress_line = f"\r{' ' * 200}\r{file_prefix}{timecode} speed={speed}x"
                        
                        # Force immediate output without buffering
                        sys.stdout.write(progress_line)
                        sys.stdout.flush()
        else:
            # In legacy style, output goes directly to terminal
            await proc.communicate()
        
        # Clear the line when finished in quiet mode
        if quiet:
            sys.stdout.write("\r" + " " * 100 + "\r")
            sys.stdout.flush()
        
        # Remove process from tracked processes
        if stats:
            stats.remove_process(proc)
        
        # Check return code
        if proc.returncode == 0:
            if stats:
                stats.increment(stats_key)
            return True
        else:
            if stats and not stats.interrupted:
                stats.increment("errors")
            return False
    except asyncio.CancelledError:
        # Clean up partial output file if needed
        if output_path:
            clean_partial_output(output_path)
        
        # Remove process from tracking
        if stats and 'proc' in locals():
            stats.remove_process(proc)
        
        raise
    except Exception as e:
        if stats and not stats.interrupted:
            stats.increment("errors")
        print(f"Исключение при выполнении команды: {str(e)}")
        
        # Remove process from tracking
        if stats and 'proc' in locals():
            stats.remove_process(proc)
        
        return False

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
        process_func: Function to process files
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
    main_task = asyncio.create_task(process_func(args, stats))
    
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