import './App.css';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AuthScreens, { type AuthSession } from './components/AuthScreens';
import Dashboard from './components/Dashboard';
import ExploreScreen from './components/ExploreScreen';
import { AUTH_STORAGE_KEY, getCurrentAccount, logoutAccount } from './auth/authClient';
import i18n from './i18n';
import {
  LANGUAGE_STORAGE_KEY,
  isSupportedLanguage,
  type SupportedLanguage,
} from './i18n/types';
import {
  ACCENT_COLOR_STORAGE_KEY,
  FONT_SIZE_STORAGE_KEY,
  getAccentColorValue,
  getInitialAccentColorMode,
  getInitialFontSizeMode,
  getInitialThemeMode,
  getReadableTextColor,
  resolveThemeMode,
  THEME_STORAGE_KEY,
  type AccentColorMode,
  type FontSizeMode,
  type ResolvedTheme,
  type ThemeMode,
} from './theme';

type LogoutDialogState = 'idle' | 'confirming' | 'logging-out';

function App() {
  const { t } = useTranslation();
  const apiBaseUrl = import.meta.env.VITE_BACKEND_URL || '';
  const [authSession, setAuthSession] = useState<AuthSession | null>(() => {
    try {
      const storedValue = window.localStorage.getItem(AUTH_STORAGE_KEY);
      if (!storedValue) return null;
      const parsedValue = JSON.parse(storedValue) as AuthSession;
      if (parsedValue.type !== 'user' || !parsedValue.token) return null;
      if (parsedValue.expiresAt && parsedValue.expiresAt <= Date.now()) {
        window.localStorage.removeItem(AUTH_STORAGE_KEY);
        return null;
      }
      return parsedValue;
    } catch {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }
  });
  const [authInitialMode, setAuthInitialMode] = useState<'welcome' | 'login'>('welcome');
  const [hasExplored, setHasExplored] = useState(false);
  const [logoutDialogState, setLogoutDialogState] = useState<LogoutDialogState>('idle');
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialThemeMode);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolveThemeMode(getInitialThemeMode()));
  const [accentColorMode, setAccentColorMode] = useState<AccentColorMode>(getInitialAccentColorMode);
  const [fontSizeMode, setFontSizeMode] = useState<FontSizeMode>(getInitialFontSizeMode);
  const [language, setLanguage] = useState<SupportedLanguage>(() =>
    isSupportedLanguage(i18n.language) ? i18n.language : 'zh-TW',
  );

  const handleAuthenticated = (session: AuthSession) => {
    setAuthSession(session);
    if (session.type === 'user') {
      window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }
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
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setAuthSession(null);
    setAuthInitialMode('welcome');
    setLogoutDialogState('idle');
  };

  const handleAuthSessionChange = (session: AuthSession) => {
    setAuthSession(session);
    if (session.type === 'user') {
      window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    }
  };

  useEffect(() => {
    if (logoutDialogState !== 'logging-out') return undefined;

    const logoutTimer = window.setTimeout(() => {
      if (authSession?.type === 'user' && authSession.token) {
        logoutAccount(apiBaseUrl, authSession.token).catch(() => undefined);
      }
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      setAuthSession(null);
      setAuthInitialMode('welcome');
      setLogoutDialogState('idle');
    }, 2500);

    return () => window.clearTimeout(logoutTimer);
  }, [apiBaseUrl, authSession, logoutDialogState]);

  useEffect(() => {
    if (authSession?.type !== 'user' || !authSession.token) return;
    getCurrentAccount(apiBaseUrl, authSession.token)
      .then((response) => {
        handleAuthSessionChange({
          ...authSession,
          username: response.user.username,
          user: response.user,
        });
      })
      .catch(() => {
        window.localStorage.removeItem(AUTH_STORAGE_KEY);
        setAuthSession(null);
        setAuthInitialMode('login');
      });
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
    const applyTheme = () => {
      const nextResolvedTheme = resolveThemeMode(themeMode);
      setResolvedTheme(nextResolvedTheme);
      document.documentElement.dataset.theme = nextResolvedTheme;
      document.documentElement.style.colorScheme = nextResolvedTheme;
      window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
    };

    applyTheme();
    if (themeMode !== 'system') return undefined;

    mediaQuery.addEventListener('change', applyTheme);
    return () => mediaQuery.removeEventListener('change', applyTheme);
  }, [themeMode]);

  useEffect(() => {
    const accentColor = getAccentColorValue(accentColorMode, resolvedTheme);
    const accentTextColor = getReadableTextColor(accentColor);

    document.documentElement.style.setProperty('--color-accent', accentColor);
    document.documentElement.style.setProperty('--color-primary-bg', accentColor);
    document.documentElement.style.setProperty('--color-focus', accentColor);
    document.documentElement.style.setProperty('--color-primary-text', accentTextColor);
    window.localStorage.setItem(ACCENT_COLOR_STORAGE_KEY, accentColorMode);
  }, [accentColorMode, resolvedTheme]);

  useEffect(() => {
    document.documentElement.lang = language;
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    if (i18n.language !== language) void i18n.changeLanguage(language);
  }, [language]);

  useEffect(() => {
    document.documentElement.dataset.fontSize = fontSizeMode;
    window.localStorage.setItem(FONT_SIZE_STORAGE_KEY, fontSizeMode);
  }, [fontSizeMode]);

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
            onAuthSessionChange={handleAuthSessionChange}
            onAccountDeleted={handleAccountDeleted}
            themeMode={themeMode}
            onThemeModeChange={setThemeMode}
            resolvedTheme={resolvedTheme}
            accentColorMode={accentColorMode}
            onAccentColorModeChange={setAccentColorMode}
            fontSizeMode={fontSizeMode}
            onFontSizeModeChange={setFontSizeMode}
            language={language}
            onLanguageChange={setLanguage}
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
                <h2 id="logout-dialog-title">{t('app.logoutConfirmTitle')}</h2>
                <div className="logout-dialog-actions">
                  <button className="btn" type="button" onClick={() => setLogoutDialogState('idle')}>
                    {t('common.cancel')}
                  </button>
                  <button className="btn btn-primary" type="button" onClick={handleConfirmLogout}>
                    {t('common.confirm')}
                  </button>
                </div>
              </>
            ) : (
              <div className="logout-loading" aria-live="polite">
                <h2 id="logout-dialog-title">{t('app.logoutLoadingTitle')}</h2>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
