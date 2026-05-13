#!/bin/bash

# vLLM 快速部署腳本
# 功能: 一鍵啟動 vLLM 服務

set -e

VLLM_MODEL="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
VLLM_MAX_MODEL_LEN="2048"
VLLM_GPU_MEMORY_UTILIZATION="0.6"
VLLM_MAX_NUM_SEQS="1"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

echo "vLLM startup script"
echo "================================"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查 Python
echo -e "${BLUE}[1/5]${NC} 檢查 Python 環境..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}Python ${python_version}${NC}"

# 檢查 CUDA
echo -e "${BLUE}[2/5]${NC} 檢查 CUDA 與 GPU..."
if command -v nvidia-smi &> /dev/null; then
    gpu_count=$(nvidia-smi --list-gpus | wc -l)
    echo -e "${GREEN}偵測到 ${gpu_count} 個 GPU${NC}"
    nvidia-smi --query-gpu=index,name,memory.total --format=csv,nounits,noheader
else
    echo -e "${RED}未偵測到 CUDA/GPU${NC}"
    echo "NVIDIA CUDA/GPU was not detected"
    exit 1
fi

# 安裝 vLLM
echo -e "${BLUE}[3/5]${NC} 安裝 vLLM..."
pip install vllm torch transformers -q
echo -e "${GREEN}vLLM installed${NC}"

# 下載模型（可選）
echo -e "${BLUE}[4/5]${NC} 模型下載（首次需要 10-30 分鐘）..."
echo "推薦模型: ${VLLM_MODEL}"
read -p "是否下載模型？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
model_name = 'cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit'
print(f'下載模型: {model_name}...')
tokenizer = AutoTokenizer.from_pretrained(model_name)
print('模型下載完成')
"
fi

# 啟動 vLLM 服務
echo -e "${BLUE}[5/5]${NC} 啟動 vLLM 服務..."
echo ""
echo -e "${YELLOW}啟動命令:${NC}"
echo ""
echo "vllm serve ${VLLM_MODEL} \\"
echo "    --host 0.0.0.0 \\"
echo "    --port 8000 \\"
echo "    --max-model-len ${VLLM_MAX_MODEL_LEN} \\"
echo "    --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION} \\"
echo "    --max-num-seqs ${VLLM_MAX_NUM_SEQS} \\"
echo "    --enable-prefix-caching \\"
echo "    --dtype auto"
echo ""
echo -e "${YELLOW}服務資訊:${NC}"
echo "  - API 端點: http://localhost:8000/v1"
echo "  - OpenAI 相容 API 連接埠: 8000"
echo "  - 推理模型: ${VLLM_MODEL}"
echo ""
echo -e "${YELLOW}啟動中...${NC}"
echo ""

# 啟動服務
vllm serve "${VLLM_MODEL}" \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len "${VLLM_MAX_MODEL_LEN}" \
    --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION}" \
    --max-num-seqs "${VLLM_MAX_NUM_SEQS}" \
    --enable-prefix-caching \
    --dtype auto \
    2>&1
