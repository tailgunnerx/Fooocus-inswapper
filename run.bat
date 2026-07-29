@echo off
setlocal EnableDelayedExpansion

:: Make sure we're running from the repo root
cd /d "%~dp0"

:: Activate the virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run configure.bat first.
    pause & exit /b 1
)

call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause & exit /b 1
)

:: Pass all arguments through to launch.py
python launch.py %*