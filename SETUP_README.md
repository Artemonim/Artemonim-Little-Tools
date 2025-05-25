# LittleTools Setup Guide

This guide helps you set up the LittleTools environment for optimal performance and ease of use.

## Quick Start (Recommended)

### Windows Users

1. **Download/Clone** the LittleTools repository
2. **Open PowerShell** in the LittleTools directory
3. **Run the setup script**:

    ```powershell
    .\start.ps1
    ```

    Or if you prefer batch files:

    ```cmd
    start.bat
    ```

The setup script will automatically:

-   ✅ Check Python 3.8+ installation
-   ✅ Create virtual environment with proper pip setup
-   ✅ Handle common environment issues
-   ✅ Launch the interactive menu

### Manual Setup (All Platforms)

If the automatic setup doesn't work or you prefer manual control:

```bash
# 1. Ensure Python 3.8+ is installed
python --version

# 2. Create virtual environment
python -m venv .venv --upgrade-deps

# 3. Run the menu
python menu.py
```

## Troubleshooting

### "Python not found"

-   Install Python 3.8+ from [python.org](https://python.org)
-   Ensure Python is added to your system PATH
-   Restart your terminal after installation

### "pip not found in virtual environment"

The new setup scripts handle this automatically. If using manual setup:

```bash
# Delete existing .venv and recreate
rm -rf .venv  # or rmdir /s .venv on Windows
python -m venv .venv --upgrade-deps

# Or bootstrap pip manually
.venv/Scripts/python -m ensurepip --upgrade  # Windows
.venv/bin/python -m ensurepip --upgrade      # Linux/macOS
```

### "Permission denied" or "Execution policy" errors (Windows)

Run PowerShell as Administrator and execute:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "FFmpeg not found" (for video tools)

Install FFmpeg system-wide:

-   **Windows**: `winget install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org)
-   **macOS**: `brew install ffmpeg`
-   **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian)

## Advanced Options

### Force Recreation of Environment

If you encounter persistent issues:

```powershell
.\start.ps1 -Force
```

### Manual Dependency Installation

```bash
# Activate virtual environment first
.venv/Scripts/activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install specific tool dependencies
pip install -r requirements_whisper_transcriber.txt
pip install -r requirements_infinite_differ.txt
# etc.
```

## System Requirements

### Minimum

-   Python 3.8+
-   2GB RAM
-   1GB free disk space

### Recommended for Whisper Transcriber

-   Python 3.9+
-   8GB RAM
-   CUDA-compatible GPU
-   FFmpeg installed system-wide
-   5GB free disk space (for models)

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
├── start.ps1             # Windows setup script
├── start.bat             # Windows batch wrapper
└── menu.py               # Main menu system
```

## Getting Help

1. **Check the tool-specific README** in each subdirectory
2. **Run with help flag**: `python tool_name.py --help`
3. **Check the main README.md** for tool descriptions
4. **Contact**: [t.me/Artemonim](https://t.me/Artemonim) or Artemonim@yandex.ru
