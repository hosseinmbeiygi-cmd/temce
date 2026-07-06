# fetch_news_daily.ps1 - Daily news fetch for Windows Task Scheduler
# Usage: powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File scripts/fetch_news_daily.ps1
# Task Scheduler Action:
#   Program: powershell.exe
#   Arguments: -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\Iran\Desktop\temce\scripts\fetch_news_daily.ps1"

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\.."
$LogDir = "$ProjectRoot\logs"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$LogFile = "$LogDir\fetch_news_$Timestamp.log"

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) { $PythonExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $PythonExe) { throw "Python not found in PATH" }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$StartTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$Header = "============================================================`n"
$Header += "  News Fetch Job - Started: $StartTime`n"
$Header += "  Project: $ProjectRoot`n"
$Header += "  Python:  $PythonExe`n"
$Header += "============================================================`n"
$Header | Out-File -FilePath $LogFile -Encoding utf8

try {
    Set-Location $ProjectRoot
    $env:PYTHONIOENCODING = "utf-8"

    & $PythonExe scripts\fetch_news.py --limit 10 --quiet --no-sentiment 2>&1 | Out-File -FilePath $LogFile -Encoding utf8 -Append

    $ExitCode = $LASTEXITCODE
    $FinishTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($ExitCode -eq 0) {
        $Footer = "`n============================================================`n"
        $Footer += "  SUCCESS - Finished: $FinishTime`n"
        $Footer += "============================================================`n"
        $Footer | Out-File -FilePath $LogFile -Encoding utf8 -Append
    } else {
        $Footer = "`n============================================================`n"
        $Footer += "  FAILED (exit code $ExitCode) - Finished: $FinishTime`n"
        $Footer += "============================================================`n"
        $Footer | Out-File -FilePath $LogFile -Encoding utf8 -Append
        exit $ExitCode
    }
} catch {
    $ErrorMsg = $_.Exception.Message
    $ErrFooter = "`n============================================================`n"
    $ErrFooter += "  ERROR: $ErrorMsg`n"
    $ErrFooter += "  Finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"
    $ErrFooter += "============================================================`n"
    $ErrFooter | Out-File -FilePath $LogFile -Encoding utf8 -Append
    exit 1
}
