@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   AI EXAM PROCTORING SYSTEM - SETUP AND RUN
echo ===================================================

cd /d "%~dp0"

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python.
    pause
    exit /b 1
)

:: Create directories if they do not exist
if not exist "app" mkdir app
if not exist "app\templates" mkdir app\templates

:: Setup Virtual Environment
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment in .venv...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate Virtual Environment and install requirements
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo [INFO] Installing required dependencies (this might take a few minutes)...
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [INFO] Setup complete! Starting Uvicorn Web Server...
echo [INFO] Access the Proctoring Dashboard at: http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

pause
