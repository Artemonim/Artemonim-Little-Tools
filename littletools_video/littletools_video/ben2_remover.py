#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BEN-2 Background Remover - LittleTools

A command-line tool to remove the background from videos using the BEN-2 model.
This tool can process a single video file or a directory of video files,
outputting videos with a transparent background in .webm format.
"""

import time
from pathlib import Path
from typing import List, Tuple, Any, Optional

import typer
from rich.console import Console
from rich.progress import (BarColumn, Progress, TextColumn,
                           TimeElapsedColumn, TimeRemainingColumn)
from rich.status import Status
from typing_extensions import Annotated

# * Core utilities from the project
# type: ignore is added because the editable install path is not visible to the linter in this workspace.
from littletools_core.utils import (
    ensure_dir_exists,
    get_files_by_extension,
    prompt_for_path,
    get_default_io_paths,
)  # type: ignore

# --- Globals & Configuration ---
console = Console()
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv"]

# * Create a Typer application. This 'app' is the entry point for the CLI.
app = typer.Typer(
    name="ben2-remover",
    help="Removes the background from videos using the BEN-2 model. Creates .webm files with transparency.",
    no_args_is_help=True,
    add_completion=False
)


def initialize_model() -> Any:
    """
    Initializes the BEN-2 model (CUDA-only enforced).

    Returns:
        The initialized BEN-2 model instance.
    """
    console.print("\n[bold yellow]* Initializing BEN-2 Model...[/bold yellow]")

    # * Import heavy dependencies here to keep top-level import lightweight.
    try:
        from huggingface_hub import hf_hub_download
        import torch
        from ben2 import BEN_Base  # type: ignore
    except ModuleNotFoundError as import_err:
        console.print("[bold red]! Required libraries for BEN-2 are missing.[/bold red]")
        console.print("  - Please rerun the installer or install the missing packages manually.")
        raise typer.Exit(code=1) from import_err

    # * Enforce CUDA-only usage
    if not torch.cuda.is_available():
        console.print("[bold red]! CUDA device is not available. BEN-2 requires a CUDA-capable GPU and the correct PyTorch+CUDA installation.")
        raise typer.Exit(code=1)

    with Status("[bold green]Checking for model weights...[/bold green]", console=console):
        weights_path = hf_hub_download(
            repo_id="PramaLLC/BEN2",
            filename="BEN2_Base.pth"
        )
    console.print(f"  [green]✓[/green] Model weights are available.")

    console.print("[yellow]* Loading model onto CUDA device...[/yellow]")
    device = torch.device("cuda")
    console.print(f"  - Using device: [bold cyan]CUDA[/bold cyan]")

    try:
        model = BEN_Base().to(device).eval()
        model.loadcheckpoints(weights_path)
        console.print("[green]✓ Model initialized successfully.[/green]")
        return model
    except Exception as e:
        console.print(f"[bold red]! Fatal Error: Could not load the BEN-2 model.[/bold red]")
        console.print(f"  - Details: {e}")
        console.print("  - Please ensure PyTorch and CUDA (if applicable) are correctly installed.")
        raise typer.Exit(code=1) from e


def _parse_bg_color(bg_color_str: str) -> Tuple[int, int, int]:
    """Parses an 'R,G,B' string into a tuple of integers."""
    try:
        r, g, b = map(int, bg_color_str.replace(" ", "").split(','))
        return (r, g, b)
    except (ValueError, TypeError):
        console.print(f"[red]! Invalid background color format: '{bg_color_str}'. Using black (0,0,0).[/red]")
        return (0, 0, 0)


@app.command(
    name="process",
    help="Process a single video file or a directory of videos to remove their background."
)
def process_videos(
    input_path: Annotated[Optional[Path], typer.Argument(
        file_okay=True,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to the input video file or directory. If omitted, you will be prompted.",
        show_default=False
    )] = None,
    output_path: Annotated[Optional[Path], typer.Option(
        "--output", "-o",
        resolve_path=True,
        help="Path to the output directory. If omitted, you will be prompted.",
        show_default=False
    )] = None,
    batch_size: Annotated[int, typer.Option(
        "--batch", "-b",
        min=1,
        help="Batch size for processing frames. Higher values require more VRAM."
    )] = 1,
    refine_foreground: Annotated[bool, typer.Option(
        "--refine",
        help="Enable an extra pass to refine the foreground edges. Slower but more accurate."
    )] = False,
    to_mp4: Annotated[bool, typer.Option(
        "--to-mp4",
        help="Output as .mp4 with a solid background instead of a transparent .webm."
    )] = False,
    bg_color: Annotated[str, typer.Option(
        "--bg-color",
        help="RGB background color (e.g., '0,255,0') to use when --to-mp4 is enabled."
    )] = "0,0,0",
):
    """
    Main command to run the background removal process on video files.
    """
    default_input, default_output_base = get_default_io_paths("ben2-remover")

    if input_path is None:
        input_path = prompt_for_path(
            "Enter the path to your input video file or directory",
            default=default_input,
        )

    if output_path is None:
        output_path = prompt_for_path(
            "Enter the path for the output directory",
            default=default_output_base,
            must_exist=False,  # The output directory doesn't have to exist yet.
        )

    start_time = time.monotonic()
    stats = {"success": 0, "failed": 0, "skipped": 0}

    # * Ensure the output directory exists.
    ensure_dir_exists(output_path)

    # * Collect all video files to be processed.
    console.print("\n[bold yellow]* Searching for video files...[/bold yellow]")
    if input_path.is_dir():
        video_files = get_files_by_extension(input_path, VIDEO_EXTENSIONS)
    else:
        video_files = [input_path]

    if not video_files:
        console.print("[yellow]! No video files found to process.[/yellow]")
        raise typer.Exit()

    total_files = len(video_files)
    console.print(f"  [green]✓[/green] Found [bold cyan]{total_files}[/bold cyan] video(s) to process.")

    # * Initialize the model once for all files.
    model = initialize_model()

    console.print("\n[bold yellow]* Starting processing...[/bold yellow]")
    rgb_tuple = _parse_bg_color(bg_color)
    output_as_webm = not to_mp4

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing videos", total=total_files)

        for video_path in video_files:
            progress.console.print(f"▶ Processing [cyan]{video_path.name}[/cyan]...")
            video_out_dir = output_path / video_path.stem
            ensure_dir_exists(video_out_dir)

            # ! The BEN-2 library requires the output path to be a string ending in a slash.
            output_path_str = str(video_out_dir) + "/"

            try:
                # * This is the core processing call.
                model.segment_video(
                    video_path=str(video_path),
                    output_path=output_path_str,
                    fps=0,  # ? 0 preserves the original FPS.
                    batch=batch_size,
                    refine_foreground=refine_foreground,
                    webm=output_as_webm,
                    rgb_value=rgb_tuple,
                    print_frames_processed=True  # ? Provides real-time feedback in the console.
                )
                stats["success"] += 1
                progress.console.print(f"  [green]✓ Success![/green] Output saved in [cyan]{video_out_dir}[/cyan]")
            except Exception as e:
                stats["failed"] += 1
                progress.console.print(f"[bold red]! Error processing {video_path.name}:[/bold red]")
                progress.console.print(f"  [red]- {e}[/red]")

            progress.update(task, advance=1)

    # * Print final summary
    end_time = time.monotonic()
    elapsed = end_time - start_time
    console.print("\n--- [bold]Operation Summary[/bold] ---")
    console.print(f"  - [green]Successful[/green]: {stats['success']}")
    console.print(f"  - [red]Failed[/red]:       {stats['failed']}")
    console.print(f"  - Elapsed time: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
    console.print("---")


if __name__ == "__main__":
    app()
