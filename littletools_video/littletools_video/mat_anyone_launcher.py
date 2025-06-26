import typer
from rich.console import Console
import sys
from pathlib import Path
import os

# * This is a workaround to make the `matanyone` package importable
# Add the parent directory of `mat_anyone` to the python path
# The structure is littletools_video/littletools_video/mat_anyone
# So we add littletools_video/littletools_video/
package_dir = Path(__file__).parent
# Add the core library directory to the path so `import matanyone` works
sys.path.insert(0, str(package_dir / "mat_anyone"))
# Also add the main package directory for `mat_anyone` imports
sys.path.insert(0, str(package_dir))

# Also need to set the working directory for the Gradio app,
# as it might expect to be run from its own directory to find assets.
hugging_face_dir = package_dir / "mat_anyone" / "hugging_face"


app = typer.Typer(
    name="mat-anyone",
    help="""
    🖼️ Launch the MatAnyone Gradio UI for advanced video matting.
    
    This tool provides an interactive interface to select objects in a video
    and generate a high-quality alpha matte, separating the foreground
    from the background.
    """,
    no_args_is_help=True
)
console = Console()

@app.command()
def launch():
    """
    Starts the Gradio web interface for MatAnyone.
    """
    console.print("[bold cyan]Launching MatAnyone Gradio UI...[/bold cyan]")
    console.print("[*] The web interface will open in your default browser.")
    console.print("[*] Press [bold]Ctrl+C[/bold] in this terminal to stop the server.")

    # Change CWD for the Gradio app to load assets correctly
    original_cwd = os.getcwd()
    os.chdir(hugging_face_dir)
    
    try:
        # Now that the path is set up, we can import the app
        from mat_anyone.hugging_face.app import demo
        
        # The demo object from app.py is a Gradio Blocks instance
        # We launch it here with proper blocking to keep CLI control
        import signal
        import sys
        import atexit
        
        def signal_handler(sig, frame):
            console.print("\n[yellow]! Server stopped by user.[/yellow]")
            cleanup_and_exit(demo)
        
        def cleanup_and_exit(demo_instance):
            """Clean up and exit properly"""
            try:
                demo_instance.close()
                console.print("Gradio server closed.")
            except Exception as e:
                console.print(f"[dim]Error closing Gradio: {e}[/dim]")
            
            # Force cleanup of any remaining processes
            try:
                import psutil
                current_pid = os.getpid()
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['pid'] == current_pid:
                            continue
                        if proc.info['name'] and 'python' in proc.info['name'].lower():
                            cmdline = proc.info['cmdline']
                            if cmdline and any('gradio' in str(arg).lower() or 'mat_anyone' in str(arg).lower() for arg in cmdline):
                                proc.terminate()
                                try:
                                    proc.wait(timeout=2)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except ImportError:
                pass
            
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        atexit.register(lambda: cleanup_and_exit(demo))
        
        demo.launch(
            inbrowser=True, 
            share=False, 
            prevent_thread_lock=False,  # Allow proper CLI integration
            show_error=True,
            quiet=False
        )
        
    except KeyboardInterrupt:
        console.print("\n[yellow]! Server stopped by user.[/yellow]")
        try:
            demo.close()
        except:
            pass
    except ImportError as e:
        console.print(f"[red]! Failed to import the Gradio application.[/red]")
        console.print(f"[dim]  Error: {e}[/dim]")
        console.print(f"[dim]  Please ensure the MatAnyone files are correctly placed in '{package_dir}/mat_anyone'[/dim]")
    except Exception as e:
        console.print(f"[red]! An unexpected error occurred while launching the UI: {e}[/red]")
    finally:
        # Restore CWD
        os.chdir(original_cwd)
        console.print("\n[bold]MatAnyone UI server has been shut down.[/bold]")

if __name__ == "__main__":
    app() 