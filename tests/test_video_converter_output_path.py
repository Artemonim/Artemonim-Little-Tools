import asyncio
from pathlib import Path

import pytest

from littletools_video import video_converter
from littletools_video.ffmpeg_utils import ProcessingStats
from littletools_core.utils import BatchTimeEstimator


async def _fake_run_ffmpeg_command(
    cmd,
    stats: ProcessingStats,
    quiet: bool,
    output_path: str,
    file_position: int,
    file_count: int,
    filename: str,
    total_duration: float,
):
    """Fake ffmpeg runner that creates the expected output file and reports success."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake")
    return True


async def _fake_get_video_duration(path: str):
    return 1.0


async def _fake_get_video_resolution(path: str):
    return (1920, 1080)


def test_output_filename_used_when_provided(tmp_path, monkeypatch):
    """Если передано output_filename, файл создаётся по точному пути (out_dir/output_filename)."""
    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"input")

    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    output_filename = "custom_name.mp4"

    # Подменяем асинхронные зависимости
    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _fake_run_ffmpeg_command)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(video_converter, "get_video_resolution", _fake_get_video_resolution)

    stats = ProcessingStats()
    estimator = BatchTimeEstimator()

    asyncio.run(
        video_converter._process_single_file_for_conversion(
            file_path=input_file,
            output_dir=out_dir,
            quality="26",
            fps="original",
            resolution="original",
            normalize_audio=False,
            overwrite=False,
            codec="hevc",
            stats=stats,
            estimator=estimator,
            position=1,
            total=1,
            use_original_name=False,
            output_filename=output_filename,
        )
    )

    out_path = out_dir / output_filename
    assert out_path.exists(), "Output file was not created at the expected location"


def test_skip_when_overwrite_false(tmp_path, monkeypatch):
    """Если файл существует и overwrite=False — операция пропускается и stats.increment('skipped') вызывается."""
    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"input")

    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    output_filename = "custom_name.mp4"
    existing = out_dir / output_filename
    existing.write_bytes(b"old")

    # Подменяем зависимости, которые не должны вызываться при пропуске
    called = {"ffmpeg": False}

    async def _maybe_run(*args, **kwargs):
        called["ffmpeg"] = True
        return await _fake_run_ffmpeg_command(*args, **kwargs)

    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _maybe_run)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(video_converter, "get_video_resolution", _fake_get_video_resolution)

    stats = ProcessingStats()
    estimator = BatchTimeEstimator()

    asyncio.run(
        video_converter._process_single_file_for_conversion(
            file_path=input_file,
            output_dir=out_dir,
            quality="26",
            fps="original",
            resolution="original",
            normalize_audio=False,
            overwrite=False,
            codec="hevc",
            stats=stats,
            estimator=estimator,
            position=1,
            total=1,
            use_original_name=False,
            output_filename=output_filename,
        )
    )

    # Убедимся, что операция была пропущена и ffmpeg не вызывался
    assert stats.stats.get("skipped", 0) == 1
    assert called["ffmpeg"] is False


