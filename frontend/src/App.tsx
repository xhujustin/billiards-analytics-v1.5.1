import './App.css';
import { useEffect, useState } from 'react';
import AuthScreens, { type AuthSession } from './components/AuthScreens';
import Dashboard from './components/Dashboard';
import ExploreScreen from './components/ExploreScreen';
import {
  getInitialThemeMode,
  resolveThemeMode,
  THEME_STORAGE_KEY,
  type ThemeMode,
} from './theme';

type LogoutDialogState = 'idle' | 'confirming' | 'logging-out';

function App() {
  const [authSession, setAuthSession] = useState<AuthSession | null>(null);
  const [authInitialMode, setAuthInitialMode] = useState<'welcome' | 'login'>('welcome');
  const [hasExplored, setHasExplored] = useState(false);
  const [logoutDialogState, setLogoutDialogState] = useState<LogoutDialogState>('idle');
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialThemeMode);

  const handleAuthenticated = (session: AuthSession) => {
    setAuthSession(session);
    setAuthInitialMode('welcome');
    setLogoutDialogState('idle');
  };

  const handleAuthAction = () => {
    if (authSession?.type === 'user') {
      setLogoutDialogState('confirming');
      return;
    }

    setAuthSession(null);
    setAuthInitialMode(authSession?.type === 'guest' ? 'login' : 'welcome');
  };

  const handleConfirmLogout = () => {
    setLogoutDialogState('logging-out');
  };

  const handleAccountDeleted = () => {
    setAuthSession(null);
    setAuthInitialMode('welcome');
    setLogoutDialogState('idle');
  };

  useEffect(() => {
    if (logoutDialogState !== 'logging-out') return undefined;

    const logoutTimer = window.setTimeout(() => {
      setAuthSession(null);
      setAuthInitialMode('welcome');
      setLogoutDialogState('idle');
    }, 2500);

    return () => window.clearTimeout(logoutTimer);
  }, [logoutDialogState]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
    const applyTheme = () => {
      const nextResolvedTheme = resolveThemeMode(themeMode);
      document.documentElement.dataset.theme = nextResolvedTheme;
      document.documentElement.style.colorScheme = nextResolvedTheme;
      window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
    };

    applyTheme();
    if (themeMode !== 'system') return undefined;

    mediaQuery.addEventListener('change', applyTheme);
    return () => mediaQuery.removeEventListener('change', applyTheme);
  }, [themeMode]);

  const shouldShowLogoutDialog = logoutDialogState !== 'idle';

  return (
    <div className="App">
      <div className={`app-shell ${shouldShowLogoutDialog ? 'is-dialog-blurred' : ''}`}>
        {!hasExplored ? (
          <ExploreScreen onStart={() => setHasExplored(true)} />
        ) : authSession ? (
          <Dashboard
            authSession={authSession}
            onAuthAction={handleAuthAction}
            onAuthSessionChange={setAuthSession}
            onAccountDeleted={handleAccountDeleted}
            themeMode={themeMode}
            onThemeModeChange={setThemeMode}
          />
        ) : (
          <AuthScreens
            initialMode={authInitialMode}
            onAuthenticated={handleAuthenticated}
            onBackToExplore={() => {
              setAuthInitialMode('welcome');
              setHasExplored(false);
            }}
          />
        )}
      </div>

      {shouldShowLogoutDialog && (
        <div
          className="logout-dialog-backdrop"
          role="presentation"
          onClick={() => {
            if (logoutDialogState === 'confirming') setLogoutDialogState('idle');
          }}
        >
          <section
            className={`logout-dialog ${logoutDialogState === 'logging-out' ? 'is-logout-loading' : ''}`}
            role={logoutDialogState === 'confirming' ? 'alertdialog' : 'status'}
            aria-modal={logoutDialogState === 'confirming'}
            aria-labelledby="logout-dialog-title"
            onClick={(event) => event.stopPropagation()}
          >
            {logoutDialogState === 'confirming' ? (
              <>
                <h2 id="logout-dialog-title">確定要登出嗎？</h2>
                <div className="logout-dialog-actions">
                  <button className="btn" type="button" onClick={() => setLogoutDialogState('idle')}>
                    取消
                  </button>
                  <button className="btn btn-primary" type="button" onClick={handleConfirmLogout}>
                    確認
                  </button>
                </div>
              </>
            ) : (
              <div className="logout-loading" aria-live="polite">
                <h2 id="logout-dialog-title">正在登出中，請稍後</h2>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
