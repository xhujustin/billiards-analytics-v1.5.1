import React, { useEffect, useMemo, useState } from 'react';
import {
  appendLoginRecord,
  findUserByName,
  FORMAT_ERROR,
  isUsernameTaken,
  loadMockUsers,
  type MockUser,
  saveMockUsers,
  securityQuestions,
  validateCredentialFormat,
} from '../auth/mockAccountStore';
import './AuthScreens.css';

export type AuthMode = 'welcome' | 'login' | 'register' | 'forgot';

export interface AuthSession {
  type: 'user' | 'guest';
  username?: string;
}

interface AuthScreensProps {
  initialMode?: AuthMode;
  onAuthenticated: (session: AuthSession) => void;
  onBackToExplore?: () => void;
}

export const AuthScreens: React.FC<AuthScreensProps> = ({
  initialMode = 'welcome',
  onAuthenticated,
  onBackToExplore,
}) => {
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [users, setUsers] = useState<MockUser[]>(() => loadMockUsers());
  const [statusMessage, setStatusMessage] = useState('');

  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isLoginLoading, setIsLoginLoading] = useState(false);

  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [registerQuestion, setRegisterQuestion] = useState(securityQuestions[0]);
  const [registerAnswer, setRegisterAnswer] = useState('');
  const [registerError, setRegisterError] = useState('');

  const [forgotUsername, setForgotUsername] = useState('');
  const [forgotAnswer, setForgotAnswer] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [forgotError, setForgotError] = useState('');
  const [isAnswerVerified, setIsAnswerVerified] = useState(false);

  const selectedForgotUser = useMemo(
    () => findUserByName(users, forgotUsername.trim()),
    [forgotUsername, users],
  );

  useEffect(() => {
    saveMockUsers(users);
  }, [users]);

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setStatusMessage('');
    setLoginError('');
    setRegisterError('');
    setForgotError('');
    setIsAnswerVerified(false);
    setIsLoginLoading(false);
  };

  const getScreenBackAction = (): (() => void) | null => {
    if (mode === 'welcome') return onBackToExplore || null;
    if (mode === 'forgot') return () => switchMode('login');
    return () => switchMode('welcome');
  };

  const handleLoginSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = loginUsername;
    const password = loginPassword;

    if (!validateCredentialFormat(username) || !validateCredentialFormat(password)) {
      setLoginError(FORMAT_ERROR);
      return;
    }

    const matchedUser = findUserByName(users, username);
    if (!matchedUser || matchedUser.password !== password) {
      if (matchedUser) {
        const nextUsers = appendLoginRecord(users, username, '失敗');
        setUsers(nextUsers);
        saveMockUsers(nextUsers);
      }
      setLoginError('使用者名稱或密碼錯誤');
      return;
    }

    const nextUsers = appendLoginRecord(users, username, '成功');
    setUsers(nextUsers);
    saveMockUsers(nextUsers);
    setLoginError('');
    setIsLoginLoading(true);
    window.setTimeout(() => {
      onAuthenticated({ type: 'user', username });
    }, 2500);
  };

  const handleRegisterSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = registerUsername;
    const password = registerPassword;
    const confirmPassword = registerConfirmPassword;
    const answer = registerAnswer.trim();

    if (!validateCredentialFormat(username) || !validateCredentialFormat(password)) {
      setRegisterError(FORMAT_ERROR);
      return;
    }

    if (password !== confirmPassword) {
      setRegisterError('確認密碼需與密碼一致');
      return;
    }

    if (!answer) {
      setRegisterError('請輸入安全問題答案');
      return;
    }

    if (isUsernameTaken(users, username)) {
      setRegisterError('名稱已被使用');
      return;
    }

    const nextUsers = [
      ...users,
      {
        username: username.trim(),
        password,
        securityQuestion: registerQuestion,
        securityAnswer: answer,
        userId: `CUE-${Date.now().toString(16).toUpperCase().slice(-6)}`,
        loginHistory: [],
      },
    ];

    setUsers(nextUsers);
    setRegisterUsername('');
    setRegisterPassword('');
    setRegisterConfirmPassword('');
    setRegisterAnswer('');
    setStatusMessage('註冊完成，請登入新帳號');
    setMode('login');
  };

  const handleVerifyAnswer = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedForgotUser) {
      setForgotError('查無此使用者');
      setIsAnswerVerified(false);
      return;
    }

    if (forgotAnswer.trim() !== selectedForgotUser.securityAnswer) {
      setForgotError('安全問題答案錯誤');
      setIsAnswerVerified(false);
      return;
    }

    setForgotError('');
    setIsAnswerVerified(true);
  };

  const handleUpdatePassword = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedForgotUser || !isAnswerVerified) {
      setForgotError('請先完成安全問題驗證');
      return;
    }

    const nextPassword = newPassword;
    const nextConfirmPassword = confirmNewPassword;

    if (!validateCredentialFormat(nextPassword)) {
      setForgotError(FORMAT_ERROR);
      return;
    }

    if (nextPassword !== nextConfirmPassword) {
      setForgotError('確認新密碼需與新密碼一致');
      return;
    }

    setUsers((currentUsers) =>
      currentUsers.map((user) =>
        user.username === selectedForgotUser.username ? { ...user, password: nextPassword } : user,
      ),
    );
    setForgotUsername('');
    setForgotAnswer('');
    setNewPassword('');
    setConfirmNewPassword('');
    setIsAnswerVerified(false);
    setStatusMessage('密碼已更新，請使用新密碼登入');
    setMode('login');
  };

  const renderWelcome = () => (
    <section className="auth-panel auth-welcome" aria-labelledby="auth-title">
      <div>
        <p className="auth-kicker">Q Track</p>
        <h1 id="auth-title">歡迎使用Q Track</h1>
        <p className="auth-subtitle">請選擇登入、註冊或以訪客身分進入主程式。</p>
      </div>

      <div className="auth-actions">
        <button className="btn btn-primary auth-action-button" type="button" onClick={() => switchMode('login')}>
          登入現有帳號
        </button>
        <button className="btn auth-action-button" type="button" onClick={() => switchMode('register')}>
          註冊新帳號
        </button>
        <button
          className="btn auth-action-button"
          type="button"
          onClick={() => onAuthenticated({ type: 'guest' })}
        >
          以訪客身分進入
        </button>
      </div>
    </section>
  );

  const renderLogin = () => (
    <section
      className={`auth-panel auth-login-panel ${isLoginLoading ? 'is-login-loading' : ''}`}
      aria-labelledby="login-title"
    >
      <div className="auth-header-row">
        <h1 id="login-title">登入現有帳號</h1>
      </div>

      {statusMessage && <p className="auth-message success">{statusMessage}</p>}
      {loginError && <p className="auth-message error">{loginError}</p>}

      <form className="auth-form" onSubmit={handleLoginSubmit}>
        <label>
          使用者名稱
          <input
            autoComplete="username"
            value={loginUsername}
            onChange={(event) => setLoginUsername(event.target.value)}
            placeholder="QTrack_User"
            disabled={isLoginLoading}
            required
          />
        </label>

        <label>
          密碼
          <input
            autoComplete="current-password"
            type="password"
            value={loginPassword}
            onChange={(event) => setLoginPassword(event.target.value)}
            placeholder="QTrack_123"
            disabled={isLoginLoading}
            required
          />
        </label>

        <button className="btn btn-primary auth-submit" type="submit" disabled={isLoginLoading}>
          {isLoginLoading ? '登入中' : '登入'}
        </button>
      </form>

      <button
        className="auth-link-button"
        type="button"
        onClick={() => switchMode('forgot')}
        disabled={isLoginLoading}
      >
        忘記密碼
      </button>
    </section>
  );

  const renderRegister = () => (
    <section className="auth-panel" aria-labelledby="register-title">
      <div className="auth-header-row">
        <h1 id="register-title">註冊新帳號</h1>
      </div>

      {registerError && <p className="auth-message error">{registerError}</p>}

      <form className="auth-form" onSubmit={handleRegisterSubmit}>
        <label>
          使用者名稱
          <input
            autoComplete="username"
            value={registerUsername}
            onChange={(event) => setRegisterUsername(event.target.value)}
            placeholder="僅允許英文字母、數字、_"
            required
          />
        </label>

        <label>
          密碼
          <input
            autoComplete="new-password"
            type="password"
            value={registerPassword}
            onChange={(event) => setRegisterPassword(event.target.value)}
            placeholder="僅允許英文字母、數字、_"
            required
          />
        </label>

        <label>
          確認密碼
          <input
            autoComplete="new-password"
            type="password"
            value={registerConfirmPassword}
            onChange={(event) => setRegisterConfirmPassword(event.target.value)}
            required
          />
        </label>

        <label>
          安全問題
          <select value={registerQuestion} onChange={(event) => setRegisterQuestion(event.target.value)}>
            {securityQuestions.map((question) => (
              <option key={question} value={question}>
                {question}
              </option>
            ))}
          </select>
        </label>

        <label>
          問題答案
          <input
            value={registerAnswer}
            onChange={(event) => setRegisterAnswer(event.target.value)}
            placeholder="用於找回密碼"
            required
          />
        </label>

        <button className="btn btn-primary auth-submit" type="submit">
          完成註冊
        </button>
      </form>
    </section>
  );

  const renderForgot = () => (
    <section className="auth-panel" aria-labelledby="forgot-title">
      <div className="auth-header-row">
        <h1 id="forgot-title">找回密碼</h1>
      </div>

      {forgotError && <p className="auth-message error">{forgotError}</p>}

      <form className="auth-form" onSubmit={handleVerifyAnswer}>
        <label>
          使用者名稱
          <input
            autoComplete="username"
            value={forgotUsername}
            onChange={(event) => {
              setForgotUsername(event.target.value);
              setForgotAnswer('');
              setIsAnswerVerified(false);
              setForgotError('');
            }}
            required
          />
        </label>

        {selectedForgotUser && (
          <>
            <div className="auth-security-question">
              <span>安全問題</span>
              <strong>{selectedForgotUser.securityQuestion}</strong>
            </div>

            <label>
              答案
              <input
                value={forgotAnswer}
                onChange={(event) => {
                  setForgotAnswer(event.target.value);
                  setIsAnswerVerified(false);
                }}
                required
              />
            </label>

            <button className="btn auth-submit" type="submit">
              驗證答案
            </button>
          </>
        )}

        {!selectedForgotUser && (
          <button className="btn auth-submit" type="submit">
            查詢使用者
          </button>
        )}
      </form>

      {isAnswerVerified && (
        <form className="auth-form auth-password-reset" onSubmit={handleUpdatePassword}>
          <label>
            新密碼
            <input
              autoComplete="new-password"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </label>

          <label>
            確認新密碼
            <input
              autoComplete="new-password"
              type="password"
              value={confirmNewPassword}
              onChange={(event) => setConfirmNewPassword(event.target.value)}
              required
            />
          </label>

          <button className="btn btn-primary auth-submit" type="submit">
            更新密碼
          </button>
        </form>
      )}
    </section>
  );

  const screenBackAction = getScreenBackAction();

  return (
    <main className="auth-screen">
      {screenBackAction && (
        <button
          className="auth-screen-back-button"
          type="button"
          aria-label="返回"
          onClick={screenBackAction}
          disabled={mode === 'login' && isLoginLoading}
        >
          &lt;
        </button>
      )}
      {mode === 'welcome' && renderWelcome()}
      {mode === 'login' && renderLogin()}
      {mode === 'register' && renderRegister()}
      {mode === 'forgot' && renderForgot()}
    </main>
  );
};

export default AuthScreens;
