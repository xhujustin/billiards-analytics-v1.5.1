import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import enUS from './locales/en-US';
import zhCN from './locales/zh-CN';
import zhTW from './locales/zh-TW';
import {
  LANGUAGE_STORAGE_KEY,
  isSupportedLanguage,
  type SupportedLanguage,
} from './types';

export const getInitialLanguage = (): SupportedLanguage => {
  try {
    const storedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isSupportedLanguage(storedLanguage)) return storedLanguage;
  } catch {
    // localStorage may be unavailable in private or restricted contexts.
  }

  const browserLanguage = navigator.language;
  if (browserLanguage.toLowerCase().startsWith('zh-cn')) return 'zh-CN';
  if (browserLanguage.toLowerCase().startsWith('zh')) return 'zh-TW';
  return 'zh-TW';
};

i18n.use(initReactI18next).init({
  resources: {
    'zh-TW': { translation: zhTW },
    'zh-CN': { translation: zhCN },
    'en-US': { translation: enUS },
  },
  lng: getInitialLanguage(),
  fallbackLng: 'zh-TW',
  interpolation: {
    escapeValue: false,
  },
  returnNull: false,
});

export default i18n;
