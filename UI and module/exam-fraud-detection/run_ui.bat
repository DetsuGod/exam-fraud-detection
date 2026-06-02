@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   AI EXAM PROCTORING SYSTEM - [UI-ONLY RUNNER]
echo ===================================================
echo [INFO] Khoi dong giao dien nhanh khong load model AI...

cd /d "%~dp0"

:: Auto-detect Python path to bypass Windows App Execution Alias issues
set "PYTHON_CMD=python"
if exist "C:\msys64\ucrt64\bin\python.exe" (
    set "PYTHON_CMD=C:\msys64\ucrt64\bin\python.exe"
    echo [INFO] Phat hien Python tai: !PYTHON_CMD!
)

:: Check Python installation
!PYTHON_CMD! --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python.
    pause
    exit /b 1
)

:: Smart detection: if global packages are already installed, run instantly!
!PYTHON_CMD! -c "import fastapi, uvicorn, jinja2, websockets" >nul 2>&1
if !errorlevel! equ 0 goto run_directly

:: Fallback to Virtual Environment if global packages are missing
echo [INFO] Thieu thu vien he thong. Tien hanh cau hinh moi truong ao (.venv)...
if not exist "app" mkdir app
if not exist "app\templates" mkdir app\templates

:: Setup Virtual Environment
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment in .venv...
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate Virtual Environment - detects both standard and MSYS2 layouts
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment - Scripts...
    call .venv\Scripts\activate.bat
    goto venv_activated
)
if exist ".venv\bin\activate.bat" (
    echo [INFO] Activating virtual environment - bin...
    call .venv\bin\activate.bat
    goto venv_activated
)

echo [ERROR] Could not find activate.bat in .venv.
pause
exit /b 1

:venv_activated
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo [INFO] Installing required dependencies - FastAPI, Uvicorn, Jinja2, etc...
pip install fastapi uvicorn jinja2 websockets
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:run_directly
echo [INFO] Phat hien day du cac thu vien can thiet - FastAPI, Uvicorn, Jinja2, Websockets.
echo [INFO] Dang khoi chay uvicorn truc tiep...
echo.
echo ===================================================
echo [INFO] Giao dien Admin Dashboard: http://127.0.0.1:8000
echo [INFO] Giao dien Sinh vien (Test): http://127.0.0.1:8000/student
echo ===================================================
echo.
!PYTHON_CMD! -m uvicorn app.main_ui:app --host 127.0.0.1 --port 8000 --reload

pause
