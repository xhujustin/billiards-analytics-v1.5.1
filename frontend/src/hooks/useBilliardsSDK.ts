/**
 * React Hooks for Billiards Analytics SDK（v1.5）
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { BilliardsSDK } from '../sdk';
import { ConnectionHealth } from '../sdk/types';
import type {
  Session,
  Stream,
  MetadataUpdatePayload,
  ConnectionHealthState,
  SDKConfig,
} from '../sdk/types';

/**
 * 使用 Billiards SDK 的主 Hook
 */
export function useBilliardsSDK(config?: Partial<SDKConfig>) {
  const sdkRef = useRef<BilliardsSDK | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [health, setHealth] = useState<ConnectionHealthState | null>(null);
  const [metadata, setMetadata] = useState<MetadataUpdatePayload | null>(null);

  useEffect(() => {
    // 創建 SDK 實例
    const sdk = new BilliardsSDK(config);
    sdkRef.current = sdk;

    // 監聽連接狀態
    const unsubConnect = sdk.wsManager.onConnect(() => {
      setIsConnected(true);
    });

    const unsubDisconnect = sdk.wsManager.onDisconnect(() => {
      setIsConnected(false);
    });

    // 監聽健康度變化
    const unsubHealth = sdk.healthMachine.subscribe((state) => {
      setHealth(state);
    });

    // 監聽 metadata
    const unsubMetadata = sdk.metadataBuffer.subscribe((data) => {
      setMetadata(data);
    });

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubHealth();
      unsubMetadata();
      sdk.destroy();
    };
  }, []);

  const initialize = useCallback(async (streamId: string = 'camera1') => {
    if (!sdkRef.current) return;
    const newSession = await sdkRef.current.initialize(streamId);
    setSession(newSession);
    return newSession;
  }, []);

  const switchStream = useCallback(async (streamId: string) => {
    if (!sdkRef.current) return false;
    return await sdkRef.current.sessionManager.switchStream(streamId);
  }, []);

  return {
    sdk: sdkRef.current,
    session,
    isConnected,
    health,
    metadata,
    initialize,
    switchStream,
  };
}

/**
 * 連接健康度 Hook
 */
export function useConnectionHealth() {
  const [health] = useState<ConnectionHealth>(ConnectionHealth.DISCONNECTED);
  const [details] = useState<ConnectionHealthState | null>(null);

  return { health, details };
}

/**
 * Streams 列表 Hook
 */
export function useStreams(apiBaseUrl: string = 'http://localhost:8001') {
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${apiBaseUrl}/api/streams`)
      .then((res) => res.json())
      .then((data) => {
        setStreams(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiBaseUrl]);

  return { streams, loading, error };
}
