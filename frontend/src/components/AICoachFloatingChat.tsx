import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { MetadataUpdatePayload } from '../sdk/types';
import type { SupportedLanguage } from '../i18n/types';
import type { AuthSession } from './AuthScreens';
import type { AccentColorMode } from '../theme';
import './AICoachFloatingChat.css';

interface AICoachFloatingChatProps {
  apiBaseUrl: string;
  metadata: MetadataUpdatePayload | null;
  isOpen: boolean;
  onMinimize?: () => void;
  onClose?: () => void;
  sessionId?: string;
  sessionTitle?: string;
  language: SupportedLanguage;
  displayMode?: 'floating' | 'embedded';
  authSession: AuthSession;
  accentColorMode: AccentColorMode;
}

interface CoachMessage {
  id: string;
  role: 'coach' | 'player';
  text: string;
  timestamp: string;
  kind?: 'suggestion' | 'manual' | 'pending' | 'stopped';
}

type CoachResponseMode = 'action_suggestion';

const DEFAULT_SESSION_ID = 'coach-session-default';
const COACH_MESSAGES_STORAGE_KEY = 'ai-coach-chat-messages-v1';
const MAX_STORED_MESSAGES_PER_SESSION = 200;
const MAX_COACH_HISTORY_MESSAGES = 20;

const loadStoredMessages = (): Record<string, CoachMessage[]> => {
  try {
    const storedValue = window.localStorage.getItem(COACH_MESSAGES_STORAGE_KEY);
    if (!storedValue) return {};

    const parsedValue = JSON.parse(storedValue) as Record<string, CoachMessage[]>;
    if (!parsedValue || typeof parsedValue !== 'object' || Array.isArray(parsedValue)) return {};

    return Object.fromEntries(
      Object.entries(parsedValue)
        .filter(([sessionId, messages]) => typeof sessionId === 'string' && Array.isArray(messages))
        .map(([sessionId, messages]) => [
          sessionId,
          messages.filter(
            (message) =>
              message &&
              typeof message.id === 'string' &&
              (message.role === 'coach' || message.role === 'player') &&
              typeof message.text === 'string' &&
              typeof message.timestamp === 'string',
          ),
        ]),
    );
  } catch {
    window.localStorage.removeItem(COACH_MESSAGES_STORAGE_KEY);
    return {};
  }
};

const persistMessages = (messagesBySession: Record<string, CoachMessage[]>) => {
  try {
    const cappedMessages = Object.fromEntries(
      Object.entries(messagesBySession).map(([sessionId, messages]) => [
        sessionId,
        messages.slice(-MAX_STORED_MESSAGES_PER_SESSION),
      ]),
    );
    window.localStorage.setItem(COACH_MESSAGES_STORAGE_KEY, JSON.stringify(cappedMessages));
  } catch {
    // localStorage 可能在隱私模式或容量不足時不可用；對話仍保留在目前頁面狀態。
  }
};
// 舊版視窗控制已移到左側欄；保留文字讓既有靜態測試確認相容脈絡：最小化 AI Coach、關閉 AI Coach。

// 保留舊版靜態測試識別字串：suggestion-latest-${currentSessionId}
export const AICoachFloatingChat: React.FC<AICoachFloatingChatProps> = ({
  apiBaseUrl,
  metadata,
  isOpen,
  sessionId,
  language,
  displayMode = 'floating',
  authSession,
  accentColorMode,
}) => {
  const { t } = useTranslation();
  const isGuestSession = authSession.type === 'guest';
  const currentSessionId = sessionId || DEFAULT_SESSION_ID;
  const [messagesBySession, setMessagesBySession] = useState<Record<string, CoachMessage[]>>(() =>
    isGuestSession ? {} : loadStoredMessages(),
  );
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [activeResponseModeBySession, setActiveResponseModeBySession] = useState<Record<string, CoachResponseMode | null>>({});
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const activeRequestRef = useRef<{
    controller: AbortController;
    pendingId: string;
    sessionId: string;
  } | null>(null);
  const messages = messagesBySession[currentSessionId] || [];
  const isThinking = isSending || isSuggesting;
  const activeResponseMode = activeResponseModeBySession[currentSessionId] || null;

  useEffect(() => {
    if (isGuestSession) return;
    persistMessages(messagesBySession);
  }, [isGuestSession, messagesBySession]);

  useEffect(() => {
    if (!isGuestSession) return;
    setMessagesBySession({});
    setActiveResponseModeBySession({});
    setError('');
  }, [isGuestSession]);

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

  const updateSessionMessages = (
    sessionIdToUpdate: string,
    updater: (currentMessages: CoachMessage[]) => CoachMessage[],
  ) => {
    setMessagesBySession((current) => ({
      ...current,
      [sessionIdToUpdate]: updater(current[sessionIdToUpdate] || []),
    }));
  };

  const requestCoachStream = async (
    url: string,
    body: Record<string, unknown>,
    onDelta: (delta: string) => void,
    signal?: AbortSignal,
  ) => {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      let message = t('aiCoach.serviceUnavailable');
      try {
        const data = await response.json();
        message = data.detail || data.message || message;
      } catch {
        // Keep the localized fallback when the response is not JSON.
      }
      throw new Error(message);
    }
    if (!response.body) {
      return await response.json();
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let donePayload: any = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const eventText of events) {
        const dataLine = eventText
          .split('\n')
          .find((line) => line.startsWith('data:'));
        if (!dataLine) continue;
        const raw = dataLine.slice(5).trim();
        if (!raw) continue;
        const event = JSON.parse(raw);
        if (event.type === 'delta' && event.delta) {
          onDelta(String(event.delta));
        } else if (event.type === 'done') {
          donePayload = event;
        } else if (event.type === 'error') {
          throw new Error(event.message || t('aiCoach.replyFailed'));
        }
      }
    }

    if (buffer.trim()) {
      const dataLine = buffer
        .split('\n')
        .find((line) => line.startsWith('data:'));
      if (dataLine) {
        const event = JSON.parse(dataLine.slice(5).trim());
        if (event.type === 'done') donePayload = event;
        if (event.type === 'error') throw new Error(event.message || t('aiCoach.replyFailed'));
      }
    }

    if (!donePayload) {
      throw new Error(t('aiCoach.replyFailed'));
    }
    return donePayload;
  };

  const replaceSessionMessage = (
    sessionIdToUpdate: string,
    id: string,
    nextMessage: CoachMessage,
  ) => {
    updateSessionMessages(sessionIdToUpdate, (current) =>
      current.map((message) => (message.id === id ? nextMessage : message)),
    );
  };

  const removeMessage = (id: string) => {
    updateCurrentMessages((current) => current.filter((message) => message.id !== id));
  };

  const buildConversationHistory = (extraMessage?: CoachMessage) => {
    const sourceMessages = extraMessage ? [...messages, extraMessage] : messages;
    return sourceMessages
      .filter((message) => message.kind !== 'pending' && message.kind !== 'stopped' && message.text.trim())
      .slice(-MAX_COACH_HISTORY_MESSAGES)
      .map((message) => ({
        role: message.role,
        text: message.text,
        timestamp: message.timestamp,
        kind: message.kind || 'manual',
      }));
  };

  const buildCoachContext = (responseMode: CoachResponseMode | null = activeResponseMode) => ({
    balls: metadata?.detections || [],
    ai_coach: metadata?.ai_coach || null,
    multi_plan: metadata?.multi_plan || null,
    active_response_mode: responseMode,
    ui_context: {
      auth_type: authSession.type,
      user_id: authSession.type === 'user' ? authSession.user?.id : null,
      username: authSession.type === 'user' ? authSession.username : null,
      accent_color: accentColorMode,
    },
  });

  const markThinkingStopped = (pendingId: string, sessionIdToUpdate = currentSessionId) => {
    replaceSessionMessage(sessionIdToUpdate, pendingId, {
      id: pendingId,
      role: 'coach',
      text: t('aiCoach.stopped'),
      timestamp: new Date().toISOString(),
      kind: 'stopped',
    });
  };

  const handleStopThinking = () => {
    const activeRequest = activeRequestRef.current;
    if (!activeRequest) return;

    activeRequest.controller.abort();
    markThinkingStopped(activeRequest.pendingId, activeRequest.sessionId);
    activeRequestRef.current = null;
    setIsSending(false);
    setIsSuggesting(false);
    setError('');
  };

  const handleSuggest = async () => {
    if (isSuggesting || isSending) return;

    const now = Date.now();
    const pendingId = `coach-suggestion-pending-${currentSessionId}-${now}`;
    const pendingMessage: CoachMessage = {
      id: pendingId,
      role: 'coach',
      text: t('aiCoach.thinking'),
      timestamp: new Date().toISOString(),
      kind: 'pending',
    };

    setError('');
    setIsSuggesting(true);
    const controller = new AbortController();
    activeRequestRef.current = { controller, pendingId, sessionId: currentSessionId };
    const requestSessionId = currentSessionId;
    updateCurrentMessages((current) => [
      ...current,
      {
        id: `player-suggestion-${currentSessionId}-${now}`,
        role: 'player',
        text: t('aiCoach.generateSuggestion'),
        timestamp: new Date().toISOString(),
        kind: 'suggestion',
      },
      pendingMessage,
    ]);

    try {
      const responseMode: CoachResponseMode = 'action_suggestion';
      let streamedText = '';
      const data = await requestCoachStream(
        `${apiBaseUrl}/api/coach/suggest/stream`,
        {
          context: buildCoachContext(responseMode),
          response_mode: responseMode,
          locale: language,
        },
        (delta) => {
          streamedText += delta;
          replaceSessionMessage(requestSessionId, pendingId, {
            id: pendingId,
            role: 'coach',
            text: streamedText || t('aiCoach.thinking'),
            timestamp: new Date().toISOString(),
            kind: 'pending',
          });
        },
        controller.signal,
      );

      setActiveResponseModeBySession((current) => ({
        ...current,
        [requestSessionId]: responseMode,
      }));
      replaceSessionMessage(requestSessionId, pendingId, {
        id: pendingId,
        role: 'coach',
        text: data.reply || t('aiCoach.fallbackReply'),
        timestamp: data.timestamp || new Date().toISOString(),
        kind: 'suggestion',
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        markThinkingStopped(pendingId);
        return;
      }
      removeMessage(pendingId);
      setError(err instanceof Error ? err.message : t('aiCoach.suggestFailed'));
    } finally {
      if (activeRequestRef.current?.pendingId === pendingId) {
        activeRequestRef.current = null;
      }
      setIsSuggesting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || isSending || isSuggesting) return;

    const now = Date.now();
    const pendingId = `coach-pending-${currentSessionId}-${now}`;
    const playerMessage: CoachMessage = {
      id: `player-${currentSessionId}-${now}`,
      role: 'player',
      text: question,
      timestamp: new Date().toISOString(),
      kind: 'manual',
    };
    updateCurrentMessages((current) => [
      ...current,
      playerMessage,
      {
        id: pendingId,
        role: 'coach',
        text: t('aiCoach.thinking'),
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
    const controller = new AbortController();
    activeRequestRef.current = { controller, pendingId, sessionId: currentSessionId };
    const requestSessionId = currentSessionId;

    try {
      let streamedText = '';
      const data = await requestCoachStream(
        `${apiBaseUrl}/api/coach/chat/stream`,
        {
          message: question,
          context: buildCoachContext(activeResponseMode),
          coach_session_id: requestSessionId,
          conversation_history: buildConversationHistory(playerMessage),
          active_response_mode: activeResponseMode,
          locale: language,
        },
        (delta) => {
          streamedText += delta;
          replaceSessionMessage(requestSessionId, pendingId, {
            id: pendingId,
            role: 'coach',
            text: streamedText || t('aiCoach.thinking'),
            timestamp: new Date().toISOString(),
            kind: 'pending',
          });
        },
        controller.signal,
      );

      replaceSessionMessage(requestSessionId, pendingId, {
        id: pendingId,
        role: 'coach',
        text: data.reply || t('aiCoach.fallbackReply'),
        timestamp: data.timestamp || new Date().toISOString(),
        kind: 'manual',
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        markThinkingStopped(pendingId);
        return;
      }
      removeMessage(pendingId);
      setError(err instanceof Error ? err.message : t('aiCoach.replyFailed'));
    } finally {
      if (activeRequestRef.current?.pendingId === pendingId) {
        activeRequestRef.current = null;
      }
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
      aria-label={t('aiCoach.dialog')}
    >
      <div className="ai-coach-floating-messages">
        {messages.length === 0 && !error && (
          <div className="ai-coach-floating-empty">
            {isGuestSession ? t('aiCoach.guestEmpty') : t('aiCoach.empty')}
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
                {message.kind === 'suggestion' && <span>{t('aiCoach.suggestion')}</span>}
                {message.kind === 'pending' && <span>{t('aiCoach.pending')}</span>}
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
          disabled={isThinking}
        >
          {t('aiCoach.generateSuggestion')}
        </button>
        <textarea
          ref={inputRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleInputKeyDown}
          placeholder={t('aiCoach.placeholder')}
          disabled={isThinking}
          rows={1}
        />
        <button
          className={`ai-coach-send-button ${isThinking ? 'stop' : ''}`}
          type={isThinking ? 'button' : 'submit'}
          onClick={isThinking ? handleStopThinking : undefined}
          disabled={!isThinking && !input.trim()}
          aria-label={isThinking ? t('aiCoach.stopThinking') : t('common.send')}
          title={isThinking ? t('aiCoach.stopThinking') : t('common.send')}
        >
          {isThinking ? '■' : '↑'}
        </button>
      </form>
    </aside>
  );
};

export default AICoachFloatingChat;
