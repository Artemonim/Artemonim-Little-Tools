import asyncio
from pathlib import Path
from typing import Any

from littletools_core.utils import BatchTimeEstimator
from littletools_video import video_converter
from littletools_video.ffmpeg_utils import ProcessingStats


async def _fake_run_ffmpeg_command(
    cmd: list[str],
    stats: ProcessingStats,
    quiet: bool,
    output_path: str,
    file_position: int,
    file_count: int,
    filename: str,
    total_duration: float,
) -> bool:
    """Fake ffmpeg runner that creates the expected output file and reports success."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake")
    return True


async def _fake_get_video_duration(path: str) -> float:
    return 1.0


async def _fake_get_video_resolution(path: str) -> tuple[int, int]:
    return (1920, 1080)


def test_output_filename_used_when_provided(tmp_path: Path, monkeypatch: Any) -> None:
    """Если передано output_filename, файл создаётся по точному пути (out_dir/output_filename)."""
    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"input")

    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    output_filename = "custom_name.mp4"

    # Подменяем асинхронные зависимости
    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _fake_run_ffmpeg_command)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(
        video_converter, "get_video_resolution", _fake_get_video_resolution
    )

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


def test_skip_when_overwrite_false(tmp_path: Path, monkeypatch: Any) -> None:
    """Если файл существует и overwrite=False — операция пропускается и stats.increment('skipped') вызывается."""
    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"input")

    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    output_filename = "custom_name.mp4"
    existing = out_dir / output_filename
    existing.write_bytes(b"old")

    # Подменяем зависимости, которые не должны вызываться при пропуске
    called: dict[str, bool] = {"ffmpeg": False}

    async def _maybe_run(*args: Any, **kwargs: Any) -> bool:
        called["ffmpeg"] = True
        return await _fake_run_ffmpeg_command(*args, **kwargs)

    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _maybe_run)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(
        video_converter, "get_video_resolution", _fake_get_video_resolution
    )

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


def test_overwrite_true_uses_original_name_in_export_dir(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """При overwrite=True и без output_filename должен использоваться оригинальный имя файла в каталоге экспорта."""
    input_file = tmp_path / "video_source.mp4"
    input_file.write_bytes(b"input")

    out_dir = tmp_path / "exports" / "nested"
    out_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _fake_run_ffmpeg_command)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(
        video_converter, "get_video_resolution", _fake_get_video_resolution
    )

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
            overwrite=True,
            codec="hevc",
            stats=stats,
            estimator=estimator,
            position=1,
            total=1,
            use_original_name=True,
            output_filename=None,
        )
    )

    expected_path = out_dir / input_file.name
    assert (
        expected_path.exists()
    ), "Output file should be created under export dir with original name"


def test_output_filename_with_leading_sep_is_relative_to_export_dir_on_windows(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """На Windows output_filename, начинающийся с '\\', трактуется как относительный к каталогу экспорта, а не корень диска."""
    import os
    import sys

    if sys.platform != "win32":
        import pytest

        pytest.skip("Windows-specific path behavior")

    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"input")

    out_dir = tmp_path / "exports"
    out_dir.mkdir()

    # Leading backslash simulates an anchored path without drive (e.g., \\nested\\target.mp4)
    output_filename = os.sep + "nested" + os.sep + "target.mp4"

    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _fake_run_ffmpeg_command)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(
        video_converter, "get_video_resolution", _fake_get_video_resolution
    )

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
            overwrite=True,
            codec="hevc",
            stats=stats,
            estimator=estimator,
            position=1,
            total=1,
            use_original_name=True,
            output_filename=output_filename,
        )
    )

    expected_path = out_dir / "nested" / "target.mp4"
    assert (
        expected_path.exists()
    ), "Anchored filename should be resolved under export dir, not drive root"


def test_single_treats_directory_like_output_as_directory(tmp_path: Path, monkeypatch: Any) -> None:
    """single(): если для одного файла ввели путь без расширения, трактуем как директорию."""
    # Arrange input file
    input_file = tmp_path / "clip.mp4"
    input_file.write_bytes(b"input")

    # Output directory path without extension
    out_dir = tmp_path / "DaVinci"

    # Stub interactive prompts: first ask for input, then for output path
    prompts: list[str] = [str(input_file), str(out_dir)]

    def _fake_prompt(_message: str, default: str | None = None) -> str:  # type: ignore[override]
        return prompts.pop(0) if prompts else (default or "")

    # Speed through settings menu by returning chosen settings directly
    def _fake_prompt_settings(settings_definitions: Any, current_settings: dict[str, Any], title: str) -> dict[str, Any]:
        # Emulate user's screenshot: overwrite On, rest defaults
        current_settings = dict(current_settings)
        current_settings["overwrite"] = True
        return current_settings

    # Patch async ffmpeg utilities
    monkeypatch.setattr(video_converter, "run_ffmpeg_command", _fake_run_ffmpeg_command)
    monkeypatch.setattr(video_converter, "get_video_duration", _fake_get_video_duration)
    monkeypatch.setattr(video_converter, "get_video_resolution", _fake_get_video_resolution)

    # Patch interactive helpers
    monkeypatch.setattr(video_converter.typer, "prompt", _fake_prompt)
    monkeypatch.setattr(video_converter, "prompt_for_interactive_settings", _fake_prompt_settings)

    # Act
    video_converter.single()

    # Assert: since overwrite=True, original name is used inside provided directory
    expected_path = out_dir / input_file.name
    assert expected_path.exists(), "Output should be created inside provided directory with original filename"
