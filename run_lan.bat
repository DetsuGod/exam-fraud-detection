@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   AI EXAM PROCTORING SYSTEM - LAN SETUP AND RUN
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

:: Generate SSL cert if not exists
if not exist "cert.pem" (
    echo [INFO] Generating self-signed SSL certificate...
    python gen_cert.py
)

:: Detect local IP address
python get_ip.py >nul 2>&1
if exist "_ip.tmp" (
    for /f "delims=" %%i in (_ip.tmp) do set LOCAL_IP=%%i
    del _ip.tmp
) else (
    set LOCAL_IP=127.0.0.1
)

echo.
echo ================================================================
echo   SERVER DANG KHOI DONG - CHO ~10 GIAY ROI CLICK LINK...
echo ================================================================
echo.
echo   [ADMIN]  https://!LOCAL_IP!:8001/
echo   [THI SINH] https://!LOCAL_IP!:8001/exam
echo.
echo   LUU Y: Lan dau truy cap, bam "Advanced" roi "Proceed to..."
echo          de bo qua canh bao chung chi tu ky.
echo ================================================================
echo.

:: Auto-open Admin Dashboard in default browser after server loads (~10s)
start /b cmd /c "timeout /t 10 /nobreak >nul && start https://!LOCAL_IP!:8001/"

echo [INFO] Starting Uvicorn HTTPS Server on https://0.0.0.0:8001 ...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --ssl-keyfile key.pem --ssl-certfile cert.pem

pause
