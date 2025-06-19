#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Converter Tool

This script uses FFmpeg to re-encode videos with specified quality and FPS settings.
It is designed to be called from the main menu.py script.

Functionality:
- Re-encodes videos using HEVC (Nvidia NVENC).
- Allows user to select quality presets (Master, Normal, Compact).
- Allows user to select FPS (original, 30, 60, 120).
- Processes all compatible video files from an input directory to an output directory.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# * Add parent directory to path to allow importing from little_tools_utils and ffmpeg_utils
sys.path.append(str(Path(__file__).parent.parent))
from little_tools_utils import get_files_by_extension, print_file_info, check_file_exists_with_overwrite, clean_partial_output, format_duration, BatchTimeEstimator
from VideoTools.ffmpeg_utils import (
    run_ffmpeg_command, standard_main, ProcessingStats, 
    run_tasks_with_semaphore, get_video_duration
)

# Define available video extensions
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".mov", ".avi", ".webm"]

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Video Converter using FFmpeg with HEVC (NVENC).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Input directory containing video files.")
    parser.add_argument("-o", "--output", required=True, help="Output directory for converted files.")
    parser.add_argument("--quality", required=True, choices=['26', '30', '34', '40'], help="Quality (CQ value): 26=Master, 30=Normal, 34=Compact, 40=Compressed.")
    parser.add_argument("--fps", required=True, help="Frames per second. Use 'original' to keep source FPS.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files in the output directory.")
    return parser.parse_args()


async def process_file(file_path: Path, args: argparse.Namespace, stats: ProcessingStats, estimator: BatchTimeEstimator, position: int, total: int):
    """
    Process a single video file.
    """
    output_filename = f"{file_path.stem}_converted.mp4"
    output_path = Path(args.output) / output_filename
    
    print_file_info(file_path.name, position, total, f"Quality: CQ-{args.quality}, FPS: {args.fps} | ETA: {estimator.get_eta_str()}")
    
    if check_file_exists_with_overwrite(output_path, args.overwrite):
        stats.increment("skipped")
        print(f"  -> Skipped: {output_path.name}")
        return

    # Get video duration for progress bar
    total_duration = await get_video_duration(str(file_path))

    # Base FFMPEG command parts
    cmd = [
        "ffmpeg", "-y",
        "-i", str(file_path),
        "-c:v", "hevc_nvenc",
        "-preset", "hq",
        "-rc", "vbr_hq",
        "-cq", args.quality,
        "-spatial_aq", "1",
        "-temporal_aq", "1",
        "-aq-strength", "8",
        "-rc-lookahead", "32",
        "-bf", "4",
        "-refs", "4",
        "-b_ref_mode", "middle",
        "-movflags", "+faststart",
        "-c:a", "copy",
    ]

    # Build video filters
    filters = []
    if args.quality == "40":
        # * Compressed mode: ensure the smaller dimension is <= 720 px while preserving aspect ratio
        filters.append("scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)',flags=lanczos")
    if args.fps != "original":
        filters.append(f"fps={args.fps}")
    if filters:
        cmd.extend(["-vf", ",".join(filters)])

    # Add output path
    cmd.append(str(output_path))
    
    try:
        success = await run_ffmpeg_command(
            cmd,
            stats=stats,
            quiet=True,
            output_path=str(output_path),
            file_position=position,
            file_count=total,
            filename=file_path.name,
            total_duration=total_duration
        )
        if success:
            print(f"  ✓ Success: {file_path.name} -> {output_path.name}")
            if total_duration:
                estimator.update(total_duration)
        else:
            print(f"  ✗ Failed: {file_path.name}. Check FFmpeg output for details.")
            clean_partial_output(output_path)
            
    except Exception as e:
        stats.increment("errors")
        print(f"  ✗ Exception while processing {file_path.name}: {e}")
        clean_partial_output(output_path)


async def process_all_files(args: argparse.Namespace, stats: ProcessingStats, stop_event: asyncio.Event):
    """
    Find and process all video files in the input directory.
    """
    input_dir = Path(args.input)
    files_to_process = get_files_by_extension(input_dir, VIDEO_EXTENSIONS)
    
    if not files_to_process:
        print(f"! No video files found in {input_dir}")
        return
        
    stats.stats['total'] = len(files_to_process)
    
    # * Set up and calculate ETA
    estimator = BatchTimeEstimator()
    print("* Calculating total video duration for ETA...")
    for file_path in files_to_process:
        duration = await get_video_duration(str(file_path))
        if duration:
            estimator.add_item(duration)
    
    if estimator.total_workload > 0:
        print(f"* Total video duration: {format_duration(estimator.total_workload)}")
    
    estimator.start()
    
    print(f"* Found {stats.stats['total']} video file(s) to process.")
    
    tasks = [
        process_file(file_path, args, stats, estimator, i + 1, stats.stats['total'])
        for i, file_path in enumerate(files_to_process)
    ]
    await run_tasks_with_semaphore(tasks, stats, stop_event)


async def main():
    """Main function to run the script."""
    # This script is designed to be called with arguments from menu.py
    # standard_main will handle the async loop, signal handling, and stats printing
    # We now pass a lambda to standard_main to include the stop_event
    await standard_main(parse_arguments(), lambda args, stats, stop_event: process_all_files(args, stats, stop_event))


if __name__ == "__main__":
    # Ensure the script is run in an environment where it can find the utils
    if str(Path(__file__).parent.parent) not in sys.path:
        sys.path.append(str(Path(__file__).parent.parent))

    from VideoTools.ffmpeg_utils import (
        standard_main, ProcessingStats, run_tasks_with_semaphore, get_video_duration
    )
    from little_tools_utils import get_files_by_extension, print_file_info, check_file_exists_with_overwrite, clean_partial_output, format_duration
    
    asyncio.run(main()) 