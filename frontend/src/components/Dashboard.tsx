import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AuthSession } from './AuthScreens';
import { useBilliardsSDK } from '../hooks/useBilliardsSDK';
import { Layout } from './Layout';
import { TopBar } from './TopBar';
import { Sidebar, type CoachMenuSession, type PageType } from './Sidebar';
import { StreamPage } from './pages/StreamPage';
import { SettingsPage, type SettingsTab } from './pages/SettingsPage';
import { AutoCalibrationPage } from './pages/AutoCalibrationPage';
import { CameraParamsPage } from './pages/CameraParamsPage';
import ColorCalibrationPage from './pages/ColorCalibrationPage';
import PracticePage from './pages/PracticePage';
import GamePage from './pages/GamePage';
import AccountManagementPage from './pages/AccountManagementPage';
import ReplayEntryPage from './pages/replay/ReplayEntryPage';
import ReplayListPage from './pages/replay/ReplayListPage';
import ReplayPlayer from './pages/replay/ReplayPlayer';
import StatsPage from './pages/replay/StatsPage';
import PlayerSelectionPage from './pages/replay/PlayerSelectionPage';
import AICoachFloatingChat from './AICoachFloatingChat';
import type { AccentColorMode, FontSizeMode, ResolvedTheme, ThemeMode } from '../theme';
import type { SupportedLanguage } from '../i18n/types';
import './Dashboard.css';

const DEV_MODE_STORAGE_KEY = 'billiards_dev_mode';
const COACH_SESSIONS_STORAGE_KEY = 'ai-coach-sessions-v1';
const ACTIVE_COACH_SESSION_STORAGE_KEY = 'ai-coach-active-session-v1';
type StreamQuality = 'low' | 'med' | 'high';

const getStoredStreamQuality = (authSession: AuthSession): StreamQuality => {
  if (authSession.type === 'guest') return 'med';
  const userKey = `stream-quality:${authSession.username || 'user'}`;
  const saved = window.localStorage.getItem(userKey) || window.localStorage.getItem('stream-quality');
  return saved === 'low' || saved === 'med' || saved === 'high' ? saved : 'med';
};

const pageLabelKeys: Record<PageType, string> = {
  stream: 'nav.stream',
  replay: 'nav.replay',
  practice: 'nav.practice',
  game: 'nav.game',
  settings: 'nav.settings',
  account: 'nav.account',
  calibration: 'nav.calibration',
  'camera-params': 'nav.cameraParams',
  'color-calibration': 'nav.colorCalibration',
};

const formatCoachSessionTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  return `${month}/${day} ${hour}:${minute}`;
};

const createCoachSession = (pageLabel: string): CoachMenuSession => {
  const now = Date.now();
  return {
    id: `coach-session-${now}`,
    title: `${pageLabel} ${formatCoachSessionTime(now)}`,
    createdAt: now,
    isPinned: false,
  };
};

const loadStoredCoachSessions = (): CoachMenuSession[] => {
  try {
    const storedValue = window.localStorage.getItem(COACH_SESSIONS_STORAGE_KEY);
    if (!storedValue) return [];

    const parsedValue = JSON.parse(storedValue) as CoachMenuSession[];
    if (!Array.isArray(parsedValue)) return [];

    return parsedValue.filter(
      (sessionItem) =>
        sessionItem &&
        typeof sessionItem.id === 'string' &&
        typeof sessionItem.title === 'string' &&
        typeof sessionItem.createdAt === 'number' &&
        typeof sessionItem.isPinned === 'boolean',
    );
  } catch {
    window.localStorage.removeItem(COACH_SESSIONS_STORAGE_KEY);
    return [];
  }
};

const loadStoredActiveCoachSessionId = (sessions: CoachMenuSession[]): string | null => {
  try {
    const storedValue = window.localStorage.getItem(ACTIVE_COACH_SESSION_STORAGE_KEY);
    if (storedValue && sessions.some((sessionItem) => sessionItem.id === storedValue)) {
      return storedValue;
    }
  } catch {
    window.localStorage.removeItem(ACTIVE_COACH_SESSION_STORAGE_KEY);
  }

  return sessions[0]?.id || null;
};

const sortCoachSessions = (sessions: CoachMenuSession[]): CoachMenuSession[] => {
  return [...sessions].sort((a, b) => {
    if (a.isPinned !== b.isPinned) return a.isPinned ? -1 : 1;
    if (a.createdAt !== b.createdAt) return b.createdAt - a.createdAt;
    return b.id.localeCompare(a.id);
  });
};

const loadDevModePreference = (): boolean => {
  return false;
};

interface DashboardProps {
  authSession: AuthSession;
  onAuthAction: () => void;
  onAuthSessionChange: (session: AuthSession) => void;
  onAccountDeleted: () => void;
  themeMode: ThemeMode;
  onThemeModeChange: (themeMode: ThemeMode) => void;
  resolvedTheme: ResolvedTheme;
  accentColorMode: AccentColorMode;
  onAccentColorModeChange: (accentColorMode: AccentColorMode) => void;
  fontSizeMode: FontSizeMode;
  onFontSizeModeChange: (fontSizeMode: FontSizeMode) => void;
  language: SupportedLanguage;
  onLanguageChange: (language: SupportedLanguage) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  authSession,
  onAuthAction,
  onAuthSessionChange,
  onAccountDeleted,
  themeMode,
  onThemeModeChange,
  resolvedTheme,
  accentColorMode,
  onAccentColorModeChange,
  fontSizeMode,
  onFontSizeModeChange,
  language,
  onLanguageChange,
}) => {
  const { t } = useTranslation();
  const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';
  const wsBaseUrl =
    import.meta.env.VITE_BACKEND_WS ||
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
  const aiCoachWsUrl = import.meta.env.VITE_AI_COACH_WS || 'ws://localhost:8010/ws/coach';
  const { session, isConnected, health, metadata, initialize } = useBilliardsSDK({
    apiBaseUrl,
    wsBaseUrl,
  });

  const [burninUrl, setBurninUrl] = useState('');
  const [currentPage, setCurrentPage] = useState<PageType>('stream');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isCoachMenuOpen, setIsCoachMenuOpen] = useState(false);
  const [isCoachChatOpen, setIsCoachChatOpen] = useState(false);
  const [coachSessions, setCoachSessions] = useState<CoachMenuSession[]>(loadStoredCoachSessions);
  const [activeCoachSessionId, setActiveCoachSessionId] = useState<string | null>(() =>
    loadStoredActiveCoachSessionId(loadStoredCoachSessions()),
  );
  const [activeSettingsTab, setActiveSettingsTab] = useState<SettingsTab>('general');
  const [isDevMode, setIsDevMode] = useState(loadDevModePreference);
  const [streamQuality, setStreamQuality] = useState<StreamQuality>(() => getStoredStreamQuality(authSession));
  const [analysisManuallyStopped, setAnalysisManuallyStopped] = useState(false);
  const analysisEnsureInFlightRef = useRef(false);

  const activeCoachSession =
    coachSessions.find((sessionItem) => sessionItem.id === activeCoachSessionId) || coachSessions[0];
  const isCoachAllowedPage = currentPage === 'stream' || currentPage === 'practice' || currentPage === 'game';

  const [replaySubPage, setReplaySubPage] = useState<
    'entry' | 'game' | 'practice' | 'player' | 'stats' | 'player-selection'
  >('entry');
  const [selectedGameId, setSelectedGameId] = useState('');
  const [selectedPlayer, setSelectedPlayer] = useState('');

  useEffect(() => {
    initialize('camera1');
  }, [initialize]);

  useEffect(() => {
    if (session) {
      setBurninUrl(`${apiBaseUrl}${session.burnin_url}?quality=med`);
    }
  }, [apiBaseUrl, session]);

  useEffect(() => {
    try {
      window.localStorage.setItem(COACH_SESSIONS_STORAGE_KEY, JSON.stringify(coachSessions));
    } catch {
      // localStorage 不可用時，對話清單仍會保留在目前頁面狀態。
    }
  }, [coachSessions]);

  useEffect(() => {
    try {
      if (activeCoachSessionId) {
        window.localStorage.setItem(ACTIVE_COACH_SESSION_STORAGE_KEY, activeCoachSessionId);
      } else {
        window.localStorage.removeItem(ACTIVE_COACH_SESSION_STORAGE_KEY);
      }
    } catch {
      // localStorage 不可用時略過持久化。
    }
  }, [activeCoachSessionId]);

  useEffect(() => {
    if (metadata) {
      setIsAnalyzing(metadata.tracking_state === 'active');
    }
  }, [metadata]);

  useEffect(() => {
    if (!isDevMode && activeSettingsTab === 'advanced-monitoring') {
      setActiveSettingsTab('general');
    }
  }, [activeSettingsTab, isDevMode]);

  useEffect(() => {
    setStreamQuality(getStoredStreamQuality(authSession));
  }, [authSession]);

  const handleStreamQualityChange = (nextQuality: StreamQuality) => {
    setStreamQuality(nextQuality);
    if (authSession.type !== 'user') return;
    window.localStorage.setItem(`stream-quality:${authSession.username || 'user'}`, nextQuality);
  };

  useEffect(() => {
    try {
      window.localStorage.setItem(DEV_MODE_STORAGE_KEY, String(isDevMode));
    } catch {
      // localStorage 可能在隱私模式或受限環境失效，開關仍維持本次 session 狀態。
    }
  }, [isDevMode]);

  const setAnalysisEnabled = async (enabled: boolean) => {
    const response = await fetch(`${apiBaseUrl}/api/control/analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    setIsAnalyzing(Boolean(data.is_analyzing));
    return Boolean(data.is_analyzing);
  };

  const ensureAnalysisEnabled = async () => {
    if (analysisEnsureInFlightRef.current) return;
    analysisEnsureInFlightRef.current = true;
    try {
      await setAnalysisEnabled(true);
      setAnalysisManuallyStopped(false);
    } catch (error) {
      console.warn('啟動辨識失敗:', error);
    } finally {
      analysisEnsureInFlightRef.current = false;
    }
  };

  const handleToggleAnalysis = async () => {
    try {
      const nextEnabled = !isAnalyzing;
      const applied = await setAnalysisEnabled(nextEnabled);
      setAnalysisManuallyStopped(!applied);
    } catch (error) {
      console.error('Failed to toggle YOLO analysis:', error);
      alert(t('app.toggleAnalysisFailed'));
    }
  };

  useEffect(() => {
    if (currentPage !== 'stream') return;
    if (isAnalyzing || analysisManuallyStopped) return;
    ensureAnalysisEnabled();
  }, [analysisManuallyStopped, currentPage, isAnalyzing]);

  useEffect(() => {
    if (isCoachAllowedPage) return;
    setIsCoachMenuOpen(false);
    setIsCoachChatOpen(false);
  }, [isCoachAllowedPage]);

  const handlePageChange = (page: PageType) => {
    if (currentPage === 'practice' && page !== 'practice') {
      fetch(`${apiBaseUrl}/api/practice/end`, { method: 'POST' }).catch((error) => {
        console.warn('結束練習失敗:', error);
      });
      fetch(`${apiBaseUrl}/api/control/overlay-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'full' }),
      }).catch((error) => {
        console.warn('恢復完整標註失敗:', error);
      });
    }
    if (page !== 'practice') {
      fetch(`${apiBaseUrl}/api/planner/disable`, { method: 'POST' }).catch((error) => {
        console.warn('停用路徑規劃失敗:', error);
      });
    }
    setCurrentPage(page);
  };

  const restoreLiveOverlayForCoach = () => {
    if (currentPage === 'practice') {
      fetch(`${apiBaseUrl}/api/practice/end`, { method: 'POST' }).catch((error) => {
        console.warn('結束練習失敗:', error);
      });
      setCurrentPage('stream');
    }

    fetch(`${apiBaseUrl}/api/planner/disable`, { method: 'POST' }).catch((error) => {
      console.warn('停用路徑規劃失敗:', error);
    });
    fetch(`${apiBaseUrl}/api/control/overlay-mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'full' }),
    }).catch((error) => {
      console.warn('恢復完整標註失敗:', error);
    });

    if (!isAnalyzing) {
      ensureAnalysisEnabled();
    }
  };

  const handleCreateCoachSession = () => {
    if (!isCoachAllowedPage) return;
    restoreLiveOverlayForCoach();
    const nextSession = createCoachSession(t(pageLabelKeys[currentPage]));
    setCoachSessions((current) => [nextSession, ...current]);
    setActiveCoachSessionId(nextSession.id);
    setIsCoachMenuOpen(true);
    setIsCoachChatOpen(true);
  };

  const handleSelectCoachSession = (sessionId: string) => {
    if (!isCoachAllowedPage) return;
    restoreLiveOverlayForCoach();
    setActiveCoachSessionId(sessionId);
    setIsCoachMenuOpen(true);
    setIsCoachChatOpen(true);
  };

  const handleToggleCoach = () => {
    if (!isCoachAllowedPage) return;
    const nextOpen = !isCoachMenuOpen;
    if (nextOpen) {
      restoreLiveOverlayForCoach();
    }
    setIsCoachMenuOpen(nextOpen);
    setIsCoachChatOpen(false);
  };

  const handleRenameCoachSession = (sessionId: string, title: string) => {
    setCoachSessions((current) =>
      current.map((sessionItem) =>
        sessionItem.id === sessionId ? { ...sessionItem, title } : sessionItem,
      ),
    );
  };

  const handleToggleCoachSessionPin = (sessionId: string) => {
    setCoachSessions((current) =>
      current.map((sessionItem) =>
        sessionItem.id === sessionId
          ? { ...sessionItem, isPinned: !sessionItem.isPinned }
          : sessionItem,
      ),
    );
  };

  const handleDeleteCoachSession = (sessionId: string) => {
    setCoachSessions((current) => {
      const sortedSessions = sortCoachSessions(current);
      const nextSessions = current.filter((sessionItem) => sessionItem.id !== sessionId);

      if (nextSessions.length === 0) {
        setActiveCoachSessionId(null);
        setIsCoachChatOpen(false);
        setIsCoachMenuOpen(true);
        return [];
      }

      if (sessionId === activeCoachSessionId) {
        const deletedIndex = sortedSessions.findIndex((sessionItem) => sessionItem.id === sessionId);
        const previousSession = sortedSessions[deletedIndex - 1];
        const nextSession = sortedSessions[deletedIndex + 1];
        const fallbackSession = previousSession || nextSession || sortCoachSessions(nextSessions)[0];
        setActiveCoachSessionId(fallbackSession.id);
      }

      return nextSessions;
    });
  };

  const handleCloseAndDeleteCoachSession = () => {
    if (activeCoachSessionId) {
      handleDeleteCoachSession(activeCoachSessionId);
    }
    setIsCoachChatOpen(false);
    setIsCoachMenuOpen(true);
  };

  const handleReplayNavigate = (page: 'stats' | 'game' | 'practice') => {
    setReplaySubPage(page === 'stats' ? 'player-selection' : page);
  };

  const handleSelectPlayer = (playerName: string) => {
    setSelectedPlayer(playerName);
    setReplaySubPage('stats');
  };

  const handlePlayRecording = (gameId: string) => {
    setSelectedGameId(gameId);
    setReplaySubPage('player');
  };

  const handleBackToReplayEntry = () => {
    setReplaySubPage('entry');
    setSelectedGameId('');
  };

  const renderCoachChat = (displayMode: 'floating' | 'embedded') => {
    if (!activeCoachSessionId) return null;

    return (
      <AICoachFloatingChat
        apiBaseUrl={apiBaseUrl}
        metadata={metadata}
        isOpen={isCoachChatOpen}
        onMinimize={() => setIsCoachChatOpen(false)}
        onClose={handleCloseAndDeleteCoachSession}
        sessionId={activeCoachSessionId}
        sessionTitle={activeCoachSession?.title || t('sidebar.conversation')}
        language={language}
        displayMode={displayMode}
        authSession={authSession}
        accentColorMode={accentColorMode}
      />
    );
  };

  const renderReplayPage = () => {
    switch (replaySubPage) {
      case 'player-selection':
        return <PlayerSelectionPage onSelectPlayer={handleSelectPlayer} onBack={handleBackToReplayEntry} />;
      case 'stats':
        return <StatsPage playerName={selectedPlayer} onBack={() => setReplaySubPage('player-selection')} />;
      case 'game':
        return <ReplayListPage mode="game" onBack={handleBackToReplayEntry} onPlayRecording={handlePlayRecording} />;
      case 'practice':
        return <ReplayListPage mode="practice" onBack={handleBackToReplayEntry} onPlayRecording={handlePlayRecording} />;
      case 'player':
        return <ReplayPlayer gameId={selectedGameId} onBack={handleBackToReplayEntry} />;
      default:
        return <ReplayEntryPage onNavigate={handleReplayNavigate} />;
    }
  };

  const renderStreamPage = () => (
    <StreamPage
      burninUrl={burninUrl}
      quality={streamQuality}
      isAnalyzing={isAnalyzing}
      health={health}
      metadata={metadata}
      isConnected={isConnected}
      isDevMode={isDevMode}
    />
  );

  const renderPage = () => {
    switch (currentPage) {
      case 'practice':
        return <PracticePage onNavigate={handlePageChange} metadata={metadata} />;
      case 'game':
        return <GamePage onNavigate={handlePageChange} />;
      case 'replay':
        return renderReplayPage();
      case 'stream':
        return renderStreamPage();
      case 'settings':
        return (
          <SettingsPage
            activeTab={activeSettingsTab}
            isDevMode={isDevMode}
            onDevModeChange={setIsDevMode}
            themeMode={themeMode}
            onThemeModeChange={onThemeModeChange}
            resolvedTheme={resolvedTheme}
            accentColorMode={accentColorMode}
            onAccentColorModeChange={onAccentColorModeChange}
            fontSizeMode={fontSizeMode}
            onFontSizeModeChange={onFontSizeModeChange}
            language={language}
            onLanguageChange={onLanguageChange}
            streamQuality={streamQuality}
            onStreamQualityChange={handleStreamQualityChange}
            session={session}
            metadata={metadata}
            apiBaseUrl={apiBaseUrl}
            aiCoachWsUrl={aiCoachWsUrl}
            burninUrl={burninUrl}
            onNavigate={handlePageChange}
          />
        );
      case 'account':
        return (
          <AccountManagementPage
            authSession={authSession}
            onSessionChange={onAuthSessionChange}
            onLoginRequest={onAuthAction}
            onAccountDeleted={onAccountDeleted}
          />
        );
      case 'calibration':
        return <AutoCalibrationPage onBack={() => handlePageChange('settings')} burninUrl={burninUrl} />;
      case 'camera-params':
        return <CameraParamsPage onBack={() => handlePageChange('settings')} />;
      case 'color-calibration':
        return (
          <ColorCalibrationPage
            onBack={() => handlePageChange('settings')}
            burninUrl={burninUrl}
          />
        );
      default:
        return renderStreamPage();
    }
  };

  const shouldShowEmbeddedCoach = isCoachAllowedPage && isCoachChatOpen && Boolean(activeCoachSessionId);
  const sidebarPage: PageType =
    currentPage === 'calibration' || currentPage === 'color-calibration' || currentPage === 'camera-params'
      ? 'settings'
      : currentPage;
  const accountDisplayName =
    authSession.type === 'guest' ? t('common.guest') : `@${authSession.username || t('auth.username')}`;
  const authActionLabel = authSession.type === 'guest' ? t('common.login') : t('common.logout');

  return (
    <Layout>
      <TopBar
        isAnalyzing={isAnalyzing}
        onToggleAnalysis={handleToggleAnalysis}
        onHomeClick={() => handlePageChange('stream')}
      />

      <div className="main-container">
        <Sidebar
          currentPage={sidebarPage}
          onPageChange={handlePageChange}
          isCoachOpen={isCoachAllowedPage && isCoachMenuOpen}
          onToggleCoach={isCoachAllowedPage ? handleToggleCoach : undefined}
          coachSessions={coachSessions}
          activeCoachSessionId={activeCoachSessionId || undefined}
          onCreateCoachSession={isCoachAllowedPage ? handleCreateCoachSession : undefined}
          onSelectCoachSession={isCoachAllowedPage ? handleSelectCoachSession : undefined}
          onRenameCoachSession={handleRenameCoachSession}
          onToggleCoachSessionPin={handleToggleCoachSessionPin}
          onDeleteCoachSession={handleDeleteCoachSession}
          activeSettingsTab={activeSettingsTab}
          isDevMode={isDevMode}
          onSettingsTabChange={setActiveSettingsTab}
          accountDisplayName={accountDisplayName}
          authActionLabel={authActionLabel}
          onOpenAccountManagement={() => handlePageChange('account')}
          onAuthAction={onAuthAction}
        />

        <main className={`main-content ${shouldShowEmbeddedCoach ? 'with-coach' : ''}`}>
          {shouldShowEmbeddedCoach && (
            <aside className="main-embedded-coach">
              {renderCoachChat('embedded')}
            </aside>
          )}
          <div className="main-page-content">{renderPage()}</div>
        </main>
      </div>
    </Layout>
  );
};

export default Dashboard;
