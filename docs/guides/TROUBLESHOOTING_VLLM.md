# 🔧 vLLM 集成故障排除指南

## 📋 目录
1. [安装问题](#1-安装问题)
2. [vLLM 启动问题](#2-vllm-启动问题)
3. [连接问题](#3-连接问题)
4. [性能问题](#4-性能问题)
5. [推理问题](#5-推理问题)
6. [后端集成问题](#6-后端集成问题)
7. [诊断工具](#7-诊断工具)

---

## 1. 安装问题

### 问题: Python 版本过低

**错误消息:**
```
Python 3.8+ required
```

**解决方案:**

检查 Python 版本：
```bash
python --version
```

升级 Python：
- Windows: 访问 python.org 下载最新版本
- Mac: 使用 `brew install python3.11`
- Linux: 使用包管理器 `apt-get install python3.10`

---

### 问题: CUDA 不可用

**错误消息:**
```
RuntimeError: CUDA is not available
```

**解决方案:**

1. 检查是否已安装 NVIDIA GPU
   ```bash
   nvidia-smi
   ```
   
   如果没有输出，您的系统没有 NVIDIA GPU。

2. 安装 CUDA 驱动
   - 访问 https://www.nvidia.com/download/driverDetails.html
   - 下载适合您 GPU 的驱动

3. 安装 CUDA 工具包
   ```bash
   # Windows
   # 下载: https://developer.nvidia.com/cuda-downloads
   
   # Mac/Linux
   # 按照官方指南安装
   ```

4. 验证 CUDA 安装
   ```bash
   nvcc --version
   ```

---

### 问题: PyTorch 安装失败

**错误消息:**
```
ERROR: Could not find a version that satisfies the requirement torch
```

**解决方案:**

```bash
# 卸载旧的 PyTorch
pip uninstall torch torchvision torchaudio

# 安装与 CUDA 兼容的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 验证安装
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

---

### 问题: vLLM 安装失败

**错误消息:**
```
error building wheel for vllm
```

**解决方案:**

```bash
# 确保有 C++ 编译器
# Windows: 安装 Visual C++ Build Tools
# Mac: xcode-select --install
# Linux: apt-get install build-essential

# 重新安装 vLLM（从源代码）
pip install vllm --no-cache-dir
```

---

## 2. vLLM 启动问题

### 问题: 模型下载失败

**错误消息:**
```
Connection timeout when downloading model
```

**解决方案:**

1. 检查网络连接
2. 手动指定模型缓存目录
   ```bash
   set HF_HOME=C:\Models  # Windows
   export HF_HOME=~/models  # Linux/Mac
   
   vllm serve unsloth/Qwen2.5-7B-bnb-4bit --port 8000
   ```

3. 使用代理（如果在中国）
   ```bash
   pip install -i https://pypi.tsinghua.edu.cn/simple vllm
   ```

---

### 问题: GPU 内存不足

**错误消息:**
```
RuntimeError: CUDA out of memory
```

**解决方案:**

1. **立即解决（不杀死进程）:**
   ```bash
   # 降低 GPU 内存利用率
   vllm serve unsloth/Qwen2.5-7B-bnb-4bit \
       --port 8000 \
       --gpu-memory-utilization 0.7  # 改为 0.7
   ```

2. **根本解决:**
   ```bash
   # 关闭其他 GPU 应用
   nvidia-smi  # 查看占用 GPU 的进程
   
   # 使用更小的模型
   vllm serve unsloth/Qwen2.5-3B-bnb-4bit --port 8000
   ```

3. **检查 GPU 内存**
   ```bash
   nvidia-smi
   
   # 应该看到
   # | GPU | Memory-Usage |
   # |  0  | 5500MiB / 8000MiB |
   ```

---

### 问题: 启动脚本执行失败

**错误消息 (Windows):**
```
Cannot be loaded because running scripts is disabled on this system
```

**解决方案:**

打开 PowerShell 作为管理员，运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**错误消息 (Linux/Mac):**
```
Permission denied: './start_vllm.sh'
```

**解决方案:**

```bash
chmod +x start_vllm.sh
./start_vllm.sh
```

---

### 问题: 启动很慢

**现象:**
```
初始化需要 5+ 分钟
```

**原因:**
- 第一次运行需要下载模型
- GPU 过热需要等待
- 系统资源不足

**解决方案:**

1. 等待首次运行完成（正常）
2. 检查 GPU 温度
   ```bash
   nvidia-smi -l 1  # 每秒刷新一次
   ```
   
3. 监控 CPU 和内存
   ```bash
   # Windows
   Get-Process | Sort-Object -Property WorkingSet -Descending | Select-Object -First 5
   
   # Linux
   top
   ```

---

## 3. 连接问题

### 问题: 无法连接到 vLLM 服务

**错误消息:**
```
ConnectionRefusedError: [WinError 10061] No connection could be made
```

**解决方案:**

1. **检查 vLLM 是否运行**
   ```bash
   curl http://localhost:8000/v1/models
   ```
   
   如果失败，启动 vLLM：
   ```bash
   scripts/start_vllm.bat
   ```

2. **检查端口是否被占用**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```
   
   如果端口被占用，找到进程 ID 并杀死：
   ```bash
   # Windows (使用找到的 PID)
   taskkill /PID 12345 /F
   
   # Linux/Mac
   kill -9 12345
   ```

3. **检查防火墙**
   ```bash
   # Windows Defender 防火墙
   # 允许 Python 访问网络
   ```

4. **检查网络配置**
   ```bash
   # 使用正确的地址
   # 本地: http://localhost:8000
   # 远程: http://<server_ip>:8000
   ```

---

### 问题: 超时错误

**错误消息:**
```
TimeoutError: Timeout connecting to host
```

**解决方案:**

1. **增加超时时间**
   ```python
   vllm_config = vLLMConfig(
       timeout=60,  # 改为 60 秒
   )
   ```

2. **检查网络延迟**
   ```bash
   ping localhost
   ```

3. **检查 vLLM 是否响应**
   ```bash
   curl -v http://localhost:8000/v1/models
   ```

---

## 4. 性能问题

### 问题: 推理速度慢

**现象:**
```
延迟 > 200ms
吞吐量 < 3 req/s
```

**解决方案:**

1. **检查 GPU 利用率**
   ```bash
   # 在另一个终端
   nvidia-smi
   
   # GPU 应该显示 85-95% 利用率
   # 如果低于 70%，检查下面的原因
   ```

2. **检查内存使用**
   ```bash
   nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
   
   # 应该显示 5-6GB 使用
   # 如果接近满，降低 --gpu-memory-utilization
   ```

3. **优化启动参数**
   ```bash
   # 启用 Prefix Caching
   vllm serve unsloth/Qwen2.5-7B-bnb-4bit \
       --port 8000 \
       --enable-prefix-caching \
       --max-model-len 2048
   ```

4. **减少生成令牌数**
   ```python
   response = await client.generate(
       prompt="...",
       max_tokens=128,  # 改为 128
   )
   ```

5. **使用批处理**
   ```python
   # 而不是多次调用 generate
   responses = await client.batch_generate(
       prompts=["提示1", "提示2", "提示3"]
   )
   ```

---

### 问题: GPU 温度过高

**现象:**
```
GPU temperature > 80°C
性能随时间降低
```

**解决方案:**

1. **降低 GPU 电源消耗**
   ```bash
   vllm serve unsloth/Qwen2.5-7B-bnb-4bit \
       --port 8000 \
       --gpu-memory-utilization 0.8  # 改为 0.8
   ```

2. **检查散热**
   - 确保 GPU 散热良好
   - 检查风冷或液冷系统

3. **暂停并冷却**
   - 停止 vLLM 服务
   - 等待 GPU 温度降低到 40°C 以下

---

## 5. 推理问题

### 问题: 生成空响应

**现象:**
```json
{
  "response": ""
}
```

**解决方案:**

1. **检查提示**
   ```python
   # 确保提示不为空
   prompt = "白球在左上角..."
   assert len(prompt) > 0
   ```

2. **增加 max_tokens**
   ```python
   response = await client.generate(
       prompt="...",
       max_tokens=512,  # 改为 512
   )
   ```

3. **降低温度**
   ```python
   response = await client.generate(
       prompt="...",
       temperature=0.5,  # 改为 0.5 而不是 0.1
   )
   ```

---

### 问题: 响应质量差

**现象:**
```
生成的建议无关或重复
```

**解决方案:**

1. **检查模型**
   ```bash
   # 确保使用了正确的模型
   curl http://localhost:8000/v1/models
   ```

2. **调整采样参数**
   ```python
   response = await client.generate(
       prompt="...",
       temperature=0.7,      # 增加多样性
       top_p=0.9,           # 调整概率
   )
   ```

3. **使用微调模型**
   - 如果仅用原始 Qwen，考虑使用微调版本
   - 参考 `ai_coach/tools/dataset_builder.py`

---

### 问题: 生成随机文本

**现象:**
```
😉😉😉 或乱码或重复单个字符
```

**解决方案:**

1. **检查模型加载**
   ```bash
   curl http://localhost:8000/v1/models
   
   # 确保显示 unsloth/Qwen2.5-7B-bnb-4bit
   ```

2. **重新启动 vLLM**
   ```bash
   # 关闭当前 vLLM
   # 重新启动
   scripts/start_vllm.bat
   ```

3. **检查 CUDA 内存**
   ```bash
   nvidia-smi
   # 如果接近满，重启或限制使用
   ```

---

## 6. 后端集成问题

### 问题: 后端无法连接 vLLM

**错误消息:**
```
vLLM service NOT available!
```

**解决方案:**

1. **检查 vLLM 是否运行**
   ```bash
   curl http://localhost:8000/v1/models
   ```

2. **检查后端配置**
   ```python
   # backend/main.py
   vllm_config = vLLMConfig(
       api_url="http://localhost:8000/v1",  # 检查地址
   )
   ```

3. **重启后端**
   ```bash
   # 关闭后端
   # 重新启动
   python -m uvicorn backend.main:app --port 8001
   ```

---

### 问题: 后端返回 503 错误

**错误消息:**
```json
{
  "status": "error",
  "message": "vLLM service not available"
}
```

**解决方案:**

1. **等待 vLLM 初始化**
   - vLLM 可能仍在启动

2. **检查 vLLM 日志**
   - 查看启动脚本输出

3. **重新启动两个服务**
   ```bash
   # 终端 1
   scripts/start_vllm.bat
   
   # 终端 2 (等待 vLLM 完全启动)
   python -m uvicorn backend.main:app --port 8001
   ```

---

### 问题: 后端推理超时（502 错误）

**错误消息:**
```json
{
  "status": "error",
  "message": "Gateway Timeout"
}
```

**解决方案:**

1. **增加后端超时**
   ```python
   # backend/main.py
   from fastapi import Request
   
   @app.middleware("http")
   async def add_timeout(request: Request, call_next):
       try:
           response = await asyncio.wait_for(
               call_next(request),
               timeout=60.0,  # 增加到 60 秒
           )
            return response
       except asyncio.TimeoutError:
           return JSONResponse(
               {"error": "Request timeout"},
               status_code=504,
           )
   ```

2. **检查 vLLM 性能**
   ```bash
   # 运行性能测试
   python test_vllm_integration.py
   ```

---

## 7. 诊断工具

### 功能 1: 完整系统诊断

```python
# diagnostics.py

import asyncio
import subprocess
from backend.services.vllm_client import vLLMClient, vLLMConfig

async def run_diagnostics():
    """运行完整诊断。"""
    
    print("=" * 70)
    print("系统诊断工具")
    print("=" * 70)
    
    # 检查 Python
    print("\n1️⃣  Python 环境")
    result = subprocess.run(["python", "--version"], capture_output=True, text=True)
    print(f"   Python: {result.stdout.strip()}")
    
    # 检查 GPU
    print("\n2️⃣  GPU 信息")
    result = subprocess.run(["nvidia-smi", "--query-gpu=index,name,driver_version", "--format=csv,noheader"], 
                          capture_output=True, text=True)
    print(result.stdout.strip())
    
    # 检查 vLLM 连接
    print("\n3️⃣  vLLM 连接")
    config = vLLMConfig(api_url="http://localhost:8000/v1")
    client = vLLMClient(config=config)
    
    try:
        health = await client.health_check()
        print(f"   连接: {'✅ 成功' if health else '❌ 失败'}")
    except Exception as e:
        print(f"   连接: ❌ {e}")
    
    # 检查推理
    print("\n4️⃣  推理测试")
    try:
        response = await client.generate("测试", max_tokens=10)
        print(f"   推理: ✅ 成功 ({len(response)} 字符)")
    except Exception as e:
        print(f"   推理: ❌ {e}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
```

运行诊断：
```bash
python diagnostics.py
```

---

### 功能 2: 仅 vLLM 诊断

```bash
# 检查 vLLM 状态
curl -s http://localhost:8000/v1/models | python -m json.tool

# 检查健康状态
curl -s http://localhost:8000/health

# 获取模型信息
curl -s http://localhost:8000/v1/model_list
```

---

### 功能 3: 性能基准测试

已包含在 `test_vllm_integration.py`：

```bash
python test_vllm_integration.py

# 应该显示
# 平均延迟: 125.3ms
# 最小延迟: 115.2ms
# 最大延迟: 145.8ms
```

---

## 🎯 快速修复清单

遇到问题时，按顺序尝试：

- [ ] 1. 重启 vLLM (`scripts/start_vllm.bat`)
- [ ] 2. 重启后端 (`python -m uvicorn backend.main:app`)
- [ ] 3. 运行诊断 (`python test_vllm_integration.py`)
- [ ] 4. 检查日志输出
- [ ] 5. 查看本文档对应部分
- [ ] 6. 检查 GPU 内存和温度
- [ ] 7. 重新安装依赖 (`pip install -r requirements.txt`)
- [ ] 8. 如果还有问题，尝试使用不同的模型版本

---

## 📞 还需要帮助？

1. 收集诊断信息
   ```bash
   python test_vllm_integration.py > diagnostics.log 2>&1
   ```

2. 检查日志文件 `diagnostics.log`

3. 参考完整指南
   - `QUICK_START_VLLM.md` - 快速启动
   - `VLLM_INTEGRATION_GUIDE.md` - 完整指南
   - `MAIN_PY_MODIFICATIONS.md` - 代码修改详解

---

**最后更新: 2026-04-13**
