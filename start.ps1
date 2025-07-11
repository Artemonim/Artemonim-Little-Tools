# LittleTools Environment Setup & Interactive Launcher Script

# --- SCRIPT CONFIGURATION ---
$VenvDir = ".venv"
$RequiredPythonVersion = "3.11"
$PipCacheDir = Join-Path $PSScriptRoot ".pip-cache"
$HfCacheDir = Join-Path $PSScriptRoot ".huggingface"

# --- ENVIRONMENT VARIABLES ---
# Set cache directories to be inside the project folder
$env:PIP_CACHE_DIR = $PipCacheDir
$env:HF_HOME = $HfCacheDir
Write-Host "* Caches will be stored in:" -ForegroundColor Gray
Write-Host "  - Pip: $PipCacheDir" -ForegroundColor Gray
Write-Host "  - Hugging Face: $HfCacheDir" -ForegroundColor Gray

# --- GRACEFUL EXIT ON CTRL+C ---
trap [System.Management.Automation.PipelineStoppedException] {
    Write-Host "`n! Operation cancelled by user. Exiting gracefully." -ForegroundColor Yellow
    exit 1
}

# --- HELPER FUNCTIONS ---

function Get-VenvPaths {
    $IsWindowsPlatform = ($PSVersionTable.PSVersion.Major -ge 3 -and $IsWindows) -or ($env:OS -eq "Windows_NT")
    if ($IsWindowsPlatform) {
        return @{
            Python = Join-Path $VenvDir "Scripts\python.exe"
            Activate = Join-Path $VenvDir "Scripts\Activate.ps1"
            LtCmd = Join-Path $VenvDir "Scripts\lt.exe"
        }
    } else {
        return @{
            Python = Join-Path $VenvDir "bin/python"
            Activate = Join-Path $VenvDir "bin/activate"
            LtCmd = Join-Path $VenvDir "bin/lt"
        }
    }
}

function Find-PythonExecutable {
    Write-Host "* Searching for Python $RequiredPythonVersion..." -ForegroundColor Yellow
    
    # ! First try Python Launcher (py) which is standard on Windows
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        try {
            # * Check if required version is available through py launcher
            $availableVersions = & py --list 2>&1
            if ($availableVersions -match "-V:$RequiredPythonVersion") {
                $testVersion = & py -$RequiredPythonVersion --version 2>&1
                if ($testVersion -match "Python $RequiredPythonVersion") {
                    Write-Host "  ✓ Found Python $RequiredPythonVersion via py launcher" -ForegroundColor Green
                    return "py -$RequiredPythonVersion"
                }
            }
        } catch {
            Write-Host "  - py launcher available but failed to check versions" -ForegroundColor Yellow
        }
    }
    
    # ! Fallback to direct commands (less reliable on Windows)
    $PythonCommands = @("python$RequiredPythonVersion", "python3", "python")
    
    foreach ($command in $PythonCommands) {
        $foundPath = Get-Command $command -ErrorAction SilentlyContinue
        if ($foundPath) {
            try {
                $versionString = (& $foundPath.Source --version 2>&1) -split " " | Select-Object -Last 1
                if ($versionString -like "$RequiredPythonVersion*") {
                    Write-Host "  ✓ Found compatible Python at: $($foundPath.Source)" -ForegroundColor Green
                    return $foundPath.Source
                }
            } catch {
                continue
            }
        }
    }
    
    Write-Host "! Error: Python $RequiredPythonVersion not found." -ForegroundColor Red
    Write-Host "  Available Python versions:" -ForegroundColor Red
    if ($PyLauncher) {
        & py --list 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    }
    Write-Host "  Please ensure Python $RequiredPythonVersion is installed and accessible."
    return $null
}

function Install-Environment {
    $PythonExe = Find-PythonExecutable
    if (-not $PythonExe) { return }

    $VenvPaths = Get-VenvPaths
    if (-not (Test-Path $VenvDir)) {
        Write-Host "* Creating virtual environment with Python $RequiredPythonVersion..." -ForegroundColor Yellow
        try {
            # * Handle py launcher command format
            if ($PythonExe -like "py -*") {
                $PythonArgs = $PythonExe -split " "
                & $PythonArgs[0] $PythonArgs[1] -m venv $VenvDir --upgrade-deps
            } else {
                & $PythonExe -m venv $VenvDir --upgrade-deps
            }
            if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
            Write-Host "  ✓ Virtual environment created." -ForegroundColor Green
        } catch [System.Management.Automation.PipelineStoppedException] {
            Write-Host "`n! Virtual environment creation cancelled by user." -ForegroundColor Yellow
            if (Test-Path $VenvDir) {
                Write-Host "* Removing partial virtual environment..."
                Remove-Item $VenvDir -Recurse -Force
            }
            return
        } catch {
            Write-Host "! Error creating virtual environment: $_" -ForegroundColor Red
            return
        }
    } else {
        Write-Host "* Virtual environment already exists. Checking for updates..." -ForegroundColor Green
    }

    Write-Host "* Installing/updating all LittleTools packages..." -ForegroundColor Yellow
    Write-Host "  This can take a few minutes if new dependencies (like torch) are being downloaded."
    try {
        # * Use pip-tools for robust dependency management (install, update, and removal of orphans)
        & $VenvPaths.Python -m pip install --upgrade pip pip-tools
        if ($LASTEXITCODE -ne 0) { throw "Failed to install pip-tools." }

        # * Dynamically build a requirements.in file
        $Requirements = [System.Collections.Generic.List[string]]::new()
        $Requirements.Add("-e ./littletools_dev")
        $Requirements.Add("-e ./littletools_cli")
        $Requirements.Add("-e ./littletools_core")
        $Requirements.Add("-e ./littletools_speech")
        $Requirements.Add("-e ./littletools_txt")
        $Requirements.Add("-e ./littletools_video")

        # * [Hygiene Check] Ensure setuptools is not a runtime dependency
        $ProjectTomlFiles = Get-ChildItem -Path $PSScriptRoot -Recurse -Filter "pyproject.toml" | Where-Object { $_.FullName -notlike "*\.venv\*" }
        foreach ($tomlFile in $ProjectTomlFiles) {
            $content = Get-Content $tomlFile.FullName -Raw
            # * Look for an exact match for "setuptools" as a dependency to avoid false positives on e.g. "types-setuptools"
            if ($content -match '(?m)^\s*dependencies\s*=\s*\[[^\]]*"setuptools([>=<~\s\d\.]*)?"') {
                Write-Host "  ! WARNING: Found 'setuptools' as a runtime dependency in $($tomlFile.FullName)." -ForegroundColor Yellow
                Write-Host "    'setuptools' should only be in [build-system], not [project.dependencies]." -ForegroundColor Yellow
            }
        }

        # * Determine PyTorch and optional xformers requirements
        Write-Host "* Determining PyTorch package list..." -ForegroundColor Yellow
        $TorchPackages = @()
        $PipCompileIndexArgs = ""
        $NvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($NvidiaSmi) {
            try {
                $NvidiaOutput = & nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>$null
                if ($LASTEXITCODE -eq 0 -and $NvidiaOutput) {
                    Write-Host "  ✓ NVIDIA GPU detected. Including xformers with CUDA support." -ForegroundColor Green
                    $TorchPackages = @("torch", "torchvision", "torchaudio", "xformers")
                    $PipCompileIndexArgs = "--index-url https://download.pytorch.org/whl/cu121"
                } else {
                    Write-Host "  - NVIDIA GPU not detected or nvidia-smi failed. CPU-only PyTorch will be installed." -ForegroundColor Yellow
                    $TorchPackages = @("torch", "torchvision", "torchaudio")
                }
            } catch {
                Write-Host "  ! Error checking GPU. CPU-only PyTorch will be installed." -ForegroundColor Yellow
                $TorchPackages = @("torch", "torchvision", "torchaudio")
            }
        } else {
            Write-Host "  - nvidia-smi not found. CPU-only PyTorch will be installed." -ForegroundColor Yellow
            $TorchPackages = @("torch", "torchvision", "torchaudio")
        }
        # * Add PyTorch and related packages
        foreach ($pkg in $TorchPackages) {
            $Requirements.Add($pkg)
        }

        # * Define temporary file paths
        $ReqsInFile = Join-Path $PSScriptRoot "temp-requirements.in"
        $ReqsTxtFile = Join-Path $PSScriptRoot "requirements.txt" # This will be our lock file

        # * Write requirements to a temporary .in file
        $HeaderLines = @(
            "# Temporary requirements generated by start.ps1 – DO NOT EDIT",
            "# Modify pyproject.toml packages or start.ps1 to change dependencies",
            "# This file will be compiled into requirements.txt by the startup script",
            ""
        )
        $HeaderLines + $Requirements | Out-File -FilePath $ReqsInFile -Encoding utf8

        # * Compile the lock file. This is where dependency conflicts are detected.
        Write-Host "* Resolving all project dependencies..." -ForegroundColor Yellow
        $PipCompileExtraArgs = @()
        if ($PipCompileIndexArgs -ne "") {
            # Use extra-index-url so default PyPI is preserved and CUDA index is added
            $PipCompileExtraArgs = @('--pip-args', "--extra-index-url https://download.pytorch.org/whl/cu121")
        }
        & $VenvPaths.Python -m piptools compile --upgrade @PipCompileExtraArgs --output-file $ReqsTxtFile $ReqsInFile -v
        if ($LASTEXITCODE -ne 0) { throw "Failed to resolve dependencies. Check for conflicts." }
        
        # * Add custom header to the generated requirements.txt
        if (Test-Path $ReqsTxtFile) {
            $existingContent = Get-Content $ReqsTxtFile -Raw
            $customHeader = "# Generated by LittleTools startup script (start.ps1) - DO NOT EDIT MANUALLY`n"
            $customHeader + $existingContent | Set-Content $ReqsTxtFile -NoNewline
        }
        
        Write-Host "  ✓ Dependencies resolved successfully." -ForegroundColor Green
        
        # * Sync the environment. This adds, updates, AND removes packages to match the lock file.
        Write-Host "* Synchronizing virtual environment... (This may take a while)" -ForegroundColor Yellow
        & $VenvPaths.Python -m piptools sync $ReqsTxtFile
        if ($LASTEXITCODE -ne 0) { throw "Failed to synchronize environment." }
        Write-Host "  ✓ All packages installed and up-to-date." -ForegroundColor Green
        
        # * Clean up temporary .in file
        Remove-Item $ReqsInFile -ErrorAction SilentlyContinue

        # * Verify CUDA availability for tools that require it
        Write-Host "* Verifying PyTorch CUDA installation..." -ForegroundColor Yellow
        $CudaCheck = & $VenvPaths.Python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('PyTorch version:', torch.__version__)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  $CudaCheck" -ForegroundColor Cyan
        }
        
    } catch [System.Management.Automation.PipelineStoppedException] {
        Write-Host "`n! Installation cancelled by user." -ForegroundColor Yellow
    } catch {
        Write-Host "! Error installing packages: $_" -ForegroundColor Red
        Write-Host "  Please check the pip output above for details."
        # * Clean up temporary requirements file on failure
        if ($ReqsInFile -and (Test-Path $ReqsInFile)) {
            Remove-Item $ReqsInFile -ErrorAction SilentlyContinue
        }
    }
}

function Reinstall-Environment {
    Write-Host "* Forcing reinstall by removing existing environment..." -ForegroundColor Yellow
    if (Test-Path $VenvDir) {
        Remove-Item $VenvDir -Recurse -Force
        Write-Host "  ✓ Environment removed."
    }
    Install-Environment
}

function Uninstall-Environment {
    Write-Host "* Uninstalling LittleTools environment..." -ForegroundColor Yellow
    if (Test-Path $VenvDir) {
        Remove-Item $VenvDir -Recurse -Force
        Write-Host "  ✓ Virtual environment removed successfully."
    } else {
        Write-Host "  - No virtual environment found to remove."
    }
}

function Launch-Menu {
    $VenvPaths = Get-VenvPaths
    if (-not (Test-Path $VenvPaths.LtCmd)) {
        Write-Host "! Error: LittleTools is not installed." -ForegroundColor Red
        Write-Host "  Please run the installer (Option 1 or 2) first."
        return
    }

    Write-Host "* Starting LittleTools CLI menu..." -ForegroundColor Yellow
    try {
        Start-Process -FilePath $VenvPaths.LtCmd -Wait -NoNewWindow
        # * Exit the PowerShell script after the interactive menu is closed.
        Write-Host "Goodbye!"
        exit 0
    } catch {
        Write-Host "! Failed to launch CLI menu: $_" -ForegroundColor Red
    }
}

# --- CACHE MANAGEMENT FUNCTIONS ---

function Confirm-Action {
    param(
        [string]$ActionMessage
    )
    Write-Host "`n! WARNING: $ActionMessage" -ForegroundColor Yellow
    $confirm = Read-Host "  Are you sure you want to continue? This cannot be undone. (y/N)"
    return $confirm.ToLower() -eq 'y'
}

function Clean-Directory {
    param(
        [string]$Path,
        [string]$CacheName
    )
    if (Test-Path $Path) {
        Write-Host "* Removing $CacheName cache at '$Path'..." -ForegroundColor Yellow
        try {
            Remove-Item -Path $Path -Recurse -Force -ErrorAction Stop
            Write-Host "  ✓ $CacheName cache removed." -ForegroundColor Green
        } catch {
            Write-Host "! Error removing '$Path': $_" -ForegroundColor Red
        }
    } else {
        Write-Host "* $CacheName cache not found at '$Path'." -ForegroundColor Gray
    }
}

function Clean-PipCache {
    if (Confirm-Action "This will remove the local Pip package cache and all Python build artifacts (*.egg-info, build/, dist/).") {
        Clean-Directory -Path $PipCacheDir -CacheName "Pip"
        
        Write-Host "* Removing Python build artifacts..." -ForegroundColor Yellow
        Get-ChildItem -Path $PSScriptRoot -Recurse -Directory -Filter "*.egg-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path $PSScriptRoot -Recurse -Directory -Filter "build" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path $PSScriptRoot -Recurse -Directory -Filter "dist" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  ✓ Build artifacts removed." -ForegroundColor Green
    } else {
        Write-Host "  - Action cancelled." -ForegroundColor Gray
    }
}

function Clean-HuggingFaceCache {
    if (Confirm-Action "This will remove ALL downloaded Hugging Face models and datasets stored locally.") {
        Clean-Directory -Path $HfCacheDir -CacheName "Hugging Face"
    } else {
        Write-Host "  - Action cancelled." -ForegroundColor Gray
    }
}

function Show-CacheMenu {
    while ($true) {
        Clear-Host
        Write-Host "`n--- Cache Management ---" -ForegroundColor Cyan
        Write-Host " [1] Clean Python / Pip cache and build artifacts"
        Write-Host " [2] Clean Hugging Face model cache"
        Write-Host " [3] Clean ALL caches"
        Write-Host " [0] Back to Main Menu"

        $cache_choice = Read-Host "`nEnter your choice"
        switch ($cache_choice) {
            "1" { Clean-PipCache }
            "2" { Clean-HuggingFaceCache }
            "3" { 
                # Ask for confirmation for each step
                Clean-PipCache
                Clean-HuggingFaceCache
            }
            "0" { return }
            default { Write-Host "! Invalid choice." -ForegroundColor Red }
        }
        
        Write-Host "`nPress any key to return to the cache menu..."
        [System.Console]::ReadKey($true) | Out-Null
    }
}

# --- MAIN MENU LOOP ---

while ($true) {
    Clear-Host
    Write-Host "`n=== LittleTools Setup & Launcher (Python $RequiredPythonVersion) ===" -ForegroundColor Cyan
    Write-Host " [1] Install or Update All Tools"
    Write-Host " [2] Force Reinstall All Tools (Clean Slate)"
    Write-Host " [3] Uninstall (Remove Environment)"
    Write-Host " [4] Launch LittleTools Menu"
    Write-Host " [5] Cache Management"
    Write-Host " [0] Exit"

    $choice = Read-Host "`nEnter your choice"

    switch ($choice) {
        "1" { Install-Environment }
        "2" { Reinstall-Environment }
        "3" { Uninstall-Environment }
        "4" { Launch-Menu }
        "5" { Show-CacheMenu }
        "0" { 
            Write-Host "Goodbye!"
            exit 0
        }
        default {
            Write-Host "! Invalid choice. Please try again." -ForegroundColor Red
        }
    }

    if ($choice -in "1", "2", "3") {
        Write-Host "`nPress any key to return to the menu..."
        [System.Console]::ReadKey($true) | Out-Null
    }
} 