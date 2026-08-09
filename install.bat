@echo off
REM --- INSTALL.BAT ---
REM This script installs the required Python packages for the YT Downloader app.

echo Checking for Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
echo.
echo ERROR: Python was not found. Please install Python and make sure it is added to your PATH.
echo You can download it from python.org.
echo.
pause
exit /b 1
)

echo Installing required Python modules (Flask and yt-dlp)...
python -m pip install flask yt-dlp

REM The yt-dlp application requires ffmpeg for handling video/audio processing.
echo.
echo NOTE: yt-dlp often requires the 'ffmpeg' program for video/audio processing (like merging or converting).
echo If you encounter errors during download, please make sure 'ffmpeg' is installed and added to your PATH.
echo.

echo Installation complete! You can now run the application using run.bat.
pause