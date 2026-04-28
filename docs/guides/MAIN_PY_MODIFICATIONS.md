# main.py 修改指南 - 完整代码段

## 📄 文件位置
`backend/main.py`

## 🔄 修改步骤

### 步骤 1: 更新导入语句

**替换以下内容：**

```python
# ❌ 删除这些导入
# from ai_coach.training.inference import InferenceEngine

# ✅ 添加这些导入
from backend.services.vllm_client import vLLMClient, vLLMConfig
import asyncio
from datetime import datetime
```

---

### 步骤 2: 全局变量初始化

**在应用实例化后添加：**

```python
# 在 app = FastAPI() 之后

# ✅ 全局变量（用于存储 vLLM 客户端）
vllm_client: vLLMClient = None
suggestion_generator: SuggestionGenerator = None
```

---

### 步骤 3: 启动事件修改

**完整修改 `@app.on_event("startup")`：**

```python
@app.on_event("startup")
async def startup_event():
    """应用启动时执行。"""
    
    global vllm_client, suggestion_generator
    
    logger.info("=" * 60)
    logger.info("🚀 Starting AI Coach System")
    logger.info("=" * 60)
    
    try:
        # ✅ 初始化 vLLM 客户端
        logger.info("1. 初始化 vLLM 客户端...")
        vllm_config = vLLMConfig(
            api_url="http://localhost:8000/v1",
            model_name="unsloth/Qwen2.5-7B-bnb-4bit",
            max_tokens=256,
            temperature=0.7,
        )
        
        vllm_client = vLLMClient(config=vllm_config)
        logger.info("   ✅ vLLM 客户端创建成功")
        
        # ✅ 检查 vLLM 服务健康状态
        logger.info("2. 检查 vLLM 服务...")
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                health = await vllm_client.health_check()
                if health:
                    logger.info("   ✅ vLLM 服务online")
                    break
            except Exception as e:
                retry_count += 1
                logger.warning(f"   ⚠️  第 {retry_count} 次连接失败: {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(2)
        
        if retry_count >= max_retries:
            logger.error("   ❌ vLLM 服务 NOT available!")
            logger.error("   请先启动 vLLM:")
            logger.error("   $ scripts/start_vllm.bat  (Windows)")
            logger.error("   $ ./scripts/start_vllm.sh  (Linux)")
            raise RuntimeError("vLLM service not available")
        
        # ✅ 初始化建议生成器
        logger.info("3. 初始化建议生成器...")
        from ai_coach.tools.websocket_coach import (
            SuggestionQueue,
            SuggestionGenerator
        )
        
        suggestion_queue = SuggestionQueue(max_queue_size=1000)
        suggestion_generator = SuggestionGenerator(
            inference_engine=vllm_client,  # ✅ 使用 vLLM 客户端
            suggestion_queue=suggestion_queue
        )
        
        logger.info("   ✅ 建议生成器初始化成功")
        
        # ✅ 启动后台任务
        logger.info("4. 启动后台任务...")
        asyncio.create_task(
            suggestion_generator.process_suggestions_forever()
        )
        logger.info("   ✅ 后台任务启动")
        
        logger.info("=" * 60)
        logger.info("✅ AI Coach System Ready")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行。"""
    
    global vllm_client
    
    logger.info("🛑 Shutting down AI Coach System...")
    
    if vllm_client:
        await vllm_client.close()
        logger.info("✅ vLLM 客户端已关闭")
```

---

### 步骤 4: 添加测试和监控端点

**在路由中添加：**

```python
@app.get("/health")
async def health_check():
    """检查系统健康状态。"""
    
    global vllm_client
    
    vllm_healthy = False
    if vllm_client:
        try:
            vllm_healthy = await vllm_client.health_check()
        except Exception as e:
            logger.error(f"vLLM 健康检查失败: {e}")
    
    status = "healthy" if vllm_healthy else "degraded"
    
    return {
        "status": status,
        "services": {
            "vllm": "online" if vllm_healthy else "offline",
            "backend": "online",
        },
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/coach/test-inference")
async def test_inference(request: dict):
    """测试 vLLM 推理 - 用于调试和验证。
    
    请求示例:
    {
        "prompt": "白球在左上角，标靶球在底袋位。建议动作：",
        "max_tokens": 256,
        "temperature": 0.7
    }
    
    响应示例:
    {
        "status": "success",
        "prompt": "白球在左上角...",
        "response": "从左上角击打白球...",
        "latency_ms": 125,
        "timestamp": "2026-04-13T10:30:00"
    }
    """
    
    global vllm_client
    
    if not vllm_client:
        return {
            "status": "error",
            "message": "vLLM client not initialized"
        }, 503
    
    try:
        import time
        
        prompt = request.get("prompt", "")
        max_tokens = request.get("max_tokens", 256)
        temperature = request.get("temperature", 0.7)
        
        if not prompt:
            return {
                "status": "error",
                "message": "prompt is required"
            }, 400
        
        # 测量响应时间
        start_time = time.time()
        
        response = await vllm_client.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        logger.info(f"✅ 推理成功 | 延迟: {latency_ms:.0f}ms | 字数: {len(response)}")
        
        return {
            "status": "success",
            "prompt": prompt,
            "response": response,
            "latency_ms": round(latency_ms, 2),
            "tokens": len(response.split()),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ 推理失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 500


@app.post("/api/coach/batch-inference")
async def batch_inference(request: dict):
    """批量推理 - 用于性能测试。
    
    请求示例:
    {
        "prompts": [
            "提示 1",
            "提示 2",
            "提示 3"
        ],
        "max_tokens": 256
    }
    """
    
    global vllm_client
    
    if not vllm_client:
        return {
            "status": "error",
            "message": "vLLM client not initialized"
        }, 503
    
    try:
        import time
        
        prompts = request.get("prompts", [])
        max_tokens = request.get("max_tokens", 256)
        
        if not prompts or len(prompts) == 0:
            return {
                "status": "error",
                "message": "prompts list is required and non-empty"
            }, 400
        
        start_time = time.time()
        
        responses = await vllm_client.batch_generate(
            prompts=prompts,
            max_tokens=max_tokens
        )
        
        latency_ms = (time.time() - start_time) * 1000
        avg_latency = latency_ms / len(prompts)
        
        logger.info(f"✅ 批量推理成功 | 总延迟: {latency_ms:.0f}ms | 平均: {avg_latency:.0f}ms")
        
        return {
            "status": "success",
            "count": len(prompts),
            "results": [
                {
                    "prompt": prompt,
                    "response": response
                }
                for prompt, response in zip(prompts, responses)
            ],
            "total_latency_ms": round(latency_ms, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ 批量推理失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 500


@app.get("/api/coach/stats")
async def coach_stats():
    """获取教练系统统计信息。"""
    
    global suggestion_generator
    
    if not suggestion_generator:
        return {
            "status": "error",
            "message": "Coach system not initialized"
        }, 503
    
    try:
        stats = suggestion_generator.get_stats()
        
        return {
            "status": "success",
            "stats": {
                "queue_size": stats.get("queue_size", 0),
                "total_processed": stats.get("total_processed", 0),
                "total_errors": stats.get("total_errors", 0),
                "avg_latency_ms": stats.get("avg_latency_ms", 0),
            },
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ 获取统计失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 500
```

---

## 🧪 测试命令

### 1. 检查系统健康状态

```bash
curl http://localhost:8001/health
```

**预期响应：**
```json
{
  "status": "healthy",
  "services": {
    "vllm": "online",
    "backend": "online"
  },
  "timestamp": "2026-04-13T10:30:00"
}
```

---

### 2. 测试单个推理

```bash
curl -X POST http://localhost:8001/api/coach/test-inference \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "白球在左上角，标靶球在底袋位。建议动作：",
    "max_tokens": 256,
    "temperature": 0.7
  }'
```

**预期响应：**
```json
{
  "status": "success",
  "prompt": "白球在左上角，标靶球在底袋位。建议动作：",
  "response": "从左上角击打白球，力度适中...",
  "latency_ms": 125.5,
  "tokens": 15,
  "timestamp": "2026-04-13T10:30:00"
}
```

---

### 3. 测试批量推理

```bash
curl -X POST http://localhost:8001/api/coach/batch-inference \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": [
      "白球在左上角，标靶球在底袋位。建议动作：",
      "当前局势如何？",
      "下一步应该怎么做？"
    ],
    "max_tokens": 256
  }'
```

**预期响应：**
```json
{
  "status": "success",
  "count": 3,
  "results": [
    {
      "prompt": "白球在左上角...",
      "response": "从左上角击打..."
    },
    ...
  ],
  "total_latency_ms": 380.5,
  "avg_latency_ms": 126.8,
  "timestamp": "2026-04-13T10:30:00"
}
```

---

### 4. 获取统计信息

```bash
curl http://localhost:8001/api/coach/stats
```

**预期响应：**
```json
{
  "status": "success",
  "stats": {
    "queue_size": 0,
    "total_processed": 42,
    "total_errors": 0,
    "avg_latency_ms": 125.3
  },
  "timestamp": "2026-04-13T10:30:00"
}
```

---

## 📋 完整修改检查清单

- [ ] 复制了 vLLMConfig 和 vLLMClient 导入
- [ ] 在全局作用域添加了 vllm_client 和 suggestion_generator 变量
- [ ] 修改了 startup_event 事件处理程序
- [ ] 修改了 shutdown_event 事件处理程序
- [ ] 添加了 /health 端点
- [ ] 添加了 /api/coach/test-inference 端点
- [ ] 添加了 /api/coach/batch-inference 端点
- [ ] 添加了 /api/coach/stats 端点
- [ ] 更新了 requirements.txt（添加 httpx, aiohttp）
- [ ] 测试了所有端点

---

## 🎯 验证步骤

1. **启动 vLLM**
   ```bash
   scripts/start_vllm.bat
   ```

2. **启动后端**
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
   ```

3. **测试健康检查**
   ```bash
   curl http://localhost:8001/health
   ```

4. **测试推理**
   ```bash
   curl -X POST http://localhost:8001/api/coach/test-inference \
     -H "Content-Type: application/json" \
     -d '{"prompt": "测试"}'
   ```

✅ 如果看到 `"status": "success"`，就表示集成成功！

---

## 🔧 故障排除

### 问题 1: 500 错误 - vLLM 服务不可用

**解决方案：**
1. 检查 vLLM 是否运行
2. 确保地址是 `http://localhost:8000/v1`
3. 检查防火墙规则

### 问题 2: 497 错误 - 模型加载超时

**解决方案：**
```python
# 增加超时时间
vllm_config = vLLMConfig(
    timeout=30,  # 改为 30 秒
)
```

### 问题 3: 推理很慢

**解决方案：**
- 检查 GPU 利用率是否达到 85%+
- 尝试减少 max_tokens
- 增加批大小进行批处理

---

## 📞 需要帮助？

1. 检查日志输出
2. 运行诊断测试
3. 查阅 VLLM_INTEGRATION_GUIDE.md
