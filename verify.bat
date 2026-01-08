@echo off
REM System Verification Script - Check all components

echo ========================================
echo Billiards Analytics System v1.5 - Verification
echo ========================================
echo.

set ALL_GOOD=1

REM 1. Check Backend Files
echo [1/6] Checking backend core files...
call :CheckFile "backend\main.py"
call :CheckFile "backend\config.py"
call :CheckFile "backend\session_manager.py"
call :CheckFile "backend\tracking_engine.py"
call :CheckFile "backend\calibration.py"
call :CheckFile "backend\mjpeg_streamer.py"
call :CheckFile "backend\requirements.txt"
call :CheckFile "backend\.env.example"
call :CheckFile "backend\error_codes.py"

REM 2. Check Frontend Files
echo.
echo [2/6] Checking frontend core files...
call :CheckFile "frontend\package.json"
call :CheckFile "frontend\tsconfig.json"
call :CheckFile "frontend\vite.config.ts"
call :CheckFile "frontend\index.html"
call :CheckFile "frontend\src\main.tsx"
call :CheckFile "frontend\src\App.tsx"
call :CheckFile "frontend\src\sdk\index.ts"
call :CheckFile "frontend\src\sdk\types.ts"
call :CheckFile "frontend\src\sdk\SessionManager.ts"
call :CheckFile "frontend\src\sdk\WebSocketManager.ts"
call :CheckFile "frontend\src\sdk\ConnectionHealthMachine.ts"
call :CheckFile "frontend\src\sdk\MetadataBuffer.ts"
call :CheckFile "frontend\src\hooks\useBilliardsSDK.ts"
call :CheckFile "frontend\src\components\Dashboard.tsx"

REM 3. Check Documentation
echo.
echo [3/6] Checking documentation...
call :CheckFile "README.md"
call :CheckFile "V1.5\API_REFERENCE.md"
call :CheckFile "V1.5\ARCHITECTURE.md"
call :CheckFile "V1.5\IMPLEMENTATION_GUIDE.md"

REM 4. Check Python
echo.
echo [4/6] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK Python: %%i
) else (
    echo   ERROR Python not installed
    set ALL_GOOD=0
)

REM 5. Check Node.js
echo.
echo [5/6] Checking Node.js environment...
node --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   OK Node.js: %%i
) else (
    echo   ERROR Node.js not installed
    set ALL_GOOD=0
)

REM 6. Check Configuration
echo.
echo [6/6] Checking configuration files...
if exist "backend\.env" (
    echo   OK backend\.env exists
) else (
    echo   WARNING backend\.env not found (will use defaults^)
    echo     Suggestion: copy backend\.env.example backend\.env
)

if exist "frontend\.env" (
    echo   OK frontend\.env exists
) else (
    echo   WARNING frontend\.env not found (will use defaults^)
)

REM Summary
echo.
echo ========================================
if %ALL_GOOD% equ 1 (
    echo SUCCESS System verification passed!
    echo ========================================
    echo.
    echo Next steps:
    echo   1. Configure backend: Edit backend\.env (optional^)
    echo   2. Start system: start.bat
    echo   3. Open frontend: http://localhost:5173
    echo   4. Read docs: README.md
) else (
    echo FAILED System verification failed!
    echo ========================================
    echo.
    echo Please check the missing files above
)
echo.
pause
exit /b

:CheckFile
if exist %~1 (
    echo   OK %~1
) else (
    echo   MISSING %~1
    set ALL_GOOD=0
)
exit /b
