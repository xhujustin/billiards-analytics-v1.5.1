/**
 * SettingsPage Component - 系統設定頁面
 * v1.5 整合 Session 和 Metadata 資訊
 */

import React, { useState, useEffect } from 'react';
import type { Session, MetadataUpdatePayload } from '../../sdk/types';
import './SettingsPage.css';

interface ColorPreset {
  name: string;
  hsv_lower: number[];
  hsv_upper: number[];
}

interface TableColorsResponse {
  current: string;
  current_display: string;
  presets: Record<string, ColorPreset>;
}


interface LightingProfile {
  name: string;
  description: string;
  params: Record<string, unknown>;
}

interface LightingProfilesResponse {
  profiles: Record<string, LightingProfile>;
  current: {
    exposure: number;
    auto_wb: boolean;
    wb_temp: number;
  };
  active_profile?: string;
}

interface RoiPoint {
  x: number;
  y: number;
}

interface RoiState {
  status?: string;
  enabled: boolean;
  configured: boolean;
  config_path: string;
  points: RoiPoint[];
  coordinate_space?: string;
  point_order?: string;
  transform?: string;
  error?: string | null;
}

interface SettingsPageProps {
  session?: Session | null;
  metadata?: MetadataUpdatePayload | null;
  onNavigate?: (page: 'calibration' | 'camera-params' | 'color-calibration') => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ session, metadata, onNavigate }) => {
  const [tableColors, setTableColors] = useState<TableColorsResponse | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>('green');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>('');
  const [lightingProfiles, setLightingProfiles] = useState<LightingProfilesResponse | null>(null);
  const [selectedLightingProfile, setSelectedLightingProfile] = useState<string>('warm');
  const [isApplyingLighting, setIsApplyingLighting] = useState<boolean>(false);

  // 攝像頭狀態
  interface CameraDevice {
    id: number;
    device_id?: number;
    backend?: number | null;
    backend_name?: string;
    name: string;
    resolution?: string;
    fps?: number;
  }
  const [cameras, setCameras] = useState<CameraDevice[]>([]);
  const [currentCameraId, setCurrentCameraId] = useState<number>(0);
  const [currentCameraBackend, setCurrentCameraBackend] = useState<number | null>(null);
  const [isSwitching, setIsSwitching] = useState<boolean>(false);
  const [roiState, setRoiState] = useState<RoiState | null>(null);
  const [roiPoints, setRoiPoints] = useState<RoiPoint[]>([]);
  const [isRoiCalibrating, setIsRoiCalibrating] = useState<boolean>(false);
  const [roiMessage, setRoiMessage] = useState<string>('');
  const [roiImageSize, setRoiImageSize] = useState<{ width: number; height: number }>({ width: 0, height: 0 });
  const [isSavingRoi, setIsSavingRoi] = useState<boolean>(false);

  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

  // 載入設定
  useEffect(() => {
    fetchTableColors();
    fetchCameras();
    fetchLightingProfiles();
    fetchRoiState();
  }, []);

  const fetchCameras = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/camera/list`);
      if (response.ok) {
        const data = await response.json();
        setCameras(data.cameras);
        setCurrentCameraId(data.current);
        setCurrentCameraBackend(data.current_backend ?? null);
        setIsSwitching(data.is_switching);
      }
    } catch (error) {
      console.error('Error fetching cameras:', error);
    }
  };

  const handleCameraSwitch = async (camera: CameraDevice) => {
    const deviceId = camera.device_id ?? camera.id;
    const backend = camera.backend ?? null;
    if (isSwitching || (deviceId === currentCameraId && backend === currentCameraBackend)) return;

    setIsSwitching(true);
    setMessage(`正在切換至 Camera ${deviceId}...`);

    try {
      const response = await fetch(`${backendUrl}/api/camera/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId, backend })
      });

      if (response.ok) {
        setCurrentCameraId(deviceId);
        setCurrentCameraBackend(backend);
        setMessage('✓ 攝像頭切換請求已發送，畫面將自動重整');
      } else {
        const error = await response.json();
        setMessage(`❌ 切換失敗: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error switching camera:', error);
      setMessage('❌ 切換失敗，請檢查後端連線');
    } finally {
      // 延遲解除鎖定狀態，等待幾秒讓切換完成
      setTimeout(() => {
        setIsSwitching(false);
        fetchCameras(); // 重新獲取狀態
      }, 3000);
    }
  };

  const fetchTableColors = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/table/colors`);
      if (!response.ok) throw new Error('Failed to fetch table colors');
      const data = await response.json();
      setTableColors(data);
      setSelectedColor(data.current_display || 'green');
    } catch (error) {
      console.error('Error fetching table colors:', error);
      setMessage('無法載入球桌顏色設定');
    }
  };

  const fetchLightingProfiles = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/camera/lighting-profiles`);
      if (!response.ok) throw new Error('Failed to fetch lighting profiles');
      const data: LightingProfilesResponse = await response.json();
      setLightingProfiles(data);

      // 以後端紀錄的 active_profile 為準，避免 wb_temp=-1 或相機回報延遲導致覆寫
      if (data.active_profile) {
        setSelectedLightingProfile(data.active_profile);
      }
    } catch (error) {
      console.error('Error fetching lighting profiles:', error);
    }
  };

  const applyLightingProfile = async (profile: string) => {
    setIsApplyingLighting(true);
    setMessage('');
    try {
      const response = await fetch(`${backendUrl}/api/camera/lighting-profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err?.detail || 'Failed to apply lighting profile');
      }

      const data = await response.json();
      const warnings: string[] = Array.isArray(data?.apply_result?.warnings) ? data.apply_result.warnings : [];
      const effective = data?.effective_current;
      const effectiveText = effective
        ? `（實際 EXP ${effective.exposure} / WB ${effective.wb_temp}K / AutoWB ${effective.auto_wb ? 'ON' : 'OFF'}）`
        : '';

      const fallbackHint = data?.wb_fallback_active ? '；硬體 WB 不支援，已啟用軟體色溫補償' : '';
      const warningHint = !data?.wb_fallback_active && warnings.length > 0 ? `；${warnings.join('、')}` : '';
      const prefix = data?.wb_fallback_active || warnings.length > 0 ? '⚠' : '✓';
      const title = data?.wb_fallback_active ? '已套用' : '已套用燈光情境：';

      setSelectedLightingProfile(profile);
      setMessage(`${prefix} ${title}${data.profile_name || profile}${effectiveText}${fallbackHint}${warningHint}`);
      await fetchLightingProfiles();
      setTimeout(() => setMessage(''), 6000);
    } catch (error) {
      console.error('Error applying lighting profile:', error);
      setMessage('✗ 套用燈光情境失敗');
    } finally {
      setIsApplyingLighting(false);
    }
  };

  const fetchRoiState = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/roi/state`);
      if (!response.ok) throw new Error('Failed to fetch ROI state');
      const data: RoiState = await response.json();
      setRoiState(data);
    } catch (error) {
      console.error('Error fetching ROI state:', error);
      setRoiMessage('無法讀取 ROI 狀態，請確認後端已啟動');
    }
  };

  const getRoiApiErrorMessage = (status: number, detail?: string) => {
    if (status === 404) {
      return 'ROI API 尚未載入，請重新啟動後端服務後再儲存';
    }
    return detail || `ROI API 呼叫失敗 (${status})`;
  };

  const handleStartRoiCalibration = () => {
    setRoiPoints([]);
    setRoiMessage('請依序點選球桌四個內角');
    setIsRoiCalibrating(true);
  };

  const handleRoiImageLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setRoiImageSize({
      width: image.naturalWidth || image.clientWidth,
      height: image.naturalHeight || image.clientHeight,
    });
  };

  const handleRoiImageClick = (event: React.MouseEvent<HTMLImageElement>) => {
    if (roiPoints.length >= 4) return;

    const image = event.currentTarget;
    const rect = image.getBoundingClientRect();
    const scaleX = (image.naturalWidth || rect.width) / rect.width;
    const scaleY = (image.naturalHeight || rect.height) / rect.height;
    const x = Math.round((event.clientX - rect.left) * scaleX);
    const y = Math.round((event.clientY - rect.top) * scaleY);
    const nextPoints = [...roiPoints, { x, y }];

    setRoiPoints(nextPoints);
    setRoiMessage(nextPoints.length === 4 ? '四點已完成，可儲存 ROI' : `已選 ${nextPoints.length}/4 點`);
  };

  const handleUndoRoiPoint = () => {
    const nextPoints = roiPoints.slice(0, -1);
    setRoiPoints(nextPoints);
    setRoiMessage(nextPoints.length > 0 ? `已選 ${nextPoints.length}/4 點` : '請依序點選球桌四個內角');
  };

  const handleSaveRoiConfig = async () => {
    if (roiPoints.length !== 4 || isSavingRoi) return;

    setIsSavingRoi(true);
    try {
      const response = await fetch(`${backendUrl}/api/roi/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ points: roiPoints }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(getRoiApiErrorMessage(response.status, error.detail));
      }

      const data: RoiState = await response.json();
      setRoiState(data);
      setIsRoiCalibrating(false);
      setRoiMessage('ROI 已儲存並啟用遮罩');
    } catch (error) {
      console.error('Error saving ROI config:', error);
      setRoiMessage(error instanceof Error ? error.message : 'ROI 儲存失敗');
    } finally {
      setIsSavingRoi(false);
    }
  };

  const handleToggleRoiEnabled = async () => {
    if (!roiState) return;

    try {
      const response = await fetch(`${backendUrl}/api/roi/enabled`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !roiState.enabled }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(getRoiApiErrorMessage(response.status, error.detail));
      }

      const data: RoiState = await response.json();
      setRoiState(data);
      setRoiMessage(data.enabled ? 'ROI mask 已啟用' : 'ROI mask 已停用');
    } catch (error) {
      console.error('Error toggling ROI mask:', error);
      setRoiMessage(error instanceof Error ? error.message : 'ROI mask 切換失敗');
    }
  };

  const handleClearRoiConfig = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/roi/config`, { method: 'DELETE' });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(getRoiApiErrorMessage(response.status, error.detail));
      }

      const data: RoiState = await response.json();
      setRoiState(data);
      setRoiPoints([]);
      setRoiMessage('ROI 設定已清除，YOLO 將回到未遮罩流程');
    } catch (error) {
      console.error('Error clearing ROI config:', error);
      setRoiMessage(error instanceof Error ? error.message : 'ROI 清除失敗');
    }
  };

  const roiPointSummary = roiState?.points?.length
    ? roiState.points.map((point, index) => `P${index + 1} (${point.x}, ${point.y})`).join('  ')
    : '尚未設定';

  const handleColorChange = async (color: string) => {
    setIsLoading(true);
    setMessage('');

    try {
      const response = await fetch(`${backendUrl}/api/table/color`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ color }),
      });

      if (!response.ok) throw new Error('Failed to update table color');

      await response.json();
      setSelectedColor(color);
      setMessage(`✓ 球桌顏色已更新為 ${tableColors?.presets[color]?.name || color}`);

      // 3秒後清除訊息
      setTimeout(() => setMessage(''), 3000);
    } catch (error) {
      console.error('Error updating table color:', error);
      setMessage('✗ 更新失敗');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="settings-page">
      <h2 className="page-title"> 系統設定</h2>



      {/* 球桌布料顏色設定 */}
      <div className="card">
        <h3 className="card-title">球桌布料顏色</h3>
        <div className="settings-content">
          <div className="setting-row">
            <span className="setting-label">當前顏色:</span>
            <span className="setting-value">
              {tableColors?.presets[selectedColor]?.name || '綠色'}
            </span>
          </div>

          <div className="setting-section">
            <p className="setting-desc">選擇球桌布料顏色（影響球桌偵測）:</p>
            <div className="device-list">
              {tableColors && Object.entries(tableColors.presets)
                .filter(([key]) => key !== 'custom') // 暫時隱藏自訂選項
                .map(([key, preset]) => (
                  <div
                    key={key}
                    className={`device-item ${selectedColor === key ? 'active' : ''}`}
                    onClick={() => !isLoading && handleColorChange(key)}
                  >
                    <input
                      type="radio"
                      name="tableColor"
                      value={key}
                      checked={selectedColor === key}
                      onChange={() => !isLoading && handleColorChange(key)}
                      disabled={isLoading}
                    />
                    <label>{preset.name}</label>
                  </div>
                ))}
            </div>
          </div>

          {message && (
            <div className={`setting-message ${message.startsWith('✓') ? 'success' : 'error'}`}>
              {message}
            </div>
          )}

          <p className="setting-desc" style={{ fontSize: '0.85em', color: '#64748b', marginTop: '8px' }}>
            💡 提示：更改顏色後，系統會重新偵測球桌區域
          </p>
        </div>
      </div>



      {/* 燈光情境設定 */}
      <div className="card">
        <h3 className="card-title">燈光情境</h3>
        <div className="settings-content">
          <div className="setting-row">
            <span className="setting-label">目前情境:</span>
            <span className="setting-value">
              {lightingProfiles?.profiles[selectedLightingProfile]?.name || selectedLightingProfile}
            </span>
          </div>

          {lightingProfiles?.current && (
            <div className="setting-row">
              <span className="setting-label">目前相機參數:</span>
              <span className="setting-value">
                EXP {lightingProfiles.current.exposure} / WB {lightingProfiles.current.wb_temp}K / AutoWB {lightingProfiles.current.auto_wb ? 'ON' : 'OFF'}
              </span>
            </div>
          )}

          <div className="setting-section">
            <p className="setting-desc">一鍵套用燈光情境（暖光/白光）:</p>
            <div className="device-list">
              {lightingProfiles && Object.entries(lightingProfiles.profiles).map(([key, profile]) => (
                <div
                  key={key}
                  className={`device-item ${selectedLightingProfile === key ? 'active' : ''} ${isApplyingLighting ? 'disabled' : ''}`}
                  onClick={() => !isApplyingLighting && applyLightingProfile(key)}
                >
                  <input
                    type="radio"
                    name="lightingProfile"
                    checked={selectedLightingProfile === key}
                    onChange={() => !isApplyingLighting && applyLightingProfile(key)}
                    disabled={isApplyingLighting}
                  />
                  <label>{profile.name} - {profile.description}</label>
                </div>
              ))}
            </div>
          </div>

          <button className="btn btn-secondary" onClick={fetchLightingProfiles} disabled={isApplyingLighting}>
            {isApplyingLighting ? '套用中...' : '重新讀取燈光情境'}
          </button>
        </div>
      </div>
      {/* 攝影機設定 */}
      <div className="card">
        <h3 className="card-title">攝影機設定</h3>
        <div className="settings-content">
          <div className="setting-row">
            <span className="setting-label">當前設備:</span>
            <span className="setting-value">
              {cameras.find(c => (c.device_id ?? c.id) === currentCameraId && (c.backend ?? null) === currentCameraBackend)?.name || `Camera ${currentCameraId}`}
              {isSwitching && ' (切換中...)'}
            </span>
          </div>

          <div className="setting-section">
            <p className="setting-desc">可用設備:</p>
            <div className="device-list">
              {cameras.length > 0 ? (
                cameras.map(camera => (
                  <div
                    key={`${camera.device_id ?? camera.id}-${camera.backend ?? 'auto'}`}
                    className={`device-item ${(currentCameraId === (camera.device_id ?? camera.id) && currentCameraBackend === (camera.backend ?? null)) ? 'active' : ''} ${isSwitching ? 'disabled' : ''}`}
                    onClick={() => !isSwitching && handleCameraSwitch(camera)}
                  >
                    <input
                      type="radio"
                      name="camera"
                      checked={currentCameraId === (camera.device_id ?? camera.id) && currentCameraBackend === (camera.backend ?? null)}
                      readOnly
                    />
                    <label>
                      {camera.name}
                      {camera.resolution && ` / ${camera.resolution}`}
                      {typeof camera.fps === 'number' && camera.fps > 0 ? ` @ ${camera.fps}fps` : ''}
                    </label>
                  </div>
                ))
              ) : (
                <div className="loading-placeholder">正在掃描設備...</div>
              )}
            </div>
          </div>

          <button
            className="btn btn-secondary"
            onClick={fetchCameras}
            disabled={isSwitching}
          >
            {isSwitching ? '切換中...' : '重新掃描設備'}
          </button>
        </div>
      </div>

      {/* 相機參數設定 */}
      <div className="card">
        <h3 className="card-title">相機參數設定</h3>
        <div className="settings-content">
          <p className="setting-desc">
            調整相機參數以優化影像品質,包含曝光、降噪、白平衡等設定
          </p>
          <button
            className="btn btn-primary"
            onClick={() => onNavigate?.('camera-params' as any)}
            style={{ marginTop: '12px' }}
          >
            開啟相機參數設定
          </button>
        </div>
      </div>

      {/* YOLO 參數 */}
      <div className="card">
        <h3 className="card-title">YOLO 參數</h3>
        <div className="settings-content">
          <div className="setting-row">
            <span className="setting-label">跳幀設定:</span>
            <span className="setting-value">2 (每 3 幀執行一次)</span>
          </div>

          <div className="setting-section">
            <label className="setting-label">影像品質:</label>
            <div className="quality-options">
              <div className="quality-option">
                <input type="radio" name="quality" value="high" defaultChecked />
                <label>高</label>
              </div>
              <div className="quality-option">
                <input type="radio" name="quality" value="med" />
                <label>中</label>
              </div>
              <div className="quality-option">
                <input type="radio" name="quality" value="low" />
                <label>低</label>
              </div>
            </div>
          </div>

          <button className="btn btn-primary">
            儲存設定
          </button>
        </div>
      </div>

      {/* 系統資訊 */}
      <div className="card">
        <h3 className="card-title">系統資訊</h3>
        <div className="settings-content">
          <div className="setting-row">
            <span className="setting-label">系統版本:</span>
            <span className="setting-value">v1.5.1</span>
          </div>
          <div className="setting-row">
            <span className="setting-label">後端 API:</span>
            <span className="setting-value">
              {import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001'}
            </span>
          </div>
          <div className="setting-row">
            <span className="setting-label">WebSocket:</span>
            <span className="setting-value">
              {import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001'}
            </span>
          </div>
        </div>
      </div>

      {/* Session 資訊 */}
      {session && (
        <div className="card">
          <h3 className="card-title">Session 資訊</h3>
          <div className="settings-content">
            <div className="session-details">
              <div className="detail-row">
                <span className="detail-label">Session ID:</span>
                <code className="detail-value">{session.session_id}</code>
              </div>
              <div className="detail-row">
                <span className="detail-label">Stream ID:</span>
                <code className="detail-value">{session.stream_id}</code>
              </div>
              <div className="detail-row">
                <span className="detail-label">Role:</span>
                <code className="detail-value">{session.role}</code>
              </div>
              <div className="detail-row">
                <span className="detail-label">狀態:</span>
                <span className="detail-value status-active">🟢 Active</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">過期時間:</span>
                <span className="detail-value">
                  {new Date(session.expires_at).toLocaleString()}
                </span>
              </div>
            </div>

            {/* 權限資訊 */}
            {session.permission_flags && session.permission_flags.length > 0 && (
              <div className="permission-section">
                <p className="setting-desc">權限列表:</p>
                <div className="permissions">
                  {session.permission_flags.map((permission) => (
                    <div key={permission} className="permission-item">
                      <span className="permission-icon">✓</span>
                      <span className="permission-name">{permission}</span>
                      <span className="permission-desc">
                        {getPermissionDescription(permission)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="session-actions">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  if (session?.session_id) {
                    navigator.clipboard.writeText(session.session_id);
                    alert('Session ID 已複製到剪貼簿');
                  }
                }}
              >
                複製 Session ID
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Metadata 即時監控 */}
      {metadata && (
        <div className="card">
          <h3 className="card-title">即時數據監控 (Metadata)</h3>
          <div className="settings-content">
            {/* 基本指標 */}
            <div className="metrics">
              <div className="metric-row">
                <span className="metric-label">Frame ID:</span>
                <span className="metric-value">{metadata.frame_id}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">檢測數量:</span>
                <span className="metric-value">{metadata.detected_count} 個物件</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">追蹤狀態:</span>
                <span className={`metric-value ${metadata.tracking_state === 'active' ? 'active' : ''}`}>
                  {metadata.tracking_state === 'active' ? '● ' : '○ '}
                  {metadata.tracking_state}
                </span>
              </div>
              <div className="metric-row">
                <span className="metric-label">更新頻率:</span>
                <span className="metric-value">{metadata.rate_hz} Hz</span>
              </div>
              {metadata.ar_paths && metadata.ar_paths.length > 0 && (
                <div className="metric-row">
                  <span className="metric-label">AR 路徑數:</span>
                  <span className="metric-value">{metadata.ar_paths.length} 條</span>
                </div>
              )}
            </div>

            {/* 檢測物件列表 */}
            {metadata.detections && metadata.detections.length > 0 && (
              <div className="detection-section">
                <p className="setting-desc">檢測物件列表:</p>
                <div className="detections">
                  {metadata.detections.map((detection, index) => {
                    const detectionLabel = detection.color || detection.label || '未知';
                    const detectionScore = detection.conf ?? detection.score ?? 0;
                    const hasBBox = Array.isArray(detection.bbox) && detection.bbox.length >= 2;
                    const hasXY = typeof detection.x === 'number' && typeof detection.y === 'number';
                    const ratioText =
                      typeof detection.white_ratio === 'number' || typeof detection.dark_ratio === 'number' || typeof detection.color_ratio === 'number';
                    const hsvMedianText = Array.isArray(detection.color_debug?.hsv_median)
                      ? `[${detection.color_debug.hsv_median
                          .map((v) => (typeof v === 'number' ? v.toFixed(1) : 'null'))
                          .join(', ')}]`
                      : 'N/A';
                    const labMedianText = Array.isArray(detection.color_debug?.lab_median)
                      ? `[${detection.color_debug.lab_median
                          .map((v) => (typeof v === 'number' ? v.toFixed(1) : 'null'))
                          .join(', ')}]`
                      : 'N/A';

                    return (
                      <div key={index} className="detection-item">
                        <span className="detection-index">#{index + 1}</span>
                        <span className="detection-label">{detectionLabel}</span>
                        <span className="detection-confidence">
                          信心度: {(detectionScore * 100).toFixed(0)}%
                        </span>
                        {hasBBox && (
                          <span className="detection-bbox">
                            [x:{detection.bbox![0]}, y:{detection.bbox![1]}]
                          </span>
                        )}
                        {!hasBBox && hasXY && (
                          <span className="detection-bbox">
                            [x:{Math.round(detection.x!)}, y:{Math.round(detection.y!)}]
                          </span>
                        )}
                        {ratioText && (
                          <span className="detection-bbox">
                            W:{(detection.white_ratio ?? 0).toFixed(3)} D:{(detection.dark_ratio ?? 0).toFixed(3)} C:{(detection.color_ratio ?? 0).toFixed(3)}
                          </span>
                        )}
                        {detection.color_debug && (
                          <>
                            <span className="detection-bbox">
                              valid:{detection.color_debug.valid_pixels ?? 0}/{detection.color_debug.mask_pixels ?? 0}
                            </span>
                            <span className="detection-bbox">HSV: {hsvMedianText}</span>
                            <span className="detection-bbox">LAB: {labMedianText}</span>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 軌跡預測 */}
            {metadata.ar_paths && metadata.ar_paths.length > 0 && (
              <div className="ar-path-section">
                <p className="setting-desc">軌跡預測:</p>
                <div className="ar-paths">
                  {metadata.ar_paths.map((path, index) => (
                    <div key={index} className="ar-path-item">
                      <span className="path-label">預測路徑 #{index + 1}:</span>
                      <span className="path-points">{path.length} 個點</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {/* 投影機校正 */}
      <div className="card">
        <h3 className="card-title">投影機校正</h3>
        <div className="settings-content">
          <div className="setting-section">
            <p className="setting-desc">
              使用 ArUco 標記自動校正投影機與相機的座標映射關係
            </p>
            <button
              className="calibration-button"
              onClick={() => onNavigate?.('calibration')}
              style={{
                marginTop: '15px',
                padding: '12px 24px',
                background: '#4a9eff',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '16px',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#3a8eef'}
              onMouseLeave={(e) => e.currentTarget.style.background = '#4a9eff'}
            >
              開始校正
            </button>
          </div>
        </div>
      </div>
      {/* 顏色校正 */}
      <div className="card">
        <h3 className="card-title">顏色校正</h3>
        <div className="settings-content">
          <div className="setting-section">
            <p className="setting-desc">
              使用目前相機畫面進行顏色標定，建立花式/斯諾克校正設定檔
            </p>
            <button
              className="calibration-button"
              onClick={() => onNavigate?.('color-calibration')}
              style={{
                marginTop: '15px',
                padding: '12px 24px',
                background: '#4a9eff',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '16px',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#3a8eef'}
              onMouseLeave={(e) => e.currentTarget.style.background = '#4a9eff'}
            >
              開啟顏色校正
            </button>
          </div>
        </div>
      </div>
      <div className="card">
        <h3 className="card-title">球桌 ROI 校正</h3>
        <div className="settings-content">
          <div className="roi-status-grid">
            <div className="setting-row">
              <span className="setting-label">校正狀態:</span>
              <span className={`setting-value ${roiState?.configured ? 'status-active' : ''}`}>
                {roiState?.configured ? '已校正' : '未校正'}
              </span>
            </div>
            <div className="setting-row">
              <span className="setting-label">ROI mask:</span>
              <span className={`setting-value ${roiState?.enabled ? 'status-active' : ''}`}>
                {roiState?.enabled ? '啟用' : '停用'}
              </span>
            </div>
          </div>

          <div className="setting-section">
            <p className="setting-desc">
              ROI 只用來在 YOLO 前遮住球桌外區域，座標保留原始相機畫面，不做透視變形。
            </p>
            <div className="roi-point-summary">
              <span className="setting-label">四點座標:</span>
              <code>{roiPointSummary}</code>
            </div>
            {roiState?.error && (
              <div className="setting-message error">
                ROI config 讀取失敗：{roiState.error}
              </div>
            )}
            {roiMessage && (
              <div className={`setting-message ${roiMessage.includes('失敗') || roiMessage.includes('無法') ? 'error' : 'success'}`}>
                {roiMessage}
              </div>
            )}
            <div className="roi-actions">
              <button className="btn btn-primary" onClick={handleStartRoiCalibration}>
                開始 ROI 校正
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleToggleRoiEnabled}
                disabled={!roiState}
              >
                {roiState?.enabled ? '停用 ROI mask' : '啟用 ROI mask'}
              </button>
              <button
                className="btn btn-danger"
                onClick={handleClearRoiConfig}
                disabled={!roiState?.configured}
              >
                清除 ROI
              </button>
            </div>
          </div>
        </div>
      </div>

      {isRoiCalibrating && (
        <div className="roi-modal" role="dialog" aria-modal="true" aria-label="球桌 ROI 校正">
          <div className="roi-modal-panel">
            <div className="roi-modal-header">
              <div>
                <h3>球桌 ROI 校正</h3>
                <p>依序點選四個球桌內角，完成後儲存。</p>
              </div>
              <button className="roi-close-button" onClick={() => setIsRoiCalibrating(false)}>
                關閉
              </button>
            </div>
            <div className="roi-calibration-stage">
              <div className="roi-image-wrap">
                <img
                  className="roi-calibration-image"
                  src={`${backendUrl}/stream/monitor`}
                  alt="ROI calibration live stream"
                  onLoad={handleRoiImageLoad}
                  onClick={handleRoiImageClick}
                  draggable={false}
                />
                {roiImageSize.width > 0 && roiImageSize.height > 0 && (
                  <svg
                    className="roi-overlay"
                    viewBox={`0 0 ${roiImageSize.width} ${roiImageSize.height}`}
                    preserveAspectRatio="none"
                  >
                    {roiPoints.length > 1 && (
                      <polyline
                        points={roiPoints.map((point) => `${point.x},${point.y}`).join(' ')}
                        fill="none"
                        stroke="#00ff2a"
                        strokeWidth="4"
                      />
                    )}
                    {roiPoints.length === 4 && (
                      <polygon
                        points={roiPoints.map((point) => `${point.x},${point.y}`).join(' ')}
                        fill="rgba(0, 255, 42, 0.12)"
                        stroke="#00ff2a"
                        strokeWidth="4"
                      />
                    )}
                    {roiPoints.map((point, index) => (
                      <g key={`${point.x}-${point.y}-${index}`}>
                        <circle cx={point.x} cy={point.y} r="14" fill="#fff200" stroke="#00ff2a" strokeWidth="4" />
                        <text x={point.x + 18} y={point.y - 18} fill="#fff200" fontSize="24" fontWeight="700">
                          P{index + 1}
                        </text>
                      </g>
                    ))}
                  </svg>
                )}
              </div>
            </div>
            <div className="roi-modal-footer">
              <span className="roi-counter">已選 {roiPoints.length}/4 點</span>
              <button className="btn btn-secondary" onClick={handleUndoRoiPoint} disabled={roiPoints.length === 0}>
                復原上一點
              </button>
              <button className="btn btn-secondary" onClick={() => setRoiPoints([])}>
                重新選取
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveRoiConfig}
                disabled={roiPoints.length !== 4 || isSavingRoi}
              >
                {isSavingRoi ? '儲存中...' : '儲存 ROI'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function getPermissionDescription(permission: string): string {
  const descriptions: Record<string, string> = {
    view: '查看即時影像',
    calibrate: '校準控制',
    replay: '回放控制',
    score_control: '計分控制',
  };
  return descriptions[permission] || permission;
}

export default SettingsPage;





