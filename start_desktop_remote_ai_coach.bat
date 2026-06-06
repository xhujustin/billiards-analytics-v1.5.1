@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "LOCAL_CLOUDFLARED=%ROOT%tools\cloudflared\cloudflared.exe"
set "CLOUDFLARED_EXE=cloudflared"
set "BACKEND_TUNNEL_LOG=%ROOT%runtime\cloudflared-desktop-backend.log"
set "FRONTEND_TUNNEL_LOG=%ROOT%runtime\cloudflared-desktop-frontend.log"
set "BACKEND_PORT=8001"
set "FRONTEND_PORT=3000"
set "AI_COACH_PORT=8010"
set "AI_COACH_WAIT_SECONDS=1200"
set "BACKEND_WAIT_SECONDS=120"
set "FRONTEND_WAIT_SECONDS=90"

echo ========================================
echo CueVex AI Coach Desktop Remote
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

echo Checking AI Coach service on :%AI_COACH_PORT% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%AI_COACH_PORT%/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo Starting AI Coach and vLLM in a separate window...
    start "CueVex AI Coach Service" /D "%ROOT%" cmd /k "call start_ai_coach.bat"
) else (
    echo OK AI Coach is already responding.
)

echo Waiting for AI Coach health check...
set "AI_COACH_READY="
for /l %%i in (1,1,%AI_COACH_WAIT_SECONDS%) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%AI_COACH_PORT%/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "AI_COACH_READY=1"
        goto ai_coach_ready
    )
    timeout /t 1 /nobreak >nul
)

:ai_coach_ready
if not defined AI_COACH_READY (
    echo ERROR AI Coach did not pass health check on http://127.0.0.1:%AI_COACH_PORT%/health within %AI_COACH_WAIT_SECONDS% seconds.
    echo Check the CueVex AI Coach Service window for vLLM startup errors.
    pause
    exit /b 1
)
echo OK AI Coach is ready.
echo.

echo Starting Backend (FastAPI on :%BACKEND_PORT%)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%BACKEND_PORT%" ^| findstr "LISTENING"') do (
    echo Port %BACKEND_PORT% is already in use by PID %%P. Stopping old backend...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
start "CueVex Backend Desktop Remote" /D "%ROOT%backend" cmd /k "set AI_COACH_ENABLED=true&& set AI_COACH_MODE=websocket&& set AI_COACH_WS_URL=ws://localhost:%AI_COACH_PORT%/ws/coach&& echo Starting FastAPI with AI Coach bridge... && ..\.venv\Scripts\python.exe main.py"

echo Waiting for Backend health check...
set "BACKEND_READY="
for /l %%i in (1,1,%BACKEND_WAIT_SECONDS%) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto backend_ready
    )
    timeout /t 1 /nobreak >nul
)

:backend_ready
if not defined BACKEND_READY (
    echo ERROR Backend did not pass health check on http://127.0.0.1:%BACKEND_PORT%/health within %BACKEND_WAIT_SECONDS% seconds.
    pause
    exit /b 1
)
echo OK Backend is ready.

echo Checking Backend AI Coach bridge state...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $state = Invoke-RestMethod -Uri 'http://127.0.0.1:%BACKEND_PORT%/api/coach/state' -TimeoutSec 5; if ($state.connected -eq $true) { exit 0 }; Write-Host ('AI Coach bridge is not connected yet: ' + ($state | ConvertTo-Json -Compress)); exit 1 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo WARNING Backend is running, but AI Coach bridge is not connected yet.
    echo You can continue, but AI Coach replies may fail until /api/coach/state reports connected=true.
)
echo.

echo Starting Cloudflare Quick Tunnel for Backend...
if exist "%BACKEND_TUNNEL_LOG%" del "%BACKEND_TUNNEL_LOG%" >nul 2>&1
set "BACKEND_PUBLIC_URL="
start "CueVex Desktop Backend Tunnel" cmd /c ""%CLOUDFLARED_EXE%" tunnel --url http://127.0.0.1:%BACKEND_PORT% > "%BACKEND_TUNNEL_LOG%" 2>&1"
for /l %%i in (1,1,45) do (
    for /f "usebackq tokens=*" %%U in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%BACKEND_TUNNEL_LOG%') { $text = Get-Content '%BACKEND_TUNNEL_LOG%' -Raw; $m = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'); if ($m.Success) { $m.Value } }"`) do (
        set "BACKEND_PUBLIC_URL=%%U"
    )
    if not "!BACKEND_PUBLIC_URL!"=="" goto backend_tunnel_ready
    timeout /t 1 /nobreak >nul
)

:backend_tunnel_ready
if "%BACKEND_PUBLIC_URL%"=="" (
    echo ERROR Could not find a backend trycloudflare.com URL in:
    echo %BACKEND_TUNNEL_LOG%
    pause
    exit /b 1
)
set "BACKEND_PUBLIC_WS=%BACKEND_PUBLIC_URL:https:=wss:%"
echo OK Backend public URL: %BACKEND_PUBLIC_URL%
echo.

echo Starting Frontend (Vite on :%FRONTEND_PORT%)...
if not exist "%ROOT%frontend\node_modules" (
    echo Installing frontend dependencies...
    pushd "%ROOT%frontend"
    call npm.cmd install
    if errorlevel 1 (
        popd
        echo ERROR npm install failed in frontend.
        pause
        exit /b 1
    )
    popd
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%FRONTEND_PORT%" ^| findstr "LISTENING"') do (
    echo Port %FRONTEND_PORT% is already in use by PID %%P. Stopping old frontend...
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
start "CueVex Frontend Desktop Remote" /D "%ROOT%frontend" cmd /k "set VITE_BACKEND_URL=%BACKEND_PUBLIC_URL%&& set VITE_BACKEND_WS=%BACKEND_PUBLIC_WS%&& set VITE_AI_COACH_WS=ws://localhost:%AI_COACH_PORT%/ws/coach&& echo Starting Vite with Backend %BACKEND_PUBLIC_URL% ... && npm.cmd run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

echo Waiting for Frontend dev server...
set "FRONTEND_READY="
for /l %%i in (1,1,%FRONTEND_WAIT_SECONDS%) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%FRONTEND_PORT%' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "FRONTEND_READY=1"
        goto frontend_ready
    )
    timeout /t 1 /nobreak >nul
)

:frontend_ready
if not defined FRONTEND_READY (
    echo ERROR Frontend did not respond on http://127.0.0.1:%FRONTEND_PORT% within %FRONTEND_WAIT_SECONDS% seconds.
    pause
    exit /b 1
)
echo OK Frontend is ready.
echo.

echo Starting Cloudflare Quick Tunnel for Frontend...
if exist "%FRONTEND_TUNNEL_LOG%" del "%FRONTEND_TUNNEL_LOG%" >nul 2>&1
set "FRONTEND_PUBLIC_URL="
start "CueVex Desktop Frontend Tunnel" cmd /c ""%CLOUDFLARED_EXE%" tunnel --url http://127.0.0.1:%FRONTEND_PORT% > "%FRONTEND_TUNNEL_LOG%" 2>&1"
for /l %%i in (1,1,45) do (
    for /f "usebackq tokens=*" %%U in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%FRONTEND_TUNNEL_LOG%') { $text = Get-Content '%FRONTEND_TUNNEL_LOG%' -Raw; $m = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'); if ($m.Success) { $m.Value } }"`) do (
        set "FRONTEND_PUBLIC_URL=%%U"
    )
    if not "!FRONTEND_PUBLIC_URL!"=="" goto frontend_tunnel_ready
    timeout /t 1 /nobreak >nul
)

:frontend_tunnel_ready
if "%FRONTEND_PUBLIC_URL%"=="" (
    echo ERROR Could not find a frontend trycloudflare.com URL in:
    echo %FRONTEND_TUNNEL_LOG%
    pause
    exit /b 1
)

echo.
echo ========================================
echo AI Coach Desktop Remote Started
echo ========================================
echo Open this URL on other devices:
echo   %FRONTEND_PUBLIC_URL%
echo.
echo Public Backend API:
echo   %BACKEND_PUBLIC_URL%
echo.
echo Local checks:
echo   AI Coach: http://127.0.0.1:%AI_COACH_PORT%/health
echo   Backend:  http://127.0.0.1:%BACKEND_PORT%/health
echo   Coach:    http://127.0.0.1:%BACKEND_PORT%/api/coach/state
echo.
echo AI Coach WebSocket remains local only:
echo   ws://localhost:%AI_COACH_PORT%/ws/coach
echo.
echo This trycloudflare URL may change every time you restart this script.
echo Close the service and tunnel windows to stop remote access.
echo.
pause
