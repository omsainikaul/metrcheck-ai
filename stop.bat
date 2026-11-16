@echo off
setlocal
title MetrCheck AI - Stop Servers (National Hackathon 6.0)
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "runner.py" --stop
) else (
    echo ============================================================
    echo   MetrCheck AI - Stopping Application Servers...
    echo ============================================================
    if exist .runner.pid (
        set /p RUNNER_PID=<.runner.pid
        if defined RUNNER_PID (
            taskkill /F /T /PID %RUNNER_PID% >nul 2>&1
            echo   [OK] Terminated runner process tree.
        )
        del /f /q .runner.pid >nul 2>&1
    )
    echo   [OK] Stop completed.
)

exit /b 0
