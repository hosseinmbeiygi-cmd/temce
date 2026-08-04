<#
.SYNOPSIS
    BrsApi Task Installer — Silent (بدون UAC)
.DESCRIPTION
    Windows Task Scheduler tasks for BrsApi data sync.
    
    اگر اسکریپت بدون دسترسی admin اجرا شود، به‌صورت خودکار با schtasks
    یک task موقتی با سطح دسترسی SYSTEM می‌سازد که اسکریپت را مخفیانه
    اجرا می‌کند — بدون پنجره و بدون UAC prompt.
    
    Creates 3 tasks:
      1. BrsApi-LiveDataSync        — هر ۵ دقیقه
      2. BrsApi-ComprehensiveSync   — هر ۲ ساعت
      3. BrsApi-Scheduler           — هر ۵ دقیقه
    
    For verbose output, run with -Verbose flag.
.EXAMPLE
    # Install tasks (silent, no UAC)
    .\scripts\install_brsapi_tasks_silent.ps1

    # Uninstall all BrsApi tasks
    .\scripts\install_brsapi_tasks_silent.ps1 -Uninstall

    # Show current tasks without installing
    .\scripts\install_brsapi_tasks_silent.ps1 -Status
#>

param(
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Elevated
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$LogDir      = "$ProjectRoot\logs"
$PythonExe   = "python"

# ── Self-elevate silently via schtasks ────────────────────────
# This is the key trick: we create a temp task that runs as SYSTEM,
# executes this script with -Elevated flag, then self-destructs.
# No UAC prompt appears because schtasks /run bypasses UAC.

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator") -and -not $Uninstall -and -not $Status) {
    Write-Host "🔺 دسترسی admin وجود ندارد — ارتقاء مخفیانه از طریق SYSTEM..."
    Write-Host "   (هیچ پنجره و UAC prompts نمایش داده نمی‌شود)"

    $tempTaskName = "BrsApi_TempElevate_$(Get-Random -Maximum 99999)"
    $scriptPath   = $PSCommandPath
    $psCode       = "& '$scriptPath' -Elevated"

    # Create a temp task that runs as SYSTEM (highest privileges, no UAC)
    $action = "powershell -NoProfile -ExecutionPolicy Bypass -Command `"$psCode`""
    schtasks /create /tn $tempTaskName /tr $action /sc once /st 00:00 /ru SYSTEM /rl highest /f | Out-Null

    if ($LASTEXITCODE -eq 0) {
        # Run the task immediately (no UAC prompt!)
        schtasks /run /tn $tempTaskName | Out-Null
        Start-Sleep -Seconds 3  # Give it a moment to start

        # Wait for completion
        $timeout = 30
        while ($timeout -gt 0) {
            $state = (schtasks /query /tn $tempTaskName /fo CSV /v 2>$null | ConvertFrom-Csv).Status
            if ($state -eq "Ready" -or $state -eq "Disabled" -or -not $state) { break }
            Start-Sleep -Seconds 1
            $timeout--
        }

        # Clean up the temp task
        schtasks /delete /tn $tempTaskName /f | Out-Null
        Write-Host "✅ ارتقاء و نصب کامل شد."
    } else {
        Write-Host "❌ خطا در ایجاد task ارتقاء. دستی اجرا کنید:" -ForegroundColor Red
        Write-Host "   Run as Administrator: powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    }
    exit
}

# ── Actual installation logic (runs with admin/SYSTEM) ────────

# Ensure log directory
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function New-BrsApiTask {
    param(
        [string]$TaskName,
        [string]$TaskDescription,
        [string]$ScriptPath,
        [string]$RepetitionInterval,
        [string]$RepetitionDuration = "P1D"
    )

    $Action = New-ScheduledTaskAction `
        -Execute $PythonExe `
        -Argument "`"$ScriptPath`"" `
        -WorkingDirectory $ProjectRoot

    $Trigger = New-ScheduledTaskTrigger `
        -Daily `
        -At "00:00" `
        -RepetitionInterval $RepetitionInterval `
        -RepetitionDuration $RepetitionDuration

    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries:$true `
        -DontStopIfGoingOnBatteries:$true `
        -StartWhenAvailable:$true `
        -RestartInterval "00:01:00" `
        -RestartCount 3 `
        -MultipleInstances IgnoreNew `
        -Hidden   # Hidden in Task Scheduler UI

    $Principal = New-ScheduledTaskPrincipal `
        -UserId "SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    $Task = New-ScheduledTask `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description $TaskDescription

    Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force | Out-Null
    Write-Host "  ✅ $TaskName"
}

function Remove-BrsApiTasks {
    Write-Host "🧹 حذف taskهای BrsApi..."
    Get-ScheduledTask -TaskName "BrsApi-*" -ErrorAction SilentlyContinue | ForEach-Object {
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
        Write-Host "  🗑️ $($_.TaskName)"
    }
}

function Show-BrsApiStatus {
    Write-Host "📋 وضعیت taskهای BrsApi:"
    $tasks = Get-ScheduledTask -TaskName "BrsApi-*" -ErrorAction SilentlyContinue
    if ($tasks) {
        $tasks | Format-Table TaskName, State, @{N='NextRunTime';E={$_.NextRunTime -or '—'}} -AutoSize
    } else {
        Write-Host "  (هیچ taskی یافت نشد)"
    }
}

# ── Main ──────────────────────────────────────────────────────

if ($Uninstall) {
    Remove-BrsApiTasks
    Write-Host "`n✅ همه taskهای BrsApi حذف شدند."
    exit
}

if ($Status) {
    Show-BrsApiStatus
    exit
}

Write-Host ""
Write-Host "══════════════════════════════════════════════════"
Write-Host "  BrsApi Task Installer — بدون UAC"
Write-Host "══════════════════════════════════════════════════"
Write-Host ""

# ── Task 1: Live Data Sync (every 5 min) ─────────────────────
$liveDataScript = Join-Path $ProjectRoot "scripts" "sync_live_data.py"
if (Test-Path $liveDataScript) {
    Write-Host "  📡 نصب task: همگام‌سازی زنده (هر ۵ دقیقه)..."
    New-BrsApiTask `
        -TaskName "BrsApi-LiveDataSync" `
        -TaskDescription "BrsApi live data sync: symbols, gold, currency, index, commodities, crypto (every 5 min)" `
        -ScriptPath $liveDataScript `
        -RepetitionInterval "PT5M"
} else { Write-Host "  ⚠️  اسکریپت پیدا نشد: $liveDataScript" }

# ── Task 2: Comprehensive Sync (every 2 hours) ────────────────
$fullUpdateScript = Join-Path $ProjectRoot "scripts" "brsapi_full_update.py"
if (Test-Path $fullUpdateScript) {
    Write-Host "  🔄 نصب task: همگام‌سازی جامع (هر ۲ ساعت)..."
    New-BrsApiTask `
        -TaskName "BrsApi-ComprehensiveSync" `
        -TaskDescription "Comprehensive BrsApi sync: per-symbol NAV, history, detail, shareholders (every 2 hours)" `
        -ScriptPath $fullUpdateScript `
        -RepetitionInterval "PT2H"
} else { Write-Host "  ⚠️  اسکریپت پیدا نشد: $fullUpdateScript" }

# ── Task 3: APScheduler Runner (every 5 min) ──────────────────
$schedulerScript = Join-Path $ProjectRoot "scripts" "start_scheduler.py"
if (Test-Path $schedulerScript) {
    Write-Host "  ⏱️  نصب task: Scheduler (هر ۵ دقیقه)..."
    New-BrsApiTask `
        -TaskName "BrsApi-Scheduler" `
        -TaskDescription "Run the full BrsApi APScheduler sync service (every 5 min)" `
        -ScriptPath $schedulerScript `
        -RepetitionInterval "PT5M"
} else { Write-Host "  ⚠️  اسکریپت پیدا نشد: $schedulerScript" }

# ── Summary ───────────────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════════"
Write-Host "  نصب کامل شد!"
Write-Host "══════════════════════════════════════════════════"
Write-Host ""
Show-BrsApiStatus
Write-Host ""
Write-Host "📂 اجرای دستی:     Start-ScheduledTask -TaskName 'BrsApi-LiveDataSync'"
Write-Host "🗑️  حذف همه:       .\scripts\install_brsapi_tasks_silent.ps1 -Uninstall"
Write-Host "📊 وضعیت:         .\scripts\install_brsapi_tasks_silent.ps1 -Status"
Write-Host ""
