import React, { useMemo, useState } from 'react';
import './Sidebar.css';

export type PageType =
  | 'practice'
  | 'game'
  | 'stream'
  | 'settings'
  | 'replay'
  | 'calibration'
  | 'camera-params'
  | 'color-calibration';

export interface CoachMenuSession {
  id: string;
  title: string;
  createdAt: number;
  isPinned: boolean;
}

interface SidebarProps {
  currentPage: PageType;
  onPageChange: (page: PageType) => void;
  isCoachOpen?: boolean;
  onToggleCoach?: () => void;
  coachSessions?: CoachMenuSession[];
  activeCoachSessionId?: string;
  onCreateCoachSession?: () => void;
  onSelectCoachSession?: (sessionId: string) => void;
  onRenameCoachSession?: (sessionId: string, title: string) => void;
  onToggleCoachSessionPin?: (sessionId: string) => void;
  onDeleteCoachSession?: (sessionId: string) => void;
}

interface MenuItem {
  id: PageType;
  label: string;
}

const primaryItems: MenuItem[] = [
  { id: 'stream', label: '即時影像' },
  { id: 'replay', label: '回放功能' },
  { id: 'practice', label: '練習模式' },
  { id: 'game', label: '遊玩模式' },
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
  coachSessions = [],
  activeCoachSessionId,
  onCreateCoachSession,
  onSelectCoachSession,
  onRenameCoachSession,
  onToggleCoachSessionPin,
  onDeleteCoachSession,
}) => {
  const [openCoachMenuSessionId, setOpenCoachMenuSessionId] = useState<string | null>(null);
  const [openCoachMenuDirection, setOpenCoachMenuDirection] = useState<'down' | 'up'>('down');
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameInput, setRenameInput] = useState('');
  const sortedCoachSessions = useMemo(() => sortCoachSessions(coachSessions), [coachSessions]);

  const startRename = (event: React.MouseEvent<HTMLButtonElement>, session: CoachMenuSession) => {
    event.stopPropagation();
    setOpenCoachMenuSessionId(null);
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
    <aside className="sidebar" onClick={() => setOpenCoachMenuSessionId(null)}>
      <nav className="sidebar-nav" aria-label="主要功能">
        {primaryItems.map((item) => (
          <button
            key={item.id}
            className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => onPageChange(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}

        <button
          type="button"
          className={`sidebar-item sidebar-coach-button ${isCoachOpen ? 'active' : ''}`}
          onClick={(event) => {
            event.stopPropagation();
            setRenamingSessionId(null);
            setOpenCoachMenuSessionId(null);
            onToggleCoach?.();
          }}
        >
          AI Coach
        </button>
      </nav>

      {isCoachOpen && (
        <section className="sidebar-coach sidebar-coach-menu">
          <div className="sidebar-coach-menu-header">
            <span>聊天</span>
            <button
              className="sidebar-coach-new-button"
              type="button"
              aria-label="新對話"
              onClick={(event) => {
                event.stopPropagation();
                setRenamingSessionId(null);
                setOpenCoachMenuSessionId(null);
                onCreateCoachSession?.();
              }}
            >
              新對話
            </button>
          </div>

          <div className="sidebar-coach-session-list">
            {sortedCoachSessions.length === 0 && (
              <div className="sidebar-coach-empty">沒有對話</div>
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
                  setOpenCoachMenuSessionId(null);
                  onSelectCoachSession?.(session.id);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.stopPropagation();
                    setRenamingSessionId(null);
                    setOpenCoachMenuSessionId(null);
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
                      <button type="submit">儲存</button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          setRenamingSessionId(null);
                          setRenameInput('');
                        }}
                      >
                        取消
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="sidebar-coach-session-row">
                      <span className="sidebar-coach-session-main">
                        <span className="sidebar-coach-session-title">
                          {session.isPinned ? '[置頂] ' : ''}
                          {session.title}
                        </span>
                      </span>

                      <button
                        className="sidebar-coach-session-options"
                        type="button"
                        aria-label="對話選單"
                        onClick={(event) => {
                          event.stopPropagation();
                          setRenamingSessionId(null);
                          const listElement = event.currentTarget.closest('.sidebar-coach-session-list');
                          const listRect = listElement?.getBoundingClientRect();
                          const buttonRect = event.currentTarget.getBoundingClientRect();
                          const estimatedMenuHeight = 118;
                          const hasRoomBelow = listRect
                            ? buttonRect.bottom + estimatedMenuHeight <= listRect.bottom
                            : true;

                          setOpenCoachMenuDirection(hasRoomBelow ? 'down' : 'up');
                          setOpenCoachMenuSessionId((current) =>
                            current === session.id ? null : session.id,
                          );
                        }}
                      >
                        •••
                      </button>
                    </div>

                    {openCoachMenuSessionId === session.id && (
                      <div
                        className={`sidebar-coach-session-dropdown ${
                          openCoachMenuDirection === 'up' ? 'open-up' : ''
                        }`}
                        onClick={(event) => event.stopPropagation()}
                      >
                        <button type="button" onClick={(event) => startRename(event, session)}>
                          重新命名
                        </button>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setOpenCoachMenuSessionId(null);
                            onToggleCoachSessionPin?.(session.id);
                          }}
                        >
                          {session.isPinned ? '取消置頂' : '置頂'}
                        </button>
                        <button
                          className="sidebar-coach-delete-action"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setOpenCoachMenuSessionId(null);
                            onDeleteCoachSession?.(session.id);
                          }}
                        >
                          刪除對話
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="sidebar-bottom">
        <button
          className={`sidebar-item ${currentPage === 'settings' ? 'active' : ''}`}
          onClick={() => onPageChange('settings')}
          type="button"
        >
          設定
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
