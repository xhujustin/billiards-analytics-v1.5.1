@echo off
REM Billiards Analytics System v1.5 - AI Coach Startup Script

echo ========================================
echo Billiards Analytics System v1.5 - AI Coach
echo ========================================
echo.

if not exist "%~dp0ai_coach\start.bat" (
    echo ERROR Missing ai_coach\start.bat.
    pause
    exit /b 1
)

REM Keep AI Coach on the backend's expected WebSocket port.
set "AI_COACH_STRICT_PORT=1"

echo Starting AI Coach WebSocket Service (:8010)
echo.
call "%~dp0ai_coach\start.bat"

if errorlevel 1 (
    echo.
    echo AI Coach startup failed with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)
