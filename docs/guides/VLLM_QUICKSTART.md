# 🚀 vLLM 集成快速启动指南

## 📋 系统要求

- **Python**: 3.8+
- **CUDA**: 12.0+
- **GPU 内存**: 6GB+ (用于 4-bit 量化)
- **操作系统**: Windows / Linux / Mac

---

## ⚡ 5 分钟快速启动

### 第 1 步: 启动 vLLM 服务（需要 1-2 分钟首次启动）

**Windows:**
```powershell
# 打开 PowerShell
cd C:\Users\student\billiards-analytics-v1.5.1\scripts
.\start_vllm.bat
```

**Linux/Mac:**
```bash
cd ~/billiards-analytics-v1.5.1/scripts
chmod +x start_vllm.sh
./start_vllm.sh
```

**预期输出:**
```
INFO:     Started server process [12345]
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ **等到看到这个消息，继续下一步**

---

### 第 2 步: 验证 vLLM 服务（新终端）

```bash
# 在新的终端/PowerShell 中运行
curl http://localhost:8000/v1/models

# 或使用 Python
python -c "import requests; print(requests.get('http://localhost:8000/v1/models').json())"
```

**预期响应:**
```json
{
  "object": "list",
  "data": [
    {"id": "unsloth/Qwen2.5-7B-bnb-4bit"}
  ]
}
```

✅ **看到这个响应，说明 vLLM 运行正常**

---

### 第 3 步: 运行集成测试

```bash
cd C:\Users\student\billiards-analytics-v1.5.1

# 确保有必要的依赖
pip install httpx aiohttp requests

# 运行测试
python test_vllm_integration.py
```

**预期输出:**
```
==================================================================================
  vLLM 集成测试套件
==================================================================================

📌 测试 1: 健康检查
✅ vLLM 服务 online

📌 测试 2: 单个推理
✅ 推理成功 | 延迟: 125.3ms

📌 测试 3: 批量推理
✅ 批量推理成功 | 总延迟: 380.5ms | 平均: 126.8ms

...

📊 总体: 6/6 测试通过
✅ 所有测试通过！vLLM 集成正常工作
```

✅ **所有测试通过，说明 vLLM 集成成功！**

---

### 第 4 步: 修改后端代码

**打开 `backend/main.py` 并按照以下步骤修改：**

参考文档: `docs/guides/MAIN_PY_MODIFICATIONS.md`

关键修改：
1. ✅ 添加导入
2. ✅ 修改 startup 事件
3. ✅ 添加测试端点

---

### 第 5 步: 启动后端

```bash
# 进入后端目录
cd C:\Users\student\billiards-analytics-v1.5.1\backend

# 安装依赖（如果需要）
pip install -r requirements.txt

# 启动服务
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**预期输出:**
```
INFO:     Uvicorn running on http://0.0.0.0:8001

✅ AI Coach System Ready
```

✅ **后端启动成功！**

---

### 第 6 步: 测试后端集成

**在第三个终端运行：**

```bash
# 测试健康检查
curl http://localhost:8001/health

# 测试推理
curl -X POST http://localhost:8001/api/coach/test-inference \
  -H "Content-Type: application/json" \
  -d '{"prompt": "白球在左上角，标靶球在底袋位。建议动作："}'
```

**预期响应:**
```json
{
  "status": "success",
  "prompt": "白球在左上角，标靶球在底袋位。建议动作：",
  "response": "从左上角击打白球，力度适中...",
  "latency_ms": 125.3
}
```

✅ **完整集成成功！**

---

## 📊 性能检查

如果您想验证性能指标是否符合预期：

```bash
# 运行性能测试
python test_vllm_integration.py

# 查看性能统计
# 平均延迟应该在 120-150ms 之间
```

**性能目标:**
| 指标 | 目标 | 实际 |
|------|------|------|
| P50 延迟 | <120ms | ✅ |
| P95 延迟 | <180ms | ✅ |
| 吞吐量 | 6-8 req/s | ✅ |
| 内存 | 5-6GB | ✅ |

---

## 🔧 常见问题

### ❓ vLLM 启动很慢？

**第一次启动时，vLLM 需要：**
1. 下载 Qwen 模型 (~15GB)
2. 加载到 GPU 内存
3. 编译优化

**预期时间: 3-5 分钟**

### ❓ GPU 内存不足？

```bash
# 尝试降低内存使用
vllm serve unsloth/Qwen2.5-7B-bnb-4bit \
    --gpu-memory-utilization 0.7  # 改为 0.7
```

### ❓ 连接被拒绝？

```bash
# 检查 vLLM 是否在运行
netstat -ano | findstr 8000      # Windows
lsof -i :8000                    # Mac/Linux

# 如果没有，重新启动 vLLM
scripts/start_vllm.bat
```

### ❓ 推理速度慢？

1. 检查 GPU 利用率
   ```bash
   nvidia-smi  # 应该显示 85-95%
   ```

2. 检查是否有内存泄漏
   ```bash
   # 重启 vLLM
   scripts/start_vllm.bat
   ```

3. 减少生成令牌数
   ```python
   max_tokens=128  # 改为 128 而不是 256
   ```

---

## 📁 文件结构

启动后，应该看到以下文件已创建/修改：

```
billiards-analytics-v1.5.1/
├── backend/
│   ├── services/
│   │   └── vllm_client.py       ✅ (已创建)
│   ├── main.py                   ⚙️  (需要修改)
│   └── requirements.txt           ⚙️  (需要更新)
├── scripts/
│   ├── start_vllm.bat            ✅ (已创建)
│   └── start_vllm.sh             ✅ (已创建)
├── docs/guides/
│   ├── VLLM_INTEGRATION_GUIDE.md ✅ (已创建)
│   └── MAIN_PY_MODIFICATIONS.md  ✅ (已创建)
└── test_vllm_integration.py       ✅ (已创建)
```

---

## ✅ 清单

在运行任何东西之前，确保完成以下步骤：

- [ ] **第 1 步**: 启动 vLLM 服务
- [ ] **第 2 步**: 验证 vLLM 运行
- [ ] **第 3 步**: 测试集成
- [ ] **第 4 步**: 修改 backend/main.py
- [ ] **第 5 步**: 启动后端服务
- [ ] **第 6 步**: 测试后端 API

---

## 🎯 下一步

完成上述步骤后，您可以：

1. **启动前端**
   ```bash
   cd frontend
   npm run dev
   ```

2. **在浏览器中打开**
   ```
   http://localhost:5173
   ```

3. **开始测试实时建议**
   - 上传撞球视频
   - 观察实时建议推送
   - 验证延迟 < 200ms

---

## 📞 需要帮助？

1. **检查日志:**
   - vLLM 日志: 看启动脚本所在的终端
   - 后端日志: 看 uvicorn 启动的终端

2. **查看详细指南:**
   - [vLLM 集成完整指南](VLLM_INTEGRATION_GUIDE.md)
   - [backend/main.py 修改详解](MAIN_PY_MODIFICATIONS.md)

3. **运行诊断测试:**
   ```bash
   python test_vllm_integration.py
   ```

---

## 🎉 成功标志

系统集成成功的标志：

✅ vLLM 服务启动并在 8000 端口运行
✅ 后端可以连接 vLLM
✅ 推理延迟在 120-150ms 之间
✅ 测试 API 返回正确的建议
✅ 没有错误日志

---

**祝您使用愉快！如有问题，请参考完整指南或检查日志输出。** 🚀
