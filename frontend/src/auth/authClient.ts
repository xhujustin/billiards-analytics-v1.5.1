export interface AuthUser {
  id: number;
  username: string;
  security_question: string;
  created_at: string;
  updated_at: string;
}

export interface LoginHistoryRecord {
  created_at: string;
  status: 'success' | 'failed';
  device: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
  expires_at: number;
}

export interface AuthMeResponse {
  user: AuthUser;
  login_history: LoginHistoryRecord[];
}

export const AUTH_STORAGE_KEY = 'qtrack_auth_session';
export const USERNAME_PATTERN = /^[A-Za-z0-9_]+$/;
export const PASSWORD_PATTERN = /^[A-Za-z0-9]+$/;

export const securityQuestions = [
  '你人生中養過的第一隻寵物叫什麼名字？',
  '你最要好的朋友名字是？',
  '你最喜歡的休閒活動是？',
  '你最嚮往或最喜歡去旅行的一個國家？',
  '你最喜歡的一部電影或動漫名稱？',
];

export const validateUsernameFormat = (value: string): boolean => {
  const username = value.trim();
  return username.length >= 3 && username.length <= 32 && USERNAME_PATTERN.test(username);
};

export const validatePasswordFormat = (value: string): boolean =>
  value.length >= 10 &&
  PASSWORD_PATTERN.test(value) &&
  /[A-Za-z]/.test(value) &&
  /\d/.test(value);

const buildHeaders = (token?: string): HeadersInit => ({
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

const getErrorCode = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    const code = body?.detail?.code || body?.code;
    if (code) return code;
  } catch {
    // Fall through to status-based codes below.
  }
  if (response.status === 404) return 'API_NOT_FOUND';
  return response.statusText;
};

const requestJson = async <T>(url: string, init: RequestInit): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error('CONNECTION_FAILED');
  }
  if (!response.ok) {
    throw new Error(await getErrorCode(response));
  }
  return response.json() as Promise<T>;
};

export const getDeviceLabel = (): string => {
  const userAgent = window.navigator.userAgent;
  const browser = userAgent.includes('Edg/')
    ? 'Edge'
    : userAgent.includes('Firefox/')
      ? 'Firefox'
      : userAgent.includes('Chrome/')
        ? 'Chrome'
        : userAgent.includes('Safari/')
          ? 'Safari'
          : 'Browser';
  const platform = window.navigator.platform || 'Unknown';
  return `${browser} / ${platform}`;
};

export const registerAccount = (
  apiBaseUrl: string,
  payload: {
    username: string;
    password: string;
    security_question: string;
    security_answer: string;
  },
): Promise<AuthResponse> =>
  requestJson(`${apiBaseUrl}/api/auth/register`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ ...payload, device: getDeviceLabel() }),
  });

export const loginAccount = (
  apiBaseUrl: string,
  username: string,
  password: string,
): Promise<AuthResponse> =>
  requestJson(`${apiBaseUrl}/api/auth/login`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ username, password, device: getDeviceLabel() }),
  });

export const logoutAccount = (apiBaseUrl: string, token: string): Promise<{ status: string }> =>
  requestJson(`${apiBaseUrl}/api/auth/logout`, {
    method: 'POST',
    headers: buildHeaders(token),
  });

export const getCurrentAccount = (apiBaseUrl: string, token: string): Promise<AuthMeResponse> =>
  requestJson(`${apiBaseUrl}/api/auth/me`, {
    method: 'GET',
    headers: buildHeaders(token),
  });

export const updateUsername = (apiBaseUrl: string, token: string, username: string): Promise<{ user: AuthUser }> =>
  requestJson(`${apiBaseUrl}/api/auth/me`, {
    method: 'PATCH',
    headers: buildHeaders(token),
    body: JSON.stringify({ username }),
  });

export const updatePassword = (
  apiBaseUrl: string,
  token: string,
  oldPassword: string,
  newPassword: string,
): Promise<{ status: string }> =>
  requestJson(`${apiBaseUrl}/api/auth/password`, {
    method: 'PATCH',
    headers: buildHeaders(token),
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });

export const updateSecurityQuestion = (
  apiBaseUrl: string,
  token: string,
  currentAnswer: string,
  securityQuestion: string,
  securityAnswer: string,
): Promise<{ user: AuthUser }> =>
  requestJson(`${apiBaseUrl}/api/auth/security-question`, {
    method: 'PATCH',
    headers: buildHeaders(token),
    body: JSON.stringify({
      current_answer: currentAnswer,
      security_question: securityQuestion,
      security_answer: securityAnswer,
    }),
  });

export const getPasswordResetQuestion = (
  apiBaseUrl: string,
  username: string,
): Promise<{ username: string; security_question: string }> =>
  requestJson(`${apiBaseUrl}/api/auth/password-reset/question?username=${encodeURIComponent(username)}`, {
    method: 'GET',
    headers: buildHeaders(),
  });

export const verifyPasswordResetAnswer = (
  apiBaseUrl: string,
  username: string,
  securityAnswer: string,
): Promise<{ verified: boolean }> =>
  requestJson(`${apiBaseUrl}/api/auth/password-reset/verify`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ username, security_answer: securityAnswer }),
  });

export const completePasswordReset = (
  apiBaseUrl: string,
  username: string,
  securityAnswer: string,
  newPassword: string,
): Promise<{ status: string }> =>
  requestJson(`${apiBaseUrl}/api/auth/password-reset/complete`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ username, security_answer: securityAnswer, new_password: newPassword }),
  });

export const deleteAccount = (apiBaseUrl: string, token: string, password: string): Promise<{ status: string }> =>
  requestJson(`${apiBaseUrl}/api/auth/me`, {
    method: 'DELETE',
    headers: buildHeaders(token),
    body: JSON.stringify({ password }),
  });
