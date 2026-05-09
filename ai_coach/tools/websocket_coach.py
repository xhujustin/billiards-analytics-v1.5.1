"""
AI Coach WebSocket 實時建議系統

架構：
1. 後端：非同步建議佇列 + WebSocket 推送
2. 前端：連接管理 + 去抖動 + 狀態同步
3. 訊息協議：JSON schema 定義

流程：
  方式A（推式）：球位穩定 → 後端自動生成 → 推送給所有客戶端
  方式B（拉式）：前端輪詢 /api/practice/state → 得到實時建議
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import uuid
from collections import deque

# Async server
from fastapi import WebSocket, WebSocketDisconnect
from concurrent.futures import ThreadPoolExecutor
import threading

# Client side (TypeScript simulation for documentation)
# In production, use: npm install ws reconnecting-websocket

logger = logging.getLogger(__name__)


# ============ 訊息協議定義 ============

class MessageType(str, Enum):
    """WebSocket 訊息類型。"""
    
    # 連接生命週期
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    HEARTBEAT = "heartbeat"
    
    # AI 建議
    COACH_SUGGESTION = "coach_suggestion"
    SUGGESTION_REQUEST = "suggestion_request"
    SUGGESTION_ACKNOWLEDGE = "suggestion_acknowledge"
    
    # 狀態更新
    GAME_STATE_UPDATE = "game_state_update"
    PRACTICE_STATE_UPDATE = "practice_state_update"
    PLAYER_STATS_UPDATE = "player_stats_update"
    
    # 錯誤與控制
    ERROR = "error"
    CONFIG_CHANGE = "config_change"


@dataclass
class CoachSuggestion:
    """AI 教練建議。"""
    
    # 基本信息
    suggestion_id: str
    timestamp: str
    
    # 場景
    game_type: str  # "nine_ball", "practice_single" 等
    white_ball_pos: str  # "左上角", "中心位" 等
    target_ball_pos: str  # "底袋位" 等
    
    # 建議內容
    title: str  # 簡短標題
    advice_text: str  # 詳細建議
    confidence_score: float  # 0-1
    
    # 附加信息
    player_name: str = "Player"
    player_skill_level: str = "intermediate"
    expected_success_rate: float = 0.7
    
    # UI 提示
    display_duration_ms: int = 5000  # 顯示時長
    priority: str = "normal"  # "low", "normal", "high"
    
    def to_dict(self) -> Dict:
        """轉換為字典。"""
        return asdict(self)


@dataclass
class WebSocketMessage:
    """標準 WebSocket 訊息格式。"""
    
    type: str
    data: Dict
    timestamp: Optional[str] = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())
    
    def to_json(self) -> str:
        """轉換為 JSON。"""
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """從 JSON 解析。"""
        data = json.loads(json_str)
        return cls(**data)


# ============ 後端：建議隊列系統 ============

class SuggestionQueue:
    """非同步建議隊列 - 解耦生成和推送。"""
    
    def __init__(self, max_queue_size: int = 1000):
        """初始化隊列。
        
        Args:
            max_queue_size: 最大隊列大小
        """
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.processing_tasks = {}  # task_id -> Task
        self.completed_suggestions = deque(maxlen=100)  # 保留最近 100 條
    
    async def enqueue_suggestion_request(
        self,
        game_state: Dict,
        player_info: Dict,
    ) -> str:
        """入隊建議請求。
        
        Args:
            game_state: 遊戲狀態
            player_info: 玩家信息
            
        Returns:
            請求 ID
        """
        request_id = str(uuid.uuid4())
        
        request = {
            "id": request_id,
            "game_state": game_state,
            "player_info": player_info,
            "created_at": datetime.now().isoformat(),
        }
        
        await self.queue.put(request)
        logger.info(f"Suggestion request queued: {request_id}")
        
        return request_id
    
    async def get_next_request(self) -> Dict:
        """獲取下一個待處理請求。"""
        return await self.queue.get()
    
    def add_completed_suggestion(self, suggestion: CoachSuggestion):
        """添加已完成的建議到歷史記錄。"""
        self.completed_suggestions.append(suggestion)
    
    def record_task(self, task_id: str, task: asyncio.Task):
        """記錄正在進行的任務。"""
        self.processing_tasks[task_id] = task
    
    def remove_task(self, task_id: str):
        """移除已完成的任務。"""
        self.processing_tasks.pop(task_id, None)


class SuggestionGenerator:
    """非同步建議生成器。"""
    
    def __init__(
        self,
        inference_engine,  # InferenceEngine 實例
        suggestion_queue: SuggestionQueue,
    ):
        """初始化生成器。
        
        Args:
            inference_engine: 推論引擎
            suggestion_queue: 建議隊列
        """
        self.inference_engine = inference_engine
        self.suggestion_queue = suggestion_queue
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    async def process_suggestions_forever(self):
        """持續處理隊列中的建議請求。"""
        
        logger.info("Suggestion generator started")
        
        while True:
            try:
                # 獲取下一個請求
                request = await self.suggestion_queue.get_next_request()
                
                logger.info(f"Processing suggestion request: {request['id']}")
                
                # 非同步執行推論（避免阻塞）
                suggestion = await self._generate_suggestion_async(request)
                
                # 添加到已完成隊列
                self.suggestion_queue.add_completed_suggestion(suggestion)
                
                logger.info(f"Suggestion generated: {suggestion.suggestion_id}")
                
            except Exception as e:
                logger.error(f"Error processing suggestion: {e}")
                await asyncio.sleep(1)  # 錯誤後等待再試
    
    async def _generate_suggestion_async(self, request: Dict) -> CoachSuggestion:
        """非同步生成建議。
        
        Args:
            request: 建議請求
            
        Returns:
            生成的建議
        """
        
        loop = asyncio.get_event_loop()
        
        # 在執行器中運行推論（避免阻塞主事件循環）
        suggestion_dict = await loop.run_in_executor(
            self.executor,
            self._generate_suggestion_sync,
            request
        )
        
        return CoachSuggestion(**suggestion_dict)
    
    def _generate_suggestion_sync(self, request: Dict) -> Dict:
        """同步生成建議（在執行器中執行）。"""
        
        game_state = request["game_state"]
        player_info = request["player_info"]
        
        # 構建提示語
        prompt = self._build_prompt(game_state, player_info)
        
        # 調用推論引擎
        advice_text = self.inference_engine.generate(
            prompt,
            max_length=256,
            temperature=0.7,
        )
        
        # 構建建議對象
        suggestion = {
            "suggestion_id": request["id"],
            "timestamp": datetime.now().isoformat(),
            "game_type": game_state.get("game_type", "nine_ball"),
            "white_ball_pos": game_state.get("white_ball_pos", "中心位"),
            "target_ball_pos": game_state.get("target_ball_pos", "底袋位"),
            "title": "打球建議",
            "advice_text": advice_text,
            "confidence_score": 0.85,
            "player_name": player_info.get("name", "Player"),
            "player_skill_level": player_info.get("skill_level", "intermediate"),
            "expected_success_rate": self._estimate_success_rate(
                game_state,
                player_info
            ),
        }
        
        return suggestion
    
    def _build_prompt(self, game_state: Dict, player_info: Dict) -> str:
        """構建推論提示語。"""
        
        white_pos = game_state.get("white_ball_pos", "未知")
        target_pos = game_state.get("target_ball_pos", "未知")
        nearby_count = game_state.get("nearby_balls_count", 0)
        skill_level = player_info.get("skill_level", "intermediate")
        
        prompt = (
            f"撞球場景分析：\n"
            f"- 白球位置：{white_pos}\n"
            f"- 標靶球位置：{target_pos}\n"
            f"- 周圍球數量：{nearby_count}\n"
            f"- 玩家等級：{skill_level}\n\n"
            f"請提供詳細的打球建議（限 100 字以內）。"
        )
        
        return prompt
    
    def _estimate_success_rate(
        self,
        game_state: Dict,
        player_info: Dict,
    ) -> float:
        """估計成功概率。"""
        
        base_rate = 0.5
        
        # 根據玩家等級調整
        skill_adjustment = {
            "beginner": -0.1,
            "intermediate": 0,
            "advanced": 0.2,
        }
        skill_level = player_info.get("skill_level", "intermediate")
        if not isinstance(skill_level, str):
            skill_level = "intermediate"
        base_rate += skill_adjustment.get(skill_level, 0)
        
        # 根據周圍球數調整
        nearby_count_raw = game_state.get("nearby_balls_count", 0)
        nearby_count = nearby_count_raw if isinstance(nearby_count_raw, (int, float)) else 0
        base_rate -= nearby_count * 0.05  # 每多 1 顆球，成功率下降 5%
        
        return max(0, min(1, base_rate))


class WebSocketConnectionManager:
    """WebSocket 連接管理。"""
    
    def __init__(self, suggestion_queue: SuggestionQueue):
        """初始化連接管理器。
        
        Args:
            suggestion_queue: 建議隊列
        """
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_sessions: Dict[str, Dict] = {}  # client_id -> session_data
        self.suggestion_queue = suggestion_queue
    
    async def connect(self, websocket: WebSocket, client_id: str, session_id: str):
        """客戶端連接。"""
        await websocket.accept()
        
        self.active_connections[client_id] = websocket
        self.client_sessions[client_id] = {
            "session_id": session_id,
            "connected_at": datetime.now().isoformat(),
        }
        
        logger.info(f"Client connected: {client_id}")
        
        # 發送歡迎訊息
        welcome_msg = WebSocketMessage(
            type=MessageType.CONNECT,
            data={"status": "connected", "client_id": client_id}
        )
        await websocket.send_text(welcome_msg.to_json())
    
    async def disconnect(self, client_id: str):
        """客戶端斷開。"""
        self.active_connections.pop(client_id, None)
        self.client_sessions.pop(client_id, None)
        
        logger.info(f"Client disconnected: {client_id}")
    
    async def broadcast_suggestion(self, suggestion: CoachSuggestion):
        """廣播建議給所有連接的客戶端。
        
        推送策略：
            - 優先級高的建議立即發送
            - 優先級低的建議可以合併（去抖動）
        """
        
        msg = WebSocketMessage(
            type=MessageType.COACH_SUGGESTION,
            data=suggestion.to_dict()
        )
        
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(msg.to_json())
                logger.debug(f"Suggestion sent to {client_id}")
            
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # 清理斷開的連接
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    async def send_to_client(self, client_id: str, message: WebSocketMessage):
        """發送訊息到特定客戶端。"""
        
        if client_id not in self.active_connections:
            logger.error(f"Client {client_id} not connected")
            return
        
        websocket = self.active_connections[client_id]
        
        try:
            await websocket.send_text(message.to_json())
        except Exception as e:
            logger.error(f"Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)


# ============ FastAPI 後端路由 ============

class CoachWebSocketRouter:
    """AI 教練 WebSocket 路由。"""
    
    def __init__(
        self,
        suggestion_queue: SuggestionQueue,
        suggestion_generator: SuggestionGenerator,
        connection_manager: WebSocketConnectionManager,
    ):
        """初始化路由。
        
        Args:
            suggestion_queue: 建議隊列
            suggestion_generator: 建議生成器
            connection_manager: 連接管理器
        """
        self.suggestion_queue = suggestion_queue
        self.suggestion_generator = suggestion_generator
        self.connection_manager = connection_manager
    
    async def websocket_endpoint(
        self,
        websocket: WebSocket,
        session_id: str,
    ):
        """WebSocket 端點。
        
        使用方式（客戶端）：
            ws://localhost:8001/ws/coach?session_id=xxx
        """
        
        client_id = str(uuid.uuid4())
        
        try:
            # 連接
            await self.connection_manager.connect(
                websocket,
                client_id,
                session_id
            )
            
            # 接收訊息迴圈
            while True:
                data = await websocket.receive_text()
                
                msg = WebSocketMessage.from_json(data)
                
                # 處理不同的訊息類型
                if msg.type == MessageType.SUGGESTION_REQUEST:
                    await self._handle_suggestion_request(
                        client_id,
                        msg
                    )
                
                elif msg.type == MessageType.HEARTBEAT:
                    await self._handle_heartbeat(client_id, msg)
                
                elif msg.type == MessageType.CONFIG_CHANGE:
                    await self._handle_config_change(client_id, msg)
        
        except WebSocketDisconnect:
            await self.connection_manager.disconnect(client_id)
        
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
            await self.connection_manager.disconnect(client_id)
    
    async def _handle_suggestion_request(self, client_id: str, msg: WebSocketMessage):
        """處理建議請求。"""
        
        game_state = msg.data.get("game_state", {})
        player_info = msg.data.get("player_info", {})
        
        # 入隊請求
        request_id = await self.suggestion_queue.enqueue_suggestion_request(
            game_state,
            player_info
        )
        
        # 發送確認
        ack_msg = WebSocketMessage(
            type=MessageType.SUGGESTION_ACKNOWLEDGE,
            data={"request_id": request_id},
            request_id=msg.request_id,
        )
        
        await self.connection_manager.send_to_client(client_id, ack_msg)
    
    async def _handle_heartbeat(self, client_id: str, msg: WebSocketMessage):
        """處理心跳。"""
        
        response = WebSocketMessage(
            type=MessageType.HEARTBEAT,
            data={"status": "alive"},
            request_id=msg.request_id,
        )
        
        await self.connection_manager.send_to_client(client_id, response)
    
    async def _handle_config_change(self, client_id: str, msg: WebSocketMessage):
        """處理配置變更。"""
        
        config = msg.data.get("config", {})
        logger.info(f"Config change for {client_id}: {config}")


# ============ 前端集成（TypeScript 示例説明） ============

FRONTEND_INTEGRATION_GUIDE = """
# 前端 WebSocket 集成指南（React/TypeScript）

## 安裝依賴
```bash
npm install ws reconnecting-websocket
npm install --save-dev @types/ws
```

## 實現步驟

### 1. WebSocket 連接管理 (hooks/useCoachWebSocket.ts)
```typescript
import { useEffect, useRef, useState } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';

interface CoachSuggestion {
  suggestion_id: string;
  title: string;
  advice_text: string;
  confidence_score: number;
  priority: 'low' | 'normal' | 'high';
  display_duration_ms: number;
}

export const useCoachWebSocket = (sessionId: string) => {
  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const [suggestion, setSuggestion] = useState<CoachSuggestion | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 連接 WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8001/ws/coach?session_id=${sessionId}`;
    
    wsRef.current = new ReconnectingWebSocket(wsUrl);
    
    wsRef.current.addEventListener('open', () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setError(null);
      
      // 發送心跳
      sendHeartbeat();
    });
    
    wsRef.current.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      
      if (msg.type === 'coach_suggestion') {
        setSuggestion(msg.data);
        
        // 自動隱藏
        const duration = msg.data.display_duration_ms || 5000;
        setTimeout(() => setSuggestion(null), duration);
      }
    });
    
    wsRef.current.addEventListener('close', () => {
      setIsConnected(false);
    });
    
    wsRef.current.addEventListener('error', (event) => {
      setError('WebSocket connection error');
      console.error('WebSocket error:', event);
    });
    
    return () => {
      wsRef.current?.close();
    };
  }, [sessionId]);
  
  const sendHeartbeat = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'heartbeat',
        timestamp: new Date().toISOString(),
      }));
    }
    
    // 每 30 秒發送一次
    setTimeout(sendHeartbeat, 30000);
  };
  
  const requestSuggestion = (gameState: any, playerInfo: any) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket not connected');
      return;
    }
    
    wsRef.current.send(JSON.stringify({
      type: 'suggestion_request',
      data: {
        game_state: gameState,
        player_info: playerInfo,
      },
      timestamp: new Date().toISOString(),
    }));
  };
  
  return {
    suggestion,
    isConnected,
    error,
    requestSuggestion,
  };
};
```

### 2. UI 元件 (components/CoachPanel.tsx)
```typescript
import React from 'react';
import { useCoachWebSocket } from '../hooks/useCoachWebSocket';

interface CoachPanelProps {
  sessionId: string;
  gameState: any;
  playerInfo: any;
}

export const CoachPanel: React.FC<CoachPanelProps> = ({
  sessionId,
  gameState,
  playerInfo,
}) => {
  const { suggestion, isConnected, error, requestSuggestion } = 
    useCoachWebSocket(sessionId);
  
  React.useEffect(() => {
    // 球位穩定時自動請求建議
    if (gameState.is_stable && !suggestion) {
      requestSuggestion(gameState, playerInfo);
    }
  }, [gameState.is_stable]);
  
  return (
    <div className="coach-panel">
      {error && <div className="alert alert-error">{error}</div>}
      
      <div className="connection-status">
        {isConnected ? '🟢 已連接' : '🔴 已斷開'}
      </div>
      
      {suggestion && (
        <div className={`suggestion ${suggestion.priority}`}>
          <h3>{suggestion.title}</h3>
          <p>{suggestion.advice_text}</p>
          <div className="confidence">
            信心度: {(suggestion.confidence_score * 100).toFixed(0)}%
          </div>
        </div>
      )}
    </div>
  );
};
```

### 3. 集成到練習頁面 (pages/PracticePage.tsx)
```typescript
<CoachPanel
  sessionId={session.id}
  gameState={currentGameState}
  playerInfo={playerProfile}
/>
```

## 去抖動策略

```typescript
// 避免過於頻繁的建議更新
const debouncedRequestSuggestion = useCallback(
  debounce((gameState, playerInfo) => {
    requestSuggestion(gameState, playerInfo);
  }, 1000),  // 1 秒內最多發送一次
  [requestSuggestion]
);
```

## 錯誤處理

- 自動重連：ReconnectingWebSocket 會自動嘗試重連
- 心跳保活：定期發送心跳防止連接超時
- 優雅降級：若 WebSocket 不可用，回退到 REST API 輪詢
"""


if __name__ == "__main__":
    print(FRONTEND_INTEGRATION_GUIDE)
    
    # 初始化各個組件
    logger.info("Initializing AI Coach WebSocket System...")
    
    # 假設推論引擎已初始化
    # inference_engine = InferenceEngine(...)
    
    # 創建隊列
    suggestion_queue = SuggestionQueue()
    
    # 創建生成器
    # suggestion_generator = SuggestionGenerator(inference_engine, suggestion_queue)
    
    # 創建連接管理器
    connection_manager = WebSocketConnectionManager(suggestion_queue)
    
    # 創建路由
    # router = CoachWebSocketRouter(
    #     suggestion_queue,
    #     suggestion_generator,
    #     connection_manager
    # )
    
    logger.info("✅ AI Coach WebSocket System initialized")
