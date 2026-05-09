export type ThemeMode = 'dark' | 'light' | 'system';
export type ResolvedTheme = 'dark' | 'light';

export const THEME_STORAGE_KEY = 'ncut.uiTheme';

export const isThemeMode = (value: string | null): value is ThemeMode => {
  return value === 'dark' || value === 'light' || value === 'system';
};

export const getInitialThemeMode = (): ThemeMode => {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemeMode(storedTheme) ? storedTheme : 'dark';
};

export const resolveThemeMode = (themeMode: ThemeMode): ResolvedTheme => {
  if (themeMode !== 'system') return themeMode;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
};
