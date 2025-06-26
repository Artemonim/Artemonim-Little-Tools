#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LittleTools Core - Hugging Face Hub Utilities

This module provides helper functions for interacting with the Hugging Face Hub,
such as downloading models and datasets.
"""

from pathlib import Path
import os
from huggingface_hub import snapshot_download
from rich.console import Console

console = Console()

# * Set a sensible cache directory within the project if not set globally
if "HF_HOME" not in os.environ:
    # Place it in the parent directory of the 'littletools_core' package folder
    project_root = Path(__file__).parent.parent.parent
    os.environ["HF_HOME"] = str(project_root / ".huggingface")


def download_hf_model(
    repo_id: str,
    cache_dir: str = None,
    allow_patterns: list[str] = None,
    ignore_patterns: list[str] = None,
    revision: str = "main",
) -> Path:
    """
    Downloads a model snapshot from the Hugging Face Hub.

    Args:
        repo_id: The ID of the repository (e.g., "openai/whisper-large-v3").
        cache_dir: The directory to cache the downloaded model.
                   Defaults to the HF_HOME environment variable.
        allow_patterns: A list of patterns to include in the download.
        ignore_patterns: A list of patterns to exclude from the download.
        revision: The specific model version to download.

    Returns:
        The local path to the downloaded model directory.

    Raises:
        Exception: If the download fails.
    """
    console.print(
        f"[*] Downloading model [cyan]'{repo_id}'[/cyan] from Hugging Face Hub..."
    )
    console.print(
        f"[*] This may take a while depending on model size and your connection."
    )
    console.print(
        f"[*] Files are cached locally in: [dim]{os.environ['HF_HOME']}[/dim]"
    )

    try:
        model_path = snapshot_download(
            repo_id=repo_id,
            cache_dir=cache_dir,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            revision=revision,
            # TODO: Add a progress bar. `huggingface_hub`'s is complex to pipe.
        )
        console.print(f"[green]✓ Model '{repo_id}' downloaded successfully.[/green]")
        return Path(model_path)
    except Exception as e:
        console.print(f"[red]! Failed to download model '{repo_id}': {e}[/red]")
        raise


__all__ = ["download_hf_model"]
