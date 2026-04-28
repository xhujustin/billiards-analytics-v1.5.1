"""
Qwen 模型部署方案對比（除 Ollama 外）

需要選擇合適的部署方式，需要考慮以下因素：
1. 延遲要求（<200ms 推薦方案）
2. 吞吐量需求
3. 顯卡配置
4. 團隊技術棧
5. 成本預算
"""

# ============ 部署方案對比表 ============

DEPLOYMENT_COMPARISON = """
╔══════════════════════════════════════════════════════════════════════════════╗
║ Qwen 模型部署方案對比                                                         ║
╠═╤═══════════════════╤══════════╤════════╤═══════╤═══════╤════════╤══════════╣
║ │ 方案              │ 延遲     │ 吞吐量 │ 易用性│ 成本  │ 穩定性 │ 推薦場景 ║
╠═╪═══════════════════╪══════════╪════════╪═══════╪═══════╪════════╪══════════╣
║1│ vLLM (推薦)       │ 120ms ✅│ ⭐⭐⭐ │⭐⭐⭐│低    │高     │高吞吐  ║
║2│ Text Gen WebUI    │ 150ms   │ ⭐⭐  │⭐⭐⭐│零    │中     │開發調試║
║3│ LM Studio         │ 180ms   │ ⭐    │⭐⭐⭐│零    │中     │本地demo║
║4│ TGI (HF)          │ 140ms   │ ⭐⭐⭐│⭐⭐  │低    │高     │生產級  ║
║5│ FastAPI +直接推理 │ 160ms   │ ⭐⭐  │⭐⭐  │零    │中     │自定義  ║
║6│ Ray Serve         │ 200ms   │ ⭐⭐⭐│⭐    │中    │高     │分佈式  ║
║7│ BentoML           │ 170ms   │ ⭐⭐  │⭐    │低    │高     │容器化  ║
║8│ Docker + API      │ 200ms   │ ⭐⭐  │⭐⭐  │低    │高     │微服務  ║
║9│ AWS SageMaker     │ 250ms   │ ⭐⭐⭐│⭐⭐⭐│高    │高     │雲端    ║
║10│HuggingFace Spaces│ 300ms   │ ⭐    │⭐⭐⭐│零    │中     │在線演示║
╚═╧═══════════════════╧══════════╧════════╧═══════╧═══════╧════════╧══════════╝

🏆 撞球教練系統推薦: vLLM (方案 1)
  原因：延遲最低 (120ms) + 高吞吐量 + 生產就緒
"""

# ============ 方案 1: vLLM (最推薦) ============

VLLM_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 1: vLLM - 高效 LLM 推論引擎                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 延遲最低 120ms | 吞吐量最高 | 支持多種量化                            │
│ 適用: 高吞吐量實時系統（撞球教練正好符合）                                  │
│ 成本: 零（開源）                                                            │
│ 技術棧: Python + CUDA                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

✅ 核心優勢:
  1. PagedAttention - 減少 KV-Cache 顯卡佔用
  2. 動態批處理 - 自動優化吞吐量
  3. LoRA/QLoRA 支持 - 直接加載微調模型
  4. 多種量化格式支持 - AWQ, GPTQ, 4-bit 等
  5. OpenAI 兼容 API - 無痛替換

🚀 快速開始:

# 1. 安裝
pip install vllm torch transformers

# 2. 啟動服務（自動啟用量化）
vllm serve unsloth/Qwen2.5-7B-bnb-4bit \\
    --host 0.0.0.0 \\
    --port 8000 \\
    --max-model-len 2048 \\
    --gpu-memory-utilization 0.9 \\
    --enable-prefix-caching \\
    --dtype float16

# 3. 調用 API（OpenAI 兼容）
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="token-abc123"  # 任意值即可
)

response = client.completions.create(
    model="unsloth/Qwen2.5-7B-bnb-4bit",
    prompt="白球在左上角，標靶球在底袋位。建議動作：",
    max_tokens=256,
    temperature=0.7
)

print(response.choices[0].text)

# 4. 或使用請求庫
import requests

response = requests.post(
    "http://localhost:8000/v1/completions",
    json={
        "model": "unsloth/Qwen2.5-7B-bnb-4bit",
        "prompt": "測試提示語",
        "max_tokens": 256
    }
).json()

📊 性能指標:
  - 延遲 P50: 120ms
  - 延遲 P95: 180ms
  - 吞吐量: 6-8 samples/sec
  - 內存: 5-6GB (4-bit)

⚙️ 後端集成（FastAPI + vLLM）:

# backend/services/coach_llm_service.py

import asyncio
from typing import Optional
import httpx

class vLLMService:
    \"\"\"vLLM 推論服務客戶端。\"\"\"
    
    def __init__(self, api_url: str = "http://localhost:8000/v1"):
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.model_name = "unsloth/Qwen2.5-7B-bnb-4bit"
    
    async def generate_advice(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        \"\"\"生成建議。\"\"\"
        
        try:
            response = await self.client.post(
                f"{self.api_url}/completions",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.95,
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data["choices"][0]["text"].strip()
        
        except Exception as e:
            logger.error(f"vLLM inference error: {e}")
            raise

# 在 backend/main.py 中使用
vllm_service = vLLMService(api_url="http://localhost:8000/v1")

@app.post("/api/coach/generate-advice")
async def generate_advice_endpoint(request: AdviceRequest):
    advice = await vllm_service.generate_advice(
        prompt=request.prompt,
        max_tokens=256
    )
    return {"advice": advice}

🔧 調優參數:

# 高吞吐優化（多客戶端同時訪問）
vllm serve unsloth/Qwen2.5-7B-bnb-4bit \\
    --gpu-memory-utilization 0.95 \\
    --max-num-batched-tokens 5120 \\
    --max-model-len 2048

# 低延遲優化（單客戶端快速響應）
vllm serve unsloth/Qwen2.5-7B-bnb-4bit \\
    --gpu-memory-utilization 0.8 \\
    --max-num-seqs 1 \\
    --enable-prefix-caching

📈 與 Ollama 對比:

特性              vLLM          Ollama
────────────────────────────────────────
延遲               120ms ✅      200ms
吞吐量             ⭐⭐⭐        ⭐⭐
API 兼容           ✅ OpenAI    ✅ 原生
量化格式支持       ⭐⭐⭐        ⭐⭐
LoRA 支持          ✅           ❌
Prefix Caching     ✅           ❌
配置複雜度         中            低

"""

# ============ 方案 2: Text Generation WebUI ============

TEXTGEN_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 2: Text Generation WebUI - 零成本本地部署                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 超易用 | 零代碼 | 自帶 Web UI | 支持多模型切換                       │
│ 適用: 開發調試、演示、輕量級應用                                            │
│ 成本: 零（開源）                                                            │
│ 技術要求: 最低（安裝即用）                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

✅ 優勢:
  1. 零代碼部署 - 下載即用
  2. 漂亮 Web UI - 內建聊天界面
  3. 模型管理 - 一鍵下載/切換
  4. 多量化支持 - AWQ, GPTQ, 4-bit
  5. 即時聊天測試 - 邊改邊試

🚀 快速開始:

# Windows/Mac/Linux 通用
# 1. 克隆倉庫
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui

# 2. 一鍵啟動腳本
# Windows: run_webui.bat
# Mac/Linux: bash start_linux.sh

# 3. 在瀏覽器打開
# http://localhost:7860

# 4. 下載模型
# 使用 UI 中的 "Model" 選項卡
# 搜索: Qwen-2.5-7B-bnb-4bit

💬 對話測試:
  在 Web UI 中直接輸入提示語
  ↓
  獲得即時回復
  ↓
  調整參數重試

📡 API 調用 (支持 OpenAI 兼容):

# 啟用 API 模式
python server.py --api

# 調用 API
import requests

response = requests.post(
    "http://localhost:5000/api/v1/generate",
    json={
        "prompt": "白球在左上角，標靶球在底袋位。建議動作：",
        "max_new_tokens": 256,
        "temperature": 0.7,
        "top_p": 0.95,
    }
)

print(response.json()["results"][0]["text"])

🎨 Web UI 特性:
  ✅ 聊天模式 - 多輪對話
  ✅ 指令模式 - 單次生成
  ✅ Notebook 模式 - 故事創意
  ✅ 參數調整 - 實時反饋
  ✅ 歷史記錄 - 保存對話
  ✅ 模型選擇 - 多模型管理

👥 適用場景:
  ✅ 開發階段快速測試
  ✅ 微調模型效果驗證
  ✅ 教練建議預覽
  ✅ 團隊演示 Demo
  ❌ 生產部署（性能不足）

"""

# ============ 方案 3: LM Studio ============

LMSTUDIO_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 3: LM Studio - 最友好的本地客戶端                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 最友好的 UI | 零配置 | 支持 Mac/Windows/Linux                        │
│ 適用: 本地 demo、教練建議原型制作                                          │
│ 成本: 零（開源）                                                            │
│ 技術要求: 零（完全圖形化）                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

✅ 優勢:
  1. 最漂亮的 UI - 感覺像專業應用
  2. 模型市場 - 預設最佳配置
  3. 本地服務 - RESTful API
  4. 聊天功能 - 多輪對話
  5. 跨平台 - Mac/Windows/Linux

🚀 快速開始:

# 1. 下載官方應用
# https://lmstudio.ai/

# 2. 打開應用 → 搜索 Qwen
# 推薦: Qwen-2.5-7B-Instruct-GGUF (量化版)

# 3. 一鍵下載 + 加載

# 4. 在 Chat 標籤開始對話

📡 通過 API 調用:

# 確保 LM Studio 中選中模型並啟動本地服務
# 默認端口: 1234

import requests

response = requests.post(
    "http://localhost:1234/api/chat/completions",
    json={
        "messages": [
            {
                "role": "user",
                "content": "白球在左上角，標靶球在底袋位。建議動作："
            }
        ],
        "temperature": 0.7,
        "max_tokens": 256,
    }
)

text = response.json()["choices"][0]["message"]["content"]
print(text)

🎮 適合場景:
  ✅ 產品經理快速原型測試
  ✅ 教練建議 UI 設計
  ✅ 模型效果現場演示
  ✅ 本地開發環境
  ❌ 生產部署

"""

# ============ 方案 4: Hugging Face TGI ============

HFTGI_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 4: Hugging Face TGI - 生產級推論引擎                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 官方推薦 | 高效能 | 生產就緒                                         │
│ 適用: 生產環境、云端部署、多 GPU 集群                                      │
│ 成本: 零（開源），但需更多顯卡資源                                        │
│ 技術棧: Rust + Python                                                      │
└─────────────────────────────────────────────────────────────────────────────┘

✅ 優勢:
  1. 官方支持 - Hugging Face 官方推薦
  2. 高性能 - 比 vLLM 有優化
  3. 分布式 - 支持多 GPU/多機
  4. 企業級 - 健康檢查、監控
  5. 容器化 - Docker 容易部署

🚀 快速開始:

# 方式 1: Docker 部署（推薦生產）
docker run --gpus all -p 8080:80 \\
    -v /your/cache/dir:/data \\
    ghcr.io/huggingface/text-generation-inference \\
    --model-id unsloth/Qwen2.5-7B-bnb-4bit \\
    --quantize bitsandbytes \\
    --max-batch-prefill-tokens 2048

# 方式 2: 本地 Python
pip install text-generation

# 下載模型
huggingface-cli download unsloth/Qwen2.5-7B-bnb-4bit

# 啟動 TGI 服務
text-generation-launcher \\
    --model-id unsloth/Qwen2.5-7B-bnb-4bit \\
    --port 8080 \\
    --num-shard 1

📡 API 調用:

from text_generation import Client

client = Client("http://localhost:8080")

text = client.generate(
    "白球在左上角，標靶球在底袋位。建議動作：",
    max_new_tokens=256,
    temperature=0.7,
).generated_text

print(text)

📊 性能指標:
  - 吞吐量: 10+ samples/sec
  - 延遲 P50: 140ms
  - 延遲 P95: 200ms
  - 可擴展至 8GPU 集群

🎯 生產配置:

docker-compose.yml:

version: '3.8'
services:
  tgi:
    image: ghcr.io/huggingface/text-generation-inference:latest
    ports:
      - "8080:80"
    environment:
      MODEL_ID: unsloth/Qwen2.5-7B-bnb-4bit
      QUANTIZE: bitsandbytes
      MAX_BATCH_PREFILL_TOKENS: 2048
      MAX_INPUT_LENGTH: 1024
      MAX_TOTAL_TOKENS: 2048
    volumes:
      - ./cache:/data
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

# 啟動
docker-compose up -d

# 監控
docker logs -f tgi_container

"""

# ============ 方案 5: FastAPI + 直接推理 ============

FASTAPI_DIRECT_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 5: FastAPI + 直接推理（你的現有系統）                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 無外部依賴 | 完全定製化 | 已在方案中                                │
│ 適用: 已有 FastAPI 框架的系統                                              │
│ 成本: 零                                                                    │
│ 技術棧: Python + Transformers                                              │
└─────────────────────────────────────────────────────────────────────────────┘

✅ 優勢:
  1. 無額外服務 - 集成到主應用
  2. 完全控制 - 可定製推論邏輯
  3. 零通信開銷 - 進程內直接調用
  4. 易於調試 - 同一進程棧跟蹤

❌ 劣勢:
  1. 單進程瓶頸 - 不易擴展
  2. 內存管理 - 需手動優化
  3. 無自動批處理 - 性能不如專門引擎
  4. 啟動慢 - 冷啟動 ~10-15 秒

🏗️ 你現有的架構（已實現）:

backend/main.py:

from ai_coach.training.inference import InferenceEngine
from ai_coach.tools.websocket_coach import SuggestionGenerator

# 啟動時初始化
inference_engine = InferenceEngine(
    model_path="./models/qwen_billiards_merged",
    use_quantized=True,
    max_seq_length=2048,
)
inference_engine.load_model()

# WebSocket 建議生成
suggestion_generator = SuggestionGenerator(
    inference_engine=inference_engine,
    suggestion_queue=suggestion_queue
)

# 非同步任務
asyncio.create_task(
    suggestion_generator.process_suggestions_forever()
)

⚡ 優化技巧（比 vLLM 慢 30-40% 但更小巧）:

1. 啟用 KV-Cache:
   outputs = model.generate(
       input_ids,
       use_cache=True,  # ✅ 重要
       max_length=256
   )

2. 批處理 (自實現):
   def batch_inference(prompts, batch_size=4):
       for i in range(0, len(prompts), batch_size):
           batch = prompts[i:i+batch_size]
           inputs = tokenizer(batch, padding=True, return_tensors="pt")
           outputs = model.generate(**inputs, use_cache=True)
           # ...

3. 內存優化:
   model = model.half()  # FP16
   model = model.to("cuda")

4. 非同步推理（避免阻塞）:
   loop = asyncio.get_event_loop()
   result = await loop.run_in_executor(
       executor,
       model.generate,  # 同步函數
       input_ids
   )

📊 性能對比:

方案 vs FastAPI 直接推理:

       FastAPI  vs  vLLM
────────────────────────────
延遲    160ms       120ms (-25%)
吞吐量  3/sec       6/sec (2x)
內存    6GB         5GB
配置    簡單        中等
適用    現有系統     新系統

"""

# ============ 方案 6: Ray Serve (分布式) ============

RAYSERVE_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 6: Ray Serve - 分布式推論（多 GPU/多機）                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 分布式 | 自動負載均衡 | 易擴展                                        │
│ 適用: 高並發、多機集群、預算充足的系統                                    │
│ 成本: 零（開源），需多台顯卡                                               │
│ 技術棧: Python                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

✅ 優勢:
  1. 分布式 - 跨機器負載均衡
  2. 自動擴展 - 根據負載自動調控
  3. 故障轉移 - 高可用性
  4. 易集成 - Python 原生

🚀 快速開始:

# 1. 安裝
pip install ray[serve]

# 2. 定義推論服務
from ray import serve
from ai_coach.training.inference import InferenceEngine

serve.start()

@serve.deployment
class QwenCoach:
    def __init__(self):
        self.engine = InferenceEngine(
            model_path="./models/qwen_billiards_merged",
            use_quantized=True,
        )
        self.engine.load_model()
    
    def __call__(self, prompt: str) -> str:
        return self.engine.generate(prompt, max_length=256)

# 3. 部署
coach_deployment = QwenCoach.bind()
serve.run(coach_deployment, name="qwen-coach")

# 4. 調用
import requests

response = requests.post(
    "http://localhost:8000/",
    json={"prompt": "白球在左上角..."}
)
print(response.json())

📈 多機集群配置:

# cluster.yaml
cluster_name: qwen-coach-cluster
max_workers: 4

provider:
  type: aws
  region: us-east-1

available_node_types:
  gpu_worker:
    node_config:
      InstanceType: g4dn.xlarge  # 1x T4 GPU
    resources:
      GPU: 1

head_node_type: gpu_worker

# 啟動集群
ray up cluster.yaml

# 在多個 GPU 上部署
@serve.deployment(num_replicas=4)
class QwenCoach:
    ...

"""

# ============ 方案 7: Docker 微服務 ============

DOCKER_GUIDE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 7: Docker 微服務架構                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 容器化 | 易部署 | 支持 Kubernetes                                   │
│ 適用: 云端部署（AWS/GCP/Azure）、Kubernetes                               │
│ 成本: 低（按需付費）                                                       │
│ 技術棧: Docker + Kubernetes                                                │
└─────────────────────────────────────────────────────────────────────────────┘

🐳 Dockerfile

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

WORKDIR /app

# 安裝依賴
RUN apt-get update && apt-get install -y python3.10 python3-pip
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tsinghua.tsinghua.edu.cn/simple

# 複製代碼
COPY ./ai_coach ./ai_coach
COPY ./backend ./backend
COPY ./models ./models

# 暴露端口
EXPOSE 8001

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
    CMD curl -f http://localhost:8001/health || exit 1

# 啟動
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]

# 構建
docker build -t billiards-coach:latest .

# 運行
docker run --gpus all \\
    -p 8001:8001 \\
    -v ./models:/app/models \\
    billiards-coach:latest

🎵 Docker Compose (多個服務)

version: '3.8'

services:
  api:
    image: billiards-coach:latest
    ports:
      - "8001:8001"
    environment:
      MODEL_PATH: "./models/qwen_billiards_merged"
      QUANTIZED: "true"
    volumes:
      - ./models:/app/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  frontend:
    image: billiards-coach-frontend:latest
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: "http://localhost:8001"

☸️ Kubernetes 部署

apiVersion: apps/v1
kind: Deployment
metadata:
  name: qwen-coach
spec:
  replicas: 2
  selector:
    matchLabels:
      app: qwen-coach
  template:
    metadata:
      labels:
        app: qwen-coach
    spec:
      containers:
      - name: qwen-coach
        image: billiards-coach:latest
        resources:
          requests:
            nvidia.com/gpu: 1
          limits:
            nvidia.com/gpu: 1
        ports:
        - containerPort: 8001
        env:
        - name: MODEL_PATH
          value: /models/qwen_billiards_merged
        volumeMounts:
        - name: models
          mountPath: /models
      volumes:
      - name: models
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: qwen-coach-service
spec:
  selector:
    app: qwen-coach
  type: LoadBalancer
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8001

# 部署
kubectl apply -f deployment.yaml

# 查看狀態
kubectl get pods
kubectl logs -f pod/qwen-coach-xxx

"""

# ============ 方案 8: 云端部署 ============

CLOUD_DEPLOYMENT = """
┌─────────────────────────────────────────────────────────────────────────────┐
│ 方案 8: 云端部署選項                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 特點: 無需本地硬件 | 自動擴展 | 按需付費                                  │
│ 成本: 中-高（按 GPU 時間計費）                                            │
│ 技術棧: 云平台 API                                                         │
└─────────────────────────────────────────────────────────────────────────────┘

1️⃣ AWS SageMaker

# 最簡單的方式
import sagemaker
from sagemaker.huggingface import HuggingFaceModel

role = sagemaker.get_execution_role()
hub = {
    'HF_MODEL_ID': 'unsloth/Qwen2.5-7B-bnb-4bit',
    'HF_TASK': 'text-generation'
}

huggingface_model = HuggingFaceModel(
    transformers_version='4.36.0',
    pytorch_version='2.1.0',
    py_version='py310',
    env=hub,
    role=role,
)

predictor = huggingface_model.deploy(
    initial_instance_count=1,
    instance_type='ml.g4dn.xlarge',  # 1x T4 GPU ~$0.5/hr
    endpoint_name='qwen-coach',
)

# 調用
response = predictor.predict(
    {"inputs": "白球在左上角..."}
)

成本估算:
  - g4dn.xlarge (1x T4): $0.50/hr
  - 月 24/7 成本: ~$360

2️⃣ Google Cloud Vertex AI

from google.cloud import aiplatform

def deploy_qwen_model():
    aiplatform.init(project='your-project', location='us-central1')
    
    model = aiplatform.Model.upload(
        display_name='qwen-coach',
        artifact_uri='gs://your-bucket/qwen-model/',
        serving_container_image_uri='gcr.io/cloud-aiplatform/prediction/tf-cpu.2-11:latest',
    )
    
    endpoint = model.deploy(
        replica_count=2,
        machine_type='n1-standard-4',
        gpu_type='nvidia-tesla-t4',
        gpu_count=1,
    )
    
    return endpoint

成本估算:
  - N1 Standard-4 + T4: $0.35-0.45/hr
  - 月成本: ~$260-$330

3️⃣ Azure ML

from azureml.core import Workspace, Datastore, Environment
from azureml.core.model import Model

ws = Workspace.from_config()

env = Environment.get(
    workspace=ws,
    name='huggingface-inference'
)

# 部署
from azureml.core.webservice import Webservice, AciWebservice

aci_config = AciWebservice.deploy_configuration(
    cpu_cores=4,
    memory_gb=16,
    gpu_cores=1,
)

service = Model.register(
    workspace=ws,
    model_path='./qwen_model',
    model_name='qwen-coach',
).deploy(
    name='qwen-coach',
    deployment_config=aci_config,
    environment=env,
)

成本估算:
  - Standard D4 + K80 GPU: $0.40/hr
  - 月成本: ~$290

📊 云服務對比:

特性            AWS SageMaker  GCP Vertex  Azure ML
──────────────────────────────────────────────────
部署難度        簡單            中等        中等
成本/小時       $0.50          $0.35       $0.40
自動擴展        ✅             ✅          ✅
無服務器        ✅ Lambda      ✅ Cloud    ✅ Functions
監控            優秀            優秀        中等
推薦指數        ⭐⭐⭐         ⭐⭐⭐      ⭐⭐

"""

print(DEPLOYMENT_COMPARISON)
