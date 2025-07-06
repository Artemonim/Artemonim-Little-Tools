# Artemonim's Little Tools

A cross-platform, modular and extensible suite of command-line utilities designed for various media, text, and AI-driven processing tasks. The project runs on Windows, Linux, and macOS, and is built with a plugin-based architecture, making it easy to add, remove, or develop new tools.

## Key Features

-   **Cross-Platform Interactive Launcher**: User-friendly setup scripts for all major platforms:
    -   **Windows**: PowerShell script (`start.ps1`)
    -   **Linux/macOS**: Bash script (`start.sh`)
    -   Both scripts provide identical functionality for setup, installation, updates, and launching the main CLI.
-   **Robust Dependency Management**: Utilizes `pip-tools` to compile a single `requirements.txt` lock file from all constituent packages. This prevents dependency conflicts and ensures a reproducible environment.
-   **Modular Architecture**: Tools are packaged as separate plugins (e.g., `littletools-video`, `littletools-txt`) and are automatically discovered by the main menu, thanks to Python's entry points.
-   **GPU Acceleration**: Automatically detects NVIDIA GPUs and installs the appropriate CUDA-enabled versions of PyTorch and xformers for performance-critical tasks.
-   **Self-Contained Caches**: All caches for `pip` and Hugging Face models are stored locally within the project directory (`.pip-cache`, `.huggingface`), keeping your system user profile clean.

## Prerequisites

-   **Python**: Version 3.11 is required. The setup script will look for it.
-   **Shell Environment**:
    -   **Windows**: PowerShell (the `start.ps1` script is the primary entry point)
    -   **Linux/macOS**: Bash (the `start.sh` script provides the same functionality)
-   **Modern NVIDIA GPU** for tools that leverage machine learning models

## Installation & Usage

1. **Clone the repository:**

    ```sh
    git clone https://github.com/Artemonim/Artemonim-Little-Tools
    cd LittleTools
    ```

2. **Run the launcher script:**

    **On Windows (PowerShell):**

    ```powershell
    ./start.ps1
    ```

    **On Linux/macOS (Terminal):**

    ```bash
    ./start.sh
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

## Support the Project

Artemonim's Little Tools is an independent open-source project. If you find this tool useful and want to support its ongoing development, your help would be greatly appreciated.

Here are a few ways you can contribute:

-   **Give a Star:** The simplest way to show your support is to star the project on [GitHub](https://github.com/Artemonim/Artemonim-Little-Tools)! It increases the project's visibility.
-   **Support My Work:** Your financial contribution helps me dedicate more time to improving this tool and creating other open-source projects. On my [**Boosty page**](https://boosty.to/artemonim), you can:
    -   Make a **one-time donation** to thank me for this specific project.
    -   Become a **monthly supporter** to help all of my creative endeavors.
-   **Try a Recommended Tool:** This project was inspired by my work with LLMs. If you're looking for a great service to work with multiple neural networks, check out [**Syntx AI**](https://t.me/syntxaibot?start=aff_157453205). Using my referral link is another way to support my work at no extra cost to you.

Thank you for your support!

## For Developers

The project is designed to be easily extensible.

-   **Project Structure**: The repository is a monorepo. Core functionality is in `littletools-core`, and the CLI menu is in `littletools-cli`. Each tool category resides in its own `littletools_*` package.
-   **Adding New Tools**: To add new functionality, you can either extend an existing package or create a new one. The system will automatically detect any new commands registered via entry points. For detailed instructions, see [ADDING_NEW_TOOLS.md](Docs/ADDING_NEW_TOOLS.md).
-   **Removing Tools**: To remove tools, you must deregister them from the relevant `pyproject.toml` and installer scripts. See [REMOVING_TOOLS.md](Docs/REMOVING_TOOLS.md) for the correct procedure.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
