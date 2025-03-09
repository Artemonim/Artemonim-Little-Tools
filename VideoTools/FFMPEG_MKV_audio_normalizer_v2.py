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
# TODO: fix the process stats of multiple files

import os
import asyncio
import argparse
from pathlib import Path

# Import common utilities
from ffmpeg_utils import (
    get_audio_tracks, build_loudnorm_filter_complex, get_metadata_options,
    run_ffmpeg_command, print_file_info, print_separator, check_output_file_exists,
    standard_main, get_mkv_files_from_path, get_max_workers, clean_partial_output,
    DEFAULT_OUTPUT_FOLDER, ProcessingStats
)

# * Default configuration
INPUT_FOLDER = "."  # Default to current directory
OUTPUT_FOLDER = DEFAULT_OUTPUT_FOLDER

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
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress progress output")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show verbose output including debug information")
                        
    return parser.parse_args()

async def process_file(filename, semaphore, file_num, total_files, loudness_params, stats, input_folder, output_folder, overwrite, quiet=False, verbose=False):
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
        stats: Stats object to track processing statistics
        input_folder: Input folder or file path
        output_folder: Output folder path
        overwrite: Whether to overwrite existing files
        quiet: Whether to suppress progress output
        verbose: Whether to show verbose debug output
    """
    async with semaphore:
        # Determine input and output paths
        input_path = filename
        if os.path.isdir(input_folder):
            input_path = os.path.join(input_folder, filename)
            # Create output path with same filename in output directory
            output_path = os.path.join(output_folder, filename)
        else:
            # If input is a file, output goes to output directory with same filename
            output_path = os.path.join(output_folder, os.path.basename(input_path))

        # Skip if already exists
        if check_output_file_exists(output_path, overwrite):
            stats.increment("skipped")
            stats.increment("total")
            return

        # Update total files stat
        stats.increment("total")
        
        # Print file info (without separator)
        print_file_info(filename, file_num, total_files)

        try:
            # Get audio track information
            try:
                audio_tracks = await get_audio_tracks(input_path, verbose=verbose)
            except Exception as e:
                print(f"Ошибка при получении аудио дорожек: {e}")
                stats.increment("errors")
                return

            if not audio_tracks:
                print(f"Нет аудиодорожек. Копирование файла: {filename}")
                
                # Create FFmpeg command arguments list
                copy_cmd_args = [
                    "ffmpeg",
                    "-y" if overwrite else "",
                    "-i", str(Path(input_path)),
                    "-c", "copy",
                    str(Path(output_path))
                ]
                
                # In the legacy style, pass output directly to terminal
                if quiet:
                    success = await run_ffmpeg_command(
                        copy_cmd_args, stats, quiet=quiet, 
                        output_path=output_path,
                        file_position=file_num, file_count=total_files, filename=filename
                    )
                else:
                    print(f"Выполняется копирование файла...")
                    proc = await asyncio.create_subprocess_exec(*[arg for arg in copy_cmd_args if arg])
                    await proc.communicate()
                    
                    if proc.returncode == 0:
                        stats.increment("processed")
                        success = True
                    else:
                        stats.increment("errors")
                        success = False
                
                return

            # Build ffmpeg command with filter_complex for audio normalization
            filter_complex = build_loudnorm_filter_complex(
                audio_tracks,
                target_loudness=loudness_params["target_loudness"],
                true_peak=loudness_params["true_peak"],
                loudness_range=loudness_params["loudness_range"]
            )

            # Preserve audio track titles
            metadata_options = get_metadata_options(audio_tracks, verbose=verbose)
            
            # Debug output
            if verbose:
                print(f"! Применение нормализации аудио для {len(audio_tracks)} дорожек: {filename}")
                print(f"! Целевая громкость: {loudness_params['target_loudness']} LUFS, Пиковый уровень: {loudness_params['true_peak']} dBTP")

            # Create FFmpeg command arguments list
            ffmpeg_cmd_args = [
                "ffmpeg",
                "-hide_banner",  # Скрыть баннер версии
                "-loglevel", "warning",  # Показывать только предупреждения и ошибки
                "-stats",  # Сохранить вывод статистики/прогресса
                "-y" if overwrite else "",
                "-i", str(Path(input_path)),
                "-filter_complex", filter_complex,
                "-map", "0:v?", 
                "-map", "0:s?"
            ]
            
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
            
            # Debug: print full command
            if verbose:
                print(f"! Команда FFmpeg: {' '.join(ffmpeg_cmd_args)}")
            
            # Add output file
            ffmpeg_cmd_args.append(str(Path(output_path)))
            
            # In the legacy style, pass output directly to terminal
            if quiet:
                # Use the wrapped function with output capturing if quiet mode
                success = await run_ffmpeg_command(
                    ffmpeg_cmd_args, stats, quiet=quiet, 
                    output_path=output_path,
                    file_position=file_num, file_count=total_files, filename=filename
                )
            else:
                # Использовать прямой вывод команды для отображения прогресса
                print(f"Выполняется команда FFmpeg для нормализации аудио...")
                # Filter out empty strings
                cmd_filtered = [arg for arg in ffmpeg_cmd_args if arg]
                proc = await asyncio.create_subprocess_exec(*cmd_filtered)
                await proc.communicate()
                
                if proc.returncode == 0:
                    stats.increment("processed")
                    success = True
                else:
                    stats.increment("errors")
                    success = False

        except asyncio.CancelledError:
            # Mark as skipped if interrupted
            if not stats.interrupted:
                stats.increment("skipped")
            clean_partial_output(output_path)
            raise
            
        except Exception as e:
            print(f"Ошибка при обработке файла: {e}")
            if not stats.interrupted:
                stats.increment("errors")
            # Try to clean up partial output
            clean_partial_output(output_path)

async def process_files(args, stats):
    """
    Process all MKV files according to arguments.
    
    Args:
        args: Command line arguments
        stats: ProcessingStats object to track results
    """
    # Get configuration from args
    input_folder = args.input or INPUT_FOLDER
    output_folder = args.output or OUTPUT_FOLDER
    overwrite = args.overwrite
    max_workers = args.threads or get_max_workers()
    quiet = args.quiet if hasattr(args, 'quiet') else False
    verbose = args.verbose if hasattr(args, 'verbose') else False
    
    # Prepare loudness parameters (with defaults if not specified)
    loudness_params = {
        "target_loudness": args.target_loudness if args.target_loudness is not None else -16.0,
        "true_peak": args.true_peak if args.true_peak is not None else -1.5,
        "loudness_range": args.loudness_range if args.loudness_range is not None else 11.0
    }

    try:
        # Get list of MKV files to process
        files = get_mkv_files_from_path(input_folder)
            
        total_files = len(files)
        if not files:
            print("Нет MKV файлов для обработки\a")
            return

        # Create and run tasks with concurrency limit
        semaphore = asyncio.Semaphore(max_workers)
        tasks = [
            asyncio.create_task(
                process_file(
                    f, semaphore, i+1, total_files, loudness_params,
                    stats, input_folder, output_folder, overwrite, quiet, verbose
                )
            )
            for i, f in enumerate(files)
        ]

        # Print separator once before starting
        print_separator()
        
        # Await all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            # Let individual tasks handle their cancellation
            await asyncio.gather(*[task for task in tasks if not task.done()], return_exceptions=True)
            raise
        
    except ValueError as e:
        print(f"Ошибка: {str(e)}")
        stats.increment("errors")
    except Exception as e:
        print(f"Непредвиденная ошибка: {str(e)}")
        stats.increment("errors")

async def main():
    """Main entry point for the script."""
    args = parse_arguments()
    await standard_main(args, process_files, DEFAULT_OUTPUT_FOLDER)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")