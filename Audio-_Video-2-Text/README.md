# Whisper Audio/Video Transcriber

This tool transcribes audio and video files using OpenAI's Whisper model. It supports GPU acceleration and can process entire directories of media files.

## Features

-   **Multi-format support**: Audio (MP3, WAV, M4A, AAC, OGG, FLAC) and Video (MP4, MKV, MOV, AVI, WebM)
-   **GPU acceleration**: CUDA support for faster processing
-   **Automatic model management**: Downloads and caches models locally
-   **Video processing**: Automatic audio extraction using FFmpeg
-   **Batch processing**: Process entire directories at once
-   **Flexible output**: Text files named after source files

## Quick Start

### Via Menu System (Recommended)

1. Run `.\start.ps1` (Windows) or `python menu.py` from project root
2. Select "Whisper Audio/Video Transcriber" from the menu
3. Choose batch mode to process all files in `0-INPUT-0`
4. Results will be saved to `0-OUTPUT-0` as `.txt` files

### Standalone Usage

```bash
# Process a single file
python whisper_transcriber.py -i audio.mp3 -o transcriptions/

# Process entire directory with GPU acceleration
python whisper_transcriber.py -i /path/to/media/ -o /path/to/output/ --gpu

# Use different model
python whisper_transcriber.py -i audio.mp3 --model large --gpu

# Specify language (optional, auto-detected by default)
python whisper_transcriber.py -i audio.mp3 --language ru
```

## Command Line Options

| Option          | Description                                                    | Default                       |
| --------------- | -------------------------------------------------------------- | ----------------------------- |
| `-i, --input`   | Input file or directory                                        | Auto-detected                 |
| `-o, --output`  | Output directory                                               | Auto-detected                 |
| `--model`       | Whisper model (tiny/base/small/medium/large/large-v2/large-v3) | medium                        |
| `--model_root`  | Directory to store models                                      | `Audio-_Video-2-Text/models/` |
| `--gpu`         | Enable GPU acceleration                                        | Disabled                      |
| `--language`    | Language code (e.g., 'en', 'ru')                               | Auto-detect                   |
| `--temperature` | Sampling temperature (0.0-1.0)                                 | 0.25                          |

## Model Information

| Model      | Size   | Parameters | Speed   | Quality         |
| ---------- | ------ | ---------- | ------- | --------------- |
| tiny       | ~40MB  | 39M        | Fastest | Basic           |
| base       | ~75MB  | 74M        | Fast    | Good            |
| small      | ~244MB | 244M       | Medium  | Better          |
| **medium** | ~786MB | 769M       | Slower  | **Recommended** |
| large      | ~2.9GB | 2.9B       | Slowest | Best            |

## System Requirements

### Required

-   Python 3.8+
-   FFmpeg (for video processing)

### Optional

-   CUDA-compatible GPU (for `--gpu` acceleration)
-   4GB+ RAM (for medium model)
-   10GB+ RAM (for large model)

## Installation

### Via Menu System

The menu system will automatically install dependencies when you first select the tool.

### Manual Installation

```bash
pip install openai-whisper ffmpeg-python
```

**Note**: You also need to install FFmpeg system-wide:

-   Windows: Download from https://ffmpeg.org/ or use `winget install ffmpeg`
-   macOS: `brew install ffmpeg`
-   Linux: `sudo apt install ffmpeg` (Ubuntu/Debian) or equivalent

## Output Format

The tool creates `.txt` files with the same name as the input file:

-   `audio.mp3` → `audio.txt`
-   `video.mkv` → `video.txt`

Each text file contains the complete transcription of the audio content.

## Troubleshooting

### Installation Issues

#### "Getting requirements to build wheel did not run successfully"
This is a common issue with openai-whisper installation. Try these solutions:

1. **Use the manual installation script**:
   ```bash
   python Audio-_Video-2-Text/install_whisper_manual.py
   ```

2. **Upgrade build tools first**:
   ```bash
   pip install --upgrade pip setuptools wheel
   pip install --no-cache-dir openai-whisper
   ```

3. **Install PyTorch separately**:
   ```bash
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
   pip install openai-whisper ffmpeg-python
   ```

#### "KeyError: '__version__'" during installation
This indicates a setuptools compatibility issue:
```bash
pip install setuptools>=65.0.0
pip install --no-cache-dir openai-whisper
```

### Runtime Issues

### "ffmpeg not found"

Install FFmpeg system-wide and ensure it's in your PATH.

### "CUDA not available"

Install CUDA toolkit and PyTorch with CUDA support, or run without `--gpu` flag.

### "Model download failed"

Ensure internet connection and sufficient disk space in the model directory.

### "Out of memory"

Try a smaller model (e.g., `--model small`) or process files individually instead of batch mode.
