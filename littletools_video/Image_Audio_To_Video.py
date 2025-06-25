#!/usr/bin/env python3
"""
Image+Audio → Video Creator

Creates an HEVC-encoded (NVENC) video from a still image and an audio track.
The resulting video keeps the image aspect ratio, but scales down so that the
longest side is at most 2160 pixels (Lanczos). Frames per second are fixed at
10 fps.

The script runs in *interactive* mode only:
1. Prompts for image path.
2. Prompts for audio path.
3. Builds the output filename automatically (same directory as the audio file
   with ``_video.mp4`` suffix) or lets the user override it.
4. Executes FFmpeg with the parameters required by the Architect.
5. Asks whether to repeat with another pair of files or exit back to the menu.

Dependencies:
    • FFmpeg (system dependency).
    • Pillow 9+ (Python dependency) – used to detect the image size.

Usage (invoked by LittleTools menu – no parameters expected)::

    python Image_Audio_To_Video.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Tuple

from PIL import Image
from littletools_core.utils import (
    check_command_available,
    print_separator,
    print_status,
)
from .ffmpeg_utils import (
    get_video_duration,
    run_ffmpeg_command,
    get_nvenc_hevc_video_options,
)


MAX_DIMENSION = 2160  # * The longer side must not exceed this value (in pixels)
FPS = 10  # * Target frames per second
# * FFmpeg NVENC encoding parameters are now fetched from ffmpeg_utils


def _ask_path(prompt: str) -> Path:
    """Prompt the user until a valid file path is provided."""
    while True:
        try:
            user_input = input(prompt).strip().strip('"')
        except KeyboardInterrupt:
            print("\n! Operation cancelled by user.")
            sys.exit(1)

        path = Path(user_input).expanduser()
        if path.is_file():
            return path
        print_status(f"File not found: {path}", "error")


def _calc_scaled_resolution(image_path: Path) -> Tuple[int, int]:
    """Return width and height ensuring the longer side ≤ ``MAX_DIMENSION``.

    The original aspect ratio is preserved and both dimensions are forced to an
    even value (NVENC requirement).
    """
    with Image.open(image_path) as img:
        width, height = img.size

    longest = max(width, height)
    if longest <= MAX_DIMENSION:
        new_w, new_h = width, height
    else:
        scale_factor = MAX_DIMENSION / float(longest)
        new_w = int(round(width * scale_factor / 2) * 2)
        new_h = int(round(height * scale_factor / 2) * 2)

    return new_w, new_h


def _build_ffmpeg_cmd(image: Path, audio: Path, output: Path) -> list[str]:
    """Compose the FFmpeg command according to the specification."""
    width, height = _calc_scaled_resolution(image)

    vf_parts = [f"scale={width}:{height}:flags=lanczos", f"fps={FPS}"]
    vf = ",".join(vf_parts)

    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-y",  # * Overwrite output without asking – the menu will have warned the user.
        "-loop",
        "1",
        "-i",
        str(image),
        "-i",
        str(audio),
        "-vf",
        vf,
        *get_nvenc_hevc_video_options(),
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-b:a",
        "320k",
        "-shortest",
        str(output),
    ]
    return cmd


# * Async execution wrapper with shared progress bar


async def _run_ffmpeg_async(cmd: list[str], audio_path: Path, output_path: Path) -> bool:
    """Execute FFmpeg with shared progress-bar utility."""
    total_duration = await get_video_duration(str(audio_path))
    success = await run_ffmpeg_command(
        cmd,
        quiet=True,
        output_path=str(output_path),
        filename=audio_path.name,
        total_duration=total_duration,
    )
    return success


def _suggest_output(audio_path: Path) -> Path:
    """Return a default output file path based on the audio filename."""
    return audio_path.with_name(f"{audio_path.stem}_video.mp4")


def main() -> None:
    """Entry-point for interactive use."""
    if not check_command_available("ffmpeg"):
        print_status("FFmpeg is not available. Please install it and make sure it is in PATH.", "error")
        sys.exit(1)

    print_separator()
    print("* Image + Audio → Video Creator (interactive mode)")

    while True:
        # * Gather user inputs
        image_path = _ask_path("Enter path to the image file: ")
        audio_path = _ask_path("Enter path to the audio file: ")

        default_output = _suggest_output(audio_path)
        try:
            output_str = input(f"Enter output video path [default: {default_output}]: ").strip()
        except KeyboardInterrupt:
            print("\n! Operation cancelled by user.")
            sys.exit(1)
        output_path = Path(output_str).expanduser() if output_str else default_output

        # * Confirm overwrite if file exists
        if output_path.exists():
            overwrite = input("Output file exists – overwrite? (y/N): ").strip().lower()
            if overwrite != "y":
                print_status("Operation cancelled – not overwriting existing file.", "warning")
                continue

        # * Build and run FFmpeg command
        ffmpeg_cmd = _build_ffmpeg_cmd(image_path, audio_path, output_path)
        print_separator()
        print("* Executing FFmpeg:")
        print("  " + " ".join(ffmpeg_cmd))
        print_separator()

        # * Run asynchronously to benefit from progress-bar parsing
        try:
            success = asyncio.run(_run_ffmpeg_async(ffmpeg_cmd, audio_path, output_path))
        except KeyboardInterrupt:
            print("\n! Encoding interrupted by user.")
            success = False

        if success:
            print_status(f"Video created successfully: {output_path}", "success")
        else:
            print_status("FFmpeg reported an error.", "error")

        # * Ask to repeat
        try:
            again = input("\nWould you like to create another video? (y to repeat / any other key to return to menu): ").strip().lower()
        except KeyboardInterrupt:
            print("\nReturning to menu.")
            break

        if again != "y":
            break

    print("\nReturning to LittleTools menu…")
