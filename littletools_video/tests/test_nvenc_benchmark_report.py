from __future__ import annotations

import json
from pathlib import Path

import pytest

from littletools_video.benchmark.nvenc_benchmark import choose_metric_backend
from littletools_video.benchmark.nvenc_benchmark import generate_variants
from littletools_video.benchmark.nvenc_benchmark import write_reports


def test_generate_variants_quick_smaller_than_full() -> None:
    quick = generate_variants("quick", max_variants=None)
    full = generate_variants("full", max_variants=None)
    assert len(quick) > 0
    assert len(full) > len(quick)


def test_generate_variants_limit() -> None:
    full = generate_variants("full", max_variants=5)
    assert len(full) == 5


def test_choose_metric_backend() -> None:
    assert choose_metric_backend(True, False) == "vmaf"
    assert choose_metric_backend(True, True) == "vmaf"
    assert choose_metric_backend(False, False) == "fallback"
    with pytest.raises(RuntimeError):
        choose_metric_backend(False, True)


def test_write_reports(tmp_path: Path) -> None:
    # Create minimal per-file rows
    rows = [
        {
            "input": "a.mp4",
            "variant": "h264_cq26_bf2",
            "label": "quick-h264-cq26",
            "codec": "h264",
            "quality": "26",
            "elapsed_s": 1.0,
            "duration_s": 10.0,
            "rtf": 10.0,
            "size_in": 100,
            "size_out": 60,
            "size_reduction_percent": 40.0,
            "efficiency_ratio": 40.0,
            "status": "ok",
            "note": "",
            "vmaf": 92.5,
        },
        {
            "input": "b.mp4",
            "variant": "h264_cq26_bf2",
            "label": "quick-h264-cq26",
            "codec": "h264",
            "quality": "26",
            "elapsed_s": 2.0,
            "duration_s": 10.0,
            "rtf": 5.0,
            "size_in": 100,
            "size_out": 55,
            "size_reduction_percent": 45.0,
            "efficiency_ratio": 50.0,
            "status": "ok",
            "note": "",
            "vmaf": 90.0,
        },
    ]
    out_dir = tmp_path / "reports"
    write_reports(rows, out_dir)
    # Check files exist
    assert (out_dir / "nvenc_benchmark_per_file.csv").exists()
    assert (out_dir / "nvenc_benchmark_per_file.json").exists()
    assert (out_dir / "nvenc_benchmark_per_file.md").exists()
    assert (out_dir / "nvenc_benchmark_agg.csv").exists()
    js = json.loads((out_dir / "nvenc_benchmark_agg.json").read_text(encoding="utf-8"))
    assert isinstance(js, list)
    assert js and "codec" in js[0] and "quality" in js[0] and "b_frames" in js[0]
