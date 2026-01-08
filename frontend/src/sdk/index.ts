/**
 * Billiards Analytics SDK（v1.5）
 * 統一對外接口
 */

export * from './types';
export { SessionManager } from './SessionManager';
export { WebSocketManager } from './WebSocketManager';
export { ConnectionHealthMachine } from './ConnectionHealthMachine';
export { MetadataBuffer } from './MetadataBuffer';

import { SessionManager } from './SessionManager';
import { WebSocketManager } from './WebSocketManager';
import { ConnectionHealthMachine } from './ConnectionHealthMachine';
import { MetadataBuffer } from './MetadataBuffer';
import type { SDKConfig, Session, Stream, Config } from './types';

/**
 * SDK 主類
 */
export class BilliardsSDK {
  public sessionManager: SessionManager;
  public wsManager: WebSocketManager;
  public healthMachine: ConnectionHealthMachine;
  public metadataBuffer: MetadataBuffer;
  private config: SDKConfig;

  constructor(config: Partial<SDKConfig> = {}) {
    this.config = {
      apiBaseUrl: config.apiBaseUrl ?? 'http://localhost:8001',
      wsBaseUrl: config.wsBaseUrl ?? 'ws://localhost:8001',
      reconnectConfig: {
        maxRetries: 5,
        baseDelay: 1000,
        maxDelay: 30000,
        jitter: 0.2,
        ...config.reconnectConfig,
      },
      sessionConfig: {
        autoRenew: true,
        renewWindowRatio: 0.2,
        minRenewWindow: 300000,
        ...config.sessionConfig,
      },
      metadataConfig: {
        bufferSize: 100,
        throttleMs: 1000,
        samplingStrategy: 'latest',
        ...config.metadataConfig,
      },
    };

    this.sessionManager = new SessionManager(
      this.config.apiBaseUrl,
      this.config.sessionConfig
    );

    this.wsManager = new WebSocketManager(this.config.reconnectConfig);

    this.healthMachine = new ConnectionHealthMachine();

    this.metadataBuffer = new MetadataBuffer(this.config.metadataConfig);

    this.setupEventHandlers();
  }

  /**
   * 初始化連接
   */
  async initialize(streamId: string = 'camera1'): Promise<Session> {
    // 嘗試恢復 session
    let session = await this.sessionManager.restoreSession();

    // 若無法恢復，創建新 session
    if (!session) {
      session = await this.sessionManager.createSession(streamId);
    }

    // 連接 WebSocket（傳遞 session_id 和 stream_id）
    const wsUrl = `${this.config.wsBaseUrl}${session.ws_url}`;
    this.wsManager.connect(wsUrl, session.session_id, session.stream_id);

    return session;
  }

  /**
   * 獲取可用 streams
   */
  async getStreams(): Promise<Stream[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/api/streams`);
    if (!response.ok) {
      throw new Error('Failed to fetch streams');
    }
    return response.json();
  }

  /**
   * 獲取配置
   */
  async getConfig(): Promise<Config> {
    const response = await fetch(`${this.config.apiBaseUrl}/api/config`);
    if (!response.ok) {
      throw new Error('Failed to fetch config');
    }
    return response.json();
  }

  /**
   * 設置事件處理器
   */
  private setupEventHandlers(): void {
    // WebSocket 連接狀態
    this.wsManager.onConnect(() => {
      this.healthMachine.updateWSConnection(true);
    });

    this.wsManager.onDisconnect(() => {
      this.healthMachine.updateWSConnection(false);
    });

    // Protocol Welcome（版本協商完成）
    this.wsManager.on('protocol.welcome', (envelope) => {
      console.log('🤝 Protocol negotiated:', envelope.payload);
    });

    // Heartbeat 處理
    this.wsManager.on('heartbeat', (envelope) => {
      this.healthMachine.updateHeartbeat(envelope.ts, envelope.payload);
    });

    // Metadata 處理
    this.wsManager.on('metadata.update', (envelope) => {
      this.metadataBuffer.push(envelope.payload);
    });

    // Session 被撤銷（Kick-Old）
    this.wsManager.on('session.revoked', (envelope) => {
      console.warn('⚠️ Session revoked:', envelope.payload);
      // 清除 localStorage 並觸發重新初始化
      localStorage.removeItem('billiards_session_id');
      localStorage.removeItem('billiards_session');
    });

    // Stream 變更（Failover）
    this.wsManager.on('stream.changed', async (envelope) => {
      console.log('🔀 Stream changed:', envelope.payload);
      // 發送 ACK
      this.wsManager.send('stream.changed.ack', { status: 'ok' });
      
      // 更新 session stream_id（若有）
      const session = this.sessionManager.getCurrentSession();
      if (session && envelope.payload.new_stream_id) {
        session.stream_id = envelope.payload.new_stream_id;
        session.burnin_url = envelope.payload.play_url;
        localStorage.setItem('billiards_session', JSON.stringify(session));
      }
    });

    // Command Error
    this.wsManager.on('cmd.error', (envelope) => {
      console.error('❌ Command error:', envelope.payload);
    });
  }

  /**
   * 銷毀 SDK
   */
  destroy(): void {
    this.wsManager.destroy();
    this.healthMachine.destroy();
    this.metadataBuffer.destroy();
    this.sessionManager.destroy();
  }
}
