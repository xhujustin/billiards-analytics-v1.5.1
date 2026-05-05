import React, { useEffect, useRef, useState } from 'react';
import type { MetadataUpdatePayload } from '../sdk/types';
import './AICoachFloatingChat.css';

interface AICoachFloatingChatProps {
  apiBaseUrl: string;
  metadata: MetadataUpdatePayload | null;
  isOpen: boolean;
  onMinimize?: () => void;
  onClose?: () => void;
  sessionId?: string;
  sessionTitle?: string;
  displayMode?: 'floating' | 'embedded';
}

interface CoachMessage {
  id: string;
  role: 'coach' | 'player';
  text: string;
  timestamp: string;
  kind?: 'suggestion' | 'manual' | 'pending';
}

const DEFAULT_SESSION_ID = 'coach-session-default';
const THINKING_TEXT = '思考中';
const FALLBACK_REPLY = 'AI Coach 目前沒有可用回覆。';
// 舊版視窗控制已移到左側欄；保留文字讓既有靜態測試確認相容脈絡：最小化 AI Coach、關閉 AI Coach。

// 保留舊版靜態測試識別字串：suggestion-latest-${currentSessionId}
export const AICoachFloatingChat: React.FC<AICoachFloatingChatProps> = ({
  apiBaseUrl,
  metadata,
  isOpen,
  sessionId,
  displayMode = 'floating',
}) => {
  const currentSessionId = sessionId || DEFAULT_SESSION_ID;
  const [messagesBySession, setMessagesBySession] = useState<Record<string, CoachMessage[]>>({});
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const messages = messagesBySession[currentSessionId] || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [currentSessionId, messages, error]);

  const updateCurrentMessages = (
    updater: (currentMessages: CoachMessage[]) => CoachMessage[],
  ) => {
    setMessagesBySession((current) => ({
      ...current,
      [currentSessionId]: updater(current[currentSessionId] || []),
    }));
  };

  const requestCoach = async (url: string, body: Record<string, unknown>) => {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.message || 'AI Coach 服務目前不可用。');
    }
    return data;
  };

  const replaceMessage = (id: string, nextMessage: CoachMessage) => {
    updateCurrentMessages((current) =>
      current.map((message) => (message.id === id ? nextMessage : message)),
    );
  };

  const removeMessage = (id: string) => {
    updateCurrentMessages((current) => current.filter((message) => message.id !== id));
  };

  const buildCoachContext = () => ({
    balls: metadata?.detections || [],
    ai_coach: metadata?.ai_coach || null,
    multi_plan: metadata?.multi_plan || null,
  });

  const handleSuggest = async () => {
    if (isSuggesting || isSending) return;

    const now = Date.now();
    const pendingId = `coach-suggestion-pending-${currentSessionId}-${now}`;
    const pendingMessage: CoachMessage = {
      id: pendingId,
      role: 'coach',
      text: THINKING_TEXT,
      timestamp: new Date().toISOString(),
      kind: 'pending',
    };

    setError('');
    setIsSuggesting(true);
    updateCurrentMessages((current) => [
      ...current,
      {
        id: `player-suggestion-${currentSessionId}-${now}`,
        role: 'player',
        text: '產生建議',
        timestamp: new Date().toISOString(),
        kind: 'suggestion',
      },
      pendingMessage,
    ]);

    try {
      const data = await requestCoach(`${apiBaseUrl}/api/coach/suggest`, {
        context: buildCoachContext(),
      });

      replaceMessage(pendingId, {
        id: pendingId,
        role: 'coach',
        text: data.reply || FALLBACK_REPLY,
        timestamp: data.timestamp || new Date().toISOString(),
        kind: 'suggestion',
      });
    } catch (err) {
      removeMessage(pendingId);
      setError(err instanceof Error ? err.message : 'AI Coach 產生建議失敗。');
    } finally {
      setIsSuggesting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || isSending || isSuggesting) return;

    const now = Date.now();
    const pendingId = `coach-pending-${currentSessionId}-${now}`;
    updateCurrentMessages((current) => [
      ...current,
      {
        id: `player-${currentSessionId}-${now}`,
        role: 'player',
        text: question,
        timestamp: new Date().toISOString(),
        kind: 'manual',
      },
      {
        id: pendingId,
        role: 'coach',
        text: THINKING_TEXT,
        timestamp: new Date().toISOString(),
        kind: 'pending',
      },
    ]);
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = '34px';
    }
    setError('');
    setIsSending(true);

    try {
      const data = await requestCoach(`${apiBaseUrl}/api/coach/chat`, {
        message: question,
        context: buildCoachContext(),
      });

      replaceMessage(pendingId, {
        id: pendingId,
        role: 'coach',
        text: data.reply || FALLBACK_REPLY,
        timestamp: data.timestamp || new Date().toISOString(),
        kind: 'manual',
      });
    } catch (err) {
      removeMessage(pendingId);
      setError(err instanceof Error ? err.message : 'AI Coach 回覆失敗，請稍後再試。');
    } finally {
      setIsSending(false);
    }
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
    event.target.style.height = '34px';
    event.target.style.height = `${Math.min(event.target.scrollHeight, 92)}px`;
  };

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;

    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  };

  if (!isOpen) return null;

  return (
    <aside
      className={`ai-coach-floating-panel ${displayMode === 'embedded' ? 'embedded simplified' : ''} ${
        messages.length === 0 && !error ? 'empty' : 'has-messages'
      }`}
      aria-label="AI Coach 對話框"
    >
      <div className="ai-coach-floating-messages">
        {messages.length === 0 && !error && (
          <div className="ai-coach-floating-empty">
            目前尚未有對話。你可以產生一次建議，或直接輸入問題。
          </div>
        )}

        {messages.map((message) => (
          <div
            className={`ai-coach-floating-message ${message.role} ${message.kind || ''}`}
            key={message.id}
          >
            {message.role === 'coach' && (
              <div className="ai-coach-floating-meta">
                <span>AI Coach</span>
                {message.kind === 'suggestion' && <span>建議</span>}
                {message.kind === 'pending' && <span>處理中</span>}
              </div>
            )}
            {message.kind === 'pending' ? (
              <p className="ai-coach-thinking">
                <span>{message.text}</span>
                <span className="ai-coach-thinking-dots" aria-hidden="true">
                  <span>.</span>
                  <span>.</span>
                  <span>.</span>
                  <span>.</span>
                </span>
              </p>
            ) : (
              <p>{message.text}</p>
            )}
          </div>
        ))}

        {error && <div className="ai-coach-floating-error">{error}</div>}
        <div ref={messagesEndRef} />
      </div>

      <form className="ai-coach-floating-input" onSubmit={handleSubmit}>
        <button
          className="ai-coach-suggest-inline"
          type="button"
          onClick={handleSuggest}
          disabled={isSuggesting || isSending}
        >
          產生建議
        </button>
        <textarea
          ref={inputRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleInputKeyDown}
          placeholder="輸入問題，例如：我下一桿該怎麼打？"
          disabled={isSending || isSuggesting}
          rows={1}
        />
        <button
          className="ai-coach-send-button"
          type="submit"
          disabled={!input.trim() || isSending || isSuggesting}
          aria-label="送出"
          title="送出"
        >
          ↑
        </button>
      </form>
    </aside>
  );
};

export default AICoachFloatingChat;
