import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  completePasswordReset,
  getPasswordResetQuestion,
  loginAccount,
  registerAccount,
  securityQuestions,
  validatePasswordFormat,
  validateUsernameFormat,
  verifyPasswordResetAnswer,
  type AuthUser,
} from '../auth/authClient';
import './AuthScreens.css';

export type AuthMode = 'welcome' | 'login' | 'register' | 'forgot';
type RegisterStep = 'username' | 'password' | 'security';
type LoginStep = 'accounts' | 'username' | 'password';
const LOGIN_SUCCESS_LOADING_MS = 2500;
const RECENT_LOGIN_ACCOUNTS_KEY = 'qtrack_recent_login_accounts';

export interface AuthSession {
  type: 'user' | 'guest';
  username?: string;
  token?: string;
  user?: AuthUser;
  expiresAt?: number;
}

interface AuthScreensProps {
  initialMode?: AuthMode;
  onAuthenticated: (session: AuthSession) => void;
  onBackToExplore?: () => void;
}

const getAuthErrorKey = (code: string): string => {
  const errorMap: Record<string, string> = {
    INVALID_USERNAME: 'auth.errorUsernameFormat',
    INVALID_PASSWORD: 'auth.errorPasswordFormat',
    USERNAME_TAKEN: 'auth.errorUsernameTaken',
    INVALID_LOGIN: 'auth.errorInvalidLogin',
    USER_NOT_FOUND: 'auth.errorUserNotFound',
    INVALID_SECURITY_ANSWER: 'auth.errorSecurityAnswer',
    API_NOT_FOUND: 'auth.errorAuthServiceUnavailable',
    CONNECTION_FAILED: 'auth.errorAuthServiceUnavailable',
  };
  return errorMap[code] || 'auth.errorRequestFailed';
};

const readRecentLoginAccounts = (): string[] => {
  try {
    const storedValue = window.localStorage.getItem(RECENT_LOGIN_ACCOUNTS_KEY);
    if (!storedValue) return [];
    const parsedValue = JSON.parse(storedValue);
    if (!Array.isArray(parsedValue)) return [];
    return parsedValue.filter((value): value is string => typeof value === 'string' && value.trim().length > 0);
  } catch {
    return [];
  }
};

const writeRecentLoginAccounts = (accounts: string[]) => {
  window.localStorage.setItem(RECENT_LOGIN_ACCOUNTS_KEY, JSON.stringify(accounts));
};

export const AuthScreens: React.FC<AuthScreensProps> = ({
  initialMode = 'welcome',
  onAuthenticated,
  onBackToExplore,
}) => {
  const { t } = useTranslation();
  const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [statusMessage, setStatusMessage] = useState('');

  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginStep, setLoginStep] = useState<LoginStep>('accounts');
  const [loginPasswordBackStep, setLoginPasswordBackStep] = useState<LoginStep>('accounts');
  const [recentLoginAccounts, setRecentLoginAccounts] = useState<string[]>(readRecentLoginAccounts);
  const [isRemovingLoginAccount, setIsRemovingLoginAccount] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [isLoginLoading, setIsLoginLoading] = useState(false);

  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [registerQuestion, setRegisterQuestion] = useState(securityQuestions[0]);
  const [registerAnswer, setRegisterAnswer] = useState('');
  const [registerError, setRegisterError] = useState('');
  const [registerStep, setRegisterStep] = useState<RegisterStep>('username');
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [isRegisterLoading, setIsRegisterLoading] = useState(false);

  const [forgotUsername, setForgotUsername] = useState('');
  const [forgotQuestion, setForgotQuestion] = useState('');
  const [forgotAnswer, setForgotAnswer] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [forgotError, setForgotError] = useState('');
  const [isAnswerVerified, setIsAnswerVerified] = useState(false);
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [isForgotLoading, setIsForgotLoading] = useState(false);

  const translateSecurityQuestion = (question: string) => {
    const index = securityQuestions.indexOf(question);
    return index >= 0 ? t(`auth.securityQuestions.${index}`, { defaultValue: question }) : question;
  };

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setStatusMessage('');
    setLoginError('');
    setLoginPassword('');
    setShowLoginPassword(false);
    if (nextMode === 'login') {
      setLoginStep('accounts');
      setLoginPasswordBackStep('accounts');
    }
    setIsRemovingLoginAccount(false);
    setRegisterError('');
    setRegisterStep('username');
    setShowRegisterPassword(false);
    setForgotError('');
    setForgotQuestion('');
    setForgotAnswer('');
    setIsAnswerVerified(false);
    setShowResetPassword(false);
    setIsLoginLoading(false);
    setIsRegisterLoading(false);
    setIsForgotLoading(false);
  };

  const getScreenBackAction = (): (() => void) | null => {
    if (mode === 'welcome') return onBackToExplore || null;
    if (mode === 'login' && loginStep === 'password') return () => setLoginStep(loginPasswordBackStep);
    if (mode === 'login' && loginStep === 'username') return () => setLoginStep('accounts');
    if (mode === 'register' && registerStep === 'security') return () => setRegisterStep('password');
    if (mode === 'register' && registerStep === 'password') return () => setRegisterStep('username');
    if (mode === 'forgot') return () => switchMode('login');
    return () => switchMode('welcome');
  };

  const completeAuthentication = (response: { token: string; user: AuthUser; expires_at: number }) => {
    onAuthenticated({
      type: 'user',
      username: response.user.username,
      token: response.token,
      user: response.user,
      expiresAt: response.expires_at,
    });
  };

  const waitForLoginSuccessLoading = () =>
    new Promise((resolve) => {
      window.setTimeout(resolve, LOGIN_SUCCESS_LOADING_MS);
    });

  const handleLoginSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = loginUsername.trim();

    if (!validateUsernameFormat(username)) {
      setLoginError(t('auth.errorUsernameFormat'));
      return;
    }
    if (!validatePasswordFormat(loginPassword)) {
      setLoginError(t('auth.errorPasswordFormat'));
      return;
    }

    setIsLoginLoading(true);
    setLoginError('');
    try {
      const response = await loginAccount(apiBaseUrl, username, loginPassword);
      await waitForLoginSuccessLoading();
      const nextRecentAccounts = [username, ...recentLoginAccounts.filter((account) => account !== username)].slice(0, 5);
      setRecentLoginAccounts(nextRecentAccounts);
      writeRecentLoginAccounts(nextRecentAccounts);
      completeAuthentication(response);
    } catch (error) {
      setLoginError(t(getAuthErrorKey(error instanceof Error ? error.message : '')));
      setIsLoginLoading(false);
    }
  };

  const handleSelectRecentLoginAccount = (username: string) => {
    if (isRemovingLoginAccount || isLoginLoading) return;
    setLoginUsername(username);
    setLoginPassword('');
    setShowLoginPassword(false);
    setLoginError('');
    setStatusMessage('');
    setLoginPasswordBackStep('accounts');
    setLoginStep('password');
  };

  const handleUseOtherLoginAccount = () => {
    setLoginUsername('');
    setLoginPassword('');
    setShowLoginPassword(false);
    setLoginError('');
    setStatusMessage('');
    setIsRemovingLoginAccount(false);
    setLoginStep('username');
  };

  const handleRemoveRecentLoginAccount = (username: string) => {
    const nextRecentAccounts = recentLoginAccounts.filter((account) => account !== username);
    setRecentLoginAccounts(nextRecentAccounts);
    writeRecentLoginAccounts(nextRecentAccounts);
    if (loginUsername === username) {
      setLoginUsername('');
    setLoginPassword('');
    setShowLoginPassword(false);
    setLoginStep('accounts');
    }
    if (nextRecentAccounts.length === 0) {
      setIsRemovingLoginAccount(false);
    }
  };

  const handleLoginUsernameNext = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = loginUsername.trim();
    if (!validateUsernameFormat(username)) {
      setLoginError(t('auth.errorUsernameFormat'));
      return;
    }

    setLoginUsername(username);
    setLoginPassword('');
    setShowLoginPassword(false);
    setLoginError('');
    setStatusMessage('');
    setLoginPasswordBackStep('username');
    setLoginStep('password');
  };

  const handleRegisterUsernameNext = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = registerUsername.trim();

    if (!validateUsernameFormat(username)) {
      setRegisterError(t('auth.errorUsernameFormat'));
      return;
    }

    setRegisterUsername(username);
    setRegisterError('');
    setRegisterStep('password');
  };

  const handleRegisterPasswordNext = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!validatePasswordFormat(registerPassword)) {
      setRegisterError(t('auth.errorPasswordFormat'));
      return;
    }
    if (registerPassword !== registerConfirmPassword) {
      setRegisterError(t('auth.errorPasswordMismatch'));
      return;
    }

    setRegisterError('');
    setRegisterStep('security');
  };

  const handleRegisterSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = registerUsername.trim();
    const answer = registerAnswer.trim();

    if (!validateUsernameFormat(username)) {
      setRegisterError(t('auth.errorUsernameFormat'));
      setRegisterStep('username');
      return;
    }
    if (!validatePasswordFormat(registerPassword)) {
      setRegisterError(t('auth.errorPasswordFormat'));
      setRegisterStep('password');
      return;
    }
    if (registerPassword !== registerConfirmPassword) {
      setRegisterError(t('auth.errorPasswordMismatch'));
      setRegisterStep('password');
      return;
    }
    if (!answer) {
      setRegisterError(t('auth.errorAnswerRequired'));
      return;
    }

    setIsRegisterLoading(true);
    setRegisterError('');
    try {
      await registerAccount(apiBaseUrl, {
        username,
        password: registerPassword,
        security_question: registerQuestion,
        security_answer: answer,
      });
      setRegisterUsername('');
      setRegisterPassword('');
      setRegisterConfirmPassword('');
      setRegisterQuestion(securityQuestions[0]);
      setRegisterAnswer('');
      setRegisterStep('username');
      setIsRegisterLoading(false);
      setLoginUsername(username);
      setLoginPassword('');
      setShowLoginPassword(false);
      setStatusMessage(t('auth.registered'));
      setLoginPasswordBackStep('username');
      setLoginStep('password');
      setMode('login');
    } catch (error) {
      setRegisterError(t(getAuthErrorKey(error instanceof Error ? error.message : '')));
      setIsRegisterLoading(false);
    }
  };

  const handleVerifyAnswer = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = forgotUsername.trim();

    if (!validateUsernameFormat(username)) {
      setForgotError(t('auth.errorUsernameFormat'));
      return;
    }

    setIsForgotLoading(true);
    setForgotError('');
    try {
      if (!forgotQuestion) {
        const response = await getPasswordResetQuestion(apiBaseUrl, username);
        setForgotUsername(response.username);
        setForgotQuestion(response.security_question);
        return;
      }

      await verifyPasswordResetAnswer(apiBaseUrl, username, forgotAnswer.trim());
      setIsAnswerVerified(true);
    } catch (error) {
      setForgotError(t(getAuthErrorKey(error instanceof Error ? error.message : '')));
      setIsAnswerVerified(false);
    } finally {
      setIsForgotLoading(false);
    }
  };

  const handleUpdatePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!isAnswerVerified) {
      setForgotError(t('auth.errorVerifyFirst'));
      return;
    }
    if (!validatePasswordFormat(newPassword)) {
      setForgotError(t('auth.errorPasswordFormat'));
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setForgotError(t('auth.errorNewPasswordMismatch'));
      return;
    }

    setIsForgotLoading(true);
    setForgotError('');
    try {
      await completePasswordReset(apiBaseUrl, forgotUsername.trim(), forgotAnswer.trim(), newPassword);
      setForgotUsername('');
      setForgotQuestion('');
      setForgotAnswer('');
      setNewPassword('');
      setConfirmNewPassword('');
      setIsAnswerVerified(false);
      setShowResetPassword(false);
      setStatusMessage(t('auth.passwordUpdated'));
      setMode('login');
    } catch (error) {
      setForgotError(t(getAuthErrorKey(error instanceof Error ? error.message : '')));
    } finally {
      setIsForgotLoading(false);
    }
  };

  const renderWelcome = () => (
    <section className="auth-panel auth-welcome" aria-labelledby="auth-title">
      <div>
        <p className="auth-kicker">CueVex</p>
        <h1 id="auth-title">{t('auth.welcomeTitle')}</h1>
        <p className="auth-subtitle">{t('auth.welcomeSubtitle')}</p>
      </div>

      <div className="auth-actions">
        <button className="btn btn-primary auth-action-button" type="button" onClick={() => switchMode('login')}>
          {t('auth.loginExisting')}
        </button>
        <button className="btn auth-action-button" type="button" onClick={() => switchMode('register')}>
          {t('auth.registerNew')}
        </button>
        <button className="btn auth-action-button" type="button" onClick={() => onAuthenticated({ type: 'guest' })}>
          {t('auth.continueAsGuest')}
        </button>
      </div>
    </section>
  );

  const renderLoginAccountPicker = () => (
    <>
      <div className="auth-account-list" aria-label={t('auth.savedAccounts')}>
        {recentLoginAccounts.length > 0 ? (
          recentLoginAccounts.map((account) => (
            <div className="auth-account-row" key={account}>
              <button
                className="auth-account-button"
                type="button"
                onClick={() => handleSelectRecentLoginAccount(account)}
                disabled={isLoginLoading || isRemovingLoginAccount}
              >
                <span>{account}</span>
              </button>
              {isRemovingLoginAccount && (
                <button
                  className="auth-account-remove-button"
                  type="button"
                  onClick={() => handleRemoveRecentLoginAccount(account)}
                >
                  {t('auth.removeSavedAccount')}
                </button>
              )}
            </div>
          ))
        ) : (
          <p className="auth-empty-accounts">{t('auth.noSavedAccounts')}</p>
        )}
      </div>

      <div className="auth-actions">
        <button className="btn btn-primary auth-action-button" type="button" onClick={handleUseOtherLoginAccount}>
          {t('auth.useOtherAccount')}
        </button>
        <button
          className="btn auth-action-button"
          type="button"
          onClick={() => setIsRemovingLoginAccount((current) => !current)}
          disabled={recentLoginAccounts.length === 0}
        >
          {isRemovingLoginAccount ? t('common.cancel') : t('auth.removeAccountFromList')}
        </button>
      </div>
    </>
  );

  const renderLoginUsernameStep = () => (
    <form className="auth-form" onSubmit={handleLoginUsernameNext}>
      <label>
        {t('auth.username')}
        <input
          autoComplete="username"
          value={loginUsername}
          onChange={(event) => {
            setLoginUsername(event.target.value);
            setLoginError('');
          }}
          placeholder={t('auth.usernamePlaceholder')}
          disabled={isLoginLoading}
          required
        />
      </label>

      <button className="btn btn-primary auth-submit" type="submit" disabled={isLoginLoading}>
        {t('common.next')}
      </button>
    </form>
  );

  const renderLoginPasswordStep = () => (
    <>
      <form className="auth-form" onSubmit={handleLoginSubmit}>
        <div className="auth-selected-account">
          <span>{t('auth.selectedAccount')}</span>
          <strong>{loginUsername}</strong>
        </div>

        <label>
          {t('auth.password')}
          <input
            autoComplete="current-password"
            type={showLoginPassword ? 'text' : 'password'}
            value={loginPassword}
            onChange={(event) => setLoginPassword(event.target.value)}
            placeholder={t('auth.passwordPlaceholder')}
            disabled={isLoginLoading}
            required
          />
        </label>
        <label className="auth-checkbox-label">
          <input
            type="checkbox"
            checked={showLoginPassword}
            onChange={(event) => setShowLoginPassword(event.target.checked)}
            disabled={isLoginLoading}
          />
          {t('auth.showPassword')}
        </label>

        <button className="btn btn-primary auth-submit" type="submit" disabled={isLoginLoading}>
          {isLoginLoading ? t('auth.loginLoading') : t('common.login')}
        </button>
      </form>

      <button className="auth-link-button" type="button" onClick={() => switchMode('forgot')} disabled={isLoginLoading}>
        {t('auth.forgotPassword')}
      </button>
    </>
  );

  const renderLogin = () => (
    <section
      className={`auth-panel auth-login-panel ${isLoginLoading ? 'is-login-loading' : ''}`}
      aria-labelledby="login-title"
    >
      <div className="auth-header-row">
        <h1 id="login-title">{t('auth.loginExisting')}</h1>
      </div>

      {statusMessage && <p className="auth-message success">{statusMessage}</p>}
      {loginError && <p className="auth-message error">{loginError}</p>}

      {loginStep === 'accounts' && renderLoginAccountPicker()}
      {loginStep === 'username' && renderLoginUsernameStep()}
      {loginStep === 'password' && renderLoginPasswordStep()}
    </section>
  );

  const renderRegisterStepIndicator = () => {
    const steps: RegisterStep[] = ['username', 'password', 'security'];
    const currentStepIndex = steps.indexOf(registerStep);

    return (
      <div className="auth-step-indicator" aria-label={t('auth.registerNew')}>
        {steps.map((step, index) => (
          <span
            key={step}
            className={`auth-step-dot ${index <= currentStepIndex ? 'is-active' : ''}`}
            aria-current={step === registerStep ? 'step' : undefined}
          />
        ))}
      </div>
    );
  };

  const renderRegisterUsernameStep = () => (
    <form className="auth-form" onSubmit={handleRegisterUsernameNext}>
      <label>
        {t('auth.username')}
        <input
          autoComplete="username"
          value={registerUsername}
          onChange={(event) => {
            setRegisterUsername(event.target.value);
            setRegisterError('');
          }}
          placeholder={t('auth.usernamePlaceholder')}
          disabled={isRegisterLoading}
          required
        />
      </label>

      <button className="btn btn-primary auth-submit" type="submit" disabled={isRegisterLoading}>
        {t('common.next')}
      </button>
    </form>
  );

  const renderRegisterPasswordStep = () => (
    <form className="auth-form" onSubmit={handleRegisterPasswordNext}>
      <label>
        {t('auth.password')}
        <input
          autoComplete="new-password"
          type={showRegisterPassword ? 'text' : 'password'}
          value={registerPassword}
          onChange={(event) => {
            setRegisterPassword(event.target.value);
            setRegisterError('');
          }}
          placeholder={t('auth.passwordPlaceholder')}
          disabled={isRegisterLoading}
          required
        />
      </label>

      <label>
        {t('auth.confirmPassword')}
        <input
          autoComplete="new-password"
          type={showRegisterPassword ? 'text' : 'password'}
          value={registerConfirmPassword}
          onChange={(event) => {
            setRegisterConfirmPassword(event.target.value);
            setRegisterError('');
          }}
          disabled={isRegisterLoading}
          required
        />
      </label>
      <label className="auth-checkbox-label">
        <input
          type="checkbox"
          checked={showRegisterPassword}
          onChange={(event) => setShowRegisterPassword(event.target.checked)}
          disabled={isRegisterLoading}
        />
        {t('auth.showPassword')}
      </label>

      <button className="btn btn-primary auth-submit" type="submit" disabled={isRegisterLoading}>
        {t('common.next')}
      </button>
    </form>
  );

  const renderRegisterSecurityStep = () => (
    <form className="auth-form" onSubmit={handleRegisterSubmit}>
      <label>
        {t('auth.securityQuestion')}
        <select
          value={registerQuestion}
          onChange={(event) => setRegisterQuestion(event.target.value)}
          disabled={isRegisterLoading}
        >
          {securityQuestions.map((question) => (
            <option key={question} value={question}>
              {translateSecurityQuestion(question)}
            </option>
          ))}
        </select>
      </label>

      <label>
        {t('auth.questionAnswer')}
        <input
          value={registerAnswer}
          onChange={(event) => {
            setRegisterAnswer(event.target.value);
            setRegisterError('');
          }}
          placeholder={t('auth.answerPlaceholder')}
          disabled={isRegisterLoading}
          required
        />
      </label>

      <button className="btn btn-primary auth-submit" type="submit" disabled={isRegisterLoading}>
        {isRegisterLoading ? t('common.processing') : t('auth.registerSubmit')}
      </button>
    </form>
  );

  const renderRegister = () => (
    <section className="auth-panel auth-register-panel" aria-labelledby="register-title">
      <div className="auth-header-row">
        <h1 id="register-title">{t('auth.registerNew')}</h1>
        {renderRegisterStepIndicator()}
      </div>

      {registerError && <p className="auth-message error">{registerError}</p>}

      {registerStep === 'username' && renderRegisterUsernameStep()}
      {registerStep === 'password' && renderRegisterPasswordStep()}
      {registerStep === 'security' && renderRegisterSecurityStep()}
    </section>
  );

  const renderForgot = () => (
    <section className="auth-panel" aria-labelledby="forgot-title">
      <div className="auth-header-row">
        <h1 id="forgot-title">{t('auth.forgotTitle')}</h1>
      </div>

      {forgotError && <p className="auth-message error">{forgotError}</p>}

      <form className="auth-form" onSubmit={handleVerifyAnswer}>
        <label>
          {t('auth.username')}
          <input
            autoComplete="username"
            value={forgotUsername}
            onChange={(event) => {
              setForgotUsername(event.target.value);
              setForgotQuestion('');
              setForgotAnswer('');
              setIsAnswerVerified(false);
              setForgotError('');
            }}
            required
          />
        </label>

        {forgotQuestion && (
          <>
            <div className="auth-security-question">
              <span>{t('auth.securityQuestion')}</span>
              <strong>{translateSecurityQuestion(forgotQuestion)}</strong>
            </div>

            <label>
              {t('auth.answer')}
              <input
                value={forgotAnswer}
                onChange={(event) => {
                  setForgotAnswer(event.target.value);
                  setIsAnswerVerified(false);
                }}
                required
              />
            </label>
          </>
        )}

        <button className="btn auth-submit" type="submit" disabled={isForgotLoading}>
          {forgotQuestion ? t('auth.verifyAnswer') : t('auth.lookupUser')}
        </button>
      </form>

      {isAnswerVerified && (
        <form className="auth-form auth-password-reset" onSubmit={handleUpdatePassword}>
          <label>
            {t('auth.newPassword')}
            <input
              autoComplete="new-password"
              type={showResetPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </label>

          <label>
            {t('auth.confirmNewPassword')}
            <input
              autoComplete="new-password"
              type={showResetPassword ? 'text' : 'password'}
              value={confirmNewPassword}
              onChange={(event) => setConfirmNewPassword(event.target.value)}
              required
            />
          </label>
          <label className="auth-checkbox-label">
            <input
              type="checkbox"
              checked={showResetPassword}
              onChange={(event) => setShowResetPassword(event.target.checked)}
              disabled={isForgotLoading}
            />
            {t('auth.showPassword')}
          </label>

          <button className="btn btn-primary auth-submit" type="submit" disabled={isForgotLoading}>
            {t('auth.updatePassword')}
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
          aria-label={t('common.back')}
          onClick={screenBackAction}
          disabled={(mode === 'login' && isLoginLoading) || (mode === 'register' && isRegisterLoading)}
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
