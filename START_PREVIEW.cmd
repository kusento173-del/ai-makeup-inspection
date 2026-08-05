@echo off
chcp 65001 >nul
title AI Makeup Monitor Preview
cd /d "%~dp0"

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File ".\scripts\makeup_monitor.ps1" -Mode Preview
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Preview finished. No group messages were sent and no dedupe state was written.
pause
exit /b %EXIT_CODE%

