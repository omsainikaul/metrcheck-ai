@echo off
setlocal
title MetrCheck AI - Server Controller (National Hackathon 6.0)
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ============================================================
    echo   ERROR: Python virtual environment not found in venv\
    echo   Please run setup.bat first to initialize dependencies.
    echo ============================================================
    pause
    exit /b 1
)

"venv\Scripts\python.exe" "runner.py"
set RUNNER_EXIT=%ERRORLEVEL%

if %RUNNER_EXIT% neq 0 (
    echo.
    echo ============================================================
    echo   [!] MetrCheck AI runner exited with code %RUNNER_EXIT%
    echo ============================================================
    pause
    exit /b %RUNNER_EXIT%
)

exit /b 0
