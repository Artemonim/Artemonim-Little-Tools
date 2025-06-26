#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Transcriber Tool

A Typer-based CLI tool to transcribe audio and video files using OpenAI's Whisper model.
This script is designed to be a plugin for the 'littletools-cli'.
"""

from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from littletools_core.utils import ensure_dir_exists, setup_signal_handler
from littletools_core.huggingface_utils import download_hf_model
import whisper
import torch
from tqdm import tqdm

app = typer.Typer(
    name="whisper-transcriber",
    help="Transcribe audio/video files using OpenAI Whisper.",
    no_args_is_help=True,
)
console = Console()

INPUT_DIR = Path.cwd() / "0-INPUT-0"
OUTPUT_DIR = Path.cwd() / "0-OUTPUT-0"

SUPPORTED_EXTENSIONS = [
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
]

# * Map friendly model names to Hugging Face Hub repository IDs
WHISPER_HF_MODELS = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large": "openai/whisper-large",
    "large-v1": "openai/whisper-large",
    "large-v2": "openai/whisper-large-v2",
    "large-v3": "openai/whisper-large-v3",
}

# --- Main Command ---


@app.command()
def run(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", help="Input directory containing media files."),
    ] = INPUT_DIR,
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for transcriptions."),
    ] = OUTPUT_DIR,
    model_name: Annotated[
        str,
        typer.Option(
            "--model", help="Name of the Whisper model to use (e.g., 'large-v3')."
        ),
    ] = "large-v3",
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output format for the transcription. [all|srt|vtt|txt|json]",
        ),
    ] = "all",
    language: Annotated[
        str, typer.Option(help="Language spoken in the audio. (e.g., 'en', 'ru')")
    ] = "ru",
    overwrite: Annotated[
        bool, typer.Option(help="Overwrite existing transcription files.")
    ] = False,
    device: Annotated[
        str, typer.Option(help="Device to use for inference ('cpu' or 'cuda').")
    ] = "cuda",
):
    """
    Transcribe all supported media files in a directory using Whisper.
    """
    ensure_dir_exists(input_dir)
    ensure_dir_exists(output_dir)

    console.print(
        f"[*] Starting Whisper transcriber with model '{model_name}' on device '{device}'."
    )
    console.print(f"[*] Input: '{input_dir}', Output: '{output_dir}'")

    if device == "cuda" and not torch.cuda.is_available():
        console.print(
            "[red]! CUDA device selected, but it is not available. Aborting.[/red]"
        )
        raise typer.Exit(code=1)

    # * Resolve model name to a Hugging Face Hub repo ID
    repo_id = WHISPER_HF_MODELS.get(model_name.lower())
    if not repo_id:
        console.print(f"[red]! Invalid model name: '{model_name}'[/red]")
        console.print(f"  Available models: {', '.join(WHISPER_HF_MODELS.keys())}")
        raise typer.Exit(code=1)

    try:
        # * Download the model from Hugging Face Hub, which returns the local path
        model_path = download_hf_model(repo_id=repo_id)
        model = whisper.load_model(model_path, device=device)
        console.print(
            f"[*] Whisper model '{model_name}' loaded successfully from local path."
        )
    except Exception as e:
        console.print(f"[red]! Failed to load Whisper model: {e}[/red]")
        raise typer.Exit(code=1)

    files_to_process = sorted(
        [p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    )

    if not files_to_process:
        console.print("[yellow]! No supported media files found.[/yellow]")
        raise typer.Exit()

    console.print(f"[*] Found {len(files_to_process)} media file(s) to process.")

    progress_bar = tqdm(files_to_process, desc="Transcribing files", unit="file")
    for file_path in progress_bar:
        progress_bar.set_description(f"Processing {file_path.name}")

        # Check for existing files
        output_exists = False
        if not overwrite:
            # A simple check for the .txt file. A more robust check would consider all formats.
            if (output_dir / f"{file_path.stem}.txt").exists():
                output_exists = True

        if output_exists:
            console.print(
                f"[yellow]  -> Skipping (output exists and --overwrite is not set).[/yellow]"
            )
            continue

        try:
            # * The 'verbose=False' is recommended when using a progress bar like tqdm
            result = model.transcribe(
                str(file_path), language=language, verbose=False, temperature=0.25
            )

            writer = whisper.utils.get_writer(output_format, str(output_dir))
            writer(result, str(file_path.stem))

            console.print(
                f"\n  -> [green]✓ Transcription successful for {file_path.name}.[/green] Output format(s): {output_format}"
            )

        except Exception as e:
            console.print(
                f"\n  -> [red]✗ Error during transcription for {file_path.name}: {e}[/red]"
            )

    console.print("\n[green]✓ Transcription process completed.[/green]")


if __name__ == "__main__":
    setup_signal_handler()
    app()
