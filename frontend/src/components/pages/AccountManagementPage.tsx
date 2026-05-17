import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AuthSession } from '../AuthScreens';
import {
  deleteAccount,
  getCurrentAccount,
  securityQuestions,
  updatePassword,
  updateSecurityQuestion,
  updateUsername,
  validatePasswordFormat,
  validateUsernameFormat,
  type LoginHistoryRecord,
} from '../../auth/authClient';
import './SettingsPage.css';
import './AccountManagementPage.css';

interface AccountManagementPageProps {
  authSession: AuthSession;
  onSessionChange: (session: AuthSession) => void;
  onLoginRequest: () => void;
  onAccountDeleted: () => void;
}

const getAuthErrorKey = (code: string): string => {
  const errorMap: Record<string, string> = {
    INVALID_USERNAME: 'auth.errorUsernameFormat',
    INVALID_PASSWORD: 'auth.errorPasswordFormat',
    USERNAME_TAKEN: 'account.usernameTaken',
    INVALID_CURRENT_PASSWORD: 'account.oldPasswordWrong',
    INVALID_SECURITY_ANSWER: 'account.currentAnswerFailed',
    API_NOT_FOUND: 'auth.errorAuthServiceUnavailable',
    CONNECTION_FAILED: 'auth.errorAuthServiceUnavailable',
  };
  return errorMap[code] || 'auth.errorRequestFailed';
};

export const AccountManagementPage: React.FC<AccountManagementPageProps> = ({
  authSession,
  onSessionChange,
  onLoginRequest,
  onAccountDeleted,
}) => {
  const { t } = useTranslation();
  const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';
  const [loginHistory, setLoginHistory] = useState<LoginHistoryRecord[]>([]);
  const [isLoadingAccount, setIsLoadingAccount] = useState(false);

  const currentUser = authSession.user;
  const [newUsername, setNewUsername] = useState(authSession.username || '');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [currentSecurityAnswer, setCurrentSecurityAnswer] = useState('');
  const [nextSecurityQuestion, setNextSecurityQuestion] = useState(securityQuestions[0]);
  const [nextSecurityAnswer, setNextSecurityAnswer] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

  const recentLoginHistory = useMemo(() => loginHistory.slice(0, 3), [loginHistory]);

  const translateSecurityQuestion = (question: string) => {
    const index = securityQuestions.indexOf(question);
    return index >= 0 ? t(`auth.securityQuestions.${index}`, { defaultValue: question }) : question;
  };
  const translateLoginStatus = (status: LoginHistoryRecord['status']) =>
    status === 'success' ? t('account.success') : t('account.failed');

  useEffect(() => {
    if (!currentUser) return;
    setNewUsername(currentUser.username);
    setNextSecurityQuestion(currentUser.security_question);
  }, [currentUser]);

  useEffect(() => {
    if (authSession.type !== 'user' || !authSession.token) return;
    setIsLoadingAccount(true);
    getCurrentAccount(apiBaseUrl, authSession.token)
      .then((response) => {
        setLoginHistory(response.login_history);
        onSessionChange({
          ...authSession,
          username: response.user.username,
          user: response.user,
        });
      })
      .catch(() => {
        setError(t('account.accountNotFoundDesc'));
      })
      .finally(() => setIsLoadingAccount(false));
  }, [apiBaseUrl, authSession.token]);

  const showMessage = (nextMessage: string) => {
    setError('');
    setMessage(nextMessage);
  };

  const showError = (nextError: string) => {
    setMessage('');
    setError(nextError);
  };

  const handleRename = async () => {
    if (!authSession.token) return;
    const username = newUsername.trim();

    if (!validateUsernameFormat(username)) {
      showError(t('auth.errorUsernameFormat'));
      return;
    }

    try {
      const response = await updateUsername(apiBaseUrl, authSession.token, username);
      onSessionChange({ ...authSession, username: response.user.username, user: response.user });
      showMessage(t('account.usernameUpdated'));
    } catch (requestError) {
      showError(t(getAuthErrorKey(requestError instanceof Error ? requestError.message : '')));
    }
  };

  const handleUpdatePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!authSession.token) return;

    if (!validatePasswordFormat(newPassword)) {
      showError(t('auth.errorPasswordFormat'));
      return;
    }

    if (newPassword !== confirmNewPassword) {
      showError(t('auth.errorNewPasswordMismatch'));
      return;
    }

    try {
      await updatePassword(apiBaseUrl, authSession.token, oldPassword, newPassword);
      setOldPassword('');
      setNewPassword('');
      setConfirmNewPassword('');
      showMessage(t('account.passwordUpdated'));
    } catch (requestError) {
      showError(t(getAuthErrorKey(requestError instanceof Error ? requestError.message : '')));
    }
  };

  const handleUpdateSecurityQuestion = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!authSession.token) return;

    if (!nextSecurityAnswer.trim()) {
      showError(t('account.newAnswerRequired'));
      return;
    }

    try {
      const response = await updateSecurityQuestion(
        apiBaseUrl,
        authSession.token,
        currentSecurityAnswer,
        nextSecurityQuestion,
        nextSecurityAnswer.trim(),
      );
      onSessionChange({ ...authSession, user: response.user, username: response.user.username });
      setCurrentSecurityAnswer('');
      setNextSecurityAnswer('');
      showMessage(t('account.securityQuestionUpdated'));
    } catch (requestError) {
      showError(t(getAuthErrorKey(requestError instanceof Error ? requestError.message : '')));
    }
  };

  const closeDeleteModal = () => {
    if (isDeletingAccount) return;
    setIsDeleteModalOpen(false);
    setDeletePassword('');
  };

  const handleDeleteAccount = async () => {
    if (!authSession.token || !deletePassword || isDeletingAccount) return;

    setIsDeletingAccount(true);
    try {
      await deleteAccount(apiBaseUrl, authSession.token, deletePassword);
      window.localStorage.removeItem('billiards_session_id');
      window.localStorage.removeItem('billiards_session');
      onAccountDeleted();
    } catch (requestError) {
      setIsDeletingAccount(false);
      showError(t(getAuthErrorKey(requestError instanceof Error ? requestError.message : '')));
    }
  };

  const renderPanelRow = (title: string, description: string, control: React.ReactNode) => (
    <div className="settings-row">
      <div className="settings-row-copy">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <div className="settings-control">{control}</div>
    </div>
  );

  if (authSession.type === 'guest') {
    return (
      <div className="settings-page account-page">
        <h2 className="page-title">{t('account.title')}</h2>
        <section className="settings-section">
          <h3 className="settings-section-title">{t('account.loginRequired')}</h3>
          <p className="settings-section-desc">{t('account.loginRequiredDesc')}</p>
          <div className="settings-panel">
            {renderPanelRow(
              t('account.currentIdentity'),
              t('account.guestIdentityDesc'),
              <strong>{t('common.guest')}</strong>,
            )}
            {renderPanelRow(
              t('account.goLogin'),
              t('account.goLoginDesc'),
              <button className="settings-button primary" type="button" onClick={onLoginRequest}>
                {t('account.goLogin')}
              </button>,
            )}
          </div>
        </section>
      </div>
    );
  }

  if (!currentUser || !authSession.token) {
    return (
      <div className="settings-page account-page">
        <h2 className="page-title">{t('account.title')}</h2>
        <section className="settings-section">
          <h3 className="settings-section-title">{t('account.accountNotFound')}</h3>
          <p className="settings-section-desc">{t('account.accountNotFoundDesc')}</p>
          <div className="settings-panel">
            {renderPanelRow(
              t('account.relogin'),
              t('account.reloginDesc'),
              <button className="settings-button primary" type="button" onClick={onLoginRequest}>
                {t('account.goLogin')}
              </button>,
            )}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="settings-page account-page">
      <h2 className="page-title">{t('account.title')}</h2>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('account.profile')}</h3>
        <p className="settings-section-desc">{t('account.profileDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(
            t('auth.username'),
            t('account.usernameDesc'),
            <div className="account-inline-control">
              <input value={newUsername} onChange={(event) => setNewUsername(event.target.value)} />
              <button className="settings-button secondary" type="button" onClick={handleRename}>
                {t('account.rename')}
              </button>
            </div>,
          )}
          {renderPanelRow(t('account.userId'), t('account.userIdDesc'), <code>{currentUser.id}</code>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('account.updatePassword')}</h3>
        <p className="settings-section-desc">{t('account.updatePasswordDesc')}</p>
        <form className="settings-panel" onSubmit={handleUpdatePassword}>
          {renderPanelRow(
            t('account.oldPassword'),
            t('account.oldPasswordDesc'),
            <input type="password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} />,
          )}
          {renderPanelRow(
            t('auth.newPassword'),
            t('account.newPasswordDesc'),
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />,
          )}
          {renderPanelRow(
            t('auth.confirmNewPassword'),
            t('account.confirmPasswordDesc'),
            <input
              type="password"
              value={confirmNewPassword}
              onChange={(event) => setConfirmNewPassword(event.target.value)}
            />,
          )}
          {renderPanelRow(
            t('account.updatePassword'),
            t('account.updatePasswordActionDesc'),
            <button className="settings-button primary" type="submit">
              {t('account.updatePassword')}
            </button>,
          )}
        </form>
      </section>

      <section className="settings-section account-security-question-section">
        <h3 className="settings-section-title">{t('account.securityQuestion')}</h3>
        <p className="settings-section-desc">{t('account.securityQuestionDesc')}</p>
        <form className="settings-panel" onSubmit={handleUpdateSecurityQuestion}>
          {renderPanelRow(
            t('account.currentAnswerVerify'),
            t('account.currentQuestion', { question: translateSecurityQuestion(currentUser.security_question) }),
            <input
              value={currentSecurityAnswer}
              onChange={(event) => setCurrentSecurityAnswer(event.target.value)}
            />,
          )}
          {renderPanelRow(
            t('account.selectNewQuestion'),
            t('account.selectNewQuestionDesc'),
            <select value={nextSecurityQuestion} onChange={(event) => setNextSecurityQuestion(event.target.value)}>
              {securityQuestions.map((question) => (
                <option key={question} value={question}>
                  {translateSecurityQuestion(question)}
                </option>
              ))}
            </select>,
          )}
          {renderPanelRow(
            t('account.newQuestionAnswer'),
            t('account.newQuestionAnswerDesc'),
            <input value={nextSecurityAnswer} onChange={(event) => setNextSecurityAnswer(event.target.value)} />,
          )}
          {renderPanelRow(
            t('account.updateSecurityQuestion'),
            t('account.updateSecurityQuestionDesc'),
            <button className="settings-button primary" type="submit">
              {t('account.updateSecurityQuestion')}
            </button>,
          )}
        </form>
        {message && <p className="settings-inline-message">{message}</p>}
        {error && <p className="account-error-message">{error}</p>}
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">{t('account.loginHistory')}</h3>
        <p className="settings-section-desc">{t('account.loginHistoryDesc')}</p>
        <div className="settings-panel account-history-panel">
          <div className="account-history-row account-history-head">
            <span>{t('account.datetime')}</span>
            <span>{t('account.loginStatus')}</span>
            <span>{t('account.device')}</span>
          </div>
          {isLoadingAccount && <div className="account-history-empty">{t('common.processing')}</div>}
          {!isLoadingAccount && recentLoginHistory.length === 0 && (
            <div className="account-history-empty">{t('account.noLoginHistory')}</div>
          )}
          {recentLoginHistory.map((record) => (
            <div className="account-history-row" key={`${record.created_at}-${record.device}-${record.status}`}>
              <span>{record.created_at}</span>
              <strong className={record.status === 'success' ? 'success' : 'failed'}>
                {translateLoginStatus(record.status)}
              </strong>
              <span>{record.device}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="settings-section account-danger-zone">
        <h3 className="settings-section-title">{t('account.deleteAccount')}</h3>
        <p className="settings-section-desc">{t('account.deleteAccountDesc')}</p>
        <div className="settings-panel">
          {renderPanelRow(
            t('account.permanentDelete'),
            t('account.permanentDeleteDesc'),
            <button className="settings-button danger" type="button" onClick={() => setIsDeleteModalOpen(true)}>
              {t('account.deleteAccount')}
            </button>,
          )}
        </div>
      </section>

      {isDeleteModalOpen && (
        <div className="account-modal-backdrop" role="presentation" onMouseDown={closeDeleteModal}>
          <section
            className="account-delete-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-account-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            {isDeletingAccount ? (
              <div className="account-deleting-state">
                <h3 id="delete-account-title">{t('account.deleting')}</h3>
                <div className="account-wave-loader" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : (
              <>
                <h3 id="delete-account-title">{t('account.deleteAccount')}</h3>
                <p className="account-delete-warning">{t('account.deleteWarning')}</p>
                <label className="account-delete-password">
                  {t('account.currentPassword')}
                  <input
                    type="password"
                    value={deletePassword}
                    onChange={(event) => setDeletePassword(event.target.value)}
                    autoFocus
                  />
                </label>
                <div className="account-modal-actions">
                  <button className="settings-button secondary" type="button" onClick={closeDeleteModal}>
                    {t('common.cancel')}
                  </button>
                  <button
                    className="settings-button danger"
                    type="button"
                    onClick={handleDeleteAccount}
                    disabled={!deletePassword}
                  >
                    {t('account.confirmDelete')}
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
};

export default AccountManagementPage;
