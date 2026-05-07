"""
vLLM 後端集成服務
完整的 FastAPI + vLLM 實現，替換直接推論引擎
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import httpx
import json

logger = logging.getLogger(__name__)


@dataclass
class vLLMConfig:
    """vLLM 配置。"""
    
    # 服務器配置
    api_url: str = "http://localhost:8000/v1"
    model_name: str = "unsloth/Qwen2.5-7B-bnb-4bit"
    
    # 推論參數
    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 50
    
    # 性能配置
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


class vLLMClient:
    """vLLM API 客戶端（替換 InferenceEngine）。"""
    
    def __init__(self, config: vLLMConfig = None):
        """初始化 vLLM 客戶端。
        
        Args:
            config: vLLM 配置
        """
        self.config = config or vLLMConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        
        logger.info(f"vLLM client initialized: {self.config.api_url}")
    
    async def health_check(self) -> bool:
        """檢查 vLLM 服務可用性。
        
        Returns:
            是否可用
        """
        try:
            response = await self.client.get(f"{self.config.api_url}/models")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"vLLM health check failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> str:
        """生成文本。
        
        Args:
            prompt: 輸入提示語
            max_tokens: 最大生成令牌數
            temperature: 采樣溫度
            top_p: Top-P 采樣參數
            
        Returns:
            生成的文本
        """
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature or self.config.temperature
        top_p = top_p or self.config.top_p
        
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": self.config.top_k,
        }
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.post(
                    f"{self.config.api_url}/completions",
                    json=payload
                )
                
                response.raise_for_status()
                
                data = response.json()
                text = data["choices"][0]["text"].strip()
                
                logger.debug(f"Generated text ({len(text)} chars)")
                
                return text
            
            except httpx.HTTPError as e:
                logger.warning(f"Attempt {attempt+1}/{self.config.max_retries} failed: {e}")
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds)
                else:
                    raise RuntimeError(f"vLLM inference failed after {self.config.max_retries} retries: {e}")
    
    async def batch_generate(
        self,
        prompts: List[str],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> List[str]:
        """批量生成文本。
        
        Args:
            prompts: 提示語列表
            max_tokens: 最大生成令牌數
            temperature: 采樣溫度
            
        Returns:
            生成的文本列表
        """
        
        tasks = [
            self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
            for prompt in prompts
        ]
        
        return await asyncio.gather(*tasks)
    
    async def close(self):
        """關閉連接。"""
        await self.client.aclose()
    
    async def __aenter__(self):
        """支持 async with。"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with。"""
        await self.close()


class vLLMStreamingClient:
    """vLLM 流式客戶端（用於 WebSocket）。"""
    
    def __init__(self, config: vLLMConfig = None):
        """初始化。"""
        self.config = config or vLLMConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
    
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """流式生成文本。
        
        Yields:
            生成的文本塊
        """
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature or self.config.temperature
        
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # 啟用流式
        }
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.config.api_url}/completions",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line[6:] if line.startswith("data: ") else line)
                        
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("text", "")
                            if delta:
                                yield delta
        
        except Exception as e:
            logger.error(f"Stream generation error: {e}")
            raise


# ============ FastAPI 集成 ============

"""
在你的 backend/main.py 中集成 vLLM：

from backend.services.vllm_client import vLLMClient, vLLMConfig
# SuggestionGenerator runs inside the remote ai_coach service.
# The main backend must call it through CoachBridge WebSocket only.

# 初始化 vLLM 客戶端
vllm_config = vLLMConfig(
    api_url="http://localhost:8000/v1",  # vLLM 服務地址
    model_name="unsloth/Qwen2.5-7B-bnb-4bit",
)

vllm_client = vLLMClient(config=vllm_config)

# 啟動事件
@app.on_event("startup")
async def startup_event():
    # 檢查 vLLM 服務
    health = await vllm_client.health_check()
    if health:
        logger.info("✅ vLLM service is available")
    else:
        logger.error("❌ vLLM service is not available. Please start vLLM service first.")
    
    # 初始化建議生成器（使用 vLLM）
    global suggestion_generator
    suggestion_generator = SuggestionGenerator(
        inference_engine=vllm_client,  # 傳入 vLLM 客戶端
        suggestion_queue=suggestion_queue
    )
    
    # 啟動後台任務
    asyncio.create_task(
        suggestion_generator.process_suggestions_forever()
    )

# 直接調用 vLLM 的端點
@app.post("/api/coach/generate-advice")
async def generate_advice(request: AdviceRequest):
    \"\"\"生成教練建議。\"\"\"
    
    try:
        advice = await vllm_client.generate(
            prompt=request.prompt,
            max_tokens=256,
            temperature=0.7
        )
        
        return {
            "status": "success",
            "advice": advice,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to generate advice: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 500

# 健康檢查
@app.get("/health")
async def health_check():
    \"\"\"檢查系統健康狀態。\"\"\"
    
    vllm_healthy = await vllm_client.health_check()
    
    return {
        "status": "healthy" if vllm_healthy else "degraded",
        "vllm_service": "online" if vllm_healthy else "offline",
        "timestamp": datetime.now().isoformat()
    }
"""


# ============ 修改 SuggestionGenerator ============

"""
修改 ai_coach/tools/websocket_coach.py 中的 SuggestionGenerator：

class SuggestionGenerator:
    def __init__(
        self,
        inference_engine,  # 改為接受 vLLMClient
        suggestion_queue: SuggestionQueue,
    ):
        self.inference_engine = inference_engine
        self.suggestion_queue = suggestion_queue
    
    async def _generate_suggestion_async(self, request: Dict) -> CoachSuggestion:
        \"\"\"非同步生成建議（使用 vLLM）。\"\"\"
        
        loop = asyncio.get_event_loop()
        
        # 直接使用 vLLM 客戶端的推論方法
        prompt = self._build_prompt(
            request["game_state"],
            request["player_info"]
        )
        
        # vLLM 客戶端本身已經支援非同步
        suggestion_text = await self.inference_engine.generate(
            prompt,
            max_tokens=256,
            temperature=0.7
        )
        
        suggestion = {
            "suggestion_id": request["id"],
            "timestamp": datetime.now().isoformat(),
            "game_type": request["game_state"].get("game_type", "nine_ball"),
            "white_ball_pos": request["game_state"].get("white_ball_pos", "中心位"),
            "target_ball_pos": request["game_state"].get("target_ball_pos", "底袋位"),
            "title": "打球建議",
            "advice_text": suggestion_text,
            "confidence_score": 0.85,
            "player_name": request["player_info"].get("name", "Player"),
            "player_skill_level": request["player_info"].get("skill_level", "intermediate"),
            "expected_success_rate": 0.7,
        }
        
        return CoachSuggestion(**suggestion)
"""


if __name__ == "__main__":
    print("vLLM 客戶端已實現，可集成到 FastAPI 後端")
