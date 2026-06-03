export interface AuthUser {
  id: number;
  username: string;
  security_question: string;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
  expires_at: number;
}

export interface PlayerGame {
  game_id: string;
  opponent: string | null;
  result: 'win' | 'loss' | 'draw';
  score: string;
  date: string;
}

export interface PracticeRecord {
  game_id: string;
  practice_type: string;
  duration_seconds: number;
  date: string;
}

export interface DashboardResponse {
  user: AuthUser;
  stats: {
    total_games: number;
    total_wins: number;
    win_rate: number;
    total_practice_sessions: number;
  };
  recent_games: PlayerGame[];
  recent_practice: PracticeRecord[];
}

export interface MobileProfile {
  user: AuthUser;
  display_name: string;
  bio?: string;
  avatar_url?: string;
  player_level: string;
  followers_count: number;
  following_count: number;
  post_count: number;
  is_following?: boolean;
  is_self?: boolean;
}

export interface CommunityPost {
  id: number;
  user_id: number | null;
  author_name: string;
  author_avatar_url?: string;
  badge: string;
  title: string;
  body: string;
  preview_type: string;
  recording_id: string | null;
  tone: string;
  created_at: string;
  updated_at: string;
  likes: number;
  comments: number;
  shares: number;
  feed_score?: number | null;
  liked_by_me: boolean;
  bookmarked_by_me: boolean;
  image_urls: string[];
  image_transforms?: Array<{ x: number; y: number; scale: number; width?: number; height?: number; frame_width?: number }>;
}

export interface CommunityComment {
  id: number;
  post_id: number;
  user_id: number;
  author_name: string;
  author_avatar_url?: string;
  author_player_level?: string;
  body: string;
  created_at: string;
  likes: number;
  liked_by_me: boolean;
}

export interface CommunityPostsResponse {
  posts: CommunityPost[];
  total: number;
  limit: number;
  offset: number;
}

export interface MobileProfilePageResponse extends CommunityPostsResponse {
  profile: MobileProfile;
}

export interface MobileFollowingFeedResponse extends CommunityPostsResponse {
  hasMoreFollowing: boolean;
}

export interface MobileTrendingFeedResponse extends CommunityPostsResponse {
  hasMoreTrending: boolean;
}

export interface CommunityUploadImageInput {
  filename?: string;
  mime_type: string;
  data: string;
}

export interface CommunityUploadResponse {
  image_urls: string[];
}

export type CommunityUploadPurpose = 'post' | 'avatar';

export interface CreateCommunityPostInput {
  body: string;
  title?: string;
  image_urls?: string[];
  image_transforms?: Array<{ x: number; y: number; scale: number; width?: number; height?: number; frame_width?: number }>;
}

export interface Friend extends AuthUser {
  friendship_created_at: string;
}

export interface FriendsResponse {
  friends: Friend[];
}

export interface FriendInviteResponse {
  qr_payload: string;
  token: string;
  expires_at: number;
  owner: AuthUser;
}

export interface AcceptFriendInviteResponse {
  friend: AuthUser;
  already_friends: boolean;
}
