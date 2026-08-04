<#
.SYNOPSIS
    BrsApi Sync Scheduler — Windows Task Scheduler Setup
.DESCRIPTION
    Sets up Windows Scheduled Tasks to automatically run BrsApi sync scripts
    at regular intervals, keeping database tables up-to-date.

    Creates 3 tasks:
    1. BrsApi-LiveDataSync   — Every 5 minutes  (symbols, gold, commodities, crypto)
    2. BrsApi-ComprehensiveSync — Every 2 hours  (NAV, history, shareholders, detail)
    3. BrsApi-Scheduler      — Every 5 minutes  (runs the full APScheduler via start_scheduler.py)

.NOTES
    Run this script as Administrator:
        powershell -ExecutionPolicy Bypass -File scripts/setup_windows_scheduler.ps1

    To remove tasks:
        Unregister-ScheduledTask -TaskName "BrsApi-*" -Confirm:$false

    View scheduled tasks:
        Get-ScheduledTask -TaskName "BrsApi-*" | Format-Table TaskName, State, NextRunTime
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

# -- Configuration --
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$PythonExe   = "python"
$LogDir      = "$ProjectRoot\logs"

# Ensure log directory exists
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# -- Helper: create or update a scheduled task --
function New-BrsApiTask {
    param(
        [string]$TaskName,
        [string]$TaskDescription,
        [string]$ScriptPath,
        [string]$RepetitionInterval,
        [string]$RepetitionDuration = "P1D",
        [string]$WorkingDir = $ProjectRoot
    )

    $actionParams = @{
        Execute = $PythonExe
        Argument = [string]::Format('"{0}"', $ScriptPath)
        WorkingDirectory = $WorkingDir
    }
    $Action = New-ScheduledTaskAction @actionParams

    $triggerParams = @{
        Daily = $true
        At = "00:00"
        RepetitionInterval = $RepetitionInterval
        RepetitionDuration = $RepetitionDuration
    }
    $Trigger = New-ScheduledTaskTrigger @triggerParams

    $settingsParams = @{
        AllowStartIfOnBatteries = $true
        DontStopIfGoingOnBatteries = $true
        StartWhenAvailable = $true
        RestartInterval = "00:01:00"
        RestartCount = 3
        MultipleInstances = "IgnoreNew"
    }
    $Settings = New-ScheduledTaskSettingsSet @settingsParams

    $principalParams = @{
        UserId = "SYSTEM"
        LogonType = "ServiceAccount"
        RunLevel = "Highest"
    }
    $Principal = New-ScheduledTaskPrincipal @principalParams

    $taskParams = @{
        Action = $Action
        Trigger = $Trigger
        Settings = $Settings
        Principal = $Principal
        Description = $TaskDescription
    }
    $Task = New-ScheduledTask @taskParams

    $registerParams = @{
        TaskName = $TaskName
        InputObject = $Task
        Force = $true
    }
    Register-ScheduledTask @registerParams

    Write-Host ("  {0} Created task: {1}" -f [char]0x2705, $TaskName)
}

# -- Main --

Write-Host ""
$sep = ("=" * 60)
Write-Host $sep
Write-Host "  BrsApi Sync Scheduler - Windows Task Setup"
Write-Host $sep
Write-Host ""
Write-Host ("Project root: {0}" -f $ProjectRoot)
Write-Host ("Python:       {0}" -f $PythonExe)
Write-Host ("Log dir:      {0}" -f $LogDir)
Write-Host ""

# -- Task 1: Live Data Sync (every 5 min) --
$liveDataScript = Join-Path $ProjectRoot "scripts" "sync_live_data.py"
if (Test-Path $liveDataScript) {
    $task1Params = @{
        TaskName = "BrsApi-LiveDataSync"
        TaskDescription = "Sync BrsApi live data: symbols, gold, currency, index, commodities, crypto (every 5 min)"
        ScriptPath = $liveDataScript
        RepetitionInterval = "PT5M"
        RepetitionDuration = "P1D"
        WorkingDir = $ProjectRoot
    }
    New-BrsApiTask @task1Params
} else {
    Write-Host ("  {0} Script not found: {1} - skipping" -f [char]0x26A0, $liveDataScript)
}

# -- Task 2: Comprehensive Sync (every 2 hours) --
$fullUpdateScript = Join-Path $ProjectRoot "scripts" "brsapi_full_update.py"
if (Test-Path $fullUpdateScript) {
    $task2Params = @{
        TaskName = "BrsApi-ComprehensiveSync"
        TaskDescription = "Comprehensive BrsApi sync: per-symbol NAV, history, detail, shareholders (every 2 hours)"
        ScriptPath = $fullUpdateScript
        RepetitionInterval = "PT2H"
        RepetitionDuration = "P1D"
        WorkingDir = $ProjectRoot
    }
    New-BrsApiTask @task2Params
} else {
    Write-Host ("  {0} Script not found: {1} - skipping" -f [char]0x26A0, $fullUpdateScript)
}

# -- Task 3: APScheduler Runner (every 5 min) --
$schedulerScript = Join-Path $ProjectRoot "scripts" "start_scheduler.py"
if (Test-Path $schedulerScript) {
    $task3Params = @{
        TaskName = "BrsApi-Scheduler"
        TaskDescription = "Run the full BrsApi APScheduler sync service (every 5 min)"
        ScriptPath = $schedulerScript
        RepetitionInterval = "PT5M"
        RepetitionDuration = "P1D"
        WorkingDir = $ProjectRoot
    }
    New-BrsApiTask @task3Params
} else {
    Write-Host ("  {0} Script not found: {1} - skipping" -f [char]0x26A0, $schedulerScript)
}

# -- Summary --

Write-Host ""
Write-Host $sep
Write-Host "  Setup Complete!"
Write-Host $sep
Write-Host ""
Write-Host "Scheduled tasks created:"
Get-ScheduledTask -TaskName "BrsApi-*" | Format-Table TaskName, State, NextRunTime
Write-Host ""
Write-Host "To view logs:"
Write-Host "  Get-ScheduledTask -TaskName 'BrsApi-*' | Get-ScheduledTaskInfo"
Write-Host ""
Write-Host "To run manually:"
Write-Host "  Start-ScheduledTask -TaskName 'BrsApi-LiveDataSync'"
Write-Host ""
Write-Host "To remove all tasks:"
Write-Host "  Get-ScheduledTask -TaskName 'BrsApi-*' | Unregister-ScheduledTask -Confirm:`$false"
Write-Host ""
Write-Host "To check current scheduler status via API:"
Write-Host "  curl http://localhost:8000/api/v1/scheduler"
Write-Host ""
