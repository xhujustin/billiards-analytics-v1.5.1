@echo off
REM vLLM 快速部署脚本（Windows）
REM 功能: 一键启动 vLLM 服务

setlocal enabledelayedexpansion

set "VLLM_MODEL=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
set "VLLM_MAX_MODEL_LEN=8192"
set "VLLM_GPU_MEMORY_UTILIZATION=0.6"
set "VLLM_MAX_NUM_SEQS=1"
if not defined PYTORCH_CUDA_ALLOC_CONF set "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"

echo 🚀 vLLM 快速部署脚本 (Windows)
echo ================================
echo.

REM 检查 Python
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python 未安装或不在 PATH 中
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python %PYTHON_VERSION%
echo.

REM 检查 CUDA
echo [2/5] 检查 CUDA 和 GPU...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo ✗ NVIDIA CUDA 工具包未安装
    echo 请访问: https://developer.nvidia.com/cuda-downloads
    pause
    exit /b 1
)
echo ✓ CUDA 已安装
nvidia-smi --query-gpu=index,name,memory.total --format=csv,nounits,noheader
echo.

REM 安装 vLLM
echo [3/5] 安装 vLLM...
pip install vllm torch transformers -q
if errorlevel 1 (
    echo ✗ vLLM 安装失败
    pause
    exit /b 1
)
echo ✓ vLLM 已安装
echo.

REM 模型下载提示
echo [4/5] 模型下载 (首次需要 10-30 分钟)...
echo 推荐模型: %VLLM_MODEL%
set /p DOWNLOAD_MODEL="是否下载模型？(y/n): "
if /i "%DOWNLOAD_MODEL%"=="y" (
    echo 下载模型中...
    python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('%VLLM_MODEL%')" >nul 2>&1
    echo ✓ 模型下载完成
)
echo.

REM 启动 vLLM 服务
echo [5/5] 启动 vLLM 服务...
echo.
echo 启动命令:
echo vllm serve %VLLM_MODEL% ^
echo     --host 0.0.0.0 ^
echo     --port 8000 ^
echo     --max-model-len %VLLM_MAX_MODEL_LEN% ^
echo     --gpu-memory-utilization %VLLM_GPU_MEMORY_UTILIZATION% ^
echo     --max-num-seqs %VLLM_MAX_NUM_SEQS% ^
echo     --enable-prefix-caching ^
echo     --dtype auto
echo.
echo 服务信息:
echo   - API 端点: http://localhost:8000/v1
echo   - OpenAI 兼容 API 端口: 8000
echo   - 推理模型: %VLLM_MODEL%
echo.
echo 启动中...
echo.

REM 启动服务
vllm serve %VLLM_MODEL% ^
    --host 0.0.0.0 ^
    --port 8000 ^
    --max-model-len %VLLM_MAX_MODEL_LEN% ^
    --gpu-memory-utilization %VLLM_GPU_MEMORY_UTILIZATION% ^
    --max-num-seqs %VLLM_MAX_NUM_SEQS% ^
    --enable-prefix-caching ^
    --dtype auto

pause
