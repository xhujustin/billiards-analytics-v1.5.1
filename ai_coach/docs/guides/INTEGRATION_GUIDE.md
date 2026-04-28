"""
AI Coach 整合範例 - 展示如何在 OpenCV 主程式中使用 AICoachManager。

此檔案展示如何將 AICoachManager 整合到 backend/main.py 中。
"""

# ============ 在 backend/main.py 中添加的代碼 ============

import sys
from pathlib import Path

# 添加 ai_coach 模組到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_coach.client import AICoachManager

# 全域 AICoachManager 實例
ai_coach_manager: Optional[AICoachManager] = None


def initialize_ai_coach():
    """初始化 AI Coach Manager。"""
    global ai_coach_manager
    
    try:
        ai_coach_manager = AICoachManager(
            vllm_api_url="http://10.0.0.100:8000/v1/chat/completions",  # A100 伺服器地址
            vllm_model="meta-llama/Llama-2-7b-chat-hf",  # 或其他模型
            table_width=1920,  # 根據實際調整
            table_height=1080,
            frame_rate=60,
        )
        print("✅ AI Coach Manager initialized successfully")
    except Exception as e:
        print(f"⚠️  Failed to initialize AI Coach Manager: {e}")
        ai_coach_manager = None


# ============ 在主程式的球追蹤迴圈中調用 ============

async def process_frame_with_ai_coach(frame, session_id="default"):
    """
    在主追蹤迴圈中調用此函數以整合 AI Coach。
    
    Example usage in main tracking loop:
    
    ```python
    # 在 main.py 中的某個地方（比如 WebSocket 或主迴圈）
    for frame in frame_stream:
        # ... 現有的 YOLO 推論代碼 ...
        
        # 從 YOLO 得到球座標
        ball_centers = [(center_x, center_y) for detection in yolo_results]
        
        # 調用 AI Coach 進行實時分析
        is_stable = ai_coach_manager.update(ball_centers, session_id)
        
        # 如果觸發穩定，UI 可以顯示分析結果
        if is_stable:
            result = AICoachManager.get_global_result(session_id)
            # 通過 WebSocket 發送給前端
            await websocket.send_json(result)
    ```
    
    Args:
        frame: OpenCV frame
        session_id: 會話識別符
    """
    if ai_coach_manager is None:
        return
    
    try:
        # 1. 進行 YOLO 推論（現有代碼）
        results = tracker.detect(frame)  # 根據實際調整
        
        # 2. 提取球中心座標
        ball_centers = []
        for detection in results:
            # 根據 PoolTracker.detect() 的實際返回格式調整
            cx, cy = detection.get("center_x"), detection.get("center_y")
            if cx is not None and cy is not None:
                ball_centers.append((cx, cy))
        
        # 3. 發送到 AI Coach Manager
        is_stable = ai_coach_manager.update(ball_centers, session_id)
        
        return is_stable
    
    except Exception as e:
        print(f"❌ Error in process_frame_with_ai_coach: {e}")


# ============ WebSocket 端點：返回 AI 分析結果 ============

@app.websocket("/ws/ai-coach/{session_id}")
async def websocket_ai_coach(websocket: WebSocket, session_id: str = "default"):
    """
    WebSocket 端點：實時推送 AI Coach 分析結果。
    
    Usage:
    - 前端連接：ws://localhost:8000/ws/ai-coach/game_session_123
    - 每當偵測到穩定並獲得 AI 建議，就推送結果給前端
    """
    await websocket.accept()
    
    try:
        while True:
            # 每 100ms 檢查一次新結果
            result = AICoachManager.get_global_result(session_id)
            
            if result:
                # 有新結果，推送給前端
                await websocket.send_json({
                    "type": "ai_coach_analysis",
                    "data": result,
                })
                
                # 清除已發送的結果（避免重複）
                AICoachManager.clear_result(session_id)
            
            await asyncio.sleep(0.1)
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")


# ============ REST API 端點：查詢最新分析結果 ============

@app.get("/api/ai-coach/result/{session_id}")
async def get_ai_coach_result(session_id: str = "default"):
    """
    REST API 端點：獲取最新的 AI 分析結果。
    
    Example:
    GET /api/ai-coach/result/game_session_123
    
    Response:
    {
        "timestamp": "2026-04-01T10:30:45.123456",
        "ball_positions": {
            "ball_0": "左上角",
            "ball_1": "中心位",
            ...
        },
        "semantic_description": "3顆球聚集在中心位，1顆球在左下角",
        "recommendation": "建議先進紅球...進球後走位到右中位...",
        "confidence": 0.85,
        "processing_time": 2.34
    }
    """
    result = AICoachManager.get_global_result(session_id)
    
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No analysis result available"}
        )
    
    return JSONResponse(content=result)


# ============ REST API 端點：查詢偵測器狀態（調試用） ============

@app.get("/api/ai-coach/detector-state/{session_id}")
async def get_detector_state(session_id: str = "default"):
    """
    REST API 端點：獲取穩定性偵測器的內部狀態（調試用）。
    
    Returns:
    {
        "buffer_size": 60,
        "is_in_cooldown": false,
        "stable_frame_count": 32,
        "last_report": false
    }
    """
    if ai_coach_manager is None:
        return JSONResponse(
            status_code=503,
            content={"error": "AI Coach Manager not initialized"}
        )
    
    return JSONResponse(
        content=ai_coach_manager.get_detector_state()
    )


# ============ 在應用啟動時初始化 AI Coach ============

@app.on_event("startup")
async def startup_event():
    """應用啟動事件。"""
    global tracker, calibrator, image_processor, ai_coach_manager
    
    # ... 現有的初始化代碼 ...
    
    # 初始化 AI Coach Manager
    initialize_ai_coach()


# ============ 使用示例：在主推論迴圈中集成 ============

@app.get("/stream/video")
async def stream_video():
    """
    視頻流端點，展示如何在實時流中集成 AI Coach。
    
    此函數展示如何在主追蹤迴圈中調用 AICoachManager.update()。
    """
    
    def generate_frames():
        session_id = "video_stream_default"
        
        while True:
            try:
                # 1. 讀取幀
                ret, frame = camera.read()
                if not ret:
                    break
                
                # 2. YOLO 推論
                results = tracker.detect(frame)
                
                # 3. 提取球座標
                ball_centers = []
                for detection in results:
                    # 根據 PoolTracker 的輸出格式調整
                    if hasattr(detection, 'boxes'):
                        for box in detection.boxes:
                            cx = (box.xyxy[0][0] + box.xyxy[0][2]) / 2
                            cy = (box.xyxy[0][1] + box.xyxy[0][3]) / 2
                            ball_centers.append((cx.item(), cy.item()))
                
                # 4. AI Coach 分析
                if ball_centers:
                    is_stable = ai_coach_manager.update(ball_centers, session_id)
                    
                    # 如果穩定，可以在幀上繪製提示
                    if is_stable:
                        cv2.putText(
                            frame,
                            "AI Analyzing...",
                            (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 255, 0),
                            2
                        )
                
                # 5. 編碼並發送幀
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' +
                       frame_bytes + b'\r\n')
            
            except Exception as e:
                print(f"Error in generate_frames: {e}")
                break
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ============ 前端整合範例（TypeScript/React） ============

"""
// frontend/src/hooks/useAICoach.ts

import { useEffect, useState, useCallback } from 'react';

interface AIAnalysis {
  timestamp: string;
  ball_positions: Record<string, string>;
  semantic_description: string;
  recommendation: string;
  confidence: number;
  processing_time: number;
}

export const useAICoach = (sessionId: string = 'default') => {
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // WebSocket 連接
    const ws = new WebSocket(`ws://localhost:8000/ws/ai-coach/${sessionId}`);

    ws.onopen = () => {
      setConnected(true);
      console.log('✅ Connected to AI Coach');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'ai_coach_analysis') {
        setAnalysis(message.data);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => ws.close();
  }, [sessionId]);

  const fetchLatestAnalysis = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/ai-coach/result/${sessionId}`
      );
      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);
      }
    } catch (error) {
      console.error('Failed to fetch analysis:', error);
    }
  }, [sessionId]);

  return { analysis, connected, fetchLatestAnalysis };
};

// Usage in component:
const AICoachPanel = () => {
  const { analysis, connected } = useAICoach('game_session_abc');

  if (!connected) return <div>Connecting to AI Coach...</div>;
  
  if (!analysis) return <div>Waiting for analysis...</div>;

  return (
    <div className="ai-coach-panel">
      <h3>AI Coach Recommendation</h3>
      <p><strong>局面描述：</strong> {analysis.semantic_description}</p>
      <p><strong>建議：</strong> {analysis.recommendation}</p>
      <p><strong>處理時間：</strong> {analysis.processing_time.toFixed(2)}s</p>
      <p><strong>置信度：</strong> {(analysis.confidence * 100).toFixed(0)}%</p>
    </div>
  );
};
"""
