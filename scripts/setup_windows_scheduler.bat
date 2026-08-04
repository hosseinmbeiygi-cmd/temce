@echo off
REM ═══════════════════════════════════════════════════════════════
REM  BrsApi Sync Scheduler — Windows Task Scheduler Setup
REM ═══════════════════════════════════════════════════════════════
REM
REM  Sets up Windows Scheduled Tasks to run BrsApi sync scripts
REM  automatically. Run this file as Administrator.
REM
REM  Usage:
REM      Double-click or run in Admin CMD:
REM          scripts\setup_windows_scheduler.bat
REM
REM  What it creates:
REM      1. BrsApi-LiveDataSync        — Every 5 minutes
REM      2. BrsApi-ComprehensiveSync   — Every 2 hours
REM      3. BrsApi-Scheduler           — Every 5 minutes
REM
REM ═══════════════════════════════════════════════════════════════

title BrsApi Sync Scheduler Setup

echo.
echo ═══════════════════════════════════════════════════════════════
echo   BrsApi Sync Scheduler — Windows Task Setup
echo ═══════════════════════════════════════════════════════════════
echo.

REM Check if running as Administrator
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo [33m[WARNING] This script must be run as Administrator![0m
    echo.
    echo Please right-click and select "Run as Administrator".
    echo.
    pause
    exit /b 1
)

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [31m[ERROR] Python not found! Please make sure Python is installed and in PATH.[0m
    pause
    exit /b 1
)

python --version
echo Project root: %PROJECT_ROOT%
echo.

REM Launch the PowerShell setup script
echo Launching PowerShell setup script...
echo.

powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup_windows_scheduler.ps1"

if %errorlevel% equ 0 (
    echo.
    echo [32m✅ Setup completed successfully![0m
) else (
    echo.
    echo [31m❌ Setup failed with error code %errorlevel%[0m
)

echo.
pause
