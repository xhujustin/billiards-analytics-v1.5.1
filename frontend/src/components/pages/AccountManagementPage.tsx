import React, { useEffect, useMemo, useState } from 'react';
import type { AuthSession } from '../AuthScreens';
import {
  findUserByName,
  FORMAT_ERROR,
  isUsernameTaken,
  loadMockUsers,
  type MockUser,
  saveMockUsers,
  securityQuestions,
  validateCredentialFormat,
} from '../../auth/mockAccountStore';
import './SettingsPage.css';
import './AccountManagementPage.css';

interface AccountManagementPageProps {
  authSession: AuthSession;
  onSessionChange: (session: AuthSession) => void;
  onLoginRequest: () => void;
  onAccountDeleted: () => void;
}

export const AccountManagementPage: React.FC<AccountManagementPageProps> = ({
  authSession,
  onSessionChange,
  onLoginRequest,
  onAccountDeleted,
}) => {
  const [users, setUsers] = useState<MockUser[]>(() => loadMockUsers());
  const currentUser = useMemo(
    () => (authSession.type === 'user' && authSession.username ? findUserByName(users, authSession.username) : undefined),
    [authSession, users],
  );

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
  const recentLoginHistory = currentUser?.loginHistory.slice(0, 3) || [];

  useEffect(() => {
    if (!currentUser) return;
    setNewUsername(currentUser.username);
    setNextSecurityQuestion(currentUser.securityQuestion);
  }, [currentUser]);

  const persistUsers = (nextUsers: MockUser[]) => {
    setUsers(nextUsers);
    saveMockUsers(nextUsers);
  };

  const showMessage = (nextMessage: string) => {
    setError('');
    setMessage(nextMessage);
  };

  const showError = (nextError: string) => {
    setMessage('');
    setError(nextError);
  };

  const updateCurrentUser = (updater: (user: MockUser) => MockUser) => {
    if (!currentUser) return;
    persistUsers(users.map((user) => (user.userId === currentUser.userId ? updater(user) : user)));
  };

  const handleRename = () => {
    if (!currentUser) return;
    const username = newUsername.trim();

    if (!validateCredentialFormat(username)) {
      showError(FORMAT_ERROR);
      return;
    }

    if (isUsernameTaken(users, username, currentUser.username)) {
      showError('名稱已被使用');
      return;
    }

    updateCurrentUser((user) => ({ ...user, username }));
    onSessionChange({ type: 'user', username });
    showMessage('使用者名稱已更新');
  };

  const handleUpdatePassword = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!currentUser) return;

    if (oldPassword !== currentUser.password) {
      showError('舊密碼錯誤');
      return;
    }

    if (!validateCredentialFormat(newPassword)) {
      showError(FORMAT_ERROR);
      return;
    }

    if (newPassword !== confirmNewPassword) {
      showError('確認新密碼需與新密碼一致');
      return;
    }

    updateCurrentUser((user) => ({ ...user, password: newPassword }));
    setOldPassword('');
    setNewPassword('');
    setConfirmNewPassword('');
    showMessage('密碼已更新');
  };

  const handleUpdateSecurityQuestion = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!currentUser) return;

    if (currentSecurityAnswer.trim() !== currentUser.securityAnswer) {
      showError('目前答案驗證失敗');
      return;
    }

    if (!nextSecurityAnswer.trim()) {
      showError('請輸入新問題答案');
      return;
    }

    updateCurrentUser((user) => ({
      ...user,
      securityQuestion: nextSecurityQuestion,
      securityAnswer: nextSecurityAnswer.trim(),
    }));
    setCurrentSecurityAnswer('');
    setNextSecurityAnswer('');
    showMessage('安全問題已更新');
  };

  const closeDeleteModal = () => {
    if (isDeletingAccount) return;
    setIsDeleteModalOpen(false);
    setDeletePassword('');
  };

  const handleDeleteAccount = () => {
    if (!currentUser || deletePassword !== currentUser.password || isDeletingAccount) return;

    setIsDeletingAccount(true);
    window.setTimeout(() => {
      const nextUsers = users.filter((user) => user.userId !== currentUser.userId);
      saveMockUsers(nextUsers);
      window.localStorage.removeItem('billiards_session_id');
      window.localStorage.removeItem('billiards_session');
      onAccountDeleted();
    }, 2500);
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
        <h2 className="page-title">帳號管理</h2>
        <section className="settings-section">
          <h3 className="settings-section-title">需要登入</h3>
          <p className="settings-section-desc">訪客可以使用主程式，但需要登入帳號後才能管理個人資料與安全設定。</p>
          <div className="settings-panel">
            {renderPanelRow(
              '目前身分',
              '訪客身分不會寫入 Mock 使用者資料。',
              <strong>訪客</strong>,
            )}
            {renderPanelRow(
              '前往登入',
              '登入後即可修改名稱、密碼與安全問題。',
              <button className="settings-button primary" type="button" onClick={onLoginRequest}>
                前往登入
              </button>,
            )}
          </div>
        </section>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="settings-page account-page">
        <h2 className="page-title">帳號管理</h2>
        <section className="settings-section">
          <h3 className="settings-section-title">找不到帳號</h3>
          <p className="settings-section-desc">目前登入狀態與 Mock 使用者資料不一致，請重新登入。</p>
          <div className="settings-panel">
            {renderPanelRow(
              '重新登入',
              '重新建立帳號 session 後再管理資料。',
              <button className="settings-button primary" type="button" onClick={onLoginRequest}>
                前往登入
              </button>,
            )}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="settings-page account-page">
      <h2 className="page-title">帳號管理</h2>

      <section className="settings-section">
        <h3 className="settings-section-title">個人檔案</h3>
        <p className="settings-section-desc">管理 Q Track 帳號的顯示名稱與個人識別資訊。</p>
        <div className="settings-panel">
          {renderPanelRow(
            '使用者名稱',
            '目前登入使用的名稱。僅允許英文字母、數字、下底線。',
            <div className="account-inline-control">
              <input value={newUsername} onChange={(event) => setNewUsername(event.target.value)} />
              <button className="settings-button secondary" type="button" onClick={handleRename}>
                修改名稱
              </button>
            </div>,
          )}
          {renderPanelRow('使用者 ID', '本機 Mock 帳號識別碼，不可修改。', <code>{currentUser.userId}</code>)}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">更新密碼</h3>
        <p className="settings-section-desc">修改登入密碼，下次登入需使用新密碼。</p>
        <form className="settings-panel" onSubmit={handleUpdatePassword}>
          {renderPanelRow(
            '舊密碼',
            '請輸入目前密碼以確認身分。',
            <input type="password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} />,
          )}
          {renderPanelRow(
            '新密碼',
            '僅允許英文字母、數字、下底線。',
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />,
          )}
          {renderPanelRow(
            '確認新密碼',
            '需與新密碼一致。',
            <input
              type="password"
              value={confirmNewPassword}
              onChange={(event) => setConfirmNewPassword(event.target.value)}
            />,
          )}
          {renderPanelRow(
            '更新密碼',
            '修改後下次登入需使用新密碼。',
            <button className="settings-button primary" type="submit">
              更新密碼
            </button>,
          )}
        </form>
      </section>

      <section className="settings-section account-security-question-section">
        <h3 className="settings-section-title">安全問題</h3>
        <p className="settings-section-desc">更新找回密碼流程使用的安全問題與答案。</p>
        <form className="settings-panel" onSubmit={handleUpdateSecurityQuestion}>
          {renderPanelRow(
            '目前的答案驗證',
            `目前問題：${currentUser.securityQuestion}`,
            <input
              value={currentSecurityAnswer}
              onChange={(event) => setCurrentSecurityAnswer(event.target.value)}
            />,
          )}
          {renderPanelRow(
            '選擇新問題',
            '更新後會套用到找回密碼流程。',
            <select value={nextSecurityQuestion} onChange={(event) => setNextSecurityQuestion(event.target.value)}>
              {securityQuestions.map((question) => (
                <option key={question} value={question}>
                  {question}
                </option>
              ))}
            </select>,
          )}
          {renderPanelRow(
            '新問題答案',
            '答案會保留大小寫差異。',
            <input value={nextSecurityAnswer} onChange={(event) => setNextSecurityAnswer(event.target.value)} />,
          )}
          {renderPanelRow(
            '更新安全問題',
            '需先通過目前答案驗證。',
            <button className="settings-button primary" type="submit">
              更新安全問題
            </button>,
          )}
        </form>
        {message && <p className="settings-inline-message">{message}</p>}
        {error && <p className="account-error-message">{error}</p>}
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">登入紀錄</h3>
        <p className="settings-section-desc">最近 3 筆本機登入紀錄。</p>
        <div className="settings-panel account-history-panel">
          <div className="account-history-row account-history-head">
            <span>日期時間</span>
            <span>登入狀態</span>
            <span>裝置</span>
          </div>
          {recentLoginHistory.length === 0 && (
            <div className="account-history-empty">尚無登入紀錄</div>
          )}
          {recentLoginHistory.map((record) => (
            <div className="account-history-row" key={`${record.datetime}-${record.device}`}>
              <span>{record.datetime}</span>
              <strong className={record.status === '成功' ? 'success' : 'failed'}>{record.status}</strong>
              <span>{record.device}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="settings-section account-danger-zone">
        <h3 className="settings-section-title">刪除帳號</h3>
        <p className="settings-section-desc">此操作會永久移除目前 Mock 帳號。</p>
        <div className="settings-panel">
          {renderPanelRow(
            '永久刪除',
            '刪除後將無法使用此帳號登入。',
            <button className="settings-button danger" type="button" onClick={() => setIsDeleteModalOpen(true)}>
              刪除帳號
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
                <h3 id="delete-account-title">正在刪除帳號...</h3>
                <div className="account-wave-loader" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : (
              <>
                <h3 id="delete-account-title">刪除帳號</h3>
                <p className="account-delete-warning">
                  確定要刪除帳號嗎？一旦刪除，您的個人設定、慣用手偏好及所有歷史數據將會永久消失，無法恢復。
                </p>
                <label className="account-delete-password">
                  當前密碼
                  <input
                    type="password"
                    value={deletePassword}
                    onChange={(event) => setDeletePassword(event.target.value)}
                    autoFocus
                  />
                </label>
                <div className="account-modal-actions">
                  <button className="settings-button secondary" type="button" onClick={closeDeleteModal}>
                    取消
                  </button>
                  <button
                    className="settings-button danger"
                    type="button"
                    onClick={handleDeleteAccount}
                    disabled={deletePassword !== currentUser.password}
                  >
                    確認刪除
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
