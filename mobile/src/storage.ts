import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { AuthUser } from './types';

const sessionKey = 'cuevex_mobile_session';

export interface StoredSession {
  baseUrl: string;
  token: string;
  user: AuthUser;
}

export async function saveSession(session: StoredSession): Promise<void> {
  if (Platform.OS === 'web') {
    window.localStorage.setItem(sessionKey, JSON.stringify(session));
    return;
  }
  await SecureStore.setItemAsync(sessionKey, JSON.stringify(session));
}

export async function loadSession(): Promise<StoredSession | null> {
  const raw = Platform.OS === 'web' ? window.localStorage.getItem(sessionKey) : await SecureStore.getItemAsync(sessionKey);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    await clearSession();
    return null;
  }
}

export async function clearSession(): Promise<void> {
  if (Platform.OS === 'web') {
    window.localStorage.removeItem(sessionKey);
    return;
  }
  await SecureStore.deleteItemAsync(sessionKey);
}
