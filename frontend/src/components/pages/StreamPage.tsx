/**
 * StreamPage Component - 即時影像頁面
 * 顯示 burn-in 串流、AI coach、系統狀態與路徑規劃。
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ConnectionHealth, type ConnectionHealthState, type Detection, type MetadataUpdatePayload, type RouteCandidate } from '../../sdk/types';
import './StreamPage.css';

interface StreamPageProps {
  burninUrl: string;
  isAnalyzing: boolean;
  health: ConnectionHealthState | null;
  metadata: MetadataUpdatePayload | null;
  isConnected: boolean;
  isDevMode?: boolean;
  coachPanel?: React.ReactNode;
}

type PlannerView = 'best' | 'topn' | 'coach';
type StreamQuality = 'low' | 'med' | 'high';

interface YoloBoxInfo {
  id: string;
  label: string;
  confidence: number | null;
  number: number | null;
  color: string | null;
  x: number;
  y: number;
  w: number;
  h: number;
}

type SvgPoint = [number, number];

export const StreamPage: React.FC<StreamPageProps> = ({
  burninUrl,
  isAnalyzing,
  health,
  metadata,
  isConnected,
  isDevMode = false,
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
  const [streamImageSize, setStreamImageSize] = useState<{ width: number; height: number } | null>(null);
  const loadingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const bestRoute = metadata?.multi_plan?.best_route;
  const routeCount = metadata?.multi_plan?.routes?.length || 0;
  const yoloDebugJson = useMemo(() => {
    if (!metadata) return '尚未收到 YOLO metadata';

    return JSON.stringify(metadata, null, 2);
  }, [metadata]);
  const yoloBoxes = useMemo<YoloBoxInfo[]>(() => {
    return getOverlayDetections().flatMap((detection, index) => {
      const box = getYoloBoxInfo(detection, index);
      return box ? [box] : [];
    });
  }, [metadata]);
  const detectionPreview = yoloBoxes.slice(0, 12);

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

  function getYoloBoxInfo(detection: Detection, index: number): YoloBoxInfo | null {
    const confidence = detection.conf ?? detection.score ?? null;
    const label = detection.label || detection.color || `#${detection.number ?? index + 1}`;
    const number = typeof detection.number === 'number' ? detection.number : null;
    const color = detection.color || detection.label || null;

    if (detection.bbox && detection.bbox.length >= 4) {
      const [x1, y1, x2, y2] = detection.bbox;
      return {
        id: `${label}-${index}`,
        label,
        confidence,
        number,
        color,
        x: x1,
        y: y1,
        w: Math.max(0, x2 - x1),
        h: Math.max(0, y2 - y1),
      };
    }

    if (detection.x == null || detection.y == null || detection.w == null || detection.h == null) {
      return null;
    }

    return {
      id: `${label}-${index}`,
      label,
      confidence,
      number,
      color,
      x: detection.x,
      y: detection.y,
      w: detection.w,
      h: detection.h,
    };
  }

  function getOverlayDetections(): Detection[] {
    const detections = [...(metadata?.detections_view || metadata?.detections || [])];
    const whiteBall = metadata?.white_ball;
    if (Array.isArray(whiteBall) && whiteBall.length >= 4) {
      const [x, y, w, h] = whiteBall.map(Number);
      const hasWhite = detections.some((detection) => {
        const box = getYoloBoxInfo(detection, -1);
        if (!box) return false;
        const label = String(box.label || box.color || '').toLowerCase();
        const isWhite = box.number === 0 || label.includes('white');
        const cx = box.x + box.w / 2;
        const cy = box.y + box.h / 2;
        const wcx = x + w / 2;
        const wcy = y + h / 2;
        return isWhite && Math.hypot(cx - wcx, cy - wcy) <= Math.max(w, h, box.w, box.h) * 0.55;
      });
      if (!hasWhite) {
        detections.unshift({ x, y, w, h, label: 'white ball', color: 'White', number: 0 });
      }
    }
    return detections;
  }

  const isPoint = (value: unknown): value is SvgPoint => (
    Array.isArray(value)
    && value.length >= 2
    && Number.isFinite(Number(value[0]))
    && Number.isFinite(Number(value[1]))
  );

  const pointValue = (value: unknown): SvgPoint | null => {
    if (!isPoint(value)) return null;
    return [Number(value[0]), Number(value[1])];
  };

  const pathFromPoints = (points: unknown) => {
    if (!Array.isArray(points)) return '';
    const clean = points.map(pointValue).filter((point): point is SvgPoint => Boolean(point));
    if (clean.length < 2) return '';
    return clean.map((point) => `${point[0]},${point[1]}`).join(' ');
  };

  const ballStrokeColor = (box: YoloBoxInfo) => {
    const number = box.number;
    if (number === 0) return '#f8fafc';
    if (number === 8) return '#111827';

    const byNumber: Record<number, string> = {
      1: '#facc15',
      2: '#2563eb',
      3: '#dc2626',
      4: '#7c3aed',
      5: '#f97316',
      6: '#16a34a',
      7: '#92400e',
      9: '#facc15',
      10: '#2563eb',
      11: '#dc2626',
      12: '#7c3aed',
      13: '#f97316',
      14: '#16a34a',
      15: '#92400e',
    };
    if (typeof number === 'number' && byNumber[number]) return byNumber[number];

    const colorName = String(box.color || box.label || '').toLowerCase();
    if (colorName.includes('white')) return '#f8fafc';
    if (colorName.includes('black')) return '#111827';
    if (colorName.includes('yellow')) return '#facc15';
    if (colorName.includes('blue')) return '#2563eb';
    if (colorName.includes('red')) return '#dc2626';
    if (colorName.includes('purple')) return '#7c3aed';
    if (colorName.includes('orange')) return '#f97316';
    if (colorName.includes('green')) return '#16a34a';
    if (colorName.includes('brown')) return '#92400e';
    return '#22d3ee';
  };

  const ballLabel = (box: YoloBoxInfo) => {
    if (box.number != null) return String(box.number);
    const colorName = String(box.color || box.label || '').toLowerCase();
    if (colorName.includes('white')) return 'W';
    if (colorName.includes('black')) return '8';
    return '';
  };

  const renderMetadataOverlay = () => {
    const overlayWidth = metadata?.img_w || streamImageSize?.width;
    const overlayHeight = metadata?.img_h || streamImageSize?.height;
    if (!metadata || !overlayWidth || !overlayHeight) return null;

    const route = metadata.multi_plan?.best_route;
    const routeSegments = route?.route_segments || [];
    const positionPlay = route?.position_play;
    const cueAfter = positionPlay?.cue_ball_after_contact;
    const targetZone = cueAfter?.target_zone;
    const avoidZones = (cueAfter?.avoid_zones || [])
      .filter((zone) => zone.type !== 'pocket_scratch')
      .slice(0, 3);
    const nextBallCenter = pointValue(positionPlay?.next_ball?.center);
    const cueLaserLine = Array.isArray(metadata.cue_laser_line) ? metadata.cue_laser_line : [];
    const cueBox = Array.isArray(metadata.cue) && metadata.cue.length >= 4 ? metadata.cue : null;

    const segmentClass = (type: string) => {
      if (type === 'cue_to_contact' || type === 'cue_laser') return 'cue';
      if (type === 'cue_after_contact') return 'cue-after';
      if (type === 'combo_transfer') return 'combo';
      return 'object';
    };

    const hasOverlay =
      yoloBoxes.length > 0
      || routeSegments.length > 0
      || targetZone
      || avoidZones.length > 0
      || cueLaserLine.length >= 2
      || cueBox;
    if (!hasOverlay) return null;

    return (
      <svg
        className="stream-metadata-overlay"
        viewBox={`0 0 ${overlayWidth} ${overlayHeight}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="metadata 前端疊圖"
      >
        {routeSegments.map((segment, index) => {
          const points = pathFromPoints(segment.points);
          if (!points) return null;
          return (
            <polyline
              key={`segment-${index}`}
              className={`stream-route-segment ${segmentClass(segment.type)}`}
              points={points}
            />
          );
        })}

        {cueLaserLine.length >= 2 && (
          <polyline className="stream-cue-laser-line" points={pathFromPoints(cueLaserLine.slice(0, 2))} />
        )}

        {targetZone && pointValue(targetZone.center) && (
          <g className="stream-zone target">
            <circle
              cx={pointValue(targetZone.center)?.[0]}
              cy={pointValue(targetZone.center)?.[1]}
              r={Number(targetZone.radius || 24)}
            />
            <text x={(pointValue(targetZone.center)?.[0] || 0) + Number(targetZone.radius || 24) + 8} y={(pointValue(targetZone.center)?.[1] || 0) + 6}>
              TARGET
            </text>
          </g>
        )}

        {avoidZones.map((zone, index) => {
          const center = pointValue(zone.center);
          if (!center) return null;
          const radius = Number(zone.radius || 24);
          return (
            <g className="stream-zone avoid" key={`avoid-${index}`}>
              <circle cx={center[0]} cy={center[1]} r={radius} />
              <text x={center[0] + radius + 8} y={center[1] + 6}>AVOID</text>
            </g>
          );
        })}

        {nextBallCenter && (
          <g className="stream-next-ball">
            <circle cx={nextBallCenter[0]} cy={nextBallCenter[1]} r="18" />
            <text x={nextBallCenter[0] + 22} y={nextBallCenter[1] - 8}>
              NEXT {positionPlay?.next_ball?.number ?? ''}
            </text>
          </g>
        )}

        {cueBox && (
          <g className="stream-cue-box">
            <rect x={cueBox[0]} y={cueBox[1]} width={cueBox[2]} height={cueBox[3]} rx="3" />
            {isDevMode && <text x={cueBox[0]} y={Math.max(14, cueBox[1] - 6)}>CUE</text>}
          </g>
        )}

        {yoloBoxes.map((box) => (
          <g key={box.id}>
            <circle
              className="stream-yolo-bbox-rect"
              style={{ stroke: ballStrokeColor(box) }}
              cx={box.x + box.w / 2}
              cy={box.y + box.h / 2}
              r={Math.max(2, Math.min(box.w, box.h) / 2)}
            />
            {ballLabel(box) && (
              <text
                className="stream-ball-number-label"
                x={box.x + box.w / 2}
                y={box.y + box.h / 2}
                textAnchor="middle"
                dominantBaseline="central"
              >
                {ballLabel(box)}
              </text>
            )}
            {isDevMode && (
              <text className="stream-yolo-bbox-label" x={box.x} y={Math.max(14, box.y - 6)}>
                {box.label} {box.confidence != null ? box.confidence.toFixed(3) : '-'}
              </text>
            )}
          </g>
        ))}
      </svg>
    );
  };

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

  const renderPositionPlaySummary = (route: RouteCandidate) => {
    const positionPlay = route.position_play;
    if (!positionPlay) return null;

    const nextBall = positionPlay.next_ball;
    const targetZone = positionPlay.cue_ball_after_contact?.target_zone;
    const expectedPoint = positionPlay.cue_ball_after_contact?.expected_point;
    const score = positionPlay.score;

    return (
      <div className="planner-best-grid">
        <div>
          <span className="planner-label">下一球</span>
          <strong>{nextBall?.number ?? '-'}</strong>
        </div>
        <div>
          <span className="planner-label">走位成功</span>
          <strong>{score?.position_success_prob != null ? `${(score.position_success_prob * 100).toFixed(0)}%` : '-'}</strong>
        </div>
        <div>
          <span className="planner-label">母球預估</span>
          <strong>{expectedPoint ? `${expectedPoint[0]}, ${expectedPoint[1]}` : '-'}</strong>
        </div>
        <div>
          <span className="planner-label">目標區</span>
          <strong>{targetZone ? `${targetZone.center?.[0] ?? '-'}, ${targetZone.center?.[1] ?? '-'} / R${targetZone.radius}` : '-'}</strong>
        </div>
      </div>
    );
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
                {renderPositionPlaySummary(bestRoute)}
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
                <span>
                  走位 {route.position_play?.score?.position_success_prob != null
                    ? `${(route.position_play.score.position_success_prob * 100).toFixed(0)}%`
                    : '-'}
                </span>
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

  const renderYoloDebugPanel = () => {
    if (!isDevMode) return null;

    return (
      <section className="stream-yolo-debug-panel" aria-label="完整 YOLO 資訊">
        <div className="stream-yolo-debug-header">
          <div>
            <h3>完整 YOLO 資訊</h3>
            <p>Frame {metadata?.frame_id ?? '-'} / {metadata?.img_w ?? '-'} x {metadata?.img_h ?? '-'}</p>
          </div>
          <span className={isAnalyzing ? 'stream-yolo-debug-badge active' : 'stream-yolo-debug-badge'}>
            {isAnalyzing ? 'YOLO ACTIVE' : 'YOLO IDLE'}
          </span>
        </div>

        <div className="stream-yolo-debug-grid">
          <div>
            <span>tracking_state</span>
            <strong>{metadata?.tracking_state ?? '-'}</strong>
          </div>
          <div>
            <span>detected_count</span>
            <strong>{metadata?.detected_count ?? 0}</strong>
          </div>
          <div>
            <span>detections.length</span>
            <strong>{metadata?.detections?.length ?? 0}</strong>
          </div>
          <div>
            <span>bbox.valid</span>
            <strong>{yoloBoxes.length}</strong>
          </div>
          <div>
            <span>rate_hz</span>
            <strong>{metadata?.rate_hz ?? 0}</strong>
          </div>
          <div>
            <span>multi_plan.routes</span>
            <strong>{routeCount}</strong>
          </div>
          <div>
            <span>events</span>
            <strong>{metadata?.events?.length ?? 0}</strong>
          </div>
        </div>

        {detectionPreview.length > 0 && (
          <div className="stream-yolo-bbox-table-wrap">
            <table className="stream-yolo-bbox-table" aria-label="YOLO bbox 與信心率">
              <thead>
                <tr>
                  <th>label</th>
                  <th>conf</th>
                  <th>x</th>
                  <th>y</th>
                  <th>w</th>
                  <th>h</th>
                </tr>
              </thead>
              <tbody>
                {detectionPreview.map((box) => (
                  <tr key={box.id}>
                    <td>{box.label}</td>
                    <td>{box.confidence != null ? box.confidence.toFixed(3) : '-'}</td>
                    <td>{box.x.toFixed(1)}</td>
                    <td>{box.y.toFixed(1)}</td>
                    <td>{box.w.toFixed(1)}</td>
                    <td>{box.h.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <pre className="stream-yolo-debug-json">{yoloDebugJson}</pre>
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
                  if (target.naturalWidth > 0 && target.naturalHeight > 0) {
                    setStreamImageSize((current) => {
                      if (current?.width === target.naturalWidth && current?.height === target.naturalHeight) {
                        return current;
                      }
                      return { width: target.naturalWidth, height: target.naturalHeight };
                    });
                  }
                  clearAllTimers();
                  setIsStreamLoading(false);
                }}
              />
            ) : (
              <div className="stream-placeholder">等待串流...</div>
            )}
            {renderMetadataOverlay()}
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
        {renderYoloDebugPanel()}
      </div>
    </div>
  );
};

export default StreamPage;
