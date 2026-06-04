@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "MOBILE_DIR=%ROOT%mobile"
set "LOCAL_CLOUDFLARED=%ROOT%tools\cloudflared\cloudflared.exe"
set "CLOUDFLARED_EXE=cloudflared"
set "EXPO_TUNNEL_LOG=%ROOT%runtime\cloudflared-mobile-expo.log"
set "EXPO_WEB_PREVIEW_PORT=19006"
set "EXPO_METRO_PORT=18181"
set "EXPO_PUBLIC_MOBILE_API_URL=https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app"
set "EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=819200"
set "METRO_TEMP_DIR=%ROOT%runtime\metro-temp"

echo ========================================
echo CueVex Mobile - Cloud Run API
echo ========================================
echo.
echo API: %EXPO_PUBLIC_MOBILE_API_URL%
echo.

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
        echo Run install_cloudflared.bat or start_mobile_remote.bat once to install it.
        pause
        exit /b 1
    )
)

if "%CLOUDFLARED_EXE%"=="cloudflared" (
    where cloudflared >nul 2>&1
    if errorlevel 1 (
        echo ERROR cloudflared is still not available.
        pause
        exit /b 1
    )
)

if not exist "%MOBILE_DIR%\package.json" (
    echo ERROR mobile package.json was not found:
    echo %MOBILE_DIR%\package.json
    pause
    exit /b 1
)

if not exist "%MOBILE_DIR%\node_modules" (
    echo Installing mobile dependencies...
    pushd "%MOBILE_DIR%"
    call npm.cmd install
    if errorlevel 1 (
        popd
        echo ERROR npm install failed in mobile.
        pause
        exit /b 1
    )
    popd
)

echo Stopping old CueVex mobile Node processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$mobile = '%MOBILE_DIR%'; Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -and $_.CommandLine.Contains($mobile) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
timeout /t 1 /nobreak >nul

if not exist "%ROOT%runtime" mkdir "%ROOT%runtime"
if exist "%METRO_TEMP_DIR%" (
    rmdir /s /q "%METRO_TEMP_DIR%" >nul 2>&1
)
mkdir "%METRO_TEMP_DIR%" >nul 2>&1

for %%P in (%EXPO_WEB_PREVIEW_PORT% %EXPO_METRO_PORT%) do (
    for /f "tokens=5" %%Q in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
        echo Port %%P is already in use by PID %%Q. Stopping old Expo process...
        taskkill /PID %%Q /F >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul

echo Starting Cloudflare Quick Tunnel for Expo Metro...
set "EXPO_PUBLIC_URL="
if exist "%EXPO_TUNNEL_LOG%" del "%EXPO_TUNNEL_LOG%" >nul 2>&1
start "CueVex Mobile Expo Cloudflare Tunnel" cmd /c ""%CLOUDFLARED_EXE%" tunnel --url http://127.0.0.1:%EXPO_METRO_PORT% > "%EXPO_TUNNEL_LOG%" 2>&1"

for /l %%i in (1,1,30) do (
    for /f "usebackq tokens=*" %%U in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%EXPO_TUNNEL_LOG%') { $text = Get-Content '%EXPO_TUNNEL_LOG%' -Raw; $m = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'); if ($m.Success) { $m.Value } }"`) do (
        set "EXPO_PUBLIC_URL=%%U"
    )
    if not "!EXPO_PUBLIC_URL!"=="" goto expo_tunnel_ready
    timeout /t 1 /nobreak >nul
)

:expo_tunnel_ready
if "%EXPO_PUBLIC_URL%"=="" (
    echo ERROR Could not find an Expo trycloudflare.com URL in:
    echo %EXPO_TUNNEL_LOG%
    pause
    exit /b 1
)

set "EXPO_TUNNEL_HOST=%EXPO_PUBLIC_URL:https://=%"
set "EXPO_GO_URL_EXP=exp://%EXPO_TUNNEL_HOST%"
set "EXPO_GO_URL_EXPS=exps://%EXPO_TUNNEL_HOST%"
echo OK Expo tunnel URL: %EXPO_PUBLIC_URL%
echo.

echo Starting Expo Metro on port %EXPO_METRO_PORT%...
start "CueVex Mobile Expo Metro" /D "%MOBILE_DIR%" cmd /k "set TEMP=%METRO_TEMP_DIR%&& set TMP=%METRO_TEMP_DIR%&& set REACT_NATIVE_PACKAGER_HOSTNAME=%EXPO_TUNNEL_HOST%&& set EXPO_PACKAGER_PROXY_URL=%EXPO_PUBLIC_URL%&& set EXPO_PUBLIC_MOBILE_API_URL=%EXPO_PUBLIC_MOBILE_API_URL%&& set EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=%EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES%&& set EXPO_NO_TELEMETRY=1&& npm.cmd run start -- --port %EXPO_METRO_PORT% --offline --clear"

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

echo.
echo ========================================
echo CueVex Mobile Started
echo ========================================
echo API:       %EXPO_PUBLIC_MOBILE_API_URL%
echo Tunnel:    %EXPO_PUBLIC_URL%
echo Expo exp:  %EXPO_GO_URL_EXP%
echo Expo exps: %EXPO_GO_URL_EXPS%
echo.
echo Scan this QR with Expo Go. The QR uses the exps URL because iOS Expo Go may reject exp URLs from Cloudflare.
if exist "%MOBILE_DIR%\node_modules\.bin\qrcode-terminal.cmd" (
    call "%MOBILE_DIR%\node_modules\.bin\qrcode-terminal.cmd" "%EXPO_GO_URL_EXPS%"
) else (
    echo %EXPO_GO_URL_EXPS%
)
echo Press w in the Expo Metro window if you want to open the web preview.
echo This QR is for development only; the Cloud Run API URL is stable.
echo.
pause
