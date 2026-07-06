@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."
if not exist logs mkdir logs
for /f "tokens=1-4 delims=/-. " %%a in ('date /t') do set LOGDATE=%%a-%%b-%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set LOGTIME=%%a%%b
set LOGTIME=!LOGTIME: =0!
set LOGFILE=logsetch_news_!LOGDATE!_!LOGTIME!.log
echo News Fetch Job - Started: !date! !time! > !LOGFILE!
set PYTHONIOENCODING=utf-8
python scriptsetch_news.py --limit 10 --quiet --no-sentiment >> !LOGFILE! 2>&1
if !ERRORLEVEL! EQU 0 (echo SUCCESS - Finished: !date! !time! >> !LOGFILE!) else (echo FAILED ^(exit !ERRORLEVEL!^) - Finished: !date! !time! >> !LOGFILE!)
endlocal
