# LittleTools

A modular and extensible suite of command-line utilities designed for various media, text, and AI-driven processing tasks. The project is built with a plugin-based architecture, making it easy to add, remove, or develop new tools.

## Key Features

-   **Interactive Launcher**: A user-friendly PowerShell script (`start.ps1`) simplifies setup, installation, updates, and launching the main CLI.
-   **Robust Dependency Management**: Utilizes `pip-tools` to compile a single `requirements.txt` lock file from all constituent packages. This prevents dependency conflicts and ensures a reproducible environment.
-   **Modular Architecture**: Tools are packaged as separate plugins (e.g., `littletools-video`, `littletools-txt`) and are automatically discovered by the main menu, thanks to Python's entry points.
-   **GPU Acceleration**: Automatically detects NVIDIA GPUs and installs the appropriate CUDA-enabled versions of PyTorch and xformers for performance-critical tasks.
-   **Self-Contained Caches**: All caches for `pip` and Hugging Face models are stored locally within the project directory (`.pip-cache`, `.huggingface`), keeping your system user profile clean.

## Prerequisites

-   **Python**: Version 3.11 is required. The setup script will look for it.
-   **PowerShell**: The `start.ps1` script is the primary entry point.
-   **NVIDIA GPU (Optional)**: For tools that leverage machine learning models (like Stable Diffusion or Whisper), an NVIDIA GPU with up-to-date drivers is highly recommended for acceptable performance. The installer will fall back to CPU-only packages if a GPU is not detected.

## Installation & Usage

1. **Clone the repository:**

    ```sh
    git clone https://github.com/Artemonim/Artemonim-Little-Tools
    cd LittleTools
    ```

2. **Run the launcher script:**
   Open a PowerShell terminal and run:

    ```powershell
    ./start.ps1
    ```

    This will present the main setup menu:

    ```
    === LittleTools Setup & Launcher (Python 3.11) ===
     [1] Install or Update All Tools
     [2] Force Reinstall All Tools (Clean Slate)
     [3] Uninstall (Remove Environment)
     [4] Launch LittleTools Menu
     [5] Cache Management
     [0] Exit
    ```

3. **Install Tools:**

    - Select option **[1] Install or Update All Tools**.
    - The script will:
        1. Find your Python 3.11 installation.
        2. Create a virtual environment (`.venv`) inside the project folder.
        3. Gather all `littletools_*` packages.
        4. Resolve all dependencies using `pip-tools` and create a `requirements.txt` lock file.
        5. Install all packages and dependencies into the virtual environment using `pip-sync`.

4. **Launch the CLI:**
    - After installation, select option **[4] Launch LittleTools Menu**.
    - This starts the interactive CLI where you can select and run tools.

## Available Tools

The following tool packages are currently available and will be automatically discovered by the menu.

### Video Tools (`littletools-video`)

-   `video-converter`: Convert videos to different formats and codecs.
-   `audio-normalizer`: Normalize audio tracks in video files to a standard loudness.
-   `video-compiler`: Merge video files with audio/subtitles (works with any video files, not just Topaz-processed).
-   `image-audio-to-video`: Create a video from a static image and an audio file.
-   `video-stylizer`: Apply AI-driven stylization to videos using Stable Diffusion.

### Text Tools (`littletools-txt`)

-   `cyrillic-remover`: Remove Cyrillic characters from text files.
-   `telegram-distiller`: Process and distill Telegram chat exports.
-   `syntx-downloader`: A tool for downloading from Syntx.
-   `wmd-converter`: A converter for WMD files.

### Speech Tools (`littletools-speech`)

-   `whisper-transcriber`: Transcribe audio files to text using OpenAI's Whisper model.

## For Developers

The project is designed to be easily extensible.

-   **Project Structure**: The repository is a monorepo. Core functionality is in `littletools-core`, and the CLI menu is in `littletools-cli`. Each tool category resides in its own `littletools_*` package.
-   **Adding New Tools**: To add new functionality, you can either extend an existing package or create a new one. The system will automatically detect any new commands registered via entry points. For detailed instructions, see [ADDING_NEW_TOOLS.md](Docs/ADDING_NEW_TOOLS.md).
-   **Removing Tools**: To remove tools, you must deregister them from the relevant `pyproject.toml` and installer scripts. See [REMOVING_TOOLS.md](Docs/REMOVING_TOOLS.md) for the correct procedure.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
