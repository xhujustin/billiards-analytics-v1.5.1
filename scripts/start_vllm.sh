#!/bin/bash

# vLLM 快速部署脚本
# 功能: 一键启动 vLLM 服务

set -e

echo "🚀 vLLM 快速部署脚本"
echo "================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查 Python
echo -e "${BLUE}[1/5]${NC} 检查 Python 环境..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python ${python_version}${NC}"

# 检查 CUDA
echo -e "${BLUE}[2/5]${NC} 检查 CUDA 和 GPU..."
if command -v nvidia-smi &> /dev/null; then
    gpu_count=$(nvidia-smi --list-gpus | wc -l)
    echo -e "${GREEN}✓ 检测到 ${gpu_count} 个 GPU${NC}"
    nvidia-smi --query-gpu=index,name,memory.total --format=csv,nounits,noheader
else
    echo -e "${RED}✗ 未检测到 CUDA/GPU${NC}"
    echo "请确保安装了 NVIDIA CUDA 工具包"
    exit 1
fi

# 安装 vLLM
echo -e "${BLUE}[3/5]${NC} 安装 vLLM..."
pip install vllm torch transformers -q
echo -e "${GREEN}✓ vLLM 已安装${NC}"

# 下载模型（可选）
echo -e "${BLUE}[4/5]${NC} 模型下载 (首次需要 10-30 分钟)..."
echo "推荐模型: unsloth/Qwen2.5-7B-bnb-4bit"
read -p "是否下载模型？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
model_name = 'unsloth/Qwen2.5-7B-bnb-4bit'
print(f'下載模型: {model_name}...')
tokenizer = AutoTokenizer.from_pretrained(model_name)
print('✓ 模型下載完成')
"
fi

# 启动 vLLM 服务
echo -e "${BLUE}[5/5]${NC} 启动 vLLM 服务..."
echo ""
echo -e "${YELLOW}启动命令:${NC}"
echo ""
echo "vllm serve unsloth/Qwen2.5-7B-bnb-4bit \\"
echo "    --host 0.0.0.0 \\"
echo "    --port 8000 \\"
echo "    --max-model-len 2048 \\"
echo "    --gpu-memory-utilization 0.9 \\"
echo "    --enable-prefix-caching \\"
echo "    --dtype float16"
echo ""
echo -e "${YELLOW}服务信息:${NC}"
echo "  - API 端点: http://localhost:8000/v1"
echo "  - OpenAI 兼容 API 端口: 8000"
echo "  - 推理模型: unsloth/Qwen2.5-7B-bnb-4bit"
echo ""
echo -e "${YELLOW}启动中...${NC}"
echo ""

# 启动服务
vllm serve unsloth/Qwen2.5-7B-bnb-4bit \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 2048 \
    --gpu-memory-utilization 0.9 \
    --enable-prefix-caching \
    --dtype float16 \
    2>&1
