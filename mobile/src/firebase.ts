declare const process: {
  env?: {
    EXPO_PUBLIC_MOBILE_REMOTE_API_URL?: string;
    EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES?: string;
  };
};

export interface MobileRuntimeConfig {
  apiBaseUrl: string;
  uploadTargetBytes: number;
  testMode: boolean;
}

const DEFAULT_UPLOAD_TARGET_BYTES = 15 * 1024 * 1024;

const parsePositiveInteger = (value: string | undefined, fallback: number): number => {
  const parsed = Number(value || '');
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback;
};

const normalizeUrl = (value: string | undefined): string => (value || '').trim().replace(/\/+$/, '');

export async function initializeMobileFirebaseTools(): Promise<MobileRuntimeConfig> {
  return {
    apiBaseUrl: normalizeUrl(process.env?.EXPO_PUBLIC_MOBILE_REMOTE_API_URL),
    uploadTargetBytes: parsePositiveInteger(process.env?.EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES, DEFAULT_UPLOAD_TARGET_BYTES),
    testMode: true,
  };
}

