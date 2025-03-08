#!/usr/bin/env python3
"""
MKV Audio Normalizer

A tool for normalizing audio tracks in MKV video files using ffmpeg's loudnorm filter.
Processes files asynchronously for improved performance.

This script:
1. Scans input location for MKV files
2. Analyzes audio tracks with ffprobe
3. Normalizes audio using the EBU R128 loudness standard
4. Preserves video and subtitle streams
5. Maintains original audio track titles

Dependencies:
- ffmpeg (with loudnorm filter)
- ffprobe

Usage:
    python FFMPEG_MKV_audio_normalizer.py [options]

Examples:
    # Process files in default locations:
    python FFMPEG_MKV_audio_normalizer.py
    
    # Specify input and output folders:
    python FFMPEG_MKV_audio_normalizer.py -i /path/to/input -o /path/to/output
    
    # Allow overwriting existing files:
    python FFMPEG_MKV_audio_normalizer.py --overwrite
    
    # Set specific number of concurrent workers:
    python FFMPEG_MKV_audio_normalizer.py --threads 4
"""

import os
import asyncio
import time
import argparse
from collections import defaultdict
from pathlib import Path

# Import common utilities
from ffmpeg_utils import (
    print_separator, print_file_info, print_final_stats,
    get_audio_tracks, build_loudnorm_filter_complex, get_metadata_options,
    get_max_workers, setup_signal_handlers, create_output_dir,
    DEFAULT_THREAD_LIMIT, DEFAULT_TARGET_LOUDNESS, DEFAULT_TRUE_PEAK, DEFAULT_LOUDNESS_RANGE
)

# =========================
# Configuration variables
# =========================
# These defaults will be overridden by command line arguments
INPUT_FOLDER = "."  # Default to current directory
OUTPUT_FOLDER = "./normalized"  # Default to 'normalized' subdirectory
MANUAL_THREAD_LIMIT = DEFAULT_THREAD_LIMIT
OVERWRITE_OUTPUT = False  # Whether to overwrite existing files
MAX_WORKERS = get_max_workers(MANUAL_THREAD_LIMIT)

# Processing statistics
stats = defaultdict(int)
start_time = time.monotonic()

def parse_arguments():
    """
    Parse command line arguments for the script.
    
    Returns:
        An argparse.Namespace object containing the argument values
    """
    parser = argparse.ArgumentParser(
        description="Normalize audio in MKV files using ffmpeg's loudnorm filter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n")[3]  # Extract the Usage section from docstring
    )
    
    parser.add_argument("-i", "--input", 
                        help="Input folder or file path (default: current directory)")
    parser.add_argument("-o", "--output", 
                        help="Output folder path (default: ./normalized)")
    parser.add_argument("-t", "--threads", type=int,
                        help=f"Number of concurrent processing threads (default: calculated based on CPU cores)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing output files")
    parser.add_argument("--target-loudness", type=float, default=DEFAULT_TARGET_LOUDNESS,
                        help=f"Target integrated loudness level in LUFS (default: {DEFAULT_TARGET_LOUDNESS})")
    parser.add_argument("--true-peak", type=float, default=DEFAULT_TRUE_PEAK,
                        help=f"Maximum true peak level in dBTP (default: {DEFAULT_TRUE_PEAK})")
    parser.add_argument("--loudness-range", type=float, default=DEFAULT_LOUDNESS_RANGE,
                        help=f"Target loudness range in LU (default: {DEFAULT_LOUDNESS_RANGE})")
                        
    return parser.parse_args()

# =========================
# Asynchronous file processing
# =========================
async def process_file(filename, semaphore, file_num, total_files, loudness_params):
    """
    Process a single MKV file to normalize its audio tracks.
    
    Uses ffprobe to detect audio tracks and ffmpeg to normalize them
    with the loudnorm filter.
    
    Args:
        filename: Name of the file to process
        semaphore: Asyncio semaphore to limit concurrent processing
        file_num: Current file number in the queue
        total_files: Total number of files to process
        loudness_params: Dictionary containing loudnorm filter parameters
        
    Returns:
        None. Updates global stats dictionary with results.
    """
    async with semaphore:
        stats['total'] += 1
        input_path = filename
        if os.path.isdir(INPUT_FOLDER):
            input_path = os.path.join(INPUT_FOLDER, filename)
            # Create output path with same filename in output directory
            output_path = os.path.join(OUTPUT_FOLDER, filename)
        else:
            # If input is a file, output goes to output directory with same filename
            output_path = os.path.join(OUTPUT_FOLDER, os.path.basename(input_path))
            
        proc = None

        print_separator()
        print_file_info(filename, file_num, total_files)

        try:
            # Check if output file already exists
            if os.path.exists(output_path):
                if OVERWRITE_OUTPUT:
                    print(f"Файл существует, перезаписываем: {filename}")
                else:
                    print(f"Файл существует, пропускаем: {filename}")
                    stats['skipped'] += 1
                    return

            # Get audio track information
            try:
                audio_tracks = await get_audio_tracks(input_path)
            except Exception as e:
                print(f"Ошибка при получении аудио дорожек: {e}")
                stats['errors'] += 1
                return

            if not audio_tracks:
                print(f"Нет аудиодорожек. Копирование файла: {filename}")
                
                # Create FFmpeg command arguments list
                copy_cmd_args = [
                    "ffmpeg",
                    "-i", str(Path(input_path)),
                    "-c", "copy"
                ]
                
                if OVERWRITE_OUTPUT:
                    copy_cmd_args.insert(1, "-y")
                    
                copy_cmd_args.append(str(Path(output_path)))
                
                proc = await asyncio.create_subprocess_exec(*copy_cmd_args)
                await proc.communicate()
                stats['processed'] += 1
                return

            # Build ffmpeg command with filter_complex for audio normalization
            filter_complex = build_loudnorm_filter_complex(
                audio_tracks,
                target_loudness=loudness_params["target_loudness"],
                true_peak=loudness_params["true_peak"],
                loudness_range=loudness_params["loudness_range"]
            )

            # Preserve audio track titles
            metadata_options = get_metadata_options(audio_tracks)

            # Create FFmpeg command arguments list for better cross-platform compatibility
            ffmpeg_cmd_args = ["ffmpeg"]
            
            if OVERWRITE_OUTPUT:
                ffmpeg_cmd_args.append("-y")
                
            ffmpeg_cmd_args.extend([
                "-i", str(Path(input_path)),
                "-filter_complex", filter_complex,
                "-map", "0:v?", 
                "-map", "0:s?"
            ])
            
            # Add audio maps
            for i in range(len(audio_tracks)):
                ffmpeg_cmd_args.extend(["-map", f"[a{i}]"])
                
            # Add encoding options    
            ffmpeg_cmd_args.extend([
                "-c:v", "copy", 
                "-c:s", "copy", 
                "-c:a", "aac"
            ])
            
            # Add metadata options
            ffmpeg_cmd_args.extend(metadata_options)
            
            # Add output file
            ffmpeg_cmd_args.append(str(Path(output_path)))
            
            print(f"Выполняется команда FFmpeg для нормализации аудио...")
            proc = await asyncio.create_subprocess_exec(*ffmpeg_cmd_args)
            await proc.communicate()
            
            if proc.returncode == 0:
                stats['processed'] += 1
            else:
                stats['errors'] += 1

        except Exception as e:
            print(f"Ошибка при проверке файла: {e}")
            stats['errors'] += 1
            return

        except asyncio.CancelledError:
            print(f"Отмена обработки: {filename}")
            if proc and proc.returncode is None:
                proc.terminate()
                await proc.wait()
            stats['errors'] += 1
            raise

# =========================
# Main function
# =========================
async def main():
    """
    Main async function that processes all MKV files.
    
    Creates output directory if needed, sets up signal handlers for
    graceful termination, and processes files concurrently with
    a semaphore to limit the number of simultaneous operations.
    """
    global INPUT_FOLDER, OUTPUT_FOLDER, MAX_WORKERS, OVERWRITE_OUTPUT
    
    # Parse command line arguments and apply to global configuration
    args = parse_arguments()
    
    if args.input:
        INPUT_FOLDER = args.input
    if args.output:
        OUTPUT_FOLDER = args.output
    if args.threads:
        MAX_WORKERS = args.threads
    if args.overwrite:
        OVERWRITE_OUTPUT = True
        
    # Prepare loudness parameters
    loudness_params = {
        "target_loudness": args.target_loudness,
        "true_peak": args.true_peak,
        "loudness_range": args.loudness_range
    }

    # Create output directory if it doesn't exist
    await create_output_dir(OUTPUT_FOLDER)

    # Get list of MKV files to process
    if os.path.isdir(INPUT_FOLDER):
        files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".mkv")]
    else:
        if os.path.isfile(INPUT_FOLDER) and INPUT_FOLDER.lower().endswith(".mkv"):
            files = [INPUT_FOLDER]
        else:
            print(f"Ошибка: {INPUT_FOLDER} не является директорией или MKV файлом")
            return
            
    total_files = len(files)
    if not files:
        print("Нет MKV файлов для обработки\a")
        return

    # Setup interrupt handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    # Create and run tasks with concurrency limit
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    tasks = [
        asyncio.create_task(process_file(f, semaphore, i+1, total_files, loudness_params))
        for i, f in enumerate(files)
    ]

    # Setup signal handlers
    cleanup_signals = setup_signal_handlers(loop, stop_event, tasks)

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        cleanup_signals()

    print_final_stats(stats, start_time)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
        print_final_stats(stats, start_time)