# Stylizer Development Plan Checklist

This document outlines the steps to implement the video stylization tool using Stable Diffusion and Real-ESRGAN, with a focus on 8GB VRAM compatibility.

## 1. Core Setup & Scaffolding

-   [ ] Create `littletools_video/littletools_video/stable_diffusion_stylizer` directory.
-   [ ] Create `stable_diffusion_stylizer.py` file.
-   [ ] Update `littletools_video/pyproject.toml`:
    -   [ ] Add `diffusers`, `transformers`, `torch`, `accelerate`, `realesrgan` to `[project.dependencies]`.
    -   [ ] (Optional) Add `xformers` to `[project.dependencies]`.
    -   [ ] Add `stylize = "littletools_video.stable_diffusion_stylizer:app"` to `[project.entry-points."littletools.commands"]`.

## 2. Video Frame Extraction (480p)

-   [ ] Implement video to frame extraction (e.g., using `ffmpeg_utils` or `subprocess`):
        `ffmpeg -i input.mp4 -vf scale=854:480 temp/frames/%06d.png`
-   [ ] Ensure `temp/frames/` is added to `.gitignore` (manual step for user).

## 3. Stable Diffusion Stylization Pipeline

-   [ ] Implement `stylize` Typer command in `stable_diffusion_stylizer.py`.
-   [ ] Integrate `littletools_core.huggingface_utils.download_hf_model` for model caching.
    -   [ ] Default `model_id` to `runwayml/stable-diffusion-v1-5` (or `stabilityai/stable-diffusion-2-base`).
    -   [ ] Добавить возможность указать стороннюю модель по абсолютному пути.
-   [ ] Initialize `StableDiffusionPipeline`:
    -   [ ] Use `torch_dtype=torch.float16`.
    -   [ ] Call `pipeline.enable_attention_slicing()`.
    -   [ ] Call `pipeline.enable_xformers_memory_efficient_attention()` (if `xformers` is installed).
-   [ ] Iterate through frames (batch_size=1) with `tqdm` progress bar.
-   [ ] Save stylized frames to `temp/stylized_frames/`.

## 4. Real-ESRGAN Upscaling (4x to FHD)

-   [ ] Integrate Real-ESRGAN отдельным скриптом:
    -   [ ] Option A: Use `RealESRGANer` class from `realesrgan` Python package.
    -   [ ] Option B: Call `realesrgan-ncnn-vulkan` command-line tool for each frame.
-   [ ] Perform 4x upscaling on stylized 480p frames to achieve FHD (1920x1080).
-   [ ] Save upscaled frames to `temp/upscaled_frames/`.

## 5. Video Reassembly

-   [ ] Option A: использовать merge режим `littletools_video\littletools_video\video_converter.py`
-   [ ] Option B: Implement frame to video reassembly (e.g., using `ffmpeg`):
        `ffmpeg -r <framerate> -i temp/upscaled_frames/stylized_up_%06d.png -c:v libx264 -pix_fmt yuv420p output.mp4`

## 6. CLI Parameters & User Experience

-   [ ] Define Typer command arguments for `stylize`:
    -   [ ] `input_video: Annotated[Path, typer.Argument(help="Input video file.")]`
    -   [ ] `prompt: Annotated[str, typer.Option("--prompt", "-p", help="Text prompt for stylization.")]`
    -   [ ] `model_id: Annotated[str, typer.Option("--model-id", "-m", help="Hugging Face model ID for Stable Diffusion.")]`
    -   [ ] `controlnet_id: Annotated[Optional[str], typer.Option("--controlnet-id", "-c", help="Hugging Face model ID for ControlNet (optional).")]`
    -   [ ] `use_animatediff: Annotated[bool, typer.Option("--animatediff", help="Enable AnimateDiff for temporal consistency.")]`
    -   [ ] `strength: Annotated[float, typer.Option("--strength", "-s", min=0.0, max=1.0, help="Stylization strength (0.0-1.0).")]`
    -   [ ] `upscale: Annotated[bool, typer.Option("--upscale", help="Enable Real-ESRGAN 4x upscaling to FHD.")]`
    -   [ ] `output: Annotated[Path, typer.Option("--output", "-o", help="Output video file path.")]`
    -   [ ] `max_resolution: Annotated[str, typer.Option("--max-res", help="Maximum resolution for processing (e.g., '480p', '720p').")]` (for initial frame extraction)
-   [ ] Add robust error handling for VRAM limits and missing dependencies.
-   [ ] Provide clear progress feedback using `tqdm`.

## 7. Testing & Optimization

-   [ ] Optimize for speed and memory efficiency.
-   [ ] Следить за тем, чтобы в VRAM оставалось только то, что используется в данный момент.

