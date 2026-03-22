import React, { useEffect, useMemo, useState } from 'react';

type ModeType = 'pool' | 'snooker';

interface ProfileSummary {
  id: number;
  mode: ModeType;
  name: string;
  created_at?: string;
  updated_at?: string;
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

interface ListResponse {
  mode: ModeType;
  system_colors: string[];
  profiles: ProfileSummary[];
}

interface DetailResponse {
  profile: ProfileDetail;
  system_colors: string[];
}

interface CalibrationState {
  profile_id: number | null;
  profile_name: string | null;
  mode: string | null;
  applied_at: string | null;
}

const emptyMapping = (): MappingItem => ({
  actual_label: '',
  hsv_lower: [0, 0, 0],
  hsv_upper: [180, 255, 255],
});

const clamp = (v: number, min: number, max: number): number => {
  if (!Number.isFinite(v)) return min;
  return Math.max(min, Math.min(max, Math.round(v)));
};

const normTriplet = (arr: number[]): number[] => {
  const [a = 0, b = 0, c = 0] = arr;
  return [clamp(a, 0, 180), clamp(b, 0, 255), clamp(c, 0, 255)];
};

const ColorCalibrationPanel: React.FC = () => {
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

  const [mode, setMode] = useState<ModeType>('pool');
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [systemColors, setSystemColors] = useState<string[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [selectedProfileName, setSelectedProfileName] = useState<string>('');
  const [mappings, setMappings] = useState<MappingDict>({});
  const [newProfileName, setNewProfileName] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>('');
  const [appliedState, setAppliedState] = useState<CalibrationState>({
    profile_id: null,
    profile_name: null,
    mode: null,
    applied_at: null,
  });

  const selectedProfile = useMemo(
    () => profiles.find((p) => p.id === selectedProfileId) || null,
    [profiles, selectedProfileId],
  );

  const fetchAppliedState = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/color-calibration/state`);
      if (!res.ok) return;
      const data = await res.json();
      if (data?.state) {
        setAppliedState(data.state as CalibrationState);
      }
    } catch {
      // ignore state fetch errors
    }
  };

  const fetchProfiles = async (targetMode: ModeType) => {
    const res = await fetch(`${backendUrl}/api/color-calibration/profiles?mode=${targetMode}`);
    if (!res.ok) {
      throw new Error('載入校正設定檔失敗');
    }
    const data: ListResponse = await res.json();
    setProfiles(data.profiles || []);
    setSystemColors(data.system_colors || []);
  };

  const fetchProfileDetail = async (profileId: number) => {
    const res = await fetch(`${backendUrl}/api/color-calibration/profiles/${profileId}`);
    if (!res.ok) {
      throw new Error('載入設定檔內容失敗');
    }
    const data: DetailResponse = await res.json();
    const profile = data.profile;
    setSelectedProfileId(profile.id);
    setSelectedProfileName(profile.name || '');

    const nextMappings: MappingDict = {};
    const colors = data.system_colors || systemColors;
    colors.forEach((color) => {
      const cfg = profile.mappings?.[color];
      nextMappings[color] = {
        actual_label: cfg?.actual_label || '',
        hsv_lower: cfg?.hsv_lower && cfg.hsv_lower.length === 3 ? cfg.hsv_lower : [0, 0, 0],
        hsv_upper: cfg?.hsv_upper && cfg.hsv_upper.length === 3 ? cfg.hsv_upper : [180, 255, 255],
      };
    });
    setMappings(nextMappings);
    setSystemColors(colors);
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
      } catch (err) {
        setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, [mode]);

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

  const handleSelectProfile = async (profileId: number) => {
    setIsLoading(true);
    setMessage('');
    try {
      await fetchProfileDetail(profileId);
      setMessage('✓ 已載入設定檔');
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : '未知錯誤'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const updateMapping = (color: string, key: 'actual_label' | 'hsv_lower' | 'hsv_upper', value: string | number, index?: number) => {
    setMappings((prev) => {
      const cur = prev[color] || emptyMapping();
      if (key === 'actual_label') {
        return {
          ...prev,
          [color]: {
            ...cur,
            actual_label: String(value),
          },
        };
      }

      const arr = [...cur[key]];
      if (index === undefined) return prev;
      arr[index] = Number(value);

      const fixed = [
        clamp(arr[0], 0, 180),
        clamp(arr[1], 0, 255),
        clamp(arr[2], 0, 255),
      ];

      return {
        ...prev,
        [color]: {
          ...cur,
          [key]: fixed,
        },
      };
    });
  };

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
      setMessage(`✓ 已套用設定檔，更新 ${data.applied ?? 0} 個顏色模板`);
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
      const res = await fetch(`${backendUrl}/api/color-calibration/reset`, {
        method: 'POST',
      });
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

  return (
    <div className="settings-content">
      <div className="setting-section">
        <p className="setting-desc">目前套用中的設定檔</p>
        <div className="applied-profile-box">
          <div><strong>名稱：</strong>{appliedState.profile_name || '未套用'}</div>
          <div><strong>模式：</strong>{appliedState.mode || '-'}</div>
          <div><strong>時間：</strong>{appliedState.applied_at || '-'}</div>
        </div>
      </div>

      <div className="setting-row">
        <span className="setting-label">球種模式</span>
        <div className="color-mode-switch">
          <button
            className={`mode-btn ${mode === 'pool' ? 'active' : ''}`}
            onClick={() => setMode('pool')}
            disabled={isLoading}
          >
            花式
          </button>
          <button
            className={`mode-btn ${mode === 'snooker' ? 'active' : ''}`}
            onClick={() => setMode('snooker')}
            disabled={isLoading}
          >
            斯諾克
          </button>
        </div>
      </div>

      <div className="setting-section">
        <p className="setting-desc">設定檔</p>
        <div className="color-profile-row">
          <select
            className="profile-select"
            value={selectedProfileId ?? ''}
            onChange={(e) => {
              const v = Number(e.target.value);
              if (v > 0) handleSelectProfile(v);
            }}
            disabled={isLoading}
          >
            <option value="">請選擇設定檔</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <input
            className="profile-input"
            type="text"
            placeholder="新增設定檔名稱"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            disabled={isLoading}
          />
          <button className="btn btn-secondary" onClick={handleCreateProfile} disabled={isLoading}>
            新增
          </button>
        </div>
      </div>

      {selectedProfile && (
        <div className="setting-section">
          <p className="setting-desc">顏色配對：{selectedProfileName}</p>
          <div className="calibration-table-wrap">
            <table className="calibration-table">
              <thead>
                <tr>
                  <th>系統顏色</th>
                  <th>實際顏色名稱</th>
                  <th>HSV Lower (H/S/V)</th>
                  <th>HSV Upper (H/S/V)</th>
                </tr>
              </thead>
              <tbody>
                {systemColors.map((color) => {
                  const cfg = mappings[color] || emptyMapping();
                  return (
                    <tr key={color}>
                      <td>{color}</td>
                      <td>
                        <input
                          type="text"
                          className="mini-input"
                          value={cfg.actual_label}
                          onChange={(e) => updateMapping(color, 'actual_label', e.target.value)}
                        />
                      </td>
                      <td>
                        <div className="hsv-grid">
                          {[0, 1, 2].map((idx) => (
                            <input
                              key={`l-${idx}`}
                              type="number"
                              className="hsv-input"
                              min={0}
                              max={idx === 0 ? 180 : 255}
                              value={cfg.hsv_lower[idx]}
                              onChange={(e) => updateMapping(color, 'hsv_lower', Number(e.target.value), idx)}
                            />
                          ))}
                        </div>
                      </td>
                      <td>
                        <div className="hsv-grid">
                          {[0, 1, 2].map((idx) => (
                            <input
                              key={`u-${idx}`}
                              type="number"
                              className="hsv-input"
                              min={0}
                              max={idx === 0 ? 180 : 255}
                              value={cfg.hsv_upper[idx]}
                              onChange={(e) => updateMapping(color, 'hsv_upper', Number(e.target.value), idx)}
                            />
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="calibration-actions">
            <button className="btn btn-primary" onClick={handleSaveMappings} disabled={isLoading}>儲存到資料庫</button>
            <button className="btn btn-secondary" onClick={handleApplyProfile} disabled={isLoading}>套用到系統顏色</button>
            <button className="btn btn-secondary" onClick={handleResetToDefault} disabled={isLoading}>一鍵回復預設模板</button>
          </div>
        </div>
      )}

      {message && (
        <div className={`setting-message ${message.startsWith('✓') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}
    </div>
  );
};

export default ColorCalibrationPanel;
