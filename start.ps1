# LittleTools Environment Setup & Interactive Launcher Script

# --- SCRIPT CONFIGURATION ---
$VenvDir = ".venv"
$RequiredPythonVersion = "3.11"

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
        & $VenvPaths.Python -m pip install --upgrade pip
        
        # * Check for NVIDIA GPU and install appropriate PyTorch version
        Write-Host "* Detecting GPU and installing PyTorch with CUDA support..." -ForegroundColor Yellow
        
        # Check if nvidia-smi is available (indicates NVIDIA GPU presence)
        $NvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($NvidiaSmi) {
            try {
                $NvidiaOutput = & nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>$null
                if ($LASTEXITCODE -eq 0 -and $NvidiaOutput) {
                    Write-Host "  ✓ NVIDIA GPU detected. Installing PyTorch with CUDA 12.1 support..." -ForegroundColor Green
                    # * Install PyTorch with CUDA 12.1 (widely compatible)
                    & $VenvPaths.Python -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
                    if ($LASTEXITCODE -ne 0) { 
                        Write-Host "  ! Failed to install CUDA PyTorch. Falling back to CPU version..." -ForegroundColor Yellow
                        & $VenvPaths.Python -m pip install --upgrade torch torchvision torchaudio
                    } else {
                        Write-Host "  ✓ PyTorch with CUDA support installed successfully." -ForegroundColor Green
                    }
                } else {
                    Write-Host "  - NVIDIA GPU not detected or nvidia-smi failed. Installing CPU-only PyTorch..." -ForegroundColor Yellow
                    & $VenvPaths.Python -m pip install --upgrade torch torchvision torchaudio
                }
            } catch {
                Write-Host "  ! Error checking GPU. Installing CPU-only PyTorch..." -ForegroundColor Yellow
                & $VenvPaths.Python -m pip install --upgrade torch torchvision torchaudio
            }
        } else {
            Write-Host "  - nvidia-smi not found. Installing CPU-only PyTorch..." -ForegroundColor Yellow
            & $VenvPaths.Python -m pip install --upgrade torch torchvision torchaudio
        }
        
        # * Install all LittleTools packages
        & $VenvPaths.Python -m pip install --upgrade -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video
        if ($LASTEXITCODE -ne 0) { throw "Failed to install one or more packages." }
        Write-Host "  ✓ All packages installed and up-to-date." -ForegroundColor Green
        
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

# --- MAIN MENU LOOP ---

while ($true) {
    Write-Host "`n=== LittleTools Setup & Launcher (Python $RequiredPythonVersion) ===" -ForegroundColor Cyan
    Write-Host " [1] Install or Update All Tools"
    Write-Host " [2] Force Reinstall All Tools (Clean Slate)"
    Write-Host " [3] Uninstall (Remove Environment)"
    Write-Host " [4] Launch LittleTools Menu"
    Write-Host " [0] Exit"

    $choice = Read-Host "`nEnter your choice"

    switch ($choice) {
        "1" { Install-Environment }
        "2" { Reinstall-Environment }
        "3" { Uninstall-Environment }
        "4" { Launch-Menu }
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
    Clear-Host
} 