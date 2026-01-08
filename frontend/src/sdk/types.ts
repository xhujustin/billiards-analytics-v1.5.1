/**
 * 撞球分析系統 TypeScript 型別定義（v1.5）
 * 對應協議契約的完整型別
 * 協議即型別 - 與後端 schema 1:1 對應
 */

// ============ Protocol Version ============

export type ProtocolVersion = 1;

export type WSMessageType =
  | 'heartbeat'
  | 'client.heartbeat'
  | 'metadata.update'
  | 'stream.changed'
  | 'stream.changed.ack'
  | 'session.revoked'
  | 'protocol.hello'
  | 'protocol.welcome'
  | 'cmd.ack'
  | 'cmd.error'
  | `cmd.${string}`;

// ============ Enums ============

export enum ConnectionHealth {
  DISCONNECTED = 'DISCONNECTED',
  STALE = 'STALE',
  NO_SIGNAL = 'NO_SIGNAL',
  DEGRADED = 'DEGRADED',
  HEALTHY = 'HEALTHY',
}

export enum PipelineState {
  RUNNING = 'RUNNING',
  RECONNECTING = 'RECONNECTING',
  NO_SIGNAL = 'NO_SIGNAL',
  ERROR = 'ERROR',
}

export enum StreamQuality {
  LOW = 'low',
  MED = 'med',
  HIGH = 'high',
}

export enum Role {
  VIEWER = 'viewer',
  OPERATOR = 'operator',
  DEVELOPER = 'developer',
  ADMIN = 'admin',
}

// ============ WebSocket Envelope ============

export interface WSEnvelope<T = any> {
  v: number;
  type: string;
  ts: number;
  session_id: string;
  stream_id: string;
  payload: T;
}

// ============ WebSocket Message Payloads ============

export interface HeartbeatPayload {
  alive: boolean;
  last_frame_ts: number;
  fps_ewma: number;
  pipeline_state: PipelineState;
}

export interface ClientHeartbeatPayload {
  ts_client: number;
}

// ============ Detection Types ============

export interface Detection {
  bbox: [number, number, number, number]; // x1, y1, x2, y2
  label: string;
  score: number; // 0..1
  track_id?: number;
}

export interface Keypoint {
  x: number;
  y: number;
  conf: number; // 0..1
  name?: string;
}

export interface MetadataUpdatePayload {
  frame_id: number;
  ts_backend: number;
  ts_capture?: number;
  img_w?: number;
  img_h?: number;
  detected_count: number;
  tracking_state: string;
  detections: Detection[];
  prediction?: any;
  ar_paths?: any[];
  bbox?: number[] | null;
  keypoints?: Keypoint[] | null;
  rate_hz?: number; // 實際推送頻率（Hz）
  events?: unknown[] | null; // reserved for P1+
}

export interface StreamChangedPayload {
  reason: string;
  play_url: string;
  new_stream_id?: string;
}

export interface StreamChangedAckPayload {
  status: string;
}

export interface SessionRevokedPayload {
  reason: string;
  message: string;
}

export interface CmdAckPayload {
  request_id: string;
  status: 'accepted' | 'applied';
  applied_state?: any;
}

export interface CmdErrorPayload {
  request_id: string;
  code:
    | 'ERR_INVALID_ARGUMENT'
    | 'ERR_PERMISSION_DENIED'
    | 'ERR_NO_SIGNAL'
    | 'ERR_CAMERA_BUSY'
    | 'ERR_CALIBRATION_FAILED'
    | 'ERR_SESSION_REPLACED'
    | 'ERR_TIMEOUT'
    | 'ERR_NETWORK'
    | 'ERR_STREAM_UNAVAILABLE'
    | 'ERR_INVALID_STATE'
    | 'ERR_RATE_LIMIT'
    | 'ERR_INTERNAL';
  message: string; // debug only, not for i18n
  details?: Record<string, unknown>;
}

export interface ProtocolHelloPayload {
  supported_versions: number[];
}

export interface ProtocolWelcomePayload {
  version: string;
  session_id: string;
  connection_id: string;
  features: string[];
  negotiated_version?: number;
}

// ============ REST API Types ============

export interface Stream {
  stream_id: string;
  name: string;
  type: 'usb' | 'rtsp' | 'file' | 'capture';
  available: boolean;
  resolution: string;
  fps: number;
  burnin_url: string;
  capabilities: StreamQuality[];
}

export interface StreamStatus {
  stream_id: string;
  alive: boolean;
  pipeline_state: PipelineState;
  last_frame_ts: number;
  fps_ewma: number;
  last_error: string | null;
}

export interface Session {
  session_id: string;
  stream_id: string;
  role: Role;
  permission_flags: string[];
  ws_url: string;
  burnin_url: string;
  expires_at: number;
}

export interface SessionRenewResponse {
  session_id: string;
  expires_at: number;
  status: string;
}

export interface Config {
  version: string;
  flags: {
    dev_ui: boolean;
    replay: boolean;
    multi_table: boolean;
  };
  limits: {
    max_sessions: number;
    session_ttl: number;
    metadata_rate_hz: number;
  };
  streams: {
    available_streams: string[];
    default_quality: StreamQuality;
  };
}

// ============ SDK Config ============

export interface SDKConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
  reconnectConfig: {
    maxRetries: number;
    baseDelay: number;
    maxDelay: number;
    jitter: number;
  };
  sessionConfig: {
    autoRenew: boolean;
    renewWindowRatio: number;
    minRenewWindow: number;
  };
  metadataConfig: {
    bufferSize: number;
    throttleMs: number;
    samplingStrategy: 'latest' | 'average';
  };
}

// ============ Connection Health ============

export interface ConnectionHealthState {
  health: ConnectionHealth;
  lastHeartbeat: number;
  lastFrameTs: number;
  wsConnected: boolean;
  pipelineState: PipelineState;
  fpsEwma: number;
}

// ============ Metadata Buffer ============

export interface MetadataBufferItem {
  timestamp: number;
  data: MetadataUpdatePayload;
}

// ============ Command Types ============

export interface Command {
  type: string;
  request_id: string;
  payload: any;
}

export interface CommandResult {
  success: boolean;
  data?: any;
  error?: string;
}

// ============ REST Error Format ============

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

// ============ Performance Metrics (P2) ============

export interface PerformanceMetrics {
  // WebSocket
  wsReconnectCount: number;
  wsMessageRate: number; // msg/s
  wsLatency?: number; // ms (optional)

  // MJPEG / Video
  videoFrameRate: number; // fps
  videoLoadTime?: number; // ms

  // Metadata
  metadataProcessTime?: number; // ms
  metadataDropRate: number; // 0..1

  // UI
  renderTime?: number; // ms
  memoryUsage?: number; // MB (best-effort)
}
