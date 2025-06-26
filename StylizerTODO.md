# Stylizer Development Plan Checklist

This document outlines the steps to implement the video stylization tool using Stable Diffusion and Real-ESRGAN, with a focus on 8GB VRAM compatibility.

## 1. Core Setup & Scaffolding

-   [x] Create `stable_diffusion_stylizer.py` file.
-   [x] Update `littletools_video/pyproject.toml`:
    -   [x] Add `diffusers`, `transformers`, `torch`, `accelerate`, `realesrgan` to `[project.dependencies]`.
    -   [x] (Optional) Add `xformers` to `[project.dependencies]`.
    -   [x] Add `stylize = "littletools_video.stable_diffusion_stylizer:app"` to `[project.entry-points."littletools.commands"]`.

## 2. Video Frame Extraction (480p)

-   [x] Implement video to frame extraction (e.g., using `ffmpeg_utils` or `subprocess`):
        `ffmpeg -i input.mp4 -vf scale=854:480 temp/frames/%06d.png`
-   [x] Ensure `temp/frames/` is added to `.gitignore`.

## 3. Stable Diffusion Stylization Pipeline

-   [x] Implement `stylize` Typer command in `stable_diffusion_stylizer.py`.
-   [x] Integrate `littletools_core.huggingface_utils.download_hf_model` for model caching.
    -   [x] Default `model_id` to `stabilityai/stable-diffusion-2-base` (new default).
    -   [x] Добавить возможность указать стороннюю модель по абсолютному пути.
-   [x] Initialize `StableDiffusionPipeline`:
    -   [x] Use `torch_dtype=torch.float16`.
    -   [x] Call `pipeline.enable_attention_slicing()`.
    -   [x] Call `pipeline.enable_xformers_memory_efficient_attention()` (if `xformers` is installed).
-   [x] Iterate through frames (batch_size=1) with Rich progress bar.
-   [x] Save stylized frames to `temp/stylized_frames/`.

## 4. Real-ESRGAN Upscaling (4x to FHD)

-   [x] Integrate Real-ESRGAN implementation:
    -   [x] Use `RealESRGANer` class from `realesrgan` Python package.
    -   [x] Initialize with RealESRGAN_x4plus model for 4x upscaling.
-   [x] Perform 4x upscaling on stylized 480p frames to achieve FHD (1920x1080).
-   [x] Save upscaled frames to `temp/upscaled_frames/`.
-   [x] Handle fallback when Real-ESRGAN fails (use stylized frames without upscaling).

## 5. Video Reassembly

-   [ ] Option A: использовать merge режим `littletools_video\littletools_video\video_converter.py`
-   [x] Option B: Implement frame to video reassembly (e.g., using `ffmpeg`):
        `ffmpeg -r <framerate> -i temp/upscaled_frames/stylized_up_%06d.png -c:v libx265 -crf 26 output.mp4`
-   [x] Auto-detect framerate from original video using `ffprobe`.

## 6. CLI Parameters & User Experience

-   [x] Define Typer command arguments for `stylize`:
    -   [x] `input_video: Annotated[Path, typer.Argument(help="Input video file.")]`
    -   [x] `prompt: Annotated[str, typer.Option("--prompt", "-p", help="Text prompt for stylization.")]`
    -   [x] `model_id: Annotated[str, typer.Option("--model-id", "-m", help="Hugging Face model ID for Stable Diffusion.")]`
    -   [x] `controlnet_id: Annotated[Optional[str], typer.Option("--controlnet-id", "-c", help="Hugging Face model ID for ControlNet (optional).")]`
    -   [x] `use_animatediff: Annotated[bool, typer.Option("--animatediff", help="Enable AnimateDiff for temporal consistency.")]`
    -   [x] `strength: Annotated[float, typer.Option("--strength", "-s", min=0.0, max=1.0, help="Stylization strength (0.0-1.0).")]`
    -   [x] `upscale: Annotated[bool, typer.Option("--upscale", help="Enable Real-ESRGAN 4x upscaling to FHD.")]`
    -   [x] `output: Annotated[Path, typer.Option("--output", "-o", help="Output video file path.")]`
    -   [x] `max_resolution: Annotated[str, typer.Option("--max-res", help="Maximum resolution for processing (e.g., '480p', '720p').")]` (for initial frame extraction)
-   [x] Add robust error handling for VRAM limits and missing dependencies.
-   [x] Provide clear progress feedback using Rich progress bars.

## 7. Testing & Optimization

-   [x] Optimize for speed and memory efficiency.
-   [x] Следить за тем, чтобы в VRAM оставалось только то, что используется в данный момент.
-   [x] Убедиться, что указаны все зависимости.
-   [x] Changed default `upscale=False` to reduce resource usage.

## 8. User Experience Improvements

-   [x] Implement comprehensive error handling with clear messages.
-   [x] Add fallback mechanism when Real-ESRGAN fails.
-   [x] Use temporary directories for processing (automatic cleanup).
-   [x] Memory-efficient processing with CPU offload and attention slicing.
-   [x] Auto-generate output filename if not specified.

## 9. Current Status

Предположительно, стилизатор может:

-   Извлекать кадры из видео
-   Стилизовать их с помощью Stable Diffusion
-   Опционально увеличивать разрешение с Real-ESRGAN
-   Собирать видео обратно с сохранением framerate
-   Работать с 8GB VRAM (оптимизации памяти)

**TEST UX**:

1. `video-stylizer stylize input.mp4 --prompt "anime style"`
2. Получить стилизованное видео `input_stylized.mp4`

**TODO для полировки**:

-   [ ] Исправить проблемы с линтингом (isort конфигурация)
-   [ ] Добавить поддержку ControlNet для лучшего контроля
-   [ ] Добавить поддержку AnimateDiff для временной согласованности
-   [ ] Тестирование на реальных видео
