export interface MockLoginRecord {
  datetime: string;
  status: '成功' | '失敗';
  device: string;
}

export interface MockUser {
  username: string;
  password: string;
  securityQuestion: string;
  securityAnswer: string;
  userId: string;
  loginHistory: MockLoginRecord[];
}

type StoredMockUser = Partial<MockUser> & {
  username?: unknown;
  password?: unknown;
  securityQuestion?: unknown;
  securityAnswer?: unknown;
  userId?: unknown;
  loginHistory?: unknown;
};

export const MOCK_USERS_STORAGE_KEY = 'qtrack_mock_users';
const LEGACY_MOCK_USERS_STORAGE_KEY = 'cuedex_mock_users';
export const CREDENTIAL_PATTERN = /^[a-zA-Z0-9_]+$/;
export const FORMAT_ERROR = '格式錯誤，僅允許英文字母、數字、與下底線 (_)';

export const securityQuestions = [
  '你人生中養過的第一隻寵物叫什麼名字？',
  '你最要好的朋友名字是？',
  '你最喜歡的休閒活動是？',
  '你最嚮往或最喜歡去旅行的一個國家？',
  '你最喜歡的一部電影或動漫名稱？',
];

const defaultUsers: MockUser[] = [
  {
    username: 'QTrack_User',
    password: 'QTrack_123',
    securityQuestion: securityQuestions[0],
    securityAnswer: 'Mimi',
    userId: 'CUE-7B1D90',
    loginHistory: [],
  },
];

export const validateCredentialFormat = (value: string): boolean => CREDENTIAL_PATTERN.test(value);

const createStableUserId = (username: string, index: number): string => {
  let hash = 0;
  const source = `${username}:${index}`;

  for (let i = 0; i < source.length; i += 1) {
    hash = (hash * 31 + source.charCodeAt(i)) >>> 0;
  }

  return `CUE-${hash.toString(16).toUpperCase().padStart(6, '0').slice(0, 6)}`;
};

const isStoredMockUser = (user: StoredMockUser): user is Required<Pick<MockUser, 'username' | 'password' | 'securityQuestion' | 'securityAnswer'>> & StoredMockUser =>
  typeof user?.username === 'string' &&
  typeof user?.password === 'string' &&
  typeof user?.securityQuestion === 'string' &&
  typeof user?.securityAnswer === 'string';

const isStoredLoginRecord = (record: unknown): record is MockLoginRecord => {
  if (!record || typeof record !== 'object') return false;

  const loginRecord = record as Partial<MockLoginRecord>;
  return (
    typeof loginRecord.datetime === 'string' &&
    (loginRecord.status === '成功' || loginRecord.status === '失敗') &&
    typeof loginRecord.device === 'string'
  );
};

const normalizeUsers = (users: StoredMockUser[]): MockUser[] =>
  users.filter(isStoredMockUser).map((user, index) => ({
    username: user.username,
    password: user.password,
    securityQuestion: securityQuestions.includes(user.securityQuestion)
      ? user.securityQuestion
      : securityQuestions[0],
    securityAnswer: user.securityAnswer,
    userId: typeof user.userId === 'string' && user.userId ? user.userId : createStableUserId(user.username, index),
    loginHistory: Array.isArray(user.loginHistory) ? user.loginHistory.filter(isStoredLoginRecord) : [],
  }));

export const saveMockUsers = (users: MockUser[]) => {
  window.localStorage.setItem(MOCK_USERS_STORAGE_KEY, JSON.stringify(users));
};

export const loadMockUsers = (): MockUser[] => {
  const storedValue =
    window.localStorage.getItem(MOCK_USERS_STORAGE_KEY) ||
    window.localStorage.getItem(LEGACY_MOCK_USERS_STORAGE_KEY);
  if (!storedValue) {
    saveMockUsers(defaultUsers);
    return defaultUsers;
  }

  try {
    const parsedValue = JSON.parse(storedValue);
    if (!Array.isArray(parsedValue)) {
      saveMockUsers(defaultUsers);
      return defaultUsers;
    }

    const normalizedUsers = normalizeUsers(parsedValue);
    saveMockUsers(normalizedUsers);
    return normalizedUsers;
  } catch {
    saveMockUsers(defaultUsers);
    return defaultUsers;
  }
};

export const findUserByName = (users: MockUser[], username: string): MockUser | undefined =>
  users.find((user) => user.username === username);

export const isUsernameTaken = (users: MockUser[], username: string, currentUsername?: string): boolean =>
  users.some((user) => user.username === username && user.username !== currentUsername);

const formatLoginDatetime = (date: Date): string => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}`;
};

const getBrowserName = (): string => {
  const userAgent = window.navigator.userAgent;
  if (userAgent.includes('Edg/')) return 'Edge';
  if (userAgent.includes('Firefox/')) return 'Firefox';
  if (userAgent.includes('Chrome/')) return 'Chrome';
  if (userAgent.includes('Safari/')) return 'Safari';
  return 'Browser';
};

const getOperatingSystemName = (): string => {
  const platform = window.navigator.platform.toLowerCase();
  const userAgent = window.navigator.userAgent.toLowerCase();
  if (platform.includes('win') || userAgent.includes('windows')) return 'Windows';
  if (platform.includes('mac')) return 'macOS';
  if (platform.includes('linux')) return 'Linux';
  if (userAgent.includes('android')) return 'Android';
  if (/iphone|ipad|ipod/.test(userAgent)) return 'iOS';
  return 'Unknown';
};

export const createLoginRecord = (status: MockLoginRecord['status']): MockLoginRecord => ({
  datetime: formatLoginDatetime(new Date()),
  status,
  device: `${getBrowserName()} / ${getOperatingSystemName()}`,
});

export const appendLoginRecord = (
  users: MockUser[],
  username: string,
  status: MockLoginRecord['status'],
): MockUser[] =>
  users.map((user) =>
    user.username === username
      ? {
          ...user,
          loginHistory: [createLoginRecord(status), ...user.loginHistory].slice(0, 10),
        }
      : user,
  );
