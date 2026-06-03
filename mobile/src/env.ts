declare const process: {
  env?: {
    EXPO_PUBLIC_MOBILE_API_URL?: string;
  };
};

export function getConfiguredApiBaseUrl(): string {
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
