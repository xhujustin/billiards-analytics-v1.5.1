import React, { useEffect, useMemo, useState } from 'react';
import type { MetadataUpdatePayload, Session } from '../../sdk/types';
import type { ThemeMode } from '../../theme';
import { CameraParamsPage } from './CameraParamsPage';
import './SettingsPage.css';

export type SettingsTab =
  | 'general'
  | 'appearance'
  | 'camera'
  | 'table-calibration'
  | 'tracking'
  | 'advanced-monitoring';

interface SettingsPageProps {
  activeTab: SettingsTab;
  isDevMode: boolean;
  onDevModeChange: (enabled: boolean) => void;
  themeMode: ThemeMode;
  onThemeModeChange: (themeMode: ThemeMode) => void;
  session?: Session | null;
  metadata?: MetadataUpdatePayload | null;
  apiBaseUrl?: string;
  aiCoachWsUrl?: string;
  onNavigate?: (page: 'calibration' | 'camera-params' | 'color-calibration') => void;
}

const tabTitles: Record<SettingsTab, string> = {
  general: '一般',
  appearance: '外觀',
  camera: '相機',
  'table-calibration': '球桌校正',
  tracking: '追蹤設定',
  'advanced-monitoring': '進階監控',
};

const tablePresets = [
  { value: 'green', label: '綠色', color: '#3d963d' },
  { value: 'gray', label: '灰色', color: '#758082' },
  { value: 'blue', label: '藍色', color: '#3d6699' },
  { value: 'pink', label: '粉色', color: '#b347a0' },
  { value: 'purple', label: '紫色', color: '#7a3d99' },
  { value: 'custom', label: '自訂', color: '#3d963d' },
];

const TABLE_PRESET_STORAGE_KEY = 'ncut.tablePreset';

const tablePresetColors = tablePresets.reduce<Record<string, string>>((colors, preset) => {
  colors[preset.value] = preset.color;
  return colors;
}, {});

const isTablePresetValue = (value: string | null): value is string => {
  return Boolean(value && tablePresetColors[value]);
};

const getInitialTablePreset = () => {
  const storedPreset = window.localStorage.getItem(TABLE_PRESET_STORAGE_KEY);
  return isTablePresetValue(storedPreset) ? storedPreset : 'green';
};

type RoiAdjustment = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

const defaultRoiAdjustment: RoiAdjustment = {
  left: 0,
  top: 0,
  right: 0,
  bottom: 0,
};

export const SettingsPage: React.FC<SettingsPageProps> = ({
  activeTab,
  isDevMode,
  onDevModeChange,
  themeMode,
  onThemeModeChange,
  session,
  metadata,
  apiBaseUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
  aiCoachWsUrl = import.meta.env.VITE_AI_COACH_WS || 'ws://localhost:8010/ws/coach',
  onNavigate,
}) => {
  const [backendApiUrl, setBackendApiUrl] = useState(
    import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
  );
  const [webSocketUrl, setWebSocketUrl] = useState(
    import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001',
  );
  const [coachWebSocketUrl, setCoachWebSocketUrl] = useState(aiCoachWsUrl);
  const [tablePreset, setTablePreset] = useState(getInitialTablePreset);
  const [customHsvLower, setCustomHsvLower] = useState('35,40,40');
  const [customHsvUpper, setCustomHsvUpper] = useState('85,255,255');
  const [roiAdjustment, setRoiAdjustment] = useState<RoiAdjustment>(defaultRoiAdjustment);
  const [tableRoiRaw, setTableRoiRaw] = useState<number[] | null>(null);
  const [tableRoiAdjusted, setTableRoiAdjusted] = useState<number[] | null>(null);
  const [tableRoiStatus, setTableRoiStatus] = useState('尚未偵測');
  const [cameraDevice, setCameraDevice] = useState('camera-0');
  const [lightingProfile, setLightingProfile] = useState('warm');
  const [roiMaskEnabled, setRoiMaskEnabled] = useState(false);
  const [roiConfigured, setRoiConfigured] = useState(false);
  const [quality, setQuality] = useState('medium');
  const [saveMessage, setSaveMessage] = useState('');
  const [isCameraParamsOpen, setIsCameraParamsOpen] = useState(false);

  const formatMetricNumber = (value: unknown, digits = 1) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toFixed(digits) : '-';
  };

  const formatPoint = (point: unknown) => {
    if (!Array.isArray(point) || point.length < 2) return '-';
    return `${formatMetricNumber(point[0], 0)}, ${formatMetricNumber(point[1], 0)}`;
  };

  const cueSummary = useMemo(() => {
    const cueBox = Array.isArray(metadata?.cue) && metadata.cue.length >= 4 ? metadata.cue : null;
    const rawCueBoxes = (metadata?.raw_yolo_boxes || []).filter((box) => box.label === 'cue');
    const bestRawCue = rawCueBoxes.reduce<(typeof rawCueBoxes)[number] | null>((best, box) => {
      if (!best) return box;
      return Number(box.conf || 0) > Number(best.conf || 0) ? box : best;
    }, null);
    const cueLaserLine = Array.isArray(metadata?.cue_laser_line) ? metadata.cue_laser_line : [];
    const primaryLine = cueLaserLine.length >= 2 ? [cueLaserLine[0], cueLaserLine[1]] : null;
    const reverseLine = cueLaserLine.length >= 4 ? [cueLaserLine[2], cueLaserLine[3]] : null;

    let lineLength = null;
    let lineAngle = null;
    if (primaryLine) {
      const [start, end] = primaryLine;
      const dx = Number(end?.[0]) - Number(start?.[0]);
      const dy = Number(end?.[1]) - Number(start?.[1]);
      if (Number.isFinite(dx) && Number.isFinite(dy)) {
        lineLength = Math.hypot(dx, dy);
        lineAngle = Math.atan2(dy, dx) * (180 / Math.PI);
      }
    }

    return {
      detected: Boolean(cueBox || bestRawCue || primaryLine),
      box: cueBox,
      center: cueBox ? [cueBox[0] + cueBox[2] / 2, cueBox[1] + cueBox[3] / 2] : null,
      bestConfidence: bestRawCue?.conf ?? null,
      rawCueCount: rawCueBoxes.length,
      primaryLine,
      reverseLine,
      lineLength,
      lineAngle,
      axisStart: Array.isArray(metadata?.cue_axis?.[0]) ? metadata?.cue_axis?.[0] : null,
      axisEnd: Array.isArray(metadata?.cue_axis?.[1]) ? metadata?.cue_axis?.[1] : null,
      laserOnly: Boolean(metadata?.cue_laser_only),
    };
  }, [metadata]);

  const rawDetectionSummary = useMemo(
    () =>
      JSON.stringify(
        (metadata?.detections || []).slice(0, 5).map((detection, index) => ({
          index: index + 1,
          x: detection.x ?? detection.bbox?.[0] ?? null,
          y: detection.y ?? detection.bbox?.[1] ?? null,
          label: detection.number ?? detection.color ?? detection.label ?? 'unknown',
          confidence: detection.conf ?? detection.score ?? null,
        })),
        null,
        2,
      ),
    [metadata],
  );

  useEffect(() => {
    let isMounted = true;

    fetch(`${apiBaseUrl}/api/table/colors`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        const nextPreset = data?.current_display || data?.current;
        if (!isMounted || !isTablePresetValue(nextPreset)) return;
        setTablePreset(nextPreset);
        window.localStorage.setItem(TABLE_PRESET_STORAGE_KEY, nextPreset);
      })
      .catch(() => {
        const storedPreset = window.localStorage.getItem(TABLE_PRESET_STORAGE_KEY);
        if (isMounted && isTablePresetValue(storedPreset)) {
          setTablePreset(storedPreset);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [apiBaseUrl]);

  useEffect(() => {
    let isMounted = true;

    fetch(`${apiBaseUrl}/api/table/roi-adjustment`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!isMounted) return;
        setRoiAdjustment({ ...defaultRoiAdjustment, ...(data?.adjustment || {}) });
        setTableRoiRaw(Array.isArray(data?.table_roi_raw) ? data.table_roi_raw : null);
        setTableRoiAdjusted(Array.isArray(data?.table_roi) ? data.table_roi : null);
        setTableRoiStatus(data?.table_roi_status || '尚未偵測');
      })
      .catch(() => {
        if (isMounted) setTableRoiStatus('尚未偵測');
      });

    return () => {
      isMounted = false;
    };
  }, [apiBaseUrl]);

  const copySessionId = async () => {
    if (!session?.session_id) return;
    await navigator.clipboard.writeText(session.session_id);
    setSaveMessage('Session ID 已複製');
    window.setTimeout(() => setSaveMessage(''), 1800);
  };

  const saveLocalSettings = () => {
    setSaveMessage('設定已暫存於本機 UI');
    window.setTimeout(() => setSaveMessage(''), 1800);
  };

  const renderToggle = (
    checked: boolean,
    onChange: (checked: boolean) => void,
    label: string,
  ) => (
    <label className="settings-toggle-control" aria-label={label}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="settings-toggle-track" aria-hidden="true">
        <span className="settings-toggle-thumb" />
      </span>
    </label>
  );

  const renderPanelRow = (
    title: string,
    description: string,
    control: React.ReactNode,
  ) => (
    <div className="settings-row">
      <div className="settings-row-copy">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <div className="settings-control">{control}</div>
    </div>
  );

  const handleTablePresetChange = (preset: string) => {
    setTablePreset(preset);
    window.localStorage.setItem(TABLE_PRESET_STORAGE_KEY, preset);

    fetch(`${apiBaseUrl}/api/table/color`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ color: preset }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setSaveMessage('球桌顏色設定已記住');
        window.setTimeout(() => setSaveMessage(''), 1800);
      })
      .catch((error) => {
        console.warn('同步球桌顏色設定失敗:', error);
        setSaveMessage('已暫存於本機，後端同步失敗');
        window.setTimeout(() => setSaveMessage(''), 2200);
      });
  };

  const parseHsvTriplet = (value: string) => {
    const parts = value.split(',').map((part) => Number(part.trim()));
    if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) {
      throw new Error('HSV 必須是 H,S,V 三個數字');
    }
    return parts.map((part, index) => {
      const max = index === 0 ? 180 : 255;
      return Math.max(0, Math.min(max, Math.round(part)));
    });
  };

  const handleApplyCustomTableColor = () => {
    let hsvLower: number[];
    let hsvUpper: number[];
    try {
      hsvLower = parseHsvTriplet(customHsvLower);
      hsvUpper = parseHsvTriplet(customHsvUpper);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : 'HSV 格式錯誤');
      window.setTimeout(() => setSaveMessage(''), 2200);
      return;
    }

    setTablePreset('custom');
    window.localStorage.setItem(TABLE_PRESET_STORAGE_KEY, 'custom');
    fetch(`${apiBaseUrl}/api/table/color`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ color: 'custom', hsv_lower: hsvLower, hsv_upper: hsvUpper }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setSaveMessage('自訂桌布顏色已套用');
        window.setTimeout(() => setSaveMessage(''), 1800);
      })
      .catch((error) => {
        console.warn('套用自訂桌布顏色失敗:', error);
        setSaveMessage('自訂桌布顏色套用失敗');
        window.setTimeout(() => setSaveMessage(''), 2200);
      });
  };

  const handleAutoDetectTableColor = () => {
    fetch(`${apiBaseUrl}/api/table/color/auto-detect`, { method: 'POST' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        const nextPreset = data?.color;
        if (isTablePresetValue(nextPreset)) {
          setTablePreset(nextPreset);
          window.localStorage.setItem(TABLE_PRESET_STORAGE_KEY, nextPreset);
        }
        setSaveMessage(`已自動檢測桌布顏色：${tablePresets.find((preset) => preset.value === nextPreset)?.label || nextPreset}`);
        window.setTimeout(() => setSaveMessage(''), 2200);
      })
      .catch((error) => {
        console.warn('自動檢測桌布顏色失敗:', error);
        setSaveMessage('自動檢測桌布顏色失敗，請先確認即時影像已啟動');
        window.setTimeout(() => setSaveMessage(''), 2600);
      });
  };

  const syncRoiAdjustment = (nextAdjustment: RoiAdjustment) => {
    setRoiAdjustment(nextAdjustment);
    fetch(`${apiBaseUrl}/api/table/roi-adjustment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(nextAdjustment),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setTableRoiRaw(Array.isArray(data?.table_roi_raw) ? data.table_roi_raw : null);
        setTableRoiAdjusted(Array.isArray(data?.table_roi) ? data.table_roi : null);
        setTableRoiStatus(data?.table_roi_status || '已更新');
      })
      .catch((error) => {
        console.warn('同步 ROI 微調失敗:', error);
        setSaveMessage('ROI 微調同步失敗');
        window.setTimeout(() => setSaveMessage(''), 2200);
      });
  };

  const handleRoiAdjustmentChange = (key: keyof RoiAdjustment, value: string) => {
    const nextValue = Number(value);
    syncRoiAdjustment({
      ...roiAdjustment,
      [key]: Number.isFinite(nextValue) ? Math.round(nextValue) : 0,
    });
  };

  const resetRoiAdjustment = () => {
    fetch(`${apiBaseUrl}/api/table/roi-adjustment/reset`, { method: 'POST' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setRoiAdjustment({ ...defaultRoiAdjustment, ...(data?.adjustment || {}) });
        setTableRoiRaw(Array.isArray(data?.table_roi_raw) ? data.table_roi_raw : null);
        setTableRoiAdjusted(Array.isArray(data?.table_roi) ? data.table_roi : null);
        setTableRoiStatus(data?.table_roi_status || '已重設');
      })
      .catch((error) => {
        console.warn('重設 ROI 微調失敗:', error);
        setSaveMessage('ROI 微調重設失敗');
        window.setTimeout(() => setSaveMessage(''), 2200);
      });
  };

  const renderTableColorSelector = () => (
    <div className="settings-color-select-control">
      <span
        className="settings-color-preview"
        style={{ background: tablePresetColors[tablePreset] }}
        aria-hidden="true"
      />
      <select value={tablePreset} onChange={(event) => handleTablePresetChange(event.target.value)}>
        {tablePresets.map((preset) => (
          <option key={preset.value} value={preset.value}>
            {preset.label}
          </option>
        ))}
      </select>
    </div>
  );

  const renderCustomTableColorControls = () => (
    <div className="settings-stack-control">
      <input
        value={customHsvLower}
        onChange={(event) => setCustomHsvLower(event.target.value)}
        placeholder="HSV 下限，例如 90,50,50"
      />
      <input
        value={customHsvUpper}
        onChange={(event) => setCustomHsvUpper(event.target.value)}
        placeholder="HSV 上限，例如 130,255,255"
      />
      <button className="settings-button secondary" type="button" onClick={handleApplyCustomTableColor}>
        套用自訂
      </button>
    </div>
  );

  const formatRoi = (roi: number[] | null) => {
    if (!Array.isArray(roi) || roi.length < 4) return '尚未偵測';
    return `x ${roi[0]}, y ${roi[1]}, w ${roi[2]}, h ${roi[3]}`;
  };

  const renderRoiAdjustmentControl = (key: keyof RoiAdjustment) => (
    <input
      type="number"
      value={roiAdjustment[key]}
      onChange={(event) => handleRoiAdjustmentChange(key, event.target.value)}
    />
  );

  void tableRoiRaw;
  void tableRoiAdjusted;
  void tableRoiStatus;
  void resetRoiAdjustment;
  void formatRoi;
  void renderRoiAdjustmentControl;

  const renderGeneral = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">系統資訊</h3>
        <p className="settings-section-desc">目前前端介面與系統版本資訊。</p>
        <div className="settings-panel">
          {renderPanelRow('版本', 'NCUT 撞球分析系統目前版本。', <strong>v1.5.1</strong>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">網路連線</h3>
        <p className="settings-section-desc">設定前端連到後端服務的位置。</p>
        <div className="settings-panel">
          {renderPanelRow(
            'Backend API',
            '後端 REST API 的連線位置。',
            <input value={backendApiUrl} onChange={(event) => setBackendApiUrl(event.target.value)} />,
          )}
          {renderPanelRow(
            'WebSocket URL',
            '後端即時資料 WebSocket 連線位置。',
            <input value={webSocketUrl} onChange={(event) => setWebSocketUrl(event.target.value)} />,
          )}
          {renderPanelRow(
            'AI Coach WebSocket URL',
            'AI Coach 遠端服務 WebSocket 連線位置。',
            <input value={coachWebSocketUrl} onChange={(event) => setCoachWebSocketUrl(event.target.value)} />,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">開發者工具</h3>
        <p className="settings-section-desc">只顯示與撞球分析除錯相關的進階資料。</p>
        <div className="settings-panel">
          {renderPanelRow(
            '顯示進階數據監控',
            '開啟後，進階監控資料會直接顯示在一般設定下方。',
            renderToggle(isDevMode, onDevModeChange, '顯示進階數據監控'),
          )}
        </div>
      </section>

      {isDevMode && renderAdvancedMonitoring()}
    </>
  );

  const renderAppearance = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">介面</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '介面主題',
            '選擇控制台的顯示主題。',
            <select
              value={themeMode}
              onChange={(event) => onThemeModeChange(event.target.value as ThemeMode)}
            >
              <option value="dark">深色</option>
              <option value="light">淺色</option>
              <option value="system">跟隨系統</option>
            </select>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">球桌風格</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '目前顏色',
            '依照後端 config 的桌布顏色預設選擇。',
            renderTableColorSelector(),
          )}
          {renderPanelRow(
            '自動檢測顏色',
            '從目前即時影像比對桌布顏色並記住結果。',
            <button className="settings-button secondary" type="button" onClick={handleAutoDetectTableColor}>
              自動檢測
            </button>,
          )}
          {renderPanelRow(
            '自訂顏色',
            '輸入桌布 HSV 範圍，適合特殊布色或光源。',
            renderCustomTableColorControls(),
          )}
        </div>
      </section>
    </>
  );

  const renderCamera = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">設備管理</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '攝影機切換',
            '選擇目前要使用的影像來源。',
            <select value={cameraDevice} onChange={(event) => setCameraDevice(event.target.value)}>
              <option value="camera-0">Camera 0</option>
              <option value="camera-1">Camera 1</option>
              <option value="obs-virtual">OBS Virtual Camera</option>
            </select>,
          )}
          {renderPanelRow(
            '重新讀取設備',
            '重新掃描可用攝影機清單。',
            <button className="settings-button secondary" type="button">重新讀取設備</button>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">環境光線</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '光源 Profile',
            '依照現場燈光選擇相機參數預設。',
            <select value={lightingProfile} onChange={(event) => setLightingProfile(event.target.value)}>
              <option value="warm">暖光</option>
              <option value="white">白光</option>
              <option value="low-light">低光源</option>
            </select>,
          )}
          {renderPanelRow(
            '進階相機參數',
            '在下方顯示預覽與參數調整。',
            <button
              className="settings-button primary"
              type="button"
              onClick={() => setIsCameraParamsOpen((current) => !current)}
              aria-expanded={isCameraParamsOpen}
            >
              {isCameraParamsOpen ? '收合參數' : '進階相機參數'}
            </button>,
          )}
        </div>
        {isCameraParamsOpen && (
          <div className="settings-inline-camera-params">
            <CameraParamsPage inline />
          </div>
        )}
      </section>
    </>
  );

  const renderTableCalibration = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">AI 教練範圍檢測</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '校正狀態',
            '目前球桌四點 ROI 是否已建立。',
            <span className={`settings-status ${roiConfigured ? 'ok' : 'bad'}`}>
              {roiConfigured ? '已校正' : '未校正'}
            </span>,
          )}
          {renderPanelRow(
            '座標摘要',
            '四個球桌內角的目前座標。',
            <code>{roiConfigured ? 'P1 (120, 96) P2 (1820, 96) P3 (1810, 980) P4 (130, 980)' : '尚未設定'}</code>,
          )}
          {renderPanelRow(
            '開始四點校正',
            '進入四點選取流程並更新 ROI 狀態。',
            <button className="settings-button primary" type="button" onClick={() => setRoiConfigured(true)}>
              開始四點校正
            </button>,
          )}
          {renderPanelRow(
            '啟用 Mask',
            '啟用後會遮住球桌外區域。',
            renderToggle(roiMaskEnabled, setRoiMaskEnabled, '啟用 Mask'),
          )}
          {renderPanelRow(
            '清除 ROI',
            '移除目前四點校正資料。',
            <button className="settings-button danger" type="button" onClick={() => setRoiConfigured(false)}>
              清除 ROI
            </button>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">硬體輔助校正</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '顏色校正',
            '開啟顏色標定與預設檔管理。',
            <button className="settings-button secondary" type="button" onClick={() => onNavigate?.('color-calibration')}>
              顏色校正
            </button>,
          )}
          {renderPanelRow(
            '投影機校正',
            '開啟投影機與相機座標校正流程。',
            <button className="settings-button secondary" type="button" onClick={() => onNavigate?.('calibration')}>
              投影機校正
            </button>,
          )}
        </div>
      </section>
    </>
  );

  const renderTableCalibrationV2 = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">球桌 ROI 微調</h3>
        <p className="settings-section-desc">先由 HSV 自動框出球桌，再微調框線邊界；AI Coach 會使用調整後的 table_roi。</p>
        <div className="settings-panel">
          {renderPanelRow('HSV 原始 ROI', '尚未套用微調前的偵測框。', <code>{formatRoi(tableRoiRaw)}</code>)}
          {renderPanelRow('調整後 ROI', '目前實際用於球桌框、球洞與 AI Coach 資料的範圍。', <code>{formatRoi(tableRoiAdjusted)}</code>)}
          {renderPanelRow('偵測狀態', '目前球桌 ROI 來源。', <strong>{tableRoiStatus}</strong>)}
          {renderPanelRow('左邊界', '負值往左，正值往右。', renderRoiAdjustmentControl('left'))}
          {renderPanelRow('上邊界', '負值往上，正值往下。', renderRoiAdjustmentControl('top'))}
          {renderPanelRow('右邊界', '負值往左，正值往右。', renderRoiAdjustmentControl('right'))}
          {renderPanelRow('下邊界', '負值往上，正值往下。', renderRoiAdjustmentControl('bottom'))}
          {renderPanelRow(
            '重設微調',
            '將四個邊界微調值全部歸零。',
            <button className="settings-button secondary" type="button" onClick={resetRoiAdjustment}>
              重設
            </button>,
          )}
        </div>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">球色與投影校正</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '顏色校正',
            '開啟子球顏色標定與預設檔管理。',
            <button className="settings-button secondary" type="button" onClick={() => onNavigate?.('color-calibration')}>
              顏色校正
            </button>,
          )}
          {renderPanelRow(
            '投影機校正',
            '開啟投影機與相機對位校正。',
            <button className="settings-button secondary" type="button" onClick={() => onNavigate?.('calibration')}>
              投影機校正
            </button>,
          )}
        </div>
      </section>
    </>
  );

  const renderTracking = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">運算品質</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '影像品質',
            '選擇追蹤與分析流程的計算品質。',
            <select value={quality} onChange={(event) => setQuality(event.target.value)}>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">變更儲存</h3>
        <div className="settings-panel">
          {renderPanelRow(
            '儲存設定',
            '目前僅將設定暫存於本機 UI。',
            <button className="settings-button primary" type="button" onClick={saveLocalSettings}>
              儲存設定
            </button>,
          )}
        </div>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>
    </>
  );

  const renderAdvancedMonitoring = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">Session 狀態</h3>
        <div className="settings-panel">
          {renderPanelRow(
            'Session ID',
            '目前前端連線使用的 Session。',
            <span className="settings-copy-row">
              <code>{session?.session_id || '尚未建立'}</code>
              <button className="settings-button compact" type="button" onClick={copySessionId} disabled={!session?.session_id}>
                複製
              </button>
            </span>,
          )}
          {renderPanelRow('使用者角色', '目前 Session 的角色。', <strong>{session?.role || 'N/A'}</strong>)}
          {renderPanelRow('串流通道', '目前連線的 Stream ID。', <strong>{session?.stream_id || 'N/A'}</strong>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">效能 Metadata</h3>
        <div className="settings-metric-grid">
          <div>
            <span>即時 FPS</span>
            <strong>{metadata?.rate_hz?.toFixed(1) || '0.0'}</strong>
          </div>
          <div>
            <span>Frame ID</span>
            <strong>{metadata?.frame_id ?? 0}</strong>
          </div>
          <div>
            <span>Tracking State</span>
            <strong>{metadata?.tracking_state || 'Idle'}</strong>
          </div>
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">原始數據</h3>
        <div className="settings-panel">
          {renderPanelRow('偵測球數', '目前 frame 中偵測到的球數。', <strong>{metadata?.detected_count ?? 0}</strong>)}
          {renderPanelRow('AR Path 數量', '目前規劃出的 AR 路徑數。', <strong>{metadata?.ar_paths?.length || 0}</strong>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">Cue 數據</h3>
        <div className="settings-metric-grid">
          <div>
            <span>偵測狀態</span>
            <strong>{cueSummary.detected ? 'Detected' : 'None'}</strong>
          </div>
          <div>
            <span>YOLO Cue</span>
            <strong>{cueSummary.rawCueCount}</strong>
          </div>
          <div>
            <span>Laser Only</span>
            <strong>{cueSummary.laserOnly ? 'ON' : 'OFF'}</strong>
          </div>
        </div>
        <div className="settings-panel settings-panel-followup">
          {renderPanelRow(
            'Cue bbox',
            '球桿在監控畫面座標中的外框。',
            <strong>
              {cueSummary.box
                ? `x ${formatMetricNumber(cueSummary.box[0], 0)}, y ${formatMetricNumber(cueSummary.box[1], 0)}, w ${formatMetricNumber(cueSummary.box[2], 0)}, h ${formatMetricNumber(cueSummary.box[3], 0)}`
                : '-'}
            </strong>,
          )}
          {renderPanelRow('Cue 中心點', '由 bbox 推算的球桿中心座標。', <strong>{formatPoint(cueSummary.center)}</strong>)}
          {renderPanelRow(
            'Cue 信心值',
            'raw YOLO cue box 中最高的信心值。',
            <strong>{cueSummary.bestConfidence == null ? '-' : formatMetricNumber(cueSummary.bestConfidence, 3)}</strong>,
          )}
          {renderPanelRow(
            'Laser 主線',
            'cue_laser_line 的第一組端點。',
            <strong>
              {cueSummary.primaryLine
                ? `${formatPoint(cueSummary.primaryLine[0])} -> ${formatPoint(cueSummary.primaryLine[1])}`
                : '-'}
            </strong>,
          )}
          {renderPanelRow(
            'Laser 長度 / 角度',
            '主線的像素長度與影像座標角度。',
            <strong>
              {cueSummary.lineLength == null || cueSummary.lineAngle == null
                ? '-'
                : `${formatMetricNumber(cueSummary.lineLength, 1)} px / ${formatMetricNumber(cueSummary.lineAngle, 1)} deg`}
            </strong>,
          )}
          {renderPanelRow(
            'Cue axis',
            '追蹤器估計的球桿軸線端點。',
            <strong>
              {cueSummary.axisStart && cueSummary.axisEnd
                ? `${formatPoint(cueSummary.axisStart)} -> ${formatPoint(cueSummary.axisEnd)}`
                : '-'}
            </strong>,
          )}
          {renderPanelRow(
            'Laser 反向線',
            '若後端有輸出第二組端點，這裡會顯示反向延伸線。',
            <strong>
              {cueSummary.reverseLine
                ? `${formatPoint(cueSummary.reverseLine[0])} -> ${formatPoint(cueSummary.reverseLine[1])}`
                : '-'}
            </strong>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">原始偵測摘要</h3>
        <pre className="settings-json-block">{rawDetectionSummary || '[]'}</pre>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>
    </>
  );

  const renderContent = () => {
    void renderTableCalibration;
    switch (activeTab) {
      case 'appearance':
        return renderAppearance();
      case 'camera':
        return renderCamera();
      case 'table-calibration':
        return renderTableCalibrationV2();
      case 'tracking':
        return renderTracking();
      case 'advanced-monitoring':
        return renderGeneral();
      case 'general':
      default:
        return renderGeneral();
    }
  };

  return (
    <div className="settings-page">
      <h2 className="page-title">{activeTab === 'advanced-monitoring' ? tabTitles.general : tabTitles[activeTab]}</h2>
      {renderContent()}
    </div>
  );
};

export default SettingsPage;
