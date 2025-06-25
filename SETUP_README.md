# LittleTools Setup Guide

This guide explains how to set up and run LittleTools on your system.

## Quick Start

1. **Clone or download** this repository to your local machine
2. **Run the setup script:**
    - On Windows: Double-click `start.bat` or run `start.ps1` in PowerShell
    - The script will automatically detect your system and install everything needed

## System Requirements

-   **Python 3.11** (the script will help you install it if missing)
-   **Windows** (primary support), Linux/macOS (experimental)
-   **For GPU-accelerated tools (like ben2-remover):**
    -   NVIDIA GPU with CUDA support
    -   NVIDIA drivers installed
    -   The setup script automatically detects NVIDIA GPUs and installs PyTorch with CUDA support

## What the Setup Script Does

The `start.ps1` script automatically:

1. **Detects Python 3.11** and guides installation if missing
2. **Creates a virtual environment** to isolate dependencies
3. **Detects NVIDIA GPU** presence using `nvidia-smi`
4. **Installs PyTorch:**
    - **With CUDA 12.1 support** if NVIDIA GPU is detected
    - **CPU-only version** as fallback if no GPU is found
5. **Installs all LittleTools packages** and their dependencies
6. **Verifies installation** and shows CUDA availability status

## GPU Support Information

-   **ben2-remover** requires a CUDA-capable NVIDIA GPU for background removal
-   **Other tools** work on both CPU and GPU systems
-   The setup script automatically installs the appropriate PyTorch version
-   If you have an NVIDIA GPU but CUDA isn't working, check:
    -   NVIDIA drivers are up to date
    -   Windows recognizes your GPU (`nvidia-smi` command works)

## Manual Setup (Advanced Users)

If you prefer manual installation:

```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install PyTorch with CUDA (if you have NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install LittleTools packages
pip install -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video
```

## Troubleshooting

### "CUDA device is not available" Error

-   Ensure you have an NVIDIA GPU
-   Update NVIDIA drivers
-   Run the setup script again to reinstall PyTorch with CUDA support

### Python Version Issues

-   The script requires Python 3.11 specifically
-   Use `py -3.11` if you have multiple Python versions

### Permission Issues

-   Run PowerShell as Administrator if needed
-   Check Windows execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## Getting Help

If you encounter issues:

1. Check the console output for specific error messages
2. Ensure all system requirements are met
3. Try the "Force Reinstall" option in the setup menu
4. Create an issue in the repository with your error logs

## Directory Structure

After setup, your directory should look like:

```
LittleTools/
├── .venv/                 # Virtual environment
├── 0-INPUT-0/            # Place input files here
├── 0-OUTPUT-0/           # Processed files appear here
├── Audio-_Video-2-Text/  # Whisper transcriber
│   ├── models/           # Downloaded Whisper models
│   └── whisper_transcriber.py
├── TxtTools/             # Text processing tools
├── VideoTools/           # Video processing tools
├── little_tools_utils.py # Common utilities for all tools
├── requirements.txt      # Core dependencies
├── start.ps1             # Windows setup script
├── start.bat             # Windows batch wrapper
└── menu.py               # Main menu system
```

## Architecture Changes

LittleTools now uses a unified architecture:

-   **Centralized Dependencies**: All tool dependencies are managed in `menu.py`
-   **Common Utilities**: Shared functionality in `little_tools_utils.py`
-   **Safe File Operations**: Files are moved to recycle bin instead of permanent deletion
-   **Cross-platform Compatibility**: Improved support for Windows, macOS, and Linux

## Getting Help

1. **Check the tool-specific README** in each subdirectory
2. **Run with help flag**: `python tool_name.py --help`
3. **Check the main README.md** for tool descriptions
4. **Contact**: [t.me/Artemonim](https://t.me/Artemonim) or Artemonim@yandex.ru
