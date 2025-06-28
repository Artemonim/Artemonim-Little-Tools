#!/bin/bash
# LittleTools Environment Setup & Interactive Launcher Script
# Cross-platform version for Linux and macOS.

# --- SCRIPT CONFIGURATION ---
VenvDir=".venv"
RequiredPythonVersion="3.11"
# * Determine script's absolute directory
ScriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PipCacheDir="$ScriptDir/.pip-cache"
HfCacheDir="$ScriptDir/.huggingface"

# --- ENVIRONMENT VARIABLES ---
# Set cache directories to be inside the project folder
export PIP_CACHE_DIR="$PipCacheDir"
export HF_HOME="$HfCacheDir"

# --- COLORS (for fancy output) ---
COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_CYAN='\033[0;36m'
COLOR_GRAY='\033[0;90m'
COLOR_NC='\033[0m' # No Color

echo -e "${COLOR_GRAY}* Caches will be stored in:${COLOR_NC}"
echo -e "${COLOR_GRAY}  - Pip: $PipCacheDir${COLOR_NC}"
echo -e "${COLOR_GRAY}  - Hugging Face: $HfCacheDir${COLOR_NC}"

# --- GRACEFUL EXIT ON CTRL+C ---
trap 'echo -e "\n${COLOR_YELLOW}! Operation cancelled by user. Exiting gracefully.${COLOR_NC}"; exit 1' INT

# --- HELPER FUNCTIONS ---

# * These variables will be populated by get_venv_paths
VenvPython=""
VenvLtCmd=""

function get_venv_paths {
    VenvPython="$ScriptDir/$VenvDir/bin/python"
    VenvLtCmd="$ScriptDir/$VenvDir/bin/lt"
}

function find_python_executable {
    echo -e "${COLOR_YELLOW}* Searching for Python $RequiredPythonVersion...${COLOR_NC}"
    local python_commands=("python$RequiredPythonVersion" "python3" "python")

    for command in "${python_commands[@]}"; do
        if command -v "$command" &>/dev/null; then
            local version_string
            # * Capture version, handling potential text before the version number
            version_string=$(LANGUAGE=en "$command" --version 2>&1 | awk '{print $NF}')
            if [[ "$version_string" == "$RequiredPythonVersion"* ]]; then
                echo -e "${COLOR_GREEN}  ✓ Found compatible Python at: $(command -v "$command")${COLOR_NC}"
                command -v "$command" # Return the path
                return 0
            fi
        fi
    done

    echo -e "${COLOR_RED}! Error: Python $RequiredPythonVersion not found.${COLOR_NC}"
    echo -e "${COLOR_RED}  Please ensure Python $RequiredPythonVersion is installed and accessible in your PATH.${COLOR_NC}"
    return 1
}

function install_environment {
    local PythonExe
    PythonExe=$(find_python_executable)
    if [ -z "$PythonExe" ]; then return 1; fi

    get_venv_paths

    if [ ! -d "$VenvDir" ]; then
        echo -e "${COLOR_YELLOW}* Creating virtual environment with Python $RequiredPythonVersion...${COLOR_NC}"
        # * The trap will handle cancellation, but we add a check for command success
        "$PythonExe" -m venv "$VenvDir" --upgrade-deps
        if [ $? -ne 0 ]; then
            echo -e "${COLOR_RED}! Error creating virtual environment.${COLOR_NC}"
            echo -e "${COLOR_YELLOW}* Removing partial virtual environment...${COLOR_NC}"
            rm -rf "$VenvDir"
            return 1
        fi
        echo -e "${COLOR_GREEN}  ✓ Virtual environment created.${COLOR_NC}"
    else
        echo -e "${COLOR_GREEN}* Virtual environment already exists. Checking for updates...${COLOR_NC}"
    fi

    echo -e "${COLOR_YELLOW}* Installing/updating all LittleTools packages with pip-tools...${COLOR_NC}"
    echo -e "  This can take a few minutes if new dependencies (like torch) are being downloaded."
    
    "$VenvPython" -m pip install --upgrade pip pip-tools &>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${COLOR_RED}! Failed to install pip-tools.${COLOR_NC}"
        return 1
    fi

    # Base requirements including all local editable packages
    REQS_IN_CONTENT=(
        "-e ./littletools_dev"
        "-e ./littletools_cli"
        "-e ./littletools_core"
        "-e ./littletools_speech"
        "-e ./littletools_txt"
        "-e ./littletools_video"
    )

    local ParentDir
    ParentDir=$(dirname "$ScriptDir")
    local AgentDocstringsGeneratorPath="$ParentDir/AgentDocstringsGenerator"
    if [ -d "$AgentDocstringsGeneratorPath" ]; then
        REQS_IN_CONTENT+=("-e file://$AgentDocstringsGeneratorPath")
    fi
    
    echo -e "${COLOR_YELLOW}* [Hygiene Check] Ensuring setuptools is not a runtime dependency...${COLOR_NC}"
    find "$ScriptDir" -path "*/.venv/*" -prune -o -name "pyproject.toml" -print0 | while IFS= read -r -d $'\0' tomlFile; do
        if grep -qE '^\s*dependencies\s*=\s*\[[^]]*"setuptools([>=<~ \d\.]*)?"' "$tomlFile"; then
             echo -e "${COLOR_YELLOW}  ! WARNING: Found 'setuptools' as a runtime dependency in $tomlFile.${COLOR_NC}"
             echo -e "${COLOR_YELLOW}    'setuptools' should only be in [build-system], not [project.dependencies].${COLOR_NC}"
        fi
    done

    echo -e "${COLOR_YELLOW}* Determining PyTorch package list...${COLOR_NC}"
    local TorchPackages=()
    local PipCompileIndexArgs=""
    if command -v nvidia-smi &>/dev/null; then
        if nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits &>/dev/null; then
            echo -e "${COLOR_GREEN}  ✓ NVIDIA GPU detected. Including xformers with CUDA support.${COLOR_NC}"
            TorchPackages=("torch" "torchvision" "torchaudio" "xformers")
            PipCompileIndexArgs="--index-url https://download.pytorch.org/whl/cu121"
        else
            echo -e "${COLOR_YELLOW}  - NVIDIA GPU not detected or nvidia-smi failed. CPU-only PyTorch will be installed.${COLOR_NC}"
            TorchPackages=("torch" "torchvision" "torchaudio")
        fi
    else
        echo -e "${COLOR_YELLOW}  - nvidia-smi not found. CPU-only PyTorch will be installed.${COLOR_NC}"
        TorchPackages=("torch" "torchvision" "torchaudio")
    fi
    
    for pkg in "${TorchPackages[@]}"; do
        REQS_IN_CONTENT+=("$pkg")
    done

    local ReqsInFile="$ScriptDir/temp-requirements.in"
    local ReqsTxtFile="$ScriptDir/requirements.txt"
    printf "%s\n" "# Temporary requirements generated by start.sh – DO NOT EDIT" "# Modify pyproject.toml packages or start.sh to change dependencies" "# This file will be compiled into requirements.txt by the startup script" "" "${REQS_IN_CONTENT[@]}" > "$ReqsInFile"

    echo -e "${COLOR_YELLOW}* Resolving all project dependencies...${COLOR_NC}"
    local PipCompileExtraArgs=()
    if [ -n "$PipCompileIndexArgs" ]; then
        PipCompileExtraArgs+=('--pip-args' "--extra-index-url https://download.pytorch.org/whl/cu121")
    fi
    
    "$VenvPython" -m piptools compile "${PipCompileExtraArgs[@]}" --output-file "$ReqsTxtFile" "$ReqsInFile" -v
    if [ $? -ne 0 ]; then
        echo -e "${COLOR_RED}! Failed to resolve dependencies. Check for conflicts.${COLOR_NC}"
        rm -f "$ReqsInFile"
        return 1
    fi
    
    # * Add custom header to the generated requirements.txt
    if [ -f "$ReqsTxtFile" ]; then
        local tempFile=$(mktemp)
        echo "# Generated by LittleTools startup script (start.sh) - DO NOT EDIT MANUALLY" > "$tempFile"
        cat "$ReqsTxtFile" >> "$tempFile"
        mv "$tempFile" "$ReqsTxtFile"
    fi
    
    echo -e "${COLOR_GREEN}  ✓ Dependencies resolved successfully.${COLOR_NC}"
    
    echo -e "${COLOR_YELLOW}* Synchronizing virtual environment... (This may take a while)${COLOR_NC}"
    "$VenvPython" -m piptools sync "$ReqsTxtFile"
    if [ $? -ne 0 ]; then
        echo -e "${COLOR_RED}! Failed to synchronize environment.${COLOR_NC}"
        rm -f "$ReqsInFile"
        return 1
    fi
    echo -e "${COLOR_GREEN}  ✓ All packages installed and up-to-date.${COLOR_NC}"
    
    rm -f "$ReqsInFile"

    echo -e "${COLOR_YELLOW}* Verifying PyTorch CUDA installation...${COLOR_NC}"
    local CudaCheck
    CudaCheck=$("$VenvPython" -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}\\nPyTorch version: {torch.__version__}')" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "${COLOR_CYAN}  $CudaCheck${COLOR_NC}"
    fi
}

function reinstall_environment {
    echo -e "${COLOR_YELLOW}* Forcing reinstall by removing existing environment...${COLOR_NC}"
    if [ -d "$VenvDir" ]; then
        rm -rf "$VenvDir"
        echo -e "  ✓ Environment removed."
    fi
    install_environment
}

function uninstall_environment {
    echo -e "${COLOR_YELLOW}* Uninstalling LittleTools environment...${COLOR_NC}"
    if [ -d "$VenvDir" ]; then
        rm -rf "$VenvDir"
        echo -e "  ✓ Virtual environment removed successfully."
    else
        echo -e "  - No virtual environment found to remove."
    fi
}

function launch_menu {
    get_venv_paths
    if [ ! -f "$VenvLtCmd" ]; then
        echo -e "${COLOR_RED}! Error: LittleTools is not installed.${COLOR_NC}"
        echo -e "  Please run the installer (Option 1 or 2) first."
        return
    fi

    echo -e "${COLOR_YELLOW}* Starting LittleTools CLI menu...${COLOR_NC}"
    "$VenvLtCmd"
    echo "Goodbye!"
    exit 0
}

# --- CACHE MANAGEMENT FUNCTIONS ---

function confirm_action {
    local message="$1"
    echo -e "\n${COLOR_YELLOW}! WARNING: $message${COLOR_NC}"
    read -p "  Are you sure you want to continue? This cannot be undone. (y/N) " -r confirm
    if [[ "$confirm" =~ ^[yY]([eE][sS])?$ ]]; then
        return 0 # Success (yes)
    else
        return 1 # Failure (no)
    fi
}

function clean_directory {
    local path="$1"
    local name="$2"
    if [ -d "$path" ]; then
        echo -e "${COLOR_YELLOW}* Removing $name cache at '$path'...${COLOR_NC}"
        rm -rf "$path"
        if [ $? -eq 0 ]; then
            echo -e "${COLOR_GREEN}  ✓ $name cache removed.${COLOR_NC}"
        else
            echo -e "${COLOR_RED}! Error removing '$path'.${COLOR_NC}"
        fi
    else
        echo -e "${COLOR_GRAY}* $name cache not found at '$path'.${COLOR_NC}"
    fi
}

function clean_pip_cache {
    if confirm_action "This will remove the local Pip package cache and all Python build artifacts (*.egg-info, build/, dist/)."; then
        clean_directory "$PipCacheDir" "Pip"
        
        echo -e "${COLOR_YELLOW}* Removing Python build artifacts...${COLOR_NC}"
        find "$ScriptDir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
        find "$ScriptDir" -type d -name "build" -exec rm -rf {} + 2>/dev/null
        find "$ScriptDir" -type d -name "dist" -exec rm -rf {} + 2>/dev/null
        echo -e "${COLOR_GREEN}  ✓ Build artifacts removed.${COLOR_NC}"
    else
        echo -e "${COLOR_GRAY}  - Action cancelled.${COLOR_NC}"
    fi
}

function clean_huggingface_cache {
    if confirm_action "This will remove ALL downloaded Hugging Face models and datasets stored locally."; then
        clean_directory "$HfCacheDir" "Hugging Face"
    else
        echo -e "${COLOR_GRAY}  - Action cancelled.${COLOR_NC}"
    fi
}

function show_cache_menu {
    while true; do
        clear
        echo -e "\n${COLOR_CYAN}--- Cache Management ---${COLOR_NC}"
        echo " [1] Clean Python / Pip cache and build artifacts"
        echo " [2] Clean Hugging Face model cache"
        echo " [3] Clean ALL caches"
        echo " [0] Back to Main Menu"

        read -p "
Enter your choice: " cache_choice
        case "$cache_choice" in
            1) clean_pip_cache ;;
            2) clean_huggingface_cache ;;
            3) 
                clean_pip_cache
                clean_huggingface_cache
                ;;
            0) return ;;
            *) echo -e "${COLOR_RED}! Invalid choice.${COLOR_NC}" ;;
        esac
        
        echo -e "\nPress any key to return to the cache menu..."
        read -n 1 -s
    done
}

# --- MAIN MENU LOOP ---

function main_menu {
    while true; do
        clear
        echo -e "\n${COLOR_CYAN}=== LittleTools Setup & Launcher (Python $RequiredPythonVersion) ===${COLOR_NC}"
        echo " [1] Install or Update All Tools"
        echo " [2] Force Reinstall All Tools (Clean Slate)"
        echo " [3] Uninstall (Remove Environment)"
        echo " [4] Launch LittleTools Menu"
        echo " [5] Cache Management"
        echo " [0] Exit"

        read -p "
Enter your choice: " choice

        case "$choice" in
            1) install_environment ;;
            2) reinstall_environment ;;
            3) uninstall_environment ;;
            4) launch_menu ;;
            5) show_cache_menu ;;
            0) 
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${COLOR_RED}! Invalid choice. Please try again.${COLOR_NC}"
                ;;
        esac

        if [[ "$choice" =~ ^[1-3|5]$ ]]; then
            echo -e "\nPress any key to return to the menu..."
            read -n 1 -s
        fi
    done
}

# --- SCRIPT ENTRYPOINT ---
main_menu 