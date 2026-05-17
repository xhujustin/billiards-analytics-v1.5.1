export type CommunityPreviewType = 'pool-table' | 'pool-table-alt' | 'pose-analysis' | 'stats';
export type CommunityTab = 'all' | 'explore' | 'following';
export type CommunitySort = 'latest' | 'popular' | 'comments';

export interface CommunityPost {
  id: number;
  user_id: number | null;
  author_name: string;
  badge: string;
  title: string;
  body: string;
  preview_type: CommunityPreviewType;
  recording_id: string | null;
  tone: string;
  created_at: string;
  updated_at: string;
  likes: number;
  comments: number;
  liked_by_me: boolean;
  bookmarked_by_me: boolean;
}

export interface CommunityComment {
  id: number;
  post_id: number;
  user_id: number | null;
  author_name: string;
  body: string;
  created_at: string;
}

export interface CommunityPostsResponse {
  posts: CommunityPost[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateCommunityPostPayload {
  title: string;
  body: string;
  preview_type: CommunityPreviewType;
  recording_id?: string | null;
}

const buildHeaders = (token?: string): HeadersInit => ({
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

const parseErrorCode = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    return body?.detail?.code || body?.code || response.statusText;
  } catch {
    return response.statusText;
  }
};

const requestJson = async <T>(url: string, init: RequestInit): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error('CONNECTION_FAILED');
  }

  if (!response.ok) {
    throw new Error(await parseErrorCode(response));
  }

  return response.json() as Promise<T>;
};

export const getCommunityPosts = (
  apiBaseUrl: string,
  params: { tab: CommunityTab; sort: CommunitySort; limit?: number; offset?: number },
  token?: string,
): Promise<CommunityPostsResponse> => {
  const query = new URLSearchParams({
    tab: params.tab,
    sort: params.sort,
    limit: String(params.limit ?? 20),
    offset: String(params.offset ?? 0),
  });

  return requestJson(`${apiBaseUrl}/api/community/posts?${query.toString()}`, {
    method: 'GET',
    headers: buildHeaders(token),
  });
};

export const createCommunityPost = (
  apiBaseUrl: string,
  token: string,
  payload: CreateCommunityPostPayload,
): Promise<CommunityPost> =>
  requestJson(`${apiBaseUrl}/api/community/posts`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify(payload),
  });

export const toggleCommunityLike = (
  apiBaseUrl: string,
  token: string,
  postId: number,
): Promise<CommunityPost> =>
  requestJson(`${apiBaseUrl}/api/community/posts/${postId}/like`, {
    method: 'POST',
    headers: buildHeaders(token),
  });

export const toggleCommunityBookmark = (
  apiBaseUrl: string,
  token: string,
  postId: number,
): Promise<CommunityPost> =>
  requestJson(`${apiBaseUrl}/api/community/posts/${postId}/bookmark`, {
    method: 'POST',
    headers: buildHeaders(token),
  });

export const getCommunityComments = (
  apiBaseUrl: string,
  postId: number,
): Promise<{ comments: CommunityComment[]; total: number }> =>
  requestJson(`${apiBaseUrl}/api/community/posts/${postId}/comments`, {
    method: 'GET',
    headers: buildHeaders(),
  });

export const createCommunityComment = (
  apiBaseUrl: string,
  token: string,
  postId: number,
  body: string,
): Promise<{ comment: CommunityComment; post: CommunityPost }> =>
  requestJson(`${apiBaseUrl}/api/community/posts/${postId}/comments`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ body }),
  });
