@echo off
REM Billiards Analytics System v1.5 - Startup Script

echo ========================================
echo Billiards Analytics System v1.5 - Starting...
echo ========================================
echo.

REM Check Python
echo Checking Python...
if exist "%~dp0.venv\Scripts\python.exe" (
    echo OK Python virtual environment found
) else (
    echo WARNING Global python not found and .venv not found.
    echo Trying to proceed anyway...
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
start "Backend Server" cmd /k "cd /d %~dp0 && (if not exist .venv\Scripts\python.exe (echo ERROR Missing .venv\Scripts\python.exe && exit /b 1)) && echo Using Python: %~dp0.venv\Scripts\python.exe && cd /d %~dp0backend && echo Starting FastAPI server... && ..\.venv\Scripts\python.exe main.py"

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
echo motion tracking: http://localhost:8001/stream/motion
echo Projection: http://localhost:8001/stream/projector
echo.
echo Close the terminal windows to stop the services
echo.
pause

