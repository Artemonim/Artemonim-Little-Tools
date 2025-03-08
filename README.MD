# Artemonim's Little Tools

[Описания и инструкция на русском...](Docs/ПРОЧТИМЕНЯ.MD)

A collection of small utility tools created for [personal commercial and non-commercial needs](/LICENSE). These tools aim to solve specific problems efficiently and can be used across different environments.

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
