import React, { useEffect, useMemo, useState } from 'react';
import './ColorCalibrationPage.css';

type ModeType = 'pool' | 'snooker';
type WizardStep = 'profile-select' | 'scan';

interface ProfileSummary {
  id: number;
  mode: ModeType;
  name: string;
}

interface MappingItem {
  actual_label: string;
  hsv_lower: number[];
  hsv_upper: number[];
}

type MappingDict = Record<string, MappingItem>;

interface ProfileDetail {
  id: number;
  mode: ModeType;
  name: string;
  mappings?: MappingDict;
}

interface CalibrationState {
  profile_id: number | null;
  profile_name: string | null;
  mode: string | null;
  applied_at: string | null;
}

interface AutoScanItem {
  index: number;
  bbox: { x: number; y: number; w: number; h: number };
  roi: { x: number; y: number; w: number; h: number };
  detected_number?: number;
  detected_label?: string;
  hsv_center: number[];
  hsv_lower: number[];
  hsv_upper: number[];
  rgb_center: number[];
}

interface ColorCalibrationPageProps {
  onBack?: () => void;
  burninUrl?: string;
}

const emptyMapping = (): MappingItem => ({
  actual_label: '',
  hsv_lower: [0, 0, 0],
  hsv_upper: [0, 0, 0],
});

const clamp = (v: number, min: number, max: number): number => {
  if (!Number.isFinite(v)) return min;
  return Math.max(min, Math.min(max, Math.round(v)));
};

const normTriplet = (arr: number[]): number[] => {
  const [a = 0, b = 0, c = 0] = arr;
  return [clamp(a, 0, 180), clamp(b, 0, 255), clamp(c, 0, 255)];
};

const getColorStyle = (colorName: string) => {
  switch (colorName.toLowerCase()) {
    case 'yellow': return { bg: '#eab308', text: '#000' };
    case 'blue': return { bg: '#2563eb', text: '#fff' };
    case 'red': return { bg: '#dc2626', text: '#fff' };
    case 'purple': return { bg: '#9333ea', text: '#fff' };
    case 'orange': return { bg: '#f97316', text: '#fff' };
    case 'green': return { bg: '#16a34a', text: '#fff' };
    case 'brown': return { bg: '#78350f', text: '#fff' };
    case 'black': return { bg: '#171717', text: '#fff' };
    case 'white': return { bg: '#ffffff', text: '#000' };
    default: return { bg: '#fbbf24', text: '#000' }; // fallback
  }
};

const ColorCalibrationPage: React.FC<ColorCalibrationPageProps> = ({ onBack, burninUrl }) => {
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

  // Wizard 步驟
  const [wizardStep, setWizardStep] = useState<WizardStep>('profile-select');

  // 設定檔列表與選擇
  const [mode, setMode] = useState<ModeType>('pool');
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [systemColors, setSystemColors] = useState<string[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [selectedProfileName, setSelectedProfileName] = useState<string>('');
  const [mappings, setMappings] = useState<MappingDict>({});
  const [newProfileName, setNewProfileName] = useState<string>('');

  // 套用狀態
  const [appliedState, setAppliedState] = useState<CalibrationState>({
    profile_id: null,
    profile_name: null,
    mode: null,
    applied_at: null,
  });

  // 掃描流程
  const [currentStepIdx, setCurrentStepIdx] = useState<number>(0);
  
  // 掃描的暫存狀態 (針對單一顏色)
  const [scannedHsvLower, setScannedHsvLower] = useState<number[]>([0, 0, 0]);
  const [scannedHsvUpper, setScannedHsvUpper] = useState<number[]>([180, 255, 255]);
  const [hasScannedCurrent, setHasScannedCurrent] = useState<boolean>(false);
  const [currentScan, setCurrentScan] = useState<AutoScanItem | null>(null);

  // UI 狀態
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((p) => p.id === selectedProfileId) || null,
    [profiles, selectedProfileId],
  );

  const currentTargetColor = systemColors.length > 0 && currentStepIdx < systemColors.length ? systemColors[currentStepIdx] : '';
  const totalSteps = systemColors.length;
  const isAllDone = systemColors.length > 0 && currentStepIdx >= systemColors.length;

  useEffect(() => {
    // 當 currentStepIdx 改變時，自動從目前的預設 mappings 帶入 HSV，以供修改與檢視
    if (systemColors.length > 0 && currentStepIdx < systemColors.length) {
      const color = systemColors[currentStepIdx];
      const existing = mappings[color] || emptyMapping();
      setScannedHsvLower([...existing.hsv_lower]);
      setScannedHsvUpper([...existing.hsv_upper]);
      setHasScannedCurrent(false);
      setCurrentScan(null);
    }
  }, [currentStepIdx, systemColors]); // 不依存 mappings，以免手動修改時重設

  // ---------- API 呼叫 ----------

  const fetchAppliedState = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/state`);
      if (!res.ok) return;
      const data = await res.json();
      if (data?.state) setAppliedState(data.state as CalibrationState);
    } catch {
      // ignore
    }
  };

  const fetchProfiles = async (targetMode: ModeType) => {
    const res = await fetch(`${backendUrl}/api/color-calibration/profiles?mode=${targetMode}`);
    if (!res.ok) throw new Error('載入校正設定檔失敗');
    const data = await res.json();
    const colors = (data.system_colors || []) as string[];
    setProfiles((data.profiles || []) as ProfileSummary[]);
    setSystemColors(colors);
    setMappings((prev) => {
      const next = { ...prev };
      colors.forEach((c) => {
        if (!next[c]) next[c] = emptyMapping();
      });
      return next;
    });
  };

  const fetchProfileDetail = async (profileId: number) => {
    const res = await fetch(`${backendUrl}/api/color-calibration/profiles/${profileId}`);
    if (!res.ok) throw new Error('載入設定檔內容失敗');
    const data = await res.json();
    const profile = data.profile as ProfileDetail;
    const colors = (data.system_colors || systemColors) as string[];

    setSelectedProfileId(profile.id);
    setSelectedProfileName(profile.name || '');
    setSystemColors(colors);

    const nextMappings: MappingDict = {};
    colors.forEach((color) => {
      const cfg = profile.mappings?.[color];
      nextMappings[color] = {
        actual_label: cfg?.actual_label || '',
        hsv_lower: cfg?.hsv_lower?.length === 3 ? cfg.hsv_lower : [0, 0, 0],
        hsv_upper: cfg?.hsv_upper?.length === 3 ? cfg.hsv_upper : [180, 255, 255],
      };
    });
    setMappings(nextMappings);
    // 不在此重設掃描，避免在掃描中儲存設定檔時畫面跳回第一顆
  };

  const resetScan = () => {
    setCurrentStepIdx(0);
    setHasScannedCurrent(false);
    setCurrentScan(null);
  };

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      setMessage('');
      try {
        await fetchProfiles(mode);
        await fetchAppliedState();
        setSelectedProfileId(null);
        setSelectedProfileName('');
        setMappings({});
        resetScan();
      } catch (err) {
        setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, [mode]);

  // ---------- 設定檔操作 ----------

  const handleCreateProfile = async () => {
    if (!newProfileName.trim()) {
      setMessage('✗ 請先輸入設定檔名稱');
      return;
    }
    setIsLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, name: newProfileName.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '建立設定檔失敗');
      }
      const data = await res.json();
      const id: number = data.profile.id;
      await fetchProfiles(mode);
      await fetchProfileDetail(id);
      setNewProfileName('');
      setMessage('✓ 設定檔已建立');
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteProfile = async (profileId: number) => {
    setIsLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/profiles/${profileId}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '刪除失敗');
      }
      await fetchProfiles(mode);
      if (selectedProfileId === profileId) {
        setSelectedProfileId(null);
        setSelectedProfileName('');
        setMappings({});
        resetScan();
      }
      setDeleteConfirmId(null);
      setMessage('✓ 設定檔已刪除');
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  // ---------- 掃描流程 ----------

  const handleEnterScan = async () => {
    if (!selectedProfileId) {
      setMessage('✗ 請先選擇設定檔');
      return;
    }
    setWizardStep('scan');
    setMessage('');
    resetScan();
  };

  const handleAutoScanStart = async () => {
    if (!selectedProfileId) {
      setMessage('✗ 請先選擇設定檔');
      return;
    }
    setIsLoading(true);
    setMessage('掃描中...');
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/auto-scan?mode=${mode}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '自動掃描失敗');
      }
      const data = await res.json();
      const scans = (data.scans || []) as AutoScanItem[];
      if (scans.length === 0) {
        throw new Error('未偵測到任何球體，請將球放到畫面中並確保亮度充足');
      }
      
      // 取出最明顯的一顆 (預設 auto-scan 會找出畫面上所有的，這裡優先取第一顆)
      const scan = scans[0];
      setScannedHsvLower([...scan.hsv_lower]);
      setScannedHsvUpper([...scan.hsv_upper]);
      setCurrentScan(scan);
      setHasScannedCurrent(true);
      setMessage(`✓ 已掃描到球體，請確認數值無誤後點擊「確認並下一個顏色」`);
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAcceptAndNext = () => {
    if (!currentTargetColor) return;

    setMappings((prev) => {
      const cur = prev[currentTargetColor] || emptyMapping();
      return {
        ...prev,
        [currentTargetColor]: {
          ...cur,
          hsv_lower: [clamp(scannedHsvLower[0], 0, 180), clamp(scannedHsvLower[1], 0, 255), clamp(scannedHsvLower[2], 0, 255)],
          hsv_upper: [clamp(scannedHsvUpper[0], 0, 180), clamp(scannedHsvUpper[1], 0, 255), clamp(scannedHsvUpper[2], 0, 255)],
        },
      };
    });

    const next = currentStepIdx + 1;
    setCurrentStepIdx(next);
    setHasScannedCurrent(false);
    
    if (next >= totalSteps) {
      setMessage('✓ 已完成所有球體參數設定');
    } else {
      setMessage(`✓ 已寫入 ${currentTargetColor}，請換下一個顏色的球 (${systemColors[next]})`);
    }
  };

  const handleSkipNext = () => {
    if (!currentTargetColor) return;
    
    const next = currentStepIdx + 1;
    setCurrentStepIdx(next);
    setHasScannedCurrent(false);
    
    if (next >= totalSteps) {
      setMessage('✓ 已完成所有球體參數設定');
    } else {
      setMessage(`略過 ${currentTargetColor}，請進行下一個 (${systemColors[next]})`);
    }
  };

  const handlePrevStep = () => {
    if (currentStepIdx > 0) {
      setCurrentStepIdx(prev => prev - 1);
      setMessage('回上一顆');
    }
  };

  // ---------- 儲存 / 套用 ----------

  const handleSaveMappings = async () => {
    if (!selectedProfileId) {
      setMessage('✗ 請先選擇設定檔');
      return;
    }
    const payload: MappingDict = {};
    systemColors.forEach((color) => {
      const cfg = mappings[color] || emptyMapping();
      payload[color] = {
        actual_label: cfg.actual_label,
        hsv_lower: normTriplet(cfg.hsv_lower),
        hsv_upper: normTriplet(cfg.hsv_upper),
      };
    });
    setIsLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/profiles/${selectedProfileId}/mappings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mappings: payload }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '儲存失敗');
      }
      await fetchProfileDetail(selectedProfileId);
      setMessage('✓ HSV 配對已儲存');
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApplyProfile = async () => {
    if (!selectedProfileId) {
      setMessage('✗ 請先選擇設定檔');
      return;
    }
    setIsLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: selectedProfileId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '套用失敗');
      }
      const data = await res.json();
      await fetchAppliedState();
      setMessage(`✓ 已套用設定檔，更新 ${data.applied ?? 0} 個顏色模板。即將返回列表...`);
      setTimeout(() => {
        setWizardStep('profile-select');
        setMessage('');
      }, 1500);
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetToDefault = async () => {
    setIsLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/reset`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '回復預設失敗');
      }
      await fetchAppliedState();
      setMessage('✓ 已回復系統預設模板');
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  // ---------- 渲染 ----------

  const renderMessage = () =>
    message ? (
      <div className={`cc-message ${message.startsWith('✓') ? 'success' : 'error'}`}>{message}</div>
    ) : null;

  // Stage 1：選擇設定檔
  const renderProfileSelect = () => (
    <div className="cc-profile-stage">
      {/* 目前套用狀態 */}
      <div className="cc-applied-bar">
        <span className="cc-applied-label">目前套用：</span>
        <span className="cc-applied-value">
          {appliedState.profile_name
            ? `${appliedState.profile_name}（${appliedState.mode || '-'}）`
            : '未套用任何設定檔'}
        </span>
        {appliedState.applied_at && (
          <span className="cc-applied-time">{appliedState.applied_at}</span>
        )}
      </div>

      {/* 模式切換 */}
      <div className="cc-section">
        <div className="cc-section-title">球種模式</div>
        <div className="cc-mode-row">
          <button
            className={`cc-mode-btn ${mode === 'pool' ? 'active' : ''}`}
            onClick={() => setMode('pool')}
            disabled={isLoading}
          >
            花式撞球
          </button>
          <button
            className={`cc-mode-btn ${mode === 'snooker' ? 'active' : ''}`}
            onClick={() => setMode('snooker')}
            disabled={isLoading}
          >
            斯諾克
          </button>
        </div>
      </div>

      {/* 設定檔列表 */}
      <div className="cc-section">
        <div className="cc-section-title">設定檔列表</div>
        {profiles.length === 0 ? (
          <p className="cc-hint">目前無設定檔，請新增一個。</p>
        ) : (
          <div className="cc-profile-list">
            {profiles.map((p) => (
              <div
                key={p.id}
                className={`cc-profile-item ${selectedProfileId === p.id ? 'selected' : ''}`}
                onClick={() => {
                  if (deleteConfirmId === p.id) return;
                  fetchProfileDetail(p.id).catch((err) =>
                    setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`),
                  );
                }}
              >
                <span className="cc-profile-name">{p.name}</span>
                {deleteConfirmId === p.id ? (
                  <div className="cc-delete-confirm">
                    <span>確定刪除？</span>
                    <button
                      className="cc-btn-danger-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteProfile(p.id);
                      }}
                      disabled={isLoading}
                    >
                      確定
                    </button>
                    <button
                      className="cc-btn-cancel-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirmId(null);
                      }}
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    className="cc-btn-delete-sm"
                    title="刪除設定檔"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirmId(p.id);
                    }}
                    disabled={isLoading}
                  >
                    刪除
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 新增設定檔 */}
      <div className="cc-section">
        <div className="cc-section-title">新增設定檔</div>
        <div className="cc-new-profile-row">
          <input
            className="cc-input"
            type="text"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreateProfile()}
            placeholder="輸入設定檔名稱"
            disabled={isLoading}
          />
          <button className="btn btn-secondary" onClick={handleCreateProfile} disabled={isLoading}>
            新增
          </button>
        </div>
      </div>

      {renderMessage()}

      {/* 進入掃描 */}
      <div className="cc-stage-footer">
        <button
          className="btn btn-primary cc-enter-btn"
          onClick={handleEnterScan}
          disabled={isLoading || !selectedProfile}
        >
          {selectedProfile ? `進入掃描 — ${selectedProfileName}` : '請先選擇設定檔'}
        </button>
        <div className="cc-reset-row">
          <button className="cc-link-btn" onClick={handleResetToDefault} disabled={isLoading}>
            一鍵回復系統預設模板
          </button>
        </div>
      </div>
    </div>
  );

  // Stage 2：掃描
  const renderScan = () => {
    return (
      <div className="cc-scan-stage">
        {/* 左側：相機畫面與快速總覽 */}
        <div className="cc-camera-panel">
          <div className="cc-camera-label">相機參考畫面</div>
          <img
            src={burninUrl || `${backendUrl}/burnin/camera1.mjpg?quality=med`}
            alt="camera stream"
            className="cc-camera-img"
          />
          
          <div className="cc-summary-list-container" style={{ marginTop: '1rem', background: '#222', padding: '10px', borderRadius: 6 }}>
            <div style={{ margin: '0 0 10px 0', color: '#fbbf24', borderBottom: '1px solid #444', paddingBottom: '5px', fontWeight: 'bold' }}>
              所有顏色 HSV 設定總覽 <span style={{fontSize: '0.8rem', color: '#9ca3af', fontWeight: 'normal'}}>(點選項目可跳轉重新設定)</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '8px' }}>
              {systemColors.map(color => {
                const m = mappings[color] || emptyMapping();
                const isCurrent = color === currentTargetColor && !isAllDone;
                return (
                  <div 
                    key={color} 
                    onClick={() => {
                        const idx = systemColors.indexOf(color);
                        if (idx !== -1) {
                            setCurrentStepIdx(idx);
                            setHasScannedCurrent(false);
                            setCurrentScan(null);
                        }
                    }}
                    style={{ 
                        display: 'flex', flexDirection: 'column', padding: '6px', 
                        background: isCurrent ? '#374151' : '#1f2937', 
                        border: isCurrent ? '1px solid #fbbf24' : '1px solid #374151',
                        borderRadius: 4, cursor: 'pointer',
                        transition: 'all 0.2s'
                    }}
                  >
                    <div style={{ marginBottom: '4px', textAlign: 'center' }}>
                      <span style={{ 
                        background: getColorStyle(color).bg, color: getColorStyle(color).text, 
                        padding: '2px 8px', borderRadius: 4, fontSize: '0.85rem', fontWeight: 'bold',
                        textShadow: getColorStyle(color).text === '#fff' ? '0 1px 2px rgba(0,0,0,0.5)' : 'none'
                      }}>
                        {color}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#9ca3af', fontFamily: 'monospace', textAlign: 'center' }}>
                      L: {m.hsv_lower.join(', ')}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#9ca3af', fontFamily: 'monospace', textAlign: 'center' }}>
                      U: {m.hsv_upper.join(', ')}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 右側：操作面板 */}
        <div className="cc-control-panel">
          {/* 設定檔標題 */}
          <div className="cc-scan-profile-bar">
            <span className="cc-profile-tag">{selectedProfileName}</span>
            <span className="cc-mode-tag">{mode === 'pool' ? '花式' : '斯諾克'}</span>
          </div>

          {/* 開始掃描按鈕 / 進度 */}
          {isAllDone ? (
            // 完成狀態
            <div className="cc-done-box">
              <div className="cc-done-title">所有顏色設定完成</div>
              <p className="cc-hint" style={{ marginBottom: '1.5rem' }}>
                您的 HSV 設定已全數輸入完畢。<br/>
                您可以隨時「點擊左下方的顏色列表」退回編輯調整任何一顆球，或使用下方按鈕儲存 / 套用配置！
              </p>
              
              <div className="cc-done-actions" style={{ flexDirection: 'column', gap: '10px' }}>
                <button
                  className="btn btn-primary"
                  onClick={handleSaveMappings}
                  disabled={isLoading}
                  style={{ width: '100%', fontSize: '1.05rem', padding: '12px' }}
                >
                  儲存到資料庫
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={handleApplyProfile}
                  disabled={isLoading}
                  style={{ width: '100%', fontSize: '1.05rem', padding: '12px' }}
                >
                  套用到系統顏色
                </button>
              </div>
              {renderMessage()}
            </div>
          ) : (
            // 掃描中：逐顆引導操作
            <>
              {/* 進度條 */}
              <div className="cc-progress-wrap">
                <div className="cc-progress-label">
                  步驟 {currentStepIdx + 1} / {totalSteps}
                  {currentTargetColor && (
                    <span 
                      className="cc-target-color-badge" 
                      style={{ 
                        marginLeft: 10, 
                        background: getColorStyle(currentTargetColor).bg, 
                        color: getColorStyle(currentTargetColor).text, 
                        padding: '2px 8px', 
                        borderRadius: 4, 
                        fontWeight: 'bold',
                        textShadow: getColorStyle(currentTargetColor).text === '#fff' ? '0 1px 2px rgba(0,0,0,0.5)' : 'none'
                      }}>
                      {currentTargetColor}
                    </span>
                  )}
                </div>
                <div className="cc-progress-bar">
                  <div
                    className="cc-progress-fill"
                    style={{ width: `${totalSteps > 0 ? Math.round(((currentStepIdx) / totalSteps) * 100) : 0}%` }}
                  />
                </div>
              </div>

              <div className="cc-scan-start-area" style={{ marginBottom: '1rem', paddingBottom: '1rem' }}>
                <p className="cc-hint" style={{ fontSize: '0.95rem', color: '#fbbf24', marginBottom: '10px' }}>
                  請將 <strong>{currentTargetColor}</strong> 顏色的球放到畫面上，並點擊下方掃描 (將自動捕捉畫面球體的 HSV)：
                </p>
                <button
                  className="btn btn-primary"
                  onClick={handleAutoScanStart}
                  disabled={isLoading}
                  style={{ width: '100%', marginBottom: '10px', background: '#3b82f6', borderColor: '#3b82f6' }}
                >
                  {isLoading ? '掃描中...' : '掃描目前球體 (Auto Scan)'}
                </button>
                {hasScannedCurrent && <div style={{ color: '#10b981', fontSize: '0.85rem' }}>✓ 已成功抓取 HSV 範圍，確認無誤後請往下一步</div>}
                
                {currentScan && hasScannedCurrent && (
                  <div className="cc-swatch-section" style={{ marginTop: '10px' }}>
                     <div className="cc-ball-swatch" style={{ background: `rgb(${currentScan.rgb_center[0]}, ${currentScan.rgb_center[1]}, ${currentScan.rgb_center[2]})` }} />
                     <div className="cc-swatch-info">
                       <div className="cc-swatch-hsv">ROI 平均：{currentScan.hsv_center.join(', ')}</div>
                       {currentScan.detected_label && <div className="cc-swatch-yolo">YOLO：{currentScan.detected_label}</div>}
                     </div>
                  </div>
                )}
              </div>

              {/* HSV 微調 */}
              {currentTargetColor && (
                <div className="cc-hsv-section">
                  <div className="cc-hsv-group-title">HSV Lower（H/S/V）</div>
                  <div className="cc-hsv-row">
                    {[0, 1, 2].map((i) => (
                      <input
                        key={`l-${i}`}
                        className="cc-hsv-input"
                        type="number"
                        min={0}
                        max={i === 0 ? 180 : 255}
                        value={scannedHsvLower[i]}
                        onChange={(e) => {
                          const val = clamp(Number(e.target.value), 0, i === 0 ? 180 : 255);
                          setScannedHsvLower(prev => {
                            const arr = [...prev];
                            arr[i] = val;
                            return arr;
                          });
                        }}
                      />
                    ))}
                  </div>
                  <div className="cc-hsv-group-title" style={{ marginTop: 10 }}>HSV Upper（H/S/V）</div>
                  <div className="cc-hsv-row">
                    {[0, 1, 2].map((i) => (
                      <input
                        key={`u-${i}`}
                        className="cc-hsv-input"
                        type="number"
                        min={0}
                        max={i === 0 ? 180 : 255}
                        value={scannedHsvUpper[i]}
                        onChange={(e) => {
                          const val = clamp(Number(e.target.value), 0, i === 0 ? 180 : 255);
                          setScannedHsvUpper(prev => {
                            const arr = [...prev];
                            arr[i] = val;
                            return arr;
                          });
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* 操作按鈕 */}
              <div className="cc-scan-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button className="btn btn-primary cc-accept-btn" onClick={handleAcceptAndNext} style={{ flex: '1 1 100%' }}>
                  確認無誤，前往下一個顏色
                </button>
                <div style={{ display: 'flex', gap: '8px', width: '100%', marginTop: '5px' }}>
                  {currentStepIdx > 0 && (
                     <button className="btn btn-secondary" onClick={handlePrevStep} style={{ flex: 1 }}>
                       回上一顆
                     </button>
                  )}
                  <button className="btn btn-secondary" onClick={handleSkipNext} style={{ flex: 1 }}>
                    跳過此顏色
                  </button>
                </div>
              </div>

              {renderMessage()}
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="cc-wizard">
      {/* 頂部標題列 */}
      <div className="cc-header">
        <div className="cc-header-left">
          {wizardStep === 'scan' ? (
            <button
              className="btn btn-secondary cc-back-btn"
              onClick={() => {
                setWizardStep('profile-select');
                setMessage('');
              }}
            >
              ← 返回設定檔
            </button>
          ) : (
            onBack && (
              <button className="btn btn-secondary cc-back-btn" onClick={onBack}>
                ← 返回設定
              </button>
            )
          )}
          <h2 className="cc-title">顏色校正</h2>
        </div>

        {/* 步驟指示器 */}
        <div className="cc-steps">
          <div className={`cc-step ${wizardStep === 'profile-select' ? 'active' : 'done'}`}>
            <span className="cc-step-num">1</span>
            <span className="cc-step-label">選擇設定檔</span>
          </div>
          <div className="cc-step-connector" />
          <div className={`cc-step ${wizardStep === 'scan' ? 'active' : ''}`}>
            <span className="cc-step-num">2</span>
            <span className="cc-step-label">YOLO 自動掃描</span>
          </div>
        </div>
      </div>

      {/* 主要內容 */}
      <div className="cc-body">
        {wizardStep === 'profile-select' ? renderProfileSelect() : renderScan()}
      </div>
    </div>
  );
};

export default ColorCalibrationPage;

