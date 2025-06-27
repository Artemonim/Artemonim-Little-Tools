# How to Add Tools to LittleTools

This guide explains how to add new tools to the LittleTools suite. The project is designed so that the main interactive menu (`lt`) automatically discovers and loads any correctly configured tool packages.

## Core Concept: Extending or Creating Packages

Each "tool" (e.g., `video-converter`) is part of a thematic Python package (e.g., `littletools_video`).

Your main task when adding new functionality is to decide:

1.  **Extend an existing package?** If your new function is closely related to video, text, audio, etc., you should add it to the corresponding package (`littletools_video`, `littletools_txt`, `littletools_speech`). This is the preferred method as it promotes code reuse.
2.  **Create a new package?** If your function represents a completely new category of tools (e.g., working with archives or images), then a new package should be created.

In both cases, it is important to actively use the common utilities from `littletools-core` to avoid code duplication.

---

## Recommendation: Loading ML Models via Hugging Face Hub

To ensure consistency and simplify the management of machine learning models (e.g., Whisper, BERT, etc.), it is highly recommended to download them from the [Hugging Face Hub](https://huggingface.co/).

A dedicated utility is provided in `littletools-core` for this purpose.

**Example Usage:**

```python
# ! bad-practice
# model = whisper.load_model("large-v3") # Direct download, can be unstable

# * good-practice
from littletools_core.huggingface_utils import download_hf_model

# 1. Define the model repository ID on Hugging Face Hub
repo_id = "openai/whisper-large-v3"

# 2. Download the model using the utility
# The utility caches the model locally in the .huggingface folder in the project root
model_path = download_hf_model(repo_id=repo_id)

# 3. Load the model from the local path
model = whisper.load_model(model_path, device="cuda")
```

This approach provides:

-   **Caching:** Models are downloaded once and stored locally.
-   **Centralized Management:** All models go through a single mechanism.
-   **Reliability:** Less dependence on direct API calls from specific libraries for downloading.

---

## Method 1: Adding a New Command to an Existing Package (Preferred)

This is the most common scenario. Let's say we want to add a new command to the `littletools_video` package. Depending on the command's complexity, there are two approaches.

### Step 1: Choose an Approach

-   **1A: Simple Command.** If your command is one or two simple functions, it's better to add it to the package's existing main file (e.g., `video_converter.py`).
-   **1B: Complex Command.** If your tool is a self-contained program with its own logic, multiple functions, and possibly specific dependencies (like `ben2-remover`), it's better to create a separate `.py` file for it within the package.

---

### Approach 1A: Simple Command (in an existing file)

This is the fastest method.

1.  **Find the target file:** Go to the package folder, e.g., `littletools_video/littletools_video/`, and find the file containing the main `typer.Typer` object. It's usually named after the main tool, like `video_converter.py`.

2.  **Add your command:** Open this file and add a new function wrapped in the `@app.command()` decorator.

```python
// ... existing code ...
from rich.console import Console
from typing_extensions import Annotated

# * The main Typer application for this package should already be defined
# app = typer.Typer(...)

console = Console()

// ... existing commands ...

@app.command()
def add_watermark(
    input_video: Annotated[Path, typer.Argument(help="Source video file.")],
    watermark_image: Annotated[Path, typer.Argument(help="Image file for the watermark.")],
    output_video: Annotated[Path, typer.Option("--output", "-o", help="Path for the final video.")]
):
    """
    Overlays a watermark image onto a video.
    """
    console.print(f"Applying watermark [cyan]{watermark_image}[/cyan] to [cyan]{input_video}[/cyan]...")

    # ? Use common functions from this same package if they exist
    # ? For example, from ffmpeg_utils.py
    #
    # ? Also, use utilities from littletools_core
    # from littletools_core.utils import some_helper_function

    # TODO: Your actual logic using FFMPEG should be here.

    console.print(f"[green]✓ Video saved to [bold]{output_video}[/bold]![/green]")

if __name__ == "__main__":
    app()
```

3.  **Done!** Since the package is already registered in the system, you don't need to do anything else. The new command will automatically appear in the menu.

---

### Approach 1B: Complex Command (in a new file)

This approach keeps the code clean by isolating complex logic.

1.  **Create the tool file:** Inside the package's source code folder (e.g., `littletools_video/littletools_video/`), create a new Python file, for instance, `my_watermark_tool.py`.

2.  **Write the tool's code:** In this new file, create a complete Typer application. The code will be very similar to creating a new package, but the file will be located inside an existing one.

    ```python
    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-
    from pathlib import Path
    import typer
    from rich.console import Console
    from typing_extensions import Annotated

    # * This 'app' object is what we will reference in pyproject.toml
    app = typer.Typer(no_args_is_help=True)
    console = Console()

    @app.command()
    def apply(
        # ... your function arguments ...
    ):
        """Applies a watermark."""
        # TODO: Your command logic
        console.print("[green]✓ Done![/green]")

    if __name__ == "__main__":
        app()
    ```

3.  **Register the command:** Open the `pyproject.toml` file of the parent package (in our example, `littletools_video/pyproject.toml`). You need to add a reference to your new tool in two places:

    -   `[project.scripts]`: Allows running the script directly from the command line.
    -   `[project.entry-points."littletools.commands"]`: Registers the command in the main `lt` menu.

    ```toml
    # littletools_video/pyproject.toml

    # ... other sections ...

    [project.scripts]
    # ... existing scripts ...
    watermarker = "littletools_video.my_watermark_tool:app"

    [project.entry-points."littletools.commands"]
    # ... existing commands ...
    watermarker = "littletools_video.my_watermark_tool:app"

    # ...
    ```

4.  **Check dependencies (if necessary):** If you added new imports to the `dependencies` section of `pyproject.toml`, verify their correctness:

    ```bash
    python requirementsBuilder.py littletools_video/littletools_video
    ```

5.  **Done!** Run `start.bat` or `start.ps1`. Since you modified `pyproject.toml`, the installer will re-register your package, and the new command will appear in the menu. You **do not need** to edit `start.ps1`, as the parent package `littletools_video` is already included in the installation.

---

## Method 2: Creating a New Thematic Tool Package

Use this method only if your new functionality does not fit into any of the existing packages.

Let's say we want to create a new tool called `archive` for working with ZIP files.

### Step 1: Create the Package Structure

1.  In the `LittleTools` project root, create a new folder for your package. The naming convention is `littletools_themename`.

    ```
    /littletools_archive
    ```

2.  Inside this folder, create another folder with the same name. This is where your Python code will reside. Also, create an empty `__init__.py` file inside it.
    ```
    /littletools_archive
        /littletools_archive
            __init__.py
    ```

### Step 2: Create the `pyproject.toml` File

This is the most important file for integration. Create a file named `pyproject.toml` in the top-level `littletools_archive` folder.

```
/littletools_archive
    pyproject.toml  <-- CREATE THIS FILE
    /littletools_archive
```

Copy and paste this template into your `pyproject.toml` and modify the highlighted sections:

    ```toml
    [build-system]
    requires = ["setuptools>=61.0"]
    build-backend = "setuptools.build_meta"

    [project]
    # --- 1. CHANGE THIS ---
    name = "littletools-archive"
    version = "0.1.0"
    description = "A tool for working with archives."
    # --------------------

    dependencies = [
        "littletools-core", # ! Important dependency on core utilities
        "typer[all]>=0.9.0",
        "rich>=13.0.0", # ! Required for console.print() and rich output
        # Add any other dependencies your tool needs, e.g., "zipfile36"
    ]
    requires-python = ">=3.8"

# --- 2. THIS IS THE MAGIC ---

# This section tells the main menu that this package provides a command.

[project.entry-points."littletools.commands"]

# `archive` is the name that will appear in the menu.

# `littletools_archive.main:app` points to the `app` object in the `main.py` file.

archive = "littletools_archive.main:app"

# --------------------------

[tool.setuptools.packages.find]
where = ["."]

```

### Step 3: Write the Tool's Code

Now, create the Python file containing your tool's logic. According to our `pyproject.toml`, this file should be named `main.py`.

```

/littletools_archive
/littletools_archive
**init**.py
main.py <-- CREATE THIS FILE

````

Here is a simple template for `main.py` using `typer` and "Better Comments" style:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Archiving tool - part of the LittleTools suite.
"""
from pathlib import Path
import typer
from rich.console import Console
from typing_extensions import Annotated

# * Create a Typer app for this specific tool.
# * This 'app' object is what the entry point in pyproject.toml refers to.
app = typer.Typer(
    name="archive",
    help="A tool for creating and extracting ZIP archives.",
    no_args_is_help=True
)

console = Console()

@app.command()
def create(
    archive_path: Annotated[Path, typer.Option("--output", "-o", help="Path for the new ZIP file.")],
    files_to_add: Annotated[list[Path], typer.Argument(help="Files or folders to add to the archive.")]
):
    """
    Creates a new ZIP archive from the specified files and folders.
    """
    console.print(f"Creating archive: [cyan]{archive_path}[/cyan]")
    for file in files_to_add:
        console.print(f"  -> Adding [yellow]{file}[/yellow]...")

    # TODO: Your actual archiving logic should be here.

    console.print("[green]✓ Archive created successfully![/green]")

@app.command()
def extract(
    archive_path: Annotated[Path, typer.Argument(help="ZIP file to extract.")],
    destination: Annotated[Path, typer.Option("--output", "-o", help="Folder to extract files to.")]
):
    """
    Extracts a ZIP archive to a destination folder.
    """
    console.print(f"Extracting [cyan]{archive_path}[/cyan] to [cyan]{destination}[/cyan]...")

    # TODO: Your actual extraction logic should be here.

    console.print("[green]✓ Archive extracted successfully![/green]")

if __name__ == "__main__":
    app()
````

### Step 4: Add the Tool to the Installer

The final step is to tell the main installation script to install your new package.

1.  Open `start.ps1`.
2.  Find the line that starts with `& $VenvPython -m pip install ...`.
3.  Add `-e ./littletools_archive` to the end of this line. It should look like this:

    ```powershell
    # Was
    & $VenvPython -m pip install -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video

    # Becomes
    & $VenvPython -m pip install -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video -e ./littletools_archive
    ```

### Step 5: Check Dependencies (Recommended)

Before the final installation, it's recommended to verify the correctness of your dependencies using the built-in analyzer:

```bash
# Check which dependencies are actually used in your code
python requirementsBuilder.py littletools_archive/littletools_archive

# For a detailed analysis with files and line numbers
python requirementsBuilder.py littletools_archive/littletools_archive --detailed
```

**Analyze the results:**

-   ✅ **All dependencies from the output should be in `pyproject.toml`**
-   ❌ **Dependencies in `pyproject.toml` but NOT in the output = potentially redundant**
-   ⚠️ **Dependencies in the output but NOT in `pyproject.toml` = missing (add them)**

**Typical dependencies for LittleTools:**

-   `typer[all]>=0.9.0` - always needed for the CLI
-   `rich>=13.0.0` - always needed for `console.print()`
-   `littletools-core` - always needed for common utilities

### Step 6: Run the Installer

That's it! Now just run `start.bat` or `start.ps1` from the project root. The script will find your new `littletools_archive` package, install it, and when the interactive menu launches, you will see "**archive**" as a new, fully functional option.
