@echo off
setlocal

cd /d "%~dp0"

if not defined AI_COACH_HOST set "AI_COACH_HOST=0.0.0.0"
if not defined AI_COACH_PORT set "AI_COACH_PORT=8010"
if not defined AI_COACH_API_URL set "AI_COACH_API_URL=http://127.0.0.1:8002/v1/chat/completions"
if not defined AI_COACH_MODEL set "AI_COACH_MODEL=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
if /i "%AI_COACH_MODEL%"=="/home/lucian039/gemma-4-awq" set "AI_COACH_MODEL=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
if not defined AI_COACH_AUTO_START_VLLM set "AI_COACH_AUTO_START_VLLM=1"
if not defined AI_COACH_VLLM_BASE_URL set "AI_COACH_VLLM_BASE_URL=http://127.0.0.1:8002"
if not defined AI_COACH_VLLM_HOST set "AI_COACH_VLLM_HOST=0.0.0.0"
if not defined AI_COACH_VLLM_PORT set "AI_COACH_VLLM_PORT=8002"
if not defined AI_COACH_VLLM_START_MODE set "AI_COACH_VLLM_START_MODE=wsl"
if not defined AI_COACH_VLLM_PYTHON set "AI_COACH_VLLM_PYTHON=/home/lucian039/miniconda3/envs/vllm_env/bin/python"
if not defined AI_COACH_VLLM_MAX_MODEL_LEN set "AI_COACH_VLLM_MAX_MODEL_LEN=8192"
if not defined AI_COACH_VLLM_GPU_MEMORY_UTILIZATION set "AI_COACH_VLLM_GPU_MEMORY_UTILIZATION=0.6"
if not defined AI_COACH_VLLM_MAX_NUM_SEQS set "AI_COACH_VLLM_MAX_NUM_SEQS=1"
if not defined PYTORCH_CUDA_ALLOC_CONF set "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"
if not defined AI_COACH_VLLM_COMMAND set "AI_COACH_VLLM_COMMAND=%AI_COACH_VLLM_PYTHON% -m vllm.entrypoints.openai.api_server --model %AI_COACH_MODEL% --host %AI_COACH_VLLM_HOST% --port %AI_COACH_VLLM_PORT% --max-model-len %AI_COACH_VLLM_MAX_MODEL_LEN% --gpu-memory-utilization %AI_COACH_VLLM_GPU_MEMORY_UTILIZATION% --max-num-seqs %AI_COACH_VLLM_MAX_NUM_SEQS%"
set "AI_COACH_WSL_VLLM_COMMAND=export PYTORCH_CUDA_ALLOC_CONF=%PYTORCH_CUDA_ALLOC_CONF%; %AI_COACH_VLLM_COMMAND%"
if not defined AI_COACH_VLLM_TIMEOUT_SECONDS set "AI_COACH_VLLM_TIMEOUT_SECONDS=900"
if not defined AI_COACH_MAX_TOKENS set "AI_COACH_MAX_TOKENS=220"
if not defined AI_COACH_MAX_PROMPT_CHARS set "AI_COACH_MAX_PROMPT_CHARS=4500"
if not defined AI_COACH_SERVER_WS_PING_INTERVAL set "AI_COACH_SERVER_WS_PING_INTERVAL=0"
if not defined AI_COACH_SERVER_WS_PING_TIMEOUT set "AI_COACH_SERVER_WS_PING_TIMEOUT=0"

set "REQUESTED_AI_COACH_PORT=%AI_COACH_PORT%"
set "AVAILABLE_AI_COACH_PORT="
for /f "delims=" %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$start=[int]$env:AI_COACH_PORT; $port=$start; while ($port -le ($start + 20)) { $listener=$null; try { $listener=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $port); $listener.Start(); $listener.Stop(); Write-Output $port; exit 0 } catch { if ($listener) { $listener.Stop() }; $port++ } }; exit 1"') do set "AVAILABLE_AI_COACH_PORT=%%P"
if not defined AVAILABLE_AI_COACH_PORT (
    echo No available AI Coach port found from %REQUESTED_AI_COACH_PORT% to %REQUESTED_AI_COACH_PORT% + 20.
    pause
    exit /b 1
)
if not "%AVAILABLE_AI_COACH_PORT%"=="%REQUESTED_AI_COACH_PORT%" (
    if /i "%AI_COACH_STRICT_PORT%"=="1" (
        echo ERROR AI Coach port %REQUESTED_AI_COACH_PORT% is already in use.
        echo The main backend is configured to connect to ws://localhost:%REQUESTED_AI_COACH_PORT%/ws/coach.
        echo Close the stale AI Coach Service window or stop the process using this port, then run start.bat again.
        pause
        exit /b 1
    )
    echo Port %REQUESTED_AI_COACH_PORT% is already in use. Using %AVAILABLE_AI_COACH_PORT% instead.
    set "AI_COACH_PORT=%AVAILABLE_AI_COACH_PORT%"
)

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

set "PYTHON_EXE=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if "%PYTHON_EXE%"=="python" if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if "%PYTHON_EXE%"=="python" (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3"
)
if "%PYTHON_EXE%"=="python" (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR Python was not found. Create ai_coach\.venv, install system Python, or keep the project root .venv available.
        pause
        exit /b 1
    )
)

echo AI Coach service starting...
echo Host: %AI_COACH_HOST%
echo Port: %AI_COACH_PORT%
echo vLLM API: %AI_COACH_API_URL%
echo Model: %AI_COACH_MODEL%
echo Auto-start vLLM: %AI_COACH_AUTO_START_VLLM%
echo vLLM command: %AI_COACH_VLLM_COMMAND%
echo PyTorch CUDA alloc conf: %PYTORCH_CUDA_ALLOC_CONF%
echo.

if /i "%AI_COACH_DRY_RUN%"=="1" (
    echo Dry run enabled. Startup configuration is valid.
    endlocal
    exit /b 0
)

if /i "%AI_COACH_AUTO_START_VLLM%"=="1" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%AI_COACH_VLLM_BASE_URL%/v1/models' | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if errorlevel 1 (
        echo vLLM is not responding at %AI_COACH_VLLM_BASE_URL%. Starting vLLM...
        if /i "%AI_COACH_VLLM_START_MODE%"=="wsl" (
            where wsl.exe >nul 2>&1
            if errorlevel 1 (
                echo wsl.exe was not found. Please install WSL or set AI_COACH_VLLM_START_MODE=windows.
                pause
                exit /b 1
            )
            start "AI Coach vLLM" powershell -NoExit -ExecutionPolicy Bypass -Command "wsl.exe bash -lc '%AI_COACH_WSL_VLLM_COMMAND%'"
        ) else (
            start "AI Coach vLLM" powershell -NoExit -ExecutionPolicy Bypass -Command "%AI_COACH_VLLM_COMMAND%"
        )
        echo Waiting for vLLM at %AI_COACH_VLLM_BASE_URL% ...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds([int]$env:AI_COACH_VLLM_TIMEOUT_SECONDS); do { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 ($env:AI_COACH_VLLM_BASE_URL + '/v1/models') | Out-Null; exit 0 } catch { Start-Sleep -Seconds 2 } } while ((Get-Date) -lt $deadline); exit 1"
        if errorlevel 1 (
            echo vLLM did not become ready within %AI_COACH_VLLM_TIMEOUT_SECONDS% seconds.
            pause
            exit /b 1
        )
    ) else (
        echo vLLM is already running at %AI_COACH_VLLM_BASE_URL%.
    )
    echo.
) else (
    echo Auto-start vLLM is disabled. Please make sure vLLM is already running at %AI_COACH_VLLM_BASE_URL%.
    echo.
)

%PYTHON_EXE% -m ai_coach.service

if errorlevel 1 (
    echo.
    echo AI Coach service exited with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)

endlocal
