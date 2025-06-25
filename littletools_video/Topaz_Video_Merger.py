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
import argparse
from pathlib import Path

# Import common utilities
from ffmpeg_utils import (
    get_audio_tracks, build_loudnorm_filter_complex, get_metadata_options,
    run_ffmpeg_command, standard_main, check_output_file_exists, print_separator,
    print_file_info, clean_partial_output, DEFAULT_OUTPUT_FOLDER, ProcessingStats
)

# * Default configuration
OUTPUT_FOLDER = DEFAULT_OUTPUT_FOLDER
DEFAULT_CRF = 22

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Normalize audio and replace video stream using dual input files",
        epilog=(__doc__ or "").split("\n")[3] if (__doc__ or "").count("\n") >= 4 else None
    )
    parser.add_argument("-i1", "--input-primary", required=True,
                        help="Primary input file (provides audio/subtitles)")
    parser.add_argument("-i2", "--input-video", required=True,
                        help="Secondary input file (provides video stream)")
    parser.add_argument("-o", "--output", 
                        help=f"Output folder path (default: {DEFAULT_OUTPUT_FOLDER})")
    parser.add_argument("-t", "--threads", type=int,
                        help="Number of concurrent tasks (default: auto)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing output files")
    parser.add_argument("--crf", type=int, default=DEFAULT_CRF,
                        help=f"HEVC CRF value (lower = better quality, default: {DEFAULT_CRF})")
    parser.add_argument("--target-loudness", type=float,
                        help="Target integrated loudness level in LUFS (default: -16.0)")
    parser.add_argument("--true-peak", type=float,
                        help="Maximum true peak level in dBTP (default: -1.5)")
    parser.add_argument("--loudness-range", type=float,
                        help="Target loudness range in LU (default: 11.0)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress progress output")
    return parser.parse_args()

async def replace_video_only(primary_path, video_path, output_path, crf, stats, overwrite=False, quiet=False):
    """
    Replace video stream without audio normalization.
    
    Args:
        primary_path: Path to primary input file (audio source)
        video_path: Path to video input file
        output_path: Path for output file
        crf: Constant Rate Factor for video encoding
        stats: ProcessingStats object to update
        overwrite: Whether to overwrite existing files
        quiet: Whether to suppress progress output
    """
    # Skip if file exists and overwrite is False
    if check_output_file_exists(output_path, overwrite):
        stats.increment("skipped")
        return
    
    filename = os.path.basename(primary_path) + " + " + os.path.basename(video_path)
    
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",  # Скрыть баннер версии
        "-loglevel", "warning",  # Показывать только предупреждения и ошибки
        "-stats",  # Сохранить вывод статистики/прогресса
        "-y" if overwrite else "",
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
    
    await run_ffmpeg_command(
        ffmpeg_cmd, stats, quiet=quiet, 
        output_path=output_path,
        file_position=1, file_count=1, filename=filename
    )

async def process_files(args, stats):
    """
    Process the merge operation on the input files.
    
    Args:
        args: Command line arguments
        stats: ProcessingStats object
    """
    # Setup configuration
    output_folder = args.output or DEFAULT_OUTPUT_FOLDER
    overwrite = args.overwrite
    quiet = args.quiet if hasattr(args, 'quiet') else False
    
    # Prepare input paths
    primary_path = Path(args.input_primary).resolve()
    video_path = Path(args.input_video).resolve()
    
    # Get output filename
    output_filename = f"{primary_path.stem}_normalized_{video_path.stem}.mkv"
    output_path = Path(output_folder) / output_filename
    
    # Update total files stat
    stats.increment("total")
    
    # Skip if file exists
    if check_output_file_exists(output_path, overwrite):
        stats.increment("skipped")
        return
    
    # Print separator
    print_separator()
    
    # Print file info with position
    filename = f"{primary_path.name} + {video_path.name}"
    print_file_info(filename, 1, 1)
    
    try:
        # Get audio track information
        audio_tracks = await get_audio_tracks(primary_path)
        
        if not audio_tracks:
            # Fallback to direct copy with video replacement
            await replace_video_only(
                primary_path, video_path, output_path, 
                args.crf, stats, overwrite, quiet
            )
            return
        
        # Build filter_complex for audio normalization
        loudness_params = {
            "target_loudness": args.target_loudness if args.target_loudness is not None else -16.0,
            "true_peak": args.true_peak if args.true_peak is not None else -1.5,
            "loudness_range": args.loudness_range if args.loudness_range is not None else 11.0
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
            "-hide_banner",  # Скрыть баннер версии
            "-loglevel", "warning",  # Показывать только предупреждения и ошибки
            "-stats",  # Сохранить вывод статистики/прогресса
            "-y" if overwrite else "",
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
        await run_ffmpeg_command(
            ffmpeg_cmd, stats, quiet=quiet, 
            output_path=output_path,
            file_position=1, file_count=1, filename=filename
        )
    
    except asyncio.CancelledError:
        # Mark as skipped if interrupted
        if not stats.interrupted:
            stats.increment("skipped")
        clean_partial_output(output_path)
        raise
        
    except Exception as e:
        if not stats.interrupted:
            stats.increment("errors")
        print(f"Произошла ошибка: {str(e)}")
        clean_partial_output(output_path)

async def main():
    """Main entry point for the script."""
    args = parse_arguments()
    await standard_main(args, process_files, DEFAULT_OUTPUT_FOLDER)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")