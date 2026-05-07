@echo off
REM Billiards Analytics System v1.5 - Startup Script

echo ========================================
echo Billiards Analytics System v1.5 - Starting...
echo ========================================
echo.

REM Check project virtual environment
echo Checking Python virtual environment...
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -c "import sys; print(sys.executable)" >nul 2>&1
    if errorlevel 1 (
        echo ERROR .venv is broken. Delete .venv and run install.bat again.
        echo.
        echo Current .venv was created from:
        if exist .venv\pyvenv.cfg type .venv\pyvenv.cfg
        echo.
        echo Python is not currently available to this terminal.
        echo Install Python 3.10-3.12, then run:
        echo   rmdir /s /q .venv
        echo   install.bat
        pause
        exit /b 1
    )
    echo OK Project .venv is available.
) else (
    echo ERROR Missing .venv\Scripts\python.exe. Please run install.bat first.
    pause
    exit /b 1
)

REM Check Node.js
echo Checking Node.js...
node --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo OK Node.js installed: %%i
) else (
    echo ERROR Node.js not installed, please install Node.js 16+
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting AI Coach WebSocket Service (:8010)
echo ========================================

REM Start AI Coach in new window. It stays decoupled from the backend and talks over WebSocket only.
if exist "%~dp0ai_coach\start.bat" (
    start "AI Coach Service" cmd /k "cd /d %~dp0ai_coach && call start.bat"
) else (
    echo WARNING ai_coach\start.bat not found. AI Coach chat will be unavailable.
)

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo Starting Backend (FastAPI on :8001)
echo ========================================

REM Start backend in new window
start "Backend Server" cmd /k "cd /d %~dp0backend && set AI_COACH_ENABLED=true&& set AI_COACH_MODE=websocket&& set AI_COACH_WS_URL=ws://localhost:8010/ws/coach&& echo Checking YOLO GPU... && (..\\.venv\\Scripts\\python.exe test-program\\utils\\check_yolo_gpu.py || echo WARNING PyTorch CUDA is not available. YOLO may run on CPU.) && echo Starting FastAPI server... && ..\\.venv\\Scripts\\python.exe main.py"

timeout /t 8 /nobreak >nul

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
echo AI Coach WS: ws://localhost:8010/ws/coach
echo Frontend UI:  http://localhost:5173
echo API Docs: http://localhost:8001/docs
echo motion tracking: http://localhost:8001/stream/motion
echo Projection: http://localhost:8001/stream/projector
echo.
echo Close the terminal windows to stop the services
echo.
pause
