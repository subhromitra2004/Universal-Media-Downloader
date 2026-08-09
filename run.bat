@echo off
REM --- RUN.BAT ---
REM This script starts the Flask web server and automatically opens the app in your browser.

REM --- FIX: FORCE NODE.JS DETECTION ---


set APP_PORT=5000
set APP_URL=http://127.0.0.1:%APP_PORT%

echo Starting YT Downloader (app.py) on port %APP_PORT%...

REM Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python not found. Please run install.bat first, or make sure Python is installed and on your PATH.
    echo.
    pause
    exit /b 1
)

REM Small delay to allow Flask to start before opening browser
start "" cmd /c "timeout /t 2 >nul && start %APP_URL%"

REM Run the Flask app
python -u app.py

pause