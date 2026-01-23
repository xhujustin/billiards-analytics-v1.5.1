/**
 * Dashboard Component (v1.5) - 重新設計
 * 現代化佈局：頂部欄 + 側邊欄 + 主內容區
 */

import React, { useEffect, useState } from 'react';
import { useBilliardsSDK } from '../hooks/useBilliardsSDK';
import { Layout } from './Layout';
import { TopBar } from './TopBar';
import { Sidebar, type PageType } from './Sidebar';
import { StreamPage } from './pages/StreamPage';
import { SettingsPage } from './pages/SettingsPage';
import { AutoCalibrationPage } from './pages/AutoCalibrationPage';
import PracticePage from './pages/PracticePage';
import GamePage from './pages/GamePage';
import ReplayEntryPage from './pages/replay/ReplayEntryPage';
import ReplayListPage from './pages/replay/ReplayListPage';
import ReplayPlayer from './pages/replay/ReplayPlayer';
import StatsPage from './pages/replay/StatsPage';
import PlayerSelectionPage from './pages/replay/PlayerSelectionPage';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { session, isConnected, health, metadata, initialize } = useBilliardsSDK({
    apiBaseUrl: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
    wsBaseUrl: import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001',
  });

  const [burninUrl, setBurninUrl] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<PageType>('stream');
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);

  // 回放功能狀態
  const [replaySubPage, setReplaySubPage] = useState<'entry' | 'game' | 'practice' | 'player' | 'stats' | 'player-selection'>('entry');
  const [selectedGameId, setSelectedGameId] = useState<string>('');
  const [selectedPlayer, setSelectedPlayer] = useState<string>('');

  // 初始化連接
  useEffect(() => {
    initialize('camera1');
  }, [initialize]);

  // 構建 Burn-in URL
  useEffect(() => {
    if (session) {
      const fullUrl = `${import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001'}${session.burnin_url
        }?quality=med`;
      setBurninUrl(fullUrl);
    }
  }, [session]);

  // 同步 isAnalyzing 狀態（從 metadata.tracking_state）
  useEffect(() => {
    if (metadata) {
      setIsAnalyzing(metadata.tracking_state === 'active');
    }
  }, [metadata]);

  // 監聽 hash 路由變化
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash === '#/calibration') {
        setCurrentPage('calibration');
      }
    };

    // 初始檢查
    handleHashChange();

    // 監聽變化
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // YOLO 控制功能
  const handleToggleAnalysis = async () => {
    const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

    try {
      const response = await fetch(`${apiBaseUrl}/api/control/toggle`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setIsAnalyzing(data.is_analyzing);
      console.log('✅ YOLO toggle successful:', data);
    } catch (error) {
      console.error('❌ Failed to toggle YOLO analysis:', error);
      alert('切換辨識狀態失敗，請檢查後端連接');
    }
  };

  // 回放功能導航處理
  const handleReplayNavigate = (page: 'stats' | 'game' | 'practice') => {
    if (page === 'stats') {
      setReplaySubPage('player-selection');
    } else {
      setReplaySubPage(page);
    }
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

  // 渲染回放功能頁面
  const renderReplayPage = () => {
    switch (replaySubPage) {
      case 'player-selection':
        return (
          <PlayerSelectionPage
            onSelectPlayer={handleSelectPlayer}
            onBack={handleBackToReplayEntry}
          />
        );
      case 'stats':
        return (
          <StatsPage
            playerName={selectedPlayer}
            onBack={() => setReplaySubPage('player-selection')}
          />
        );
      case 'game':
        return (
          <ReplayListPage
            mode="game"
            onBack={handleBackToReplayEntry}
            onPlayRecording={handlePlayRecording}
          />
        );
      case 'practice':
        return (
          <ReplayListPage
            mode="practice"
            onBack={handleBackToReplayEntry}
            onPlayRecording={handlePlayRecording}
          />
        );
      case 'player':
        return (
          <ReplayPlayer
            gameId={selectedGameId}
            onBack={handleBackToReplayEntry}
          />
        );
      default:
        return <ReplayEntryPage onNavigate={handleReplayNavigate} />;
    }
  };

  // 渲染當前頁面
  const renderPage = () => {
    switch (currentPage) {
      case 'practice':
        return <PracticePage onNavigate={setCurrentPage} />;
      case 'game':
        return <GamePage onNavigate={setCurrentPage} />;
      case 'replay':
        return renderReplayPage();
      case 'stream':
        return (
          <StreamPage
            burninUrl={burninUrl}
            isAnalyzing={isAnalyzing}
            health={health}
            metadata={metadata}
            isConnected={isConnected}
          />
        );
      case 'settings':
        return <SettingsPage session={session} metadata={metadata} />;
      case 'calibration':
        return <AutoCalibrationPage />;
      default:
        return <StreamPage burninUrl={burninUrl} isAnalyzing={isAnalyzing} health={health} metadata={metadata} isConnected={isConnected} />;
    }
  };

  return (
    <Layout>
      <TopBar isAnalyzing={isAnalyzing} onToggleAnalysis={handleToggleAnalysis} />

      <div className="main-container">
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />

        <main className="main-content">
          {renderPage()}
        </main>
      </div>
    </Layout>
  );
};

export default Dashboard;
