from __future__ import annotations

# * Public CLI surface
from .nvenc_benchmark import app as app  # re-export Typer app


def nvenc_main() -> None:
    """Entry point for console script."""
    app()





