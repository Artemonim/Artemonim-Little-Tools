#!/usr/bin/env python3
"""
LittleTools Environment Setup and Execution Menu

This script provides an interactive menu to set up dependencies and run tools
in the LittleTools project. It uses a single virtual environment and automatically
processes files from 0-INPUT-0 to 0-OUTPUT-0 where applicable.

Usage:
    python menu.py

Features:
    - Interactive menu for tool selection
    - Single virtual environment management
    - Selective dependency installation
    - Automatic file processing (0-INPUT-0 → 0-OUTPUT-0)
    - Tool execution with automatic path handling
    - Source file cleanup options
    - Compact mode for denser terminal output
"""

import os
import sys
import subprocess
import platform
import json
import glob
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import signal  # * Better Comments: signal handling for cleanup

# * Configuration variables
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_DIR = SCRIPT_DIR / ".venv"
CONFIG_FILE = SCRIPT_DIR / "setup_config.json"
INPUT_DIR = SCRIPT_DIR / "0-INPUT-0"
OUTPUT_DIR = SCRIPT_DIR / "0-OUTPUT-0"

# * Tool definitions
TOOLS = {
    "telegram_distiller": {
        "name": "Telegram Chats Distiller",
        "description": "Process Telegram chat export JSON files",
        "path": "TxtTools",
        "script": "Telegram_Chats_Distiller.py",
        "requirements_file": "requirements_telegram_distiller.txt",
        "system_deps": [],
        "supports_batch": True,
        "input_extensions": [".json"],
        "output_extension": "_distilled.json",
        "args_template": ["-i", "{input_file}", "-o", "{output_file}"],
        "needs_dependencies": False
    },
    "infinite_differ": {
        "name": "Infinite Differ (Multiple Text Comparator)",
        "description": "Compare multiple text files simultaneously with GUI",
        "path": "TxtTools/MultipleTextComparator",
        "script": "Infinite_Differ.py",
        "requirements_file": "requirements_infinite_differ.txt",
        "system_deps": [],
        "supports_batch": False,
        "input_extensions": [".txt", ".md", ".py", ".js", ".html", ".css"],
        "output_extension": None,
        "args_template": [],
        "needs_dependencies": True
    },
    "wmd_converter": {
        "name": "Word-Markdown Converter",
        "description": "Convert between DOCX and Markdown formats",
        "path": "TxtTools/WMDconverter",
        "script": "WMDconverter.py",
        "requirements_file": "requirements_wmd_converter.txt",
        "system_deps": ["pandoc"],
        "supports_batch": True,
        "input_extensions": [".docx", ".md"],
        "output_extension": None,
        "args_template": ["--source", "{input_file}", "--output", "{output_file}", "--media-dir", "{media_dir}"],
        "needs_dependencies": True
    },
    "ffmpeg_normalizer": {
        "name": "FFMPEG MKV Audio Normalizer",
        "description": "Normalize audio tracks in MKV files. Script processes entire input dir.",
        "path": "VideoTools",
        "script": "FFMPEG_MKV_audio_normalizer_v2.py",
        "requirements_file": "requirements_video_tools.txt",
        "system_deps": ["ffmpeg", "ffprobe"],
        "supports_batch": True,
        "input_extensions": [".mkv"],
        "output_extension": "_normalized.mkv",
        "args_template": ["-i", "{input_dir}", "-o", "{output_dir}"],
        "needs_dependencies": False,
        "batch_takes_dir_input": True
    },
    "topaz_merger": {
        "name": "Topaz Video Merger",
        "description": "Dual-input video/audio normalizer and merger",
        "path": "VideoTools",
        "script": "Topaz_Video_Merger.py",
        "requirements_file": "requirements_video_tools.txt",
        "system_deps": ["ffmpeg", "ffprobe"],
        "supports_batch": False,
        "input_extensions": [".mkv", ".mp4", ".avi"],
        "output_extension": "_merged.mkv",
        "args_template": ["-i1", "{primary_input}", "-i2", "{video_input}", "-o", "{output_dir}"],
        "needs_dependencies": False
    },
    "whisper_transcriber": {
        "name": "Whisper Audio/Video Transcriber",
        "description": "Transcribe audio/video files using OpenAI Whisper. Processes entire input dir.",
        "path": "Audio-_Video-2-Text",
        "script": "whisper_transcriber.py",
        "requirements_file": "Audio-_Video-2-Text/requirements_whisper_transcriber.txt",
        "system_deps": ["ffmpeg"],
        "supports_batch": True,
        "batch_takes_dir_input": True,
        "input_extensions": [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".mkv", ".mov", ".avi", ".webm"],
        "output_extension": ".txt",
        "args_template": ["-i", "{input_dir}", "-o", "{output_dir}", "--model", "large-v3-turbo"],
        "needs_dependencies": True
    }
}

# Global state for tracking current installation
_current_installation = {
    "tool_id": None,
    "packages_installed": [],
    "python_exe": None,
    "in_progress": False
}

# Handle Ctrl+C to rollback current installation only
def _signal_handler(signum, frame):
    if _current_installation["in_progress"]:
        print("\n* Installation interrupted by user. Rolling back current installation...")
        _rollback_current_installation()
    else:
        print("\n* Operation interrupted by user.")
    sys.exit(1)

def _rollback_current_installation():
    """Rollback packages installed during current session."""
    if not _current_installation["packages_installed"] or not _current_installation["python_exe"]:
        print("* No packages to rollback.")
        return
    
    python_exe = _current_installation["python_exe"]
    packages = _current_installation["packages_installed"]
    tool_id = _current_installation["tool_id"]
    
    print(f"* Uninstalling {len(packages)} package(s) for {tool_id}...")
    for package in packages:
        try:
            subprocess.run([python_exe, "-m", "pip", "uninstall", "-y", package], 
                         check=True, capture_output=True, text=True)
            print(f"  ✓ Uninstalled: {package}")
        except subprocess.CalledProcessError as e:
            print(f"  ! Failed to uninstall {package}: {e}")
    
    # Clear tracking
    _current_installation["packages_installed"].clear()
    _current_installation["tool_id"] = None
    _current_installation["in_progress"] = False

signal.signal(signal.SIGINT, _signal_handler)

def clear_screen_if_compact(is_compact: bool):
    """Clears the terminal screen if compact mode is enabled."""
    if is_compact:
        os.system('cls' if platform.system() == "Windows" else 'clear')


class ToolManager:
    """Manages the setup and execution of LittleTools."""
    
    def __init__(self):
        """Initialize the tool manager."""
        self.config = self.load_config()
        self.ensure_directories()
        self.initialize_default_tools()
        
    def load_config(self) -> Dict:
        """Load setup configuration from file."""
        default_config = {
            "installed_tools": [],
            "last_update": None,
            "compact_mode": True
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    for key, value in default_config.items():
                        if key not in loaded_config:
                            loaded_config[key] = value
                    return loaded_config
            except (json.JSONDecodeError, FileNotFoundError):
                pass 
        return default_config
    
    def save_config(self):
        """Save setup configuration to file."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"! Warning: Could not save config: {e}")
    
    def ensure_directories(self):
        INPUT_DIR.mkdir(exist_ok=True)
        OUTPUT_DIR.mkdir(exist_ok=True)
    
    def initialize_default_tools(self):
        for tool_id, tool in TOOLS.items():
            if not tool["needs_dependencies"] and tool_id not in self.config["installed_tools"]:
                if self.check_all_system_dependencies(tool_id):
                    self.config["installed_tools"].append(tool_id)
        self.save_config()
    
    def check_python_venv(self) -> bool:
        try:
            subprocess.run([sys.executable, "-m", "venv", "--help"], 
                         capture_output=True, check=True, text=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def check_system_dependency(self, dep_name: str) -> bool:
        try:
            result = subprocess.run([dep_name, "--version"], capture_output=True, check=False, text=True)
            if result.returncode == 0: return True
            result = subprocess.run([dep_name, "-version"], capture_output=True, check=False, text=True)
            if result.returncode == 0: return True
            subprocess.run([dep_name], capture_output=True, check=False, text=True)
            return True 
        except FileNotFoundError:
            if platform.system() == "Windows":
                try:
                    result = subprocess.run([f"{dep_name}.exe", "--version"], capture_output=True, check=False, text=True)
                    return result.returncode == 0
                except FileNotFoundError: pass
            return False
        except subprocess.CalledProcessError: 
             return True 
        return False

    def check_all_system_dependencies(self, tool_id: str) -> bool:
        tool = TOOLS[tool_id]
        for dep in tool["system_deps"]:
            if not self.check_system_dependency(dep):
                return False
        return True
    
    def create_venv(self) -> bool:
        """Creates virtual environment with proper pip installation."""
        if VENV_DIR.exists():
            return True
        print("* Creating virtual environment...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR), "--upgrade-deps"], 
                         check=True, text=True)
            print(f"* Virtual environment created: {VENV_DIR}")
            
            # Verify pip is available
            if not self.verify_and_fix_pip():
                return False
                
            return True
        except subprocess.CalledProcessError as e:
            print(f"! Failed to create virtual environment: {e}")
            return False
    
    def verify_and_fix_pip(self) -> bool:
        """Verifies pip is available in venv and attempts to fix if missing."""
        python_exe = self.get_venv_python()
        if not python_exe:
            print("! Virtual environment Python not found.")
            return False
        
        # Check if pip is available
        try:
            subprocess.run([python_exe, "-m", "pip", "--version"], 
                         capture_output=True, check=True, text=True)
            return True
        except subprocess.CalledProcessError:
            print("! pip not found in virtual environment. Attempting to bootstrap...")
            
            # Try to bootstrap pip using ensurepip
            try:
                subprocess.run([python_exe, "-m", "ensurepip", "--upgrade"], 
                             check=True, text=True, capture_output=True)
                print("* pip bootstrapped successfully.")
                
                # Verify pip works now
                subprocess.run([python_exe, "-m", "pip", "--version"], 
                             capture_output=True, check=True, text=True)
                return True
            except subprocess.CalledProcessError as e:
                print(f"! Failed to bootstrap pip: {e}")
                print("  Please try recreating the virtual environment:")
                print(f"  1. Delete the {VENV_DIR} directory")
                print("  2. Run this script again")
                print("  Or use the start.ps1 script with -Force option")
                return False
    
    def get_venv_python(self) -> Optional[str]:
        suffix = "Scripts/python.exe" if platform.system() == "Windows" else "bin/python"
        python_exe = VENV_DIR / suffix
        return str(python_exe) if python_exe.exists() else None
    
    def install_tool_dependencies(self, tool_id: str) -> bool:
        """Installs Python dependencies for a tool."""
        tool = TOOLS[tool_id]
        if not tool["needs_dependencies"]:
            if tool_id not in self.config["installed_tools"]:
                if self.check_all_system_dependencies(tool_id):
                     self.config["installed_tools"].append(tool_id)
                     self.save_config()
            return True
        
        requirements_path = SCRIPT_DIR / tool["requirements_file"]
        if not requirements_path.exists():
            print(f"! Requirements file not found: {requirements_path}")
            return False
        
        with open(requirements_path, 'r', encoding='utf-8') as f:
            if not any(line.strip() and not line.strip().startswith('#') for line in f):
                if tool_id not in self.config["installed_tools"]:
                     if self.check_all_system_dependencies(tool_id):
                        self.config["installed_tools"].append(tool_id)
                        self.save_config()
                return True
        
        if not self.create_venv(): 
            return False
            
        python_exe = self.get_venv_python()
        if not python_exe:
            print("! Virtual environment Python not found.")
            return False
        
        # Verify pip is working before attempting installation
        if not self.verify_and_fix_pip():
            print("! Cannot proceed with dependency installation - pip is not available.")
            return False
        
        # Initialize installation tracking
        global _current_installation
        _current_installation["tool_id"] = tool_id
        _current_installation["python_exe"] = python_exe
        _current_installation["packages_installed"] = []
        _current_installation["in_progress"] = True
        
        try:
            # Upgrade pip, setuptools, and wheel first to avoid build issues
            try:
                print(f"* Upgrading pip, setuptools, and wheel for {tool['name']}...")
                subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], 
                             check=True, text=True, capture_output=True)
                print("* Build tools upgraded successfully.")
            except subprocess.CalledProcessError as e:
                print(f"! Warning: Failed to upgrade build tools: {e.stderr if e.stderr else e.stdout}")
                print("  Continuing with installation anyway...")
            
            # GPU-only specialized installation for Whisper Transcriber
            if tool_id == 'whisper_transcriber':
                try:
                    print(f"* Installing GPU PyTorch for {tool['name']}...")
                    subprocess.run([
                        python_exe, "-m", "pip", "install", "--no-cache-dir",
                        "torch==2.7.0+cu118", "torchaudio==2.7.0+cu118",
                        "--extra-index-url", "https://download.pytorch.org/whl/cu118"
                    ], check=True, text=True, capture_output=True)
                    _current_installation["packages_installed"].extend(["torch", "torchaudio"])
                    
                    print(f"* Installing openai-whisper from GitHub for {tool['name']} (temporary workaround)...")
                    subprocess.run([
                        python_exe, "-m", "pip", "install", "--no-cache-dir", "git+https://github.com/openai/whisper.git"
                    ], check=True, text=True, capture_output=True)
                    _current_installation["packages_installed"].append("openai-whisper")
                    
                    print(f"* Installing ffmpeg-python for {tool['name']}...")
                    subprocess.run([
                        python_exe, "-m", "pip", "install", "--no-cache-dir", "ffmpeg-python>=0.2.0"
                    ], check=True, text=True, capture_output=True)
                    _current_installation["packages_installed"].append("ffmpeg-python")
                    
                    print(f"* Dependencies installed successfully for {tool['name']}.")
                    if tool_id not in self.config["installed_tools"]:
                        self.config["installed_tools"].append(tool_id)
                        self.save_config()
                    
                    # Clear tracking on success
                    _current_installation["in_progress"] = False
                    _current_installation["packages_installed"].clear()
                    return True
                except subprocess.CalledProcessError as e:
                    print(f"! Failed GPU-specialized install for {tool['name']}: {e.stderr.strip() if e.stderr else e.stdout.strip()}")
                    print("  Rolling back installed packages...")
                    _rollback_current_installation()
                    return False
            
            # Generic install via requirements file
            print(f"* Installing dependencies for {tool['name']} from {tool['requirements_file']}...")
            
            # Parse requirements to track individual packages
            with open(requirements_path, 'r', encoding='utf-8') as f:
                requirements_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
            # Extract package names for tracking
            for req_line in requirements_lines:
                # Extract package name (before ==, >=, etc.)
                package_name = req_line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('!')[0].strip()
                if package_name:
                    _current_installation["packages_installed"].append(package_name)
            
            # Prepare pip install command
            install_cmd = [python_exe, "-m", "pip", "install", "--no-cache-dir", "-r", str(requirements_path)]
            subprocess.run(install_cmd, check=True, text=True, capture_output=True)
            print(f"* Dependencies installed successfully for {tool['name']}.")
            if tool_id not in self.config["installed_tools"]:
                self.config["installed_tools"].append(tool_id)
                self.save_config()
            
            # Clear tracking on success
            _current_installation["in_progress"] = False
            _current_installation["packages_installed"].clear()
            return True
            
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else e.stdout
            print(f"! Failed to install dependencies for {tool['name']}:\n{error_output.strip()}")
            print("  Rolling back installed packages...")
            _rollback_current_installation()
            print("  This might be due to:\n  - Network connectivity issues\n  - Package compatibility problems\n  - Insufficient disk space\n  - Build tool version conflicts\n  Try running installation again or check error details above.")
            return False
        except KeyboardInterrupt:
            # Signal handler will handle the rollback
            raise
    
    def setup_tool(self, tool_id: str) -> bool:
        tool = TOOLS[tool_id]
        print(f"\n--- Setting up: {tool['name']} ---")
        
        missing_sys_deps = [dep for dep in tool["system_deps"] if not self.check_system_dependency(dep)]
        if missing_sys_deps:
            print(f"! Missing system dependencies: {', '.join(missing_sys_deps)}")
            print("  Please install them manually and try setup again.")
            return False
        
        if not self.install_tool_dependencies(tool_id): return False
        
        print(f"* {tool['name']} setup check completed.")
        return True
    
    def uninstall_tool(self, tool_id: str) -> bool:
        tool = TOOLS[tool_id]
        if tool_id not in self.config["installed_tools"]:
            print(f"* {tool['name']} was not marked as installed.")
            return False
        
        if not tool["needs_dependencies"]:
            self.config["installed_tools"].remove(tool_id)
            self.save_config()
            print(f"* {tool['name']} removed from installed tools list (no Python dependencies to uninstall).")
            return True
        
        python_exe = self.get_venv_python()
        if not python_exe:
            print(f"! Virtual environment not found. Removing {tool['name']} from installed tools list only.")
            self.config["installed_tools"].remove(tool_id)
            self.save_config()
            return True
        
        # Get packages to uninstall based on tool
        packages_to_uninstall = []
        if tool_id == 'whisper_transcriber':
            packages_to_uninstall = ["torch", "torchaudio", "openai-whisper", "ffmpeg-python"]
            
            # Also remove Whisper models directory if it exists
            models_dir = SCRIPT_DIR / "Audio-_Video-2-Text" / "models"
            if models_dir.exists():
                try:
                    shutil.rmtree(models_dir)
                    print(f"  ✓ Removed Whisper models directory: {models_dir}")
                except Exception as e:
                    print(f"  ! Warning: Could not remove models directory '{models_dir}': {e}")
        else:
            # Parse requirements file to get package names
            requirements_path = SCRIPT_DIR / tool["requirements_file"]
            if requirements_path.exists():
                with open(requirements_path, 'r', encoding='utf-8') as f:
                    requirements_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
                for req_line in requirements_lines:
                    # Extract package name (before ==, >=, etc.)
                    package_name = req_line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('!')[0].strip()
                    if package_name:
                        packages_to_uninstall.append(package_name)
        
        if not packages_to_uninstall:
            print(f"* No packages identified for uninstallation for {tool['name']}.")
            self.config["installed_tools"].remove(tool_id)
            self.save_config()
            return True
        
        print(f"* Uninstalling Python dependencies for {tool['name']}...")
        print(f"  Packages to remove: {', '.join(packages_to_uninstall)}")
        
        uninstalled_count = 0
        for package in packages_to_uninstall:
            try:
                result = subprocess.run([python_exe, "-m", "pip", "uninstall", "-y", package], 
                                     check=True, capture_output=True, text=True)
                print(f"  ✓ Uninstalled: {package}")
                uninstalled_count += 1
            except subprocess.CalledProcessError:
                # Package might not be installed, which is fine
                print(f"  - Skipped: {package} (not installed or already removed)")
        
        self.config["installed_tools"].remove(tool_id)
        self.save_config()
        print(f"* {tool['name']} uninstalled successfully ({uninstalled_count} packages removed).")
        return True
    
    def is_tool_ready(self, tool_id: str) -> bool:
        tool = TOOLS[tool_id]
        py_deps_met = True
        if tool["needs_dependencies"]:
            py_deps_met = tool_id in self.config["installed_tools"]
        
        sys_deps_met = self.check_all_system_dependencies(tool_id)
        return py_deps_met and sys_deps_met
    
    def get_input_files(self, tool_id: str) -> List[Path]:
        tool = TOOLS[tool_id]
        return sorted([Path(f) for ext in tool["input_extensions"] for f in glob.glob(str(INPUT_DIR / f"*{ext}"))])

    def run_tool_on_file(self, tool_id: str, input_file: Path, output_file_override: Optional[Path] = None) -> bool:
        tool = TOOLS[tool_id]
        script_path = SCRIPT_DIR / tool["path"] / tool["script"]
        
        if not script_path.exists():
            print(f"! Script {script_path.name} not found in {tool['path']}")
            return False
        
        python_exe = self.get_venv_python() or sys.executable
        
        if output_file_override:
            actual_output_file = output_file_override
        elif tool.get("output_extension"):
            actual_output_file = OUTPUT_DIR / f"{input_file.stem}{tool['output_extension']}"
        elif tool_id == "wmd_converter":
             actual_output_file = OUTPUT_DIR / f"{input_file.stem}{'.md' if input_file.suffix.lower() == '.docx' else '.docx'}"
        else:
            actual_output_file = OUTPUT_DIR / input_file.name
        
        args = []
        for arg_template_part in tool["args_template"]:
            if arg_template_part == "{input_file}":
                args.append(str(input_file))
            elif arg_template_part == "{output_file}":
                args.append(str(actual_output_file))
            elif arg_template_part == "{media_dir}" and tool_id == "wmd_converter":
                args.append(str(OUTPUT_DIR / f"{input_file.stem}_media"))
            else:
                args.append(arg_template_part)
        
        cmd = [python_exe, str(script_path)] + args
        
        try:
            original_cwd = os.getcwd()
            os.chdir(SCRIPT_DIR) 
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✓ Success: {input_file.name} → {actual_output_file.name}")
                return True
            else:
                print(f"  ✗ Failed {input_file.name}. Error:\n    {result.stderr.strip() or result.stdout.strip() or 'No output'}")
                return False
        except Exception as e:
            print(f"  ✗ Error executing {script_path.name} on {input_file.name}: {e}")
            return False
        finally:
            os.chdir(original_cwd)

    def run_tool_batch(self, tool_id: str) -> Tuple[bool, str]:
        tool = TOOLS[tool_id]
        
        if tool.get("batch_takes_dir_input", False):
            print(f"* Running {tool['name']} (processes entire input directory via its own logic)...")
            script_path = SCRIPT_DIR / tool["path"] / tool["script"]
            if not script_path.exists():
                print(f"! Script {script_path.name} not found.")
                return False, self.post_execution_menu(tool_id, False)
            
            python_exe = self.get_venv_python() or sys.executable
            processed_args = [ \
                    str(INPUT_DIR) if a == "{input_dir}" else \
                    str(OUTPUT_DIR) if a == "{output_dir}" else \
                    a for a in tool["args_template"]]
            
            cmd = [python_exe, str(script_path)] + processed_args
            print(f"* Executing: {' '.join(cmd)}")
            try:
                original_cwd = os.getcwd()
                os.chdir(SCRIPT_DIR)
                result = subprocess.run(cmd, text=True)
                successful_execution = result.returncode == 0
                
                if successful_execution and "{output_dir}" in tool["args_template"]:
                    input_files_for_cleanup = self.get_input_files(tool_id)
                    if input_files_for_cleanup:
                        print("* Note: Cleanup will be offered for files in input dir matching tool's extensions.")
                        self.offer_cleanup(input_files_for_cleanup)
                
                return successful_execution, self.post_execution_menu(tool_id, successful_execution)
            except Exception as e:
                print(f"! Error running {tool['name']} in batch: {e}")
                return False, self.post_execution_menu(tool_id, False)
            finally:
                os.chdir(original_cwd)

        if not tool["supports_batch"]:
            print(f"! {tool['name']} does not support batch processing.")
            return False, self.post_execution_menu(tool_id, False)
        
        input_files = self.get_input_files(tool_id)
        if not input_files:
            print(f"! No input files for {tool['name']} in {INPUT_DIR} (ext: {', '.join(tool['input_extensions'])}).")
            return False, self.post_execution_menu(tool_id, False)
        
        print(f"* Found {len(input_files)} files to process for {tool['name']}:")
        for f in input_files: print(f"  - {f.name}")
        
        if input_files and tool.get("batch_takes_dir_input"):
            print(f"  (Script will scan '{INPUT_DIR}' directly)")
        
        success_count = 0
        processed_files_map = {}

        for input_file in input_files:
            print(f"\n* Processing: {input_file.name}")
            output_file_path = OUTPUT_DIR / f"{input_file.stem}{tool.get('output_extension', '_processed')}{input_file.suffix}"
            if tool_id == "wmd_converter":
                 output_file_path = OUTPUT_DIR / f"{input_file.stem}{'.md' if input_file.suffix.lower() == '.docx' else '.docx'}"

            if self.run_tool_on_file(tool_id, input_file, output_file_path):
                success_count += 1
                processed_files_map[str(input_file)] = str(output_file_path)
        
        print(f"\n* Batch processing summary for {tool['name']}:")
        print(f"  - Successfully processed: {success_count}")
        print(f"  - Failed or skipped: {len(input_files) - success_count}")
        
        if success_count > 0:
            successful_input_paths = [Path(p_str) for p_str in processed_files_map.keys()]
            self.offer_cleanup(successful_input_paths)
        
        all_succeeded = success_count == len(input_files)
        return all_succeeded, self.post_execution_menu(tool_id, all_succeeded if input_files else False)

    def run_tool_interactive(self, tool_id: str) -> Tuple[bool, str]:
        tool = TOOLS[tool_id]
        script_path = SCRIPT_DIR / tool["path"] / tool["script"]
        successful_execution = False
        
        if not script_path.exists():
            print(f"! Script not found: {script_path}")
            return False, self.post_execution_menu(tool_id, False)
        
        python_exe = self.get_venv_python() or sys.executable
        
        args = self.prepare_interactive_args(tool_id) 
        if args is None: 
            return False, self.post_execution_menu(tool_id, False) 
        
        cmd = [python_exe, str(script_path)] + args
        
        print(f"* Executing: {' '.join(str(c) for c in cmd)}")
        
        try:
            original_cwd = os.getcwd()
            os.chdir(SCRIPT_DIR)
            if tool_id == "infinite_differ": 
                print("* Launching GUI tool. Please close it to continue this menu...")
                process = subprocess.Popen(cmd)
                process.wait() 
                successful_execution = process.returncode == 0
            else:
                result = subprocess.run(cmd, text=True) 
                successful_execution = result.returncode == 0
        except KeyboardInterrupt:
            print("\n* Tool execution interrupted by user.")
        except Exception as e:
            print(f"! Error running {tool['name']} interactively: {e}")
        finally:
            os.chdir(original_cwd)
        
        return successful_execution, self.post_execution_menu(tool_id, successful_execution)
    
    def post_execution_menu(self, tool_id: str, execution_was_successful: Optional[bool]) -> str:
        tool = TOOLS[tool_id]
        # Screen is NOT cleared here; it's cleared by the calling menu (main or tool_menu) if compact.

        status_msg = "* Tool operation finished." 
        if execution_was_successful is not None:
            status_text = "successful" if execution_was_successful else "unsuccessful"
            status_msg = f"* Tool operation was {status_text}: {tool['name']}"
        print(f"\n{status_msg}")

        print("\nWhat would you like to do next?")
        print(f"  1. Return to {tool['name']} menu")
        print("  2. Return to main menu")
        print("  0. Exit program")
        
        while True:
            try:
                choice = input("\nEnter your choice: ").strip()
                if choice == '0': return 'exit'
                elif choice == '1': return 'tool_menu'
                elif choice == '2': return 'main_menu'
                else: print("! Invalid choice. (0, 1, or 2)")
            except KeyboardInterrupt: return 'exit'
    
    def prepare_interactive_args(self, tool_id: str) -> Optional[List[str]]:
        tool = TOOLS[tool_id]
        # Screen cleared by run_tool_interactive or run_tool_menu before calling this if compact.
        print(f"\n--- {tool['name']}: Interactive Mode Setup ---")
        if tool.get("description"): print(f"--- {tool['description']} ---")

        if not tool["args_template"]:
            if tool_id == "infinite_differ":
                 print("* This is a GUI tool and will be launched without additional arguments.")
                 return []
            else:
                print(f"* {tool['name']} has no pre-defined arguments. You can enter them manually.")
                custom_args_str = input("  Enter all arguments (or press Enter if none): ").strip()
                return custom_args_str.split() if custom_args_str else []

        final_args = []
        template_args = tool["args_template"]
        idx = 0
        while idx < len(template_args):
            template_part = template_args[idx]
            
            if template_part.startswith("{") and template_part.endswith("}"):
                placeholder = template_part[1:-1]
                prompt = f"  Enter value for '{placeholder}'"
                default_value_info = ""

                if placeholder == "input_file" or placeholder == "primary_input" or placeholder == "video_input":
                    prompt += f" (e.g., file in {INPUT_DIR} or full path)"
                elif placeholder == "output_file":
                     prompt += f" (e.g., in {OUTPUT_DIR}, or Enter for auto-name)"
                elif placeholder == "input_dir":
                    default_value_info = f" (default: {INPUT_DIR})"
                    prompt += default_value_info
                elif placeholder == "output_dir":
                    default_value_info = f" (default: {OUTPUT_DIR})"
                    prompt += default_value_info
                elif placeholder == "media_dir":
                    prompt += f" (e.g., in {OUTPUT_DIR}/<doc_name>_media, Enter for auto)"
                
                prompt += ": "
                user_value = input(prompt).strip()
                
                if not user_value:
                    if placeholder == "input_dir": user_value = str(INPUT_DIR)
                    elif placeholder == "output_dir": user_value = str(OUTPUT_DIR)
                    elif (placeholder == "output_file" or placeholder == "media_dir") and \
                         idx > 0 and template_args[idx-1] in ["-o", "--output", "--media-dir"]:
                        if final_args and final_args[-1] == template_args[idx-1]:
                            final_args.pop()
                        idx +=1 
                        continue 
                
                final_args.append(user_value)
                idx += 1
            else: 
                final_args.append(template_part)
                idx += 1
            # No clear_screen_if_compact here per argument, only at start/end of main interaction points.

        return final_args

    def offer_cleanup(self, successfully_processed_files: List[Path]):
        if not successfully_processed_files: return
        
        print(f"\n* Source File Cleanup Option *")
        print(f"  This will delete {len(successfully_processed_files)} successfully processed source files from {INPUT_DIR}:")
        for f_path in successfully_processed_files[:10]: print(f"    - {f_path.name}")
        if len(successfully_processed_files) > 10: print(f"    ...and {len(successfully_processed_files)-10} more.")

        choice = input("  Delete these source files? (y/N): ").strip().lower()
        
        if choice == 'y':
            deleted_count = 0
            for file_path in successfully_processed_files:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    print(f"  ✓ Deleted: {file_path.name}")
                except Exception as e:
                    print(f"  ✗ Failed to delete {file_path.name}: {e}")
            print(f"* Deleted {deleted_count} source files.")
        else:
            print("* Source files were kept.")


def print_menu(manager: ToolManager):
    print("\n" + "="*60)
    print(f"{'LittleTools Environment Setup Menu':^60}")
    print("="*60)
    print("Available Tools (select number to run):")
    for i, (tool_id, tool) in enumerate(TOOLS.items(), 1):
        print(f"  {i:2d}. {tool['name']}")
    print("\nActions:")
    num_tools = len(TOOLS)
    print(f"  {num_tools+1:2d}. Install/Setup tool dependencies")
    print(f"  {num_tools+2:2d}. Uninstall tool (remove dependencies & mark as not installed)")
    print(f"  {num_tools+3:2d}. Show tool status & input file counts")
    compact_status = 'ON' if manager.config.get("compact_mode", True) else 'OFF'
    print(f"  {num_tools+4:2d}. Compact mode: {compact_status} (Toggle)")
    print(f"  {num_tools+5:2d}. List all compatible input files") 
    print(f"  {num_tools+6:2d}. Clean .venv & config (Reset)") 
    print("   0. Exit")


def select_tools_for_action(manager: ToolManager, action_description: str) -> List[str]:
    # Screen cleared by main loop before calling this typically
    print(f"\n--- Select Tool(s) to {action_description} ---")
    tool_ids = list(TOOLS.keys())
    for i, tool_id in enumerate(tool_ids, 1):
        print(f"  {i:2d}. {TOOLS[tool_id]['name']}")
    print("\n  all. Select all tools")
    print("  0. Cancel / Back to Main Menu")

    selected_tool_keys = []
    while True:
        raw_input = input("Enter selection (numbers separated by space, 'all', or 0): ").strip().lower()
        # No clear here, let main loop handle after selection returns

        if raw_input == '0': return []
        if raw_input == 'all': return tool_ids
        
        try:
            chosen_indices = [int(x.strip()) for x in raw_input.split()]
            current_selection = []
            valid_input = True
            for idx in chosen_indices:
                if 1 <= idx <= len(tool_ids):
                    current_selection.append(tool_ids[idx-1])
                else:
                    print(f"! Invalid selection: {idx}. Not a valid tool number.")
                    valid_input = False
                    break 
            if valid_input and current_selection:
                return current_selection
            elif not valid_input:
                input("Press Enter to try again...") 
                # Reprint selection prompt (screen not cleared, adds to existing)
                print(f"\n--- Select Tool(s) to {action_description} ---")
                for i, tool_id in enumerate(tool_ids, 1): print(f"  {i:2d}. {TOOLS[tool_id]['name']}")
                print("\n  all. Select all tools\n  0. Cancel / Back to Main Menu")

        except ValueError:
            print("! Invalid input. Please use numbers, 'all', or 0.")
            input("Press Enter to try again...")
            # Reprint selection prompt
            print(f"\n--- Select Tool(s) to {action_description} ---")
            for i, tool_id in enumerate(tool_ids, 1): print(f"  {i:2d}. {TOOLS[tool_id]['name']}")
            print("\n  all. Select all tools\n  0. Cancel / Back to Main Menu")

        except KeyboardInterrupt: return []


def select_single_tool_for_action(manager: ToolManager, action_description: str) -> Optional[str]:
    print(f"\n--- Select a Single Tool to {action_description} ---")
    tool_ids = list(TOOLS.keys())
    for i, tool_id in enumerate(tool_ids, 1):
        print(f"  {i:2d}. {TOOLS[tool_id]['name']}")
    print("  0. Cancel / Back to Main Menu")

    while True:
        raw_input = input("Enter tool number (or 0 to cancel): ").strip()
        # No clear here

        if raw_input == '0': return None
        try:
            idx = int(raw_input)
            if 1 <= idx <= len(tool_ids):
                return tool_ids[idx-1]
            else:
                print(f"! Invalid selection: {idx}. Not a valid tool number.")
        except ValueError:
            print("! Invalid input. Please enter a number or 0.")
        except KeyboardInterrupt: return None
        input("Press Enter to try again...")
        # Reprint selection prompt
        print(f"\n--- Select a Single Tool to {action_description} ---")
        for i, tool_id in enumerate(tool_ids, 1): print(f"  {i:2d}. {TOOLS[tool_id]['name']}")
        print("  0. Cancel / Back to Main Menu")


def run_tool_menu(manager: ToolManager, tool_id: str) -> str:
    tool = TOOLS[tool_id]
    is_compact = manager.config.get("compact_mode", True)
    
    while True: 
        clear_screen_if_compact(is_compact) # Clear at the start of tool menu loop
        print(f"\n{'='*55}\nTool: {tool['name']}\n{'='*55}")
        if tool.get('description'): print(f"{tool['description']}")
        
        if not manager.is_tool_ready(tool_id):
            print("\n! Tool is not ready. Dependencies might be missing or not set up.")
            choice = input("  Would you like to install dependencies for this tool now? (y/N): ").strip().lower()
            if choice in ['y', 'yes']:
                manager.setup_tool(tool_id)
                input("\nPress Enter to continue...")
            return 'main_menu'
        
        input_files = manager.get_input_files(tool_id)
        print(f"\nInput Directory: {INPUT_DIR}")
        print(f"Output Directory: {OUTPUT_DIR}")
        print(f"Found {len(input_files)} compatible file(s) in input directory for this tool:")
        if input_files:
            for f in input_files[:5]: print(f"  - {f.name}")
            if len(input_files) > 5: print(f"  ... and {len(input_files) - 5} more.")
        else:
             print("  (None)")
        
        print("\nRun Options:")
        can_batch = tool["supports_batch"] and (input_files or tool.get("batch_takes_dir_input"))
        if can_batch:
            batch_note = f"(processes all compatible files from {INPUT_DIR} to {OUTPUT_DIR})" \
                         if not tool.get("batch_takes_dir_input") else \
                         f"(script processes entire {INPUT_DIR} to {OUTPUT_DIR})"
            print(f"  1. Batch mode {batch_note}")
        print("  2. Interactive mode (manually specify inputs/options)")
        if tool_id == "infinite_differ": print("      (this will open the GUI application)")
        print("  0. Back to Main Menu")
        
        choice = input("\nEnter your choice: ").strip()
        # No clear after this input, action handling will do it or next loop iteration.

        post_exec_action = 'tool_menu' 

        if choice == '0': return 'main_menu'
        
        if choice == '1' and can_batch:
            # Clear will happen inside run_tool_batch if needed, or here before post_execution_menu
            _success, post_exec_action = manager.run_tool_batch(tool_id)
        elif choice == '2':
            _success, post_exec_action = manager.run_tool_interactive(tool_id)
        else:
            print("! Invalid choice.")
            input("Press Enter to try again...")
            continue 

        if post_exec_action == 'exit': return 'exit'
        if post_exec_action == 'main_menu': return 'main_menu'


def show_details_view(manager: ToolManager, mode: str):
    # Screen cleared by main loop before calling this.
    title = "Tool Status & Input File Counts" if mode == "status" else "Compatible Input Files List"
    print(f"\n{'='*70}\n{title:^70}\n{'='*70}")
    
    total_compatible_files = 0
    for tool_id, tool in TOOLS.items():
        print(f"\n--- {tool['name']} ---")
        if mode == "status":
            is_ready = manager.is_tool_ready(tool_id)
            status_str = "✓ Ready" if is_ready else "✗ Not Ready"
            py_deps_key = "installed_tools"
            py_deps_str = "Installed" if tool_id in manager.config[py_deps_key] else \
                          "Not Installed" if tool["needs_dependencies"] else "N/A (no Python deps)"
            
            print(f"  Overall Status: {status_str}")
            print(f"  Python Deps:    {py_deps_str}")

            sys_deps_list = tool["system_deps"]
            if sys_deps_list:
                missing_sys = [dep for dep in sys_deps_list if not manager.check_system_dependency(dep)]
                sys_deps_str = f"Missing: {', '.join(missing_sys)}" if missing_sys else "All Found"
            else:
                sys_deps_str = "N/A (none required)"
            print(f"  System Deps:    {sys_deps_str}")
        
        input_files = manager.get_input_files(tool_id)
        if mode == "status":
             print(f"  Input Files:    {len(input_files)} compatible file(s) found in {INPUT_DIR}")
        elif mode == "input_files":
            print(f"  Supported extensions: {', '.join(tool['input_extensions'])}")
            if input_files:
                print(f"  Found {len(input_files)} file(s) in {INPUT_DIR}:")
                for f_path in input_files: print(f"    - {f_path.name}")
                total_compatible_files += len(input_files)
            else:
                print(f"    No compatible files found in {INPUT_DIR}.")

    if mode == "input_files": 
        print(f"\nTotal compatible input files found across all tools: {total_compatible_files}")
    print(f"\nInput Directory: {INPUT_DIR}\nOutput Directory for processed files: {OUTPUT_DIR}")
    
    input("\nPress Enter to return to the main menu...")


def clean_all(manager: ToolManager):
    # Screen cleared by main loop.
    print("\nWARNING: This will remove the .venv directory (if it exists)\n         and the setup_config.json file (resetting all settings).")
    confirm = input("Are you ABSOLUTELY sure? This cannot be undone. (yes/N): ").strip()

    if confirm == 'yes':
        cleaned = []
        if VENV_DIR.exists():
            try:
                shutil.rmtree(VENV_DIR)
                cleaned.append(".venv directory")
            except Exception as e: print(f"! Error cleaning .venv: {e}")
        
        if CONFIG_FILE.exists():
            try:
                CONFIG_FILE.unlink()
                cleaned.append("setup_config.json")
            except Exception as e: print(f"! Error cleaning config: {e}")
        
        if cleaned:
            print("\n* Successfully cleaned:")
            for item in cleaned: print(f"  - {item}")
            print("* Restarting ToolManager with default settings...")
            manager.config = manager.load_config() 
            manager.initialize_default_tools() 
        else:
            print("\n* Nothing was found to clean (or items already removed).")
    else:
        print("\n* Cleaning operation cancelled.")
    
    input("\nPress Enter to return to the main menu...")


def main():
    manager = ToolManager()
    is_compact = manager.config.get("compact_mode", True)
    clear_screen_if_compact(is_compact) 

    print("Welcome to LittleTools Menu!")
    
    while True:
        is_compact = manager.config.get("compact_mode", True) 
        
        print_menu(manager)
        choice = input("\nEnter your choice (0 to exit): ").strip()
        clear_screen_if_compact(is_compact) # Clear *after* input, *before* processing action
            
        if choice == '0':
            print("Goodbye!")
            break
        
        try:
            tool_idx = int(choice)
            if 1 <= tool_idx <= len(TOOLS):
                tool_id_selected = list(TOOLS.keys())[tool_idx-1]
                nav_action = run_tool_menu(manager, tool_id_selected) 
                if nav_action == 'exit':
                    print("Goodbye!") 
                    break
                continue 
        except ValueError:
            pass 
        
        num_tools = len(TOOLS)
        if choice == str(num_tools + 1):
            selected_ids = select_tools_for_action(manager, "Install/Setup")
            if selected_ids:
                for tid in selected_ids:
                    # No clear here, setup_tool is just info unless it prompts.
                    manager.setup_tool(tid) 
                    input("\nPress Enter to continue to next selection or finish...")
                print("Finished setup process for selected tools.")
                input("Press Enter to return to main menu...")

        elif choice == str(num_tools + 2):
            tool_to_act_on = select_single_tool_for_action(manager, "Uninstall (remove dependencies)")
            if tool_to_act_on:
                manager.uninstall_tool(tool_to_act_on)
                input("\nPress Enter to return to main menu...")

        elif choice == str(num_tools + 3):
            show_details_view(manager, mode="status") 
            
        elif choice == str(num_tools + 4):
            new_compact_mode = not manager.config.get("compact_mode", True)
            manager.config["compact_mode"] = new_compact_mode
            manager.save_config()
            print(f"\n* Compact mode is now {'ON' if new_compact_mode else 'OFF'}.")
            input("Press Enter to continue...")
            
        elif choice == str(num_tools + 5):
            show_details_view(manager, mode="input_files")

        elif choice == str(num_tools + 6):
            clean_all(manager)
            
        else: 
            print("! Invalid choice. Please try again.")
            input("Press Enter to continue...")
        
if __name__ == "__main__":
    main() 