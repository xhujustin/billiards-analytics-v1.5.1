@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "ENV_FILE=%ROOT%mobile-remote.env"
set "LOCAL_CLOUDFLARED=%ROOT%tools\cloudflared\cloudflared.exe"
set "CLOUDFLARED_EXE=cloudflared"
set "TUNNEL_LOG=%ROOT%runtime\cloudflared-quick-tunnel.log"
set "EXPO_TUNNEL_LOG=%ROOT%runtime\cloudflared-expo-tunnel.log"
set "EXPO_WEB_PREVIEW_PORT=19006"

echo ========================================
echo CueVex Mobile Remote Quick Tunnel
echo ========================================
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
        echo cloudflared was not found. Starting installer...
        call "%ROOT%install_cloudflared.bat"
        if exist "%LOCAL_CLOUDFLARED%" (
            set "CLOUDFLARED_EXE=%LOCAL_CLOUDFLARED%"
        ) else (
            where cloudflared >nul 2>&1
            if not errorlevel 1 set "CLOUDFLARED_EXE=cloudflared"
        )
    )
)

if "%CLOUDFLARED_EXE%"=="cloudflared" (
    where cloudflared >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR cloudflared is still not available.
        echo Run install_cloudflared.bat again or install cloudflared manually.
        pause
        exit /b 1
    )
)

if not exist "%ROOT%runtime" mkdir "%ROOT%runtime"

for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq cloudflared.exe" /NH 2^>nul ^| findstr /I "cloudflared.exe"') do (
    echo Stopping old Cloudflare tunnel process PID %%P...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

set "MOBILE_REQUIRE_HTTPS_QR=true"
set "CLOUDFLARE_TUNNEL_MODE=quick"
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

if not defined EXPO_METRO_PORT set "EXPO_METRO_PORT=18181"

echo ========================================
echo Starting Cloudflare Quick Tunnel
echo ========================================
set "MOBILE_PUBLIC_BASE_URL="
for /l %%R in (1,1,3) do (
    if not "!MOBILE_PUBLIC_BASE_URL!"=="" goto tunnel_ready
    if exist "%TUNNEL_LOG%" del "%TUNNEL_LOG%" >nul 2>&1
    echo Starting Cloudflare Quick Tunnel attempt %%R/3...
    start "CueVex Cloudflare Quick Tunnel" cmd /c ""%CLOUDFLARED_EXE%" tunnel --url http://127.0.0.1:8001 > "%TUNNEL_LOG%" 2>&1"

    echo Waiting for trycloudflare.com URL...
    for /l %%i in (1,1,30) do (
        for /f "usebackq tokens=*" %%U in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%TUNNEL_LOG%') { $text = Get-Content '%TUNNEL_LOG%' -Raw; $m = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'); if ($m.Success) { $m.Value } }"`) do (
            set "MOBILE_PUBLIC_BASE_URL=%%U"
        )
        if not "!MOBILE_PUBLIC_BASE_URL!"=="" goto tunnel_ready
        timeout /t 1 /nobreak >nul
    )
    echo Cloudflare Quick Tunnel attempt %%R did not return a URL. Retrying...
)

:tunnel_ready
if "%MOBILE_PUBLIC_BASE_URL%"=="" (
    echo ERROR Could not find a trycloudflare.com URL in:
    echo %TUNNEL_LOG%
    echo Check the Cloudflare Quick Tunnel window.
    pause
    exit /b 1
)

>"%ENV_FILE%" echo MOBILE_PUBLIC_BASE_URL=%MOBILE_PUBLIC_BASE_URL%
>>"%ENV_FILE%" echo CLOUDFLARE_TUNNEL_MODE=quick
>>"%ENV_FILE%" echo MOBILE_REQUIRE_HTTPS_QR=true
>>"%ENV_FILE%" echo ACCOUNT_STORE_BACKEND=%ACCOUNT_STORE_BACKEND%
>>"%ENV_FILE%" echo SUPABASE_URL=%SUPABASE_URL%
>>"%ENV_FILE%" echo SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%
>>"%ENV_FILE%" echo SUPABASE_STORAGE_BUCKET=%SUPABASE_STORAGE_BUCKET%
>>"%ENV_FILE%" echo EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=%EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES%
echo OK Quick Tunnel URL: %MOBILE_PUBLIC_BASE_URL%
echo.

echo ========================================
echo Starting Backend (FastAPI on :8001)
echo ========================================
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Port 8001 is already in use by PID %%P. Stopping old backend...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
start "CueVex Backend Remote" /D "%ROOT%backend" cmd /k "set MOBILE_PUBLIC_BASE_URL=%MOBILE_PUBLIC_BASE_URL%&& set MOBILE_REQUIRE_HTTPS_QR=true&& set ACCOUNT_STORE_BACKEND=%ACCOUNT_STORE_BACKEND%&& set SUPABASE_URL=%SUPABASE_URL%&& set SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%&& set SUPABASE_STORAGE_BUCKET=%SUPABASE_STORAGE_BUCKET%&& set AI_COACH_ENABLED=true&& set AI_COACH_MODE=websocket&& set AI_COACH_WS_URL=ws://localhost:8010/ws/coach&& set AI_COACH_STREAMING_ENABLED=true&& echo Starting FastAPI server with %MOBILE_PUBLIC_BASE_URL% ... && ..\.venv\Scripts\python.exe main.py"

echo Waiting for Backend health check...
set "BACKEND_READY="
for /l %%i in (1,1,60) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto backend_ready
    )
    timeout /t 1 /nobreak >nul
)

:backend_ready
if not defined BACKEND_READY (
    echo ERROR Backend did not pass health check on http://127.0.0.1:8001/health within 60 seconds.
    pause
    exit /b 1
)
echo OK Backend is ready.
echo.

echo ========================================
echo Starting Expo Mobile Dev Server
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

for %%P in (%EXPO_WEB_PREVIEW_PORT% %EXPO_METRO_PORT%) do (
    for /f "tokens=5" %%Q in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
        echo Port %%P is already in use by PID %%Q. Stopping old Expo process...
        taskkill /PID %%Q /F >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul

echo Starting local computer preview on port %EXPO_WEB_PREVIEW_PORT%...
start "CueVex Expo Web Preview" /D "%ROOT%mobile" cmd /k "set EXPO_PUBLIC_MOBILE_API_URL=%MOBILE_PUBLIC_BASE_URL%&& set EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=%EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES%&& set EXPO_NO_TELEMETRY=1&& npm.cmd run web -- --port %EXPO_WEB_PREVIEW_PORT% --offline --clear"

echo Starting Expo Metro locally on port %EXPO_METRO_PORT%...
start "CueVex Expo Metro" /D "%ROOT%mobile" cmd /k "set EXPO_PUBLIC_MOBILE_API_URL=%MOBILE_PUBLIC_BASE_URL%&& set EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=%EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES%&& set EXPO_NO_TELEMETRY=1&& npm.cmd run start:remote -- --port %EXPO_METRO_PORT% --clear"

echo Waiting for Expo Metro status...
set "EXPO_READY="
for /l %%i in (1,1,60) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%EXPO_METRO_PORT%/status' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "EXPO_READY=1"
        goto expo_ready
    )
    timeout /t 1 /nobreak >nul
)

:expo_ready
if not defined EXPO_READY (
    echo ERROR Expo Metro did not pass status check on http://127.0.0.1:%EXPO_METRO_PORT%/status within 60 seconds.
    pause
    exit /b 1
)
echo OK Expo Metro is ready.
echo.

echo ========================================
echo Starting Cloudflare Quick Tunnel for Expo
echo ========================================
set "EXPO_PUBLIC_URL="
for /l %%R in (1,1,3) do (
    set "EXPO_CANDIDATE_URL="
    if exist "%EXPO_TUNNEL_LOG%" del "%EXPO_TUNNEL_LOG%" >nul 2>&1
    echo Starting Expo Cloudflare Quick Tunnel attempt %%R/3...
    start "CueVex Expo Cloudflare Tunnel" cmd /c ""%CLOUDFLARED_EXE%" tunnel --url http://127.0.0.1:%EXPO_METRO_PORT% > "%EXPO_TUNNEL_LOG%" 2>&1"

    echo Waiting for Expo trycloudflare.com URL...
    for /l %%i in (1,1,30) do (
        for /f "usebackq tokens=*" %%U in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%EXPO_TUNNEL_LOG%') { $text = Get-Content '%EXPO_TUNNEL_LOG%' -Raw; $m = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'); if ($m.Success) { $m.Value } }"`) do (
            set "EXPO_CANDIDATE_URL=%%U"
        )
        if not "!EXPO_CANDIDATE_URL!"=="" goto expo_candidate_found
        timeout /t 1 /nobreak >nul
    )

    :expo_candidate_found
    if "!EXPO_CANDIDATE_URL!"=="" (
        echo Expo Cloudflare Quick Tunnel attempt %%R did not return a URL. Retrying...
    ) else (
        echo Checking Expo tunnel status: !EXPO_CANDIDATE_URL!/status
        for /l %%i in (1,1,90) do (
            powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $u='!EXPO_CANDIDATE_URL!'; $h=([Uri]$u).Host; Resolve-DnsName $h -ErrorAction Stop | Out-Null; $r=Invoke-WebRequest -Uri ($u + '/status') -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
            if not errorlevel 1 (
                set "EXPO_PUBLIC_URL=!EXPO_CANDIDATE_URL!"
                goto expo_tunnel_ready
            )
            timeout /t 1 /nobreak >nul
        )
        echo ERROR Expo tunnel is not reachable yet:
        echo !EXPO_CANDIDATE_URL!/status
        echo Retrying with a fresh Cloudflare tunnel...
        timeout /t 1 /nobreak >nul
    )
)

:expo_tunnel_ready
if "%EXPO_PUBLIC_URL%"=="" (
    echo ERROR Expo tunnel did not become reachable after 3 attempts.
    echo Check %EXPO_TUNNEL_LOG% or retry start_mobile_remote.bat later.
    pause
    exit /b 1
)

set "EXPO_GO_URL=%EXPO_PUBLIC_URL:https://=exps://%"
echo OK Expo URL: %EXPO_GO_URL%
echo.

>>"%ENV_FILE%" echo EXPO_PUBLIC_URL=%EXPO_PUBLIC_URL%
>>"%ENV_FILE%" echo EXPO_GO_URL=%EXPO_GO_URL%
>>"%ENV_FILE%" echo EXPO_METRO_PORT=%EXPO_METRO_PORT%

if exist "%ROOT%mobile\node_modules\.bin\qrcode-terminal.cmd" (
    echo Scan this QR with Expo Go:
    call "%ROOT%mobile\node_modules\.bin\qrcode-terminal.cmd" "%EXPO_GO_URL%"
) else (
    echo qrcode-terminal was not found. Open this URL in Expo Go:
    echo %EXPO_GO_URL%
)

echo.
echo ========================================
echo Remote Mobile Quick Tunnel Started
echo ========================================
echo Public API: %MOBILE_PUBLIC_BASE_URL%
echo Local API:  http://127.0.0.1:8001
echo Expo URL:  %EXPO_GO_URL%
echo PC View:   http://127.0.0.1:%EXPO_WEB_PREVIEW_PORT%/?api=http://127.0.0.1:8001
echo Mode:       Cloudflare Quick Tunnel
echo.
echo Expo is exposed through Cloudflare Quick Tunnel, so it does not depend on ngrok.
echo Open PC View in your browser to inspect the same mobile UI locally.
echo In Expo Go, open the mobile app and log in with:
echo   %MOBILE_PUBLIC_BASE_URL%
echo.
echo This trycloudflare URL may change every time you restart this script.
echo Regenerate friend QR codes after each restart.
echo.
pause
