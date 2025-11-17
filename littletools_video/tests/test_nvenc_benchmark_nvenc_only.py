from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import littletools_video.benchmark.nvenc_benchmark as nb


def _smallest_in(dir_path: Path) -> Path | None:
    files = [p for p in dir_path.iterdir() if p.is_file()]
    if not files:
        return None
    return min(files, key=lambda p: p.stat().st_size)


def test_require_nvenc_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch get_nvenc_video_options to simulate software fallback
    def _fake_options(codec: str, quality: str) -> list[str]:
        return ["-c:v", "libx264", "-crf", "23"]

    monkeypatch.setattr(nb, "get_nvenc_video_options", _fake_options)
    v = nb.VariantParams(
        codec="h264",
        quality="30",
        b_frames=0,
        temporal_aq=False,
        rc_lookahead=0,
        aq_strength=0,
        multipass="off",
        b_ref_mode="disabled",
        main10=False,
        label="unit-fastest",
    )
    # Use a dummy file path; _encode_once will fail earlier due to guard
    with pytest.raises(RuntimeError):
        asyncio.run(
            nb._encode_once(  # type: ignore[attr-defined]
                Path("nonexistent.mp4"),
                Path("T:/Temp/NVENC"),
                v,
                overwrite=True,
                stats=None,
                total_duration=None,
                require_nvenc=True,
            )
        )


def test_integration_fastest_variant_if_nvenc_available(tmp_path: Path) -> None:
    # Integration test: run fastest plausible H.264 variant on smallest test file if available
    test_dir = Path("littletools_video/littletools_video/benchmark/testData")
    if not test_dir.exists():
        pytest.skip("testData folder not present")
    src = _smallest_in(test_dir)
    if src is None:
        pytest.skip("No files in testData")
    # Decide availability by inspecting options
    opts = nb.get_nvenc_video_options("h264", "40")
    if "h264_nvenc" not in opts:
        pytest.skip("NVENC not available in FFmpeg build")
    v = nb.VariantParams(
        codec="h264",
        quality="40",
        b_frames=0,
        temporal_aq=False,
        rc_lookahead=0,
        aq_strength=0,
        multipass="off",
        b_ref_mode="disabled",
        main10=False,
        label="anchor-fastest",
    )
    out_dir = tmp_path
    out, used, elapsed = asyncio.run(
        nb._encode_once(  # type: ignore[attr-defined]
            src, out_dir, v, overwrite=True, stats=None, total_duration=None, require_nvenc=True
        )
    )
    assert used is True
    assert out is not None and out.exists() and out.stat().st_size > 0

