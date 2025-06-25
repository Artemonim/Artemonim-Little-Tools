#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Audio/Video Transcriber

This script transcribes audio from audio and video files using OpenAI's Whisper model.
It can process individual files or all compatible files in a directory.
Models are downloaded automatically and stored locally.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
import whisper # type: ignore
import ffmpeg # type: ignore
import torch # type: ignore
import tqdm # type: ignore
from typing import Optional, Tuple # Added for type hinting
import re
import time

# * Import common utilities
sys.path.append(str(Path(__file__).parent.parent))
from littletools_core.utils import (
    setup_signal_handler, is_interrupted, register_cleanup_function,
    ensure_dir_exists, check_command_available, safe_delete,
    format_duration, print_file_info, print_status,
    BatchTimeEstimator
)

# * Increase recursion limit at module level to avoid RecursionError
sys.setrecursionlimit(10000)

# * Better Comments:
# * Important
# ! Warning
# ? Question
# TODO:

# * Configuration variables
SCRIPT_DIR = Path(__file__).parent.absolute()
DEFAULT_MODEL_ROOT = SCRIPT_DIR / "models"
DEFAULT_MODEL_NAME = "large-v3-turbo"
DEFAULT_OUTPUT_DIR_NAME = "0-OUTPUT-0" # Relative to project root if run via menu
DEFAULT_INPUT_DIR_NAME = "0-INPUT-0"   # Relative to project root if run via menu
TEMPERATURE = 0.25

# * Paths to sound files
SUCCESS_SOUND_PATH = SCRIPT_DIR / "Sounds" / "task_complete.opus"
ERROR_SOUND_PATH = SCRIPT_DIR / "Sounds" / "error.opus"

SUPPORTED_EXTENSIONS = [
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",  # Common audio
    ".mp4", ".mkv", ".mov", ".avi", ".webm"           # Common video
]

def check_ffmpeg_availability() -> bool:
    """Checks if ffmpeg is installed and available in PATH."""
    return check_command_available("ffmpeg")

def play_sound(sound_path: Path):
    """Play a sound file using ffplay."""
    try:
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
    except Exception:
        pass

def get_audio_duration(file_path: Path) -> float:
    """Get audio duration in seconds from a media file."""
    try:
        probe = ffmpeg.probe(str(file_path))
        return float(probe['format']['duration'])
    except Exception:
        return 0.0

def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.fff timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

def transcribe_file(file_path: Path, model, output_dir: Path, estimator: BatchTimeEstimator, output_format: str = "text", current_file: int = 1, total_files: int = 1) -> bool:
    """Transcribe a single audio or video file."""
    if is_interrupted():
        return False
    
    print(f"* Processing ({current_file}/{total_files} | ETA: {estimator.get_eta_str()}): {file_path.name}")
    
    # * Track processing start time
    file_start_time = time.time()
    file_duration = get_audio_duration(file_path)
    
    temp_audio_file = None
    try:
        # Check if it's a video file that needs audio extraction
        if file_path.suffix.lower() in [".mp4", ".mkv", ".mov", ".avi", ".webm"]:
            print(f"  Extracting audio from video file...")
            temp_audio_file = output_dir / f"temp_audio_{file_path.stem}.wav"
            
            try:
                (
                    ffmpeg
                    .input(str(file_path))
                    .output(str(temp_audio_file), acodec='pcm_s16le', ac=1, ar='16000')
                    .overwrite_output()
                    .run(quiet=True, capture_stdout=True)
                )
                audio_to_transcribe = temp_audio_file
            except ffmpeg.Error as e:
                print(f"! Error extracting audio: {e}")
                return False
        else:
            audio_to_transcribe = file_path
        
        if is_interrupted():
            return False
        
        print(f"  Transcribing with Whisper...")
        
        # Transcribe with Whisper using custom tqdm progress based on timestamps
        # Determine audio duration for progress bar
        try:
            probe = ffmpeg.probe(str(audio_to_transcribe))
            total_duration = float(probe['format']['duration'])
            file_duration = total_duration
        except Exception:
            total_duration = None

        # Prepare transcription arguments
        transcribe_args = {'temperature': TEMPERATURE, 'verbose': True}

        if total_duration:
            from contextlib import redirect_stdout

            class TqdmWriter:
                def __init__(self, total):
                    self.pbar = tqdm.tqdm(
                        total=total, 
                        unit='s', 
                        unit_scale=True, 
                        unit_divisor=1000,
                        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}, {rate_fmt}]'
                    )
                def write(self, text):
                    # * Handle both MM:SS.ss and HH:MM:SS.ss timestamp formats
                    m = re.search(r'\[(?:(\d+):)?(\d+):(\d+\.\d+) +--> +(?:(\d+):)?(\d+):(\d+\.\d+)\]', text)
                    if m:
                        # Extract end timestamp (groups 4, 5, 6)
                        end_hours = int(m.group(4)) if m.group(4) else 0
                        end_minutes = int(m.group(5))
                        end_seconds = float(m.group(6))
                        current = end_hours * 3600 + end_minutes * 60 + end_seconds
                        self.pbar.n = current
                        self.pbar.refresh()
                def flush(self):
                    pass

            writer = TqdmWriter(total_duration)
            # Capture Whisper's stdout to parse timestamps
            with redirect_stdout(writer):
                result = model.transcribe(str(audio_to_transcribe), **transcribe_args)
            writer.pbar.close()
        else:
            result = model.transcribe(str(audio_to_transcribe), **transcribe_args)
        
        if is_interrupted():
            return False
        
        # Save transcription based on output format
        if output_format == "text":
            output_file = output_dir / f"{file_path.stem}_transcription.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result['text'])
        elif output_format == "timestamped":
            output_file = output_dir / f"{file_path.stem}_transcription_timestamped.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                for segment in result['segments']:
                    start_time = format_timestamp(segment['start'])
                    end_time = format_timestamp(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"[{start_time} --> {end_time}] {text}\n")
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        print(f"  ✓ Transcription saved to: {output_file.name}")
        
        # * Update time tracking variables
        estimator.update(file_duration)
        
        return True
        
    except Exception as e:
        print(f"! Error transcribing {file_path.name}: {e}")
        return False
    finally:
        if temp_audio_file and temp_audio_file.exists():
            try:
                temp_audio_file.unlink()
            except Exception:
                pass

# * Signal handling is now managed by little_tools_utils

def check_existing_output_files(output_dir: Path, files_to_process: list, output_format: str = "text") -> Tuple[str, set]:
    """
    Check if output files already exist and ask user for confirmation.
    
    Args:
        output_dir: Output directory path
        files_to_process: List of input files to be processed
        output_format: Output format ("text" or "timestamped")
        
    Returns:
        Tuple of (action, files_to_skip_set) where:
        - action: 'continue', 'skip_existing', or 'cancel'
        - files_to_skip_set: Set of input file paths to skip (only relevant for 'skip_existing')
    """
    existing_files = []
    files_with_existing_output = set()
    
    for input_file in files_to_process:
        if output_format == "text":
            output_file = output_dir / f"{input_file.stem}_transcription.txt"
        else:  # timestamped
            output_file = output_dir / f"{input_file.stem}_transcription_timestamped.txt"
        
        if output_file.exists():
            existing_files.append(output_file.name)
            files_with_existing_output.add(input_file)
    
    if existing_files:
        print(f"\n! Warning: {len(existing_files)} output file(s) already exist in '{output_dir}':")
        for filename in existing_files[:5]:  # Show first 5 files
            print(f"  - {filename}")
        if len(existing_files) > 5:
            print(f"  ... and {len(existing_files) - 5} more.")
        
        print("\nChoose how to handle existing files:")
        print("  1. Overwrite existing files (continue processing all files)")
        print("  2. Skip files with existing output (process only new files)")
        print("  3. Cancel processing")
        
        while True:
            try:
                choice = input("Enter your choice (1/2/3): ").strip()
                if choice == '1':
                    return 'continue', set()
                elif choice == '2':
                    return 'skip_existing', files_with_existing_output
                elif choice == '3':
                    return 'cancel', set()
                else:
                    print("Please enter '1', '2', or '3'.")
            except KeyboardInterrupt:
                print("\n! Operation cancelled by user.")
                return 'cancel', set()
    
    return 'continue', set()

def main():
    """Main function to parse arguments and run transcription."""
    # Set up signal handler for graceful interruption
    setup_signal_handler()
    
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video files using OpenAI Whisper.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        help=(
            "Path to a single audio/video file or a directory containing media files.\n"
            f"If not specified, defaults to '{DEFAULT_INPUT_DIR_NAME}' relative to project root (if run from menu.py)\n"
            "or current script's parent directory if run standalone."
        )
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help=(
            "Directory to save transcription (.txt) files.\n"
            f"If not specified, defaults to '{DEFAULT_OUTPUT_DIR_NAME}' relative to project root (if run from menu.py)\n"
            "or a new 'transcriptions' subdirectory in the input directory if run standalone."
        )
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL_NAME,
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "large-v3-turbo"],
        help=f"Whisper model to use (default: {DEFAULT_MODEL_NAME})."
    )
    parser.add_argument(
        "--model_root",
        type=str,
        default=str(DEFAULT_MODEL_ROOT),
        help=(
            "Directory to store downloaded Whisper models.\n"
            f"(default: {DEFAULT_MODEL_ROOT})"
        )
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Language code (e.g., 'en', 'ru') for transcription. Detects automatically if not set."
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=TEMPERATURE,
        help=f"Temperature for sampling (0.0 to 1.0). Higher values make output more random (default: {TEMPERATURE})."
    )
    parser.add_argument(
        "--format",
        type=str,
        default="text",
        choices=["text", "timestamped"],
        help="Output format: 'text' for plain text, 'timestamped' for text with timestamps (default: text)."
    )

    args = parser.parse_args()

    # Enforce GPU-only processing
    if not torch.cuda.is_available():
        print("! CUDA GPU is required but not available. Aborting.")
        sys.exit(1)
    use_gpu = True  # GPU processing enforced

    # Determine input and output directories
    # This logic tries to be smart about standalone vs. menu.py execution
    # menu.py will pass absolute paths for input and output
    if args.input and Path(args.input).is_absolute():
        input_path = Path(args.input)
    elif args.input: # Relative path provided
        input_path = Path.cwd() / args.input
    elif SCRIPT_DIR.parent.name == "Audio-_Video-2-Text" and (SCRIPT_DIR.parent.parent / DEFAULT_INPUT_DIR_NAME).exists():
        # Likely run via menu.py, use project-level 0-INPUT-0
        input_path = SCRIPT_DIR.parent.parent / DEFAULT_INPUT_DIR_NAME
    else:
        # Standalone, use script's parent as base for input search
        input_path = SCRIPT_DIR.parent / DEFAULT_INPUT_DIR_NAME
        if not input_path.exists():
            input_path = SCRIPT_DIR.parent # Fallback to script's parent dir
            print(f"? Input path not specified and default '{DEFAULT_INPUT_DIR_NAME}' not found. Using '{input_path}'.")

    if args.output and Path(args.output).is_absolute():
        output_dir = Path(args.output)
    elif args.output: # Relative path provided
        output_dir = Path.cwd() / args.output
    elif SCRIPT_DIR.parent.name == "Audio-_Video-2-Text" and (SCRIPT_DIR.parent.parent / DEFAULT_OUTPUT_DIR_NAME).exists():
        # Likely run via menu.py, use project-level 0-OUTPUT-0
        output_dir = SCRIPT_DIR.parent.parent / DEFAULT_OUTPUT_DIR_NAME
    else:
        # Standalone, create 'transcriptions' subdir in input_path if it's a dir, or script's parent
        base_for_output = input_path if input_path.is_dir() else input_path.parent
        output_dir = base_for_output / "transcriptions"
        print(f"? Output path not specified. Using '{output_dir}'.")

    ensure_dir_exists(output_dir)
    
    model_root_path = Path(args.model_root)
    ensure_dir_exists(model_root_path)

    print(f"* Using Whisper model: {args.model}")
    print(f"* Model download directory: {model_root_path}")
    print(f"* Input path: {input_path}")
    print(f"* Output directory: {output_dir}")
    print(f"* Output format: {args.format}")
    print("* GPU acceleration: Enabled")
    if args.language:
        print(f"* Language: {args.language}")
    if args.temperature != 0.0:
        print(f"* Temperature: {args.temperature}")

    # Gather list of files to process before overwrite confirmation
    files_to_process = []
    if not input_path.exists():
        print(f"! Input path '{input_path}' does not exist.")
        sys.exit(1)
    if input_path.is_file():
        if input_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files_to_process.append(input_path)
        else:
            print(f"! Input file '{input_path.name}' is not a supported audio/video type.")
            sys.exit(1)
    elif input_path.is_dir():
        print(f"* Scanning directory '{input_path}' for media files...")
        for item in input_path.iterdir():
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                files_to_process.append(item)
        if not files_to_process:
            print(f"! No compatible media files found in '{input_path}'.")
            sys.exit(0)
    else:
        print(f"! Input path '{input_path}' is neither a file nor a directory.")
        sys.exit(1)
    print(f"* Found {len(files_to_process)} file(s) to process.")

    # Check for existing output files and ask for confirmation
    overwrite_action, files_to_skip = check_existing_output_files(output_dir, files_to_process, args.format)
    if overwrite_action == 'cancel':
        print("* Operation cancelled by user.")
        play_sound(ERROR_SOUND_PATH)
        sys.exit(0)
    elif overwrite_action == 'skip_existing':
        files_to_process = [f for f in files_to_process if f not in files_to_skip]
        if not files_to_process:
            print("* No files to process after skipping existing outputs.")
            sys.exit(0)
        print(f"* Will process {len(files_to_process)} file(s) (skipping {len(files_to_skip)} with existing output).")

    try:
        device = "cuda"
        model = whisper.load_model(args.model, download_root=str(model_root_path), device=device)
        print(f"* Model '{args.model}' loaded successfully on GPU.")
    except Exception as e:
        print(f"! Failed to load Whisper model '{args.model}': {e}")
        print("  Please ensure the model name is correct and you have internet access for the first download.")
        sys.exit(1)

    # * Initialize time tracking variables
    estimator = BatchTimeEstimator()
    
    # * Calculate total audio duration for all files
    print("* Calculating total audio duration...")
    for file_path in files_to_process:
        duration = get_audio_duration(file_path)
        estimator.add_item(duration)
    
    if estimator.total_workload > 0:
        print(f"* Total audio duration: {format_duration(estimator.total_workload)}")

    # Start the master timer
    estimator.start()
    
    successful_transcriptions = 0
    for current_file_num, file_to_process in enumerate(files_to_process, 1):
        # Check for interruption before processing each file
        if is_interrupted():
            print("\n! Processing interrupted by user.")
            break
            
        if transcribe_file(file_to_process, model, output_dir, estimator, args.format, current_file_num, len(files_to_process)):
            successful_transcriptions += 1

    print(f'\n--- Transcription Summary ---')
    print(f"  Total files processed: {len(files_to_process)}")
    print(f"  Successful transcriptions: {successful_transcriptions}")
    print(f"  Failed transcriptions: {len(files_to_process) - successful_transcriptions}")
    print(f"  Output saved to: {output_dir}")
    
    if is_interrupted():
        print("  Status: Interrupted by user")
        play_sound(ERROR_SOUND_PATH)
        sys.exit(130)  # Standard exit code for SIGINT

    if successful_transcriptions < len(files_to_process) and files_to_process:
        play_sound(ERROR_SOUND_PATH)
        sys.exit(1)  # Indicate partial failure if there were files to process

    # * Play success notification
    play_sound(SUCCESS_SOUND_PATH)

if __name__ == "__main__":
    # For ffmpeg-python to find ffmpeg when script is frozen by PyInstaller
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
    main() 