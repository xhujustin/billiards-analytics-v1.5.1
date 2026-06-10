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

export interface LoginHistoryEntry {
  created_at: string;
  status: string;
  device: string;
}

export interface AuthMeResponse {
  user: AuthUser;
  login_history: LoginHistoryEntry[];
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

export interface AbilityScore {
  key: 'accuracy' | 'cue_control' | 'power_control' | 'stroke_stability' | 'position_play';
  label: string;
  score: number;
}

export interface RecommendedTraining {
  title: string;
  reason: string;
  duration_minutes: number;
}

export type AnalyticsDataStatus = 'ready' | 'pending_desktop_sync' | 'empty';

export interface DashboardOverview {
  joined_at?: string;
  joined_days: number;
  total_practice_sessions: number;
  total_battle_matches: number;
  overall_score: number;
  level_label: string;
  score_basis: string;
}

export interface DashboardWeeklySummary {
  practice_hours: number;
  shot_count: number | null;
  pot_count: number | null;
  pot_rate: number | null;
  shot_data_status: AnalyticsDataStatus;
}

export interface DashboardChartPoint {
  x: string;
  y: number;
  label?: string;
  week_start_label?: string;
  week_end_label?: string;
  practice_hours?: number;
  shot_count?: number;
  pot_count?: number;
  pot_rate?: number;
}

export interface DashboardChartSeries {
  title: string;
  x_label: string;
  y_label: string;
  status: AnalyticsDataStatus;
  points: DashboardChartPoint[];
}

export interface DashboardAnalyticsV1 {
  overall_score: number;
  level_label: string;
  score_confidence: 'low' | 'medium';
  score_basis: string;
  ability_scores: AbilityScore[];
  coach_summary: string;
  strongest_ability: string;
  weakest_ability: string;
  recommended_trainings: RecommendedTraining[];
  recent_trend: {
    label: string;
    summary: string;
  };
  overview?: DashboardOverview;
  weekly_summary?: DashboardWeeklySummary;
  chart_series?: {
    practice_trend: DashboardChartSeries;
    accuracy_trend: DashboardChartSeries;
  };
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
  analytics_v1?: DashboardAnalyticsV1;
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
  is_private?: boolean;
  is_following?: boolean;
  is_self?: boolean;
  block_state?: 'none' | 'blocked_by_me' | 'blocked_me';
  is_blocked_by_me?: boolean;
  has_blocked_me?: boolean;
}

export interface MobileBlockedUser {
  user: AuthUser;
  display_name: string;
  avatar_url?: string;
  blocked_at: string;
}

export interface MobileFollowUser {
  user: AuthUser;
  display_name: string;
  avatar_url?: string;
  player_level: string;
  is_following?: boolean;
  is_self?: boolean;
  followed_at: string;
}

export interface MobileFollowListResponse {
  users: MobileFollowUser[];
  total: number;
  limit: number;
  offset: number;
  kind: 'followers' | 'following';
}

export interface MobileBlocksResponse {
  blocked_users: MobileBlockedUser[];
  total: number;
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

export interface MobileNotificationSettings {
  user_id: number;
  push_enabled: boolean;
  post_likes_enabled: boolean;
  post_comments_enabled: boolean;
  comment_replies_enabled: boolean;
  comment_likes_enabled: boolean;
  new_followers_enabled: boolean;
  mutual_follows_enabled: boolean;
  account_security_enabled: boolean;
  login_changes_enabled: boolean;
  service_announcements_enabled: boolean;
  show_preview_enabled: boolean;
  type_only_enabled: boolean;
  quiet_hours_enabled: boolean;
  updated_at?: string;
}

export type MobileNotificationSettingsUpdate = Partial<Omit<MobileNotificationSettings, 'user_id' | 'updated_at'>>;

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
