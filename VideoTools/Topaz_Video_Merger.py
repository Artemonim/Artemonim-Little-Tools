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
import signal
import json
import platform
import time
import argparse
from collections import defaultdict
from pathlib import Path

# Configuration variables
INPUT_PRIMARY = None  # Primary input (audio/subtitles)
INPUT_VIDEO = None    # Video source
OUTPUT_FOLDER = "./normalized"
MANUAL_THREAD_LIMIT = 2
AUTO_THREAD_LIMIT_DIVIDER = 3
OVERWRITE_OUTPUT = False
MAX_WORKERS = max((os.cpu_count() or MANUAL_THREAD_LIMIT) // AUTO_THREAD_LIMIT_DIVIDER, MANUAL_THREAD_LIMIT)
stats = defaultdict(int)
start_time = time.monotonic()

def print_separator():
    print("\n" + "═" * 50 + "\n")

def print_file_info(filename, current, total):
    print(f"Обработка файла [{current}/{total}]: {filename}")
    print(f"Осталось задач: {total - current}")

def print_final_stats():
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
    return parser.parse_args()

async def process_files(args):
    global MAX_WORKERS, OVERWRITE_OUTPUT, stats
    OVERWRITE_OUTPUT = args.overwrite
    MAX_WORKERS = args.threads or MAX_WORKERS
    OUTPUT_FOLDER = args.output or "./normalized"
    
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
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
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=index:stream_tags=title",
            "-print_format", "json", str(primary_path)
        ]
        ffprobe_proc = await asyncio.create_subprocess_exec(
            *ffprobe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ffprobe_proc.communicate()
        if ffprobe_proc.returncode != 0:
            raise RuntimeError(f"FFprobe error: {stderr.decode()}")
        
        audio_info = json.loads(stdout.decode())
        audio_tracks = audio_info.get('streams', [])
        
        if not audio_tracks:
            print("Нет аудиодорожек, копирование...")
            # Fallback to direct copy with video replacement
            await replace_video_only(primary_path, video_path, output_path, args.crf)
            return
        
        # Build filter_complex for audio normalization
        I = -16.0  # Target loudness
        filter_complex = "".join(
            f"[0:a:{i}]loudnorm=I={I}:TP=-1.5:LRA=11[a{i}];" for i in range(len(audio_tracks))
        ).rstrip(';')
        
        # Prepare metadata options
        metadata_options = []
        for i, track in enumerate(audio_tracks):
            title = track.get('tags', {}).get('title', '')
            if title:
                metadata_options.extend([f"-metadata:s:a:{i}", f"title={title}"])
        
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
        print(" ".join([arg for arg in ffmpeg_cmd if arg]))  # Filter out empty strings
        
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
            print(f"Ошибка кодирования: {proc.stderr.read().decode()}")
    
    except Exception as e:
        stats['errors'] += 1
        print(f"Произошла ошибка: {str(e)}")
    finally:
        stats['total'] += 1

async def main():
    global stats
    args = parse_arguments()
    
    await process_files(args)
    print_final_stats()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
        print_final_stats()