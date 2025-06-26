#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stable Diffusion Video Stylizer

This tool stylizes videos using Stable Diffusion models and upscales them using Real-ESRGAN.
Optimized for 8GB VRAM with memory-efficient techniques.
"""

import asyncio
import functools
import tempfile
import os
from pathlib import Path
from typing import Any, Optional, Tuple

import typer
from rich.console import Console
from rich.progress import Progress, TaskID
from typing_extensions import Annotated

# * Suppress xformers FutureWarnings and import required modules for stderr redirection
import warnings
import contextlib
warnings.filterwarnings("ignore", category=FutureWarning, module="xformers")

from littletools_core.huggingface_utils import download_hf_model
from littletools_core.utils import (
    ensure_dir_exists,
    prompt_for_path,
    prompt_for_interactive_settings,
)

# * Global configuration
console = Console()
app = typer.Typer(
    name="stylize",
    help="Stylize videos using Stable Diffusion and upscale with Real-ESRGAN.",
    no_args_is_help=True,
)

# * Enable torch.compile() caching for better performance
os.environ["TORCH_COMPILE_CACHE_DIR"] = os.path.join(os.getcwd(), ".torch_compile_cache")
os.environ["TORCHINDUCTOR_CACHE_DIR"] = os.path.join(os.getcwd(), ".torchinductor_cache")

# * Set torch matmul precision for better performance on Ampere+ GPUs
try:
    import torch
    if torch.cuda.is_available():
        torch.set_float32_matmul_precision('high')
except ImportError:
    pass # torch not installed yet

# * Global variable to store the master compiled pipeline
_compiled_master_pipeline = None


def clear_pipeline_cache():
    """Clear the cached master pipeline to free memory."""
    global _compiled_master_pipeline
    if _compiled_master_pipeline is not None:
        console.print("[*] Clearing cached master pipeline...")
        _compiled_master_pipeline = None
        console.print("[green]✓ Pipeline cache cleared[/green]")


def get_resolution_dimensions(resolution: str) -> Tuple[int, int]:
    """
    Convert resolution string to width, height tuple.

    Args:
        resolution: Resolution string like '480p', '720p', '1080p'

    Returns:
        Tuple of (width, height)
    """
    resolution_map = {
        "480p": (854, 480),
        "720p": (1280, 720),
        "1080p": (1920, 1080),
    }
    if resolution not in resolution_map:
        raise ValueError(f"Unsupported resolution: {resolution}")
    return resolution_map[resolution]


async def extract_frames(
    input_video: Path, frames_dir: Path, resolution: str = "480p", test_mode: bool = False
) -> bool:
    """
    Extract frames from video at specified resolution.

    Args:
        input_video: Path to the input video file
        frames_dir: Directory to save extracted frames
        resolution: Target resolution for extraction
        test_mode: If True, only process the first 2 seconds.

    Returns:
        True if successful, False otherwise
    """
    try:
        # * Ensure frames directory exists
        ensure_dir_exists(frames_dir)

        # * Get target dimensions
        width, height = get_resolution_dimensions(resolution)

        console.print(f"[*] Extracting frames at {resolution} ({width}x{height})...")
        if test_mode:
            console.print("[yellow]! Test mode enabled: processing first 2 seconds only.[/yellow]")

        # * Build ffmpeg command for frame extraction
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output files
            "-i",
            str(input_video),
            "-vf",
            f"scale={width}:{height}:flags=lanczos",
            "-q:v",
            "2",  # High quality JPEG
        ]

        # * If in test mode, only extract first 2 seconds
        if test_mode:
            ffmpeg_cmd.extend(["-t", "2"])

        ffmpeg_cmd.append(str(frames_dir / "%06d.png"))

        # * Run ffmpeg command
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            console.print(f"[red]! FFmpeg error: {stderr.decode()}[/red]")
            return False

        # * Count extracted frames
        frame_files = list(frames_dir.glob("*.png"))
        console.print(f"[green]✓ Extracted {len(frame_files)} frames[/green]")
        return True

    except Exception as e:
        console.print(f"[red]! Error extracting frames: {e}[/red]")
        return False


def setup_master_compiled_pipeline(model_id: str, scheduler_name: str = "UniPC") -> Any:
    """
    Set up and compile the master Stable Diffusion pipeline.

    On CUDA: the pipeline is loaded directly on GPU with `.to('cuda')`. Attention slicing
    and xformers memory-efficient attention are enabled for VRAM optimization.
    
    ! NOTE: `torch.compile()` and `enable_model_cpu_offload()` are disabled to prevent
    ! platform-specific conflicts on Windows (e.g., Triton dependency for torch.compile).

    This should be called once, then workers can clone from it.
    """
    global _compiled_master_pipeline
    
    if _compiled_master_pipeline is not None:
        console.print("[green]✓ Using cached compiled master pipeline[/green]")
        return _compiled_master_pipeline

    try:
        # * Import torch here to check if CUDA is available
        import torch
        # * Suppress xformers/triton warnings during diffusers import
        with open(os.devnull, 'w') as _f, contextlib.redirect_stderr(_f):
            from diffusers import (
                StableDiffusionImg2ImgPipeline,
                DDIMScheduler,
                EulerAncestralDiscreteScheduler,
                DPMSolverMultistepScheduler,
                UniPCMultistepScheduler,
            )

        console.print(f"[*] Setting up MASTER Stable Diffusion pipeline with model: {model_id}")

        # * Ensure cache directories exist
        os.makedirs(os.environ["TORCH_COMPILE_CACHE_DIR"], exist_ok=True)
        os.makedirs(os.environ["TORCHINDUCTOR_CACHE_DIR"], exist_ok=True)

        # * Check if model_id is a local path or HF model ID
        if Path(model_id).exists():
            model_path = model_id
            console.print(f"[*] Using local model: {model_path}")
        else:
            # * Download model from Hugging Face Hub
            model_path = download_hf_model(model_id)
            console.print(f"[*] Downloaded model to: {model_path}")

        # * Initialize pipeline with memory optimizations
        device = "cuda" if torch.cuda.is_available() else "cpu"
        console.print(f"[*] Using device: {device}")

        if device == "cuda":
            # * Load pipeline on GPU while suppressing external warnings
            with open(os.devnull, 'w') as _devnull, contextlib.redirect_stderr(_devnull):
                pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
                    str(model_path),
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                ).to("cuda")
            # * Enable attention slicing for VRAM optimization
            pipeline.enable_attention_slicing()
            console.print("[*] GPU attention slicing enabled for VRAM optimization")
            # * Attempt to enable xformers for further optimization
            try:
                pipeline.enable_xformers_memory_efficient_attention()
                console.print("[*] XFormers memory efficient attention enabled")
            except Exception:
                console.print("[yellow]! XFormers not available, continuing without it.[/yellow]")
        else:
            # * Load CPU pipeline while suppressing external warnings
            with open(os.devnull, 'w') as _devnull, contextlib.redirect_stderr(_devnull):
                pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
                    str(model_path),
                    torch_dtype=torch.float32,
                    use_safetensors=True,
                )
            console.print("[yellow]! CUDA not available, using CPU (will be slow)[/yellow]")

        # * Set the scheduler based on user choice
        console.print(f"[*] Setting scheduler to: {scheduler_name}")
        if scheduler_name == "UniPC":
            scheduler = UniPCMultistepScheduler.from_config(pipeline.scheduler.config)
        elif scheduler_name == "DDIM":
            scheduler = DDIMScheduler.from_config(pipeline.scheduler.config)
        elif scheduler_name == "EulerA":
            scheduler = EulerAncestralDiscreteScheduler.from_config(
                pipeline.scheduler.config
            )
        elif scheduler_name == "DPM2M":
            scheduler = DPMSolverMultistepScheduler.from_config(
                pipeline.scheduler.config
            )
        else:  # Default to UniPC if invalid choice
            console.print(
                f"[yellow]! Invalid scheduler '{scheduler_name}', defaulting to UniPC.[/yellow]"
            )
            scheduler = UniPCMultistepScheduler.from_config(pipeline.scheduler.config)

        pipeline.scheduler = scheduler
        # * The pipeline's device is managed by the offloader if enabled.
        # * Manually moving it again conflicts with the offloading mechanism.
        # pipeline.to(device)
        
        # * Cache the compiled pipeline
        _compiled_master_pipeline = pipeline
        console.print("[green]💾 MASTER pipeline cached for reuse[/green]")
        
        return pipeline

    except ImportError as e:
        console.print(f"[red]! Missing dependencies: {e}[/red]")
        console.print("[yellow]Run: pip install diffusers transformers torch[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]! Error setting up master pipeline: {e}[/red]")
        raise typer.Exit(1)


def create_worker_pipeline() -> Any:
    """
    Create a worker pipeline by cloning the compiled master pipeline.
    
    Returns:
        A worker pipeline based on the compiled master
    """
    if _compiled_master_pipeline is None:
        raise ValueError("Master pipeline must be created first")
    
    try:
        import torch
        import copy
        
        # * Create a shallow copy of the master pipeline for this worker
        # ! Deep copy would duplicate the entire model in memory - we want to share weights
        console.print("[*] Creating worker pipeline from compiled master...")
        worker_pipeline = copy.copy(_compiled_master_pipeline)
        
        # * Clone only the critical components that need to be separate per worker
        worker_pipeline.unet = copy.copy(_compiled_master_pipeline.unet)
        worker_pipeline.scheduler = copy.deepcopy(_compiled_master_pipeline.scheduler)
        
        # * Ensure worker is on the correct device
        if torch.cuda.is_available():
            # ! Do not manually move to cuda. The worker pipeline inherits the
            # ! offloading mechanism from the master, which manages device placement.
            pass
        
        console.print("[green]✓ Worker pipeline created from compiled master[/green]")
        return worker_pipeline
        
    except Exception as e:
        console.print(f"[red]! Error creating worker pipeline: {e}[/red]")
        raise


async def _stylize_worker(
    frame_file: Path,
    stylized_dir: Path,
    pipeline: Any,
    prompt: str,
    strength: float,
    inference_steps: int,
    semaphore: asyncio.Semaphore,
    progress: Progress,
    task_id: TaskID,
):
    """
    Worker to stylize a single frame, designed to be run concurrently.
    """
    from PIL import Image
    import torch

    try:
        async with semaphore:
            # Check for cancellation before starting work
            if progress.finished:
                return

            loop = asyncio.get_running_loop()

            # Load image (sync)
            input_image = Image.open(frame_file).convert("RGB")

            # Run blocking ML call in executor to not block the event loop
            func = functools.partial(
                pipeline,
                prompt=prompt,
                image=input_image,
                strength=strength,
                guidance_scale=7.5,
                num_inference_steps=inference_steps,
            )
            result = await loop.run_in_executor(None, func)

            output_file = stylized_dir / f"stylized_{frame_file.name}"
            result.images[0].save(output_file, "PNG")

            # Clear VRAM after each frame
            if hasattr(pipeline, "vae") and torch.cuda.is_available():
                torch.cuda.empty_cache()

            # Update progress
            progress.update(task_id, advance=1)

    except Exception as e:
        console.print(f"[red]\n! Error processing frame {frame_file.name}: {e}[/red]")
        # Propagate the exception to be caught by asyncio.gather
        raise


async def stylize_frames(
    frames_dir: Path,
    stylized_dir: Path,
    pipelines: list[Any],
    prompt: str,
    strength: float = 0.75,
    inference_steps: int = 12,
    progress: Optional[Progress] = None,
    task_id: Optional[TaskID] = None,
) -> bool:
    """
    Stylize extracted frames using Stable Diffusion concurrently.
    """
    try:
        ensure_dir_exists(stylized_dir)
        frame_files = sorted(list(frames_dir.glob("*.png")))
        if not frame_files:
            console.print("[red]! No frames found to stylize[/red]")
            return False

        if not progress or task_id is None:
            console.print("[red]! Progress bar not provided to stylize_frames[/red]")
            return False

        CONCURRENCY_LIMIT = len(pipelines)
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        console.print(
            f"[*] Concurrently processing frames ({CONCURRENCY_LIMIT} at a time)..."
        )

        tasks = [
            _stylize_worker(
                frame_file,
                stylized_dir,
                pipelines[i % CONCURRENCY_LIMIT],
                prompt,
                strength,
                inference_steps,
                semaphore,
                progress,
                task_id,
            )
            for i, frame_file in enumerate(frame_files)
        ]

        # Use gather with a custom loop to enable fail-fast behavior
        try:
            # Create a set of pending tasks
            pending_tasks = {asyncio.create_task(t) for t in tasks}

            while pending_tasks:
                # Wait for any task to complete
                done, pending = await asyncio.wait(
                    pending_tasks, return_when=asyncio.FIRST_COMPLETED
                )

                # Check for exceptions in completed tasks
                for task in done:
                    exc = task.exception()
                    if exc:
                        # If any task has an exception, cancel all others
                        for p_task in pending:
                            p_task.cancel()
                        # Wait for cancellations to propagate
                        if pending:
                            await asyncio.wait(pending)
                        # Re-raise the original exception
                        raise exc

                # Update the set of pending tasks
                pending_tasks = pending

        except asyncio.CancelledError:
            console.print(f"\n[yellow]! Stylization was cancelled by the user.[/yellow]")
            return False
        except Exception:
            # The specific error is already printed in the worker
            console.print(f"\n[red]! A critical error occurred during stylization.[/red]")
            return False
        finally:
            # Ensure all tasks are cleaned up
            all_tasks = asyncio.all_tasks()
            for task in all_tasks:
                if "stylize_worker" in str(task):
                    task.cancel()

        # Final check
        stylized_files = list(stylized_dir.glob("*.png"))
        if len(stylized_files) != len(frame_files):
            console.print(
                f"[yellow]\n! Frame count mismatch. Expected {len(frame_files)}, "
                f"got {len(stylized_files)}. Some frames may have failed.[/yellow]"
            )
            return False

        return True

    except ImportError as e:
        console.print(f"[red]! Missing dependencies: {e}[/red]")
        console.print("[yellow]Run: pip install Pillow torch[/yellow]")
        return False
    except Exception:
        # The specific error is already printed in the worker
        console.print(f"\n[red]! A critical error occurred during stylization.[/red]")
        return False


async def get_video_framerate(input_video: Path) -> float:
    """
    Get video framerate using ffprobe.

    Args:
        input_video: Path to the input video

    Returns:
        Video framerate as float, defaults to 25.0 if detection fails
    """
    try:
        ffprobe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "csv=p=0",
            str(input_video),
        ]

        proc = await asyncio.create_subprocess_exec(
            *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and stdout:
            framerate_str = stdout.decode().strip()
            # Handle fractional framerates like "30000/1001"
            if "/" in framerate_str:
                num, den = framerate_str.split("/")
                framerate = float(num) / float(den)
            else:
                framerate = float(framerate_str)

            console.print(f"[*] Detected framerate: {framerate:.2f} fps")
            return framerate
        else:
            console.print(
                "[yellow]! Could not detect framerate, using 25.0 fps[/yellow]"
            )
            return 25.0

    except Exception as e:
        console.print(
            f"[yellow]! Error detecting framerate: {e}, using 25.0 fps[/yellow]"
        )
        return 25.0


async def reassemble_video(
    frames_dir: Path, output_path: Path, input_video: Path
) -> bool:
    """
    Reassemble frames into video using ffmpeg with HEVC CQ=26.

    Args:
        frames_dir: Directory containing frames to reassemble
        output_path: Output video file path
        input_video: Original input video for framerate detection

    Returns:
        True if successful, False otherwise
    """
    try:
        # * Get list of frame files and ensure they exist
        frame_files = sorted(list(frames_dir.glob("*.png")))
        if not frame_files:
            console.print("[red]! No frames found for video reassembly[/red]")
            return False

        console.print(f"[*] Reassembling {len(frame_files)} frames into video...")

        # * Get source video framerate
        framerate = await get_video_framerate(input_video)

        # * Build ffmpeg command for HEVC encoding with CQ=26
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-framerate",
            str(framerate),
            "-i",
            str(frames_dir / "stylized_%06d.png"),  # Input pattern
            "-c:v",
            "libx265",  # HEVC codec
            "-crf",
            "26",  # Constant Quality 26
            "-preset",
            "medium",  # Encoding preset
            "-pix_fmt",
            "yuv420p",  # Pixel format for compatibility
            "-movflags",
            "+faststart",  # Web optimization
            str(output_path),
        ]

        console.print("[*] Encoding with HEVC CQ=26...")

        # * Run ffmpeg command
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            console.print(
                f"[red]! FFmpeg error during reassembly: {stderr.decode()}[/red]"
            )
            return False

        console.print("[green]✓ Video reassembled successfully[/green]")
        return True

    except Exception as e:
        console.print(f"[red]! Error during video reassembly: {e}[/red]")
        return False


async def upscale_frames_realesrgan(stylized_dir: Path, upscaled_dir: Path) -> bool:
    """
    Upscale stylized frames using Real-ESRGAN.

    Args:
        stylized_dir: Directory containing stylized frames
        upscaled_dir: Directory to save upscaled frames

    Returns:
        True if successful, False otherwise
    """
    try:
        # * Ensure output directory exists
        ensure_dir_exists(upscaled_dir)

        # * Get list of stylized frame files
        frame_files = sorted(list(stylized_dir.glob("*.png")))
        if not frame_files:
            console.print("[red]! No stylized frames found for upscaling[/red]")
            return False

        console.print(f"[*] Upscaling {len(frame_files)} frames with Real-ESRGAN...")

        # * Try to import Real-ESRGAN
        try:
            from realesrgan import RealESRGANer
            from realesrgan.archs.srvgg_arch import SRVGGNetCompact
            import cv2
        except ImportError as e:
            console.print(f"[red]! Missing Real-ESRGAN dependencies: {e}[/red]")
            console.print("[yellow]Run: pip install realesrgan opencv-python[/yellow]")
            return False

        # * Initialize Real-ESRGAN upscaler
        # * Use RealESRGAN_x4plus for 4x upscaling
        model = SRVGGNetCompact(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_conv=32,
            upscale=4,
            act_type="prelu",
        )

        upsampler = RealESRGANer(
            scale=4,
            model_path="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            model=model,
            tile=0,
            tile_pad=10,
            pre_pad=0,
            half=True,  # * Use FP16 for faster processing and lower VRAM usage
        )

        # * Process each frame
        for i, frame_file in enumerate(frame_files):
            console.print(
                f"[*] Upscaling frame {i+1}/{len(frame_files)}: {frame_file.name}"
            )

            # * Load image
            img = cv2.imread(str(frame_file), cv2.IMREAD_COLOR)

            # * Upscale with Real-ESRGAN
            output, _ = upsampler.enhance(img, outscale=4)

            # * Save upscaled frame
            output_file = upscaled_dir / f"upscaled_{frame_file.name}"
            cv2.imwrite(str(output_file), output)

        console.print(
            f"[green]✓ Successfully upscaled {len(frame_files)} frames[/green]"
        )
        return True

    except Exception as e:
        console.print(f"[red]! Error during Real-ESRGAN upscaling: {e}[/red]")
        return False


async def run_stylization(
    input_video: Path,
    prompt: str,
    model_id: str,
    controlnet_id: Optional[str],
    use_animatediff: bool,
    strength: float,
    inference_steps: int,
    scheduler: str,
    upscale: bool,
    output: Path,
    max_resolution: str,
    test_mode: bool,
    work_dir: Optional[Path] = None,
):
    """
    Run the asynchronous stylization pipeline.
    """
    console.print("[bold cyan]Starting video stylization...[/bold cyan]")
    console.print(f"Input: [yellow]{input_video}[/yellow]")
    console.print(f"Prompt: [green]'{prompt}'[/green]")
    console.print(f"Model: [blue]{model_id}[/blue]")

    # * Create temporary directories; allow custom work_dir to host temp files
    temp_dir_kwargs: dict[str, Any] = {"prefix": "stylizer_"}
    if work_dir:
        temp_dir_kwargs["dir"] = work_dir
    with tempfile.TemporaryDirectory(**temp_dir_kwargs) as temp_dir:
        temp_path = Path(temp_dir)
        frames_dir = temp_path / "frames"
        stylized_dir = temp_path / "stylized_frames"
        upscaled_dir = temp_path / "upscaled_frames"
        final_frames_dir = stylized_dir  # Will be upscaled_dir if upscaling enabled

        console.print(f"[dim]Working directory: {temp_path}[/dim]")

        # * Step 1: Extract frames
        console.print("\n[bold]Step 1: Extracting frames[/bold]")
        success = await extract_frames(input_video, frames_dir, max_resolution, test_mode)
        if not success:
            console.print("[red]! Failed to extract frames[/red]")
            raise typer.Exit(1)

        # * Step 2: Set up master pipeline and create workers
        CONCURRENCY_LIMIT = 2
        console.print(
            f"\n[bold]Step 2: Setting up master pipeline and {CONCURRENCY_LIMIT} worker pipelines[/bold]"
        )
        
        # * Create and compile the master pipeline first
        master_pipeline = setup_master_compiled_pipeline(model_id, scheduler)
        
        # * Create worker pipelines from the compiled master
        pipelines = [create_worker_pipeline() for _ in range(CONCURRENCY_LIMIT)]
        # * Optional: ControlNet support (stub)
        if controlnet_id:
            console.print(
                f"[yellow]! ControlNet support not yet implemented (controlnet_id={controlnet_id})[/yellow]"
            )
        # * Optional: AnimateDiff support (stub)
        if use_animatediff:
            console.print(
                "[yellow]! AnimateDiff support not yet implemented (use_animatediff enabled)[/yellow]"
            )

        # * Step 3: Stylize frames
        console.print("\n[bold]Step 3: Stylizing frames[/bold]")
        console.print(f"[*] Prompt: '{prompt}'")
        console.print(f"[*] Strength: {strength}")

        with Progress() as progress_bar:
            task = progress_bar.add_task(
                "Stylizing frames...", total=len(list(frames_dir.glob("*.png")))
            )
            success = await stylize_frames(
                frames_dir, stylized_dir, pipelines, prompt, strength, inference_steps, progress_bar, task
            )
            if not success:
                console.print("[red]! Failed to stylize frames[/red]")
                raise typer.Exit(1)

        # * Step 4: Upscaling (optional)
        if upscale:
            console.print("\n[bold]Step 4: Upscaling frames (Real-ESRGAN)[/bold]")
            success = await upscale_frames_realesrgan(stylized_dir, upscaled_dir)
            if success:
                final_frames_dir = upscaled_dir
            else:
                console.print(
                    "[yellow]! Real-ESRGAN upscaling failed, using stylized frames without upscaling[/yellow]"
                )
        else:
            console.print("\n[dim]Skipping upscaling (--upscale not enabled)[/dim]")

        # * Step 5: Reassemble video
        console.print("\n[bold]Step 5: Reassembling video[/bold]")
        success = await reassemble_video(final_frames_dir, output, input_video)
        if not success:
            console.print("[red]! Failed to reassemble video[/red]")
            raise typer.Exit(1)

        console.print("\n[bold green]✓ Video stylization completed![/bold green]")
        console.print(f"[green]Output saved to: {output}[/green]")


@app.command()
def stylize(
    input_video: Annotated[Optional[Path], typer.Argument(help="Input video file.")] = None,
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="Text prompt for stylization.")] = None,
    model_id: Annotated[
        str,
        typer.Option(
            "--model-id", "-m", help="Hugging Face model ID for Stable Diffusion (e.g., stabilityai/stable-diffusion-2-base)."
        ),
    ] = "stabilityai/stable-diffusion-2-base",
    controlnet_id: Annotated[
        Optional[str],
        typer.Option(
            "--controlnet-id", "-c", help="Hugging Face model ID for ControlNet (optional)."
        ),
    ] = None,
    use_animatediff: Annotated[
        bool,
        typer.Option(
            "--animatediff", help="Enable AnimateDiff for temporal consistency."
        ),
    ] = False,
    strength: Annotated[
        Optional[float],
        typer.Option(
            "--strength", "-s", min=0.0, max=1.0, help="Stylization strength (0.0-1.0)."
        ),
    ] = None,
    inference_steps: Annotated[
        Optional[int],
        typer.Option("--steps", help="Number of inference steps for Stable Diffusion."),
    ] = None,
    scheduler: Annotated[
        str,
        typer.Option(
            "--scheduler",
            help="Scheduler to use: UniPC, DDIM, EulerA, DPM2M.",
        ),
    ] = "UniPC",
    upscale: Annotated[
        bool, typer.Option("--upscale", help="Enable Real-ESRGAN 4x upscaling to FHD.")
    ] = False,  # * Changed default to False since Real-ESRGAN is heavy
    output: Annotated[
        Optional[Path], typer.Option("--output", "-o", help="Output video file path.")
    ] = None,
    max_resolution: Annotated[
        str,
        typer.Option(
            "--max-res",
            help="Maximum resolution for processing (e.g., '480p', '720p').",
        ),
    ] = "480p",
    work_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--work-dir", "-w", help="Directory for temporary files (defaults to system temp)."
        ),
    ] = None,
    test_mode: Annotated[
        bool,
        typer.Option(
            "--test-mode",
            help="Enable test mode (process first 2 seconds only).",
        ),
    ] = False,
):
    """
    Stylize a video using Stable Diffusion and optionally upscale with Real-ESRGAN.

    The process involves:
    1. Extract frames from video at specified resolution
    2. Stylize frames using Stable Diffusion
    3. Optionally upscale frames using Real-ESRGAN
    4. Reassemble video with HEVC encoding
    """
    # * Interactive prompt for input video
    if input_video is None:
        input_video = prompt_for_path(
            "Enter input video file:",
            default=None,
            must_exist=True,
            file_okay=True,
            dir_okay=False,
        )
    # * Validate input file exists
    if not input_video.exists():
        console.print(f"[red]! Error: Input video not found: {input_video}[/red]")
        raise typer.Exit(1)

    # * Interactive prompt for stylization prompt
    if prompt is None:
        prompt = typer.prompt("Enter text prompt for stylization:")
    # * Ensure prompt is set
    assert prompt is not None

    # * --- Interactive Settings Menu ---
    # * We handle sliders separately as the generic function doesn't support them
    final_strength = strength
    if final_strength is None:
        final_strength = typer.prompt(
            "Enter stylization strength (0.0 to 1.0)", type=float, default=0.75
        )
    # * Validate strength
    if not (0.0 <= final_strength <= 1.0):
        console.print(
            f"[red]! Invalid strength: {final_strength}. Must be between 0.0 and 1.0.[/red]"
        )
        final_strength = 0.75

    final_steps = inference_steps
    if final_steps is None:
        final_steps = typer.prompt(
            "Enter number of inference steps (e.g., 8-20)", type=int, default=12
        )

    settings_definitions = [
        {
            "key": "scheduler",
            "label": "Scheduler",
            "type": "choice",
            "choices": {
                "UniPC": "UniPC",
                "DDIM": "DDIM",
                "EulerA": "EulerA",
                "DPM2M": "DPM2M",
            },
        },
        {"key": "upscale", "label": "4x Upscaling (Real-ESRGAN)", "type": "toggle"},
        {"key": "test_mode", "label": "Test Mode (First 2s)", "type": "toggle"},
    ]

    # * Get initial values from CLI or defaults for non-slider settings
    current_settings = {
        "scheduler": scheduler,
        "upscale": upscale,
        "test_mode": test_mode,
    }

    # * Launch interactive menu for toggles and choices
    # * We enter interactive mode if the script is run without flags.
    is_interactive = not (
        strength or inference_steps or upscale or test_mode or scheduler != "UniPC"
    )

    final_settings = None
    if is_interactive:
        final_settings = prompt_for_interactive_settings(
            settings_definitions, current_settings, title="Stylizer Settings"
        )
        if final_settings is None:
            console.print("[yellow]! Operation cancelled by user.[/yellow]")
            raise typer.Exit()
    else:
        final_settings = current_settings

    # * Extract final values
    final_scheduler = str(final_settings["scheduler"])
    final_upscale = bool(final_settings["upscale"])
    final_test_mode = bool(final_settings["test_mode"])

    # * Set up output path
    if output is None:
        output = input_video.parent / f"{input_video.stem}_stylized.mp4"

    console.print(f"Output: [yellow]{output}[/yellow]")

    # * Run the async pipeline
    asyncio.run(
        run_stylization(
            input_video,
            prompt,
            model_id,
            controlnet_id,
            use_animatediff,
            final_strength,
            final_steps,
            final_scheduler,
            final_upscale,
            output,
            max_resolution,
            final_test_mode,
            work_dir,
        )
    )


if __name__ == "__main__":
    app()
