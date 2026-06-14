declare const process: {
  env?: {
    EXPO_PUBLIC_MOBILE_API_URL?: string;
    NODE_ENV?: string;
  };
};
declare const window:
  | undefined
  | {
      location?: Location;
      __CUEVEX_PWA_API_BASE_URL__?: string;
    };
declare const __DEV__: boolean | undefined;

const CLOUD_MOBILE_API_URL = 'https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app';
const PWA_DOMAIN_API_URLS: Record<string, string> = {
  'apppwa.lessleap.com': 'https://appcoachapi.lessleap.com',
};

export function getExplicitApiBaseUrl(): string {
  const location = typeof window !== 'undefined' ? window.location : undefined;

  if (location?.search) {
    const queryUrl = new URLSearchParams(location.search).get('api')?.trim().replace(/\/+$/, '');
    if (queryUrl) return queryUrl;
  }

  const pwaMetaUrl =
    typeof document !== 'undefined'
      ? document.querySelector('meta[name="cuevex-api-base-url"]')?.getAttribute('content')?.trim().replace(/\/+$/, '')
      : '';
  if (pwaMetaUrl) return pwaMetaUrl;

  const pwaUrl = typeof window !== 'undefined' ? window.__CUEVEX_PWA_API_BASE_URL__?.trim().replace(/\/+$/, '') : '';
  if (pwaUrl) return pwaUrl;

  const envUrl = process.env?.EXPO_PUBLIC_MOBILE_API_URL?.trim().replace(/\/+$/, '');
  if (envUrl) return envUrl;

  if (location?.hostname) {
    const mappedUrl = PWA_DOMAIN_API_URLS[location.hostname.toLowerCase()];
    if (mappedUrl) return mappedUrl;
    return `http://${location.hostname}:8001`;
  }

  return '';
}

export function getConfiguredApiBaseUrl(): string {
  const explicitUrl = getExplicitApiBaseUrl();
  if (explicitUrl) return explicitUrl;
  const isDevelopment = typeof __DEV__ !== 'undefined' ? __DEV__ : process.env?.NODE_ENV !== 'production';
  if (isDevelopment) return '';
  return CLOUD_MOBILE_API_URL;
}
