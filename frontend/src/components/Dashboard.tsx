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
import { SessionPage } from './pages/SessionPage';
import { MetadataPage } from './pages/MetadataPage';
import { SettingsPage } from './pages/SettingsPage';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { session, isConnected, health, metadata, initialize } = useBilliardsSDK({
    apiBaseUrl: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
    wsBaseUrl: import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001',
  });

  const [burninUrl, setBurninUrl] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<PageType>('stream');
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);

  // 初始化連接
  useEffect(() => {
    initialize('camera1');
  }, [initialize]);

  // 構建 Burn-in URL
  useEffect(() => {
    if (session) {
      const fullUrl = `${import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001'}${
        session.burnin_url
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

  // 渲染當前頁面
  const renderPage = () => {
    switch (currentPage) {
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
      case 'session':
        return <SessionPage session={session} />;
      case 'metadata':
        return <MetadataPage metadata={metadata} />;
      case 'settings':
        return <SettingsPage />;
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
