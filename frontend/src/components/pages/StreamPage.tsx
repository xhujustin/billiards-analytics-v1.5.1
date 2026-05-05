import React, { useEffect, useState } from 'react';
import { ConnectionHealth, type ConnectionHealthState, type MetadataUpdatePayload } from '../../sdk/types';
import './StreamPage.css';

interface StreamPageProps {
  burninUrl: string;
  isAnalyzing: boolean;
  health: ConnectionHealthState | null;
  metadata: MetadataUpdatePayload | null;
  isConnected: boolean;
  coachPanel?: React.ReactNode;
}

export const StreamPage: React.FC<StreamPageProps> = ({
  burninUrl,
  isAnalyzing,
  health,
  metadata,
  isConnected,
  coachPanel,
}) => {
  const [quality, setQuality] = useState<'low' | 'med' | 'high'>(() => {
    const saved = localStorage.getItem('stream-quality');
    return saved === 'low' || saved === 'med' || saved === 'high' ? saved : 'med';
  });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [isStreamLoading, setIsStreamLoading] = useState(false);
  const [imgRef, setImgRef] = useState<HTMLImageElement | null>(null);
  const [loadingTimeoutRef, setLoadingTimeoutRef] = useState<NodeJS.Timeout | null>(null);
  const [retryTimeoutRef, setRetryTimeoutRef] = useState<NodeJS.Timeout | null>(null);

  const routeCount = metadata?.multi_plan?.routes?.length || 0;

  const getHealthColor = () => {
    if (!health) return '#8a8a8a';
    if (health.health === ConnectionHealth.HEALTHY) return '#22c55e';
    if (health.health === ConnectionHealth.DEGRADED) return '#eab308';
    if (health.health === ConnectionHealth.NO_SIGNAL) return '#f97316';
    if (health.health === ConnectionHealth.STALE) return '#ef4444';
    return '#8a8a8a';
  };

  const getHealthText = () => health?.health || 'INITIALIZING';
  const getPipelineState = () => health?.pipelineState || 'INITIALIZING';

  const clearAllTimers = () => {
    if (loadingTimeoutRef) {
      clearTimeout(loadingTimeoutRef);
      setLoadingTimeoutRef(null);
    }
    if (retryTimeoutRef) {
      clearTimeout(retryTimeoutRef);
      setRetryTimeoutRef(null);
    }
  };

  const getCurrentBurninUrl = () => {
    if (!burninUrl) return '';

    try {
      const url = new URL(burninUrl, window.location.origin);
      url.searchParams.set('quality', quality);
      url.searchParams.set('_t', streamKey.toString());
      return url.toString();
    } catch {
      const separator = burninUrl.includes('?') ? '&' : '?';
      return `${burninUrl}${separator}quality=${quality}&_t=${streamKey}`;
    }
  };

  const handleQualityChange = (newQuality: 'low' | 'med' | 'high') => {
    if (newQuality === quality) return;

    clearAllTimers();
    if (imgRef) {
      imgRef.src = '';
      imgRef.onload = null;
      imgRef.onerror = null;
    }

    setIsStreamLoading(true);
    setQuality(newQuality);
    localStorage.setItem('stream-quality', newQuality);

    setTimeout(() => setStreamKey((prev) => prev + 1), 200);
    const timeout = setTimeout(() => {
      setIsStreamLoading(false);
      setLoadingTimeoutRef(null);
    }, 5000);
    setLoadingTimeoutRef(timeout);
  };

  const handleFullscreen = () => {
    const stage = document.querySelector('.stream-video-frame');
    if (!stage) return;

    if (!isFullscreen && stage.requestFullscreen) {
      stage.requestFullscreen();
      setIsFullscreen(true);
    } else if (isFullscreen && document.exitFullscreen) {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    return () => {
      clearAllTimers();
      if (imgRef) {
        imgRef.src = '';
        imgRef.onload = null;
        imgRef.onerror = null;
      }
    };
  }, [imgRef]);

  return (
    <div className={`stream-page ${coachPanel ? 'with-coach' : 'without-coach'}`}>
      {coachPanel && (
        <aside className="stream-left-coach-area">
          <div className="stream-chat-body">{coachPanel}</div>
        </aside>
      )}

      <div className="stream-content-column">
        <div className="stream-page-header">
          <h2>即時影像</h2>
          <p>球桌影像、辨識狀態與系統健康度集中顯示在這個工作區。</p>
        </div>

        <section className="stream-video-card">
          <div className="stream-video-frame">
            {isStreamLoading && <div className="stream-loading-overlay">載入串流中...</div>}
            {burninUrl ? (
              <img
                key={`stream-${quality}-${streamKey}`}
                ref={(el) => setImgRef(el)}
                src={getCurrentBurninUrl()}
                alt="撞球即時影像"
                className="stream-video"
                style={{ opacity: isStreamLoading ? 0.3 : 1 }}
                onError={(event) => {
                  const target = event.target as HTMLImageElement;
                  if (loadingTimeoutRef) {
                    clearTimeout(loadingTimeoutRef);
                    setLoadingTimeoutRef(null);
                  }

                  const retries = parseInt(target.dataset.retryCount || '0', 10);
                  if (retries >= 3) {
                    setIsStreamLoading(false);
                    target.style.display = 'none';
                    return;
                  }

                  target.dataset.retryCount = (retries + 1).toString();
                  const retryTimeout = setTimeout(() => {
                    target.src = `${getCurrentBurninUrl()}&retry=${Date.now()}`;
                    setRetryTimeoutRef(null);
                  }, 2000);
                  setRetryTimeoutRef(retryTimeout);
                }}
                onLoad={(event) => {
                  const target = event.target as HTMLImageElement;
                  target.dataset.retryCount = '0';
                  target.style.display = 'block';
                  clearAllTimers();
                  setIsStreamLoading(false);
                }}
              />
            ) : (
              <div className="stream-placeholder">等待串流...</div>
            )}
          </div>

          <div className="stream-controls">
            <div className="quality-control">
              <span className="control-label">畫質</span>
              <button className={`quality-btn ${quality === 'low' ? 'active' : ''}`} onClick={() => handleQualityChange('low')} type="button">
                低
              </button>
              <button className={`quality-btn ${quality === 'med' ? 'active' : ''}`} onClick={() => handleQualityChange('med')} type="button">
                中
              </button>
              <button className={`quality-btn ${quality === 'high' ? 'active' : ''}`} onClick={() => handleQualityChange('high')} type="button">
                高
              </button>
            </div>

            <button className="fullscreen-btn" onClick={handleFullscreen} type="button">
              全螢幕
            </button>
          </div>
        </section>

        <section className="status-cards" aria-label="系統狀態">
          <div className="status-card">
            <h3>YOLO 辨識狀態</h3>
            <div className="status-content">
              <div className="status-row">
                <span>狀態</span>
                <strong className={isAnalyzing ? 'active' : 'inactive'}>{isAnalyzing ? '啟用' : '停用'}</strong>
              </div>
              <div className="status-row">
                <span>追蹤</span>
                <strong>{metadata?.tracking_state || 'idle'}</strong>
              </div>
              <div className="status-row">
                <span>偵測球數</span>
                <strong>{metadata?.detected_count || 0}</strong>
              </div>
              <div className="status-row">
                <span>更新率</span>
                <strong>{metadata?.rate_hz || 0} Hz</strong>
              </div>
              <div className="status-row">
                <span>路徑數</span>
                <strong>{routeCount}</strong>
              </div>
            </div>
          </div>

          <div className="status-card">
            <h3>系統健康度</h3>
            <div className="status-content">
              <div className="status-row">
                <span>WebSocket</span>
                <strong style={{ color: isConnected ? '#22c55e' : '#ef4444' }}>
                  {isConnected ? '已連線' : '未連線'}
                </strong>
              </div>
              <div className="status-row">
                <span>Health</span>
                <strong style={{ color: getHealthColor() }}>{getHealthText()}</strong>
              </div>
              <div className="status-row">
                <span>FPS</span>
                <strong>{health?.fpsEwma.toFixed(1) || '0.0'}</strong>
              </div>
              <div className="status-row">
                <span>Pipeline</span>
                <strong>{getPipelineState()}</strong>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default StreamPage;
