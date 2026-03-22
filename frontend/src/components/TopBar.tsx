/**
 * TopBar Component - 頂部導航欄
 * 包含 Logo、標題、YOLO 控制按鈕和即時效能指標
 */

import React, { useState, useEffect, useRef } from 'react';
import './TopBar.css';

interface TopBarProps {
  isAnalyzing: boolean;
  onToggleAnalysis: () => Promise<void>;
}

interface PerformanceStats {
  current_fps: number;
  avg_latency_ms: number;
  stream_active: boolean;
  is_analyzing: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({ isAnalyzing, onToggleAnalysis }) => {
  const [isToggling, setIsToggling] = useState(false);
  const [perfStats, setPerfStats] = useState<PerformanceStats | null>(null);
  const isFetchingRef = useRef(false);

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      await onToggleAnalysis();
    } finally {
      setIsToggling(false);
    }
  };

  // 定期獲取效能統計：僅在頁面可見時輪詢，避免背景請求堆疊
  useEffect(() => {
    let timer: number | null = null;
    let disposed = false;

    const fetchPerfStats = async () => {
      if (disposed || document.hidden || isFetchingRef.current) {
        return;
      }

      isFetchingRef.current = true;
      try {
        const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';
        const response = await fetch(`${apiBaseUrl}/api/performance/stats`);
        if (response.ok) {
          const data = await response.json();
          setPerfStats(data);
        }
      } catch (error) {
        // 靜默失敗,不影響主功能
        console.debug('Performance stats fetch failed:', error);
      } finally {
        isFetchingRef.current = false;
      }
    };

    const scheduleNext = (delayMs: number) => {
      if (disposed) return;
      timer = window.setTimeout(async () => {
        await fetchPerfStats();
        scheduleNext(document.hidden ? 5000 : 2000);
      }, delayMs);
    };

    const handleVisibilityChange = () => {
      if (disposed) return;
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      scheduleNext(document.hidden ? 5000 : 200);
    };

    fetchPerfStats();
    scheduleNext(2000);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      disposed = true;
      if (timer !== null) {
        clearTimeout(timer);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <div className="top-bar">
      <div className="top-bar-left">
        <div className="logo">NCUT </div>
        <h1 className="title">撞球分析系統 v1.5.1</h1>
      </div>

      <div className="top-bar-center">
        {perfStats && (
          <div className="performance-stats">
            <div className="perf-stat">
              <span className="perf-label">FPS:</span>
              <span className="perf-value fps-value">
                {perfStats.current_fps.toFixed(1)}
              </span>
            </div>
            <div className="perf-stat">
              <span className="perf-label">延遲:</span>
              <span className="perf-value latency-value">
                {perfStats.avg_latency_ms.toFixed(0)}ms
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="top-bar-right">
        <button
          className="btn btn-start"
          onClick={handleToggle}
          disabled={isToggling || isAnalyzing}
        >
          {isToggling && !isAnalyzing ? ' 啟動中...' : '🟢 啟動辨識'}
        </button>
        <button
          className="btn btn-stop"
          onClick={handleToggle}
          disabled={isToggling || !isAnalyzing}
        >
          {isToggling && isAnalyzing ? ' 停止中...' : '🔴 停止辨識'}
        </button>
      </div>
    </div>
  );
};

export default TopBar;
