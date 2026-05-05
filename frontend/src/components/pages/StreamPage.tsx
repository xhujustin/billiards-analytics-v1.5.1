/**
 * StreamPage Component - 即時影像頁面
 * 顯示 burn-in 串流、AI coach、系統狀態與路徑規劃。
 */

import React, { useEffect, useRef, useState } from 'react';
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

type PlannerView = 'best' | 'topn' | 'coach';
type StreamQuality = 'low' | 'med' | 'high';

export const StreamPage: React.FC<StreamPageProps> = ({
  burninUrl,
  isAnalyzing,
  health,
  metadata,
  isConnected,
  coachPanel,
}) => {
  const [quality, setQuality] = useState<StreamQuality>(() => {
    const saved = localStorage.getItem('stream-quality');
    return saved === 'low' || saved === 'med' || saved === 'high' ? saved : 'med';
  });
  const [plannerView, setPlannerView] = useState<PlannerView>('best');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [isStreamLoading, setIsStreamLoading] = useState(false);
  const loadingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const bestRoute = metadata?.multi_plan?.best_route;
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
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  };

  const getCurrentBurninUrl = () => {
    if (!burninUrl) return '';

    try {
      const url = new URL(burninUrl, window.location.origin);
      url.searchParams.set('quality', quality);
      url.searchParams.set('client_id', 'stream-page-monitor');
      url.searchParams.set('_t', streamKey.toString());
      return url.toString();
    } catch {
      const separator = burninUrl.includes('?') ? '&' : '?';
      return `${burninUrl}${separator}quality=${quality}&client_id=stream-page-monitor&_t=${streamKey}`;
    }
  };

  const handleQualityChange = (newQuality: StreamQuality) => {
    if (newQuality === quality) return;

    clearAllTimers();
    if (imgRef.current) {
      imgRef.current.src = '';
      imgRef.current.onload = null;
      imgRef.current.onerror = null;
    }

    setIsStreamLoading(true);
    setQuality(newQuality);
    localStorage.setItem('stream-quality', newQuality);

    setTimeout(() => setStreamKey((prev) => prev + 1), 200);
    loadingTimeoutRef.current = setTimeout(() => {
      setIsStreamLoading(false);
      loadingTimeoutRef.current = null;
    }, 5000);
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
      if (imgRef.current) {
        imgRef.current.src = '';
        imgRef.current.onload = null;
        imgRef.current.onerror = null;
      }
    };
  }, []);

  useEffect(() => {
    const healthCheckInterval = setInterval(() => {
      if (imgRef.current?.src) {
        const url = new URL(imgRef.current.src, window.location.origin);
        console.log(`Connection health check: ${url.pathname}, quality=${quality}`);
      }
    }, 30000);

    return () => clearInterval(healthCheckInterval);
  }, [quality]);

  const retryStream = (target: HTMLImageElement) => {
    const retries = parseInt(target.dataset.retryCount || '0', 10);
    if (retries >= 3) {
      setIsStreamLoading(false);
      target.style.display = 'none';
      return;
    }

    target.dataset.retryCount = (retries + 1).toString();
    retryTimeoutRef.current = setTimeout(() => {
      const separator = getCurrentBurninUrl().includes('?') ? '&' : '?';
      target.src = `${getCurrentBurninUrl()}${separator}retry=${Date.now()}`;
      retryTimeoutRef.current = null;
    }, 2000);
  };

  const renderPlannerCard = () => {
    if (!metadata?.multi_plan) return null;

    return (
      <section className="planner-card">
        <div className="planner-card-header">
          <h3>多球路徑規劃</h3>
          <div className="planner-tabs" role="tablist" aria-label="多球路徑規劃視圖">
            <button className={`planner-tab ${plannerView === 'best' ? 'active' : ''}`} onClick={() => setPlannerView('best')} type="button">
              最佳
            </button>
            <button className={`planner-tab ${plannerView === 'topn' ? 'active' : ''}`} onClick={() => setPlannerView('topn')} type="button">
              Top-N
            </button>
            <button className={`planner-tab ${plannerView === 'coach' ? 'active' : ''}`} onClick={() => setPlannerView('coach')} type="button">
              教練
            </button>
          </div>
        </div>

        {plannerView === 'best' && (
          <div className="planner-content">
            {bestRoute ? (
              <>
                <div className="planner-best-grid">
                  <div>
                    <span className="planner-label">路線</span>
                    <strong>{bestRoute.route_type}</strong>
                  </div>
                  <div>
                    <span className="planner-label">目標球</span>
                    <strong>{bestRoute.target_ball_number ?? '-'}</strong>
                  </div>
                  <div>
                    <span className="planner-label">成功率</span>
                    <strong>{(bestRoute.success_prob * 100).toFixed(0)}%</strong>
                  </div>
                  <div>
                    <span className="planner-label">難度</span>
                    <strong>{bestRoute.difficulty}</strong>
                  </div>
                </div>
                <div className="planner-stroke">
                  <span>{bestRoute.stroke_hint.type}</span>
                  <span>{bestRoute.stroke_hint.power}</span>
                  <span>{bestRoute.stroke_hint.spin}</span>
                </div>
                <p className="planner-note">{bestRoute.stroke_hint.rationale}</p>
              </>
            ) : (
              <p className="planner-note">{metadata.multi_plan.error || '目前沒有可用路線。'}</p>
            )}
          </div>
        )}

        {plannerView === 'topn' && (
          <div className="planner-route-list">
            {metadata.multi_plan.routes.map((route, index) => (
              <div className="planner-route-row" key={route.id || index}>
                <span>#{index + 1}</span>
                <strong>{typeof route.metadata?.strategy_label === 'string' ? route.metadata.strategy_label : route.route_type}</strong>
                <span>Ball {route.target_ball_number ?? '-'}</span>
                <span>{(route.success_prob * 100).toFixed(0)}%</span>
                <span>難度 {route.difficulty}</span>
              </div>
            ))}
          </div>
        )}

        {plannerView === 'coach' && (
          <div className="planner-coach-notes">
            {(metadata.multi_plan.coach_notes?.length ? metadata.multi_plan.coach_notes : ['目前沒有教練提示。']).map((note, index) => (
              <p key={index}>{note}</p>
            ))}
          </div>
        )}
      </section>
    );
  };

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
                ref={imgRef}
                src={getCurrentBurninUrl()}
                alt="撞球即時影像"
                className="stream-video"
                style={{ opacity: isStreamLoading ? 0.3 : 1 }}
                onError={(event) => {
                  const target = event.currentTarget;
                  if (loadingTimeoutRef.current) {
                    clearTimeout(loadingTimeoutRef.current);
                    loadingTimeoutRef.current = null;
                  }
                  retryStream(target);
                }}
                onLoad={(event) => {
                  const target = event.currentTarget;
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

        {renderPlannerCard()}
      </div>
    </div>
  );
};

export default StreamPage;
