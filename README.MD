# Artemonim's Little Tools

[Описания и инструкция на русском...](Docs/ПРОЧТИМЕНЯ.MD)

A collection of small utility tools created for [personal commercial and non-commercial needs](/LICENSE). These tools aim to solve specific problems efficiently and can be used across different environments.

## 🚀 Quick Setup

For easy environment management and automated file processing, use our setup scripts:

**Windows (Recommended):**

```powershell
.\start.ps1
```

**Windows (Alternative):**

```cmd
start.bat
```

**Manual (All platforms):**

```bash
python menu.py
```

The startup scripts will:

-   ✅ Check Python 3.8+ installation
-   ✅ Create/verify virtual environment with pip
-   ✅ Handle common environment issues automatically
-   ✅ Launch the interactive menu

**Features:**

-   📁 Automatic file processing (`0-INPUT-0` → `0-OUTPUT-0`)
-   🔧 Single virtual environment for all tools
-   📦 Install only the dependencies you need
-   🚀 Batch processing for multiple files
-   🧹 Safe file deletion (moves to recycle bin/trash)
-   🎤 Audio/Video transcription with OpenAI Whisper
-   🛠️ Unified common utilities for all tools

## 🛠️ Available Tools

### Audio/Video Tools

-   [Whisper Audio/Video Transcriber](#whisper-audiovideo-transcriber)
-   [Image+Audio → Video Creator](#imageaudio-%E2%86%92-video-creator)

### Text Tools

-   [Telegram Chats Distiller](#telegram-chats-distiller)
-   [Infinite Differ (Multiple Text Comparator)](#infinite-differ)
-   [Word-Markdown Converter](#word-markdown-converter)

### Video Tools

-   [FFMPEG MKV Audio Normalizer](#ffmpeg-mkv-audio-normalizer)
-   [Topaz Video Merger](#topaz-video-merger)
-   [Video Converter](#video-converter)

### Utility Tools

-   [Requirements Builder](#requirements-builder)

## 🏗️ Architecture

LittleTools uses a unified architecture with shared utilities:

-   **`little_tools_utils.py`**: Common functionality for all tools

    -   Signal handling for graceful interruption (Ctrl+C)
    -   Safe file deletion (recycle bin/trash)
    -   Cross-platform compatibility helpers
    -   Console output formatting
    -   File and directory operations

-   **`menu.py`**: Central management system

    -   Interactive tool selection
    -   Dependency management
    -   Batch processing coordination
    -   Configuration management

-   **Individual tools**: Focused on their specific functionality while leveraging shared utilities

See [SETUP_README.md](SETUP_README.md) for detailed setup instructions.

## Audio/Video Tools

### Whisper Audio/Video Transcriber

Transcribes audio and video files using OpenAI's Whisper model with GPU acceleration support.

**Features:**

-   Supports multiple audio formats (MP3, WAV, M4A, AAC, OGG, FLAC)
-   Supports multiple video formats (MP4, MKV, MOV, AVI, WebM)
-   GPU acceleration for faster processing (CUDA)
-   Automatic model downloading and caching
-   Medium model by default for optimal quality/speed balance
-   Automatic audio extraction from video files using FFmpeg
-   Batch processing of entire directories

**Dependencies:**

-   openai-whisper
-   ffmpeg (system dependency)
-   CUDA-compatible GPU (optional, for acceleration)

**Usage:**

```bash
python Audio-_Video-2-Text/whisper_transcriber.py [options]
```

### Image+Audio → Video Creator

Creates an HEVC-encoded (Nvidia NVENC) video from a still image and an audio track.
The resulting video keeps the image aspect ratio, but scales down so that the
longest side is at most 2160 pixels (Lanczos). Frames per second are fixed at
10 fps. Audio is re-encoded to AAC, 48 kHz, 320 kbps.

**Features:**

-   Combines a single image and a single audio file into an HEVC-encoded MP4 video.
-   Preserves image aspect ratio with intelligent scaling (max 2160p on longest side).
-   Fixed 10 FPS video output.
-   Audio re-encoded to high-quality AAC (48 kHz, 320 kbps).
-   Interactive-only mode for guided input.

**Dependencies:**

-   Pillow 9+ (Python dependency)
-   ffmpeg (system dependency)

**Usage:**

```bash
# This tool is launched via the interactive menu (menu.py)
# python VideoTools/Image_Audio_To_Video.py # (Not typically run directly)
```

## Text Tools

### Telegram Chats Distiller

Processes Telegram chat export JSON files by extracting and transforming messages.

**Features:**

-   Extracts text from the "text_entities" field in each message
-   Preserves message ID, creation date, and media attachments information
-   Removes formatting while keeping the essential text
-   Outputs a clean JSON file with the transformed data

**Usage:**

```
python3 TxtTools/Telegram_Chats_Distiller.py --input <input_file> [--output <output_file>]
```

### Infinite Differ

A powerful tool for comparing multiple text files simultaneously with Git-like diff visualization.

**Features:**

-   Compare more than two text sources at once
-   Highlights additions, deletions, and modifications across files
-   Color-coded visualization of changes
-   Line number indicators
-   Search functionality

**Usage:**

```
python TxtTools/MultipleTextComparator/Infinite_Differ.py
```

### Word-Markdown Converter

Convert between DOCX and Markdown formats.

**Features:**

-   Supports conversion from DOCX to Markdown and vice-versa
-   Handles embedded images and media, saving them to a specified directory
-   Utilizes Pandoc for robust and accurate conversions
-   Batch processing for multiple files

**Dependencies:**

-   pypandoc
-   pandoc (system dependency)

**Usage:**

```bash
python TxtTools/WMDconverter/WMDconverter.py --source <input_file> --output <output_file> [--media-dir <media_directory>]
```

## Video Tools

### FFMPEG MKV Audio Normalizer

A tool for normalizing audio tracks in MKV video files using ffmpeg's loudnorm filter.

**Features:**

-   Scans input location for MKV files
-   Analyzes audio tracks with ffprobe
-   Normalizes audio using the EBU R128 loudness standard
-   Preserves video and subtitle streams
-   Maintains original audio track titles
-   Processes files asynchronously for improved performance

**Dependencies:**

-   ffmpeg (with loudnorm filter)
-   ffprobe

**Usage:**

```
python VideoTools/FFMPEG_MKV_audio_normlizer.py [options]
```

### Topaz Video Merger

A dual-input video/audio normalizer and merger. This tool combines two video or audio inputs, normalizes their audio, and merges them into a single output file.

**Features:**

-   Accepts two input files (primary and secondary, typically video and audio)
-   Normalizes audio for both inputs using EBU R128 loudness standard
-   Merges inputs while preserving video and audio streams
-   Supports various common video and audio formats

**Dependencies:**

-   ffmpeg
-   ffprobe

**Usage:**

```bash
python VideoTools/Topaz_Video_Merger.py -i1 <primary_input_file> -i2 <secondary_input_file> -o <output_directory>
```

### Video Converter

Re-encodes videos with HEVC (Nvidia NVENC) with quality and FPS options.

**Features:**

-   Re-encodes videos using HEVC (Nvidia NVENC).
-   Allows user to select quality presets (Master, Normal, Compact).
-   Allows user to select FPS (original, 30, 60, 120).
-   Processes all compatible video files from an input directory to an output directory.
-   Single-file processing on GPU to avoid resource contention.

**Dependencies:**

-   ffmpeg (system dependency)

**Usage:**

```bash
python VideoTools/video_converter.py [options]
```

## Utility Tools

### Requirements Builder

A utility script to generate requirements.txt by scanning Python files for imports.

**Features:**

-   Scans all Python files in the specified directory and its subdirectories
-   Detects non-standard imports using AST parsing
-   Includes version information for installed packages
-   Supports custom output locations
-   Offers to install packages via pip after generating the file
-   Can recursively generate requirements.txt for subdirectories

**Usage:**

```
python requirementsBuilder.py
```

## Custom Tools

You can request a custom tool by contacting me at [t.me/Artemonim](https://t.me/Artemonim) or Artemonim@yandex.ru.

If any of these tools have been particularly helpful to you, feel free to express your appreciation! :3

## Agent Tools

### GitHub Issue Synchronization Script for Cursor IDE

`ghsync.py` allows your Agent to interact with GitHub issues in your repository.

It enables reading all labels and issues, editing existing issues, and creating new ones. The script supports changing issue status but cannot delete issues.

**Requirements:**

1.  **Python 3**: Ensure Python 3 is installed on your system.
2.  **GitHub CLI (gh)**: The [GitHub CLI](https://cli.github.com/) must be installed and authenticated (`gh auth login`).

**Usage:**

Add the `.cursor` folder to your repository and read [ghsync_Readme.md](/AgentTools/GithubIssueSynchronizationScript/.cursor/Gitdata/ghsync_Readme.md).
