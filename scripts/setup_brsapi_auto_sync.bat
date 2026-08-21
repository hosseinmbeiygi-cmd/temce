@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup_brsapi_auto_sync.ps1" %*
exit /b %ERRORLEVEL%
