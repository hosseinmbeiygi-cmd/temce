<#
.SYNOPSIS
    Install the nightly BrsApi auto-sync Windows Scheduled Task.
.DESCRIPTION
    Registers one per-user task that runs sync_all_tables_auto.bat every day
    at 00:10 local time (Tehran in this environment), after the daily quota
    reset. The task uses the project's virtualenv Python through the batch
    wrapper and writes logs under <project>\logs.

    This installer intentionally runs as the current user. It does not need
    administrator/UAC privileges and works with the project on the user's
    Desktop. The user must be logged in at the scheduled time.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_brsapi_auto_sync.ps1
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_brsapi_auto_sync.ps1 -Status
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_brsapi_auto_sync.ps1 -RunNow
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_brsapi_auto_sync.ps1 -Uninstall
#>

[CmdletBinding()]
param(
    [switch]$Status,
    [switch]$RunNow,
    [switch]$Uninstall,
    [string]$Time = "00:10"
)

$ErrorActionPreference = "Stop"
$TaskName = "BrsApi-NightlyAutoSync"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$BatchPath = Join-Path $ProjectRoot "scripts\sync_all_tables_auto.bat"

function Get-TaskOrNull {
    Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

function Show-TaskStatus {
    $task = Get-TaskOrNull
    if ($null -eq $task) {
        Write-Host "No task registered: $TaskName"
        return
    }

    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    [pscustomobject]@{
        TaskName       = $task.TaskName
        State          = $task.State
        NextRunTime    = $info.NextRunTime
        LastRunTime    = $info.LastRunTime
        LastTaskResult = $info.LastTaskResult
        Action         = ($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " | "
    } | Format-List
}

if (-not (Test-Path -LiteralPath $BatchPath)) {
    throw "Sync wrapper was not found: $BatchPath"
}

if ($Uninstall) {
    if (Get-TaskOrNull) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed task: $TaskName"
    } else {
        Write-Host "Task was not registered: $TaskName"
    }
    exit 0
}

if ($Status) {
    Show-TaskStatus
    exit 0
}

# Validate the requested local time before registering the task.
try {
    $parsedTime = [datetime]::ParseExact($Time, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
} catch {
    throw "Time must use 24-hour HH:mm format, for example 00:10. Received: $Time"
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/d /c `"`"$BatchPath`"`"" `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $parsedTime
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries:$true `
    -DontStopIfGoingOnBatteries:$true `
    -StartWhenAvailable:$true `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -MultipleInstances IgnoreNew

$userId = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Run scripts/sync_all_tables_auto.py nightly after the BrsApi daily quota reset."

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Write-Host "Registered: $TaskName"
Write-Host "Schedule:   daily at $Time (local Windows time)"
Write-Host "Wrapper:    $BatchPath"
Write-Host "Account:    $userId"

if ($RunNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started task now. Check the log under $ProjectRoot\logs after it finishes."
}

Show-TaskStatus
