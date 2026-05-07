import React, { useMemo, useState } from 'react';
import './AICoachChatWindow.css';

type ChatRole = 'coach' | 'player';

interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  createdAt: number;
}

interface ChatSession {
  id: string;
  title: string;
  mode: string;
  createdAt: number;
  isPinned: boolean;
  messages: ChatMessage[];
}

const DEFAULT_MODE = 'AI Coach - 即時影像模式';

const createSession = (index: number): ChatSession => {
  const now = Date.now();
  return {
    id: `session-${now}-${index}`,
    title: `新對話 ${index}`,
    mode: DEFAULT_MODE,
    createdAt: now,
    isPinned: false,
    messages: [],
  };
};

const sortSessions = (sessions: ChatSession[]): ChatSession[] => {
  return [...sessions].sort((a, b) => {
    if (a.isPinned !== b.isPinned) return a.isPinned ? -1 : 1;
    if (a.createdAt !== b.createdAt) return b.createdAt - a.createdAt;
    return b.id.localeCompare(a.id);
  });
};

export const AICoachChatWindow: React.FC = () => {
  const initialSession = useMemo(() => createSession(1), []);
  const [sessions, setSessions] = useState<ChatSession[]>([initialSession]);
  const [activeSessionId, setActiveSessionId] = useState(initialSession.id);
  const [openMenuSessionId, setOpenMenuSessionId] = useState<string | null>(null);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isClosed, setIsClosed] = useState(false);
  const [input, setInput] = useState('');
  const [sessionCounter, setSessionCounter] = useState(1);

  const sortedSessions = useMemo(() => sortSessions(sessions), [sessions]);
  const activeSession = sessions.find((session) => session.id === activeSessionId) || sessions[0];
  const currentMode = activeSession?.mode || DEFAULT_MODE;

  const handleCreateSession = (event?: React.MouseEvent<HTMLButtonElement>) => {
    event?.stopPropagation();
    const nextIndex = sessionCounter + 1;
    const nextSession = createSession(nextIndex);
    setSessionCounter(nextIndex);
    setSessions((current) => [nextSession, ...current]);
    setActiveSessionId(nextSession.id);
    setOpenMenuSessionId(null);
    setIsClosed(false);
    setIsMinimized(false);
  };

  const handleTogglePin = (event: React.MouseEvent<HTMLButtonElement>, sessionId: string) => {
    event.stopPropagation();
    setSessions((current) =>
      current.map((session) =>
        session.id === sessionId ? { ...session, isPinned: !session.isPinned } : session,
      ),
    );
    setOpenMenuSessionId(null);
  };

  const handleDeleteSession = (event: React.MouseEvent<HTMLButtonElement>, sessionId: string) => {
    event.stopPropagation();
    const nextSessions = sessions.filter((session) => session.id !== sessionId);

    if (nextSessions.length === 0) {
      const nextIndex = sessionCounter + 1;
      const nextSession = createSession(nextIndex);
      setSessionCounter(nextIndex);
      setSessions([nextSession]);
      setActiveSessionId(nextSession.id);
      setOpenMenuSessionId(null);
      return;
    }

    if (sessionId === activeSessionId) {
      const currentSorted = sortedSessions;
      const deletedIndex = currentSorted.findIndex((session) => session.id === sessionId);
      const previousSession = currentSorted[deletedIndex - 1];
      const nextSession = currentSorted[deletedIndex + 1];
      const fallbackSession = previousSession || nextSession || sortSessions(nextSessions)[0];
      setActiveSessionId(fallbackSession.id);
    }

    setSessions(nextSessions);
    setOpenMenuSessionId(null);
  };

  const handleSend = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setInput('');
  };

  if (isClosed) return null;

  return (
    <section className="ai-coach-chat-window" onClick={() => setOpenMenuSessionId(null)}>
      <header className="ai-coach-chat-window__header">
        <div>
          <h2>{currentMode}</h2>
          <p>多對話歷史紀錄</p>
        </div>
        <div className="ai-coach-chat-window__header-actions">
          <button type="button" onClick={handleCreateSession}>
            建立新對話
          </button>
          <button type="button" onClick={(event) => {
            event.stopPropagation();
            setIsMinimized((current) => !current);
          }}>
            {isMinimized ? '還原' : '最小化'}
          </button>
          <button type="button" onClick={(event) => {
            event.stopPropagation();
            setIsClosed(true);
          }}>
            關閉
          </button>
        </div>
      </header>

      {!isMinimized && (
        <div className="ai-coach-chat-window__body">
          <aside className="ai-coach-chat-window__history" aria-label="對話歷史紀錄">
            <div className="ai-coach-chat-window__history-title">歷史紀錄</div>
            <div className="ai-coach-chat-window__session-list">
              {sortedSessions.map((session) => (
                <button
                  type="button"
                  className={`ai-coach-chat-window__session ${session.id === activeSessionId ? 'active' : ''}`}
                  key={session.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    setActiveSessionId(session.id);
                    setOpenMenuSessionId(null);
                  }}
                >
                  <span className="ai-coach-chat-window__session-main">
                    <span className="ai-coach-chat-window__session-title">
                      {session.isPinned ? '[置頂] ' : ''}
                      {session.title}
                    </span>
                    <span className="ai-coach-chat-window__session-meta">
                      {new Date(session.createdAt).toLocaleString('zh-TW', {
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </span>
                  <span className="ai-coach-chat-window__session-options-wrap">
                    <span
                      className="ai-coach-chat-window__session-options"
                      role="button"
                      tabIndex={0}
                      onClick={(event) => {
                        event.stopPropagation();
                        setOpenMenuSessionId((current) => (current === session.id ? null : session.id));
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.stopPropagation();
                          setOpenMenuSessionId((current) => (current === session.id ? null : session.id));
                        }
                      }}
                    >
                      •••
                    </span>
                    {openMenuSessionId === session.id && (
                      <span className="ai-coach-chat-window__dropdown" onClick={(event) => event.stopPropagation()}>
                        <button type="button" onClick={(event) => handleTogglePin(event, session.id)}>
                          {session.isPinned ? '取消置頂' : '置頂'}
                        </button>
                        <button type="button" onClick={(event) => handleDeleteSession(event, session.id)}>
                          刪除對話
                        </button>
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          </aside>

          <main className="ai-coach-chat-window__chat">
            <div className="ai-coach-chat-window__messages">
              {activeSession?.messages.length ? (
                activeSession.messages.map((message) => (
                  <div className={`ai-coach-chat-window__message ${message.role}`} key={message.id}>
                    <span>{message.role === 'coach' ? 'AI Coach' : '你'}</span>
                    <p>{message.text}</p>
                  </div>
                ))
              ) : (
                <div className="ai-coach-chat-window__empty">此對話尚無訊息。</div>
              )}
            </div>

            <form className="ai-coach-chat-window__input" onSubmit={handleSend}>
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="輸入問題"
              />
              <button type="submit" disabled={!input.trim()}>
                送出
              </button>
            </form>
          </main>
        </div>
      )}
    </section>
  );
};

export default AICoachChatWindow;
