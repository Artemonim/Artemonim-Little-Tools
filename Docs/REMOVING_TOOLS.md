# How to Remove Tools from LittleTools

This guide explains how to remove existing tools from the LittleTools suite. The removal process always consists of two main steps:

1.  **Deregistering the tool:** Removing its entry from configuration files.
2.  **Deleting the source code:** Removing the files or code snippets that implement the tool.

---

## Step 1: Determine How the Tool is Integrated

Before deleting anything, you need to understand how the tool was added. Open `Docs/ADDING_NEW_TOOLS.md` and match your case with one of the scenarios:

-   **Scenario 1A: Simple command in an existing file.** A `@app.command()` function was added to a shared file like `video_converter.py`.
-   **Scenario 1B: Complex command in a new file.** A separate `.py` file was created within a package (like `ben2_remover.py`) and registered in that package's `pyproject.toml`.
-   **Scenario 2: An entire tool package.** A whole `littletools_themename` directory was created and added to `start.ps1`.

## Step 2: Perform Removal According to the Scenario

### Removing by Scenario 1A (Simple Command)

This is the easiest case.

1.  **Find the file:** Go to the package folder (e.g., `littletools_video/littletools_video/`) and open the file containing your command (e.g., `video_converter.py`).
2.  **Delete the code:** Find and completely remove the Python function that implements the command (the code block starting with `@app.command()`).

That's it! No other edits are required.

### Removing by Scenario 1B (Complex Command)

This requires one more step.

1.  **Deregister:** Open the `pyproject.toml` of the package containing the tool (e.g., `littletools_video/pyproject.toml`).
    -   Find the `[project.entry-points."littletools.commands"]` section and delete the line related to your tool.
    -   Find the `[project.scripts]` section and also delete the corresponding line from there.
    -   If specific dependencies were added for this tool in the `dependencies` section, remove them to avoid keeping unnecessary clutter.
2.  **Delete the file:** Delete the `.py` file with the tool's code (e.g., `littletools_video/littletools_video/my_watermark_tool.py`).
3.  **(Mandatory) Check and clean dependencies:** After deleting the code, be sure to check the `pyproject.toml` for "orphaned" dependencies. See the "Cleaning Up Unused Dependencies" section below.

After this, run `start.bat` or `start.ps1` for the changes to take effect.

### Removing by Scenario 2 (Entire Package)

This is the complete removal of an entire category of tools.

1.  **Deregister the package:**
    -   Open `start.ps1` in the project root.
    -   Find the `& $VenvPython -m pip install ...` line.
    -   Remove the flag for your package from this line (e.g., `-e ./littletools_archive`).
2.  **Delete the folder:** Completely delete your package directory (e.g., `littletools_archive`).
3.  **(Recommended) Clean the environment:** Delete the `.venv` folder and run `start.bat` or `start.ps1` to rebuild the environment from scratch.

---

## Cleaning Up Unused Dependencies (A Critically Important Step!)

After removing code from a package (especially under scenarios 1B and 2), you **MUST** check if any dependencies that are no longer used remain in `pyproject.toml`. **DO NOT REMOVE dependencies manually** - this can lead to errors.

### The Correct Process for Cleaning Dependencies:

1.  **Generate current dependencies:** Run the improved `requirementsBuilder.py` script from the project root:

    ```bash
    # Basic analysis (recommended to start)
    python requirementsBuilder.py <path-to-package-source>

    # Detailed analysis with file and line numbers of imports
    python requirementsBuilder.py <path-to-package-source> --detailed

    # Example:
    python requirementsBuilder.py littletools_video/littletools_video --detailed
    ```

    **Advantages of the improved builder:**

    -   ✅ Excludes standard Python libraries and local project packages
    -   ✅ Shows the files and lines where each dependency is used
    -   ✅ Finds missing dependencies (used but not listed in pyproject.toml)
    -   ✅ Provides clearly structured output with instructions

2.  **Compare the lists:**

    -   Analyze the output of `requirementsBuilder.py` - it lists the modules that are _actually_ imported in the code.
    -   Open your package's `pyproject.toml` and look at the `dependencies` list.
    -   **Special attention:** Some dependencies might be imported only inside functions or conditionally, so double-check with a grep search.

3.  **Make informed decisions:**

    -   ✅ **Safe to remove:** Dependencies that do not appear in the output of `requirementsBuilder.py` or in the grep search results.
    -   ⚠️ **Double-check:** Dependencies that are in `requirementsBuilder.py` but seem specific to the removed tool.
    -   ❌ **DO NOT remove:** Dependencies that are used by the remaining tools in the package.

4.  **Example Analysis:**

    ```
    requirementsBuilder.py showed: PIL, controlnet_aux, cv2, diffusers, numpy, realesrgan, rich, torch, torchvision, typer
    In pyproject.toml there are: Pillow, typer, tqdm, opencv-python, diffusers, transformers, torch, torchvision, accelerate, realesrgan, basicsr, xformers, controlnet-aux, compel, invisible-watermark

    Decisions:
    ✅ Add: rich (used, but missing from pyproject.toml)
    ✅ Remove: tqdm (not used in this package)
    ✅ Keep: all Stable Diffusion dependencies (used in stable_diffusion_stylizer.py)
    ```

> **! Critical Warning:** The `requirementsBuilder.py` script is not perfect and may not see some dynamic or conditional imports. Always double-check with a grep search and analyze the code manually before removing dependencies. It is better to leave an extra dependency than to break working code.

After following these steps, the tool will be completely removed from the project.
