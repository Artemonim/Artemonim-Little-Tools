#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Converter and Compiler Tool

This script uses FFmpeg to:
1. Re-encode videos with specified quality, FPS, resolution, and audio normalization settings.
2. Compile a new video from a primary video source and additional audio/subtitle tracks.

It is designed to be called from the main menu.py script.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List

from littletools_core.utils import (
    BatchTimeEstimator,
    check_file_exists_with_overwrite,
    clean_partial_output,
    format_duration,
    get_files_by_extension,
    print_file_info,
)
from .ffmpeg_utils import (
    ProcessingStats,
    get_video_duration,
    get_video_resolution,
    get_nvenc_hevc_video_options,
    run_ffmpeg_command,
    run_tasks_with_semaphore,
    standard_main,
)

# Define available video extensions
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".mov", ".avi", ".webm"]


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Video Converter & Compiler using FFmpeg.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    
    # * Base arguments for both modes
    parser.add_argument("--mode", default="convert", choices=["convert", "compile"], help="Operating mode: 'convert' to re-encode files, 'compile' to merge tracks.")
    parser.add_argument("-o", "--output", required=True, help="Output directory for processed files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files in the output directory.")

    # * Arguments for 'convert' mode
    convert_group = parser.add_argument_group('Convert Mode Options')
    convert_group.add_argument("-i", "--input", help="Input directory containing video files (for 'convert' mode).")
    convert_group.add_argument("--quality", choices=['26', '30', '34', '40'], help="Quality (CQ value): 26=Master, 30=Normal, 34=Compact, 40=Compressed.")
    convert_group.add_argument("--fps", help="Frames per second. Use 'original' to keep source FPS.")
    convert_group.add_argument("--resolution", default='original', choices=['original', '480p', '720p', '1080p', '2160p'], help="Output resolution (e.g., '1080p'). Scales down only. 'original' keeps source resolution.")
    convert_group.add_argument("--normalize-audio", action="store_true", help="Normalize audio to -3dB true peak using a loudnorm filter.")

    # * Arguments for 'compile' mode
    compile_group = parser.add_argument_group('Compile Mode Options')
    compile_group.add_argument("--inputs", nargs='+', help="Input files for 'compile' mode. The first file is the video source.")
    compile_group.add_argument("--keep-original-audio", action="store_true", help="Keep audio from the primary video source file.")
    compile_group.add_argument("--keep-original-subtitles", action="store_true", help="Keep subtitles from the primary video source file.")
    compile_group.add_argument("--output-container", default='mkv', choices=['mp4', 'mkv'], help="Container for the output file in 'compile' mode.")


    args = parser.parse_args()

    # * Validate arguments based on mode
    if args.mode == 'convert':
        if not args.input or not args.quality or not args.fps:
            parser.error("-i/--input, --quality, and --fps are required for --mode=convert")
    elif args.mode == 'compile':
        if not args.inputs:
            parser.error("--inputs is required for --mode=compile")

    return args


async def process_file_convert(file_path: Path, args: argparse.Namespace, stats: ProcessingStats, estimator: BatchTimeEstimator, position: int, total: int):
    """
    Process a single video file for conversion.
    """
    output_filename = f"{file_path.stem}_converted.mp4"
    output_path = Path(args.output) / output_filename
    
    eta_str = estimator.get_eta_str()
    print_file_info(file_path.name, position, total, f"Quality: CQ-{args.quality}, FPS: {args.fps}, Res: {args.resolution} | ETA: {eta_str}")
    
    if check_file_exists_with_overwrite(output_path, args.overwrite):
        stats.increment("skipped")
        print(f"  -> Skipped: {output_path.name}")
        return

    total_duration = await get_video_duration(str(file_path))

    # * Build video filters
    filters = []
    # Resolution scaling
    if args.resolution != "original":
        res_map = {"480p": 480, "720p": 720, "1080p": 1080, "2160p": 2160}
        target_height = res_map.get(args.resolution)
        
        if target_height:
            resolution = await get_video_resolution(str(file_path))
            if resolution:
                original_height = resolution[1]
                if original_height > target_height:
                    filters.append(f"scale=-2:{target_height}:flags=lanczos")
    
    elif args.quality == "40":
        # If no resolution is set, apply the old logic for "Compressed" quality
        filters.append("scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)',flags=lanczos")

    if args.fps != "original":
        filters.append(f"fps={args.fps}")
        
    # * Build video command parts
    video_cmd = get_nvenc_hevc_video_options(quality=args.quality)
    if filters:
        video_cmd.extend(["-vf", ",".join(filters)])
        
    # * Build audio command parts
    if args.normalize_audio:
        audio_cmd = [
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "loudnorm=I=-16:TP=-3:LRA=11:print_format=summary"
        ]
    else:
        audio_cmd = ["-c:a", "copy"]

    # * Assemble the final FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", str(file_path),
    ]
    cmd.extend(video_cmd)
    cmd.extend(audio_cmd)
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


async def process_files_convert(args: argparse.Namespace, stats: ProcessingStats, stop_event: asyncio.Event):
    """
    Find and process all video files for conversion.
    """
    input_dir = Path(args.input)
    files_to_process = get_files_by_extension(input_dir, VIDEO_EXTENSIONS)
    
    if not files_to_process:
        print(f"! No video files found in {input_dir}")
        return
        
    stats.stats['total'] = len(files_to_process)
    
    estimator = BatchTimeEstimator()
    print("* Calculating total video duration for ETA...")
    for file_path in files_to_process:
        duration = await get_video_duration(str(file_path))
        if duration:
            estimator.add_item(duration)
    
    if estimator.total_workload > 0:
        print(f"* Total video duration: {format_duration(estimator.total_workload)}")
    
    estimator.start()
    
    print(f"* Found {stats.stats['total']} video file(s) to process for conversion.")
    
    tasks = [
        process_file_convert(file_path, args, stats, estimator, i + 1, stats.stats['total'])
        for i, file_path in enumerate(files_to_process)
    ]
    await run_tasks_with_semaphore(tasks, stats, stop_event)


async def process_files_compile(args: argparse.Namespace, stats: ProcessingStats, stop_event: asyncio.Event):
    """
    Process files for track compilation.
    """
    if stop_event.is_set():
        return

    input_files = [Path(f) for f in args.inputs]
    primary_input = input_files[0]
    
    output_filename = f"{primary_input.stem}_compiled.{args.output_container}"
    output_path = Path(args.output) / output_filename

    print_file_info(f"Compiling from {primary_input.name}", 1, 1, f"Output: {output_filename}")

    if check_file_exists_with_overwrite(output_path, args.overwrite):
        stats.increment("skipped")
        print(f"  -> Skipped: {output_path.name}")
        return

    # --- Assemble FFmpeg command ---
    cmd = ["ffmpeg", "-y"]

    # Add all inputs
    for file_path in input_files:
        cmd.extend(["-i", str(file_path)])

    # Map video from the first file (assuming one video stream)
    cmd.extend(["-map", "0:v:0"])

    # Map audio tracks
    if args.keep_original_audio:
        cmd.extend(["-map", "0:a?"])
    for i in range(1, len(input_files)):
        cmd.extend(["-map", f"{i}:a?"])

    # Map subtitle tracks
    if args.keep_original_subtitles:
        cmd.extend(["-map", "0:s?"])
    for i in range(1, len(input_files)):
        cmd.extend(["-map", f"{i}:s?"])
        
    # Set codecs. For MP4, we must convert subtitles to a compatible format.
    if args.output_container == 'mp4':
        print("* MP4 output selected. Subtitles will be converted to 'mov_text' for compatibility.")
        cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text"])
    else:
        cmd.extend(["-c", "copy"]) # For MKV, copy everything as is
    
    cmd.append(str(output_path))
    
    stats.stats['total'] = 1
    
    try:
        total_duration = await get_video_duration(str(primary_input))

        success = await run_ffmpeg_command(
            cmd,
            stats=stats,
            quiet=True,
            output_path=str(output_path),
            file_position=1,
            file_count=1,
            filename=output_filename,
            total_duration=total_duration
        )
        if success:
            print(f"  ✓ Success: Compilation finished -> {output_path.name}")
        else:
            print(f"  ✗ Failed: {primary_input.name}. Check FFmpeg output for details.")
            print(f"  ! Tip: The '{args.output_container}' container might not support all video/audio stream codecs from the input files. Try 'mkv' for better compatibility.")
            clean_partial_output(output_path)
            
    except Exception as e:
        stats.increment("errors")
        print(f"  ✗ Exception while compiling {primary_input.name}: {e}")
        clean_partial_output(output_path)


async def main():
    """Main function to run the script."""
    args = parse_arguments()
    
    if args.mode == 'convert':
        await standard_main(args, lambda a, s, e: process_files_convert(a, s, e))
    elif args.mode == 'compile':
        await standard_main(args, lambda a, s, e: process_files_compile(a, s, e)) 