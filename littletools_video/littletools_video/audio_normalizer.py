#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFMPEG MKV Audio Normalizer Tool

A Typer-based CLI tool to normalize audio tracks in MKV files using FFmpeg.
Processes all .mkv files in a directory.
This script is designed to be a plugin for the 'littletools-cli'.
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from littletools_core.utils import BatchTimeEstimator
from littletools_core.utils import ensure_dir_exists
from littletools_core.utils import format_duration
from littletools_core.utils import prompt_for_path
from littletools_core.utils import run_tasks_with_semaphore
from littletools_core.utils import setup_signal_handler
from littletools_video.ffmpeg_utils import ProcessingStats
from littletools_video.ffmpeg_utils import build_loudnorm_filter_complex
from littletools_video.ffmpeg_utils import get_audio_tracks
from littletools_video.ffmpeg_utils import get_max_workers
from littletools_video.ffmpeg_utils import get_metadata_options
from littletools_video.ffmpeg_utils import run_ffmpeg_command
from littletools_video.ffmpeg_utils import setup_signal_handlers
from littletools_video.ffmpeg_utils import standard_main

app = typer.Typer(
    name="audio-normalizer",
    help="Normalize audio tracks in MKV files using FFmpeg (processes a directory).",
    no_args_is_help=True,
)
console = Console()

INPUT_DIR = Path.cwd() / "0-INPUT-0"
OUTPUT_DIR = Path.cwd() / "0-OUTPUT-0"


async def process_file(
    file_path: Path,
    output_dir: Path,
    overwrite: bool,
    stats: ProcessingStats,
    estimator: BatchTimeEstimator,
    position: int,
    total: int,
):
    """Normalizes a single MKV file."""
    output_path = output_dir / f"{file_path.stem}_normalized.mkv"

    if not overwrite and output_path.exists():
        console.print(
            f"[{position}/{total}] Skipping {file_path.name} (output exists)."
        )
        stats.increment("skipped")
        return

    console.print(f"[{position}/{total}] Normalizing {file_path.name}...")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(file_path),
        "-map",
        "0",
        "-c:v",
        "copy",
        "-c:s",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(output_path),
    ]

    success = await run_ffmpeg_command(
        cmd, stats, quiet=True, output_path=str(output_path)
    )
    if success:
        console.print(f"  -> [green]✓ Normalized:[/green] {output_path.name}")
    else:
        console.print(f"  -> [red]✗ Failed to normalize:[/red] {file_path.name}")


@app.command()
def run(
    input_dir: Annotated[
        Path, typer.Option("--input", "-i", help="Input directory with MKV files.")
    ] = INPUT_DIR,
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for normalized files."),
    ] = OUTPUT_DIR,
    overwrite: Annotated[bool, typer.Option(help="Overwrite existing files.")] = False,
    concurrency: Annotated[
        int, typer.Option(help="Number of files to process at once.")
    ] = 2,
):
    """
    Batch-normalizes the audio of all .mkv files in a directory.
    """
    ensure_dir_exists(input_dir)
    ensure_dir_exists(output_dir)

    console.print(f"[*] Starting MKV audio normalization from '{input_dir}'.")

    files = sorted(input_dir.glob("*.mkv"))
    if not files:
        console.print("[yellow]! No .mkv files found in the input directory.[/yellow]")
        raise typer.Exit()

    console.print(f"[*] Found {len(files)} MKV file(s) to process.")

    stats = ProcessingStats()
    estimator = BatchTimeEstimator()
    stop_event = asyncio.Event()

    async def main_async():
        tasks = [
            process_file(f, output_dir, overwrite, stats, estimator, i + 1, len(files))
            for i, f in enumerate(files)
        ]
        await run_tasks_with_semaphore(tasks, stop_event, concurrency)

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]! User interrupted the process.[/yellow]")
        stop_event.set()

    console.print("\n--- Normalization Summary ---")
    # stats.print_summary() # print_summary needs an elapsed time argument
    console.print("[green]✓ Normalization process finished.[/green]")


if __name__ == "__main__":
    setup_signal_handler()
    app()
