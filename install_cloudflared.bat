@echo off
setlocal
set "ROOT=%~dp0"
set "LOCAL_CLOUDFLARED=%ROOT%tools\cloudflared\cloudflared.exe"

echo ========================================
echo Cloudflare cloudflared Installer
echo ========================================
echo.

if exist "%LOCAL_CLOUDFLARED%" (
    echo OK local cloudflared is already available:
    "%LOCAL_CLOUDFLARED%" --version
    echo.
    pause
    exit /b 0
)

where cloudflared >nul 2>&1
if not errorlevel 1 (
    echo OK cloudflared is already installed:
    cloudflared --version
    echo.
    pause
    exit /b 0
)

where winget >nul 2>&1
if errorlevel 1 (
    echo winget was not found. Downloading portable cloudflared.exe to project tools folder...
    if not exist "%ROOT%tools\cloudflared" mkdir "%ROOT%tools\cloudflared"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%LOCAL_CLOUDFLARED%' -UseBasicParsing; exit 0 } catch { Write-Error $_; exit 1 }"
    if errorlevel 1 (
        echo.
        echo ERROR cloudflared download failed.
        echo Install it manually from:
        echo https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
        echo.
        pause
        exit /b 1
    )
    echo.
    echo OK downloaded local cloudflared:
    "%LOCAL_CLOUDFLARED%" --version
    echo.
    pause
    exit /b 0
)

echo Installing cloudflared with winget...
winget install --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo.
    echo ERROR cloudflared installation failed.
    echo You can install it manually from:
    echo https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
    pause
    exit /b 1
)

echo.
echo OK cloudflared installed.
echo Please close and reopen your terminal before running start_mobile_remote.bat.
echo.
pause
