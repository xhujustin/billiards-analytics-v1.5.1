@echo off
REM Billiards Analytics System v1.5 - Startup Script

echo ========================================
echo Billiards Analytics System v1.5 - Starting...
echo ========================================
echo.

REM Check Python
echo Checking Python...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo OK Python installed: !PYTHON_VERSION!
) else (
    echo ERROR Python not installed, please install Python 3.8+
    pause
    exit /b 1
)

REM Check Node.js
echo Checking Node.js...
node --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VERSION=%%i
    echo OK Node.js installed: !NODE_VERSION!
) else (
    echo ERROR Node.js not installed, please install Node.js 16+
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting Backend (FastAPI on :8001)
echo ========================================

REM Start backend in new window
start "Backend Server" cmd /k "cd /d %~dp0backend && (if exist venv\Scripts\activate.bat (echo Activating virtual environment... && call venv\Scripts\activate.bat) else (echo Creating virtual environment... && python -m venv venv && call venv\Scripts\activate.bat && pip install -r requirements.txt)) && echo Starting FastAPI server... && python main.py"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo Starting Frontend (Vite on :5173)
echo ========================================

REM Start frontend in new window
start "Frontend Server" cmd /k "cd /d %~dp0frontend && (if not exist node_modules (echo Installing dependencies... && npm install)) && echo Starting Vite dev server... && npm run dev"

echo.
echo ========================================
echo System Started Successfully!
echo ========================================
echo.
echo Backend API: http://localhost:8001
echo Frontend UI:  http://localhost:5173
echo API Docs: http://localhost:8001/docs
echo.
echo Close the terminal windows to stop the services
echo.
pause
