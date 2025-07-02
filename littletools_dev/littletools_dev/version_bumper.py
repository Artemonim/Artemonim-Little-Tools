"""
LittleTools Version Bumper CLI.

* Displays current versions of all LittleTools sub-packages.
* Lets the user interactively bump selected packages (major/minor/patch).
* Updates `pyproject.toml` and corresponding `__init__.py` files.
* Applies global version bump following hybrid rules.

Requirements:
    - Python ≥ 3.11 (uses `tomllib`).
    - No external dependencies beyond *Typer* and *rich*, which are already
      part of the LittleTools dependency tree.

Usage:
    python -m littletools_dev.version_bumper list    # * Show versions
    python -m littletools_dev.version_bumper bump    # * Interactive bump
    python -m littletools_dev.version_bumper --help  # * CLI help

The script purposefully avoids the `bump-my-version` runtime dependency to
keep the toolchain minimal and Windows-friendly.
"""

from __future__ import annotations

# * Built-in Imports
import re
from enum import Enum
from pathlib import Path
from typing import Dict
from typing import Tuple

# * Third-party Imports (already in project requirements)
import typer
from rich.console import Console
from rich.table import Table

# * ---------------------------------------------------------------------------
# * Configuration
# * ---------------------------------------------------------------------------

# ? Adjust the relative paths only if the project layout changes.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# * Mapping of package names to their metadata paths.
# * Keep this in one place for easier maintenance.
PACKAGE_INDEX: Dict[str, Tuple[Path, Path]] = {
    # {pkg_name: (pyproject_path, init_file_path)}
    "littletools-cli": (
        PROJECT_ROOT / "littletools_cli" / "pyproject.toml",
        PROJECT_ROOT / "littletools_cli" / "littletools_cli" / "__init__.py",
    ),
    "littletools-core": (
        PROJECT_ROOT / "littletools_core" / "pyproject.toml",
        PROJECT_ROOT / "littletools_core" / "littletools_core" / "__init__.py",
    ),
    "littletools-speech": (
        PROJECT_ROOT / "littletools_speech" / "pyproject.toml",
        PROJECT_ROOT / "littletools_speech" / "littletools_speech" / "__init__.py",
    ),
    "littletools-txt": (
        PROJECT_ROOT / "littletools_txt" / "pyproject.toml",
        PROJECT_ROOT / "littletools_txt" / "littletools_txt" / "__init__.py",
    ),
    "littletools-video": (
        PROJECT_ROOT / "littletools_video" / "pyproject.toml",
        PROJECT_ROOT / "littletools_video" / "littletools_video" / "__init__.py",
    ),
    "littletools-dev": (
        PROJECT_ROOT / "littletools_dev" / "pyproject.toml",
        PROJECT_ROOT / "littletools_dev" / "littletools_dev" / "__init__.py",
    ),
}

# * Root-level global version location.
ROOT_PYPROJECT: Path = PROJECT_ROOT / "pyproject.toml"

# * ---------------------------------------------------------------------------
# * Helper Enums & Functions
# * ---------------------------------------------------------------------------


class BumpScope(str, Enum):
    """Enumeration of possible version bump types."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"

    # * Priority order used when propagating to the global version.
    def precedence(self) -> int:  # noqa: D401 (simple verb phrase)
        """Return precedence value (higher means more significant)."""
        return {self.MAJOR: 3, self.MINOR: 2, self.PATCH: 1}[self]


VERSION_RE = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)")


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse *SemVer* string into integer components."""
    match = VERSION_RE.fullmatch(version_str.strip())
    if match is None:
        raise ValueError(f"Invalid version string: '{version_str}'")
    return tuple(int(match.group(part)) for part in ("major", "minor", "patch"))  # type: ignore[return-value]


def bump_version(version_str: str, scope: BumpScope) -> str:  # noqa: D401
    """Return a new version bumped according to *scope*."""
    major, minor, patch = parse_version(version_str)
    if scope is BumpScope.MAJOR:
        return f"{major + 1}.0.0"
    if scope is BumpScope.MINOR:
        return f"{major}.{minor + 1}.0"
    # * PATCH
    return f"{major}.{minor}.{patch + 1}"


# * ---------------------------------------------------------------------------
# * Low-level file utilities (no TOML dump dependency)                         *
# * ---------------------------------------------------------------------------

PROJECT_VERSION_LINE_RE = re.compile(
    r"^version\s*=\s*\"(?P<version>[^\"]+)\"", re.MULTILINE
)
INIT_VERSION_LINE_RE = re.compile(
    r"^__version__\s*=\s*\"(?P<version>[^\"]+)\"", re.MULTILINE
)


def read_version_from_pyproject(pyproject_path: Path) -> str:
    """Return current version declared in *pyproject.toml*."""
    text = pyproject_path.read_text(encoding="utf-8")
    match = PROJECT_VERSION_LINE_RE.search(text)
    if match is None:
        raise RuntimeError(f"Version line not found in {pyproject_path}")
    return match.group("version")


def replace_version_in_file(
    path: Path, pattern: re.Pattern[str], new_version: str
) -> None:
    """Replace version line matching *pattern* with *new_version* inside *path*."""
    text = path.read_text(encoding="utf-8")
    if pattern.search(text) is None:
        # * Insert a new version line at the top if none exists.
        new_line = f'__version__ = "{new_version}"\n'
        text = new_line + text
    else:
        text = pattern.sub(
            lambda m: m.group(0).split("=")[0] + f'= "{new_version}"', text, count=1
        )
    path.write_text(text, encoding="utf-8")


def update_package_version(
    pyproject_path: Path, init_path: Path, new_version: str
) -> None:
    """Update *pyproject.toml* and *__init__.py* with *new_version*."""
    # * Update pyproject
    text = pyproject_path.read_text(encoding="utf-8")
    text = PROJECT_VERSION_LINE_RE.sub(f'version = "{new_version}"', text, count=1)
    pyproject_path.write_text(text, encoding="utf-8")

    # * Update __init__.py
    replace_version_in_file(init_path, INIT_VERSION_LINE_RE, new_version)


# * ---------------------------------------------------------------------------
# * CLI – powered by Typer                                                      *
# * ---------------------------------------------------------------------------

app = typer.Typer(
    add_completion=False,
    help="""Interactively bump LittleTools package versions.""",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main(ctx: typer.Context):
    """
    Display the bump menu if no subcommand is invoked.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(bump)


@app.command("list")
def show_versions() -> None:  # noqa: D401 (simple verb phrase)
    """Print a table of current package versions."""
    table = Table(title="LittleTools Package Versions")
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Package")
    table.add_column("Version", style="green")
    for idx, (pkg, (pyproject_path, _)) in enumerate(PACKAGE_INDEX.items(), start=1):
        version = read_version_from_pyproject(pyproject_path)
        table.add_row(str(idx), pkg, version)
    # * Global version
    global_version = get_global_version()
    table.add_row(
        "-", "[b]GLOBAL[/b]", f"[bright_yellow]{global_version}[/bright_yellow]"
    )
    console.print(table)


@app.command()
def bump() -> None:  # noqa: D401 (simple verb phrase)
    """Interactive version bump menu."""
    # * Show current versions first
    show_versions()

    # * Prompt user for packages
    selection = typer.prompt(
        "Enter package indexes to bump (comma-separated) or 'all'",
        default="all",
    )
    if selection.strip().lower() == "all":
        chosen_keys: list[str] = list(PACKAGE_INDEX.keys())
    else:
        try:
            idxs = [int(item) for item in re.split(r"[ ,]+", selection.strip()) if item]
        except ValueError as exc:
            typer.echo(f"Invalid index value: {exc}")
            raise typer.Exit(code=1)
        chosen_keys = []
        for i in idxs:
            try:
                chosen_keys.append(list(PACKAGE_INDEX.keys())[i - 1])
            except IndexError:
                typer.echo(f"Index {i} is out of range.")
                raise typer.Exit(code=1)

    # * Collect desired bump scope for each chosen package
    bump_decisions: Dict[str, BumpScope] = {}
    for pkg in chosen_keys:
        scope_str = typer.prompt(
            f"Select bump type for [bold]{pkg}[/bold] (major/minor/patch)",
            default="patch",
        ).lower()
        try:
            scope = BumpScope(scope_str)
        except ValueError:
            typer.echo("Please enter 'major', 'minor', or 'patch'.")
            raise typer.Exit(code=1)
        bump_decisions[pkg] = scope

    # * Execute bumps
    highest_scope: BumpScope | None = None
    for pkg, scope in bump_decisions.items():
        pyproject_path, init_path = PACKAGE_INDEX[pkg]
        current_version = read_version_from_pyproject(pyproject_path)
        new_version = bump_version(current_version, scope)
        update_package_version(pyproject_path, init_path, new_version)
        typer.echo(f"[UPDATED] {pkg}: {current_version} -> {new_version}")

        # * Track highest scope
        if highest_scope is None or scope.precedence() > highest_scope.precedence():
            highest_scope = scope

    # * Bump global version accordingly
    if highest_scope is not None:
        bump_global_version(highest_scope)
        typer.echo("Global version updated.")

    typer.echo("\nDone! New versions:")
    show_versions()


# * ---------------------------------------------------------------------------
# * Global version helpers                                                     *
# * ---------------------------------------------------------------------------


def get_global_version() -> str:
    """Return global LittleTools version defined in root `pyproject.toml`."""
    content = ROOT_PYPROJECT.read_text(encoding="utf-8")
    match = re.search(
        r"^version\s*=\s*\"(?P<ver>[^\"]+)\"", content, flags=re.MULTILINE
    )
    if match:
        return match.group("ver")
    # * Fallback to custom section
    m2 = re.search(
        r"^\[tool.littletools\][^\n]*\nversion\s*=\s*\"(?P<ver>[^\"]+)\"",
        content,
        flags=re.MULTILINE,
    )
    if m2:
        return m2.group("ver")
    raise RuntimeError("Global version not found in root pyproject.toml")


def bump_global_version(scope: BumpScope) -> None:
    """Apply *scope* bump to global version in root `pyproject.toml`."""
    current = get_global_version()
    new_version = bump_version(current, scope)
    text = ROOT_PYPROJECT.read_text(encoding="utf-8")
    if "[tool.littletools]" not in text:
        # * Append section if missing.
        text += f'\n[tool.littletools]\nversion = "{new_version}"\n'
    else:
        text = re.sub(
            r"([\n\r]version\s*=\s*)\"[^\"]+\"",
            lambda m: m.group(1) + f'"{new_version}"',
            text,
            count=1,
        )
    ROOT_PYPROJECT.write_text(text, encoding="utf-8")


# * ---------------------------------------------------------------------------
# * Entrypoint                                                                 *
# * ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
