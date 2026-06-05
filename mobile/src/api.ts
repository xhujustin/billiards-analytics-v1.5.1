import {
  AuthResponse,
  AuthMeResponse,
  CommunityComment,
  CommunityUploadImageInput,
  CommunityUploadPurpose,
  CommunityUploadResponse,
  CommunityPost,
  CommunityPostsResponse,
  CreateCommunityPostInput,
  DashboardResponse,
  FriendsResponse,
  MobileProfile,
  MobileProfilePageResponse,
  MobileFollowingFeedResponse,
  MobileTrendingFeedResponse,
} from './types';

const jsonHeaders = (token?: string): HeadersInit => ({
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

async function readError(response: Response): Promise<string> {
  const fallback = `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
  try {
    const text = await response.text();
    if (!text) return fallback;
    try {
      const body = JSON.parse(text);
      const detail = body?.detail;
      if (typeof detail === 'string') return `${fallback}: ${detail}`;
      const message = detail?.message || detail?.code || body?.message || body?.error;
      return message ? `${fallback}: ${message}` : `${fallback}: ${text.slice(0, 160)}`;
    } catch {
      return `${fallback}: ${text.slice(0, 160)}`;
    }
  } catch {
    return fallback;
  }
}

async function requestJson<T>(baseUrl: string, path: string, init: RequestInit, timeoutMs?: number): Promise<T> {
  const normalizedBaseUrl = baseUrl.trim().replace(/\/+$/, '');
  if (!normalizedBaseUrl) {
    throw new Error('請確認後端位址已設定，必須是 https:// 雲端網址或 http://桌機IP:8001。');
  }

  let response: Response;
  const controller = timeoutMs ? new AbortController() : undefined;
  const timeoutId = timeoutMs && controller ? setTimeout(() => controller.abort(), timeoutMs) : undefined;
  try {
    response = await fetch(`${normalizedBaseUrl}${path}`, controller ? { ...init, signal: controller.signal } : init);
  } catch (error) {
    if (timeoutId) clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('\u8f09\u5165\u903e\u6642\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66\u3002');
    }
    throw new Error('無法連線到後端，請確認 Cloud Run API 可連線，或重新啟動 mobile.bat。');
  }
  if (timeoutId) clearTimeout(timeoutId);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<T>;
}

export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

export function login(baseUrl: string, username: string, password: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>(baseUrl, '/api/auth/login', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ username, password, device: 'Expo Mobile' }),
  });
}

export function register(
  baseUrl: string,
  username: string,
  password: string,
  securityQuestion: string,
  securityAnswer: string,
): Promise<AuthResponse> {
  return requestJson<AuthResponse>(baseUrl, '/api/auth/register', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({
      username,
      password,
      security_question: securityQuestion,
      security_answer: securityAnswer,
      device: 'Expo Mobile',
    }),
  });
}

export function logout(baseUrl: string, token: string): Promise<{ status: string }> {
  return requestJson<{ status: string }>(baseUrl, '/api/auth/logout', {
    method: 'POST',
    headers: jsonHeaders(token),
  });
}

export function updateAuthProfile(baseUrl: string, token: string, username: string): Promise<{ user: AuthResponse['user'] }> {
  return requestJson<{ user: AuthResponse['user'] }>(baseUrl, '/api/auth/me', {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify({ username }),
  });
}

export function getAuthMe(baseUrl: string, token: string): Promise<AuthMeResponse> {
  return requestJson<AuthMeResponse>(baseUrl, '/api/auth/me', {
    method: 'GET',
    headers: jsonHeaders(token),
  });
}

export function changePassword(
  baseUrl: string,
  token: string,
  oldPassword: string,
  newPassword: string,
  logoutOtherDevices: boolean,
): Promise<{ status: string }> {
  return requestJson<{ status: string }>(baseUrl, '/api/auth/password', {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
      logout_other_devices: logoutOtherDevices,
    }),
  });
}

export function getDashboard(baseUrl: string, token: string): Promise<DashboardResponse> {
  return requestJson<DashboardResponse>(baseUrl, '/api/mobile/dashboard', {
    method: 'GET',
    headers: jsonHeaders(token),
  });
}

const normalizeMobileProfile = (baseUrl: string, profile: MobileProfile): MobileProfile => ({
  ...profile,
  avatar_url: resolveImageUrl(baseUrl, profile.avatar_url || ''),
});

export async function getMobileProfile(baseUrl: string, token: string): Promise<MobileProfile> {
  const profile = await requestJson<MobileProfile>(baseUrl, '/api/mobile/profile', {
    method: 'GET',
    headers: jsonHeaders(token),
  });
  return normalizeMobileProfile(baseUrl, profile);
}

export async function updateMobileProfile(
  baseUrl: string,
  token: string,
  input: { display_name?: string; bio?: string; avatar_url?: string; is_private?: boolean },
): Promise<MobileProfile> {
  const profile = await requestJson<MobileProfile>(baseUrl, '/api/mobile/profile', {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(input),
  });
  return normalizeMobileProfile(baseUrl, profile);
}

export async function getMobilePublicProfile(baseUrl: string, token: string, userId: number): Promise<MobileProfile> {
  const profile = await requestJson<MobileProfile>(baseUrl, `/api/mobile/users/${userId}/profile`, {
    method: 'GET',
    headers: jsonHeaders(token),
  });
  return normalizeMobileProfile(baseUrl, profile);
}

export async function getMobilePublicProfilePosts(
  baseUrl: string,
  token: string,
  userId: number,
  limit = 20,
  offset = 0,
): Promise<CommunityPostsResponse> {
  const response = await requestJson<CommunityPostsResponse>(
    baseUrl,
    `/api/mobile/users/${userId}/posts?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
      headers: jsonHeaders(token),
    },
  );
  return {
    ...response,
    posts: (response.posts || []).map((post) => normalizeCommunityPost(baseUrl, post)),
  };
}

export async function getMobilePublicProfilePage(
  baseUrl: string,
  token: string,
  userId: number,
  limit = 20,
  offset = 0,
): Promise<MobileProfilePageResponse> {
  const response = await requestJson<MobileProfilePageResponse>(
    baseUrl,
    `/api/mobile/users/${userId}/profile-page?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
      headers: jsonHeaders(token),
    },
    8000,
  );
  return {
    ...response,
    profile: normalizeMobileProfile(baseUrl, response.profile),
    posts: (response.posts || []).map((post) => normalizeCommunityPost(baseUrl, post)),
  };
}

export function followMobileUser(baseUrl: string, token: string, userId: number): Promise<{ is_following: boolean }> {
  return requestJson<{ is_following: boolean }>(baseUrl, `/api/mobile/follows/${userId}`, {
    method: 'POST',
    headers: jsonHeaders(token),
  });
}

export function unfollowMobileUser(baseUrl: string, token: string, userId: number): Promise<{ is_following: boolean }> {
  return requestJson<{ is_following: boolean }>(baseUrl, `/api/mobile/follows/${userId}`, {
    method: 'DELETE',
    headers: jsonHeaders(token),
  });
}

const resolveImageUrl = (baseUrl: string, url: string): string => {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('file://')) return url;
  return `${normalizeBaseUrl(baseUrl)}${url.startsWith('/') ? url : `/${url}`}`;
};

const normalizeCommunityPost = (baseUrl: string, post: CommunityPost): CommunityPost => ({
  ...post,
  author_avatar_url: resolveImageUrl(baseUrl, post.author_avatar_url || ''),
  shares: Number(post.shares || 0),
  image_urls: Array.isArray(post.image_urls) ? post.image_urls.map((url) => resolveImageUrl(baseUrl, url)).filter(Boolean).slice(0, 3) : [],
  image_transforms: Array.isArray(post.image_transforms) ? post.image_transforms.slice(0, 3) : [],
});

const normalizeCommunityComment = (baseUrl: string, comment: CommunityComment): CommunityComment => ({
  ...comment,
  author_avatar_url: resolveImageUrl(baseUrl, comment.author_avatar_url || ''),
  author_player_level: comment.author_player_level || '',
  likes: Number(comment.likes || 0),
  liked_by_me: Boolean(comment.liked_by_me),
});

export async function getMyCommunityPosts(baseUrl: string, token: string): Promise<CommunityPostsResponse> {
  const response = await requestJson<CommunityPostsResponse>(
    baseUrl,
    '/api/community/posts?tab=following&sort=latest&limit=10&offset=0',
    {
      method: 'GET',
      headers: jsonHeaders(token),
    },
  );
  return {
    ...response,
    posts: (response.posts || []).map((post) => normalizeCommunityPost(baseUrl, post)),
  };
}

export async function getMobileFollowingFeed(
  baseUrl: string,
  token: string,
  limit: number,
  offset: number,
): Promise<MobileFollowingFeedResponse> {
  const response = await requestJson<MobileFollowingFeedResponse>(
    baseUrl,
    `/api/mobile/feed/following?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
      headers: jsonHeaders(token),
    },
  );
  return {
    ...response,
    posts: (response.posts || []).map((post) => normalizeCommunityPost(baseUrl, post)),
  };
}

export async function getMobileTrendingFeed(
  baseUrl: string,
  token: string,
  limit: number,
  offset: number,
  excludeIds: number[],
): Promise<MobileTrendingFeedResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (excludeIds.length) params.set('exclude_ids', excludeIds.join(','));
  const response = await requestJson<MobileTrendingFeedResponse>(
    baseUrl,
    `/api/mobile/feed/trending?${params.toString()}`,
    {
      method: 'GET',
      headers: jsonHeaders(token),
    },
  );
  return {
    ...response,
    posts: (response.posts || []).map((post) => normalizeCommunityPost(baseUrl, post)),
  };
}

export function uploadCommunityImages(baseUrl: string, token: string, images: CommunityUploadImageInput[], purpose: CommunityUploadPurpose = 'post'): Promise<CommunityUploadResponse> {
  return requestJson<CommunityUploadResponse>(baseUrl, '/api/community/uploads', {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ images, purpose }),
  });
}

export async function createCommunityPost(baseUrl: string, token: string, input: CreateCommunityPostInput): Promise<CommunityPost> {
  const post = await requestJson<CommunityPost>(baseUrl, '/api/community/posts', {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({
      body: input.body,
      title: input.title || '',
      image_urls: input.image_urls || [],
      image_transforms: input.image_transforms || [],
    }),
  });
  return normalizeCommunityPost(baseUrl, post);
}

export function deleteCommunityPost(baseUrl: string, token: string, postId: number): Promise<{ status: string; post_id: number }> {
  return requestJson<{ status: string; post_id: number }>(baseUrl, `/api/community/posts/${postId}`, {
    method: 'DELETE',
    headers: jsonHeaders(token),
  });
}

export async function toggleCommunityLike(baseUrl: string, token: string, postId: number): Promise<CommunityPost> {
  const post = await requestJson<CommunityPost>(baseUrl, `/api/community/posts/${postId}/like`, {
    method: 'POST',
    headers: jsonHeaders(token),
  });
  return normalizeCommunityPost(baseUrl, post);
}

export async function toggleCommunityBookmark(baseUrl: string, token: string, postId: number): Promise<CommunityPost> {
  const post = await requestJson<CommunityPost>(baseUrl, `/api/community/posts/${postId}/bookmark`, {
    method: 'POST',
    headers: jsonHeaders(token),
  });
  return normalizeCommunityPost(baseUrl, post);
}

export async function createCommunityComment(baseUrl: string, token: string, postId: number, body: string): Promise<{ comment: CommunityComment; post: CommunityPost }> {
  const response = await requestJson<{ comment: CommunityComment; post: CommunityPost }>(baseUrl, `/api/community/posts/${postId}/comments`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ body }),
  });
  return { comment: normalizeCommunityComment(baseUrl, response.comment), post: normalizeCommunityPost(baseUrl, response.post) };
}

export async function getCommunityComments(baseUrl: string, token: string, postId: number): Promise<{ comments: CommunityComment[]; total: number }> {
  const response = await requestJson<{ comments: CommunityComment[]; total: number }>(baseUrl, `/api/community/posts/${postId}/comments`, {
    method: 'GET',
    headers: jsonHeaders(token),
  });
  return { ...response, comments: (response.comments || []).map((comment) => normalizeCommunityComment(baseUrl, comment)) };
}

export async function toggleCommunityCommentLike(baseUrl: string, token: string, commentId: number): Promise<CommunityComment> {
  const comment = await requestJson<CommunityComment>(baseUrl, `/api/community/comments/${commentId}/like`, {
    method: 'POST',
    headers: jsonHeaders(token),
  });
  return normalizeCommunityComment(baseUrl, comment);
}

export function getFriends(baseUrl: string, token: string): Promise<FriendsResponse> {
  return requestJson<FriendsResponse>(baseUrl, '/api/friends', {
    method: 'GET',
    headers: jsonHeaders(token),
  });
}

export function parseUserProfileQrPayload(payload: string): { userId?: number } {
  const trimmed = payload.trim();
  if (!trimmed) return {};
  const directUserId = Number(trimmed);
  if (Number.isInteger(directUserId) && directUserId > 0) return { userId: directUserId };

  const queryStart = trimmed.indexOf('?');
  if (queryStart < 0) return {};
  const params = new URLSearchParams(trimmed.slice(queryStart + 1));
  const rawUserId = params.get('userId') || params.get('user_id') || params.get('id') || '';
  const userId = Number(rawUserId);
  return Number.isInteger(userId) && userId > 0 ? { userId } : {};
}

export function startFriendGame(baseUrl: string, token: string, friendUserId: number): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(baseUrl, `/api/friends/${friendUserId}/start-game`, {
    method: 'POST',
    headers: jsonHeaders(token),
  });
}
