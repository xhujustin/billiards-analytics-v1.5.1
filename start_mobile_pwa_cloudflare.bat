@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "ENV_FILE=%ROOT%mobile-remote.env"
set "LOCAL_CLOUDFLARED=%ROOT%tools\cloudflared\cloudflared.exe"
set "CLOUDFLARED_EXE=cloudflared"
set "NAMED_TUNNEL_LOG=%ROOT%runtime\cloudflared-pwa-named-tunnel.log"
set "API_PORT=8001"
set "PWA_WEB_PORT=19006"

echo ========================================
echo CueVex Mobile PWA Cloudflare Domain Mode
echo ========================================
echo.
echo This mode uses a Cloudflare Named Tunnel with your own domain.
echo It does not use random trycloudflare.com URLs or Expo Go.
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

where cloudflared >nul 2>&1
if errorlevel 1 (
    if exist "%LOCAL_CLOUDFLARED%" (
        set "CLOUDFLARED_EXE=%LOCAL_CLOUDFLARED%"
    ) else (
        echo ERROR cloudflared was not found.
        echo Run install_cloudflared.bat or install cloudflared manually.
        pause
        exit /b 1
    )
)

set "CLOUDFLARE_TUNNEL_MODE=named"
set "CLOUDFLARE_TUNNEL_NAME="
set "PWA_PUBLIC_URL="
set "PWA_API_BASE_URL="
set "ACCOUNT_STORE_BACKEND=supabase"
set "SUPABASE_URL="
set "SUPABASE_SERVICE_ROLE_KEY="
set "SUPABASE_STORAGE_BUCKET=community-uploads"
set "EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=819200"

if exist "%ENV_FILE%" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

if not "%CLOUDFLARE_TUNNEL_MODE%"=="named" (
    echo ERROR mobile-remote.env must set CLOUDFLARE_TUNNEL_MODE=named for domain PWA mode.
    pause
    exit /b 1
)

if "%CLOUDFLARE_TUNNEL_NAME%"=="" (
    echo ERROR mobile-remote.env must set CLOUDFLARE_TUNNEL_NAME.
    echo Example: CLOUDFLARE_TUNNEL_NAME=cuevex-mobile
    pause
    exit /b 1
)

if "%PWA_PUBLIC_URL%"=="" (
    echo ERROR mobile-remote.env must set PWA_PUBLIC_URL.
    echo Example: PWA_PUBLIC_URL=https://app.example.com
    pause
    exit /b 1
)
echo %PWA_PUBLIC_URL% | findstr /I "CHANGE_ME" >nul
if not errorlevel 1 (
    echo ERROR Replace PWA_PUBLIC_URL in mobile-remote.env with your real PWA domain.
    pause
    exit /b 1
)

if "%PWA_API_BASE_URL%"=="" (
    echo ERROR mobile-remote.env must set PWA_API_BASE_URL.
    echo Example: PWA_API_BASE_URL=https://api.example.com
    pause
    exit /b 1
)
echo %PWA_API_BASE_URL% | findstr /I "CHANGE_ME" >nul
if not errorlevel 1 (
    echo ERROR Replace PWA_API_BASE_URL in mobile-remote.env with your real API domain.
    pause
    exit /b 1
)

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
echo Starting Cloudflare Named Tunnel
echo ========================================
set "TUNNEL_ALREADY_CONNECTED="
powershell -NoProfile -ExecutionPolicy Bypass -Command "$name='%CLOUDFLARE_TUNNEL_NAME%'; $out=& '%CLOUDFLARED_EXE%' tunnel info $name 2>&1; $text=($out -join [Environment]::NewLine); if ($LASTEXITCODE -ne 0) { $out | Out-File -Encoding utf8 '%NAMED_TUNNEL_LOG%'; if ($text -match 'Cannot determine default origin certificate path|Error locating origin cert|client didn''t specify origincert path') { exit 3 }; if ($text -match 'error parsing tunnel ID|could not find tunnel|not found') { exit 2 }; exit 2 }; if ($text -match 'CONNECTOR ID') { exit 0 }; exit 1"
if errorlevel 3 (
    echo WARN Cloudflare Named Tunnel cannot be inspected because cloudflared is not logged in for this Windows user.
    echo Check %NAMED_TUNNEL_LOG%.
    echo Continuing without restarting cloudflared, assuming the named tunnel is handled by the Windows service.
    echo To inspect or change the tunnel manually, run:
    echo   cloudflared tunnel login
    echo   cloudflared tunnel list
    echo   cloudflared tunnel info "%CLOUDFLARE_TUNNEL_NAME%"
    set "TUNNEL_ALREADY_CONNECTED=1"
) else if errorlevel 2 (
    echo ERROR Cloudflare Named Tunnel was not found or cannot be inspected.
    echo Check %NAMED_TUNNEL_LOG%.
    echo Run: cloudflared tunnel list
    echo Then set CLOUDFLARE_TUNNEL_NAME in mobile-remote.env to the exact tunnel NAME or ID.
    pause
    exit /b 1
)
if not errorlevel 1 (
    set "TUNNEL_ALREADY_CONNECTED=1"
    echo OK Named tunnel is already connected by cloudflared.
)

if not defined TUNNEL_ALREADY_CONNECTED (
    for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq cloudflared.exe" /NH 2^>nul ^| findstr /I "cloudflared.exe"') do (
        echo Stopping old cloudflared process PID %%P...
        taskkill /PID %%P /F >nul 2>&1
    )
    timeout /t 1 /nobreak >nul

    if exist "%NAMED_TUNNEL_LOG%" del "%NAMED_TUNNEL_LOG%" >nul 2>&1
    start "CueVex Cloudflare Named Tunnel" cmd /c ""%CLOUDFLARED_EXE%" tunnel run "%CLOUDFLARE_TUNNEL_NAME%" > "%NAMED_TUNNEL_LOG%" 2>&1"
    echo Started named tunnel: %CLOUDFLARE_TUNNEL_NAME%
    echo Log: %NAMED_TUNNEL_LOG%
    echo.
    timeout /t 3 /nobreak >nul
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$log='%NAMED_TUNNEL_LOG%'; if (Test-Path $log) { $text=Get-Content $log -Raw; if ($text -match 'error parsing tunnel ID') { exit 3 }; if ($text -match 'Cannot determine default origin certificate path|Error locating origin cert|credentials file') { exit 2 } }"
    if errorlevel 3 (
        echo ERROR Cloudflare Named Tunnel name or ID is invalid.
        echo Check %NAMED_TUNNEL_LOG%.
        echo Run: cloudflared tunnel list
        echo Then set CLOUDFLARE_TUNNEL_NAME in mobile-remote.env to the exact tunnel NAME or ID.
        pause
        exit /b 1
    )
    if errorlevel 2 (
        echo ERROR Cloudflare Named Tunnel did not start.
        echo Check %NAMED_TUNNEL_LOG%.
        echo This usually means cloudflared is not logged in, cert.pem is missing, or the tunnel credentials file is missing.
        echo Run: cloudflared tunnel login
        echo Or use start_mobile_remote.bat for a temporary quick tunnel URL.
        pause
        exit /b 1
    )
)

echo ========================================
echo Starting Backend (FastAPI on :%API_PORT%)
echo ========================================
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%API_PORT%" ^| findstr "LISTENING"') do (
    echo Port %API_PORT% is already in use by PID %%P. Stopping old backend...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

start "CueVex Backend PWA Domain" /D "%ROOT%backend" cmd /k "set MOBILE_PUBLIC_BASE_URL=%PWA_API_BASE_URL%&& set MOBILE_REQUIRE_HTTPS_QR=true&& set ACCOUNT_STORE_BACKEND=%ACCOUNT_STORE_BACKEND%&& set SUPABASE_URL=%SUPABASE_URL%&& set SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%&& set SUPABASE_STORAGE_BUCKET=%SUPABASE_STORAGE_BUCKET%&& set AI_COACH_ENABLED=true&& set AI_COACH_MODE=websocket&& set AI_COACH_WS_URL=ws://localhost:8010/ws/coach&& set AI_COACH_STREAMING_ENABLED=true&& echo Starting FastAPI server for PWA domain %PWA_API_BASE_URL% ... && ..\.venv\Scripts\python.exe main.py"

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

start "CueVex Mobile PWA Domain" /D "%ROOT%mobile" cmd /k "set EXPO_PUBLIC_MOBILE_API_URL=%PWA_API_BASE_URL%&& set EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=%EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES%&& set PWA_WEB_PORT=%PWA_WEB_PORT%&& set EXPO_NO_TELEMETRY=1&& npm.cmd run web:pwa"

echo Waiting for local PWA preview...
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
echo Mobile PWA Cloudflare Domain Started
echo ========================================
echo PWA:       %PWA_PUBLIC_URL%
echo API:       %PWA_API_BASE_URL%
echo Local PWA: http://127.0.0.1:%PWA_WEB_PORT%/?api=http://127.0.0.1:%API_PORT%^&v=pwa-local
echo Mode:      Cloudflare Named Tunnel, domain PWA
echo.
echo Cloudflare ingress must route:
echo   PWA domain -^> http://127.0.0.1:%PWA_WEB_PORT%
echo   API domain -^> http://127.0.0.1:%API_PORT%
echo.
pause
