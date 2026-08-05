@echo off
chcp 65001 >nul
title AI Makeup Monitor
cd /d "%~dp0"

echo AI Makeup Monitor
echo.
echo Keep this window open to monitor every 10 minutes.
echo Close this window or press Ctrl+C to stop.
echo.

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File ".\scripts\makeup_monitor.ps1" -Mode Monitor
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" echo Monitor exited with code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%

