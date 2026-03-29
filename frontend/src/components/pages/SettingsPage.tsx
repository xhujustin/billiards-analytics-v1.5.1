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

  // 攝像頭狀態
  interface CameraDevice {
    id: number;
    name: string;
  }
  const [cameras, setCameras] = useState<CameraDevice[]>([]);
  const [currentCameraId, setCurrentCameraId] = useState<number>(0);
  const [isSwitching, setIsSwitching] = useState<boolean>(false);

  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

  // 載入設定
  useEffect(() => {
    fetchTableColors();
    fetchCameras();
  }, []);

  const fetchCameras = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/camera/list`);
      if (response.ok) {
        const data = await response.json();
        setCameras(data.cameras);
        setCurrentCameraId(data.current);
        setIsSwitching(data.is_switching);
      }
    } catch (error) {
      console.error('Error fetching cameras:', error);
    }
  };

  const handleCameraSwitch = async (deviceId: number) => {
    if (isSwitching || deviceId === currentCameraId) return;

    setIsSwitching(true);
    setMessage(`正在切換至 Camera ${deviceId}...`);

    try {
      const response = await fetch(`${backendUrl}/api/camera/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId })
      });

      if (response.ok) {
        setCurrentCameraId(deviceId);
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


      {/* 攝影機設定 */}
      <div className="card">
        <h3 className="card-title">攝影機設定</h3>
        <div className="settings-content">
          <div className="setting-row">
            <span className="setting-label">當前設備:</span>
            <span className="setting-value">
              {cameras.find(c => c.id === currentCameraId)?.name || `Camera ${currentCameraId}`}
              {isSwitching && ' (切換中...)'}
            </span>
          </div>

          <div className="setting-section">
            <p className="setting-desc">可用設備:</p>
            <div className="device-list">
              {cameras.length > 0 ? (
                cameras.map(camera => (
                  <div
                    key={camera.id}
                    className={`device-item ${currentCameraId === camera.id ? 'active' : ''} ${isSwitching ? 'disabled' : ''}`}
                    onClick={() => !isSwitching && handleCameraSwitch(camera.id)}
                  >
                    <input
                      type="radio"
                      name="camera"
                      checked={currentCameraId === camera.id}
                      readOnly
                    />
                    <label>{camera.name}</label>
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
