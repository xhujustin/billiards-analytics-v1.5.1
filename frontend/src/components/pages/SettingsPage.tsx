import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { MetadataUpdatePayload, Session } from '../../sdk/types';
import {
  accentColorOptions,
  getAccentColorValue,
  getReadableTextColor,
  type AccentColorMode,
  type FontSizeMode,
  type ResolvedTheme,
  type ThemeMode,
} from '../../theme';
import { languageLabels, supportedLanguages, type SupportedLanguage } from '../../i18n/types';
import { CameraParamsPage } from './CameraParamsPage';
import { AutoCalibrationPage } from './AutoCalibrationPage';
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
  resolvedTheme: ResolvedTheme;
  accentColorMode: AccentColorMode;
  onAccentColorModeChange: (accentColorMode: AccentColorMode) => void;
  fontSizeMode: FontSizeMode;
  onFontSizeModeChange: (fontSizeMode: FontSizeMode) => void;
  language: SupportedLanguage;
  onLanguageChange: (language: SupportedLanguage) => void;
  streamQuality: StreamQuality;
  onStreamQualityChange: (quality: StreamQuality) => void;
  session?: Session | null;
  metadata?: MetadataUpdatePayload | null;
  apiBaseUrl?: string;
  aiCoachWsUrl?: string;
  burninUrl?: string;
  onNavigate?: (page: 'calibration' | 'camera-params' | 'color-calibration') => void;
}

const tabTitleKeys: Record<SettingsTab, string> = {
  general: 'settings.tabs.general',
  appearance: 'settings.tabs.appearance',
  camera: 'settings.tabs.camera',
  'table-calibration': 'settings.tabs.tableCalibration',
  tracking: 'settings.tabs.tracking',
  'advanced-monitoring': 'settings.tabs.advancedMonitoring',
};

const tablePresets = [
  { value: 'green', color: '#3d963d' },
  { value: 'gray', color: '#758082' },
  { value: 'blue', color: '#3d6699' },
  { value: 'pink', color: '#b347a0' },
  { value: 'purple', color: '#7a3d99' },
  { value: 'custom', color: '#3d963d' },
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

type RoiPoint = {
  x: number;
  y: number;
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

type SettingsSubView = 'main' | 'roi-editor' | 'color-editor' | 'projector-editor';
type StreamQuality = 'low' | 'med' | 'high';
type ColorCalibrationMode = 'pool' | 'snooker';

interface ColorCalibrationProfileSummary {
  id: number;
  mode: ColorCalibrationMode;
  name: string;
  created_at?: string;
  updated_at?: string;
}

interface ColorMappingItem {
  actual_label: string;
  hsv_lower: number[];
  hsv_upper: number[];
}

type ColorMappingDict = Record<string, ColorMappingItem>;

interface ColorCalibrationProfileDetail extends ColorCalibrationProfileSummary {
  mappings?: ColorMappingDict;
}

interface ColorAutoScanItem {
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

const emptyColorMapping = (): ColorMappingItem => ({
  actual_label: '',
  hsv_lower: [0, 0, 0],
  hsv_upper: [180, 255, 255],
});

const clampHsvValue = (value: number, min: number, max: number): number => {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, Math.round(value)));
};

const normalizeHsvTriplet = (values: number[]): number[] => {
  const [h = 0, s = 0, v = 0] = values;
  return [
    clampHsvValue(h, 0, 180),
    clampHsvValue(s, 0, 255),
    clampHsvValue(v, 0, 255),
  ];
};

const getBallColorStyle = (colorName: string) => {
  switch (colorName.toLowerCase()) {
    case 'yellow': return { bg: '#eab308', text: '#000000' };
    case 'blue': return { bg: '#2563eb', text: '#ffffff' };
    case 'red': return { bg: '#dc2626', text: '#ffffff' };
    case 'purple': return { bg: '#9333ea', text: '#ffffff' };
    case 'orange': return { bg: '#f97316', text: '#ffffff' };
    case 'green': return { bg: '#16a34a', text: '#ffffff' };
    case 'brown': return { bg: '#78350f', text: '#ffffff' };
    case 'black': return { bg: '#111111', text: '#ffffff' };
    case 'white': return { bg: '#ffffff', text: '#000000' };
    case 'pink': return { bg: '#ec4899', text: '#ffffff' };
    default: return { bg: '#fbbf24', text: '#000000' };
  }
};

export const SettingsPage: React.FC<SettingsPageProps> = ({
  activeTab,
  isDevMode,
  onDevModeChange,
  themeMode,
  onThemeModeChange,
  resolvedTheme,
  accentColorMode,
  onAccentColorModeChange,
  fontSizeMode,
  onFontSizeModeChange,
  language,
  onLanguageChange,
  streamQuality,
  onStreamQualityChange,
  session,
  metadata,
  apiBaseUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
  aiCoachWsUrl = import.meta.env.VITE_AI_COACH_WS || 'ws://localhost:8010/ws/coach',
  burninUrl = '',
}) => {
  const { t } = useTranslation();
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
  const [tableRoiStatus, setTableRoiStatus] = useState('');
  const [roiPoints, setRoiPoints] = useState<RoiPoint[]>([]);
  const [draftRoiPoints, setDraftRoiPoints] = useState<RoiPoint[]>([]);
  const [initialDraftRoiPoints, setInitialDraftRoiPoints] = useState<RoiPoint[]>([]);
  const [settingsSubView, setSettingsSubView] = useState<SettingsSubView>('main');
  const [isRoiCaptureMode, setIsRoiCaptureMode] = useState(false);
  const [selectedRoiPointIndex, setSelectedRoiPointIndex] = useState<number | null>(null);
  const [roiImageSize, setRoiImageSize] = useState<{ width: number; height: number } | null>(null);
  const [cameraDevice, setCameraDevice] = useState('camera-0');
  const [lightingProfile, setLightingProfile] = useState('warm');
  const [saveMessage, setSaveMessage] = useState('');
  const [isCameraParamsOpen, setIsCameraParamsOpen] = useState(false);
  const [isAccentMenuOpen, setIsAccentMenuOpen] = useState(false);
  const [colorCalibrationMode, setColorCalibrationMode] = useState<ColorCalibrationMode>('pool');
  const [colorCalibrationProfiles, setColorCalibrationProfiles] = useState<ColorCalibrationProfileSummary[]>([]);
  const [selectedColorProfileId, setSelectedColorProfileId] = useState<number | null>(null);
  const [isColorProfilesLoading, setIsColorProfilesLoading] = useState(false);
  const [colorProfilesMessage, setColorProfilesMessage] = useState('');
  const [isNewColorProfileOpen, setIsNewColorProfileOpen] = useState(false);
  const [newColorProfileName, setNewColorProfileName] = useState('');
  const [colorModalProfile, setColorModalProfile] = useState<ColorCalibrationProfileDetail | null>(null);
  const [colorModalSystemColors, setColorModalSystemColors] = useState<string[]>([]);
  const [colorModalMappings, setColorModalMappings] = useState<ColorMappingDict>({});
  const [initialColorModalMappings, setInitialColorModalMappings] = useState<ColorMappingDict>({});
  const [colorModalStep, setColorModalStep] = useState(0);
  const [colorModalScan, setColorModalScan] = useState<ColorAutoScanItem | null>(null);
  const [hasColorModalScanned, setHasColorModalScanned] = useState(false);
  const [colorModalHsvLower, setColorModalHsvLower] = useState<number[]>([0, 0, 0]);
  const [colorModalHsvUpper, setColorModalHsvUpper] = useState<number[]>([180, 255, 255]);
  const [isColorModalAdvancedOpen, setIsColorModalAdvancedOpen] = useState(false);
  const [isColorModalLoading, setIsColorModalLoading] = useState(false);
  const [colorModalMessage, setColorModalMessage] = useState('');
  const roiImageRef = useRef<HTMLImageElement | null>(null);
  const currentAccentColor = getAccentColorValue(accentColorMode, resolvedTheme);
  const currentAccentTextColor = getReadableTextColor(currentAccentColor);
  const currentAccentLabel =
    accentColorMode === 'default'
      ? t('settings.appearance.accentColorOptions.default')
      : currentAccentColor;
  const isRoiEditorView = activeTab === 'table-calibration' && settingsSubView === 'roi-editor';
  const isColorEditorView = activeTab === 'table-calibration' && settingsSubView === 'color-editor';
  const isProjectorEditorView = activeTab === 'table-calibration' && settingsSubView === 'projector-editor';

  const fetchColorCalibrationProfiles = useCallback(async (mode: ColorCalibrationMode) => {
    setIsColorProfilesLoading(true);
    setColorProfilesMessage('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/color-calibration/profiles?mode=${mode}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const profiles = (Array.isArray(data?.profiles) ? data.profiles : []) as ColorCalibrationProfileSummary[];
      setColorCalibrationProfiles(profiles);
      setSelectedColorProfileId((current) => {
        if (current && profiles.some((profile) => profile.id === current)) return current;
        return profiles[0]?.id ?? null;
      });
    } catch {
      setColorCalibrationProfiles([]);
      setSelectedColorProfileId(null);
      setColorProfilesMessage(t('settings.tableCalibration.colorProfilesLoadFailed'));
    } finally {
      setIsColorProfilesLoading(false);
    }
  }, [apiBaseUrl]);

  const colorModalCurrentColor =
    colorModalSystemColors.length > 0 && colorModalStep < colorModalSystemColors.length
      ? colorModalSystemColors[colorModalStep]
      : '';
  const isColorModalDone = colorModalSystemColors.length > 0 && colorModalStep >= colorModalSystemColors.length;
  const colorModalModeLabel = colorModalProfile?.mode === 'snooker'
    ? t('settings.tableCalibration.snookerMode')
    : t('settings.tableCalibration.poolMode');
  const colorModalPendingMapping = colorModalCurrentColor
    ? colorModalMappings[colorModalCurrentColor] || emptyColorMapping()
    : emptyColorMapping();
  const hasPendingColorModalHsvChange =
    colorModalCurrentColor
      ? JSON.stringify(normalizeHsvTriplet(colorModalHsvLower)) !== JSON.stringify(colorModalPendingMapping.hsv_lower)
        || JSON.stringify(normalizeHsvTriplet(colorModalHsvUpper)) !== JSON.stringify(colorModalPendingMapping.hsv_upper)
      : false;
  const hasUnsavedColorModalChanges =
    JSON.stringify(colorModalMappings) !== JSON.stringify(initialColorModalMappings)
    || hasPendingColorModalHsvChange
    || colorModalStep > 0;

  const getColorCalibrationStreamUrl = () => {
    const baseUrl = burninUrl || `${apiBaseUrl}/burnin/camera1.mjpg`;
    try {
      const url = new URL(baseUrl, window.location.origin);
      url.searchParams.set('quality', 'med');
      url.searchParams.set('client_id', 'color-calibration-editor');
      return url.toString();
    } catch {
      const separator = baseUrl.includes('?') ? '&' : '?';
      return `${baseUrl}${separator}quality=med&client_id=color-calibration-editor`;
    }
  };

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
    if (activeTab !== 'table-calibration') return;
    fetchColorCalibrationProfiles(colorCalibrationMode);
  }, [activeTab, colorCalibrationMode, fetchColorCalibrationProfiles]);

  useEffect(() => {
    if (activeTab === 'table-calibration') return;
    setSettingsSubView('main');
    setIsRoiCaptureMode(false);
    setSelectedRoiPointIndex(null);
  }, [activeTab]);

  useEffect(() => {
    if (!isColorEditorView || !colorModalCurrentColor) return;
    const currentMapping = colorModalMappings[colorModalCurrentColor] || emptyColorMapping();
    setColorModalHsvLower([...currentMapping.hsv_lower]);
    setColorModalHsvUpper([...currentMapping.hsv_upper]);
    setColorModalScan(null);
    setHasColorModalScanned(false);
  }, [colorModalCurrentColor, isColorEditorView]);

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
        setTableRoiStatus(data?.table_roi_status || '');
      })
      .catch(() => {
        if (isMounted) setTableRoiStatus('');
      });

    return () => {
      isMounted = false;
    };
  }, [apiBaseUrl]);

  useEffect(() => {
    let isMounted = true;

    fetch(`${apiBaseUrl}/api/table/roi-polygon`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!isMounted) return;
        const nextPoints = normalizeRoiPoints(data?.points);
        setRoiPoints(nextPoints);
        if (Array.isArray(data?.table_roi)) setTableRoiAdjusted(data.table_roi);
        if (data?.table_roi_status) setTableRoiStatus(data.table_roi_status);
      })
      .catch(() => {
        if (isMounted) setRoiPoints([]);
      });

    return () => {
      isMounted = false;
    };
  }, [apiBaseUrl]);

  const copySessionId = async () => {
    if (!session?.session_id) return;
    await navigator.clipboard.writeText(session.session_id);
    setSaveMessage(t('settings.advanced.sessionCopied'));
    window.setTimeout(() => setSaveMessage(''), 1800);
  };

  const saveLocalSettings = () => {
    setSaveMessage(t('settings.tracking.saved'));
    window.setTimeout(() => setSaveMessage(''), 1800);
  };

  const createColorCalibrationProfile = async () => {
    const name = newColorProfileName.trim();
    if (!name) {
      setColorProfilesMessage(t('settings.tableCalibration.profileNameRequired'));
      return;
    }

    setIsColorProfilesLoading(true);
    setColorProfilesMessage('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/color-calibration/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: colorCalibrationMode, name }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const createdProfileId = Number(data?.profile?.id);
      if (Number.isFinite(createdProfileId)) setSelectedColorProfileId(createdProfileId);
      setNewColorProfileName('');
      setIsNewColorProfileOpen(false);
      setColorProfilesMessage(t('settings.tableCalibration.colorProfileCreated'));
      await fetchColorCalibrationProfiles(colorCalibrationMode);
    } catch {
      setColorProfilesMessage(t('settings.tableCalibration.colorProfileCreateFailed'));
    } finally {
      setIsColorProfilesLoading(false);
    }
  };

  const applySelectedColorCalibrationProfile = async () => {
    if (!selectedColorProfileId) {
      setColorProfilesMessage(t('settings.tableCalibration.selectProfileFirst'));
      return;
    }

    setIsColorProfilesLoading(true);
    setColorProfilesMessage('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/color-calibration/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: selectedColorProfileId }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setColorProfilesMessage(t('settings.tableCalibration.colorProfileApplied'));
    } catch {
      setColorProfilesMessage(t('settings.tableCalibration.colorProfileApplyFailed'));
    } finally {
      setIsColorProfilesLoading(false);
    }
  };

  const editColorCalibrationProfile = async (profileId: number) => {
    setIsColorModalLoading(true);
    setColorProfilesMessage('');
    setColorModalMessage('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/color-calibration/profiles/${profileId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const profile = data.profile as ColorCalibrationProfileDetail;
      const colors = (Array.isArray(data.system_colors) ? data.system_colors : []) as string[];
      const nextMappings: ColorMappingDict = {};

      colors.forEach((color) => {
        const mapping = profile.mappings?.[color];
        nextMappings[color] = {
          actual_label: mapping?.actual_label || '',
          hsv_lower: Array.isArray(mapping?.hsv_lower) && mapping.hsv_lower.length === 3
            ? normalizeHsvTriplet(mapping.hsv_lower)
            : emptyColorMapping().hsv_lower,
          hsv_upper: Array.isArray(mapping?.hsv_upper) && mapping.hsv_upper.length === 3
            ? normalizeHsvTriplet(mapping.hsv_upper)
            : emptyColorMapping().hsv_upper,
        };
      });

      setColorModalProfile(profile);
      setColorModalSystemColors(colors);
      setColorModalMappings(nextMappings);
      setInitialColorModalMappings(JSON.parse(JSON.stringify(nextMappings)) as ColorMappingDict);
      setColorModalStep(0);
      setColorModalScan(null);
      setHasColorModalScanned(false);
      setIsColorModalAdvancedOpen(false);
      setSettingsSubView('color-editor');
    } catch {
      setColorProfilesMessage(t('settings.tableCalibration.colorProfileLoadFailed'));
    } finally {
      setIsColorModalLoading(false);
    }
  };

  const writeCurrentColorModalMapping = () => {
    if (!colorModalCurrentColor) return;
    setColorModalMappings((current) => {
      const previous = current[colorModalCurrentColor] || emptyColorMapping();
      return {
        ...current,
        [colorModalCurrentColor]: {
          ...previous,
          hsv_lower: normalizeHsvTriplet(colorModalHsvLower),
          hsv_upper: normalizeHsvTriplet(colorModalHsvUpper),
        },
      };
    });
  };

  const scanCurrentColorBall = async () => {
    if (!colorModalProfile || !colorModalCurrentColor) return;
    setIsColorModalLoading(true);
    setColorModalMessage(t('settings.tableCalibration.scanningCurrentBall'));
    try {
      const response = await fetch(`${apiBaseUrl}/api/color-calibration/auto-scan?mode=${colorModalProfile.mode}`);
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(error?.detail || t('settings.tableCalibration.autoScanFailed'));
      }
      const data = await response.json();
      const scans = (Array.isArray(data?.scans) ? data.scans : []) as ColorAutoScanItem[];
      if (scans.length === 0) throw new Error(t('settings.tableCalibration.noBallRoiAvailable'));

      const scan = scans[0];
      setColorModalScan(scan);
      setColorModalHsvLower([...scan.hsv_lower]);
      setColorModalHsvUpper([...scan.hsv_upper]);
      setHasColorModalScanned(true);
      setColorModalMessage(t('settings.tableCalibration.scanCurrentBallSuccess'));
    } catch (error) {
      setColorModalMessage(error instanceof Error ? error.message : t('settings.tableCalibration.autoScanFailed'));
    } finally {
      setIsColorModalLoading(false);
    }
  };

  const acceptColorAndNext = () => {
    if (!colorModalCurrentColor) return;
    writeCurrentColorModalMapping();
    const nextStep = colorModalStep + 1;
    setColorModalStep(nextStep);
    setHasColorModalScanned(false);
    setColorModalScan(null);
    setColorModalMessage(
      nextStep >= colorModalSystemColors.length
        ? t('settings.tableCalibration.allColorsCompleteSaveExit')
        : t('settings.tableCalibration.colorWrittenNext', { color: colorModalCurrentColor }),
    );
  };

  const skipColorAndNext = () => {
    const nextStep = colorModalStep + 1;
    setColorModalStep(nextStep);
    setHasColorModalScanned(false);
    setColorModalScan(null);
    setColorModalMessage(
      nextStep >= colorModalSystemColors.length
        ? t('settings.tableCalibration.lastStepConfirmSave')
        : t('settings.tableCalibration.colorSkipped'),
    );
  };

  const goPreviousColor = () => {
    if (colorModalStep <= 0) return;
    writeCurrentColorModalMapping();
    setColorModalStep((current) => Math.max(0, current - 1));
    setColorModalMessage(t('settings.tableCalibration.previousColorSelected'));
  };

  const closeColorCalibrationEditor = () => {
    if (hasUnsavedColorModalChanges && !window.confirm(t('settings.tableCalibration.unsavedColorCloseConfirm'))) {
      return;
    }
    setSettingsSubView('main');
    setColorModalProfile(null);
    setColorModalSystemColors([]);
    setColorModalMappings({});
    setInitialColorModalMappings({});
    setColorModalMessage('');
    setColorModalScan(null);
  };

  const saveColorCalibrationAndExit = async () => {
    if (!colorModalProfile) return;
    const payload: ColorMappingDict = {};
    colorModalSystemColors.forEach((color) => {
      const mapping = colorModalMappings[color] || emptyColorMapping();
      const isCurrent = color === colorModalCurrentColor;
      payload[color] = {
        actual_label: mapping.actual_label || '',
        hsv_lower: isCurrent ? normalizeHsvTriplet(colorModalHsvLower) : normalizeHsvTriplet(mapping.hsv_lower),
        hsv_upper: isCurrent ? normalizeHsvTriplet(colorModalHsvUpper) : normalizeHsvTriplet(mapping.hsv_upper),
      };
    });

    setIsColorModalLoading(true);
    setColorModalMessage('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/color-calibration/profiles/${colorModalProfile.id}/mappings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mappings: payload }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setInitialColorModalMappings(JSON.parse(JSON.stringify(payload)) as ColorMappingDict);
      setColorModalMappings(payload);
      setSettingsSubView('main');
      setColorModalProfile(null);
      setColorModalMessage('');
      setColorProfilesMessage(t('settings.tableCalibration.colorProfileSaved'));
      await fetchColorCalibrationProfiles(colorCalibrationMode);
    } catch {
      setColorModalMessage(t('settings.tableCalibration.colorProfileSaveFailed'));
    } finally {
      setIsColorModalLoading(false);
    }
  };

  const handleStreamQualityChange = (nextQuality: StreamQuality) => {
    onStreamQualityChange(nextQuality);
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

  const renderAccentColorControl = () => (
    <div
      className="settings-accent-picker"
      onBlur={(event) => {
        const nextFocusTarget = event.relatedTarget as Node | null;
        if (!nextFocusTarget || !event.currentTarget.contains(nextFocusTarget)) {
          setIsAccentMenuOpen(false);
        }
      }}
    >
      <button
        className="settings-accent-trigger"
        type="button"
        aria-haspopup="menu"
        aria-expanded={isAccentMenuOpen}
        aria-label={t('settings.appearance.accentColorAria')}
        style={{
          backgroundColor: currentAccentColor,
          color: currentAccentTextColor,
        }}
        onClick={() => setIsAccentMenuOpen((current) => !current)}
      >
        <span>{currentAccentLabel}</span>
      </button>
      {isAccentMenuOpen && (
        <div className="settings-accent-menu" role="listbox" aria-label={t('settings.appearance.accentColor')}>
          {accentColorOptions.map((option) => {
            const optionColor = getAccentColorValue(option.mode, resolvedTheme);
            const optionLabel = t(`settings.appearance.accentColorOptions.${option.mode}`);
            const optionDisplayLabel = option.mode === 'default' ? optionLabel : optionColor;
            const optionTextColor = getReadableTextColor(optionColor);
            return (
              <button
                key={option.mode}
                className={`settings-accent-option ${accentColorMode === option.mode ? 'active' : ''}`}
                type="button"
                role="option"
                aria-selected={accentColorMode === option.mode}
                aria-label={`${optionLabel} ${optionColor}`}
                title={`${optionLabel} ${optionColor}`}
                style={{
                  background: optionColor,
                  borderColor: accentColorMode === option.mode ? optionTextColor : optionColor,
                  color: optionTextColor,
                }}
                onClick={() => {
                  onAccentColorModeChange(option.mode);
                  setIsAccentMenuOpen(false);
                }}
              >
                <span>{optionDisplayLabel}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );

  const getTablePresetLabel = (preset: string) =>
    t(`settings.appearance.presets.${preset}`, { defaultValue: preset });

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
        setSaveMessage(t('settings.appearance.tableColorSaved'));
        window.setTimeout(() => setSaveMessage(''), 1800);
      })
      .catch((error) => {
        console.warn('同步球桌顏色設定失敗:', error);
        setSaveMessage(t('settings.appearance.tableColorSyncFailed'));
        window.setTimeout(() => setSaveMessage(''), 2200);
      });
  };

  const parseHsvTriplet = (value: string) => {
    const parts = value.split(',').map((part) => Number(part.trim()));
    if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) {
      throw new Error(t('settings.appearance.hsvTripletRequired'));
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
      setSaveMessage(error instanceof Error ? error.message : t('settings.appearance.hsvFormatError'));
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
        setSaveMessage(t('settings.appearance.customColorApplied'));
        window.setTimeout(() => setSaveMessage(''), 1800);
      })
      .catch((error) => {
        console.warn('套用自訂桌布顏色失敗:', error);
        setSaveMessage(t('settings.appearance.customColorApplyFailed'));
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
        setSaveMessage(t('settings.appearance.autoDetectedColor', {
          color: getTablePresetLabel(nextPreset || ''),
        }));
        window.setTimeout(() => setSaveMessage(''), 2200);
      })
      .catch((error) => {
        console.warn('自動檢測桌布顏色失敗:', error);
        setSaveMessage(t('settings.appearance.autoDetectFailed'));
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
        setTableRoiStatus(data?.table_roi_status || t('settings.tableCalibration.roiUpdated'));
      })
      .catch((error) => {
        console.warn('同步 ROI 微調失敗:', error);
        setSaveMessage(t('settings.tableCalibration.roiSyncFailed'));
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
        setTableRoiStatus(data?.table_roi_status || t('settings.tableCalibration.roiReset'));
      })
      .catch((error) => {
        console.warn('重設 ROI 微調失敗:', error);
        setSaveMessage(t('settings.tableCalibration.roiResetFailed'));
        window.setTimeout(() => setSaveMessage(''), 2200);
      });
  };

  const normalizeRoiPoints = (points: unknown): RoiPoint[] => {
    if (!Array.isArray(points)) return [];
    return points.flatMap((point) => {
      if (Array.isArray(point) && point.length >= 2) {
        const x = Number(point[0]);
        const y = Number(point[1]);
        return Number.isFinite(x) && Number.isFinite(y) ? [{ x: Math.round(x), y: Math.round(y) }] : [];
      }
      if (point && typeof point === 'object' && 'x' in point && 'y' in point) {
        const rawPoint = point as { x: unknown; y: unknown };
        const x = Number(rawPoint.x);
        const y = Number(rawPoint.y);
        return Number.isFinite(x) && Number.isFinite(y) ? [{ x: Math.round(x), y: Math.round(y) }] : [];
      }
      return [];
    }).slice(0, 4);
  };

  const roiRectToPoints = (roi: number[] | null): RoiPoint[] => {
    if (!Array.isArray(roi) || roi.length < 4) return [];
    const [x, y, w, h] = roi.map((value) => Math.round(Number(value) || 0));
    if (w <= 0 || h <= 0) return [];
    return [
      { x, y },
      { x: x + w, y },
      { x: x + w, y: y + h },
      { x, y: y + h },
    ];
  };

  const getRoiStreamUrl = () => {
    const baseUrl = burninUrl || `${apiBaseUrl}/burnin/camera1.mjpg`;
    try {
      const url = new URL(baseUrl, window.location.origin);
      url.searchParams.set('quality', 'med');
      url.searchParams.set('client_id', 'roi-polygon-editor');
      return url.toString();
    } catch {
      const separator = baseUrl.includes('?') ? '&' : '?';
      return `${baseUrl}${separator}quality=med&client_id=roi-polygon-editor`;
    }
  };

  const areRoiPointsEqual = (pointsA: RoiPoint[], pointsB: RoiPoint[]) => {
    if (pointsA.length !== pointsB.length) return false;
    return pointsA.every((point, index) => point.x === pointsB[index]?.x && point.y === pointsB[index]?.y);
  };

  const hasUnsavedRoiChanges = () => !areRoiPointsEqual(draftRoiPoints, initialDraftRoiPoints);

  const saveDraftRoiPoints = () => {
    if (draftRoiPoints.length !== 4) {
      setSaveMessage(t('settings.tableCalibration.roiPolygonIncomplete'));
      window.setTimeout(() => setSaveMessage(''), 2400);
      return;
    }

    fetch(`${apiBaseUrl}/api/table/roi-polygon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ points: draftRoiPoints }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        const savedPoints = normalizeRoiPoints(data?.points);
        const nextSavedPoints = savedPoints.length === 4 ? savedPoints : draftRoiPoints;
        setRoiPoints(nextSavedPoints);
        setDraftRoiPoints(nextSavedPoints);
        setInitialDraftRoiPoints(nextSavedPoints);
        if (Array.isArray(data?.table_roi)) setTableRoiAdjusted(data.table_roi);
        if (data?.table_roi_status) setTableRoiStatus(data.table_roi_status);
        setSettingsSubView('main');
        setIsRoiCaptureMode(false);
        setSaveMessage(t('settings.tableCalibration.roiPolygonSaved'));
        window.setTimeout(() => setSaveMessage(''), 1800);
      })
      .catch((error) => {
        console.warn('同步 ROI 四點失敗:', error);
        setSaveMessage(t('settings.tableCalibration.roiPolygonSaveFailed'));
        window.setTimeout(() => setSaveMessage(''), 2400);
      });
  };

  const getRoiPointerPosition = (event: React.MouseEvent<HTMLElement>): RoiPoint | null => {
    const image = roiImageRef.current;
    if (!image || !roiImageSize) return null;

    const rect = image.getBoundingClientRect();
    const imageRatio = roiImageSize.width / roiImageSize.height;
    const boxRatio = rect.width / rect.height;
    const renderedWidth = boxRatio > imageRatio ? rect.height * imageRatio : rect.width;
    const renderedHeight = boxRatio > imageRatio ? rect.height : rect.width / imageRatio;
    const offsetX = (rect.width - renderedWidth) / 2;
    const offsetY = (rect.height - renderedHeight) / 2;
    const x = ((event.clientX - rect.left - offsetX) / renderedWidth) * roiImageSize.width;
    const y = ((event.clientY - rect.top - offsetY) / renderedHeight) * roiImageSize.height;

    if (x < 0 || y < 0 || x > roiImageSize.width || y > roiImageSize.height) return null;
    return { x: Math.round(x), y: Math.round(y) };
  };

  const handleRoiStageClick = (event: React.MouseEvent<HTMLElement>) => {
    if (!isRoiCaptureMode) return;
    const point = getRoiPointerPosition(event);
    if (!point) return;

    setDraftRoiPoints((current) => {
      const nextPoints = [...current, point].slice(0, 4);
      setSelectedRoiPointIndex(nextPoints.length - 1);
      if (nextPoints.length === 4) {
        setIsRoiCaptureMode(false);
      }
      return nextPoints;
    });
  };

  const handleResetRoiPolygon = () => {
    setDraftRoiPoints([]);
    setInitialDraftRoiPoints([]);
    setRoiPoints([]);
    setSelectedRoiPointIndex(null);
    setIsRoiCaptureMode(true);
    fetch(`${apiBaseUrl}/api/table/roi-polygon/reset`, { method: 'POST' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (Array.isArray(data?.table_roi)) setTableRoiAdjusted(data.table_roi);
        else setTableRoiAdjusted(null);
        if (data?.table_roi_status) setTableRoiStatus(data.table_roi_status);
      })
      .catch((error) => {
        console.warn('重設 ROI 四點失敗:', error);
        setSaveMessage(t('settings.tableCalibration.roiPolygonResetFailed'));
        window.setTimeout(() => setSaveMessage(''), 2400);
      });
  };

  const restoreDefaultRoiPolygon = () => {
    const nextPoints = roiRectToPoints(tableRoiAdjusted).length
      ? roiRectToPoints(tableRoiAdjusted)
      : roiRectToPoints(tableRoiRaw);
    if (nextPoints.length !== 4) {
      setSaveMessage(t('settings.tableCalibration.roiDefaultUnavailable'));
      window.setTimeout(() => setSaveMessage(''), 2400);
      return;
    }

    setDraftRoiPoints(nextPoints);
    setSelectedRoiPointIndex(0);
    setIsRoiCaptureMode(false);
  };

  const openRoiPolygonEditor = () => {
    const savedPoints = roiPoints.map((point) => ({ ...point }));
    const yoloPoints = roiRectToPoints(tableRoiAdjusted).length
      ? roiRectToPoints(tableRoiAdjusted)
      : roiRectToPoints(tableRoiRaw);
    const nextDraft = savedPoints.length === 4 ? savedPoints : yoloPoints;
    setDraftRoiPoints(nextDraft);
    setInitialDraftRoiPoints(nextDraft);
    setSettingsSubView('roi-editor');
    setIsRoiCaptureMode(nextDraft.length < 4);
    setSelectedRoiPointIndex(nextDraft.length ? 0 : null);
  };

  const closeRoiPolygonEditor = () => {
    if (hasUnsavedRoiChanges() && !window.confirm(t('settings.tableCalibration.roiUnsavedCloseConfirm'))) {
      return;
    }
    setDraftRoiPoints(initialDraftRoiPoints.map((point) => ({ ...point })));
    setSettingsSubView('main');
    setIsRoiCaptureMode(false);
    setSelectedRoiPointIndex(null);
  };

  const moveSelectedRoiPoint = useCallback((dx: number, dy: number) => {
    if (selectedRoiPointIndex == null) return;
    setDraftRoiPoints((current) => {
      if (!current[selectedRoiPointIndex]) return current;
      const nextPoints = current.map((point, index) => {
        if (index !== selectedRoiPointIndex) return point;
        return {
          x: Math.max(0, Math.min(roiImageSize?.width ?? Number.MAX_SAFE_INTEGER, point.x + dx)),
          y: Math.max(0, Math.min(roiImageSize?.height ?? Number.MAX_SAFE_INTEGER, point.y + dy)),
        };
      });
      return nextPoints;
    });
  }, [roiImageSize, selectedRoiPointIndex]);

  useEffect(() => {
    if (!isRoiEditorView) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (/^[1-4]$/.test(event.key)) {
        const nextIndex = Number(event.key) - 1;
        if (draftRoiPoints[nextIndex]) {
          event.preventDefault();
          setSelectedRoiPointIndex(nextIndex);
          setIsRoiCaptureMode(false);
        }
        return;
      }

      if (selectedRoiPointIndex == null) return;
      const keyToDelta: Record<string, [number, number]> = {
        ArrowUp: [0, -1],
        ArrowDown: [0, 1],
        ArrowLeft: [-1, 0],
        ArrowRight: [1, 0],
      };
      const delta = keyToDelta[event.key];
      if (!delta) return;
      event.preventDefault();
      moveSelectedRoiPoint(delta[0], delta[1]);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [draftRoiPoints, isRoiEditorView, moveSelectedRoiPoint, selectedRoiPointIndex]);

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
            {getTablePresetLabel(preset.value)}
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
        placeholder={t('settings.appearance.hsvLowerPlaceholder')}
      />
      <input
        value={customHsvUpper}
        onChange={(event) => setCustomHsvUpper(event.target.value)}
        placeholder={t('settings.appearance.hsvUpperPlaceholder')}
      />
      <button className="settings-button secondary" type="button" onClick={handleApplyCustomTableColor}>
        {t('settings.appearance.applyCustom')}
      </button>
    </div>
  );

  const formatRoi = (roi: number[] | null) => {
    if (!Array.isArray(roi) || roi.length < 4) return t('settings.appearance.notDetected');
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

  const renderColorCalibrationEditor = () => {
    if (!colorModalProfile) return null;

    const currentColorStyle = colorModalCurrentColor ? getBallColorStyle(colorModalCurrentColor) : getBallColorStyle('yellow');
    const progressPercent = colorModalSystemColors.length > 0
      ? Math.round((Math.min(colorModalStep, colorModalSystemColors.length) / colorModalSystemColors.length) * 100)
      : 0;

    return (
      <section className="color-calibration-editor-page" aria-label={t('settings.tableCalibration.colorCalibrationEditorAria')}>
        <div className="color-calibration-editor-header">
          <div>
            <h3>{t('settings.tableCalibration.colorCalibrationEditorTitle', { mode: colorModalModeLabel, name: colorModalProfile.name })}</h3>
          </div>
          <div className="color-calibration-progress">
            <div className="color-calibration-progress-label">
              <span>{t('settings.tableCalibration.stepProgress', { current: Math.min(colorModalStep + 1, colorModalSystemColors.length), total: colorModalSystemColors.length })}</span>
              {colorModalCurrentColor && (
                <span
                  className="color-calibration-color-badge"
                  style={{ background: currentColorStyle.bg, color: currentColorStyle.text }}
                >
                  {colorModalCurrentColor}
                </span>
              )}
            </div>
            <div className="color-calibration-progress-bar">
              <div className="color-calibration-progress-fill" style={{ width: `${progressPercent}%` }} />
            </div>
          </div>
        </div>

        <section className="color-calibration-preview-panel">
          <div className="color-calibration-preview-label">{t('settings.tableCalibration.cameraReference')}</div>
          <div className="color-calibration-preview-frame">
            <img
              src={getColorCalibrationStreamUrl()}
              alt={t('settings.tableCalibration.colorCalibrationPreviewAlt')}
              className="color-calibration-preview-image"
            />
          </div>
        </section>

        <div className="color-calibration-control-panel">
          {isColorModalDone ? (
            <div className="color-calibration-operation-card">
              <strong>{t('settings.tableCalibration.allColorsComplete')}</strong>
              <span>{t('settings.tableCalibration.confirmThenSaveExit')}</span>
            </div>
          ) : (
            <>
              <div className="color-calibration-instruction">
                <p>
                  {t('settings.tableCalibration.placeColorBallPrefix')} <strong>{colorModalCurrentColor}</strong> {t('settings.tableCalibration.placeColorBallSuffix')}
                </p>
                {colorModalScan && hasColorModalScanned && (
                  <div className="color-calibration-scan-result">
                    <span
                      className="color-calibration-swatch"
                      style={{ background: `rgb(${colorModalScan.rgb_center[0]}, ${colorModalScan.rgb_center[1]}, ${colorModalScan.rgb_center[2]})` }}
                    />
                    <span>ROI HSV: {colorModalScan.hsv_center.join(', ')}</span>
                  </div>
                )}
              </div>
              <div className="color-calibration-action-row">
                <button
                  className="settings-button primary"
                  type="button"
                  onClick={hasColorModalScanned ? acceptColorAndNext : scanCurrentColorBall}
                  disabled={isColorModalLoading}
                >
                  {hasColorModalScanned ? t('settings.tableCalibration.confirmNextColor') : t('settings.tableCalibration.scanCurrentBall')}
                </button>
                <button
                  className="settings-button secondary"
                  type="button"
                  onClick={goPreviousColor}
                  disabled={isColorModalLoading || colorModalStep <= 0}
                >
                  {t('settings.tableCalibration.previousColor')}
                </button>
                <button
                  className="settings-button secondary"
                  type="button"
                  onClick={skipColorAndNext}
                  disabled={isColorModalLoading}
                >
                  {t('settings.tableCalibration.skipColor')}
                </button>
              </div>
              <div className="color-calibration-advanced-inline">
                <span className="color-calibration-advanced-label">{t('settings.tableCalibration.advanced')}</span>
                <button
                  className={`color-calibration-advanced-switch ${isColorModalAdvancedOpen ? 'active' : ''}`}
                  type="button"
                  role="switch"
                  aria-checked={isColorModalAdvancedOpen}
                  aria-label={t('settings.tableCalibration.advancedHsvAria')}
                  onClick={() => setIsColorModalAdvancedOpen((current) => !current)}
                >
                  <span />
                </button>
              </div>
              {isColorModalAdvancedOpen && (
                <div className="color-calibration-advanced">
                  <div className="color-calibration-hsv-editor">
                    <label>
                      HSV Lower (H/S/V)
                      <div className="color-calibration-hsv-row">
                        {[0, 1, 2].map((index) => (
                          <input
                            key={`lower-${index}`}
                            type="number"
                            min={0}
                            max={index === 0 ? 180 : 255}
                            value={colorModalHsvLower[index]}
                            onChange={(event) => {
                              const value = clampHsvValue(Number(event.target.value), 0, index === 0 ? 180 : 255);
                              setColorModalHsvLower((current) => {
                                const next = [...current];
                                next[index] = value;
                                return next;
                              });
                            }}
                          />
                        ))}
                      </div>
                    </label>
                    <label>
                      HSV Upper (H/S/V)
                      <div className="color-calibration-hsv-row">
                        {[0, 1, 2].map((index) => (
                          <input
                            key={`upper-${index}`}
                            type="number"
                            min={0}
                            max={index === 0 ? 180 : 255}
                            value={colorModalHsvUpper[index]}
                            onChange={(event) => {
                              const value = clampHsvValue(Number(event.target.value), 0, index === 0 ? 180 : 255);
                              setColorModalHsvUpper((current) => {
                                const next = [...current];
                                next[index] = value;
                                return next;
                              });
                            }}
                          />
                        ))}
                      </div>
                    </label>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="color-calibration-editor-footer">
          <div className="color-calibration-message-slot">
            {colorModalMessage && <p className="color-calibration-message">{colorModalMessage}</p>}
          </div>
          <div className="color-calibration-editor-actions">
            <button className="settings-button secondary" type="button" onClick={closeColorCalibrationEditor}>
              {t('settings.tableCalibration.close')}
            </button>
            <button
              className="settings-button primary"
              type="button"
              onClick={saveColorCalibrationAndExit}
              disabled={isColorModalLoading}
            >
              {t('settings.tableCalibration.saveAndExit')}
            </button>
          </div>
        </div>
      </section>
    );
  };

  const renderRoiPolygonEditor = () => {
    const svgWidth = roiImageSize?.width || 1280;
    const svgHeight = roiImageSize?.height || 720;
    const polylinePoints = draftRoiPoints.map((point) => `${point.x},${point.y}`).join(' ');
    const closedPolygonPoints = draftRoiPoints.length === 4 ? polylinePoints : '';
    const selectedPoint = selectedRoiPointIndex != null ? draftRoiPoints[selectedRoiPointIndex] : null;
    const getPointLabelProps = (point: RoiPoint) => {
      const isNearTop = point.y < 34;
      const isNearRight = point.x > svgWidth - 42;
      const isNearLeft = point.x < 24;
      return {
        x: isNearRight ? point.x - 16 : point.x + 13,
        y: isNearTop ? point.y + 28 : point.y - 13,
        textAnchor: (isNearRight ? 'end' : isNearLeft ? 'start' : 'start') as 'end' | 'start',
      };
    };

    return (
      <section className="roi-editor-page" aria-label={t('settings.tableCalibration.roiPolygonPage')}>
        <div className="roi-editor-page-header">
          <div>
            <h3>{t('settings.tableCalibration.roiPolygonTitle')}</h3>
            <p>{isRoiCaptureMode ? t('settings.tableCalibration.roiCaptureHint') : t('settings.tableCalibration.roiAdjustHint')}</p>
          </div>
          <button className="settings-button secondary compact" type="button" onClick={restoreDefaultRoiPolygon}>
            {t('settings.tableCalibration.restoreDefaultRoiPolygon')}
          </button>
        </div>

        <div className="roi-editor-stage" onClick={handleRoiStageClick}>
          <img
            ref={roiImageRef}
            src={getRoiStreamUrl()}
            alt={t('settings.tableCalibration.roiLiveImageAlt')}
            className="roi-editor-stream"
            onLoad={(event) => {
              const image = event.currentTarget;
              if (image.naturalWidth && image.naturalHeight) {
                setRoiImageSize({ width: image.naturalWidth, height: image.naturalHeight });
              }
            }}
          />
          <svg
            className="roi-editor-overlay"
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            preserveAspectRatio="xMidYMid meet"
            aria-hidden="true"
          >
            {closedPolygonPoints && <polygon className="roi-editor-polygon-fill" points={closedPolygonPoints} />}
            {polylinePoints && <polyline className="roi-editor-polyline" points={polylinePoints} />}
            {draftRoiPoints.length === 4 && (
              <line
                className="roi-editor-polyline"
                x1={draftRoiPoints[3].x}
                y1={draftRoiPoints[3].y}
                x2={draftRoiPoints[0].x}
                y2={draftRoiPoints[0].y}
              />
            )}
            {draftRoiPoints.map((point, index) => {
              const labelProps = getPointLabelProps(point);
              return (
                <g key={`${point.x}-${point.y}-${index}`} onClick={(event) => {
                  event.stopPropagation();
                  setSelectedRoiPointIndex(index);
                  setIsRoiCaptureMode(false);
                }}>
                  <circle
                    className={index === selectedRoiPointIndex ? 'roi-editor-point active' : 'roi-editor-point'}
                    cx={point.x}
                    cy={point.y}
                    r="10"
                  />
                  <text
                    className="roi-editor-point-label"
                    x={labelProps.x}
                    y={labelProps.y}
                    textAnchor={labelProps.textAnchor}
                  >
                    {index + 1}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="roi-editor-page-footer">
          <div className="roi-point-status">
            <strong>{selectedPoint ? `P${(selectedRoiPointIndex ?? 0) + 1}: ${selectedPoint.x}, ${selectedPoint.y}` : t('settings.tableCalibration.noRoiPointSelected')}</strong>
            <span>{t('settings.tableCalibration.roiPointCount', { count: draftRoiPoints.length })}</span>
          </div>
          <div className="roi-direction-pad" aria-label={t('settings.tableCalibration.roiNudgeControls')}>
            {[
              { key: 'up' as const, label: t('settings.tableCalibration.nudgeUp'), glyph: '↑', dx: 0, dy: -1 },
              { key: 'left' as const, label: t('settings.tableCalibration.nudgeLeft'), glyph: '←', dx: -1, dy: 0 },
              { key: 'right' as const, label: t('settings.tableCalibration.nudgeRight'), glyph: '→', dx: 1, dy: 0 },
              { key: 'down' as const, label: t('settings.tableCalibration.nudgeDown'), glyph: '↓', dx: 0, dy: 1 },
            ].map((item) => (
              <button
                key={item.key}
                className={`roi-direction-button ${item.key}`}
                type="button"
                aria-label={item.label}
                title={item.label}
                onClick={() => moveSelectedRoiPoint(item.dx, item.dy)}
                disabled={selectedRoiPointIndex == null}
              >
                {item.glyph}
              </button>
            ))}
          </div>
          <div className="roi-primary-actions">
            <button className="settings-button secondary" type="button" onClick={handleResetRoiPolygon}>
              {t('settings.tableCalibration.resetRoiPolygon')}
            </button>
            <button className="settings-button secondary" type="button" onClick={closeRoiPolygonEditor}>
              {t('settings.tableCalibration.closeRoiPolygon')}
            </button>
            <button className="settings-button secondary" type="button" onClick={saveDraftRoiPoints}>
              {t('settings.tableCalibration.saveAndExitRoiPolygon')}
            </button>
          </div>
        </div>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>
    );
  };

  const renderProjectorCalibrationEditor = () => (
    <section className="projector-calibration-editor-page" aria-label={t('settings.tableCalibration.projectorCalibration')}>
      <AutoCalibrationPage
        onBack={() => setSettingsSubView('main')}
        burninUrl={burninUrl}
      />
    </section>
  );

  const renderGeneral = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.general.systemInfo')}</h3>
        <p className="settings-section-desc">{t('settings.general.systemInfoDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(t('settings.general.version'), t('settings.general.versionDesc'), <strong>v1.5.1</strong>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.general.generalSettings')}</h3>
        <p className="settings-section-desc">{t('settings.general.generalSettingsDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.general.language'),
            t('settings.general.languageDesc'),
            <select
              value={language}
              onChange={(event) => onLanguageChange(event.target.value as SupportedLanguage)}
            >
              {supportedLanguages.map((item) => (
                <option key={item} value={item}>
                  {languageLabels[item]}
                </option>
              ))}
            </select>,
          )}
          {renderPanelRow(
            t('settings.tracking.streamQuality'),
            t('settings.tracking.streamQualityDesc'),
            <select
              value={streamQuality}
              onChange={(event) => handleStreamQualityChange(event.target.value as StreamQuality)}
            >
              <option value="low">{t('settings.tracking.low')}</option>
              <option value="med">{t('settings.tracking.medium')}</option>
              <option value="high">{t('settings.tracking.high')}</option>
            </select>,
          )}
        </div>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.general.network')}</h3>
        <p className="settings-section-desc">{t('settings.general.networkDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(
            'Backend API',
            t('settings.general.backendApiDesc'),
            <input value={backendApiUrl} onChange={(event) => setBackendApiUrl(event.target.value)} />,
          )}
          {renderPanelRow(
            'WebSocket URL',
            t('settings.general.websocketDesc'),
            <input value={webSocketUrl} onChange={(event) => setWebSocketUrl(event.target.value)} />,
          )}
          {renderPanelRow(
            'AI Coach WebSocket URL',
            t('settings.general.aiCoachWsDesc'),
            <input value={coachWebSocketUrl} onChange={(event) => setCoachWebSocketUrl(event.target.value)} />,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.general.developerTools')}</h3>
        <p className="settings-section-desc">{t('settings.general.developerToolsDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.general.showAdvancedMonitoring'),
            t('settings.general.showAdvancedMonitoringDesc'),
            renderToggle(isDevMode, onDevModeChange, t('settings.general.showAdvancedMonitoring')),
          )}
        </div>
      </section>

      {isDevMode && renderAdvancedMonitoring()}
    </>
  );

  const renderAppearance = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.appearance.interface')}</h3>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.appearance.theme'),
            t('settings.appearance.themeDesc'),
            <select
              value={themeMode}
              onChange={(event) => onThemeModeChange(event.target.value as ThemeMode)}
            >
              <option value="dark">{t('settings.appearance.dark')}</option>
              <option value="light">{t('settings.appearance.light')}</option>
              <option value="system">{t('settings.appearance.system')}</option>
            </select>,
          )}
          {renderPanelRow(
            t('settings.appearance.accentColor'),
            t('settings.appearance.accentColorDesc'),
            renderAccentColorControl(),
          )}
          {renderPanelRow(
            t('settings.appearance.fontSize'),
            t('settings.appearance.fontSizeDesc'),
            <select
              value={fontSizeMode}
              onChange={(event) => onFontSizeModeChange(event.target.value as FontSizeMode)}
            >
              <option value="small">{t('settings.appearance.fontSizeSmall')}</option>
              <option value="standard">{t('settings.appearance.fontSizeStandard')}</option>
              <option value="large">{t('settings.appearance.fontSizeLarge')}</option>
              <option value="xlarge">{t('settings.appearance.fontSizeXLarge')}</option>
            </select>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.appearance.tableStyle')}</h3>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.appearance.currentColor'),
            t('settings.appearance.currentColorDesc'),
            renderTableColorSelector(),
          )}
          {renderPanelRow(
            t('settings.appearance.autoDetectColorShort'),
            t('settings.appearance.autoDetectColorShortDesc'),
            <button className="settings-button secondary" type="button" onClick={handleAutoDetectTableColor}>
              {t('settings.appearance.autoDetectColorShort')}
            </button>,
          )}
          {renderPanelRow(
            t('settings.appearance.customColorShort'),
            t('settings.appearance.customColorShortDesc'),
            renderCustomTableColorControls(),
          )}
        </div>
      </section>
    </>
  );

  const renderCamera = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.camera.deviceManagement')}</h3>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.camera.cameraSwitch'),
            t('settings.camera.cameraSwitchDesc'),
            <select value={cameraDevice} onChange={(event) => setCameraDevice(event.target.value)}>
              <option value="camera-0">Camera 0</option>
              <option value="camera-1">Camera 1</option>
              <option value="obs-virtual">OBS Virtual Camera</option>
            </select>,
          )}
          {renderPanelRow(
            t('settings.camera.refreshDeviceList'),
            t('settings.camera.refreshDeviceListDesc'),
            <button className="settings-button secondary" type="button">{t('settings.camera.refreshDeviceList')}</button>,
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.camera.lighting')}</h3>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.camera.lightingProfile'),
            t('settings.camera.lightingProfileDesc'),
            <select value={lightingProfile} onChange={(event) => setLightingProfile(event.target.value)}>
              <option value="warm">{t('settings.camera.warm')}</option>
              <option value="white">{t('settings.camera.white')}</option>
              <option value="low-light">{t('settings.camera.lowLight')}</option>
            </select>,
          )}
          {renderPanelRow(
            t('settings.camera.cameraParams'),
            t('settings.camera.advancedParamsInlineDesc'),
            <button
              className="settings-button primary"
              type="button"
              onClick={() => setIsCameraParamsOpen((current) => !current)}
              aria-expanded={isCameraParamsOpen}
            >
              {isCameraParamsOpen ? t('settings.camera.closeCameraParams') : t('settings.camera.cameraParams')}
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

  const renderTableCalibrationV2 = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.tableCalibration.roiAdjustment')}</h3>
        <p className="settings-section-desc">{t('settings.tableCalibration.roiAdjustmentDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(t('settings.tableCalibration.hsvAutoRoi'), t('settings.tableCalibration.originalRoiDesc'), <code>{formatRoi(tableRoiRaw)}</code>)}
          {renderPanelRow(t('settings.tableCalibration.adjustedRoi'), t('settings.tableCalibration.adjustedRoiDesc'), <code>{formatRoi(tableRoiAdjusted)}</code>)}
          {renderPanelRow(
            t('settings.tableCalibration.detectionStatus'),
            t('settings.tableCalibration.detectionStatusDesc'),
            <strong>{tableRoiStatus || t('settings.appearance.notDetected')}</strong>,
          )}
          {renderPanelRow(
            t('settings.tableCalibration.openRoiPolygon'),
            t('settings.tableCalibration.openRoiPolygonDesc'),
            <button className="settings-button secondary" type="button" onClick={openRoiPolygonEditor}>
              {t('settings.tableCalibration.openRoiPolygon')}
            </button>,
          )}
        </div>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.tableCalibration.colorProjectionCalibration')}</h3>
        <div className="settings-panel settings-color-mode-card">
          {renderPanelRow(
            t('settings.tableCalibration.mode'),
            t('settings.tableCalibration.colorModeDesc'),
            <select
              value={colorCalibrationMode}
              onChange={(event) => {
                setColorCalibrationMode(event.target.value as ColorCalibrationMode);
                setSelectedColorProfileId(null);
                setIsNewColorProfileOpen(false);
                setNewColorProfileName('');
                setColorProfilesMessage('');
              }}
              disabled={isColorProfilesLoading}
            >
              <option value="pool">{t('settings.tableCalibration.poolMode')}</option>
              <option value="snooker">{t('settings.tableCalibration.snookerMode')}</option>
            </select>,
          )}
        </div>

        <div className="settings-panel settings-profile-list-card">
          <div className="settings-calibration-subsection">
            <div className="settings-profile-list" aria-label={t('settings.tableCalibration.profileList')}>
              <div className="settings-profile-list-title">{t('settings.tableCalibration.profileList')}</div>
              {isColorProfilesLoading && colorCalibrationProfiles.length === 0 ? (
                <div className="settings-profile-empty">{t('settings.tableCalibration.profilesLoading')}</div>
              ) : colorCalibrationProfiles.length === 0 ? (
                <div className="settings-profile-empty">{t('settings.tableCalibration.noProfiles')}</div>
              ) : (
                <select
                  className="settings-profile-select"
                  value={selectedColorProfileId ?? ''}
                  onChange={(event) => {
                    const nextId = Number(event.target.value);
                    setSelectedColorProfileId(Number.isFinite(nextId) ? nextId : null);
                    setColorProfilesMessage('');
                  }}
                  disabled={isColorProfilesLoading}
                >
                  {colorCalibrationProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              )}

              <div className="settings-profile-action-row">
                <button
                  className="settings-button primary"
                  type="button"
                  onClick={applySelectedColorCalibrationProfile}
                  disabled={isColorProfilesLoading || !selectedColorProfileId}
                >
                  {t('settings.tableCalibration.applyProfile')}
                </button>
                <button
                  className="settings-button secondary"
                  type="button"
                  onClick={() => {
                    if (!selectedColorProfileId) {
                      setColorProfilesMessage(t('settings.tableCalibration.selectProfileFirst'));
                      return;
                    }
                    editColorCalibrationProfile(selectedColorProfileId);
                  }}
                  disabled={isColorProfilesLoading || !selectedColorProfileId}
                >
                  {t('settings.tableCalibration.edit')}
                </button>
              </div>

              {!isNewColorProfileOpen && (
                <button
                  className="settings-button secondary settings-add-profile-button"
                  type="button"
                  onClick={() => setIsNewColorProfileOpen(true)}
                  disabled={isColorProfilesLoading}
                >
                  {t('settings.tableCalibration.addProfile')}
                </button>
              )}

              {isNewColorProfileOpen ? (
                <div className="settings-new-profile-row">
                  <input
                    type="text"
                    value={newColorProfileName}
                    onChange={(event) => setNewColorProfileName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') createColorCalibrationProfile();
                      if (event.key === 'Escape') {
                        setIsNewColorProfileOpen(false);
                        setNewColorProfileName('');
                      }
                    }}
                    placeholder={t('settings.tableCalibration.profileNamePlaceholder')}
                    disabled={isColorProfilesLoading}
                  />
                  <button
                    className="settings-button primary compact"
                    type="button"
                    onClick={createColorCalibrationProfile}
                    disabled={isColorProfilesLoading}
                  >
                    {t('settings.tableCalibration.add')}
                  </button>
                  <button
                    className="settings-button secondary compact"
                    type="button"
                    onClick={() => {
                      setIsNewColorProfileOpen(false);
                      setNewColorProfileName('');
                      setColorProfilesMessage('');
                    }}
                    disabled={isColorProfilesLoading}
                  >
                    {t('common.cancel')}
                  </button>
                </div>
              ) : null}
            </div>
            {colorProfilesMessage && <p className="settings-inline-message">{colorProfilesMessage}</p>}
          </div>
        </div>

        <h4 className="settings-subsection-title settings-projection-title">{t('settings.tableCalibration.projection')}</h4>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.tableCalibration.projectorCalibration'),
            t('settings.tableCalibration.projectorCalibrationDesc2'),
            <button className="settings-button secondary" type="button" onClick={() => setSettingsSubView('projector-editor')}>
              {t('settings.tableCalibration.projectorCalibration')}
            </button>,
          )}
        </div>
      </section>
    </>
  );

  const renderTracking = () => (
    <>
      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.tracking.saveChanges')}</h3>
        <div className="settings-panel">
          {renderPanelRow(
            t('settings.tracking.saveLocal'),
            t('settings.tracking.saveLocalDesc'),
            <button className="settings-button primary" type="button" onClick={saveLocalSettings}>
              {t('settings.tracking.saveLocal')}
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
        <h3 className="settings-section-title">{t('settings.advanced.sessionStatus')}</h3>
        <div className="settings-panel">
          {renderPanelRow(
            'Session ID',
            t('settings.advanced.sessionIdDesc'),
            <span className="settings-copy-row">
              <code>{session?.session_id || t('settings.advanced.noSession')}</code>
              <button className="settings-button compact" type="button" onClick={copySessionId} disabled={!session?.session_id}>
                {t('common.copy')}
              </button>
            </span>,
          )}
          {renderPanelRow(t('settings.advanced.userRole'), t('settings.advanced.userRoleDesc'), <strong>{session?.role || 'N/A'}</strong>)}
          {renderPanelRow(t('settings.advanced.streamId'), t('settings.advanced.streamIdDesc'), <strong>{session?.stream_id || 'N/A'}</strong>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('settings.advanced.performanceMetadata')}</h3>
        <div className="settings-metric-grid">
          <div>
            <span>{t('settings.advanced.liveFps')}</span>
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
        <h3 className="settings-section-title">{t('settings.advanced.rawData')}</h3>
        <div className="settings-panel">
          {renderPanelRow(t('settings.advanced.detectedObjects'), t('settings.advanced.detectedObjectsDesc'), <strong>{metadata?.detected_count ?? 0}</strong>)}
          {renderPanelRow(t('settings.advanced.arPathCount'), t('settings.advanced.arPathCountDesc'), <strong>{metadata?.ar_paths?.length || 0}</strong>)}
        </div>
        <pre className="settings-json-block">{rawDetectionSummary || '[]'}</pre>
        {saveMessage && <p className="settings-inline-message">{saveMessage}</p>}
      </section>
    </>
  );

  const renderContent = () => {
    if (isRoiEditorView) return renderRoiPolygonEditor();
    if (isColorEditorView) return renderColorCalibrationEditor();
    if (isProjectorEditorView) return renderProjectorCalibrationEditor();

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
    <div className={isRoiEditorView || isColorEditorView || isProjectorEditorView ? 'settings-page settings-page--wide' : 'settings-page'}>
      {!isRoiEditorView && !isColorEditorView && !isProjectorEditorView && (
        <h2 className="page-title">
          {t(activeTab === 'advanced-monitoring' ? tabTitleKeys.general : tabTitleKeys[activeTab])}
        </h2>
      )}
      {renderContent()}
    </div>
  );
};

export default SettingsPage;
