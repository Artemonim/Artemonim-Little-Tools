# LittleTools Environment Setup Script
# This script ensures proper Python environment setup before running menu.py

param(
    [switch]$Force,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
LittleTools Environment Setup Script

Usage: .\start.ps1 [-Force] [-Help]

Options:
  -Force    Force recreation of virtual environment even if it exists
  -Help     Show this help message

This script will:
1. Check if Python 3.8+ is installed
2. Create or verify virtual environment with pip
3. Launch menu.py for tool management

"@
    exit 0
}

# * Configuration
$VenvDir = ".venv"
$MenuScript = "menu.py"
$MinPythonVersion = [Version]"3.8.0"

Write-Host "=== LittleTools Environment Setup ===" -ForegroundColor Cyan

# * Check if Python is available
Write-Host "* Checking Python installation..." -ForegroundColor Yellow
try {
    $PythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found in PATH"
    }
    
    # Parse version (format: "Python 3.x.x")
    $VersionString = ($PythonVersion -split " ")[1]
    $CurrentVersion = [Version]$VersionString
    
    if ($CurrentVersion -lt $MinPythonVersion) {
        throw "Python version $CurrentVersion is too old. Minimum required: $MinPythonVersion"
    }
    
    Write-Host "  ✓ Python $CurrentVersion found" -ForegroundColor Green
} catch {
    Write-Host "! Error: $_" -ForegroundColor Red
    Write-Host "  Please install Python $MinPythonVersion or later from https://python.org" -ForegroundColor Yellow
    Write-Host "  Make sure Python is added to your system PATH." -ForegroundColor Yellow
    exit 1
}

# * Check if venv module is available
Write-Host "* Checking venv module..." -ForegroundColor Yellow
try {
    python -m venv --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "venv module not available"
    }
    Write-Host "  ✓ venv module available" -ForegroundColor Green
} catch {
    Write-Host "! Error: venv module not found" -ForegroundColor Red
    Write-Host "  Please ensure you have a complete Python installation." -ForegroundColor Yellow
    exit 1
}

# * Handle virtual environment
$VenvExists = Test-Path $VenvDir
$VenvPython = if ($IsWindows -or $env:OS -eq "Windows_NT") { 
    Join-Path $VenvDir "Scripts\python.exe" 
} else { 
    Join-Path $VenvDir "bin/python" 
}
$VenvPip = if ($IsWindows -or $env:OS -eq "Windows_NT") { 
    Join-Path $VenvDir "Scripts\pip.exe" 
} else { 
    Join-Path $VenvDir "bin/pip" 
}

if ($Force -and $VenvExists) {
    Write-Host "* Removing existing virtual environment (--Force specified)..." -ForegroundColor Yellow
    Remove-Item $VenvDir -Recurse -Force
    $VenvExists = $false
}

if (-not $VenvExists) {
    Write-Host "* Creating virtual environment..." -ForegroundColor Yellow
    try {
        python -m venv $VenvDir --upgrade-deps
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
    } catch {
        Write-Host "! Error creating virtual environment: $_" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "* Virtual environment already exists" -ForegroundColor Green
}

# * Verify virtual environment has working Python and pip
Write-Host "* Verifying virtual environment..." -ForegroundColor Yellow

if (-not (Test-Path $VenvPython)) {
    Write-Host "! Error: Python executable not found in virtual environment" -ForegroundColor Red
    Write-Host "  Try running with -Force to recreate the environment" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $VenvPip)) {
    Write-Host "! Error: pip not found in virtual environment" -ForegroundColor Red
    Write-Host "  Attempting to bootstrap pip..." -ForegroundColor Yellow
    
    try {
        & $VenvPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "ensurepip failed"
        }
        Write-Host "  ✓ pip bootstrapped successfully" -ForegroundColor Green
    } catch {
        Write-Host "! Error: Could not bootstrap pip: $_" -ForegroundColor Red
        Write-Host "  Try running with -Force to recreate the environment" -ForegroundColor Yellow
        exit 1
    }
}

# * Test pip functionality
Write-Host "* Testing pip functionality..." -ForegroundColor Yellow
try {
    & $VenvPip --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pip test failed"
    }
    Write-Host "  ✓ pip is working correctly" -ForegroundColor Green
} catch {
    Write-Host "! Error: pip is not working: $_" -ForegroundColor Red
    Write-Host "  Try running with -Force to recreate the environment" -ForegroundColor Yellow
    exit 1
}

# * Upgrade pip and setuptools to latest versions
Write-Host "* Upgrading pip and setuptools..." -ForegroundColor Yellow
try {
    & $VenvPython -m pip install --upgrade pip setuptools wheel | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed"
    }
    Write-Host "  ✓ pip and setuptools upgraded" -ForegroundColor Green
} catch {
    Write-Host "! Warning: Could not upgrade pip/setuptools: $_" -ForegroundColor Yellow
    Write-Host "  This may cause issues with some package installations" -ForegroundColor Yellow
}

# * Check if menu.py exists
if (-not (Test-Path $MenuScript)) {
    Write-Host "! Error: $MenuScript not found in current directory" -ForegroundColor Red
    Write-Host "  Please run this script from the LittleTools root directory" -ForegroundColor Yellow
    exit 1
}

Write-Host "* Environment setup complete!" -ForegroundColor Green
Write-Host "* Launching menu.py..." -ForegroundColor Yellow
Write-Host ""

# * Launch menu.py
try {
    python $MenuScript
} catch {
    Write-Host "! Error launching menu.py: $_" -ForegroundColor Red
    exit 1
} 