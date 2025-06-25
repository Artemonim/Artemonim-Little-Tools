@echo off
REM LittleTools Environment Setup - Batch Wrapper
REM This script calls the PowerShell setup script

echo LittleTools Environment Setup
echo.

REM Check if PowerShell is available
powershell -Command "exit 0" >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: PowerShell is not available or not working properly.
    echo Please ensure PowerShell is installed and accessible.
    pause
    exit /b 1
)

REM Run the PowerShell setup script
echo Running PowerShell setup script...
powershell -ExecutionPolicy Bypass -File "start.ps1" %*

REM Check if the PowerShell script succeeded
if %errorlevel% neq 0 (
    echo.
    echo Setup script encountered an error.
    pause
    exit /b %errorlevel%
) 