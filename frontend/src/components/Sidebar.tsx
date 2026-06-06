import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { SettingsTab } from './pages/SettingsPage';
import './Sidebar.css';

export type PageType =
  | 'practice'
  | 'game'
  | 'stream'
  | 'settings'
  | 'replay'
  | 'account'
  | 'calibration'
  | 'camera-params'
  | 'color-calibration';

export interface CoachMenuSession {
  id: string;
  title: string;
  createdAt: number;
  isPinned: boolean;
}

interface CoachMenuPosition {
  left: number;
  top: number;
}

interface SidebarProps {
  currentPage: PageType;
  onPageChange: (page: PageType) => void;
  isCoachOpen?: boolean;
  onToggleCoach?: () => void;
  isCoachHistoryEnabled?: boolean;
  coachSessions?: CoachMenuSession[];
  activeCoachSessionId?: string;
  onCreateCoachSession?: () => void;
  onSelectCoachSession?: (sessionId: string) => void;
  onRenameCoachSession?: (sessionId: string, title: string) => void;
  onToggleCoachSessionPin?: (sessionId: string) => void;
  onDeleteCoachSession?: (sessionId: string) => void;
  activeSettingsTab?: SettingsTab;
  isDevMode?: boolean;
  onSettingsTabChange?: (tab: SettingsTab) => void;
  accountDisplayName?: string;
  authActionLabel?: string;
  onOpenAccountManagement?: () => void;
  onAuthAction?: () => void;
}

interface MenuItem {
  id: PageType;
  labelKey: string;
}

const primaryItems: MenuItem[] = [
  { id: 'stream', labelKey: 'nav.stream' },
  { id: 'replay', labelKey: 'nav.replay' },
  { id: 'practice', labelKey: 'nav.practice' },
  { id: 'game', labelKey: 'nav.game' },
];

const settingsTabItems: Array<{ id: SettingsTab; labelKey: string; requiresDevMode?: boolean }> = [
  { id: 'general', labelKey: 'settings.tabs.general' },
  { id: 'appearance', labelKey: 'settings.tabs.appearance' },
  { id: 'camera', labelKey: 'settings.tabs.camera' },
  { id: 'table-calibration', labelKey: 'settings.tabs.tableCalibration' },
  { id: 'tracking', labelKey: 'settings.tabs.tracking' },
];

const sortCoachSessions = (sessions: CoachMenuSession[]): CoachMenuSession[] => {
  return [...sessions].sort((a, b) => {
    if (a.isPinned !== b.isPinned) return a.isPinned ? -1 : 1;
    if (a.createdAt !== b.createdAt) return b.createdAt - a.createdAt;
    return b.id.localeCompare(a.id);
  });
};

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onPageChange,
  isCoachOpen = false,
  onToggleCoach,
  isCoachHistoryEnabled = true,
  coachSessions = [],
  activeCoachSessionId,
  onCreateCoachSession,
  onSelectCoachSession,
  onRenameCoachSession,
  onToggleCoachSessionPin,
  onDeleteCoachSession,
  activeSettingsTab = 'general',
  isDevMode = false,
  onSettingsTabChange,
  accountDisplayName,
  authActionLabel,
  onOpenAccountManagement,
  onAuthAction,
}) => {
  const { t } = useTranslation();
  const [openCoachMenuSessionId, setOpenCoachMenuSessionId] = useState<string | null>(null);
  const [openCoachMenuPosition, setOpenCoachMenuPosition] = useState<CoachMenuPosition | null>(null);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameInput, setRenameInput] = useState('');
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const sortedCoachSessions = useMemo(() => sortCoachSessions(coachSessions), [coachSessions]);
  const isCoachSectionOpen = isCoachOpen;

  const closeCoachSessionMenu = () => {
    setOpenCoachMenuSessionId(null);
    setOpenCoachMenuPosition(null);
  };

  const startRename = (event: React.MouseEvent<HTMLButtonElement>, session: CoachMenuSession) => {
    event.stopPropagation();
    closeCoachSessionMenu();
    setRenamingSessionId(session.id);
    setRenameInput(session.title);
  };

  const submitRename = (event: React.FormEvent<HTMLFormElement>, sessionId: string) => {
    event.stopPropagation();
    event.preventDefault();
    const title = renameInput.trim();
    if (title) onRenameCoachSession?.(sessionId, title);
    setRenamingSessionId(null);
    setRenameInput('');
  };

  return (
    <aside
      className={`sidebar ${isSidebarCollapsed ? 'is-collapsed' : ''}`}
      onClick={() => {
        closeCoachSessionMenu();
        setIsSettingsMenuOpen(false);
      }}
    >
      <button
        className="sidebar-collapse-toggle"
        type="button"
        aria-label={isSidebarCollapsed ? t('sidebar.expandSidebar') : t('sidebar.collapseSidebar')}
        aria-expanded={!isSidebarCollapsed}
        onClick={(event) => {
          event.stopPropagation();
          closeCoachSessionMenu();
          setRenamingSessionId(null);
          setIsSettingsMenuOpen(false);
          setIsSidebarCollapsed((current) => !current);
        }}
      >
        <span aria-hidden="true">{isSidebarCollapsed ? '›' : '‹'}</span>
      </button>
      <nav className="sidebar-nav" aria-label={t('nav.mainMenu')}>
        {currentPage === 'settings' ? (
          <>
            <button
              className="sidebar-item sidebar-back-item"
              onClick={(event) => {
                event.stopPropagation();
                closeCoachSessionMenu();
                setRenamingSessionId(null);
                setIsSettingsMenuOpen(false);
                onPageChange('stream');
              }}
              type="button"
            >
              <span className="sidebar-back-arrow" aria-hidden="true">
                &larr;
              </span>
              <span>{t('nav.backToMain')}</span>
            </button>
            {settingsTabItems
              .filter((item) => !item.requiresDevMode || isDevMode)
              .map((item) => (
                <button
                  key={item.id}
                  className={`sidebar-item ${activeSettingsTab === item.id ? 'active' : ''}`}
                  onClick={() => onSettingsTabChange?.(item.id)}
                  type="button"
                >
                  {t(item.labelKey)}
                </button>
              ))}
          </>
        ) : onToggleCoach ? (
          <>
            <button
              type="button"
              className={`sidebar-item sidebar-dropdown-toggle sidebar-coach-button ${isCoachSectionOpen ? 'active' : ''}`}
              onClick={(event) => {
                event.stopPropagation();
                setRenamingSessionId(null);
                closeCoachSessionMenu();
                setIsSettingsMenuOpen(false);
                onToggleCoach();
              }}
            >
              <span>AI 教練</span>
              <span className="sidebar-chevron" aria-hidden="true" />
            </button>
            {isCoachSectionOpen && (
              <section className="sidebar-coach sidebar-coach-menu">
                <button
                  className="sidebar-item sidebar-new-conversation-button"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setRenamingSessionId(null);
                    closeCoachSessionMenu();
                    onCreateCoachSession?.();
                  }}
                >
                  {isCoachHistoryEnabled ? t('sidebar.newConversation') : t('aiCoach.guestOneTimeChat')}
                </button>
                {isCoachHistoryEnabled ? (
                  <>
                    <div className="sidebar-coach-menu-header">
                      <span>{t('sidebar.conversation')}</span>
                    </div>

                    <div className="sidebar-coach-session-list">
                      {sortedCoachSessions.length === 0 && (
                        <div className="sidebar-coach-empty">{t('sidebar.noConversation')}</div>
                      )}

                      {sortedCoachSessions.map((session) => (
                        <div
                          className={`sidebar-coach-session ${
                            session.id === activeCoachSessionId ? 'active' : ''
                          }`}
                          key={session.id}
                          role="button"
                          tabIndex={0}
                          onClick={(event) => {
                            event.stopPropagation();
                            setRenamingSessionId(null);
                            closeCoachSessionMenu();
                            onSelectCoachSession?.(session.id);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.stopPropagation();
                              setRenamingSessionId(null);
                              closeCoachSessionMenu();
                              onSelectCoachSession?.(session.id);
                            }
                          }}
                        >
                          {renamingSessionId === session.id ? (
                            <form
                              className="sidebar-coach-rename-form"
                              onSubmit={(event) => submitRename(event, session.id)}
                              onClick={(event) => event.stopPropagation()}
                              onKeyDown={(event) => {
                                event.stopPropagation();
                                if (event.key === 'Escape') {
                                  setRenamingSessionId(null);
                                  setRenameInput('');
                                }
                              }}
                            >
                              <input
                                value={renameInput}
                                onChange={(event) => setRenameInput(event.target.value)}
                                onFocus={(event) => event.currentTarget.select()}
                                autoFocus
                                maxLength={32}
                              />
                              <div className="sidebar-coach-rename-actions">
                                <button type="submit">{t('common.confirm')}</button>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setRenamingSessionId(null);
                                    setRenameInput('');
                                  }}
                                >
                                  {t('common.cancel')}
                                </button>
                              </div>
                            </form>
                          ) : (
                            <>
                              <div className="sidebar-coach-session-row">
                                <span className="sidebar-coach-session-main">
                                  <span className="sidebar-coach-session-title">
                                    {session.isPinned ? `[${t('sidebar.pinned')}] ` : ''}
                                    {session.title}
                                  </span>
                                </span>

                                <button
                                  className="sidebar-coach-session-options"
                                  type="button"
                                  aria-label={t('sidebar.conversationOptions')}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setRenamingSessionId(null);
                                    const buttonRect = event.currentTarget.getBoundingClientRect();
                                    const menuWidth = 152;
                                    const estimatedMenuHeight = 118;
                                    const gap = 6;
                                    const viewportPadding = 8;
                                    const maxLeft = window.innerWidth - menuWidth - viewportPadding;
                                    const hasRoomBelow =
                                      buttonRect.bottom + estimatedMenuHeight + gap <=
                                      window.innerHeight - viewportPadding;
                                    const left = Math.max(
                                      viewportPadding,
                                      Math.min(maxLeft, buttonRect.right - menuWidth),
                                    );
                                    const top = hasRoomBelow
                                      ? buttonRect.bottom + gap
                                      : Math.max(
                                          viewportPadding,
                                          buttonRect.top - estimatedMenuHeight - gap,
                                        );

                                    if (openCoachMenuSessionId === session.id) {
                                      closeCoachSessionMenu();
                                      return;
                                    }

                                    setOpenCoachMenuPosition({ left, top });
                                    setOpenCoachMenuSessionId(session.id);
                                  }}
                                >
                                  ...
                                </button>
                              </div>

                              {openCoachMenuSessionId === session.id && (
                                <div
                                  className="sidebar-coach-session-dropdown"
                                  style={
                                    openCoachMenuPosition
                                      ? {
                                          left: `${openCoachMenuPosition.left}px`,
                                          top: `${openCoachMenuPosition.top}px`,
                                        }
                                      : undefined
                                  }
                                  onClick={(event) => event.stopPropagation()}
                                >
                                  <button type="button" onClick={(event) => startRename(event, session)}>
                                    {t('common.rename')}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      closeCoachSessionMenu();
                                      onToggleCoachSessionPin?.(session.id);
                                    }}
                                  >
                                    {session.isPinned ? t('sidebar.unpin') : t('sidebar.pin')}
                                  </button>
                                  <button
                                    className="sidebar-coach-delete-action"
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      closeCoachSessionMenu();
                                      onDeleteCoachSession?.(session.id);
                                    }}
                                  >
                                    {t('sidebar.deleteConversation')}
                                  </button>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="sidebar-coach-empty">{t('aiCoach.guestHistoryDisabled')}</div>
                )}
              </section>
            )}
          </>
        ) : (
          primaryItems.map((item) => (
            <button
              key={item.id}
              className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
              onClick={() => onPageChange(item.id)}
              type="button"
            >
              {t(item.labelKey)}
            </button>
          ))
        )}
      </nav>

      {currentPage !== 'settings' && (
        <div className="sidebar-bottom">
          {isSettingsMenuOpen && (
            <div className="sidebar-settings-menu" onClick={(event) => event.stopPropagation()}>
              <div className="sidebar-settings-account">
                <span>{accountDisplayName || t('common.guest')}</span>
              </div>
              <button
                className="sidebar-settings-menu-item"
                type="button"
                onClick={() => {
                  setIsSettingsMenuOpen(false);
                  onOpenAccountManagement?.();
                }}
              >
                {t('nav.account')}
              </button>
              <div className="sidebar-settings-separator" />
              <button
                className="sidebar-settings-menu-item"
                type="button"
                onClick={() => {
                  setIsSettingsMenuOpen(false);
                  onPageChange('settings');
                }}
              >
                {t('nav.settings')}
              </button>
              <div className="sidebar-settings-separator" />
              <button
                className="sidebar-settings-menu-item"
                type="button"
                onClick={() => {
                  setIsSettingsMenuOpen(false);
                  onAuthAction?.();
                }}
              >
                {authActionLabel || t('common.login')}
              </button>
            </div>
          )}
          <button
            className="sidebar-item"
            onClick={(event) => {
              event.stopPropagation();
              closeCoachSessionMenu();
              setRenamingSessionId(null);
              setIsSettingsMenuOpen((current) => !current);
            }}
            type="button"
          >
            {t('nav.settings')}
          </button>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
