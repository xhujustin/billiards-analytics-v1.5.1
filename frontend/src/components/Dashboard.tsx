import React, { useEffect, useRef, useState } from 'react';
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
import type { ThemeMode } from '../theme';
import './Dashboard.css';

const pageLabels: Record<PageType, string> = {
  stream: '即時影像',
  replay: '回放功能',
  practice: '練習模式',
  game: '遊玩模式',
  settings: '設定',
  account: '帳號管理',
  calibration: '投影機校正',
  'camera-params': '相機參數',
  'color-calibration': '顏色校正',
};

const formatCoachSessionTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  return `${month}/${day} ${hour}:${minute}`;
};

const createCoachSession = (page: PageType): CoachMenuSession => {
  const now = Date.now();
  return {
    id: `coach-session-${now}`,
    title: `${pageLabels[page]} ${formatCoachSessionTime(now)}`,
    createdAt: now,
    isPinned: false,
  };
};

const sortCoachSessions = (sessions: CoachMenuSession[]): CoachMenuSession[] => {
  return [...sessions].sort((a, b) => {
    if (a.isPinned !== b.isPinned) return a.isPinned ? -1 : 1;
    if (a.createdAt !== b.createdAt) return b.createdAt - a.createdAt;
    return b.id.localeCompare(a.id);
  });
};

interface DashboardProps {
  authSession: AuthSession;
  onAuthAction: () => void;
  onAuthSessionChange: (session: AuthSession) => void;
  onAccountDeleted: () => void;
  themeMode: ThemeMode;
  onThemeModeChange: (themeMode: ThemeMode) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  authSession,
  onAuthAction,
  onAuthSessionChange,
  onAccountDeleted,
  themeMode,
  onThemeModeChange,
}) => {
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
  const [coachSessions, setCoachSessions] = useState<CoachMenuSession[]>([]);
  const [activeCoachSessionId, setActiveCoachSessionId] = useState<string | null>(null);
  const [activeSettingsTab, setActiveSettingsTab] = useState<SettingsTab>('general');
  const [isDevMode, setIsDevMode] = useState(false);
  const [analysisManuallyStopped, setAnalysisManuallyStopped] = useState(false);
  const analysisEnsureInFlightRef = useRef(false);

  const activeCoachSession =
    coachSessions.find((sessionItem) => sessionItem.id === activeCoachSessionId) || coachSessions[0];

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
    if (metadata) {
      setIsAnalyzing(metadata.tracking_state === 'active');
    }
  }, [metadata]);

  useEffect(() => {
    if (!isDevMode && activeSettingsTab === 'advanced-monitoring') {
      setActiveSettingsTab('general');
    }
  }, [activeSettingsTab, isDevMode]);

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
      alert('切換辨識狀態失敗，請確認後端服務是否正常。');
    }
  };

  useEffect(() => {
    if (currentPage !== 'stream') return;
    if (isAnalyzing || analysisManuallyStopped) return;
    ensureAnalysisEnabled();
  }, [analysisManuallyStopped, currentPage, isAnalyzing]);

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
    restoreLiveOverlayForCoach();
    const nextSession = createCoachSession(currentPage);
    setCoachSessions((current) => [nextSession, ...current]);
    setActiveCoachSessionId(nextSession.id);
    setIsCoachMenuOpen(true);
    setIsCoachChatOpen(true);
  };

  const handleSelectCoachSession = (sessionId: string) => {
    restoreLiveOverlayForCoach();
    setActiveCoachSessionId(sessionId);
    setIsCoachMenuOpen(true);
    setIsCoachChatOpen(true);
  };

  const handleToggleCoach = () => {
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
        sessionTitle={activeCoachSession?.title || '對話'}
        displayMode={displayMode}
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
      isAnalyzing={isAnalyzing}
      health={health}
      metadata={metadata}
      isConnected={isConnected}
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
            session={session}
            metadata={metadata}
            apiBaseUrl={apiBaseUrl}
            aiCoachWsUrl={aiCoachWsUrl}
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
        return <ColorCalibrationPage onBack={() => handlePageChange('settings')} burninUrl={burninUrl} />;
      default:
        return renderStreamPage();
    }
  };

  const shouldShowEmbeddedCoach = currentPage !== 'settings' && isCoachChatOpen && Boolean(activeCoachSessionId);
  const sidebarPage: PageType =
    currentPage === 'calibration' || currentPage === 'color-calibration' || currentPage === 'camera-params'
      ? 'settings'
      : currentPage;
  const accountDisplayName =
    authSession.type === 'guest' ? '訪客' : `@${authSession.username || '使用者'}`;
  const authActionLabel = authSession.type === 'guest' ? '登入' : '登出';

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
          isCoachOpen={isCoachMenuOpen}
          onToggleCoach={handleToggleCoach}
          coachSessions={coachSessions}
          activeCoachSessionId={activeCoachSessionId || undefined}
          onCreateCoachSession={handleCreateCoachSession}
          onSelectCoachSession={handleSelectCoachSession}
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
