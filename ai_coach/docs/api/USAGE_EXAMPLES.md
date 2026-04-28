"""
AI Coach 實用範例 - 快速開始指南。

本檔案包含在 backend 中實際集成 AICoachManager 的代碼範例。
"""

# ============================================================================
# 例 1：在 WebSocket 主推論迴圈中集成 AI Coach（推薦）
# ============================================================================

import asyncio
from typing import Optional, List, Tuple

# 在 backend/main.py 的開頭添加
from ai_coach.client import AICoachManager

# 全域 AI Coach 實例
ai_coach_manager: Optional[AICoachManager] = None


async def initialize_ai_coach():
    """初始化 AI Coach Manager。"""
    global ai_coach_manager
    
    ai_coach_manager = AICoachManager(
        vllm_api_url="http://10.0.0.100:8000/v1/chat/completions",
        vllm_model="meta-llama/Llama-2-7b-chat-hf",
        table_width=1920,
        table_height=1080,
        frame_rate=60,
    )
    print("✅ AI Coach Manager ready")


# 在 app startup 事件中調用
@app.on_event("startup")
async def startup():
    global tracker, ai_coach_manager
    
    # ... 現有初始化代碼 ...
    tracker = PoolTracker(model_path=config.MODEL_PATH)
    
    # 初始化 AI Coach
    await initialize_ai_coach()


# ============================================================================
# 例 2：主推論迴圈中集成（WebSocket）
# ============================================================================

@app.websocket("/ws/game/{session_id}")
async def websocket_game_stream(websocket: WebSocket, session_id: str):
    """
    主遊戲流 WebSocket。
    
    整合了 YOLO 推論和 AI Coach 分析。
    """
    await websocket.accept()
    
    try:
        # 視頻流的幀迴圈
        frame_count = 0
        
        while True:
            # 1. 讀取幀（假設有攝像頭連接）
            ret, frame = camera.read()
            if not ret:
                break
            
            frame_count += 1
            
            # 2. YOLO 推論獲取球座標
            try:
                results = tracker.detect(frame)  # 根據實際 API 調整
                
                # 提取球中心座標
                ball_centers: List[Tuple[float, float]] = []
                
                # 根據 PoolTracker.detect() 的實際返回格式提取
                # 以下是假設的格式，需要根據實際調整
                if results is not None:
                    for detection in results:
                        if hasattr(detection, 'boxes'):
                            for box in detection.boxes:
                                cx = (box.xyxy[0][0].item() + box.xyxy[0][2].item()) / 2
                                cy = (box.xyxy[0][1].item() + box.xyxy[0][3].item()) / 2
                                ball_centers.append((cx, cy))
                
                # 3. 調用 AI Coach Manager
                if ai_coach_manager and ball_centers:
                    is_stable = ai_coach_manager.update(ball_centers, session_id)
                    
                    # 獲取最新分析結果
                    analysis = AICoachManager.get_global_result(session_id)
                    
                    # 發送給前端
                    response_data = {
                        "type": "frame_data",
                        "frame_count": frame_count,
                        "ball_count": len(ball_centers),
                        "is_stable": is_stable,
                        "analysis": analysis,  # 包含 AI 建議（如果有）
                    }
                    
                    await websocket.send_json(response_data)
                    
                    # 清除已發送的結果
                    if analysis:
                        AICoachManager.clear_result(session_id)
            
            except Exception as e:
                print(f"Error in frame processing: {e}")
            
            # 限制幀率（避免過快發送）
            await asyncio.sleep(1/60)  # 60 FPS
    
    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
        # 清理會話數據
        AICoachManager.clear_result(session_id)


# ============================================================================
# 例 3：使用 REST API 端點查詢結果
# ============================================================================

@app.get("/api/ai-coach/analyze/{session_id}")
async def get_ai_analysis(session_id: str):
    """
    REST API：獲取最新的 AI 分析結果。
    
    Example:
    GET /api/ai-coach/analyze/game_abc_123
    
    Response:
    {
        "timestamp": "2026-04-01T10:30:45.123456",
        "ball_positions": {
            "ball_0": "左上角",
            "ball_1": "中心位",
            "ball_2": "右下角"
        },
        "semantic_description": "3顆球在球台右下方區域",
        "recommendation": "建議先進黃球3號...",
        "confidence": 0.87,
        "processing_time": 1.23
    }
    """
    if ai_coach_manager is None:
        return JSONResponse(
            status_code=503,
            content={"error": "AI Coach Manager not available"}
        )
    
    result = AICoachManager.get_global_result(session_id)
    
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"message": "No analysis available yet"}
        )
    
    return JSONResponse(content=result)


# ============================================================================
# 例 4：手動觸發分析
# ============================================================================

@app.post("/api/ai-coach/analyze")
async def manual_analysis(
    frame_data: dict = Body(...),
    session_id: str = "manual"
):
    """
    手動觸發 AI 分析。
    
    Request body:
    {
        "balls": [
            {"x": 100, "y": 200},
            {"x": 500, "y": 300},
            ...
        ],
        "session_id": "optional_session_id"
    }
    """
    if ai_coach_manager is None:
        return JSONResponse(
            status_code=503,
            content={"error": "AI Coach Manager not available"}
        )
    
    try:
        balls_data = frame_data.get("balls", [])
        ball_centers = [(ball["x"], ball["y"]) for ball in balls_data]
        session_id = frame_data.get("session_id", session_id)
        
        # 觸發分析
        ai_coach_manager.update(ball_centers, session_id)
        
        return JSONResponse(
            status_code=202,
            content={"message": "Analysis triggered", "session_id": session_id}
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )


# ============================================================================
# 例 5：前端集成（React + TypeScript）
# ============================================================================

"""
// frontend/src/components/AICoachPanel.tsx

import React, { useEffect, useState, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

interface BallPosition {
  [key: string]: string;
}

interface AnalysisResult {
  timestamp: string;
  ball_positions: BallPosition;
  semantic_description: string;
  recommendation: string;
  confidence: number;
  processing_time: number;
}

interface GameStreamMessage {
  type: string;
  frame_count: number;
  ball_count: number;
  is_stable: boolean;
  analysis?: AnalysisResult;
}

export const AICoachPanel: React.FC<{ sessionId: string }> = ({ sessionId }) => {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [ballCount, setBallCount] = useState(0);

  const { lastMessage, readyState } = useWebSocket(
    `/ws/game/${sessionId}`
  );

  useEffect(() => {
    if (!lastMessage) return;

    try {
      const data: GameStreamMessage = JSON.parse(
        lastMessage.data
      );

      setBallCount(data.ball_count);

      if (data.is_stable) {
        setIsAnalyzing(true);
      }

      if (data.analysis) {
        setAnalysis(data.analysis);
        setIsAnalyzing(false);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [lastMessage]);

  return (
    <div className="ai-coach-panel">
      <div className="header">
        <h2>🤖 AI 教練</h2>
        <span className={`status ${readyState === 1 ? 'connected' : 'disconnected'}`}>
          {readyState === 1 ? '● 連接中' : '○ 未連接'}
        </span>
      </div>

      <div className="stats">
        <p>檢測到的球數: <strong>{ballCount}</strong></p>
      </div>

      {isAnalyzing && (
        <div className="analyzing">
          <div className="spinner"></div>
          <p>分析中...</p>
        </div>
      )}

      {analysis && (
        <div className="analysis-result">
          <div className="description">
            <h3>局面描述</h3>
            <p>{analysis.semantic_description}</p>
          </div>

          <div className="recommendation">
            <h3>📋 AI 建議</h3>
            <p>{analysis.recommendation}</p>
          </div>

          <div className="confidence">
            <h3>置信度: {(analysis.confidence * 100).toFixed(0)}%</h3>
            <div className="progress-bar">
              <div 
                className="progress" 
                style={{ width: `${analysis.confidence * 100}%` }}
              />
            </div>
          </div>

          <div className="metadata">
            <small>
              處理時間: {analysis.processing_time.toFixed(2)}s | 
              時間戳: {new Date(analysis.timestamp).toLocaleTimeString()}
            </small>
          </div>
        </div>
      )}

      {!analysis && !isAnalyzing && (
        <div className="empty-state">
          <p>等待球台靜止以獲取分析...</p>
        </div>
      )}
    </div>
  );
};

// CSS 樣式示例
const AICoachStyles = `
.ai-coach-panel {
  border: 2px solid #4CAF50;
  border-radius: 8px;
  padding: 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  font-family: 'Segoe UI', sans-serif;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.header h2 {
  margin: 0;
  color: #2c3e50;
}

.status {
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 20px;
  background: #ecf0f1;
}

.status.connected {
  color: #27ae60;
}

.status.disconnected {
  color: #e74c3c;
}

.analyzing {
  text-align: center;
  padding: 20px;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #4CAF50;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.analysis-result {
  background: white;
  border-radius: 8px;
  padding: 15px;
  margin-top: 10px;
}

.description, .recommendation {
  margin-bottom: 15px;
}

.description h3, .recommendation h3 {
  margin: 0 0 8px 0;
  color: #2c3e50;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.recommendation {
  background: #e8f5e9;
  padding: 10px;
  border-radius: 5px;
  border-left: 4px solid #4CAF50;
}

.confidence {
  margin-top: 15px;
}

.progress-bar {
  height: 8px;
  background: #ecf0f1;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 5px;
}

.progress {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #45a049);
  transition: width 0.3s ease;
}

.metadata {
  margin-top: 10px;
  color: #7f8c8d;
}

.empty-state {
  text-align: center;
  padding: 30px;
  color: #95a5a6;
}
`;
"""


# ============================================================================
# 例 6：A100 vLLM 伺服器配置範例
# ============================================================================

"""
# 在 A100 伺服器上啟動 vLLM

# 1. 安裝 vLLM
pip install vllm

# 2. 啟動 vLLM 伺服器（以 Llama-2-7b-chat 為例）
python -m vllm.entrypoints.openai.api_server \\
    --model meta-llama/Llama-2-7b-chat-hf \\
    --gpu-memory-utilization 0.9 \\
    --tensor-parallel-size 1 \\
    --dtype bfloat16 \\
    --max-num-seqs 256 \\
    --enable-prefix-caching \\
    --port 8000

# 3. 測試 API
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "messages": [
      {"role": "user", "content": "台球比賽的技巧是什麼？"}
    ],
    "temperature": 0.7,
    "max_tokens": 256
  }'

# 4. 在 OpenCV 主程式中配置對應的 vLLM API 地址
ai_coach_manager = AICoachManager(
    vllm_api_url="http://10.0.0.100:8000/v1/chat/completions",
    vllm_model="meta-llama/Llama-2-7b-chat-hf",
)
"""


# ============================================================================
# 例 7：調試和監控
# ============================================================================

@app.get("/api/ai-coach/debug/{session_id}")
async def debug_ai_coach(session_id: str):
    """
    調試端點：查詢 AI Coach 內部狀態。
    
    Returns:
    {
        "detector_state": {
            "buffer_size": 60,
            "is_in_cooldown": false,
            "stable_frame_count": 45,
            "last_report": true
        },
        "session_id": "debug_session"
    }
    """
    if ai_coach_manager is None:
        return JSONResponse(
            status_code=503,
            content={"error": "AI Coach Manager not available"}
        )
    
    return JSONResponse(
        content={
            "detector_state": ai_coach_manager.get_detector_state(),
            "session_id": session_id,
        }
    )


@app.post("/api/ai-coach/reset/{session_id}")
async def reset_ai_coach(session_id: str):
    """
    重置 AI Coach 檢測器（用於新遊戲開始）。
    """
    if ai_coach_manager is None:
        return JSONResponse(
            status_code=503,
            content={"error": "AI Coach Manager not available"}
        )
    
    ai_coach_manager.reset_detector()
    AICoachManager.clear_result(session_id)
    
    return JSONResponse(
        status_code=200,
        content={"message": "AI Coach reset successfully"}
    )


# ============================================================================
# 快速集成檢查清單
# ============================================================================

"""
集成 AI Coach 的檢查清單：

□ 1. 安裝依賴
    pip install requests numpy

□ 2. 配置 vLLM API 地址
    - 確認 A100 伺服器地址
    - 測試 API 連接能力

□ 3. 初始化 AICoachManager
    - 在 app startup 事件中調用 initialize_ai_coach()

□ 4. 集成到主推論迴圈
    - 從 YOLO 提取球座標
    - 調用 ai_coach_manager.update()

□ 5. 前端集成
    - 連接 WebSocket /ws/game/{session_id}
    - 顯示 AI 建議面板

□ 6. 測試和調試
    - 使用 /api/ai-coach/debug/{session_id} 查看內部狀態
    - 監控處理時間和錯誤

□ 7. 性能優化
    - 調整 vLLM 的 GPU 利用率
    - 考慮請求批處理
"""
