/**
 * Metadata Buffer（v1.5）
 * 高頻 metadata 緩衝與節流處理
 */

import type { MetadataUpdatePayload, MetadataBufferItem } from './types';

export class MetadataBuffer {
  private buffer: MetadataBufferItem[] = [];
  private maxSize: number;
  private throttleMs: number;
  private samplingStrategy: 'latest' | 'average';
  private lastEmit: number = 0;
  private listeners: ((data: MetadataUpdatePayload) => void)[] = [];
  private emitInterval: NodeJS.Timeout | null = null;

  constructor(config: {
    maxSize?: number;
    throttleMs?: number;
    samplingStrategy?: 'latest' | 'average';
  } = {}) {
    this.maxSize = config.maxSize ?? 100;
    this.throttleMs = config.throttleMs ?? 1000; // 預設 1Hz
    this.samplingStrategy = config.samplingStrategy ?? 'latest';

    this.startEmitLoop();
  }

  /**
   * 添加 metadata 到 buffer
   */
  push(data: MetadataUpdatePayload): void {
    this.buffer.push({
      timestamp: Date.now(),
      data,
    });

    // 超過上限則移除最舊的
    if (this.buffer.length > this.maxSize) {
      this.buffer.shift();
    }
  }

  /**
   * 訂閱 throttled metadata
   */
  subscribe(listener: (data: MetadataUpdatePayload) => void): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  /**
   * 啟動定期發送循環
   */
  private startEmitLoop(): void {
    this.emitInterval = setInterval(() => {
      const now = Date.now();
      if (now - this.lastEmit >= this.throttleMs && this.buffer.length > 0) {
        const data = this.sample();
        if (data) {
          this.lastEmit = now;
          this.listeners.forEach((listener) => listener(data));
        }
      }
    }, this.throttleMs / 2); // 檢查頻率是節流間隔的一半
  }

  /**
   * 根據策略採樣數據
   */
  private sample(): MetadataUpdatePayload | null {
    if (this.buffer.length === 0) return null;

    if (this.samplingStrategy === 'latest') {
      // 取最新的
      const item = this.buffer[this.buffer.length - 1];
      this.buffer = []; // 清空 buffer
      return item.data;
    } else {
      // average 策略（簡化：僅取最新，實際可實現平均）
      const item = this.buffer[this.buffer.length - 1];
      this.buffer = [];
      return item.data;
    }
  }

  /**
   * 清空 buffer
   */
  clear(): void {
    this.buffer = [];
  }

  /**
   * 獲取 buffer 當前大小
   */
  size(): number {
    return this.buffer.length;
  }

  /**
   * 銷毀
   */
  destroy(): void {
    if (this.emitInterval) {
      clearInterval(this.emitInterval);
      this.emitInterval = null;
    }
    this.buffer = [];
    this.listeners = [];
  }
}
