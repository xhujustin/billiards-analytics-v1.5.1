import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { PageType } from './Sidebar';
import cueVexLogo from '../../CueVex logo.png';
import './TopBar.css';

interface TopBarProps {
  currentPage: PageType;
  activeNavId?: string;
  isAnalyzing: boolean;
  onToggleAnalysis: () => Promise<void>;
  onNavigate: (page: PageType) => void;
  onOpenAnalysis: () => void;
  onOpenHistory: () => void;
  accountDisplayName: string;
  authActionLabel: string;
  onOpenAccountManagement: () => void;
  onAuthAction: () => void;
}

const navItems: Array<{
  id: string;
  label: string;
  page?: PageType;
  action?: 'analysis' | 'history';
}> = [
  { id: 'home', label: '監控', page: 'stream' },
  { id: 'analysis', label: '分析', action: 'analysis' },
  { id: 'training', label: '訓練', page: 'practice' },
  { id: 'game', label: '遊戲', page: 'game' },
  { id: 'history', label: '歷史', action: 'history' },
];

const deriveActiveNavId = (page: PageType): string => {
  if (page === 'stream') return 'home';
  if (page === 'replay') return 'history';
  if (page === 'practice') return 'training';
  if (page === 'settings' || page === 'calibration' || page === 'camera-params' || page === 'color-calibration') {
    return 'settings';
  }
  return page;
};

export const TopBar: React.FC<TopBarProps> = ({
  currentPage,
  activeNavId,
  isAnalyzing,
  onToggleAnalysis,
  onNavigate,
  onOpenAnalysis,
  onOpenHistory,
  accountDisplayName,
  authActionLabel,
  onOpenAccountManagement,
  onAuthAction,
}) => {
  const { t } = useTranslation();
  const [isToggling, setIsToggling] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const resolvedActiveNavId = activeNavId || deriveActiveNavId(currentPage);
  const normalizedAuthLabel = authActionLabel.toLowerCase().includes('logout') || authActionLabel.includes('登出') ? '登出' : '登入';
  const analysisStatusLabel = isAnalyzing ? t('topBar.analysisActive') : t('topBar.analysisStandby');
  const analysisActionLabel = isToggling
    ? t('topBar.analysisToggling')
    : isAnalyzing
      ? t('topBar.stopAnalysis')
      : t('topBar.startAnalysis');

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      await onToggleAnalysis();
    } finally {
      setIsToggling(false);
    }
  };

  const handleNavClick = (item: (typeof navItems)[number]) => {
    setIsAccountMenuOpen(false);
    if (item.action === 'analysis') {
      onOpenAnalysis();
      return;
    }
    if (item.action === 'history') {
      onOpenHistory();
      return;
    }
    if (item.page) onNavigate(item.page);
  };

  const handleAccountMenuAction = (action: () => void) => {
    setIsAccountMenuOpen(false);
    action();
  };

  return (
    <header className="top-bar">
      <button className="top-brand" type="button" onClick={() => onNavigate('stream')}>
        <span className="top-brand-mark" aria-hidden="true">
          <img src={cueVexLogo} alt="" />
        </span>
        <span className="top-brand-copy">
          <strong>CueVex</strong>
          <small>智慧分析，精準進步。</small>
        </span>
      </button>

      <nav className="top-nav" aria-label="主要導覽">
        {navItems.map((item) => (
          <button
            className={`top-nav-item ${resolvedActiveNavId === item.id ? 'active' : ''}`}
            key={item.id}
            type="button"
            onClick={() => handleNavClick(item)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="top-actions">
        <div className="top-analysis-controls" aria-label={t('topBar.analysisControls')}>
          <button
            className={`top-analysis-status ${isAnalyzing ? 'is-active' : 'is-standby'}`}
            type="button"
            disabled
            aria-live="polite"
          >
            {analysisStatusLabel}
          </button>
          <button
            className={`top-analysis-action ${isAnalyzing ? 'is-stop' : 'is-start'}`}
            type="button"
            aria-label={analysisActionLabel}
            onClick={handleToggle}
            disabled={isToggling}
          >
            {analysisActionLabel}
          </button>
        </div>
        <div className="top-account">
          <button
            className="top-account-button"
            type="button"
            onClick={() => setIsAccountMenuOpen((value) => !value)}
          >
            <span>
              <strong>{accountDisplayName}</strong>
            </span>
            <span className="top-account-orb" aria-hidden="true" />
            <span className="top-account-chevron" aria-hidden="true" />
          </button>
          {isAccountMenuOpen && (
            <div className="top-account-menu">
              <button type="button" onClick={() => handleAccountMenuAction(onOpenAccountManagement)}>
                帳號管理
              </button>
              <button type="button" onClick={() => handleAccountMenuAction(() => onNavigate('settings'))}>
                設定
              </button>
              <button type="button" onClick={() => handleAccountMenuAction(onAuthAction)}>
                {normalizedAuthLabel}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default TopBar;
