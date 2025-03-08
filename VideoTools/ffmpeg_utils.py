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
"""

import os
import asyncio
import signal
import json
import platform
import time
from collections import defaultdict
from pathlib import Path

# * Configuration variables with defaults
DEFAULT_THREAD_LIMIT = 2
AUTO_THREAD_LIMIT_DIVIDER = 3
DEFAULT_TARGET_LOUDNESS = -16.0
DEFAULT_TRUE_PEAK = -1.5
DEFAULT_LOUDNESS_RANGE = 11.0

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

# Console output functions
def print_separator():
    """Prints a separator line for better console output readability."""
    print("\n" + "═" * 50 + "\n")

def print_file_info(filename, current, total):
    """
    Prints information about the file being processed.
    
    Args:
        filename: Name of the file being processed
        current: Current file number
        total: Total number of files to process
    """
    print(f"Обработка файла [{current}/{total}]: {filename}")
    print(f"Осталось задач: {total - current}")

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
    print(f"Затраченное время: {duration:.2f} секунд")
    print_separator()

# FFmpeg utilities
async def get_audio_tracks(input_path):
    """
    Get audio track information from a media file using ffprobe.
    
    Args:
        input_path: Path to the input media file
        
    Returns:
        list: List of audio tracks with metadata
        
    Raises:
        RuntimeError: If ffprobe fails or JSON parsing fails
    """
    input_path_quoted = str(Path(input_path))  # Proper path handling
    ffprobe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index:stream_tags=title",
        "-print_format", "json", input_path_quoted
    ]
    
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
        return audio_info.get('streams', [])
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

def get_metadata_options(audio_tracks):
    """
    Generate ffmpeg metadata options to preserve audio track titles.
    
    Args:
        audio_tracks: List of audio tracks with metadata
        
    Returns:
        list: FFmpeg metadata command arguments
    """
    metadata_options = []
    for i, track in enumerate(audio_tracks):
        title = track.get('tags', {}).get('title', '')
        if title:
            metadata_options.extend([f"-metadata:s:a:{i}", f"title={title}"])
    return metadata_options

# Async task and signal handling
def setup_signal_handlers(loop, stop_event, tasks):
    """
    Set up signal handlers for graceful termination.
    
    Args:
        loop: asyncio event loop
        stop_event: Event to signal task termination
        tasks: List of running tasks
        
    Returns:
        callable: Function to remove signal handlers
    """
    def signal_handler():
        """Handle interrupt signals by canceling all tasks."""
        print("\nПрерывание: остановка задач...")
        stop_event.set()
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
    os.makedirs(path, exist_ok=True) 