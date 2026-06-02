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
call pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Check if PyTorch with CUDA is available
python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] CUDA-enabled PyTorch is already installed.
    goto :START_SERVER
)

echo [INFO] CUDA-enabled PyTorch not found. Checking for NVIDIA GPU...
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] No NVIDIA GPU detected. Running in standard CPU mode.
    goto :START_SERVER
)

echo [INFO] NVIDIA GPU detected! Installing CUDA 12.4 enabled PyTorch for high FPS...
call pip uninstall -y torch torchvision
call pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

:START_SERVER
echo [INFO] Setup complete! Starting Uvicorn Web Server...
echo [INFO] Access the Proctoring Dashboard at: http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

pause