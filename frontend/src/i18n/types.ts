export const LANGUAGE_STORAGE_KEY = 'ncut.language';

export const supportedLanguages = ['zh-TW', 'zh-CN', 'en-US'] as const;

export type SupportedLanguage = (typeof supportedLanguages)[number];

export const languageLabels: Record<SupportedLanguage, string> = {
  'zh-TW': '繁體中文',
  'zh-CN': '简体中文',
  'en-US': 'English',
};

export const isSupportedLanguage = (value: string | null | undefined): value is SupportedLanguage =>
  supportedLanguages.includes(value as SupportedLanguage);

