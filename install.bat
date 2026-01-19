@echo off
REM Billiards Analytics System v1.5 - Installation Script

echo ========================================
echo Billiards Analytics System v1.5 - Installer
echo ========================================
echo.

REM 1. Check Python
echo [1/3] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK Found %%i
) else (
    echo   ERROR Python not found! Please install Python 3.8+ and add to PATH.
    pause
    exit /b 1
)

REM 2. Check Node.js
echo [2/3] Checking Node.js environment...
node --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   OK Found %%i
) else (
    echo   ERROR Node.js not found! Please install Node.js 16+ and add to PATH.
    pause
    exit /b 1
)

REM 3. Setup Backend
echo.
echo [3/3] Setting up Backend...
cd /d "%~dp0backend"

if not exist venv (
    echo   Creating virtual environment...
    python -m venv venv
) else (
    echo   Virtual environment already exists.
)

echo   Activating virtual environment...
call venv\Scripts\activate.bat

echo   Installing/Updating Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

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
