<!-- 2e3d4ec4-8efc-4b26-8b66-3b7a46185de5 54c3b1f6-d9e9-497e-b1f2-56662acba3b9 -->
# NVENC Benchmark (internal tool)

## What we’ll build

A standalone NVENC benchmarking CLI inside `littletools_video` that:

- Sweeps a “full” parameter grid (codec/quality/AQ/lookahead/10-bit/b-frames/b_ref/temporal_aq/multipass)
- Encodes each input variant using existing helpers
- Computes quality metrics (VMAF + VMAF NEG when `libvmaf` exists; otherwise falls back to SSIM/PSNR or optionally fails)
- Writes CSV/JSON/MD reports (per-file and aggregated), with robust error/status tagging
- Not shown in the LittleTools main menu; exposed only as a console script
- Includes a pytest covering grid generation, metric selection, and report writer

## Files to add/update

- Add: `littletools_video/littletools_video/benchmark/__init__.py` (exports `app`)
- Add: `littletools_video/littletools_video/benchmark/__main__.py` (runs `app()`)
- Add: `littletools_video/littletools_video/benchmark/nvenc_benchmark.py`
- Typer CLI with command `run`
- Variant grid generator for “full” profile
- Encoder wrapper using `get_nvenc_video_options` + parameter overrides (bf, b_ref_mode, temporal_aq, multipass, aq_strength, rc_lookahead, hevc 10‑bit via `-pix_fmt p010le` + `-profile:v main10`)
- Metrics:
    - Detect `libvmaf` (parse `ffmpeg -filters`)
        - If available: compute VMAF and VMAF NEG (two passes) via `libvmaf` filter
        - Else: compute SSIM + PSNR (fallback) OR fail if `--require-vmaf`
    - Расчитывать дельту потери размера в `%`
    - **Разработать и внедрить ключевую метрику**: расчёт соотношения дельты потери размера к потери качества по VMAF
        - чем меньше размер и выше VMAF - тем лучше вариант настроек
- Parse metrics from ffmpeg output (JSON for VMAF, stdout regex for SSIM/PSNR)
- Robust error classification (unsupported/failed/oom) and continuation
- Reporting (CSV/JSON/MD) with: params, duration, size, bitrate, RTF, metrics, status
- Concurrency default 1 (avoid GPU contention), configurable
- Options: `--inputs` (multi), `--input-dir`, `--out`, `--profile {full|extended|quick|custom}`, `--require-vmaf`, `--vmaf-model-dir`, `--max-variants`, `--overwrite`, `--concurrency`, `--keep-outputs`
- Update: `littletools_video/pyproject.toml`
- `[project.scripts]` add: `nvenc-benchmark = "littletools_video.benchmark:nvenc_main"` (or `:app`)
- Do NOT add to `[project.entry-points."littletools.commands"]`
- Add tests: `littletools_video/tests/test_nvenc_benchmark_report.py`
- Unit tests (pytest) that:
- Validate ‘full’ grid generator yields expected shape with filtering applied
- Validate metric backend selection (mock `libvmaf` detection) and parsing stubs
- Validate report assembly to CSV/JSON/MD with synthetic rows
- No external deps beyond stdlib + pytest (already used in repo); heavy calls mocked

## Key behaviors

- Defaults to “full” profile but allows limiting via `--max-variants`
- Uses existing `ffmpeg_utils.run_ffmpeg_command`, `get_video_duration`, `ProcessingStats`
- Handles HEVC 10‑bit (main10) when requested and classifies failure if unsupported
- VMAF NEG computed alongside standard VMAF when available; otherwise SSIM/PSNR fallback or error with `--require-vmaf`
- Clear statuses: ok | unsupported | failed | oom; continue processing and mark in reports

## Usage examples

- CLI (installed editable):
`nvenc-benchmark run --input-dir 0-INPUT-0 --out tools_out/nvenc_bench --profile full --max-variants 600`
- Require VMAF only:
`nvenc-benchmark run --input video1.mp4 --out tools_out/nvenc_bench --require-vmaf`
- Provide model dir:
`nvenc-benchmark run --input video1.mp4 --vmaf-model-dir PATH_TO_MODELS`

## No new dependencies

- Pure Typer + stdlib + existing LittleTools utils; metrics via ffmpeg only
- Tests mock ffmpeg subprocess to avoid GPU/codec requirements

## Дополнительно

- Тестовые видео доступны в папке `littletools_video/littletools_video/benchmark/testData`
- Промежуточные файлы, не несущую отчётную информацию (например, конвертированные видео), должны удаляться после получения данных с их обработки и при возникновении ошибок.
    - Промежуточные файлы видео сохраняй по абсолютному пути `T:\Temp\NVENC`
    - Для хранения статистических и отчётных данных используй `littletools_video\littletools_video\benchmark\reports`
- Если VMAF или VMAF NEG недоступны и ты не можешь добыть их самостоятельно - дать Архитектуру инструкции по их добавлению.
    - На этом ПК использовался пакет FFMetrics, внутри которого работает VMAF, так что эту метрику ПК точно поддерживает.
- Добавить в варианты сетап параметров, который общепринято считается быстрейшим и/или должен быть быстрейшим теоретически.
    - Если это не одно и то же, то также добавить сетап параметров, который общепринято считается худшим по качеству и/или должен быть худшим теоретически.

### To-dos

- [ ] Create benchmark package with Typer app and entry point
- [ ] Implement full parameter grid and filtering/limiting controls
- [ ] Run encodes via FFmpeg util with robust error handling
- [ ] Detect libvmaf availability and models; support require/fallback
- [ ] Compute VMAF and VMAF NEG or fallback SSIM/PSNR; parse outputs
- [ ] Aggregate variant results; write CSV/JSON/MD reports
- [ ] Classify failures (unsupported/oom/failed) and continue
- [ ] Wire Typer CLI, options, and add console script in pyproject
- [ ] Add pytest for grid generation, metric selection, report assembly
- [ ] Add README section/snippet with usage and model path guidance