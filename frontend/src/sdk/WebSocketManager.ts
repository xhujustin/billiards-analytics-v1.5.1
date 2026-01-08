/**
 * WebSocket Manager（v1.5）
 * 實現 v1.5 協議：envelope、重連策略、heartbeat、版本協商
 */

import type { WSEnvelope, SDKConfig, ProtocolVersion, WSMessageType } from './types';

type MessageHandler = (envelope: WSEnvelope) => void;
type ConnectionHandler = () => void;

// v1.5 定案重連配置
export const DEFAULT_RECONNECT_CONFIG = {
  maxRetries: 5,
  baseDelay: 1000, // 1s (initialDelay)
  maxDelay: 30000, // 30s
  jitter: 0.2, // ±20%
};

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private wsUrl: string = '';
  private reconnectAttempts: number = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private connectionHandlers: ConnectionHandler[] = [];
  private disconnectionHandlers: ConnectionHandler[] = [];
  private reconnectConfig: SDKConfig['reconnectConfig'];
  private isIntentionallyClosed: boolean = false;
  private negotiatedVersion: ProtocolVersion = 1;
  private sessionId: string = '';
  private streamId: string = '';

  constructor(config?: Partial<SDKConfig['reconnectConfig']>) {
    this.reconnectConfig = {
      ...DEFAULT_RECONNECT_CONFIG,
      ...config,
    };
  }

  /**
   * 連接 WebSocket
   */
  connect(wsUrl: string, sessionId: string = '', streamId: string = ''): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }

    this.wsUrl = wsUrl;
    this.sessionId = sessionId;
    this.streamId = streamId;
    this.isIntentionallyClosed = false;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('✅ WebSocket connected');
        this.reconnectAttempts = 0;
        
        // 發送 protocol.hello（版本協商）
        this.sendProtocolHello();
        
        this.startClientHeartbeat();
        this.connectionHandlers.forEach((handler) => handler());
      };

      this.ws.onmessage = (event) => {
        try {
          const envelope: WSEnvelope = JSON.parse(event.data);
          this.handleMessage(envelope);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
      };

      this.ws.onclose = (event) => {
        console.log(`👋 WebSocket closed: code=${event.code}, reason=${event.reason}`);
        this.stopClientHeartbeat();
        this.disconnectionHandlers.forEach((handler) => handler());

        // Kick-Old 情況（4001）不重連
        if (event.code === 4001) {
          console.warn('⛔ Connection kicked by server, not reconnecting');
          this.isIntentionallyClosed = true;
          return;
        }

        // 自動重連
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * 斷開連接
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    this.stopClientHeartbeat();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  /**
   * 發送消息
   */
  send(type: WSMessageType, payload: any, sessionId?: string, streamId?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot send message');
      return;
    }

    const envelope: WSEnvelope = {
      v: this.negotiatedVersion,
      type,
      ts: Date.now(),
      session_id: sessionId || this.sessionId,
      stream_id: streamId || this.streamId,
      payload,
    };

    this.ws.send(JSON.stringify(envelope));
  }

  /**
   * 發送 protocol.hello（版本協商）
   */
  private sendProtocolHello(): void {
    this.send('protocol.hello', {
      supported_versions: [1], // 目前僅支援 v1
    });
  }

  /**
   * 訂閱消息類型
   */
  on(type: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type)!.push(handler);

    // 返回取消訂閱函數
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  /**
   * 訂閱連接事件
   */
  onConnect(handler: ConnectionHandler): () => void {
    this.connectionHandlers.push(handler);
    return () => {
      const index = this.connectionHandlers.indexOf(handler);
      if (index > -1) {
        this.connectionHandlers.splice(index, 1);
      }
    };
  }

  /**
   * 訂閱斷開事件
   */
  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectionHandlers.push(handler);
    return () => {
      const index = this.disconnectionHandlers.indexOf(handler);
      if (index > -1) {
        this.disconnectionHandlers.splice(index, 1);
      }
    };
  }

  /**
   * 獲取連接狀態
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * 處理收到的消息
   */
  private handleMessage(envelope: WSEnvelope): void {
    const handlers = this.messageHandlers.get(envelope.type);
    if (handlers) {
      handlers.forEach((handler) => handler(envelope));
    }

    // 通配符處理器
    const allHandlers = this.messageHandlers.get('*');
    if (allHandlers) {
      allHandlers.forEach((handler) => handler(envelope));
    }
  }

  /**
   * 調度重連
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.reconnectConfig.maxRetries) {
      console.error('⛔ Max reconnect attempts reached');
      return;
    }

    // Exponential backoff: min(maxDelay, baseDelay * 2^attempt)
    const baseDelay = this.reconnectConfig.baseDelay * Math.pow(2, this.reconnectAttempts);
    const delay = Math.min(baseDelay, this.reconnectConfig.maxDelay);

    // 添加 jitter（±20% 隨機抖動，避免雷擊式重連）
    const jitter = delay * this.reconnectConfig.jitter * (Math.random() * 2 - 1);
    const finalDelay = Math.max(0, delay + jitter);

    console.log(
      `🔄 Reconnecting in ${Math.round(finalDelay / 1000)}s (attempt ${
        this.reconnectAttempts + 1
      }/${this.reconnectConfig.maxRetries})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect(this.wsUrl, this.sessionId, this.streamId);
    }, finalDelay);
  }

  /**
   * 啟動客戶端 heartbeat（每 5 秒）
   */
  private startClientHeartbeat(): void {
    this.stopClientHeartbeat();

    this.heartbeatTimer = setInterval(() => {
      this.send('client.heartbeat', {
        ts_client: Date.now(),
      });
    }, 5000);
  }

  /**
   * 停止客戶端 heartbeat
   */
  private stopClientHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * 銷毀管理器
   */
  destroy(): void {
    this.disconnect();
    this.messageHandlers.clear();
    this.connectionHandlers = [];
    this.disconnectionHandlers = [];
  }
}
