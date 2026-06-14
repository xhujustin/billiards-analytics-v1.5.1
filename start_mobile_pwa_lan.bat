@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "ENV_FILE=%ROOT%mobile-remote.env"
set "API_PORT=8001"
set "PWA_WEB_PORT=19006"

echo ========================================
echo CueVex Mobile PWA LAN Mode
echo ========================================
echo.
echo This mode does not use Cloudflare proxy or Expo Go.
echo Open the printed PWA URL on a phone connected to the same LAN.
echo.

if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo ERROR Missing .venv\Scripts\python.exe. Please run install.bat first.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo ERROR Node.js was not found. Please install Node.js 16+.
    pause
    exit /b 1
)

set "ACCOUNT_STORE_BACKEND=supabase"
set "SUPABASE_URL="
set "SUPABASE_SERVICE_ROLE_KEY="
set "SUPABASE_STORAGE_BUCKET=community-uploads"
set "EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=819200"
set "MOBILE_PUBLIC_BASE_URL="

if exist "%ENV_FILE%" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

if not "%PWA_WEB_PORT%"=="" set "PWA_WEB_PORT=%PWA_WEB_PORT%"

set "LAN_IP="
if not "%MOBILE_PUBLIC_BASE_URL%"=="" (
    for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { ([Uri]'%MOBILE_PUBLIC_BASE_URL%').Host } catch { '' }"`) do set "LAN_IP=%%I"
)
if "%LAN_IP%"=="" (
    for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1 -ExpandProperty IPAddress; if ($ip) { $ip }"`) do set "LAN_IP=%%I"
)
if "%LAN_IP%"=="" set "LAN_IP=127.0.0.1"

set "PWA_API_BASE_URL=http://%LAN_IP%:%API_PORT%"
set "PWA_PUBLIC_URL=http://%LAN_IP%:%PWA_WEB_PORT%/?api=http://%LAN_IP%:%API_PORT%^&v=pwa-lan"

if /I "%ACCOUNT_STORE_BACKEND%"=="supabase" (
    if "%SUPABASE_URL%"=="" (
        echo ERROR ACCOUNT_STORE_BACKEND=supabase requires SUPABASE_URL in %ENV_FILE%.
        pause
        exit /b 1
    )
    if "%SUPABASE_SERVICE_ROLE_KEY%"=="" (
        echo ERROR ACCOUNT_STORE_BACKEND=supabase requires SUPABASE_SERVICE_ROLE_KEY in %ENV_FILE%.
        pause
        exit /b 1
    )
)

if not exist "%ROOT%runtime" mkdir "%ROOT%runtime"

echo ========================================
echo Starting Backend (FastAPI on :%API_PORT%)
echo ========================================
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%API_PORT%" ^| findstr "LISTENING"') do (
    echo Port %API_PORT% is already in use by PID %%P. Stopping old backend...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

start "CueVex Backend PWA LAN" /D "%ROOT%backend" cmd /k "set MOBILE_PUBLIC_BASE_URL=%PWA_API_BASE_URL%&& set MOBILE_REQUIRE_HTTPS_QR=false&& set ACCOUNT_STORE_BACKEND=%ACCOUNT_STORE_BACKEND%&& set SUPABASE_URL=%SUPABASE_URL%&& set SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%&& set SUPABASE_STORAGE_BUCKET=%SUPABASE_STORAGE_BUCKET%&& set AI_COACH_ENABLED=true&& set AI_COACH_MODE=websocket&& set AI_COACH_WS_URL=ws://localhost:8010/ws/coach&& set AI_COACH_STREAMING_ENABLED=true&& echo Starting FastAPI server for PWA LAN %PWA_API_BASE_URL% ... && ..\.venv\Scripts\python.exe main.py"

echo Waiting for Backend health check...
set "BACKEND_READY="
for /l %%i in (1,1,60) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%API_PORT%/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto backend_ready
    )
    timeout /t 1 /nobreak >nul
)

:backend_ready
if not defined BACKEND_READY (
    echo ERROR Backend did not pass health check on http://127.0.0.1:%API_PORT%/health within 60 seconds.
    pause
    exit /b 1
)
echo OK Backend is ready.
echo.

echo ========================================
echo Starting Mobile PWA Web Preview
echo ========================================
if not exist "%ROOT%mobile\node_modules" (
    echo Installing mobile dependencies...
    pushd "%ROOT%mobile"
    call npm.cmd install
    if errorlevel 1 (
        popd
        echo ERROR npm install failed in mobile.
        pause
        exit /b 1
    )
    popd
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PWA_WEB_PORT%" ^| findstr "LISTENING"') do (
    echo Port %PWA_WEB_PORT% is already in use by PID %%P. Stopping old PWA preview...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

start "CueVex Mobile PWA LAN" /D "%ROOT%mobile" cmd /k "set EXPO_PUBLIC_MOBILE_API_URL=%PWA_API_BASE_URL%&& set EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=%EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES%&& set PWA_WEB_PORT=%PWA_WEB_PORT%&& set EXPO_NO_TELEMETRY=1&& npm.cmd run web:pwa"

echo Waiting for PWA preview...
set "PWA_READY="
for /l %%i in (1,1,60) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%PWA_WEB_PORT%/?api=http://127.0.0.1:%API_PORT%^&v=pwa-local' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "PWA_READY=1"
        goto pwa_ready
    )
    timeout /t 1 /nobreak >nul
)

:pwa_ready
if not defined PWA_READY (
    echo ERROR PWA preview did not pass health check on http://127.0.0.1:%PWA_WEB_PORT% within 60 seconds.
    pause
    exit /b 1
)

echo OK PWA preview is ready.
echo.
echo ========================================
echo Mobile PWA LAN Started
echo ========================================
echo API:       %PWA_API_BASE_URL%
echo PC View:   http://127.0.0.1:%PWA_WEB_PORT%/?api=http://127.0.0.1:%API_PORT%^&v=pwa-local
echo Phone PWA: http://%LAN_IP%:%PWA_WEB_PORT%/?api=http://%LAN_IP%:%API_PORT%^&v=pwa-lan
echo Mode:      PWA LAN, no proxy
echo.
echo Phone and PC must be on the same network. If the phone cannot open the URL, allow Windows Firewall for ports %PWA_WEB_PORT% and %API_PORT%.
echo.
pause
