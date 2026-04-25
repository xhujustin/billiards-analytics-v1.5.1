@echo off
REM Billiards Analytics System v1.5 - Installation Script

echo ========================================
echo Billiards Analytics System v1.5 - Installer
echo ========================================
echo.

set "PY_CMD="

REM 1. Check Python
echo [1/4] Checking Python environment...
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    for /f "tokens=*" %%i in ('py -3 --version 2^>^&1') do echo   OK Found %%i
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
        for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK Found %%i
    ) else (
        echo   ERROR Python not found! Please install Python 3.10-3.12 and add it to PATH or install the Python Launcher.
        pause
        exit /b 1
    )
)

REM 2. Check Node.js
echo [2/4] Checking Node.js environment...
node --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   OK Found %%i
) else (
    echo   ERROR Node.js not found! Please install Node.js 16+ and add to PATH.
    pause
    exit /b 1
)

REM 3. Setup Backend
echo.
echo [3/4] Setting up Backend...
cd /d "%~dp0"

if not exist .venv (
    echo   Creating root virtual environment .venv...
    %PY_CMD% -m venv .venv
) else (
    echo   Root virtual environment .venv already exists.
    .venv\Scripts\python.exe -c "import sys; print(sys.executable)" >nul 2>&1
    if errorlevel 1 (
        echo   ERROR Existing .venv is broken.
        echo.
        echo   Current .venv was created from:
        if exist .venv\pyvenv.cfg type .venv\pyvenv.cfg
        echo.
        echo   Please install Python 3.10-3.12, then delete .venv and run install.bat again:
        echo     rmdir /s /q .venv
        echo     install.bat
        pause
        exit /b 1
    )
)

echo   Activating root virtual environment...
call .venv\Scripts\activate.bat

cd /d "%~dp0backend"
echo   Installing/Updating Python dependencies...
python -m pip install --upgrade pip

nvidia-smi >nul 2>&1
if not errorlevel 1 (
    echo   NVIDIA GPU detected. Installing CUDA-enabled PyTorch...
    python -m pip install --upgrade --force-reinstall -r requirements-cuda.txt
) else (
    echo   NVIDIA GPU not detected by nvidia-smi. Keeping default PyTorch install path.
)

pip install -r requirements.txt

echo   Verifying PyTorch CUDA visibility...
python test-program\utils\check_yolo_gpu.py

if not exist ".env" (
    if exist ".env.example" (
        echo   Creating .env from .env.example...
        copy .env.example .env >nul
    ) else (
        echo   WARNING: .env.example not found, skipping .env creation.
    )
) else (
    echo   .env already exists.
)

REM 4. Setup Frontend
echo.
echo [4/4] Setting up Frontend...
cd /d "%~dp0frontend"

if not exist node_modules (
    echo   Installing Node.js dependencies...
    cmd /c npm install
) else (
    echo   Node modules folder exists. Running install to ensure sync...
    cmd /c npm install
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo You can now start the system using 'start.bat'
echo.
pause

