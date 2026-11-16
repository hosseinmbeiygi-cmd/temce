#Requires -Version 5.1

<#
.SYNOPSIS
    راه‌اندازی همزمان بک‌اند (FastAPI) و فرانت‌اند (Next.js) برای توسعه
.DESCRIPTION
    این اسکریپت هر دو سرویس Backend و Frontend را در پنجره‌های جداگانه اجرا می‌کند.
    برای متوقف کردن، Enter را در این پنجره بزنید تا همه سرویس‌ها متوقف شوند.
.EXAMPLE
    .\run.ps1
    make dev-all
#>

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $rootDir "frontend"
$logDir = Join-Path $rootDir "logs"

# Create logs directory if needed
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ── Utility Functions ─────────────────────────

function Write-Title($text) {
    Write-Host "`n==============================" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "==============================" -ForegroundColor Cyan
}

function Get-Timestamp {
    return (Get-Date -Format "HH:mm:ss")
}

function New-ServerWindow($title, $workingDir, $command, $logFile) {
    $startInfo = @{
        FilePath         = "powershell.exe"
        ArgumentList     = @(
            "-NoExit",
            "-Command", "& {
                Write-Host 'Starting $title...' -ForegroundColor Green;
                Write-Host 'Log: $logFile' -ForegroundColor DarkGray;
                Set-Location '$workingDir';
                & $command 2>&1 | Tee-Object -FilePath '$logFile'
            }"
        )
        WindowStyle      = "Normal"
        PassThru         = $true
    }
    return Start-Process @startInfo
}

# ── Cleanup ──────────────────────────────────

$serverProcesses = @()
$cleanupDone = $false

function Cleanup {
    if ($cleanupDone) { return }
    $cleanupDone = $true

    Write-Host "`n$(Get-Timestamp) در حال متوقف کردن سرویس‌ها..." -ForegroundColor Yellow
    foreach ($proc in $serverProcesses) {
        if ($proc -and !$proc.HasExited) {
            try {
                $proc.Kill($true)
                Write-Host "  ✕ PID $($proc.Id) متوقف شد" -ForegroundColor Red
            } catch {
                # Process already exited
            }
        }
    }
    Write-Host "$(Get-Timestamp) همه سرویس‌ها متوقف شدند." -ForegroundColor Green
}

# ── Main ─────────────────────────────────────

Clear-Host
Write-Title "راه‌اندازی همزمان فرانت و بک‌اند"
Write-Host "برای مشاهده لاگ‌ها: $logDir" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Backend ──────────────────────────
Write-Host "[1/2] راه‌اندازی Backend (FastAPI) روی پورت 8000..." -ForegroundColor Green
$backendLog = Join-Path $logDir "backend.log"
$backendProc = New-ServerWindow -title "Backend (FastAPI)" `
    -workingDir $rootDir `
    -command "python main.py" `
    -logFile $backendLog
$serverProcesses += $backendProc
Write-Host "  ✓ Backend PID: $($backendProc.Id)" -ForegroundColor DarkGray
Start-Sleep -Seconds 3

# ── Step 2: Frontend ─────────────────────────
Write-Host "[2/2] راه‌اندازی Frontend (Next.js) روی پورت 3000..." -ForegroundColor Green
$frontendLog = Join-Path $logDir "frontend.log"
$frontendProc = New-ServerWindow -title "Frontend (Next.js)" `
    -workingDir $frontendDir `
    -command "npx next dev --webpack" `
    -logFile $frontendLog
$serverProcesses += $frontendProc
Write-Host "  ✓ Frontend PID: $($frontendProc.Id)" -ForegroundColor DarkGray

# ── Summary ──────────────────────────────────
Write-Title "هر دو سرویس در حال اجرا هستند"
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor Yellow
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Logs:" -ForegroundColor DarkGray
Write-Host "    Get-Content -Path '$backendLog' -Tail 20 -Wait" -ForegroundColor DarkGray
Write-Host "    Get-Content -Path '$frontendLog' -Tail 20 -Wait" -ForegroundColor DarkGray
Write-Host ""
Write-Host "──────────────────────────────────────────" -ForegroundColor Cyan
Write-Host "  Enter را بزنید تا همه سرویس‌ها متوقف شوند" -ForegroundColor Red
Write-Host "──────────────────────────────────────────" -ForegroundColor Cyan

# ── Wait for user input ──────────────────────
try {
    # Monitor child processes; if both exit, we're done
    while ($true) {
        # Check if both windows were closed manually
        $alive = $serverProcesses | Where-Object { !$_.HasExited }
        if ($alive.Count -eq 0) {
            Write-Host "`n$(Get-Timestamp) همه سرویس‌ها متوقف شدند." -ForegroundColor Yellow
            break
        }
        # Check for keypress (non-blocking)
        try {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                if ($key.Key -eq "Enter") {
                    Write-Host "`n$(Get-Timestamp) دریافت Enter..." -ForegroundColor Yellow
                    break
                }
            }
        } catch {
            # Non-interactive stdin (e.g. piped from make); fall back to blocking read
            Write-Host "`n"
            Read-Host -Prompt "Press Enter to stop" | Out-Null
            break
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    Cleanup
}
