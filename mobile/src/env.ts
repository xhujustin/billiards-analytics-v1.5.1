declare const process: {
  env?: {
    EXPO_PUBLIC_MOBILE_API_URL?: string;
    NODE_ENV?: string;
  };
};
declare const __DEV__: boolean | undefined;

const CLOUD_MOBILE_API_URL = 'https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app';

export function getExplicitApiBaseUrl(): string {
  const location = typeof window !== 'undefined' ? window.location : undefined;

  if (location?.search) {
    const queryUrl = new URLSearchParams(location.search).get('api')?.trim().replace(/\/+$/, '');
    if (queryUrl) return queryUrl;
  }

  const envUrl = process.env?.EXPO_PUBLIC_MOBILE_API_URL?.trim().replace(/\/+$/, '');
  if (envUrl) return envUrl;

  if (location?.hostname) {
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
