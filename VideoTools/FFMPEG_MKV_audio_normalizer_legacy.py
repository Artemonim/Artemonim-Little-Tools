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
import signal
import json
import platform
import time
import argparse
from collections import defaultdict
from pathlib import Path

# =========================
# Configuration variables
# =========================
# These defaults will be overridden by command line arguments
INPUT_FOLDER = "."  # Default to current directory
OUTPUT_FOLDER = "./normalized"  # Default to 'normalized' subdirectory
MANUAL_THREAD_LIMIT = 2  # ! Minimum number of threads to use
AUTO_THREAD_LIMIT_DIVIDER = 3  # * Controls automatic thread calculation (cpu_count / this_value)
OVERWRITE_OUTPUT = False  # Whether to overwrite existing files
cpu_count = os.cpu_count() or MANUAL_THREAD_LIMIT
MAX_WORKERS = max(cpu_count // AUTO_THREAD_LIMIT_DIVIDER, MANUAL_THREAD_LIMIT)

# Processing statistics
stats = defaultdict(int)
start_time = time.monotonic()

# =========================
# Helper functions
# =========================
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

def print_final_stats():
    """Prints final processing statistics."""
    duration = time.monotonic() - start_time
    print_separator()
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print(f"Всего файлов: {stats['total']}")
    print(f"Успешно обработано: {stats['processed']}")
    print(f"Пропущено: {stats['skipped']}")
    print(f"Ошибок: {stats['errors']}")
    print(f"Затраченное время: {duration:.2f} секунд")
    print_separator()

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
    parser.add_argument("--target-loudness", type=float, default=-16.0,
                        help="Target integrated loudness level in LUFS (default: -16.0)")
    parser.add_argument("--true-peak", type=float, default=-1.5,
                        help="Maximum true peak level in dBTP (default: -1.5)")
    parser.add_argument("--loudness-range", type=float, default=11.0,
                        help="Target loudness range in LU (default: 11.0)")
                        
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

            # Get audio track information - use shell=False for better cross-platform compatibility
            input_path_quoted = str(Path(input_path))  # Proper path handling for both OS
            ffprobe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index:stream_tags=title",
                "-print_format", "json", input_path_quoted
            ]
            
            # Use create_subprocess_exec for better cross-platform compatibility
            ffprobe_proc = await asyncio.create_subprocess_exec(
                *ffprobe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await ffprobe_proc.communicate()
            
            if ffprobe_proc.returncode != 0:
                print(f"Ошибка ffprobe: {stderr.decode()}")
                stats['errors'] += 1
                return

            try:
                audio_info = json.loads(stdout.decode())
            except json.JSONDecodeError as e:
                print(f"Ошибка парсинга JSON: {e}")
                stats['errors'] += 1
                return

            audio_tracks = audio_info.get('streams', [])
            if not audio_tracks:
                print(f"Нет аудиодорожек. Копирование файла: {filename}")
                
                # Create FFmpeg command arguments list
                copy_cmd_args = [
                    "ffmpeg",
                    "-i", input_path_quoted,
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
            # Using the custom loudness parameters
            I = loudness_params["target_loudness"]
            TP = loudness_params["true_peak"]
            LRA = loudness_params["loudness_range"]
            
            filter_complex = "".join(
                f"[0:a:{i}]loudnorm=I={I}:TP={TP}:LRA={LRA}[a{i}];"
                for i in range(len(audio_tracks))
            )
            filter_complex = filter_complex.rstrip(';')

            # Preserve audio track titles
            metadata_options = []
            for i, track in enumerate(audio_tracks):
                title = track.get('tags', {}).get('title', '')
                if title:
                    metadata_options.append(f"-metadata:s:a:{i}")
                    metadata_options.append(f"title={title}")

            # Create FFmpeg command arguments list for better cross-platform compatibility
            ffmpeg_cmd_args = ["ffmpeg"]
            
            if OVERWRITE_OUTPUT:
                ffmpeg_cmd_args.append("-y")
                
            ffmpeg_cmd_args.extend([
                "-i", input_path_quoted,
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
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

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
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

    # Create and run tasks with concurrency limit
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    tasks = [
        asyncio.create_task(process_file(f, semaphore, i+1, total_files, loudness_params))
        for i, f in enumerate(files)
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        if platform.system() != 'Windows':
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    print_final_stats()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
        print_final_stats()