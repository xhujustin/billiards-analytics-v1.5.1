/**
 * StreamPage Component - 即時影像頁面
 * 顯示 burn-in 串流和狀態卡片
 */

import React, { useState, useEffect } from 'react';
import { ConnectionHealth, type ConnectionHealthState, type MetadataUpdatePayload } from '../../sdk/types';
import './StreamPage.css';

interface StreamPageProps {
  burninUrl: string;
  isAnalyzing: boolean;
  health: ConnectionHealthState | null;
  metadata: MetadataUpdatePayload | null;
  isConnected: boolean;
}

export const StreamPage: React.FC<StreamPageProps> = ({
  burninUrl,
  isAnalyzing,
  health,
  metadata,
  isConnected,
}) => {
  const [plannerView, setPlannerView] = useState<'best' | 'topn' | 'coach'>('best');
  // 從 localStorage 讀取上次選擇的畫質，預設為 'med'
  const [quality, setQuality] = useState<'low' | 'med' | 'high'>(() => {
    const saved = localStorage.getItem('stream-quality');
    return (saved === 'low' || saved === 'med' || saved === 'high') ? saved : 'med';
  });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [streamKey, setStreamKey] = useState(0); // 用於強制重新載入圖片
  const [isStreamLoading, setIsStreamLoading] = useState(false); // 串流載入狀態
  const [loadingTimeoutRef, setLoadingTimeoutRef] = useState<NodeJS.Timeout | null>(null); // 載入超時計時器
  const [retryTimeoutRef, setRetryTimeoutRef] = useState<NodeJS.Timeout | null>(null); // 重試計時器
  const [imgRef, setImgRef] = useState<HTMLImageElement | null>(null); // 圖片元素引用，用於強制中斷連接

  const getHealthColor = () => {
    if (!health) return '#64748b';

    switch (health.health) {
      case ConnectionHealth.HEALTHY:
        return '#22c55e';
      case ConnectionHealth.DEGRADED:
        return '#eab308';
      case ConnectionHealth.NO_SIGNAL:
        return '#f97316';
      case ConnectionHealth.STALE:
        return '#ef4444';
      case ConnectionHealth.DISCONNECTED:
        return '#64748b';
      default:
        return '#64748b';
    }
  };

  const getHealthText = () => {
    if (!health) return '初始化中...';
    return health.health;
  };

  const getPipelineState = () => {
    if (!health) return 'INITIALIZING';
    return health.pipelineState;
  };

  const bestRoute = metadata?.multi_plan?.best_route;
  const routeCount = metadata?.multi_plan?.routes?.length || 0;

  const handleFullscreen = () => {
    const videoContainer = document.querySelector('.stream-video-container');
    if (!videoContainer) return;

    if (!isFullscreen) {
      if (videoContainer.requestFullscreen) {
        videoContainer.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  };

  const getCurrentBurninUrl = () => {
    if (!burninUrl) return '';
    
    // 解析原始 URL 並更新 quality 參數
    try {
      const url = new URL(burninUrl, window.location.origin);
      url.searchParams.set('quality', quality);
      // 添加時間戳防止緩存（僅在切換畫質時）
      url.searchParams.set('_t', streamKey.toString());
      return url.pathname + url.search;
    } catch (e) {
      // 如果 burninUrl 已經是完整 URL，直接使用
      const separator = burninUrl.includes('?') ? '&' : '?';
      return `${burninUrl}${separator}quality=${quality}&_t=${streamKey}`;
    }
  };

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

  const handleQualityChange = (newQuality: 'low' | 'med' | 'high') => {
    // 如果與當前畫質相同，忽略
    if (newQuality === quality) {
      console.log(`🎨 Quality already set to ${quality}, skipping`);
      return;
    }

    console.log(`🎨 Quality change requested: ${quality} → ${newQuality}`);

    // 清除所有現有計時器，防止狀態衝突
    clearAllTimers();

    // 🔑 關鍵修復：徹底關閉舊連接，防止連接池耗盡
    if (imgRef) {
      console.log('🔌 Force closing current stream connection');
      // 步驟1: 清空src立即中斷HTTP連接
      imgRef.src = '';
      // 步驟2: 移除事件監聽器，防止干擾
      imgRef.onload = null;
      imgRef.onerror = null;
      // 不要手動從DOM移除，讓React通過key變化來管理
    }

    // 強制重置載入狀態
    setIsStreamLoading(true);
    setQuality(newQuality);

    // 保存到 localStorage
    localStorage.setItem('stream-quality', newQuality);

    // 延遲200ms確保瀏覽器完全釋放舊連接，然後重建img元素
    setTimeout(() => {
      setStreamKey(prev => prev + 1);
    }, 200);

    // 設置最大載入超時（5秒）
    const timeout = setTimeout(() => {
      console.warn('⚠️ Stream loading timeout (5s), forcing reset');
      setIsStreamLoading(false);
      setLoadingTimeoutRef(null);
    }, 5000);
    setLoadingTimeoutRef(timeout);
  };

  // 監控畫質變化，輸出調試信息
  useEffect(() => {
    const url = getCurrentBurninUrl();
    console.log(`🎨 Quality state: ${quality}, streamKey: ${streamKey}`);
    console.log(`📺 Burnin URL: ${url}`);
  }, [quality, streamKey]);

  // Cleanup: 組件卸載時清除所有計時器和連接
  useEffect(() => {
    return () => {
      console.log('🧹 StreamPage cleanup: clearing all resources');
      clearAllTimers();
      
      // 組件卸載時徹底關閉連接
      if (imgRef) {
        imgRef.src = '';
        imgRef.onload = null;
        imgRef.onerror = null;
      }
    };
  }, [imgRef]);

  // 定期檢查連接健康度（每30秒）
  useEffect(() => {
    const healthCheckInterval = setInterval(() => {
      if (imgRef && imgRef.src) {
        const url = new URL(imgRef.src, window.location.origin);
        console.log(`💓 Connection health check: ${url.pathname}, quality=${quality}`);
      }
    }, 30000);

    return () => {
      clearInterval(healthCheckInterval);
    };
  }, [imgRef, quality]);

  return (
    <div className="stream-page">
      <h2 className="page-title"> 即時影像</h2>

      {/* 影像區域 */}
      <div className="stream-video-section card">
        <div className="stream-video-container" style={{ position: 'relative' }}>
          {isStreamLoading && (
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 10,
              color: '#22c55e',
              fontSize: '16px',
              fontWeight: 'bold',
              background: 'rgba(0,0,0,0.7)',
              padding: '10px 20px',
              borderRadius: '8px'
            }}>
               切換畫質中...
            </div>
          )}
          {burninUrl ? (
            <img
              key={`stream-${quality}-${streamKey}`}
              ref={(el) => setImgRef(el)} // 保存圖片元素引用
              src={getCurrentBurninUrl()}
              alt="Burn-in Stream"
              className="stream-video"
              style={{ opacity: isStreamLoading ? 0.3 : 1, transition: 'opacity 0.3s' }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                console.error('❌ Stream load error');

                // 清除載入計時器（但不清除重試計時器）
                if (loadingTimeoutRef) {
                  clearTimeout(loadingTimeoutRef);
                  setLoadingTimeoutRef(null);
                }

                // 重試邏輯
                const retries = parseInt(target.dataset.retryCount || '0', 10);
                if (retries >= 3) {
                  console.error('⚠️ MJPEG stream failed after 3 retries, resetting state');
                  setIsStreamLoading(false);
                  target.style.display = 'none';
                  return;
                }

                target.dataset.retryCount = (retries + 1).toString();
                console.log(`🔄 Retrying stream load (${retries + 1}/3)...`);

                // 使用獨立的重試計時器
                const retryTimeout = setTimeout(() => {
                  target.src = getCurrentBurninUrl() + '&retry=' + Date.now();
                  setRetryTimeoutRef(null);
                }, 2000);
                setRetryTimeoutRef(retryTimeout);
              }}
              onLoad={(e) => {
                const target = e.target as HTMLImageElement;
                target.dataset.retryCount = '0';
                target.style.display = 'block';

                // 清除所有計時器
                clearAllTimers();

                // 重置載入狀態
                setIsStreamLoading(false);
                console.log('✅ Stream loaded successfully');
              }}
            />
          ) : (
            <div className="stream-placeholder">
              等待串流...
            </div>
          )}
        </div>

        <div className="stream-controls">
          <div className="quality-control">
            <span className="control-label">畫質:</span>
            <button
              className={`quality-btn ${quality === 'low' ? 'active' : ''}`}
              onClick={() => handleQualityChange('low')}
            >
              {isStreamLoading && quality === 'low' ? '。' : '低'}
            </button>
            <button
              className={`quality-btn ${quality === 'med' ? 'active' : ''}`}
              onClick={() => handleQualityChange('med')}
            >
              {isStreamLoading && quality === 'med' ? '。' : '中'}
            </button>
            <button
              className={`quality-btn ${quality === 'high' ? 'active' : ''}`}
              onClick={() => handleQualityChange('high')}
            >
              {isStreamLoading && quality === 'high' ? '。' : '高'}
            </button>
          </div>

          <button className="fullscreen-btn" onClick={handleFullscreen}>
            ⛶ 全螢幕
          </button>
        </div>
      </div>

      {/* 狀態卡片區域 */}
      <div className="status-cards">
        {/* YOLO 辨識狀態 */}
        <div className="card status-card">
          <h3 className="card-title"> YOLO 辨識狀態</h3>
          <div className="status-content">
            <div className="status-row">
              <span className="status-label">辨識狀態:</span>
              <span className={`status-value ${isAnalyzing ? 'active' : 'inactive'}`}>
                {isAnalyzing ? '● 已啟用' : '○ 已停用'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">追蹤狀態:</span>
              <span className="status-value">
                {metadata?.tracking_state || 'idle'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">檢測數量:</span>
              <span className="status-value">
                {metadata?.detected_count || 0} 個物件
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">更新頻率:</span>
              <span className="status-value">
                {metadata?.rate_hz || 0} Hz
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">規劃候選:</span>
              <span className="status-value">
                {routeCount} 條
              </span>
            </div>
          </div>
        </div>

        {/* 系統連接狀態 */}
        <div className="card status-card">
          <h3 className="card-title"> 系統連接狀態</h3>
          <div className="status-content">
            <div className="status-row">
              <span className="status-label">WebSocket:</span>
              <span className="status-value" style={{ color: isConnected ? '#22c55e' : '#ef4444' }}>
                {isConnected ? '🟢 已連接' : '🔴 未連接'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">Health:</span>
              <span className="status-value" style={{ color: getHealthColor() }}>
                {getHealthText()}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">FPS:</span>
              <span className="status-value">
                 {health?.fpsEwma.toFixed(1) || '0.0'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">Pipeline:</span>
              <span className="status-value">
                 {getPipelineState()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {metadata?.multi_plan && (
        <div className="card planner-card">
          <div className="planner-card-header">
            <h3 className="card-title">多球路徑規劃</h3>
            <div className="planner-tabs" role="tablist" aria-label="多球路徑規劃視圖">
              <button
                className={`planner-tab ${plannerView === 'best' ? 'active' : ''}`}
                onClick={() => setPlannerView('best')}
              >
                最佳
              </button>
              <button
                className={`planner-tab ${plannerView === 'topn' ? 'active' : ''}`}
                onClick={() => setPlannerView('topn')}
              >
                Top-N
              </button>
              <button
                className={`planner-tab ${plannerView === 'coach' ? 'active' : ''}`}
                onClick={() => setPlannerView('coach')}
              >
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
                  <strong>{route.route_type}</strong>
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
        </div>
      )}
    </div>
  );
};

export default StreamPage;
