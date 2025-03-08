#!/usr/bin/env python3
"""
Dual-Input MKV Audio/Video Normalizer
A tool for normalizing audio tracks in MKV files using ffmpeg's loudnorm filter,
while replacing the video stream with a separate source file.
Processes files asynchronously with optimized HEVC encoding to avoid gradient artifacts.
This script:
1. Takes two input files:
   - Primary: audio, subtitles, and metadata
   - Secondary: video stream
2. Analyzes audio tracks with ffprobe
3. Normalizes audio using EBU R128 standard
4. Encodes video to H.265 with artifact-minimizing settings
5. Preserves original track titles and metadata
Dependencies:
- ffmpeg (with loudnorm filter and x265 support)
- ffprobe
Usage:
    python DualInput_Normalizer.py [options]
Examples:
    # Process with default paths and 2 threads
    python DualInput_Normalizer.py -i1 input_primary.mkv -i2 input_video.mp4
    # Specify output folder and 4 threads:
    python DualInput_Normalizer.py -i1 input1.mkv -i2 input2.mp4 -o output --threads 4
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

# Configuration variables
INPUT_PRIMARY = None  # Primary input (audio/subtitles)
INPUT_VIDEO = None    # Video source
OUTPUT_FOLDER = "./normalized"
MANUAL_THREAD_LIMIT = DEFAULT_THREAD_LIMIT
OVERWRITE_OUTPUT = False
MAX_WORKERS = get_max_workers(MANUAL_THREAD_LIMIT)
stats = defaultdict(int)
start_time = time.monotonic()

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Normalize audio and replace video stream using dual input files",
        epilog=__doc__.split("\n")[3]
    )
    parser.add_argument("-i1", "--input-primary", required=True,
                        help="Primary input file (provides audio/subtitles)")
    parser.add_argument("-i2", "--input-video", required=True,
                        help="Secondary input file (provides video stream)")
    parser.add_argument("-o", "--output", 
                        help="Output folder path (default: ./normalized)")
    parser.add_argument("-t", "--threads", type=int,
                        help="Number of concurrent tasks (default: auto)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing output files")
    parser.add_argument("--crf", type=int, default=22,
                        help="HEVC CRF value (lower = better quality, default: 22)")
    parser.add_argument("--target-loudness", type=float, default=DEFAULT_TARGET_LOUDNESS,
                        help=f"Target integrated loudness level in LUFS (default: {DEFAULT_TARGET_LOUDNESS})")
    parser.add_argument("--true-peak", type=float, default=DEFAULT_TRUE_PEAK,
                        help=f"Maximum true peak level in dBTP (default: {DEFAULT_TRUE_PEAK})")
    parser.add_argument("--loudness-range", type=float, default=DEFAULT_LOUDNESS_RANGE,
                        help=f"Target loudness range in LU (default: {DEFAULT_LOUDNESS_RANGE})")
    return parser.parse_args()

async def replace_video_only(primary_path, video_path, output_path, crf):
    """
    Replace video stream without audio normalization.
    
    Args:
        primary_path: Path to primary input file (audio source)
        video_path: Path to video input file
        output_path: Path for output file
        crf: Constant Rate Factor for video encoding
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-y" if OVERWRITE_OUTPUT else "",
        "-i", str(primary_path),
        "-i", str(video_path),
        "-map", "0:v? -flags +bitexact",  # Explicitly exclude primary video
        "-map", "1:v",                   # Use video from secondary input
        "-map", "0:a",                   # All audio tracks
        "-map", "0:s?",                  # All subtitles
        "-c:v", "libx265",
        "-x265-params",
        "qpstep=1:rect=1:hexagon=1:aq-mode=3:aq-strength=1.2:psy-rd=2.0:psy-trellis=2",
        "-crf", str(crf),
        "-preset", "medium",
        "-tag:v", "hvc1",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-c:s", "copy",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    # Filter empty strings from command
    ffmpeg_cmd = [arg for arg in ffmpeg_cmd if arg]
    
    print("Запуск копирования видео:")
    print(" ".join(ffmpeg_cmd))
    
    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    
    if proc.returncode == 0:
        stats['processed'] += 1
        print("Копирование завершено успешно")
    else:
        stats['errors'] += 1
        print(f"Ошибка копирования видео")

async def process_files(args):
    global MAX_WORKERS, OVERWRITE_OUTPUT, stats
    OVERWRITE_OUTPUT = args.overwrite
    MAX_WORKERS = args.threads or MAX_WORKERS
    OUTPUT_FOLDER = args.output or "./normalized"
    
    await create_output_dir(OUTPUT_FOLDER)
    
    # Prepare input paths
    primary_path = Path(args.input_primary).resolve()
    video_path = Path(args.input_video).resolve()
    
    # Get output filename
    output_filename = f"{primary_path.stem}_normalized_{video_path.stem}.mkv"
    output_path = Path(OUTPUT_FOLDER) / output_filename
    
    if output_path.exists() and not OVERWRITE_OUTPUT:
        stats['skipped'] += 1
        print(f"Файл существует: {output_filename}, пропускаем")
        return
    
    print_separator()
    print(f"Обработка: {primary_path.name} + {video_path.name}")
    
    try:
        # Get audio track info from primary source
        audio_tracks = await get_audio_tracks(primary_path)
        
        if not audio_tracks:
            print("Нет аудиодорожек, копирование...")
            # Fallback to direct copy with video replacement
            await replace_video_only(primary_path, video_path, output_path, args.crf)
            return
        
        # Build filter_complex for audio normalization
        loudness_params = {
            "target_loudness": args.target_loudness,
            "true_peak": args.true_peak,
            "loudness_range": args.loudness_range
        }
        filter_complex = build_loudnorm_filter_complex(
            audio_tracks, 
            target_loudness=loudness_params["target_loudness"],
            true_peak=loudness_params["true_peak"], 
            loudness_range=loudness_params["loudness_range"]
        )
        
        # Prepare metadata options
        metadata_options = get_metadata_options(audio_tracks)
        
        # Build FFmpeg command
        ffmpeg_cmd = [
            "ffmpeg",
            "-y" if OVERWRITE_OUTPUT else "",
            "-i", str(primary_path),
            "-i", str(video_path),
            "-filter_complex", filter_complex,
            "-map", "0:v? -flags +bitexact",  # Explicitly exclude primary video
            "-map", "1:v",                   # Use video from secondary input
            "-map", "0:a",                   # All audio tracks
            "-map", "0:s?",                  # All subtitles
        ]
        
        # Add audio outputs with normalized streams
        for i in range(len(audio_tracks)):
            ffmpeg_cmd.extend(["-map", f"[a{i}]"])
        
        # Video encoding parameters (optimized for gradients)
        ffmpeg_cmd.extend([
            "-c:v", "libx265",
            "-x265-params",
            "qpstep=1:rect=1:hexagon=1:aq-mode=3:aq-strength=1.2:psy-rd=2.0:psy-trellis=2",
            "-crf", str(args.crf),
            "-preset", "medium",  # Balance between speed/quality
            "-tag:v", "hvc1",     # For better compatibility
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-c:s", "copy",
            *metadata_options,
            "-movflags", "+faststart",
            str(output_path)
        ])
        
        # Execute command
        print("Запуск кодирования:")
        # Filter out empty strings
        ffmpeg_cmd = [arg for arg in ffmpeg_cmd if arg]
        print(" ".join(ffmpeg_cmd))
        
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        
        if proc.returncode == 0:
            stats['processed'] += 1
            print("Обработка завершена успешно")
        else:
            stats['errors'] += 1
            print(f"Ошибка кодирования")
    
    except Exception as e:
        stats['errors'] += 1
        print(f"Произошла ошибка: {str(e)}")
    finally:
        stats['total'] += 1

async def main():
    global stats
    args = parse_arguments()
    
    # Setup signal handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    task = asyncio.create_task(process_files(args))
    tasks = [task]
    
    cleanup_signals = setup_signal_handlers(loop, stop_event, tasks)
    
    try:
        await task
    except asyncio.CancelledError:
        print("\nЗадача отменена")
    finally:
        cleanup_signals()
    
    print_final_stats(stats, start_time)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
        print_final_stats(stats, start_time)