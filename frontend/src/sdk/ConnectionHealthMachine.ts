/**
 * Connection Health Machine（v1.5）
 * 實現 Connection Health Score (CHS) 狀態機
 * 優先序：DISCONNECTED > STALE > NO_SIGNAL > DEGRADED > HEALTHY
 */

import { ConnectionHealth, PipelineState, ConnectionHealthState } from './types';

// CHS 閾值定案
const HEARTBEAT_TIMEOUT_MS = 6000; // 2x interval (3s)
const FRAME_TIMEOUT_MS = 2000; // 超過 2 秒未更新畫面
const MIN_FPS = 10; // 最小可接受 FPS

export class ConnectionHealthMachine {
  private state: ConnectionHealthState = {
    health: ConnectionHealth.DISCONNECTED,
    lastHeartbeat: 0,
    lastFrameTs: 0,
    wsConnected: false,
    pipelineState: PipelineState.NO_SIGNAL,
    fpsEwma: 0,
  };

  private listeners: ((state: ConnectionHealthState) => void)[] = [];
  private checkInterval: NodeJS.Timeout | null = null;
  private consecutiveHealthyHeartbeats: number = 0;

  constructor() {
    this.startHealthCheck();
  }

  /**
   * 更新 WebSocket 連接狀態
   */
  updateWSConnection(connected: boolean): void {
    this.state.wsConnected = connected;
    this.updateHealth();
  }

  /**
   * 更新 heartbeat 時間戳
   */
  updateHeartbeat(timestamp: number, payload: any): void {
    this.state.lastHeartbeat = timestamp;
    this.state.lastFrameTs = payload.last_frame_ts || 0;
    this.state.pipelineState = payload.pipeline_state || PipelineState.NO_SIGNAL;
    this.state.fpsEwma = payload.fps_ewma || 0;
    
    // 追蹤連續健康的 heartbeat（用於 STALE → HEALTHY 轉換）
    const now = Date.now();
    if (
      now - this.state.lastFrameTs <= FRAME_TIMEOUT_MS &&
      this.state.pipelineState === PipelineState.RUNNING
    ) {
      this.consecutiveHealthyHeartbeats++;
    } else {
      this.consecutiveHealthyHeartbeats = 0;
    }
    
    this.updateHealth();
  }

  /**
   * 更新健康度狀態（v1.5 定案轉換邏輯）
   */
  private updateHealth(): void {
    const now = Date.now();
    const { wsConnected, lastHeartbeat, pipelineState, fpsEwma } = this.state;
    
    let newHealth: ConnectionHealth;
    const timeSinceHeartbeat = now - lastHeartbeat;

    // 優先序：DISCONNECTED > STALE > NO_SIGNAL > DEGRADED > HEALTHY
    if (!wsConnected) {
      newHealth = ConnectionHealth.DISCONNECTED;
    } else if (timeSinceHeartbeat > HEARTBEAT_TIMEOUT_MS) {
      // WS 連線中但超過 6 秒未收到 heartbeat（後端卡死或事件迴圈停滯）
      newHealth = ConnectionHealth.STALE;
    } else {
      // ✅ 信任後端的 pipeline_state 判斷，避免時鐘同步問題
      switch (pipelineState) {
        case PipelineState.NO_SIGNAL:
          newHealth = ConnectionHealth.NO_SIGNAL;
          break;
        case PipelineState.ERROR:
          newHealth = ConnectionHealth.STALE;
          break;
        case PipelineState.RECONNECTING:
          newHealth = ConnectionHealth.DEGRADED;
          break;
        case PipelineState.RUNNING:
          // 檢查 FPS 是否過低
          if (fpsEwma < MIN_FPS) {
            newHealth = ConnectionHealth.DEGRADED;
          } else {
            newHealth = ConnectionHealth.HEALTHY;
          }
          break;
        default:
          newHealth = ConnectionHealth.DEGRADED;
      }
    }

    if (newHealth !== this.state.health) {
      const oldHealth = this.state.health;
      this.state.health = newHealth;
      this.notifyListeners();
      console.log(`📊 Health: ${oldHealth} → ${newHealth}`);
      
      // 重置計數器
      this.consecutiveHealthyHeartbeats = 0;
    }
  }

  /**
   * 獲取當前健康度狀態
   */
  getState(): ConnectionHealthState {
    return { ...this.state };
  }

  /**
   * 訂閱狀態變化
   */
  subscribe(listener: (state: ConnectionHealthState) => void): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  /**
   * 通知所有監聽器
   */
  private notifyListeners(): void {
    this.listeners.forEach((listener) => listener(this.state));
  }

  /**
   * 啟動健康檢查（每秒）
   */
  private startHealthCheck(): void {
    this.checkInterval = setInterval(() => {
      this.updateHealth();
    }, 1000);
  }

  /**
   * 停止健康檢查
   */
  destroy(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
    this.listeners = [];
  }
}
