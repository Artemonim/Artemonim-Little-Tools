#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image+Audio to Video Creator Tool

A Typer-based CLI tool to create a video from a still image and an audio track.
This script is designed to be a plugin for the 'littletools-cli'.
"""

import asyncio
from pathlib import Path

import typer
from PIL import Image
from rich.console import Console
from typing import Optional
from typing_extensions import Annotated

from littletools_core.utils import (
    ensure_dir_exists,
    get_platform_info,
    setup_signal_handler,
)
from littletools_video.ffmpeg_utils import (
    ProcessingStats,
    get_video_duration,
    run_ffmpeg_command,
)

app = typer.Typer(
    name="image-audio-to-video",
    help="Create a video from a still image and an audio track.",
    no_args_is_help=True,
)
console = Console()

OUTPUT_DIR = Path.cwd() / "0-OUTPUT-0"


async def create_video(image_path: Path, audio_path: Path, output_path: Path):
    """Asynchronously creates the video using FFmpeg."""
    stats = ProcessingStats()

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if width % 2 != 0 or height % 2 != 0:
                console.print(
                    "[yellow]! Warning: Image dimensions are not even. This may cause issues with some video codecs.[/yellow]"
                )
    except Exception as e:
        console.print(f"[red]! Could not read image dimensions: {e}[/red]")
        raise typer.Exit(code=1)

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-tune",
        "stillimage",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(output_path),
    ]

    console.print("[*] Starting video creation with FFmpeg...")
    total_duration = await get_video_duration(str(audio_path))

    success = await run_ffmpeg_command(
        cmd,
        stats,
        quiet=True,
        output_path=str(output_path),
        total_duration=total_duration,
    )

    if success:
        console.print(
            f"[green]✓ Video created successfully![/green] Output: {output_path.name}"
        )
    else:
        console.print(
            f"[red]! Video creation failed. Check FFmpeg output for details.[/red]"
        )
        raise typer.Exit(code=1)


@app.command()
def run(
    image_file: Annotated[
        Path, typer.Option("--image", "-i", help="Path to the input image file.")
    ],
    audio_file: Annotated[
        Path, typer.Option("--audio", "-a", help="Path to the input audio file.")
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Path for the output video file. [default: <image_stem>.mp4]",
        ),
    ] = None,
):
    """
    Creates a video from one image and one audio file.
    """
    if not image_file.exists():
        console.print(f"[red]! Image file not found: {image_file}[/red]")
        raise typer.Exit(code=1)
    if not audio_file.exists():
        console.print(f"[red]! Audio file not found: {audio_file}[/red]")
        raise typer.Exit(code=1)

    if output_file is None:
        ensure_dir_exists(OUTPUT_DIR)
        output_file = OUTPUT_DIR / f"{image_file.stem}.mp4"
    else:
        ensure_dir_exists(output_file.parent)

    console.print(f"[*] Image Source: {image_file.name}")
    console.print(f"[*] Audio Source: {audio_file.name}")
    console.print(f"[*] Output File: {output_file.name}")

    try:
        asyncio.run(create_video(image_file, audio_file, output_file))
    except KeyboardInterrupt:
        console.print("\n[yellow]! User interrupted the process.[/yellow]")
        raise typer.Exit()


if __name__ == "__main__":
    setup_signal_handler()
    app()
