@echo off
REM ============================================================
REM  BrsApi Auto Sync — runs scripts/sync_all_tables_auto.py
REM  Scheduled daily at 00:10 Tehran (03:40 system, UTC+7) right
REM  after the free BrsApi quota resets at midnight.
REM
REM  Logs appended to logs/brsapi_sync_YYYYMMDD.log
REM ============================================================
setlocal EnableExtensions

REM ── Project root (this batch lives in scripts/) ──────────
set "ROOT=%~dp0.."
cd /d "%ROOT%"

REM ── Log file (daily) ─────────────────────────────────────
set "LOGDIR=%ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
for /f "tokens=1-3 delims=/" %%a in ("%date%") do set "D=%%a%%b%%c"
set "LOG=%LOGDIR%\brsapi_sync_%D%.log"

echo [%date% %time%] ===== BrsApi Auto Sync start ===== >> "%LOG%"

REM ── Run the sync script (UTF-8 output) ──────────────────
"%ROOT%\venv\Scripts\python.exe" -X utf8 "%ROOT%\scripts\sync_all_tables_auto.py" >> "%LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo [%date% %time%] BrsApi Auto Sync finished (exit=%EXIT_CODE%) >> "%LOG%"
exit /b %EXIT_CODE%
