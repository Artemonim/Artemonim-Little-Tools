# LittleTools Environment Setup Script
# This script ensures a proper Python virtual environment and installs all tools.

param(
    [switch]$Force,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
LittleTools Environment Setup Script

Usage: .\start.ps1 [-Force] [-Help]

Options:
  -Force    Force recreation of the virtual environment.
  -Help     Show this help message.

This script will:
1. Check if Python 3.8+ is installed.
2. Create or verify the '.venv' virtual environment.
3. Install all LittleTools packages in editable mode.
4. Provide instructions on how to use the tools.
"@
    exit 0
}

# * Configuration
$VenvDir = ".venv"
$MinPythonVersion = [Version]"3.8.0"

Write-Host "=== LittleTools Environment Setup ===" -ForegroundColor Cyan

# * Check if Python is available
Write-Host "* Checking Python installation..." -ForegroundColor Yellow
try {
    $PythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python not found in PATH" }
    
    $VersionString = ($PythonVersion -split " ")[1]
    $CurrentVersion = [Version]$VersionString
    
    if ($CurrentVersion -lt $MinPythonVersion) {
        throw "Python version $CurrentVersion is too old. Minimum required: $MinPythonVersion"
    }
    
    Write-Host "  ✓ Python $CurrentVersion found" -ForegroundColor Green
} catch {
    Write-Host "! Error: $_" -ForegroundColor Red
    Write-Host "  Please install Python $MinPythonVersion or later and ensure it's in your PATH." -ForegroundColor Yellow
    exit 1
}

# * Define venv paths
$VenvPython = if ($IsWindows -or $env:OS -eq "Windows_NT") { 
    Join-Path $VenvDir "Scripts\python.exe" 
} else { 
    Join-Path $VenvDir "bin/python" 
}

# * Handle virtual environment creation/recreation
if ($Force -and (Test-Path $VenvDir)) {
    Write-Host "* Removing existing virtual environment (--Force specified)..." -ForegroundColor Yellow
    Remove-Item $VenvDir -Recurse -Force
}

if (-not (Test-Path $VenvDir)) {
    Write-Host "* Creating virtual environment..." -ForegroundColor Yellow
    try {
        python -m venv $VenvDir --upgrade-deps
        if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment" }
        Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
    } catch {
        Write-Host "! Error creating virtual environment: $_" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "* Virtual environment already exists." -ForegroundColor Green
}

# * Install all packages from the workspace
Write-Host "* Installing all LittleTools packages in editable mode..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes, especially for packages like torch."
try {
    # Install the main CLI and all discovered local packages.
    # The editable flag (-e) means changes to the source code are reflected immediately.
    & $VenvPython -m pip install -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install one or more packages."
    }
    Write-Host "  ✓ All packages installed successfully." -ForegroundColor Green
} catch {
    Write-Host "! Error installing packages: $_" -ForegroundColor Red
    Write-Host "  Please check the pip output above for details." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n=== Setup Complete! ===" -ForegroundColor Cyan
Write-Host "All tools are now installed in the virtual environment."
Write-Host "To run a tool, activate the environment and use the 'lt' command." -ForegroundColor Yellow
Write-Host "Example commands:"
Write-Host "  Windows (Command Prompt):"
Write-Host "    `"`$VenvDir\Scripts\activate.bat`""
Write-Host "    `"lt --help`""
Write-Host "    `"lt video-converter --help`""
Write-Host ""
Write-Host "  Windows (PowerShell):"
Write-Host "    `"`$VenvDir\Scripts\Activate.ps1`""
Write-Host "    `"lt`""
Write-Host ""
Write-Host "You can now run the activation command for your shell to get started."

# * Automatically launch the CLI menu (lt)
try {
    $LtCmd = if ($IsWindows -or $env:OS -eq "Windows_NT") {
        Join-Path $VenvDir "Scripts\lt.exe"
    } else {
        Join-Path $VenvDir "bin/lt"
    }

    Write-Host "* Starting LittleTools CLI menu..." -ForegroundColor Yellow
    & $LtCmd
} catch {
    Write-Host "! Failed to launch CLI menu: $_" -ForegroundColor Red
    Write-Host "  You can still start it manually after activating the environment." -ForegroundColor Yellow
}

exit 0 