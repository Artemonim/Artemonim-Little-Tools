#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word <-> Markdown Converter Tool

A Typer-based CLI tool to convert files between .docx and .md formats using pandoc.
This script is designed to be a plugin for the 'littletools-cli'.
"""

from pathlib import Path

import pypandoc
import typer
from rich.console import Console
from typing import Optional
from typing_extensions import Annotated

from littletools_core.utils import ensure_dir_exists, setup_signal_handler

app = typer.Typer(
    name="wmd-converter",
    help="Convert between .docx and .md formats using pandoc.",
    no_args_is_help=True,
)
console = Console()

OUTPUT_DIR = Path.cwd() / "0-OUTPUT-0"


def do_conversion(input_path: Path, output_path: Path, media_dir: Path):
    """Performs the pandoc conversion."""
    try:
        ensure_dir_exists(output_path.parent)
        ensure_dir_exists(media_dir)

        # Determine conversion direction
        from_format = 'docx' if input_path.suffix.lower() == '.docx' else 'markdown'
        to_format = 'markdown' if from_format == 'docx' else 'docx'

        extra_args = [
            '--extract-media', str(media_dir),
            '--standalone'
        ]

        console.print(f"[*] Converting '{input_path.name}' ({from_format}) -> '{output_path.name}' ({to_format})...")
        pypandoc.convert_file(
            str(input_path),
            to_format,
            outputfile=str(output_path),
            extra_args=extra_args
        )
        console.print(f"[green]✓ Conversion successful.[/green] Media saved to '{media_dir.name}'.")

    except Exception as e:
        console.print(f"[red]! An error occurred during conversion: {e}[/red]")
        console.print("[yellow]  Please ensure 'pandoc' is installed and in your system's PATH.[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def run(
    source: Annotated[Path, typer.Option("--source", "-s", help="Source file (.docx or .md) to convert.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Path for the output file.")],
    media_dir: Annotated[Optional[Path], typer.Option(help="Directory to store extracted media. [default: <output_dir>/<source_stem>_media]")] = None,
):
    """
    Converts a single file from .docx to .md or vice-versa.
    """
    if not source.exists():
        console.print(f"[red]! Source file not found: {source}[/red]")
        raise typer.Exit(code=1)

    if media_dir is None:
        media_dir = output.parent / f"{source.stem}_media"

    do_conversion(source, output, media_dir)


if __name__ == "__main__":
    setup_signal_handler()
    app()