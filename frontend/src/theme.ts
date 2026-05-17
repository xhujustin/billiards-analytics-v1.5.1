export type ThemeMode = 'dark' | 'light' | 'system';
export type ResolvedTheme = 'dark' | 'light';
export type FontSizeMode = 'small' | 'standard' | 'large' | 'xlarge';
export type AccentColorMode = 'default' | 'emerald' | 'indigo' | 'amber' | 'cyan';

export const THEME_STORAGE_KEY = 'ncut.uiTheme';
export const FONT_SIZE_STORAGE_KEY = 'ncut.uiFontSize';
export const ACCENT_COLOR_STORAGE_KEY = 'ncut.uiAccentColor';

export const accentColorOptions: Array<{
  mode: AccentColorMode;
  dark: string;
  light: string;
}> = [
  { mode: 'default', dark: '#F5F5F5', light: '#2563EB' },
  { mode: 'emerald', dark: '#10B981', light: '#059669' },
  { mode: 'indigo', dark: '#6366F1', light: '#4F46E5' },
  { mode: 'amber', dark: '#F59E0B', light: '#D97706' },
  { mode: 'cyan', dark: '#06B6D4', light: '#0891B2' },
];

export const isThemeMode = (value: string | null): value is ThemeMode => {
  return value === 'dark' || value === 'light' || value === 'system';
};

export const getInitialThemeMode = (): ThemeMode => {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemeMode(storedTheme) ? storedTheme : 'dark';
};

export const isFontSizeMode = (value: string | null): value is FontSizeMode => {
  return value === 'small' || value === 'standard' || value === 'large' || value === 'xlarge';
};

export const getInitialFontSizeMode = (): FontSizeMode => {
  const storedFontSize = window.localStorage.getItem(FONT_SIZE_STORAGE_KEY);
  return isFontSizeMode(storedFontSize) ? storedFontSize : 'standard';
};

export const isAccentColorMode = (value: string | null): value is AccentColorMode => {
  return value === 'default' || value === 'emerald' || value === 'indigo' || value === 'amber' || value === 'cyan';
};

export const getInitialAccentColorMode = (): AccentColorMode => {
  const storedAccentColor = window.localStorage.getItem(ACCENT_COLOR_STORAGE_KEY);
  return isAccentColorMode(storedAccentColor) ? storedAccentColor : 'default';
};

export const resolveThemeMode = (themeMode: ThemeMode): ResolvedTheme => {
  if (themeMode !== 'system') return themeMode;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
};

export const getAccentColorValue = (accentColorMode: AccentColorMode, resolvedTheme: ResolvedTheme) => {
  const option = accentColorOptions.find((item) => item.mode === accentColorMode) || accentColorOptions[0];
  return option[resolvedTheme];
};

export const getReadableTextColor = (backgroundColor: string) => {
  const normalized = backgroundColor.replace('#', '');
  const r = Number.parseInt(normalized.slice(0, 2), 16);
  const g = Number.parseInt(normalized.slice(2, 4), 16);
  const b = Number.parseInt(normalized.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.58 ? '#111111' : '#ffffff';
};
