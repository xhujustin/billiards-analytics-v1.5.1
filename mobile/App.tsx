import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Animated, Dimensions, FlatList, Image, ImageStyle, Keyboard as RNKeyboard, LogBox, Modal, NativeScrollEvent, NativeSyntheticEvent, Platform, Pressable, SafeAreaView, ScrollView, StatusBar, StyleProp, StyleSheet, Text, TextInput, TextStyle, View, Vibration } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as FileSystem from 'expo-file-system/legacy';
import * as ImageManipulator from 'expo-image-manipulator';
import * as MediaLibrary from 'expo-media-library';
import {
  BarChart3,
  Bell,
  Bookmark,
  ChevronDown,
  ChevronRight,
  Grid3X3,
  Heart,
  Home,
  Keyboard,
  Lock,
  LogOut,
  MessageCircle,
  MoreHorizontal,
  Plus,
  QrCode,
  Search,
  Send,
  Settings,
  ShieldCheck,
  User,
  UserPlus,
  Users,
  X,
} from 'lucide-react-native';
import Svg, { Circle, Path, Polyline } from 'react-native-svg';
import QRCode from 'react-native-qrcode-svg';

import {
  acceptFriendInvite,
  createCommunityComment,
  createCommunityPost,
  createFriendInvite,
  deleteCommunityPost,
  getCommunityComments,
  getDashboard,
  getFriends,
  getMobileFollowingFeed,
  getMobileProfile,
  getMobilePublicProfile,
  getMobilePublicProfilePage,
  getMobilePublicProfilePosts,
  getMobileTrendingFeed,
  getMyCommunityPosts,
  followMobileUser,
  login,
  logout,
  normalizeBaseUrl,
  parseFriendInvitePayload,
  startFriendGame,
  toggleCommunityCommentLike,
  toggleCommunityLike,
  unfollowMobileUser,
  uploadCommunityImages,
  updateMobileProfile,
} from './src/api';
import { getConfiguredApiBaseUrl } from './src/env';
import { initializeMobileFirebaseTools } from './src/firebase';
import { clearSession, loadSession, saveSession, StoredSession } from './src/storage';
import { AuthUser, CommunityComment, CommunityPost, DashboardResponse, Friend, FriendInviteResponse, MobileProfile, PlayerGame } from './src/types';

type MainTab = '首頁' | '數據' | '掃碼' | '好友' | '我的';
type DataSection = '總覽' | '對戰記錄' | '進攻數據' | '球型表現';
type ProfileMode = 'profile' | 'picker' | 'albums' | 'compose' | 'editProfile' | 'avatarPicker';
type LocalPhoto = {
  id: string;
  uri: string;
  filename?: string;
  mimeType?: string;
  width?: number;
  height?: number;
};
type CompressedUploadPhoto = LocalPhoto & {
  uploadFilename: string;
  uploadMimeType: 'image/jpeg';
};
type LocalAlbumOption = {
  id: string;
  title: string;
  album: MediaLibrary.Album | null;
  count?: number;
  coverUri?: string;
};
type PhotoTransform = { x: number; y: number; scale: number };
type SavedPhotoTransform = PhotoTransform & { width?: number; height?: number; frame_width?: number };
type FeedMode = 'FOLLOWING' | 'RECOMMENDED';
type CaughtUpBannerItem = { type: 'caught_up_banner'; id: string };
type HomeFeedItem = CommunityPost | CaughtUpBannerItem;
type HomeProfileRoute = { userId: number; previewName?: string; previewAvatarUrl?: string; previewLevel?: string };
type AuthorProfileTarget = number | null | undefined | HomeProfileRoute;

const purple = '#4F46E5';
const ink = '#111827';
const muted = '#6B7280';
const line = '#E5E7EB';
const success = '#22C55E';
const danger = '#EF4444';
const warning = '#F59E0B';
const FEED_PAGE_SIZE = 10;
const CAUGHT_UP_BANNER_ID = 'caught-up-banner';
const POST_IMAGE_MAX_EDGE = 1600;
const POST_IMAGE_COMPRESS_QUALITY = 0.8;
const AVATAR_IMAGE_MAX_EDGE = 512;
const AVATAR_IMAGE_COMPRESS_QUALITY = 0.82;
const MOBILE_UPLOAD_TARGET_BYTES = 800 * 1024;
const iosSystemFontFamily = Platform.select({
  ios: 'System',
  web: '-apple-system, BlinkMacSystemFont, "PingFang TC", "Helvetica Neue", Arial, sans-serif',
});
const appTextFont: Pick<TextStyle, 'fontFamily'> = iosSystemFontFamily ? { fontFamily: iosSystemFontFamily } : {};

LogBox.ignoreAllLogs(true);

function mimeTypeForFilename(filename = ''): string {
  const normalized = filename.toLowerCase();
  if (normalized.endsWith('.png')) return 'image/png';
  if (normalized.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}

function jpegFilenameForPhoto(photo: LocalPhoto): string {
  const source = photo.filename || `${photo.id}.jpg`;
  const withoutExtension = source.replace(/\.[^.]+$/, '');
  return `${withoutExtension || photo.id}.jpg`;
}

function isNearPhotoListBottom(event: NativeSyntheticEvent<NativeScrollEvent>): boolean {
  const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
  return contentOffset.y + layoutMeasurement.height >= contentSize.height - 900;
}

function isCaughtUpBannerItem(item: HomeFeedItem): item is CaughtUpBannerItem {
  return 'type' in item && item.type === 'caught_up_banner';
}

function getPostMediaWidth(): number {
  return Platform.OS === 'web' ? 430 : Dimensions.get('window').width;
}

function getWidthFitImageSize(photo: LocalPhoto, frameWidth: number): { width: number; height: number } {
  const imageRatio = photo.width && photo.height ? photo.width / photo.height : 1;
  return { width: frameWidth, height: frameWidth / imageRatio };
}

function clampWidthFitTransform(photo: LocalPhoto, frameWidth: number, transform: PhotoTransform): PhotoTransform {
  const frameHeight = frameWidth * 1.25;
  const scale = Math.max(1, Math.min(3, transform.scale));
  const imageSize = getWidthFitImageSize(photo, frameWidth);
  const maxOffsetX = Math.max(0, (imageSize.width * scale - frameWidth) / 2);
  const scaledHeight = imageSize.height * scale;
  const maxOffsetY = scaledHeight > frameHeight ? (scaledHeight - frameHeight) / 2 : 0;
  return {
    x: Math.max(-maxOffsetX, Math.min(maxOffsetX, transform.x)),
    y: Math.max(-maxOffsetY, Math.min(maxOffsetY, transform.y)),
    scale,
  };
}

function scaleSavedTransformToFrame(transform: SavedPhotoTransform, frameWidth: number): PhotoTransform {
  const sourceFrameWidth = transform.frame_width && transform.frame_width > 0 ? transform.frame_width : frameWidth;
  const ratio = frameWidth / sourceFrameWidth;
  return {
    x: (transform.x || 0) * ratio,
    y: (transform.y || 0) * ratio,
    scale: transform.scale || 1,
  };
}

async function preparePhotoForPost(photo: LocalPhoto): Promise<LocalPhoto> {
  if (photo.width && photo.height && !photo.uri.startsWith('ph://')) return photo;
  try {
    const info = await MediaLibrary.getAssetInfoAsync(photo.id, { shouldDownloadFromNetwork: true });
    const sizedInfo = info as MediaLibrary.AssetInfo & { width?: number; height?: number };
    return {
      ...photo,
      uri: info.localUri || info.uri || photo.uri,
      width: photo.width || sizedInfo.width,
      height: photo.height || sizedInfo.height,
    };
  } catch {
    return photo;
  }
}

async function resolveUploadablePhotoUri(photo: LocalPhoto): Promise<string> {
  const uri = photo.uri.startsWith('ph://')
    ? (await MediaLibrary.getAssetInfoAsync(photo.id, { shouldDownloadFromNetwork: true })).localUri || photo.uri
    : photo.uri;
  if (!uri || uri.startsWith('ph://')) {
    throw new Error('無法取得可上傳的本機照片，請重新選擇照片。');
  }
  return uri;
}

async function compressPhotoForUpload(photo: LocalPhoto, maxEdge: number, quality: number): Promise<CompressedUploadPhoto> {
  const prepared = await preparePhotoForPost(photo);
  const sourceUri = await resolveUploadablePhotoUri(prepared);
  const width = prepared.width || 0;
  const height = prepared.height || 0;
  const longestEdge = Math.max(width, height);
  const actions: ImageManipulator.Action[] = [];
  if (longestEdge > maxEdge && width > 0 && height > 0) {
    actions.push({ resize: width >= height ? { width: maxEdge } : { height: maxEdge } });
  }
  const result = await ImageManipulator.manipulateAsync(sourceUri, actions, {
    compress: quality,
    format: ImageManipulator.SaveFormat.JPEG,
  });
  if (!result.uri) {
    throw new Error('照片壓縮失敗，請重新選擇照片。');
  }
  return {
    ...prepared,
    uri: result.uri,
    filename: jpegFilenameForPhoto(prepared),
    mimeType: 'image/jpeg',
    width: result.width || prepared.width,
    height: result.height || prepared.height,
    uploadFilename: jpegFilenameForPhoto(prepared),
    uploadMimeType: 'image/jpeg',
  };
}

function estimateBase64ByteLength(data: string): number {
  const normalized = data.replace(/^data:image\/[a-zA-Z0-9.+-]+;base64,/, '').replace(/\s/g, '');
  const padding = normalized.endsWith('==') ? 2 : normalized.endsWith('=') ? 1 : 0;
  return Math.max(0, Math.floor((normalized.length * 3) / 4) - padding);
}

function assertWithinMobileUploadTarget(data: string, targetBytes: number): void {
  const size = estimateBase64ByteLength(data);
  if (size > targetBytes) {
    const targetKb = Math.round(targetBytes / 1024);
    throw new Error(`測試階段單張圖片壓縮後需小於 ${targetKb}KB，請換較小圖片或降低解析度。`);
  }
}

function AvatarImage({ uri, imageStyle, iconSize }: { uri: string; imageStyle: StyleProp<ImageStyle>; iconSize: number }) {
  const [failedUri, setFailedUri] = useState('');
  useEffect(() => {
    setFailedUri('');
  }, [uri]);
  if (uri && uri !== failedUri) {
    return <Image source={{ uri }} style={imageStyle} resizeMode="cover" onError={() => setFailedUri(uri)} />;
  }
  return <User size={iconSize} color={muted} />;
}

export default function App() {
  const [tab, setTab] = useState<MainTab>('首頁');
  const [dataSection, setDataSection] = useState<DataSection>('總覽');
  const [baseUrl, setBaseUrl] = useState(() => getConfiguredApiBaseUrl());
  const [uploadTargetBytes, setUploadTargetBytes] = useState(MOBILE_UPLOAD_TARGET_BYTES);
  const [token, setToken] = useState('');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [profile, setProfile] = useState<MobileProfile | null>(null);
  const [myPosts, setMyPosts] = useState<CommunityPost[]>([]);
  const [homeProfileRoute, setHomeProfileRoute] = useState<HomeProfileRoute | null>(null);
  const [viewedProfileUserId, setViewedProfileUserId] = useState<number | null>(null);
  const [viewedProfile, setViewedProfile] = useState<MobileProfile | null>(null);
  const [viewedPosts, setViewedPosts] = useState<CommunityPost[]>([]);
  const [viewedProfileError, setViewedProfileError] = useState('');
  const [loadingViewedProfile, setLoadingViewedProfile] = useState(false);
  const [followUpdating, setFollowUpdating] = useState(false);
  const [feedItems, setFeedItems] = useState<HomeFeedItem[]>([]);
  const [currentMode, setCurrentMode] = useState<FeedMode>('FOLLOWING');
  const [followingOffset, setFollowingOffset] = useState(0);
  const [recommendedOffset, setRecommendedOffset] = useState(0);
  const [hasMoreFollowing, setHasMoreFollowing] = useState(true);
  const [hasMoreRecommended, setHasMoreRecommended] = useState(true);
  const [loadingFeed, setLoadingFeed] = useState(false);
  const [refreshingFeed, setRefreshingFeed] = useState(false);
  const [feedError, setFeedError] = useState('');
  const [profileError, setProfileError] = useState('');
  const [profileMode, setProfileMode] = useState<ProfileMode>('profile');
  const [albumReturnMode, setAlbumReturnMode] = useState<ProfileMode>('picker');
  const [albums, setAlbums] = useState<MediaLibrary.Album[]>([]);
  const [albumOptions, setAlbumOptions] = useState<LocalAlbumOption[]>([]);
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const [photoEndCursor, setPhotoEndCursor] = useState<string | undefined>(undefined);
  const [photoHasNextPage, setPhotoHasNextPage] = useState(false);
  const [photoLoadingMore, setPhotoLoadingMore] = useState(false);
  const [selectedPhotos, setSelectedPhotos] = useState<LocalPhoto[]>([]);
  const [previewPhoto, setPreviewPhoto] = useState<LocalPhoto | null>(null);
  const [activeAlbum, setActiveAlbum] = useState<MediaLibrary.Album | null>(null);
  const [mediaError, setMediaError] = useState('');
  const [composeText, setComposeText] = useState('');
  const [editingComposePhotoId, setEditingComposePhotoId] = useState('');
  const [composePhotoTransforms, setComposePhotoTransforms] = useState<Record<string, { x: number; y: number; scale: number }>>({});
  const [editDisplayName, setEditDisplayName] = useState('');
  const [editBio, setEditBio] = useState('');
  const [editAvatarUrl, setEditAvatarUrl] = useState('');
  const [avatarPhoto, setAvatarPhoto] = useState<LocalPhoto | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [invite, setInvite] = useState<FriendInviteResponse | null>(null);
  const [showInviteQr, setShowInviteQr] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [scanLocked, setScanLocked] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const photoLoadingMoreRef = useRef(false);
  const feedLoadingRef = useRef(false);
  const publicProfileRequestId = useRef(0);
  const seenPostIds = useRef<Set<number>>(new Set());
  const prefetchedAvatarUrls = useRef<Set<string>>(new Set());
  const prefetchedPostImageUrls = useRef<Set<string>>(new Set());

  const normalizedBaseUrl = useMemo(() => normalizeBaseUrl(baseUrl), [baseUrl]);
  const isSignedIn = Boolean(token && user);

  const prefetchAvatarUrls = (urls: Array<string | undefined>) => {
    urls.forEach((url) => {
      if (!url || url.startsWith('file://') || prefetchedAvatarUrls.current.has(url)) return;
      prefetchedAvatarUrls.current.add(url);
      Image.prefetch(url).catch(() => {
        prefetchedAvatarUrls.current.delete(url);
      });
    });
  };

  const prefetchPostImageUrls = (urls: Array<string | undefined>) => {
    urls.forEach((url) => {
      if (!url || url.startsWith('file://') || prefetchedPostImageUrls.current.has(url)) return;
      prefetchedPostImageUrls.current.add(url);
      Image.prefetch(url).catch(() => {
        prefetchedPostImageUrls.current.delete(url);
      });
    });
  };

  useEffect(() => {
    initializeMobileFirebaseTools().then((runtimeConfig) => {
      setUploadTargetBytes(runtimeConfig.uploadTargetBytes || MOBILE_UPLOAD_TARGET_BYTES);
      if (runtimeConfig.apiBaseUrl && !getConfiguredApiBaseUrl()) {
        setBaseUrl((current) => current || runtimeConfig.apiBaseUrl);
      }
    }).catch(() => {
      setUploadTargetBytes(MOBILE_UPLOAD_TARGET_BYTES);
    });
  }, []);

  useEffect(() => {
    loadSession().then((stored) => {
      const configuredBaseUrl = getConfiguredApiBaseUrl();
      if (!stored) {
        if (configuredBaseUrl) setBaseUrl(configuredBaseUrl);
        return;
      }
      const effectiveBaseUrl = configuredBaseUrl || stored.baseUrl;
      setBaseUrl(effectiveBaseUrl);
      setToken(stored.token);
      setUser(stored.user);
      if (effectiveBaseUrl !== stored.baseUrl) {
        void saveSession({ ...stored, baseUrl: effectiveBaseUrl });
      }
      void refreshAll({ ...stored, baseUrl: effectiveBaseUrl });
    });
  }, []);

  useEffect(() => {
    if (tab === '掃碼') return;
    setInvite(null);
    setShowInviteQr(false);
    if (tab === '\u9996\u9801') return;
    if (tab !== '我的') {
      setHomeProfileRoute(null);
      setViewedProfileUserId(null);
      setViewedProfile(null);
      setViewedPosts([]);
      setViewedProfileError('');
    }
  }, [tab]);

  useEffect(() => {
    prefetchAvatarUrls([profile?.avatar_url, ...myPosts.map((post) => post.author_avatar_url)]);
    prefetchPostImageUrls(myPosts.flatMap((post) => post.image_urls || []));
  }, [profile?.avatar_url, myPosts]);

  useEffect(() => {
    prefetchAvatarUrls([viewedProfile?.avatar_url, ...viewedPosts.map((post) => post.author_avatar_url)]);
    prefetchPostImageUrls(viewedPosts.flatMap((post) => post.image_urls || []));
  }, [viewedProfile?.avatar_url, viewedPosts]);

  useEffect(() => {
    const feedPosts = feedItems.filter((item): item is CommunityPost => !isCaughtUpBannerItem(item));
    prefetchAvatarUrls(feedPosts.map((post) => post.author_avatar_url));
    prefetchPostImageUrls(feedPosts.flatMap((post) => post.image_urls || []));
  }, [feedItems]);

  const takeUniqueFeedPosts = (posts: CommunityPost[]): CommunityPost[] => {
    const uniquePosts: CommunityPost[] = [];
    posts.forEach((post) => {
      if (seenPostIds.current.has(post.id)) return;
      seenPostIds.current.add(post.id);
      uniquePosts.push(post);
    });
    return uniquePosts;
  };

  const appendCaughtUpBanner = () => {
    setFeedItems((current) => {
      if (current.some((item) => isCaughtUpBannerItem(item))) return current;
      return [...current, { type: 'caught_up_banner', id: CAUGHT_UP_BANNER_ID }];
    });
  };

  const loadRecommendedFeedPage = async (
    activeBaseUrl = normalizedBaseUrl,
    activeToken = token,
    offset = recommendedOffset,
  ) => {
    const response = await getMobileTrendingFeed(
      activeBaseUrl,
      activeToken,
      FEED_PAGE_SIZE,
      offset,
      Array.from(seenPostIds.current),
    );
    const uniquePosts = takeUniqueFeedPosts(response.posts);
    if (uniquePosts.length) {
      setFeedItems((current) => [...current, ...uniquePosts]);
    }
    setRecommendedOffset(response.offset + response.limit);
    setHasMoreRecommended(response.hasMoreTrending);
  };

  const refreshHomeFeed = async (activeBaseUrl = normalizedBaseUrl, activeToken = token) => {
    if (!activeBaseUrl || !activeToken) return;
    if (feedLoadingRef.current) return;
    feedLoadingRef.current = true;
    setLoadingFeed(true);
    setRefreshingFeed(true);
    setFeedError('');
    try {
      seenPostIds.current = new Set();
      setCurrentMode('FOLLOWING');
      setFollowingOffset(0);
      setRecommendedOffset(0);
      setHasMoreFollowing(true);
      setHasMoreRecommended(true);
      const following = await getMobileFollowingFeed(activeBaseUrl, activeToken, FEED_PAGE_SIZE, 0);
      const followingPosts = takeUniqueFeedPosts(following.posts);
      const nextItems: HomeFeedItem[] = [...followingPosts];
      setFollowingOffset(following.offset + following.limit);
      setHasMoreFollowing(following.hasMoreFollowing);
      if (!following.hasMoreFollowing) {
        nextItems.push({ type: 'caught_up_banner', id: CAUGHT_UP_BANNER_ID });
        setCurrentMode('RECOMMENDED');
        const trending = await getMobileTrendingFeed(activeBaseUrl, activeToken, FEED_PAGE_SIZE, 0, Array.from(seenPostIds.current));
        const trendingPosts = takeUniqueFeedPosts(trending.posts);
        nextItems.push(...trendingPosts);
        setRecommendedOffset(trending.offset + trending.limit);
        setHasMoreRecommended(trending.hasMoreTrending);
      }
      setFeedItems(nextItems);
    } catch (error) {
      setFeedItems([]);
      setCurrentMode('RECOMMENDED');
      setHasMoreFollowing(false);
      setHasMoreRecommended(false);
      setFeedError(error instanceof Error ? error.message : '\u7121\u6cd5\u8f09\u5165\u9996\u9801\u52d5\u614b\u3002');
    } finally {
      feedLoadingRef.current = false;
      setLoadingFeed(false);
      setRefreshingFeed(false);
    }
  };

  const loadMoreHomeFeed = async () => {
    if (!token || !normalizedBaseUrl || feedLoadingRef.current || feedError) return;
    if (currentMode === 'RECOMMENDED' && !hasMoreRecommended) return;
    feedLoadingRef.current = true;
    setLoadingFeed(true);
    try {
      if (currentMode === 'FOLLOWING') {
        if (!hasMoreFollowing) {
          appendCaughtUpBanner();
          setCurrentMode('RECOMMENDED');
          await loadRecommendedFeedPage(normalizedBaseUrl, token, recommendedOffset);
          return;
        }
        const response = await getMobileFollowingFeed(normalizedBaseUrl, token, FEED_PAGE_SIZE, followingOffset);
        const uniquePosts = takeUniqueFeedPosts(response.posts);
        if (uniquePosts.length) {
          setFeedItems((current) => [...current, ...uniquePosts]);
        }
        setFollowingOffset(response.offset + response.limit);
        setHasMoreFollowing(response.hasMoreFollowing);
        if (!response.hasMoreFollowing) {
          appendCaughtUpBanner();
          setCurrentMode('RECOMMENDED');
          await loadRecommendedFeedPage(normalizedBaseUrl, token, recommendedOffset);
        }
        return;
      }
      await loadRecommendedFeedPage(normalizedBaseUrl, token, recommendedOffset);
    } catch (error) {
      setCurrentMode('RECOMMENDED');
      setHasMoreFollowing(false);
      setHasMoreRecommended(false);
      setFeedError(error instanceof Error ? error.message : '\u7121\u6cd5\u8f09\u5165\u66f4\u591a\u8cbc\u6587\u3002');
    } finally {
      feedLoadingRef.current = false;
      setLoadingFeed(false);
    }
  };

  const persistSession = async (sessionBaseUrl: string, sessionToken: string, sessionUser: AuthUser) => {
    const normalized = normalizeBaseUrl(sessionBaseUrl);
    setBaseUrl(normalized);
    setToken(sessionToken);
    setUser(sessionUser);
    await saveSession({ baseUrl: normalized, token: sessionToken, user: sessionUser });
  };

  const refreshAll = async (session?: StoredSession) => {
    const activeBaseUrl = normalizeBaseUrl(session?.baseUrl || normalizedBaseUrl);
    const activeToken = session?.token || token;
    if (!activeBaseUrl || !activeToken) return;
    setRefreshing(true);
    try {
      const [dashboardData, friendsData] = await Promise.all([
        getDashboard(activeBaseUrl, activeToken),
        getFriends(activeBaseUrl, activeToken),
      ]);
      setDashboard(dashboardData);
      setUser(dashboardData.user);
      setFriends(friendsData.friends);
      setProfileError('');
      try {
        const [profileData, postsData] = await Promise.all([
          getMobileProfile(activeBaseUrl, activeToken),
          getMyCommunityPosts(activeBaseUrl, activeToken),
        ]);
        setProfile(profileData);
        setMyPosts(postsData.posts);
      } catch (profileLoadError) {
        setProfile(null);
        setMyPosts([]);
        setProfileError(profileLoadError instanceof Error ? profileLoadError.message : '無法載入個人主頁。');
      }
      await refreshHomeFeed(activeBaseUrl, activeToken);
    } catch (error) {
      Alert.alert('同步失敗', error instanceof Error ? error.message : '無法連線到後端。');
    } finally {
      setRefreshing(false);
    }
  };

  const handleLogin = async () => {
    setLoading(true);
    try {
      const activeBaseUrl = normalizeBaseUrl(normalizedBaseUrl || getConfiguredApiBaseUrl());
      if (activeBaseUrl && activeBaseUrl !== baseUrl) {
        setBaseUrl(activeBaseUrl);
      }
      const response = await login(activeBaseUrl, username.trim(), password);
      await persistSession(activeBaseUrl, response.token, response.user);
      setPassword('');
      await refreshAll({ baseUrl: activeBaseUrl, token: response.token, user: response.user });
    } catch (error) {
      Alert.alert('登入失敗', error instanceof Error ? error.message : '請確認後端位址可連線。');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      if (token && normalizedBaseUrl) await logout(normalizedBaseUrl, token);
    } catch {
      // 後端離線時仍清除本機 session。
    }
    setToken('');
    setUser(null);
    setDashboard(null);
    setFriends([]);
    setProfile(null);
    setMyPosts([]);
    setViewedProfileUserId(null);
    setViewedProfile(null);
    setViewedPosts([]);
    setViewedProfileError('');
    setFeedItems([]);
    setCurrentMode('FOLLOWING');
    setFollowingOffset(0);
    setRecommendedOffset(0);
    setHasMoreFollowing(true);
    setHasMoreRecommended(true);
    seenPostIds.current = new Set();
    setProfileError('');
    setProfileMode('profile');
    setAlbumReturnMode('picker');
    setSelectedPhotos([]);
    setPreviewPhoto(null);
    setAvatarPhoto(null);
    setEditDisplayName('');
    setEditBio('');
    setEditAvatarUrl('');
    setComposeText('');
    setInvite(null);
    setShowInviteQr(false);
    await clearSession();
  };

  const handleCreateInvite = async () => {
    if (!token) return;
    setLoading(true);
    try {
      setInvite(await createFriendInvite(normalizedBaseUrl, token));
      setShowInviteQr(true);
    } catch (error) {
      Alert.alert('QR 產生失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setLoading(false);
    }
  };

  const handleScan = async (payload: string) => {
    if (!token || scanLocked) return;
    setScanLocked(true);
    try {
      const parsed = parseFriendInvitePayload(payload);
      const inviteBaseUrl = normalizeBaseUrl(parsed.baseUrl || normalizedBaseUrl);
      const result = await acceptFriendInvite(inviteBaseUrl, token, payload);
      if (user) await persistSession(inviteBaseUrl, token, user);
      Alert.alert('已加入好友', `${result.friend.username} 已加入好友列表。`);
      await refreshAll({ baseUrl: inviteBaseUrl, token, user: user as AuthUser });
      setTab('好友');
    } catch (error) {
      Alert.alert('掃描失敗', error instanceof Error ? error.message : '這不是有效的好友 QR。');
    } finally {
      setTimeout(() => setScanLocked(false), 1200);
    }
  };

  const handleStartGame = async (friend: Friend) => {
    if (!token) return;
    setLoading(true);
    try {
      await startFriendGame(normalizedBaseUrl, token, friend.id);
      Alert.alert('對戰已建立', `已建立 ${user?.username} vs ${friend.username} 的九號球對戰。`);
      await refreshAll();
    } catch (error) {
      Alert.alert('建立對戰失敗', error instanceof Error ? error.message : '請確認桌面端後端狀態。');
    } finally {
      setLoading(false);
    }
  };

  const refreshProfileContent = async (activeBaseUrl = normalizedBaseUrl, activeToken = token) => {
    if (!activeBaseUrl || !activeToken) return;
    const [profileData, postsData] = await Promise.all([
      getMobileProfile(activeBaseUrl, activeToken),
      getMyCommunityPosts(activeBaseUrl, activeToken),
    ]);
    setProfile(profileData);
    setMyPosts(postsData.posts);
    setProfileError('');
  };

  const openPublicProfile = async (targetUserId?: any) => {
    if (!targetUserId || !token || !normalizedBaseUrl) return;
    const route = typeof targetUserId === 'number' ? { userId: targetUserId } : targetUserId;
    const nextUserId = typeof targetUserId === 'number' ? targetUserId : route?.userId;
    if (!nextUserId) return;
    const requestId = publicProfileRequestId.current + 1;
    publicProfileRequestId.current = requestId;
    setHomeProfileRoute(route);
    setViewedProfileUserId(nextUserId);
    setViewedProfileError('');
    setTab('\u9996\u9801');
    setProfileMode('profile');
    if (user?.id === nextUserId) {
      setViewedProfile(profile);
      setViewedPosts(myPosts);
      setLoadingViewedProfile(false);
      void refreshProfileContent();
      return;
    }
    setViewedProfile(null);
    setViewedPosts([]);
    setLoadingViewedProfile(true);
    try {
      const pageData = await getMobilePublicProfilePage(normalizedBaseUrl, token, nextUserId);
      if (publicProfileRequestId.current !== requestId) return;
      setViewedProfile(pageData.profile);
      setViewedPosts(pageData.posts);
    } catch (error: any) {
      if (publicProfileRequestId.current !== requestId) return;
      setViewedProfile(null);
      setViewedPosts([]);
      setViewedProfileError(error instanceof Error ? error.message : '\u8f09\u5165\u4f7f\u7528\u8005\u4e3b\u9801\u5931\u6557');
    } finally {
      if (publicProfileRequestId.current === requestId) setLoadingViewedProfile(false);
    }
    return;
    setHomeProfileRoute({ userId: targetUserId });
    setViewedProfileUserId(targetUserId!);
    setViewedProfile(null);
    setViewedPosts([]);
    setLoadingViewedProfile(true);
    setViewedProfileError('');
    setTab('\u9996\u9801');
    setProfileMode('profile');
    try {
      const [profileData, postsData] = await Promise.all([
        getMobilePublicProfile(normalizedBaseUrl, token, targetUserId!),
        getMobilePublicProfilePosts(normalizedBaseUrl, token, targetUserId!),
      ]);
      setViewedProfile(profileData);
      setViewedPosts(postsData.posts);
    } catch (error: any) {
      setViewedProfile(null);
      setViewedPosts([]);
      setViewedProfileError(error instanceof Error ? error.message : '載入使用者主頁失敗');
    } finally {
      setLoadingViewedProfile(false);
    }
    return;
    if (user?.id === targetUserId) {
      setViewedProfileUserId(null);
      setViewedProfile(null);
      setViewedPosts([]);
      setViewedProfileError('');
      setTab('我的');
      setProfileMode('profile');
      return;
    }
    setViewedProfileUserId(targetUserId!);
    setViewedProfile(null);
    setViewedPosts([]);
    setLoadingViewedProfile(true);
    setViewedProfileError('');
    setTab('我的');
    setProfileMode('profile');
    try {
      const [profileData, postsData] = await Promise.all([
        getMobilePublicProfile(normalizedBaseUrl, token, targetUserId!),
        getMobilePublicProfilePosts(normalizedBaseUrl, token, targetUserId!),
      ]);
      setViewedProfile(profileData);
      setViewedPosts(postsData.posts);
    } catch (error: any) {
      setViewedProfile(null);
      setViewedPosts([]);
      setViewedProfileError(error instanceof Error ? error.message : '無法載入個人主頁。');
    } finally {
      setLoadingViewedProfile(false);
    }
  };

  const closePublicProfile = () => {
    publicProfileRequestId.current += 1;
    setHomeProfileRoute(null);
    setViewedProfileUserId(null);
    setViewedProfile(null);
    setViewedPosts([]);
    setViewedProfileError('');
  };

  const handleToggleFollowViewedProfile = async () => {
    if (!token || !normalizedBaseUrl || !viewedProfile || followUpdating) return;
    const targetUserId = viewedProfile.user.id;
    setFollowUpdating(true);
    try {
      if (viewedProfile.is_following) {
        await unfollowMobileUser(normalizedBaseUrl, token, targetUserId);
        setViewedProfile((current) => current ? {
          ...current,
          is_following: false,
          followers_count: Math.max(0, current.followers_count - 1),
        } : current);
      } else {
        await followMobileUser(normalizedBaseUrl, token, targetUserId);
        setViewedProfile((current) => current ? {
          ...current,
          is_following: true,
          followers_count: current.followers_count + 1,
        } : current);
      }
      await refreshProfileContent();
      await refreshHomeFeed();
    } catch (error) {
      Alert.alert('追蹤失敗', error instanceof Error ? error.message : '無法更新追蹤狀態。');
    } finally {
      setFollowUpdating(false);
    }
  };

  const resolveAssetPhoto = async (asset: MediaLibrary.Asset): Promise<LocalPhoto | null> => {
    try {
      const info = await MediaLibrary.getAssetInfoAsync(asset, { shouldDownloadFromNetwork: true });
      const uri = info.localUri || info.uri || asset.uri;
      if (!uri || uri.startsWith('ph://')) return null;
      return {
        id: asset.id,
        uri,
        filename: asset.filename,
        mimeType: mimeTypeForFilename(asset.filename),
        width: asset.width,
        height: asset.height,
      };
    } catch {
      if (!asset.uri || asset.uri.startsWith('ph://')) return null;
      return {
        id: asset.id,
        uri: asset.uri,
        filename: asset.filename,
        mimeType: mimeTypeForFilename(asset.filename),
        width: asset.width,
        height: asset.height,
      };
    }
  };

  const loadAlbumPhotos = async (album?: MediaLibrary.Album | null) => {
    setMediaError('');
    photoLoadingMoreRef.current = true;
    setPhotoLoadingMore(true);
    try {
      const result = await MediaLibrary.getAssetsAsync({
        album: album || undefined,
        first: 100,
        mediaType: ['photo'],
        sortBy: [MediaLibrary.SortBy.creationTime],
      });
      const resolvedPhotos = await Promise.all(result.assets.map(resolveAssetPhoto));
      const nextPhotos = resolvedPhotos.filter((photo): photo is LocalPhoto => Boolean(photo));
      setPhotos(nextPhotos);
      setPhotoEndCursor(result.endCursor);
      setPhotoHasNextPage(result.hasNextPage);
      setPreviewPhoto((current) => current && nextPhotos.some((photo) => photo.id === current.id) ? current : nextPhotos[0] || null);
    } finally {
      photoLoadingMoreRef.current = false;
      setPhotoLoadingMore(false);
    }
  };

  const loadMorePhotos = async () => {
    if (photoLoadingMoreRef.current || !photoHasNextPage) return;
    setMediaError('');
    photoLoadingMoreRef.current = true;
    setPhotoLoadingMore(true);
    try {
      const result = await MediaLibrary.getAssetsAsync({
        album: activeAlbum || undefined,
        after: photoEndCursor,
        first: 100,
        mediaType: ['photo'],
        sortBy: [MediaLibrary.SortBy.creationTime],
      });
      const resolvedPhotos = await Promise.all(result.assets.map(resolveAssetPhoto));
      const nextPhotos = resolvedPhotos.filter((photo): photo is LocalPhoto => Boolean(photo));
      setPhotos((current) => {
        const currentIds = new Set(current.map((photo) => photo.id));
        return [...current, ...nextPhotos.filter((photo) => !currentIds.has(photo.id))];
      });
      setPhotoEndCursor(result.endCursor);
      setPhotoHasNextPage(result.hasNextPage);
    } catch (error) {
      setMediaError(error instanceof Error ? error.message : '無法載入更多照片。');
    } finally {
      photoLoadingMoreRef.current = false;
      setPhotoLoadingMore(false);
    }
  };

  const buildAlbumOptions = async (albumList: MediaLibrary.Album[]) => {
    const recentAsset = await MediaLibrary.getAssetsAsync({
      first: 1,
      mediaType: ['photo'],
      sortBy: [MediaLibrary.SortBy.creationTime],
    });
    const recentCover = recentAsset.assets[0] ? await resolveAssetPhoto(recentAsset.assets[0]) : null;
    const options = await Promise.all(albumList.map(async (album) => {
      const coverAsset = await MediaLibrary.getAssetsAsync({
        album,
        first: 1,
        mediaType: ['photo'],
        sortBy: [MediaLibrary.SortBy.creationTime],
      });
      const cover = coverAsset.assets[0] ? await resolveAssetPhoto(coverAsset.assets[0]) : null;
      return {
        id: album.id,
        title: album.title,
        album,
        count: album.assetCount,
        coverUri: cover?.uri,
      };
    }));
    setAlbumOptions([
      { id: 'all', title: '所有照片', album: null, count: recentAsset.totalCount, coverUri: recentCover?.uri },
      ...options,
    ]);
  };

  const openPhotoPicker = async () => {
    setProfileMode('picker');
    setAlbumReturnMode('picker');
    setSelectedPhotos([]);
    setPreviewPhoto(null);
    setComposeText('');
    setActiveAlbum(null);
    setMediaError('');
    try {
      const permission = await MediaLibrary.requestPermissionsAsync();
      if (!permission.granted) {
        setPhotos([]);
        setPhotoEndCursor(undefined);
        setPhotoHasNextPage(false);
        photoLoadingMoreRef.current = false;
        setPhotoLoadingMore(false);
        setMediaError('尚未允許相簿權限。');
        return;
      }
      const albumList = await MediaLibrary.getAlbumsAsync({ includeSmartAlbums: true });
      setAlbums(albumList);
      await buildAlbumOptions(albumList);
      await loadAlbumPhotos(null);
    } catch (error) {
      setPhotos([]);
      setPhotoEndCursor(undefined);
      setPhotoHasNextPage(false);
      photoLoadingMoreRef.current = false;
      setPhotoLoadingMore(false);
      setMediaError(error instanceof Error ? error.message : '無法讀取相簿。');
    }
  };

  const openEditProfile = () => {
    setEditDisplayName(profile?.display_name?.trim() || user?.username || '');
    setEditBio(profile?.bio?.trim() || '');
    setEditAvatarUrl(profile?.avatar_url || '');
    setAvatarPhoto(null);
    setProfileMode('editProfile');
  };

  const openAvatarPicker = async () => {
    setProfileMode('avatarPicker');
    setAlbumReturnMode('avatarPicker');
    setSelectedPhotos([]);
    setPreviewPhoto(null);
    setActiveAlbum(null);
    setMediaError('');
    try {
      const permission = await MediaLibrary.requestPermissionsAsync();
      if (!permission.granted) {
        setPhotos([]);
        setMediaError('需要相簿權限才能更換頭像。');
        return;
      }
      const albumList = await MediaLibrary.getAlbumsAsync({ includeSmartAlbums: true });
      setAlbums(albumList);
      await buildAlbumOptions(albumList);
      await loadAlbumPhotos(null);
    } catch (error) {
      setPhotos([]);
      setMediaError(error instanceof Error ? error.message : '無法讀取相簿。');
    }
  };

  const saveMobileProfile = async () => {
    if (!token || savingProfile) return;
    setSavingProfile(true);
    try {
      let avatarUrl = editAvatarUrl;
      if (avatarPhoto) {
        const compressedAvatar = await compressPhotoForUpload(avatarPhoto, AVATAR_IMAGE_MAX_EDGE, AVATAR_IMAGE_COMPRESS_QUALITY);
        const data = await FileSystem.readAsStringAsync(compressedAvatar.uri, { encoding: FileSystem.EncodingType.Base64 });
        assertWithinMobileUploadTarget(data, uploadTargetBytes);
        const uploaded = await uploadCommunityImages(normalizedBaseUrl, token, [{
          filename: compressedAvatar.uploadFilename,
          mime_type: compressedAvatar.uploadMimeType,
          data,
        }], 'avatar');
        avatarUrl = uploaded.image_urls[0] || '';
      }
      const updatedProfile = await updateMobileProfile(normalizedBaseUrl, token, {
        display_name: editDisplayName,
        bio: editBio,
        avatar_url: avatarUrl,
      });
      setProfile(updatedProfile);
      setEditAvatarUrl(updatedProfile.avatar_url || '');
      setAvatarPhoto(null);
      setProfileMode('profile');
      await refreshProfileContent();
    } catch (error) {
      Alert.alert('儲存失敗', error instanceof Error ? error.message : '無法儲存個人檔案');
    } finally {
      setSavingProfile(false);
    }
  };

  const selectAlbum = async (album: MediaLibrary.Album | null) => {
    setActiveAlbum(album);
    setSelectedPhotos([]);
    setPreviewPhoto(null);
    await loadAlbumPhotos(album);
    setProfileMode(albumReturnMode === 'avatarPicker' ? 'avatarPicker' : 'picker');
  };

  const cycleAlbum = () => {
    setAlbumReturnMode(profileMode === 'avatarPicker' ? 'avatarPicker' : 'picker');
    setProfileMode('albums');
  };

  const togglePhoto = (photo: LocalPhoto) => {
    setPreviewPhoto(photo);
    setSelectedPhotos((current) => {
      if (current.some((item) => item.id === photo.id)) {
        return current.filter((item) => item.id !== photo.id);
      }
      return current.length >= 3 ? current : [...current, photo];
    });
  };

  const sharePost = async () => {
    if (!token || publishing) return;
    const body = composeText.trim();
    if (!body && !selectedPhotos.length) {
      Alert.alert('無法分享', '請輸入文字或選擇照片。');
      return;
    }
    setPublishing(true);
    try {
      const postPhotos = await Promise.all(selectedPhotos.map((photo) => compressPhotoForUpload(photo, POST_IMAGE_MAX_EDGE, POST_IMAGE_COMPRESS_QUALITY)));
      const images = await Promise.all(postPhotos.map(async (photo) => {
        const uri = photo.uri.startsWith('ph://')
          ? (await MediaLibrary.getAssetInfoAsync(photo.id, { shouldDownloadFromNetwork: true })).localUri || photo.uri
          : photo.uri;
        if (uri.startsWith('ph://')) {
          throw new Error('這張照片尚未下載到本機，請改選其他照片或先在相簿中下載。');
        }
        const data = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
        assertWithinMobileUploadTarget(data, uploadTargetBytes);
        return {
          filename: photo.uploadFilename,
          mime_type: photo.uploadMimeType,
          data,
        };
      }));
      const uploaded = images.length ? await uploadCommunityImages(normalizedBaseUrl, token, images, 'post') : { image_urls: [] };
      const mediaWidth = getPostMediaWidth();
      const imageTransforms = postPhotos.map((photo) => {
        const clamped = clampWidthFitTransform(photo, mediaWidth, composePhotoTransforms[photo.id] || { x: 0, y: 0, scale: 1 });
        return { ...clamped, width: photo.width || 0, height: photo.height || 0, frame_width: mediaWidth };
      });
      await createCommunityPost(normalizedBaseUrl, token, { body, image_urls: uploaded.image_urls, image_transforms: imageTransforms });
      setComposeText('');
      setSelectedPhotos([]);
      setPreviewPhoto(null);
      setComposePhotoTransforms({});
      setProfileMode('profile');
      await refreshProfileContent();
    } catch (error) {
      Alert.alert('分享失敗', error instanceof Error ? error.message : '無法建立貼文。');
    } finally {
      setPublishing(false);
    }
  };

  const handleDeletePost = (post: CommunityPost) => {
    if (!token) return;
    Alert.alert('刪除貼文', '確定要刪除嗎？', [
      { text: '取消', style: 'cancel' },
      {
        text: '刪除',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteCommunityPost(normalizedBaseUrl, token, post.id);
            await refreshProfileContent();
          } catch (error) {
            Alert.alert('刪除失敗', error instanceof Error ? error.message : '無法刪除貼文');
          }
        },
      },
    ]);
  };

  const updatePostInList = (nextPost: CommunityPost) => {
    setMyPosts((current) => current.map((post) => (post.id === nextPost.id ? nextPost : post)));
    setViewedPosts((current) => current.map((post) => (post.id === nextPost.id ? nextPost : post)));
    setFeedItems((current) => current.map((item) => {
      if (isCaughtUpBannerItem(item)) return item;
      return item.id === nextPost.id ? nextPost : item;
    }));
  };

  const handleTogglePostLike = async (post: CommunityPost) => {
    if (!token) return;
    try {
      updatePostInList(await toggleCommunityLike(normalizedBaseUrl, token, post.id));
    } catch (error) {
      Alert.alert('按讚失敗', error instanceof Error ? error.message : '無法更新貼文按讚。');
    }
  };

  const handleCreatePostComment = async (post: CommunityPost, body: string) => {
    if (!token) return;
    try {
      const response = await createCommunityComment(normalizedBaseUrl, token, post.id, body);
      prefetchAvatarUrls([response.comment.author_avatar_url || profile?.avatar_url]);
      updatePostInList(response.post);
      return response.comment;
    } catch (error) {
      Alert.alert('留言失敗', error instanceof Error ? error.message : '無法新增留言。');
      throw error;
    }
  };

  const handleLoadPostComments = async (post: CommunityPost) => {
    if (!token) return [];
    const response = await getCommunityComments(normalizedBaseUrl, token, post.id);
    prefetchAvatarUrls(response.comments.map((comment) => comment.author_avatar_url || (Number(comment.user_id) === user?.id ? profile?.avatar_url : '')));
    return response.comments;
  };

  const handleToggleCommentLike = async (comment: CommunityComment) => {
    if (!token) return comment;
    return toggleCommunityCommentLike(normalizedBaseUrl, token, comment.id);
  };

  const renderContent = () => {
    if (!isSignedIn) {
      return <LoginPage baseUrl={baseUrl} username={username} setUsername={setUsername} password={password} setPassword={setPassword} loading={loading} onLogin={handleLogin} />;
    }
    if (profileMode === 'albums') return <AlbumSelectionPage albums={albumOptions} activeAlbumId={activeAlbum?.id || 'all'} onClose={() => setProfileMode(albumReturnMode === 'avatarPicker' ? 'avatarPicker' : 'picker')} onSelect={(album) => void selectAlbum(album)} />;
    if (tab === '首頁') {
      return homeProfileRoute ? (
          <ProfilePage
            user={user}
            profile={(viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? profile : viewedProfile}
            dashboard={dashboard}
            posts={(viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? myPosts : viewedPosts}
            loading={(viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? false : loadingViewedProfile}
            error={viewedProfileError}
            isOwnProfile={viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId}
            previewName={homeProfileRoute.previewName}
            previewAvatarUrl={homeProfileRoute.previewAvatarUrl}
            previewLevel={homeProfileRoute.previewLevel}
            preferBackButton
            showOwnEditButton={false}
            followUpdating={followUpdating}
            onBack={closePublicProfile}
            onAddPost={openPhotoPicker}
            onRefresh={() => openPublicProfile(homeProfileRoute.userId)}
            onEditProfile={openEditProfile}
            onToggleFollow={handleToggleFollowViewedProfile}
            onAuthorPress={openPublicProfile}
            onDeletePost={handleDeletePost}
            onTogglePostLike={handleTogglePostLike}
            onCreatePostComment={handleCreatePostComment}
            onLoadPostComments={handleLoadPostComments}
            onToggleCommentLike={handleToggleCommentLike}
            onLogout={handleLogout}
          />
        ) : (
        <HomePage
          user={user}
          dashboard={dashboard}
          profile={profile}
          feedItems={feedItems}
          feedError={feedError}
          loadingFeed={loadingFeed}
          refreshing={refreshing || refreshingFeed}
          onRefresh={() => refreshAll()}
          onLoadMore={loadMoreHomeFeed}
          onAuthorPress={openPublicProfile}
          onDeletePost={handleDeletePost}
          onTogglePostLike={handleTogglePostLike}
          onCreatePostComment={handleCreatePostComment}
          onLoadPostComments={handleLoadPostComments}
          onToggleCommentLike={handleToggleCommentLike}
        />
      );
    }
    if (tab === '掃碼') return <ScanPage invite={invite} showInviteQr={showInviteQr} setShowInviteQr={setShowInviteQr} loading={loading} permissionGranted={Boolean(permission?.granted)} requestPermission={requestPermission} onCreateInvite={handleCreateInvite} onScan={handleScan} scanLocked={scanLocked} />;
    if (tab === '好友') return <FriendsPage friends={friends} loading={loading} onStartGame={handleStartGame} />;
    if (tab === '我的' && profileMode === 'picker') return <PhotoPickerPage photos={photos} selected={selectedPhotos} albumTitle={activeAlbum?.title || '所有照片'} albumsAvailable={albums.length > 0} error={mediaError} hasMorePhotos={photoHasNextPage} loadingMorePhotos={photoLoadingMore} onLoadMorePhotos={loadMorePhotos} onClose={() => setProfileMode('profile')} onNext={() => selectedPhotos.length && setProfileMode('compose')} onSelect={togglePhoto} onCycleAlbum={cycleAlbum} />;
    if (tab === '我的' && profileMode === 'avatarPicker') return <AvatarPickerPage photos={photos} preview={previewPhoto || avatarPhoto} albumTitle={activeAlbum?.title || '所有照片'} albumsAvailable={albums.length > 0} error={mediaError} hasMorePhotos={photoHasNextPage} loadingMorePhotos={photoLoadingMore} onLoadMorePhotos={loadMorePhotos} onClose={() => setProfileMode('editProfile')} onUse={(photo) => { setAvatarPhoto(photo); setPreviewPhoto(photo); setProfileMode('editProfile'); }} onSelect={(photo) => setPreviewPhoto(photo)} onCycleAlbum={cycleAlbum} />;
    if (tab === '我的' && profileMode === 'compose' && editingComposePhotoId) {
      const editingPhoto = selectedPhotos.find((photo) => photo.id === editingComposePhotoId) || selectedPhotos[0];
      if (!editingPhoto) {
        return <ComposePostPage photos={selectedPhotos} transforms={composePhotoTransforms} text={composeText} setText={setComposeText} loading={publishing} onClose={() => setProfileMode('picker')} onEditPhoto={setEditingComposePhotoId} onShare={sharePost} />;
      }
      return <ComposePhotoEditorPage photo={editingPhoto} transform={composePhotoTransforms[editingPhoto.id] || { x: 0, y: 0, scale: 1 }} onChangeTransform={(nextTransform) => setComposePhotoTransforms((current) => ({ ...current, [editingPhoto.id]: nextTransform }))} onDone={() => setEditingComposePhotoId('')} />;
    }
    if (tab === '我的' && profileMode === 'compose') return <ComposePostPage photos={selectedPhotos} transforms={composePhotoTransforms} text={composeText} setText={setComposeText} loading={publishing} onClose={() => setProfileMode('picker')} onEditPhoto={setEditingComposePhotoId} onShare={sharePost} />;
    if (tab === '我的' && profileMode === 'editProfile') return <EditProfilePage displayName={editDisplayName} bio={editBio} avatarUrl={avatarPhoto?.uri || editAvatarUrl} loading={savingProfile} onChangeName={setEditDisplayName} onChangeBio={setEditBio} onClose={() => setProfileMode('profile')} onSave={saveMobileProfile} onPickAvatar={openAvatarPicker} onRemoveAvatar={() => { setAvatarPhoto(null); setEditAvatarUrl(''); }} />;
    if (tab === '我的') {
      const isViewingOtherProfile = false;
      return (
        <ProfilePage
          user={user}
          profile={isViewingOtherProfile ? viewedProfile : profile}
          dashboard={dashboard}
          posts={isViewingOtherProfile ? viewedPosts : myPosts}
          loading={isViewingOtherProfile ? loadingViewedProfile : refreshing && !profile}
          error={isViewingOtherProfile ? viewedProfileError : profileError}
          isOwnProfile={!isViewingOtherProfile}
          followUpdating={followUpdating}
          onBack={isViewingOtherProfile ? closePublicProfile : undefined}
          onAddPost={openPhotoPicker}
          onRefresh={() => isViewingOtherProfile ? openPublicProfile(viewedProfileUserId) : refreshAll()}
          onEditProfile={openEditProfile}
          onToggleFollow={handleToggleFollowViewedProfile}
          onAuthorPress={openPublicProfile}
          onDeletePost={handleDeletePost}
          onTogglePostLike={handleTogglePostLike}
          onCreatePostComment={handleCreatePostComment}
          onLoadPostComments={handleLoadPostComments}
          onToggleCommentLike={handleToggleCommentLike}
          onLogout={handleLogout}
        />
      );
    }
    if (dataSection === '對戰記錄') return <MatchHistoryPage value={dataSection} onChange={setDataSection} dashboard={dashboard} />;
    if (dataSection === '進攻數據') return <UnsupportedDataPage title="進攻數據" value={dataSection} onChange={setDataSection} />;
    if (dataSection === '球型表現') return <UnsupportedDataPage title="球型表現" value={dataSection} onChange={setDataSection} />;
    return <DataOverviewPage value={dataSection} onChange={setDataSection} dashboard={dashboard} />;
  };

  const RootView = Platform.OS === 'web' ? View : SafeAreaView;
  const isCreatorMode = isSignedIn && tab === '我的' && (profileMode === 'picker' || profileMode === 'albums' || profileMode === 'compose' || profileMode === 'editProfile' || profileMode === 'avatarPicker');
  const isHomeScrollManaged = isSignedIn && tab === '首頁';
  const isProfileScrollManaged = isSignedIn && tab === '我的' && profileMode === 'profile';
  const shouldShowBottomNav = isSignedIn && !isCreatorMode;
  const contentNode = renderContent();

  return (
    <RootView style={[styles.shell, Platform.OS === 'web' && styles.shellWeb]}>
      <StatusBar barStyle="dark-content" />
      <View style={Platform.OS === 'web' ? styles.phoneWeb : styles.phone}>
        {isHomeScrollManaged ? (
          <View style={styles.homeContentFrame}>{contentNode}</View>
        ) : isProfileScrollManaged ? (
          <View style={styles.profileContentFrame}>{contentNode}</View>
        ) : isCreatorMode ? (
          <View style={styles.contentFrame}>{contentNode}</View>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
            {contentNode}
          </ScrollView>
        )}
        {shouldShowBottomNav ? <BottomNav active={tab} onChange={setTab} /> : null}
      </View>
    </RootView>
  );
}

function LoginPage(props: {
  baseUrl: string;
  username: string;
  setUsername: (value: string) => void;
  password: string;
  setPassword: (value: string) => void;
  loading: boolean;
  onLogin: () => void;
}) {
  return (
    <View style={styles.loginWrap}>
      <Text style={styles.brand}>CueVex</Text>
      <Text style={styles.loginTitle}>桌面端帳號登入</Text>
      <Text style={styles.loginCopy}>一鍵啟動時會自動帶入後端位址；資料會同步桌面端同一份紀錄。</Text>
      <View style={styles.autoEndpointCard}>
        <Text style={styles.autoEndpointLabel}>後端自動連線</Text>
        <Text style={styles.autoEndpointValue} numberOfLines={1}>{props.baseUrl || '啟動中'}</Text>
      </View>
      <Input label="帳號" value={props.username} onChangeText={props.setUsername} placeholder="Player001" />
      <Input label="密碼" value={props.password} onChangeText={props.setPassword} placeholder="Password123" secureTextEntry />
      <Pressable style={styles.primaryButton} onPress={props.onLogin} disabled={props.loading}>
        {props.loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>登入並同步</Text>}
      </Pressable>
    </View>
  );
}

function HomePage({
  user,
  dashboard,
  profile,
  feedItems,
  feedError,
  loadingFeed,
  refreshing,
  onRefresh,
  onLoadMore,
  onAuthorPress,
  onDeletePost,
  onTogglePostLike,
  onCreatePostComment,
  onLoadPostComments,
  onToggleCommentLike,
}: {
  user: AuthUser | null;
  dashboard: DashboardResponse | null;
  profile: MobileProfile | null;
  feedItems: HomeFeedItem[];
  feedError: string;
  loadingFeed: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  onLoadMore: () => void;
  onAuthorPress: (target?: AuthorProfileTarget) => void;
  onDeletePost: (post: CommunityPost) => void;
  onTogglePostLike: (post: CommunityPost) => void;
  onCreatePostComment: (post: CommunityPost, body: string) => Promise<CommunityComment | undefined>;
  onLoadPostComments: (post: CommunityPost) => Promise<CommunityComment[]>;
  onToggleCommentLike: (comment: CommunityComment) => Promise<CommunityComment>;
}) {
  const stats = dashboard?.stats;
  const score = Math.round((stats?.total_wins || 0) * 25 + (stats?.total_games || 0) * 5);
  const winRate = stats ? `${Math.round(stats.win_rate * 100)}%` : '--';
  const displayName = profile?.display_name?.trim() || user?.username || 'CueVex';
  const avatarUrl = profile?.avatar_url || '';
  const playerLevel = profile?.player_level || '新手玩家 I';
  return (
    <FlatList
      data={feedItems}
      keyExtractor={(item) => (isCaughtUpBannerItem(item) ? item.id : `post-${item.id}`)}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={styles.homeFeedContent}
      refreshing={refreshing}
      onRefresh={onRefresh}
      onEndReached={feedError ? undefined : onLoadMore}
      onEndReachedThreshold={0.45}
      ListHeaderComponent={(
        <View style={styles.homeHeaderStack}>
          <DualActionHeader
            title="CueVex"
            left={<Search size={22} color={ink} strokeWidth={2.4} />}
            right={refreshing ? <ActivityIndicator color={purple} /> : <Bell size={20} color={ink} strokeWidth={2.4} />}
          />
          <View style={styles.homeDivider} />
          <View style={styles.scoreCard}>
            <View style={{ flex: 1 }}>
              <Text style={styles.scoreLabel}>積分</Text>
              <Text style={styles.scoreValue}>{score}</Text>
              <Text style={styles.scoreMeta}>總場次 {stats?.total_games ?? 0}  勝場 {stats?.total_wins ?? 0}</Text>
            </View>
            <View style={styles.badgeCircle}><ShieldCheck size={36} color={success} /></View>
            <View style={styles.scoreProgressWrap}>
              <ProgressBar value={Math.min(100, stats ? stats.win_rate * 100 : 0)} />
              <View style={styles.spaceBetween}><Text style={styles.scoreFoot}>勝率來自桌面端紀錄</Text><Text style={styles.scoreFoot}>{winRate}</Text></View>
            </View>
          </View>
        </View>
      )}
      renderItem={({ item }) => {
        if (isCaughtUpBannerItem(item)) {
          return (
            <View style={styles.caughtUpBanner}>
              <Text style={styles.caughtUpTitle}>已看完最新動態</Text>
              <Text style={styles.caughtUpText}>接著看看全站熱門貼文</Text>
            </View>
          );
        }
        return (
          <PostCard
            post={item}
            fallbackAuthor={displayName}
            fallbackAvatarUrl={avatarUrl}
            currentUserId={user?.id || 0}
            currentPlayerLevel={playerLevel}
            onDelete={onDeletePost}
            onAuthorPress={onAuthorPress}
            onToggleLike={onTogglePostLike}
            onCreateComment={onCreatePostComment}
            onLoadComments={onLoadPostComments}
            onToggleCommentLike={onToggleCommentLike}
          />
        );
      }}
      ListFooterComponent={feedError ? (
        <View style={styles.feedErrorBox}>
          <Text style={styles.feedErrorTitle}>{'\u52d5\u614b\u8f09\u5165\u5931\u6557'}</Text>
          <Text style={styles.feedErrorText}>{feedError}</Text>
          <Text style={styles.feedErrorHint}>{'\u4e0b\u62c9\u91cd\u65b0\u6574\u7406'}</Text>
        </View>
      ) : loadingFeed ? <View style={styles.feedFooter}><ActivityIndicator color={purple} /></View> : null}
    />
  );
}

function DataOverviewPage({ value, onChange, dashboard }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null }) {
  const stats = dashboard?.stats;
  const cards = [
    ['總場次', `${stats?.total_games ?? 0}`, Math.min(100, (stats?.total_games ?? 0) * 4)],
    ['勝場', `${stats?.total_wins ?? 0}`, Math.min(100, (stats?.total_wins ?? 0) * 5)],
    ['勝率', stats ? `${Math.round(stats.win_rate * 100)}%` : '--', stats ? stats.win_rate * 100 : 0],
    ['練習次數', `${stats?.total_practice_sessions ?? 0}`, Math.min(100, (stats?.total_practice_sessions ?? 0) * 8)],
  ] as const;
  return (
    <View style={styles.stack}>
      <PageHeader title="數據" />
      <DataSelector value={value} onChange={onChange} />
      <View style={styles.spaceBetween}><Text style={styles.sectionTitle}>關鍵數據</Text><Text style={styles.linkText}>桌面端同步</Text></View>
      <View style={styles.twoGrid}>{cards.map(([label, cardValue, progress]) => <StatCard key={label} label={label} value={cardValue} progress={progress} />)}</View>
      <Card>
        <View style={styles.spaceBetween}><Text style={styles.sectionTitle}>表現趨勢</Text><Pill text="近期紀錄" /></View>
        <LineChartSvg height={180} values={(dashboard?.recent_games || []).map((_, index) => 42 + index * 7).slice(0, 8)} />
      </Card>
    </View>
  );
}

function MatchHistoryPage({ value, onChange, dashboard }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null }) {
  const [filter, setFilter] = useState<'全部' | '勝利' | '失敗'>('全部');
  const allMatches = dashboard?.recent_games || [];
  const filtered = allMatches.filter((match) => filter === '全部' || (filter === '勝利' ? match.result === 'win' : match.result === 'loss'));
  return (
    <View style={styles.stack}>
      <PageHeader title="數據" />
      <DataSelector value={value} onChange={onChange} />
      <View style={styles.segment}>
        {(['全部', '勝利', '失敗'] as const).map((item) => (
          <Pressable key={item} style={[styles.segmentItem, filter === item && styles.segmentActive]} onPress={() => setFilter(item)}>
            <Text style={[styles.segmentText, filter === item && styles.segmentTextActive]}>{item}</Text>
          </Pressable>
        ))}
      </View>
      <Card>{filtered.length ? filtered.map((match) => <MatchRow key={match.game_id} match={match} />) : <EmptyState text="沒有符合條件的對戰紀錄。" />}</Card>
    </View>
  );
}

function UnsupportedDataPage({ title, value, onChange }: { title: string; value: DataSection; onChange: (value: DataSection) => void }) {
  return (
    <View style={styles.stack}>
      <PageHeader title="數據" />
      <View style={styles.spaceBetween}><DataSelector value={value} onChange={onChange} /><Pill text="過去 30 天" /></View>
      <Card><Text style={styles.sectionTitle}>{title}</Text><EmptyState text="目前後端尚未提供此細項統計，因此不顯示 mock data。接上真實訓練統計 API 後會在此呈現。" /></Card>
    </View>
  );
}

function ScanPage(props: {
  invite: FriendInviteResponse | null;
  showInviteQr: boolean;
  setShowInviteQr: (value: boolean) => void;
  loading: boolean;
  permissionGranted: boolean;
  requestPermission: () => void;
  onCreateInvite: () => void;
  onScan: (payload: string) => void;
  scanLocked: boolean;
}) {
  const showInviteQr = props.showInviteQr && Boolean(props.invite);
  const primaryButtonText = showInviteQr ? '恢復掃碼框' : props.invite ? '顯示我的 QR Code' : props.permissionGranted ? '產生我的 QR Code' : '允許相機掃描';
  const handlePrimaryPress = () => {
    if (showInviteQr) {
      props.setShowInviteQr(false);
      return;
    }
    if (props.invite) {
      props.setShowInviteQr(true);
      return;
    }
    if (props.permissionGranted) {
      props.onCreateInvite();
      return;
    }
    props.requestPermission();
  };

  return (
    <View style={[styles.stack, styles.scanStack]}>
      <PageHeader title="掃碼" />
      <View style={styles.scanPanel}>
        <Text style={styles.sectionTitle}>{showInviteQr ? '我的 QR Code' : '掃描好友 QR Code'}</Text>
        <View style={styles.scanVisualSlot}>
          {showInviteQr && props.invite ? (
            <View style={styles.myQrBox}>
              <QRCode value={props.invite.qr_payload} size={226} />
              <Text style={styles.subText}>10 分鐘內有效</Text>
            </View>
          ) : props.permissionGranted ? (
              <View style={styles.cameraFrame}>
                <CameraView style={styles.camera} barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={(event) => !props.scanLocked && props.onScan(event.data)} />
              </View>
            ) : (
              <View style={styles.qrScanner}>
                <Corner style={{ left: 0, top: 0, borderLeftWidth: 4, borderTopWidth: 4 }} />
                <Corner style={{ right: 0, top: 0, borderRightWidth: 4, borderTopWidth: 4 }} />
                <Corner style={{ left: 0, bottom: 0, borderLeftWidth: 4, borderBottomWidth: 4 }} />
                <Corner style={{ right: 0, bottom: 0, borderRightWidth: 4, borderBottomWidth: 4 }} />
                <QrCode size={84} color={ink} />
              </View>
            )}
        </View>
        <Pressable style={styles.primaryButton} onPress={handlePrimaryPress} disabled={props.loading}>
          {showInviteQr || props.permissionGranted || props.invite ? <Grid3X3 size={17} color="#fff" /> : <Keyboard size={17} color="#fff" />}
          <Text style={styles.primaryButtonText}>{primaryButtonText}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function FriendsPage({ friends, loading, onStartGame }: { friends: Friend[]; loading: boolean; onStartGame: (friend: Friend) => void }) {
  return (
    <View style={styles.stack}>
      <PageHeader title="好友" action={<UserPlus size={20} color={ink} />} />
      <View style={styles.searchBox}><Search size={17} color={muted} /><Text style={styles.searchPlaceholder}>搜尋好友</Text></View>
      <Card>{friends.length ? friends.map((friend) => <FriendRow key={friend.id} friend={friend} loading={loading} onStartGame={onStartGame} />) : <EmptyState text="尚未加入好友，請到掃碼頁掃描好友 QR。" />}</Card>
    </View>
  );
}

function ProfilePage({
  user,
  profile,
  dashboard,
  posts,
  loading,
  error,
  isOwnProfile = true,
  previewName = '',
  previewAvatarUrl = '',
  previewLevel = '',
  preferBackButton = false,
  showOwnEditButton = true,
  followUpdating = false,
  onBack,
  onAddPost,
  onRefresh,
  onEditProfile,
  onToggleFollow,
  onAuthorPress,
  onDeletePost,
  onTogglePostLike,
  onCreatePostComment,
  onLoadPostComments,
  onToggleCommentLike,
  onLogout,
}: {
  user: AuthUser | null;
  profile: MobileProfile | null;
  dashboard: DashboardResponse | null;
  posts: CommunityPost[];
  loading: boolean;
  error: string;
  isOwnProfile?: boolean;
  previewName?: string;
  previewAvatarUrl?: string;
  previewLevel?: string;
  preferBackButton?: boolean;
  showOwnEditButton?: boolean;
  followUpdating?: boolean;
  onBack?: () => void;
  onAddPost: () => void;
  onRefresh: () => void;
  onEditProfile: () => void;
  onToggleFollow?: () => void;
  onAuthorPress?: (target?: AuthorProfileTarget) => void;
  onDeletePost: (post: CommunityPost) => void;
  onTogglePostLike: (post: CommunityPost) => void;
  onCreatePostComment: (post: CommunityPost, body: string) => Promise<CommunityComment | undefined>;
  onLoadPostComments: (post: CommunityPost) => Promise<CommunityComment[]>;
  onToggleCommentLike: (comment: CommunityComment) => Promise<CommunityComment>;
  onLogout: () => void;
}) {
  const [profileTab, setProfileTab] = useState<'posts' | 'stats'>('posts');
  const displayName = profile?.display_name?.trim() || (isOwnProfile ? user?.username : '') || (isOwnProfile ? '尚未設定名稱' : '載入中');
  const playerLevel = profile?.player_level || '新手玩家 I';
  const bio = profile?.bio?.trim() || '';
  const avatarUrl = profile?.avatar_url || '';
  const resolvedDisplayName = profile?.display_name?.trim() || previewName.trim() || displayName;
  const resolvedPlayerLevel = profile?.player_level || previewLevel || playerLevel;
  const resolvedAvatarUrl = profile?.avatar_url || previewAvatarUrl || avatarUrl;
  const followers = profile?.followers_count ?? 0;
  const following = profile?.following_count ?? 0;
  const postCount = profile?.post_count ?? posts.length;
  const stats = dashboard?.stats;

  return (
    <ScrollView
      showsVerticalScrollIndicator={false}
      stickyHeaderIndices={[2]}
      style={styles.profileFlatPage}
      contentContainerStyle={styles.profileScrollContent}
    >
      <DualActionHeader
        title={resolvedDisplayName}
        left={!preferBackButton && isOwnProfile ? <Plus size={22} color={ink} /> : <X size={22} color={ink} />}
        right={isOwnProfile && showOwnEditButton ? (loading ? <ActivityIndicator color={purple} /> : <Settings size={20} color={ink} />) : null}
        onLeft={!preferBackButton && isOwnProfile ? onAddPost : onBack}
      />
      <View style={styles.profileFlatSection}>
        <View style={styles.profileHeroRow}>
          <View style={styles.profileAvatar}><AvatarImage uri={resolvedAvatarUrl} imageStyle={styles.profileAvatarImage} iconSize={38} /></View>
          <View style={styles.profileHeroContent}>
            <Text style={styles.profileLevel}>{resolvedPlayerLevel}</Text>
            <View style={styles.profileStatsRow}>
              <ProfileStat label="貼文數" value={postCount} />
              <ProfileStat label="追蹤者" value={followers} />
              <ProfileStat label="追蹤中" value={following} />
            </View>
          </View>
          <Pressable style={styles.iconButton} onPress={onRefresh}>
            <Bell size={18} color={muted} />
          </Pressable>
        </View>
        {bio ? <Text style={styles.profileBio}>{bio}</Text> : null}
        {(!isOwnProfile || showOwnEditButton) ? <Pressable
          style={[styles.editProfileButton, !isOwnProfile && profile?.is_following && styles.followingProfileButton]}
          onPress={isOwnProfile ? onEditProfile : onToggleFollow}
          disabled={!isOwnProfile && followUpdating}
        >
          {followUpdating ? (
            <ActivityIndicator color={isOwnProfile || !profile?.is_following ? ink : purple} />
          ) : (
            <Text style={[styles.editProfileText, !isOwnProfile && profile?.is_following && styles.followingProfileText]}>
              {isOwnProfile ? '編輯個人檔案' : profile?.is_following ? '已追蹤' : '追蹤'}
            </Text>
          )}
        </Pressable> : null}
      </View>
      <View style={styles.profileStickyTabs}>
        <View style={styles.profileModeTabs}>
          <Pressable style={styles.profileModeTab} onPress={() => setProfileTab('posts')}>
            <Grid3X3 size={21} color={profileTab === 'posts' ? purple : muted} strokeWidth={profileTab === 'posts' ? 2.8 : 2.2} />
          </Pressable>
          <Pressable style={styles.profileModeTab} onPress={() => setProfileTab('stats')}>
            <BarChart3 size={22} color={profileTab === 'stats' ? purple : muted} strokeWidth={profileTab === 'stats' ? 2.8 : 2.2} />
          </Pressable>
        </View>
        <View style={styles.profileContentDivider} />
      </View>
      {error ? <FlatMessage text={error} /> : null}
      {!error && loading && profileTab === 'posts' ? <View style={styles.flatMessage}><ActivityIndicator color={purple} /></View> : null}
      {!error && !loading && profileTab === 'posts' && posts.length === 0 ? <FlatMessage text="尚無貼文" /> : null}
      {!error && !loading && profileTab === 'posts' && posts.map((post) => (
        <PostCard key={post.id} post={post} fallbackAuthor={resolvedDisplayName} fallbackAvatarUrl={resolvedAvatarUrl} currentUserId={user?.id || 0} currentPlayerLevel={resolvedPlayerLevel} onDelete={onDeletePost} onAuthorPress={onAuthorPress} onToggleLike={onTogglePostLike} onCreateComment={onCreatePostComment} onLoadComments={onLoadPostComments} onToggleCommentLike={onToggleCommentLike} />
      ))}
      {!error && profileTab === 'stats' ? (
        <View style={styles.profileStatsPanel}>
          <ProfileDataRow label="總場次" value={stats?.total_games ?? 0} />
          <ProfileDataRow label="勝場" value={stats?.total_wins ?? 0} />
          <ProfileDataRow label="勝率" value={`${Math.round((stats?.win_rate ?? 0) * 100)}%`} />
          <ProfileDataRow label="練習次數" value={stats?.total_practice_sessions ?? 0} />
        </View>
      ) : null}
      <View style={styles.flatLogout}>
        <SettingsRow icon={<LogOut size={18} color={danger} />} label="登出" danger onPress={onLogout} />
      </View>
    </ScrollView>
  );
}

function DualActionHeader({ title, left, right, onLeft, onRight }: { title: string; left?: React.ReactNode; right?: React.ReactNode; onLeft?: () => void; onRight?: () => void }) {
  return (
    <View style={styles.pageHeader}>
      <Pressable style={styles.headerLeftAction} onPress={onLeft}>{left}</Pressable>
      <Text style={styles.pageTitle} numberOfLines={1}>{title}</Text>
      <Pressable style={styles.headerAction} onPress={onRight}>{right}</Pressable>
    </View>
  );
}

function FlatMessage({ text }: { text: string }) {
  return <View style={styles.flatMessage}><Text style={styles.emptyText}>{text}</Text></View>;
}

function ProfileStat({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.profileStatItem}>
      <Text style={styles.profileStatValue}>{value}</Text>
      <Text style={styles.profileStatLabel}>{label}</Text>
    </View>
  );
}

function ProfileDataRow({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.profileDataRow}>
      <Text style={styles.profileDataLabel}>{label}</Text>
      <Text style={styles.profileDataValue}>{value}</Text>
    </View>
  );
}

function EditProfilePage({
  displayName,
  bio,
  avatarUrl,
  loading,
  onChangeName,
  onChangeBio,
  onClose,
  onSave,
  onPickAvatar,
  onRemoveAvatar,
}: {
  displayName: string;
  bio: string;
  avatarUrl: string;
  loading: boolean;
  onChangeName: (value: string) => void;
  onChangeBio: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
  onPickAvatar: () => void;
  onRemoveAvatar: () => void;
}) {
  const [showAvatarMenu, setShowAvatarMenu] = useState(false);
  return (
    <View style={styles.editProfilePage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onClose}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>編輯個人檔案</Text>
        <Pressable onPress={onSave} disabled={loading}>
          {loading ? <ActivityIndicator color={purple} /> : <Text style={styles.nextText}>完成</Text>}
        </Pressable>
      </View>
      <View style={styles.editAvatarBlock}>
        <View style={styles.editAvatar}><AvatarImage uri={avatarUrl} imageStyle={styles.editAvatarImage} iconSize={42} /></View>
        <Pressable onPress={() => setShowAvatarMenu(true)}><Text style={styles.changeAvatarText}>更換頭像</Text></Pressable>
      </View>
      <View style={styles.editFieldRow}>
        <Text style={styles.editFieldLabel}>使用者名稱</Text>
        <TextInput style={styles.editFieldInput} value={displayName} onChangeText={onChangeName} placeholder="使用者名稱" placeholderTextColor="#9CA3AF" />
      </View>
      <View style={styles.editFieldRow}>
        <Text style={styles.editFieldLabel}>個人簡介</Text>
        <TextInput style={[styles.editFieldInput, styles.editBioInput]} value={bio} onChangeText={onChangeBio} placeholder="介紹一下自己" placeholderTextColor="#9CA3AF" multiline />
      </View>
      {showAvatarMenu ? (
        <View style={styles.avatarMenuOverlay}>
          <Pressable style={styles.avatarMenuBackdrop} onPress={() => setShowAvatarMenu(false)} />
          <View style={styles.avatarMenuSheet}>
            <Pressable style={styles.avatarMenuItem} onPress={() => { setShowAvatarMenu(false); onPickAvatar(); }}>
              <Text style={styles.avatarMenuText}>從相簿中選擇</Text>
            </Pressable>
            <Pressable style={styles.avatarMenuItem} onPress={() => { setShowAvatarMenu(false); onRemoveAvatar(); }}>
              <Text style={styles.avatarMenuDanger}>移除頭像</Text>
            </Pressable>
            <Pressable style={styles.avatarMenuCancel} onPress={() => setShowAvatarMenu(false)}>
              <Text style={styles.avatarMenuText}>取消</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}

function AvatarPickerPage({
  photos,
  preview,
  albumTitle,
  albumsAvailable,
  error,
  hasMorePhotos,
  loadingMorePhotos,
  onLoadMorePhotos,
  onClose,
  onUse,
  onSelect,
  onCycleAlbum,
}: {
  photos: LocalPhoto[];
  preview?: LocalPhoto | null;
  albumTitle: string;
  albumsAvailable: boolean;
  error: string;
  hasMorePhotos: boolean;
  loadingMorePhotos: boolean;
  onLoadMorePhotos: () => void;
  onClose: () => void;
  onUse: (photo: LocalPhoto) => void;
  onSelect: (photo: LocalPhoto) => void;
  onCycleAlbum: () => void;
}) {
  const scrollRef = useRef<ScrollView | null>(null);
  const avatarPreviewAnim = useRef(new Animated.Value(1)).current;
  const [showAvatarPreview, setShowAvatarPreview] = useState(true);
  const topArmedForPreview = useRef(false);
  const avatarListScrollY = useRef(0);
  const [avatarGridWidth, setAvatarGridWidth] = useState(0);
  const [avatarScrollEnabled, setAvatarScrollEnabled] = useState(true);
  const avatarPanX = useRef(new Animated.Value(0)).current;
  const avatarPanY = useRef(new Animated.Value(0)).current;
  const avatarScale = useRef(new Animated.Value(1)).current;
  const avatarTransform = useRef({ x: 0, y: 0, scale: 1 });
  const touchStart = useRef({
    x: 0,
    y: 0,
    offsetX: 0,
    offsetY: 0,
    distance: 0,
    scale: 1,
  });
  const activePreview = preview || photos[0] || null;
  const previewSize = Platform.OS === 'web' ? 430 : Dimensions.get('window').width;
  const imageRatio = activePreview?.width && activePreview?.height ? activePreview.width / activePreview.height : 1;
  const baseImageSize = imageRatio >= 1
    ? { width: previewSize * imageRatio, height: previewSize }
    : { width: previewSize, height: previewSize / imageRatio };
  const avatarTileWidth = avatarGridWidth ? avatarGridWidth / 3 : `${100 / 3}%`;
  const circleSize = previewSize;
  const circleLeft = (previewSize - circleSize) / 2;
  const circleTop = (previewSize - circleSize) / 2;
  const circlePath = `M0 0H${previewSize}V${previewSize}H0Z M${circleLeft + circleSize / 2} ${circleTop} A${circleSize / 2} ${circleSize / 2} 0 1 0 ${circleLeft + circleSize / 2} ${circleTop + circleSize} A${circleSize / 2} ${circleSize / 2} 0 1 0 ${circleLeft + circleSize / 2} ${circleTop}Z`;
  const resetAvatarTransform = () => {
    avatarTransform.current = { x: 0, y: 0, scale: 1 };
    avatarPanX.setValue(0);
    avatarPanY.setValue(0);
    avatarScale.setValue(1);
  };
  const clampAvatarOffset = (nextOffset: { x: number; y: number }, nextScale = avatarTransform.current.scale) => {
    const maxOffsetX = Math.max(0, (baseImageSize.width * nextScale - circleSize) / 2);
    const maxOffsetY = Math.max(0, (baseImageSize.height * nextScale - circleSize) / 2);
    return {
      x: Math.max(-maxOffsetX, Math.min(maxOffsetX, nextOffset.x)),
      y: Math.max(-maxOffsetY, Math.min(maxOffsetY, nextOffset.y)),
    };
  };
  const distanceBetweenTouches = (touches: Array<{ pageX: number; pageY: number }>) => {
    if (touches.length < 2) return 0;
    const dx = touches[0].pageX - touches[1].pageX;
    const dy = touches[0].pageY - touches[1].pageY;
    return Math.sqrt(dx * dx + dy * dy);
  };
  const handleAvatarSelect = (photo: LocalPhoto) => {
    resetAvatarTransform();
    setAvatarPreviewVisible(true);
    onSelect(photo);
  };
  const setAvatarPreviewVisible = (visible: boolean) => {
    setShowAvatarPreview(visible);
    Animated.timing(avatarPreviewAnim, {
      toValue: visible ? 1 : 0,
      duration: 220,
      useNativeDriver: false,
    }).start();
  };
  const finishAvatarGesture = () => {
    const nextScale = Math.max(1, Math.min(3, avatarTransform.current.scale));
    const nextOffset = clampAvatarOffset({ x: avatarTransform.current.x, y: avatarTransform.current.y }, nextScale);
    avatarTransform.current = { ...nextOffset, scale: nextScale };
    Animated.parallel([
      Animated.spring(avatarScale, { toValue: nextScale, useNativeDriver: true, bounciness: 0, speed: 18 }),
      Animated.spring(avatarPanX, { toValue: nextOffset.x, useNativeDriver: true, bounciness: 0, speed: 18 }),
      Animated.spring(avatarPanY, { toValue: nextOffset.y, useNativeDriver: true, bounciness: 0, speed: 18 }),
    ]).start();
    setAvatarScrollEnabled(true);
  };
  useEffect(() => {
    resetAvatarTransform();
  }, [activePreview?.id]);
  return (
    <View style={styles.creatorPage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onClose}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>選擇頭像</Text>
        <Pressable onPress={() => activePreview && onUse(activePreview)} disabled={!activePreview}><Text style={[styles.nextText, !activePreview && { color: muted }]}>完成</Text></Pressable>
      </View>
      <Animated.View style={[styles.avatarPreviewAnimated, {
        height: avatarPreviewAnim.interpolate({ inputRange: [0, 1], outputRange: [0, previewSize] }),
        opacity: avatarPreviewAnim,
      }]}>
      <View style={[styles.avatarPreviewStatic, { width: previewSize, height: previewSize }]}>
        <View
          style={[styles.avatarCropPreview, { width: previewSize, height: previewSize }]}
          onTouchStart={(event) => {
            setAvatarScrollEnabled(false);
            const touches = event.nativeEvent.touches;
            if (touches.length >= 2) {
              touchStart.current = { ...touchStart.current, distance: distanceBetweenTouches(touches), scale: avatarTransform.current.scale };
              return;
            }
            const touch = touches[0];
            if (!touch) return;
            touchStart.current = { ...touchStart.current, x: touch.pageX, y: touch.pageY, offsetX: avatarTransform.current.x, offsetY: avatarTransform.current.y };
          }}
          onTouchMove={(event) => {
            const touches = event.nativeEvent.touches;
            if (touches.length >= 2) {
              const startDistance = touchStart.current.distance || distanceBetweenTouches(touches);
              const nextScale = Math.max(1, Math.min(3, touchStart.current.scale * (distanceBetweenTouches(touches) / startDistance)));
              avatarTransform.current.scale = nextScale;
              avatarScale.setValue(nextScale);
              return;
            }
            const touch = touches[0];
            if (!touch) return;
            const nextOffset = {
              x: touchStart.current.offsetX + touch.pageX - touchStart.current.x,
              y: touchStart.current.offsetY + touch.pageY - touchStart.current.y,
            };
            avatarTransform.current.x = nextOffset.x;
            avatarTransform.current.y = nextOffset.y;
            avatarPanX.setValue(nextOffset.x);
            avatarPanY.setValue(nextOffset.y);
          }}
          onTouchEnd={finishAvatarGesture}
          onTouchCancel={finishAvatarGesture}
        >
          {activePreview ? (
            <Animated.Image
              source={{ uri: activePreview.uri }}
              style={[styles.avatarCropImage, {
                width: baseImageSize.width,
                height: baseImageSize.height,
                transform: [{ translateX: avatarPanX }, { translateY: avatarPanY }, { scale: avatarScale }],
              }]}
              resizeMode="contain"
            />
          ) : <Text style={styles.emptyText}>{error || '沒有可選照片'}</Text>}
          <Svg pointerEvents="none" style={StyleSheet.absoluteFill} width={previewSize} height={previewSize} viewBox={`0 0 ${previewSize} ${previewSize}`}>
            <Path d={circlePath} fill="rgba(17,24,39,0.46)" fillRule="evenodd" />
          </Svg>
        </View>
      </View>
      </Animated.View>
      <ScrollView
        ref={scrollRef}
        scrollEnabled={avatarScrollEnabled}
        showsVerticalScrollIndicator={false}
        stickyHeaderIndices={[0]}
        contentContainerStyle={styles.photoPickerScroll}
        scrollEventThrottle={16}
        onScroll={(event) => {
          const y = event.nativeEvent.contentOffset.y;
          avatarListScrollY.current = y;
          if (hasMorePhotos && !loadingMorePhotos && isNearPhotoListBottom(event)) onLoadMorePhotos();
          if (y > 18) {
            topArmedForPreview.current = false;
            if (showAvatarPreview) setAvatarPreviewVisible(false);
          }
        }}
        onScrollBeginDrag={() => {
          if (!showAvatarPreview && avatarListScrollY.current <= 2 && topArmedForPreview.current) {
            setAvatarPreviewVisible(true);
            topArmedForPreview.current = false;
          }
        }}
        onScrollEndDrag={(event) => {
          const y = event.nativeEvent.contentOffset.y;
          if (y <= 2 && !showAvatarPreview) {
            topArmedForPreview.current = true;
          }
        }}
        onMomentumScrollEnd={(event) => {
          const y = event.nativeEvent.contentOffset.y;
          avatarListScrollY.current = y;
          if (y <= 2 && !showAvatarPreview) topArmedForPreview.current = true;
        }}
      >
        <View style={styles.albumBar}>
          <Pressable style={styles.albumButton} onPress={onCycleAlbum} disabled={!albumsAvailable}>
            <Text style={styles.albumText}>{albumTitle}</Text>
            <ChevronDown size={16} color={ink} />
          </Pressable>
        </View>
        {error ? <FlatMessage text={error} /> : null}
        <View style={styles.avatarPhotoGrid} onLayout={(event) => setAvatarGridWidth(event.nativeEvent.layout.width)}>
          {photos.map((photo) => (
            <Pressable key={photo.id} style={[styles.avatarPhotoTile, { width: avatarTileWidth }, activePreview?.id === photo.id && styles.avatarSelectedTile]} onPress={() => handleAvatarSelect(photo)}>
              <Image source={{ uri: photo.uri }} style={styles.photoTileImage} resizeMode="cover" />
            </Pressable>
          ))}
        </View>
        {loadingMorePhotos ? <ActivityIndicator style={styles.photoLoadingMore} color={purple} /> : null}
      </ScrollView>
    </View>
  );
}

function PostCard({
  post,
  fallbackAuthor,
  fallbackAvatarUrl,
  currentUserId,
  currentPlayerLevel,
  onDelete,
  onAuthorPress,
  onToggleLike,
  onCreateComment,
  onLoadComments,
  onToggleCommentLike,
  edgeToEdge = true,
}: {
  post: CommunityPost;
  fallbackAuthor: string;
  fallbackAvatarUrl: string;
  currentUserId: number;
  currentPlayerLevel: string;
  onDelete: (post: CommunityPost) => void;
  onAuthorPress?: (target?: AuthorProfileTarget) => void;
  onToggleLike: (post: CommunityPost) => void;
  onCreateComment: (post: CommunityPost, body: string) => Promise<CommunityComment | undefined>;
  onLoadComments: (post: CommunityPost) => Promise<CommunityComment[]>;
  onToggleCommentLike: (comment: CommunityComment) => Promise<CommunityComment>;
  edgeToEdge?: boolean;
}) {
  const images = post.image_urls.slice(0, 3);
  const mediaWidth = getPostMediaWidth();
  const [activeImage, setActiveImage] = useState(0);
  const [remoteImageSizes, setRemoteImageSizes] = useState<Record<string, { width: number; height: number }>>({});
  const [showMenu, setShowMenu] = useState(false);
  const [showCommentSheet, setShowCommentSheet] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [comments, setComments] = useState<CommunityComment[]>([]);
  const [loadingComments, setLoadingComments] = useState(false);
  const [submittingComment, setSubmittingComment] = useState(false);
  const [expandedBody, setExpandedBody] = useState(false);
  const [bodyLineCount, setBodyLineCount] = useState<number | null>(null);
  const likeBurstScale = useRef(new Animated.Value(0)).current;
  const lastImageTapAt = useRef(0);
  const isOwnPost = currentUserId > 0 && Number(post.user_id) === currentUserId;
  const avatarUrl = post.author_avatar_url || (isOwnPost ? fallbackAvatarUrl : '');
  const canManagePost = isOwnPost;
  const imageKey = images.join('|');
  const postBody = post.body.trim();
  const isBodyTruncated = bodyLineCount !== null && bodyLineCount > 1;
  useEffect(() => {
    setExpandedBody(false);
    setBodyLineCount(null);
  }, [post.id, post.body]);
  useEffect(() => {
    images.forEach((url, index) => {
      const savedTransform = post.image_transforms?.[index];
      if ((savedTransform?.width && savedTransform?.height) || remoteImageSizes[url]) return;
      Image.getSize(
        url,
        (width, height) => setRemoteImageSizes((current) => ({ ...current, [url]: { width, height } })),
        () => undefined,
      );
    });
  }, [imageKey, post.image_transforms, remoteImageSizes]);
  const playLikeBurst = () => {
    Vibration.vibrate(35);
    likeBurstScale.setValue(0);
    Animated.sequence([
      Animated.spring(likeBurstScale, { toValue: 1, useNativeDriver: true, bounciness: 12, speed: 18 }),
      Animated.timing(likeBurstScale, { toValue: 0, duration: 260, useNativeDriver: true }),
    ]).start();
  };
  const handleImagePress = () => {
    const now = Date.now();
    if (now - lastImageTapAt.current < 360) {
      playLikeBurst();
      if (!post.liked_by_me) onToggleLike(post);
      lastImageTapAt.current = 0;
      return;
    }
    lastImageTapAt.current = now;
  };
  const handleSubmitComment = async () => {
    const body = commentText.trim();
    if (!body || submittingComment) return;
    setSubmittingComment(true);
    try {
      const nextComment = await onCreateComment(post, body);
      if (nextComment) setComments((current) => [...current, nextComment]);
      setCommentText('');
    } finally {
      setSubmittingComment(false);
    }
  };
  const openCommentSheet = async () => {
    setShowCommentSheet(true);
    setLoadingComments(true);
    try {
      setComments(await onLoadComments(post));
    } catch (error) {
      Alert.alert('留言載入失敗', error instanceof Error ? error.message : '無法載入留言。');
    } finally {
      setLoadingComments(false);
    }
  };
  const handleToggleCommentLike = async (comment: CommunityComment) => {
    const updated = await onToggleCommentLike(comment);
    setComments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  };

  return (
    <View style={[styles.postCard, !edgeToEdge && styles.postCardInset]}>
      <View style={styles.postHeader}>
        <Pressable
          style={styles.postAuthorTapArea}
          onPress={() => onAuthorPress?.({
            userId: post.user_id!,
            previewName: post.author_name || fallbackAuthor,
            previewAvatarUrl: avatarUrl,
            previewLevel: post.badge || currentPlayerLevel,
          })}
          disabled={!post.user_id || !onAuthorPress}
        >
        <View style={styles.postAvatar}><AvatarImage uri={avatarUrl} imageStyle={styles.postAvatarImage} iconSize={18} /></View>
        <View style={{ flex: 1 }}>
          <Text style={styles.postAuthor}>{post.author_name || fallbackAuthor}</Text>
          <Text style={styles.postMeta}>{formatPostTime(post.created_at)}</Text>
        </View>
        </Pressable>
        {canManagePost ? (
          <Pressable onPress={() => setShowMenu((value) => !value)} hitSlop={10}>
            <MoreHorizontal size={20} color={muted} />
          </Pressable>
        ) : null}
        {showMenu && canManagePost ? (
          <View style={styles.postMenu}>
            <Pressable
              style={styles.postMenuItem}
              onPress={() => {
                setShowMenu(false);
                onDelete(post);
              }}
            >
              <Text style={styles.postMenuDanger}>刪除貼文</Text>
            </Pressable>
          </View>
        ) : null}
      </View>
      {postBody ? (
        <View style={styles.postBody}>
          <Text
            style={styles.postBodyMeasure}
            onTextLayout={(event) => setBodyLineCount(event.nativeEvent.lines.length)}
          >
            {postBody}
          </Text>
          {expandedBody ? (
            <Text style={styles.postBodyText}>{postBody}</Text>
          ) : (
            <View style={styles.postBodyCollapsed}>
              <Text style={styles.postBodyText} numberOfLines={1} ellipsizeMode="tail">
                {postBody}
              </Text>
              {isBodyTruncated ? (
                <Pressable onPress={() => setExpandedBody(true)} hitSlop={8}>
                  <Text style={styles.postBodyMore}>更多</Text>
                </Pressable>
              ) : null}
            </View>
          )}
        </View>
      ) : null}
      {images.length ? (
        <View style={styles.postImagesFrame}>
        <ScrollView
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          style={styles.postImagesRow}
          onScroll={(event) => {
            setActiveImage(Math.round(event.nativeEvent.contentOffset.x / mediaWidth));
          }}
          scrollEventThrottle={16}
        >
          {images.map((url, index) => {
            const savedTransform = post.image_transforms?.[index] || { x: 0, y: 0, scale: 1 };
            const measuredSize = remoteImageSizes[url];
            const photoLike = { id: `${post.id}-${index}`, uri: url, width: savedTransform.width || measuredSize?.width || mediaWidth, height: savedTransform.height || measuredSize?.height || mediaWidth * 1.25 };
            const imageSize = getWidthFitImageSize(photoLike, mediaWidth);
            const safeTransform = clampWidthFitTransform(photoLike, mediaWidth, scaleSavedTransformToFrame(savedTransform, mediaWidth));
            return (
            <Pressable key={url} onPress={handleImagePress} style={[styles.postImage, { width: mediaWidth }]}>
              <Image
                source={{ uri: url }}
                style={[
                  styles.postImageInner,
                  {
                    width: imageSize.width,
                    height: imageSize.height,
                    transform: [{ translateX: safeTransform.x }, { translateY: safeTransform.y }, { scale: safeTransform.scale }],
                  },
                ]}
                resizeMode="cover"
              />
            </Pressable>
            );
          })}
        </ScrollView>
          <Animated.View
            pointerEvents="none"
            style={[
              styles.likeBurst,
              {
                opacity: likeBurstScale,
                transform: [
                  {
                    scale: likeBurstScale.interpolate({ inputRange: [0, 1], outputRange: [0.55, 1] }),
                  },
                ],
              },
            ]}
          >
            <Heart size={84} color="#fff" fill="#fff" />
          </Animated.View>
          {images.length > 1 ? (
            <View style={styles.postImageDots}>
              {images.map((url, index) => <View key={`${url}-${index}`} style={[styles.postImageDot, activeImage === index && styles.postImageDotActive]} />)}
            </View>
          ) : null}
        </View>
      ) : null}
      <View style={styles.postActions}>
        <Pressable onPress={() => onToggleLike(post)} hitSlop={10}>
          <ActionCount icon={<Heart size={17} color={post.liked_by_me ? purple : muted} fill={post.liked_by_me ? purple : 'transparent'} />} value={post.likes} active={post.liked_by_me} />
        </Pressable>
        <Pressable onPress={openCommentSheet} hitSlop={10}>
          <ActionCount icon={<MessageCircle size={17} color={showCommentSheet ? purple : muted} />} value={post.comments} active={showCommentSheet} />
        </Pressable>
        <ActionCount icon={<Send size={17} color={muted} />} value={post.shares} />
        <Bookmark size={18} color={post.bookmarked_by_me ? purple : muted} fill={post.bookmarked_by_me ? purple : 'transparent'} />
      </View>
      <CommentSheet
        visible={showCommentSheet}
        post={post}
        comments={comments}
        loadingComments={loadingComments}
        commentText={commentText}
        submitting={submittingComment}
        currentUserId={currentUserId}
        currentAvatarUrl={fallbackAvatarUrl}
        currentPlayerLevel={currentPlayerLevel}
        onChangeText={setCommentText}
        onClose={() => setShowCommentSheet(false)}
        onSubmit={handleSubmitComment}
        onAuthorPress={onAuthorPress}
        onToggleCommentLike={handleToggleCommentLike}
      />
    </View>
  );
}

function ActionCount({ icon, value, active = false }: { icon: React.ReactNode; value: number; active?: boolean }) {
  return <View style={styles.actionCount}><>{icon}</><Text style={[styles.actionCountText, active && styles.actionCountTextActive]}>{value}</Text></View>;
}

function CommentSheet({
  visible,
  post,
  comments,
  loadingComments,
  commentText,
  submitting,
  currentUserId,
  currentAvatarUrl,
  currentPlayerLevel,
  onChangeText,
  onClose,
  onSubmit,
  onAuthorPress,
  onToggleCommentLike,
}: {
  visible: boolean;
  post: CommunityPost;
  comments: CommunityComment[];
  loadingComments: boolean;
  commentText: string;
  submitting: boolean;
  currentUserId: number;
  currentAvatarUrl: string;
  currentPlayerLevel: string;
  onChangeText: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
  onAuthorPress?: (target?: AuthorProfileTarget) => void;
  onToggleCommentLike: (comment: CommunityComment) => void;
}) {
  const sheetOffset = useRef(new Animated.Value(1)).current;
  const sheetPositionY = useRef(new Animated.Value(0)).current;
  const screenHeight = Dimensions.get('window').height;
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const sheetDragStartY = useRef(0);
  const sheetDragStartPosition = useRef(0);
  const sheetPositionRef = useRef(0);
  const androidTopInset = Platform.OS === 'android' ? StatusBar.currentHeight || 24 : 0;
  const bottomInset = Platform.OS === 'android' ? 0 : 34;
  const collapsedSheetHeight = Math.round(screenHeight * 0.67);
  const expandedSheetHeight = Math.round(screenHeight * 0.9);
  const sheetHeight = Math.max(320, Math.min(expandedSheetHeight, screenHeight - androidTopInset - 8));
  const collapsedOffset = Math.max(0, sheetHeight - collapsedSheetHeight);
  const quickEmojis = ['👏', '🔥', '🎱', '💯', '🙌'];

  const setSheetPosition = (value: number) => {
    sheetPositionRef.current = value;
    sheetPositionY.setValue(value);
  };

  const springSheetPosition = (value: number) => {
    sheetPositionRef.current = value;
    Animated.spring(sheetPositionY, { toValue: value, useNativeDriver: true, bounciness: 0, speed: 18 }).start();
  };

  useEffect(() => {
    if (!visible) return;
    setIsExpanded(false);
    setSheetPosition(collapsedOffset);
    sheetOffset.setValue(1);
    Animated.spring(sheetOffset, { toValue: 0, useNativeDriver: true, bounciness: 0, speed: 18 }).start();
  }, [visible, sheetOffset, collapsedOffset]);

  useEffect(() => {
    if (!visible) {
      setKeyboardHeight(0);
      return;
    }
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillChangeFrame' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = RNKeyboard.addListener(showEvent, (event) => {
      setKeyboardHeight(Math.max(0, event.endCoordinates?.height || 0));
      setIsExpanded(true);
      springSheetPosition(0);
    });
    const hideSub = RNKeyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [visible]);

  const closeWithAnimation = () => {
    Animated.timing(sheetOffset, { toValue: 1, duration: 170, useNativeDriver: true }).start(onClose);
  };
  const snapSheetTo = (expanded: boolean) => {
    setIsExpanded(expanded);
    springSheetPosition(expanded ? 0 : collapsedOffset);
  };
  const handleBackdropPress = () => {
    RNKeyboard.dismiss();
    closeWithAnimation();
  };
  const handleSheetDragEnd = (pageY: number) => {
    const deltaY = pageY - sheetDragStartY.current;
    const currentPosition = sheetPositionRef.current;
    if (currentPosition < collapsedOffset * 0.62 || deltaY < -28) {
      snapSheetTo(true);
      return;
    }
    if (deltaY > 28) {
      if (sheetDragStartPosition.current < collapsedOffset || keyboardHeight > 0) {
        snapSheetTo(false);
        RNKeyboard.dismiss();
        return;
      }
      closeWithAnimation();
      return;
    }
    snapSheetTo(isExpanded || currentPosition < collapsedOffset / 2);
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={closeWithAnimation}>
      <View style={styles.commentSheetRoot}>
        <Pressable style={styles.commentSheetBackdrop} onPress={handleBackdropPress} />
        <View pointerEvents="none" style={[styles.commentBottomFill, { height: keyboardHeight > 0 ? keyboardHeight + 88 : bottomInset + 88 }]} />
        <SafeAreaView pointerEvents="box-none" style={[styles.commentSheetSafeArea, { paddingTop: androidTopInset }]}>
        <Animated.View
          style={[
            styles.commentSheet,
            {
              height: sheetHeight,
              transform: [
                { translateY: sheetOffset.interpolate({ inputRange: [0, 1], outputRange: [0, sheetHeight] }) },
                { translateY: sheetPositionY },
              ],
            },
          ]}
        >
          <View
            style={styles.commentSheetHeaderTouch}
            onTouchStart={(event) => {
              sheetDragStartY.current = event.nativeEvent.pageY;
              sheetDragStartPosition.current = sheetPositionRef.current;
            }}
            onTouchMove={(event) => {
              const deltaY = event.nativeEvent.pageY - sheetDragStartY.current;
              const nextPosition = Math.max(0, Math.min(collapsedOffset + 90, sheetDragStartPosition.current + deltaY));
              setSheetPosition(nextPosition);
            }}
            onTouchEnd={(event) => handleSheetDragEnd(event.nativeEvent.pageY)}
          >
            <View style={styles.commentSheetHandle} />
          <View style={styles.commentSheetHeader}>
            <Text style={styles.commentSheetTitle}>留言</Text>
          </View>
          </View>
          <ScrollView style={styles.commentSheetBody} contentContainerStyle={styles.commentSheetBodyContent} keyboardShouldPersistTaps="handled">
            {loadingComments ? <ActivityIndicator color={purple} /> : null}
            {!loadingComments && comments.length === 0 ? <FlatMessage text="還沒有留言，成為第一個留言的人。" /> : null}
            {comments.map((comment) => {
              const isOwnComment = currentUserId > 0 && Number(comment.user_id) === currentUserId;
              const commentAvatarUrl = comment.author_avatar_url || (isOwnComment ? currentAvatarUrl : '');
              const commentPlayerLevel = comment.author_player_level || (isOwnComment ? currentPlayerLevel : '');
              const handleCommentAuthorPress = () => {
                onAuthorPress?.({
                  userId: comment.user_id,
                  previewName: comment.author_name,
                  previewAvatarUrl: commentAvatarUrl,
                  previewLevel: commentPlayerLevel,
                });
                onClose();
              };
              return (
                <View key={comment.id} style={styles.commentRow}>
                  <Pressable style={styles.commentAuthorTapArea} onPress={handleCommentAuthorPress} disabled={!onAuthorPress || !comment.user_id}>
                    <View style={styles.commentAvatar}>
                      <AvatarImage uri={commentAvatarUrl} imageStyle={styles.commentAvatarImage} iconSize={17} />
                    </View>
                    <View style={styles.commentTextBlock}>
                    <View style={styles.commentMetaRow}>
                      <Text style={styles.commentAuthor}>{comment.author_name}</Text>
                      {commentPlayerLevel ? <Text style={styles.commentLevel}>{commentPlayerLevel}</Text> : null}
                      <Text style={styles.commentTime}>{formatPostTime(comment.created_at)}</Text>
                    </View>
                    <Text style={styles.commentBody}>{comment.body}</Text>
                    </View>
                  </Pressable>
                  <Pressable style={styles.commentLikeButton} onPress={() => onToggleCommentLike(comment)} hitSlop={10}>
                    <View style={styles.commentLikeIconSlot}>
                      <Heart size={17} color={comment.liked_by_me ? purple : muted} fill={comment.liked_by_me ? purple : 'transparent'} />
                    </View>
                    {comment.likes ? <Text style={[styles.commentLikeText, comment.liked_by_me && styles.actionCountTextActive]}>{comment.likes}</Text> : null}
                  </Pressable>
                </View>
              );
            })}
          </ScrollView>
        </Animated.View>
        </SafeAreaView>
        <View pointerEvents="box-none" style={[styles.commentComposer, { bottom: keyboardHeight, paddingBottom: keyboardHeight > 0 ? 8 : 8 + bottomInset }]}>
          <View style={styles.commentEmojiBar}>
            {quickEmojis.map((emoji) => (
              <Pressable key={emoji} style={styles.commentEmojiButton} onPress={() => onChangeText(`${commentText}${emoji}`)}>
                <Text style={styles.commentEmojiText}>{emoji}</Text>
              </Pressable>
            ))}
          </View>
          <View style={styles.commentInputRow}>
            <TextInput
              style={styles.commentInput}
              value={commentText}
              onChangeText={onChangeText}
              placeholder="留言..."
              placeholderTextColor="#9CA3AF"
              returnKeyType="send"
              onSubmitEditing={onSubmit}
            />
            <Pressable style={[styles.commentSendButton, (!commentText.trim() || submitting) && styles.commentSendButtonDisabled]} onPress={onSubmit} disabled={!commentText.trim() || submitting}>
              {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.commentSendText}>送出</Text>}
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function formatPostTime(value: string): string {
  const normalizedValue = /Z$|[+-]\d{2}:?\d{2}$/.test(value)
    ? value
    : `${value.replace(' ', 'T')}Z`;
  const date = new Date(normalizedValue);
  if (Number.isNaN(date.getTime())) return '';
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return '剛剛';
  if (minutes < 60) return `${minutes} 分鐘前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小時前`;
  return date.toLocaleDateString();
}

function PhotoPickerPage({
  photos,
  selected,
  preview,
  albumTitle,
  albumsAvailable,
  error,
  hasMorePhotos,
  loadingMorePhotos,
  onLoadMorePhotos,
  onClose,
  onNext,
  onSelect,
  onCycleAlbum,
}: {
  photos: LocalPhoto[];
  selected: LocalPhoto[];
  preview?: LocalPhoto | null;
  albumTitle: string;
  albumsAvailable: boolean;
  error: string;
  hasMorePhotos: boolean;
  loadingMorePhotos: boolean;
  onLoadMorePhotos: () => void;
  onClose: () => void;
  onNext: () => void;
  onSelect: (photo: LocalPhoto) => void;
  onCycleAlbum: () => void;
}) {
  const scrollRef = useRef<ScrollView | null>(null);
  const touchStartY = useRef(0);
  const activePreview = preview || selected[selected.length - 1] || photos[0];
  const handleSelect = (photo: LocalPhoto) => {
    onSelect(photo);
  };
  const revealPreview = () => {
    scrollRef.current?.scrollTo({ y: 0, animated: true });
  };
  return (
    <View style={styles.creatorPage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onClose}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>新貼文</Text>
        <Pressable onPress={onNext} disabled={!selected.length}><Text style={[styles.nextText, !selected.length && { color: muted }]}>下一步</Text></Pressable>
      </View>
      <ScrollView
        ref={scrollRef}
        showsVerticalScrollIndicator={false}
        stickyHeaderIndices={[1]}
        contentContainerStyle={styles.photoPickerScroll}
        scrollEventThrottle={16}
        onScroll={(event) => {
          if (hasMorePhotos && !loadingMorePhotos && isNearPhotoListBottom(event)) onLoadMorePhotos();
        }}
      >
        <View style={styles.photoPreview}>
          {activePreview ? <Image source={{ uri: activePreview.uri }} style={styles.photoPreviewImage} resizeMode="contain" /> : <Text style={styles.emptyText}>{error || '沒有可選照片'}</Text>}
        </View>
        <View
          style={styles.albumBar}
          onTouchStart={(event) => {
            touchStartY.current = event.nativeEvent.pageY;
          }}
          onTouchEnd={(event) => {
            if (event.nativeEvent.pageY - touchStartY.current > 8) revealPreview();
          }}
        >
          <Pressable style={styles.albumButton} onPress={onCycleAlbum} disabled={!albumsAvailable}>
            <Text style={styles.albumText}>{albumTitle}</Text>
            <ChevronDown size={16} color={ink} />
          </Pressable>
          <Text style={styles.photoLimitText}>最多 3 張</Text>
        </View>
        {error ? <FlatMessage text={error} /> : null}
        <View style={styles.photoGrid}>
          {photos.map((photo) => {
            const selectedIndex = selected.findIndex((item) => item.id === photo.id);
            return (
              <Pressable key={photo.id} style={styles.photoTile} onPress={() => handleSelect(photo)}>
                <Image source={{ uri: photo.uri }} style={styles.photoTileImage} resizeMode="cover" />
                {selectedIndex >= 0 ? <View style={styles.photoSelectedBadge}><Text style={styles.photoSelectedText}>{selectedIndex + 1}</Text></View> : null}
              </Pressable>
            );
          })}
        </View>
        {loadingMorePhotos ? <ActivityIndicator style={styles.photoLoadingMore} color={purple} /> : null}
      </ScrollView>
    </View>
  );
}

function AlbumSelectionPage({
  albums,
  activeAlbumId,
  onClose,
  onSelect,
}: {
  albums: LocalAlbumOption[];
  activeAlbumId: string;
  onClose: () => void;
  onSelect: (album: MediaLibrary.Album | null) => void;
}) {
  return (
    <View style={styles.creatorPage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onClose}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>選擇相簿</Text>
        <View style={{ width: 24 }} />
      </View>
      <View style={styles.albumList}>
        {albums.map((item) => (
          <Pressable key={item.id} style={styles.albumRow} onPress={() => onSelect(item.album)}>
            {item.coverUri ? <Image source={{ uri: item.coverUri }} style={styles.albumCover} resizeMode="cover" /> : <View style={styles.albumCover} />}
            <View style={{ flex: 1 }}>
              <Text style={styles.albumRowTitle}>{item.title}</Text>
              <Text style={styles.albumRowMeta}>{item.count ?? 0} 張照片</Text>
            </View>
            {activeAlbumId === item.id ? <Text style={styles.albumActiveText}>目前</Text> : null}
            <ChevronRight size={17} color={muted} />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function ComposePostPage({
  photos,
  transforms,
  text,
  setText,
  loading,
  onClose,
  onEditPhoto,
  onShare,
}: {
  photos: LocalPhoto[];
  transforms: Record<string, { x: number; y: number; scale: number }>;
  text: string;
  setText: (value: string) => void;
  loading: boolean;
  onClose: () => void;
  onEditPhoto: (photoId: string) => void;
  onShare: () => void;
}) {
  const mediaWidth = getPostMediaWidth();
  return (
    <View style={styles.creatorPage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onClose}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>撰寫貼文</Text>
        <View style={{ width: 42 }} />
      </View>
      <ScrollView horizontal pagingEnabled showsHorizontalScrollIndicator={false} style={styles.composePreviewScroll}>
        {photos.map((photo) => {
          const transform = transforms[photo.id] || { x: 0, y: 0, scale: 1 };
          const imageSize = getWidthFitImageSize(photo, mediaWidth);
          const safeTransform = clampWidthFitTransform(photo, mediaWidth, transform);
          return (
            <Pressable
              key={photo.id}
              style={[styles.composePreviewFrame, { width: mediaWidth }]}
              onPress={() => onEditPhoto(photo.id)}
            >
              <Image
                source={{ uri: photo.uri }}
                style={[
                  styles.composePreviewImage,
                  {
                    width: imageSize.width,
                    height: imageSize.height,
                    transform: [{ translateX: safeTransform.x }, { translateY: safeTransform.y }, { scale: safeTransform.scale }],
                  },
                ]}
                resizeMode="cover"
              />
            </Pressable>
          );
        })}
      </ScrollView>
      <TextInput
        style={styles.composeInput}
        value={text}
        onChangeText={setText}
        placeholder="寫下今天的練習、球館或對戰心得..."
        placeholderTextColor="#9CA3AF"
        multiline
        textAlignVertical="top"
      />
      <Pressable style={[styles.shareButton, loading && { opacity: 0.7 }]} onPress={onShare} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.shareButtonText}>完成</Text>}
      </Pressable>
    </View>
  );
}

function ComposePhotoEditorPage({
  photo,
  transform,
  onChangeTransform,
  onDone,
}: {
  photo: LocalPhoto;
  transform: { x: number; y: number; scale: number };
  onChangeTransform: (transform: { x: number; y: number; scale: number }) => void;
  onDone: () => void;
}) {
  const mediaWidth = getPostMediaWidth();
  const imageSize = getWidthFitImageSize(photo, mediaWidth);
  const animatedX = useRef(new Animated.Value(transform.x)).current;
  const animatedY = useRef(new Animated.Value(transform.y)).current;
  const animatedScale = useRef(new Animated.Value(transform.scale)).current;
  const editTouchStart = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0, distance: 0, scale: 1 });
  const liveTransform = useRef(transform);
  useEffect(() => {
    const clamped = clampWidthFitTransform(photo, mediaWidth, transform);
    liveTransform.current = clamped;
    animatedX.setValue(clamped.x);
    animatedY.setValue(clamped.y);
    animatedScale.setValue(clamped.scale);
  }, [photo, mediaWidth, transform.x, transform.y, transform.scale, animatedX, animatedY, animatedScale]);
  const setLiveTransform = (nextTransform: PhotoTransform) => {
    liveTransform.current = nextTransform;
    animatedX.setValue(nextTransform.x);
    animatedY.setValue(nextTransform.y);
    animatedScale.setValue(nextTransform.scale);
  };
  const finishEditGesture = () => {
    const clamped = clampWidthFitTransform(photo, mediaWidth, liveTransform.current);
    liveTransform.current = clamped;
    onChangeTransform(clamped);
    Animated.parallel([
      Animated.spring(animatedX, { toValue: clamped.x, useNativeDriver: true, bounciness: 0, speed: 18 }),
      Animated.spring(animatedY, { toValue: clamped.y, useNativeDriver: true, bounciness: 0, speed: 18 }),
      Animated.spring(animatedScale, { toValue: clamped.scale, useNativeDriver: true, bounciness: 0, speed: 18 }),
    ]).start();
  };
  const distanceBetweenComposeTouches = (touches: Array<{ pageX: number; pageY: number }>) => {
    if (touches.length < 2) return 0;
    const dx = touches[0].pageX - touches[1].pageX;
    const dy = touches[0].pageY - touches[1].pageY;
    return Math.sqrt(dx * dx + dy * dy);
  };
  return (
    <View style={styles.creatorPage}>
      <View style={styles.creatorHeader}>
        <View style={{ width: 24 }} />
        <Text style={styles.pageTitle}>編輯照片</Text>
        <Pressable onPress={() => { onChangeTransform(liveTransform.current); onDone(); }}><Text style={styles.nextText}>完成</Text></Pressable>
      </View>
      <View
        style={[styles.composeEditorFrame, { width: mediaWidth }]}
        onTouchStart={(event) => {
          const touches = event.nativeEvent.touches;
          if (touches.length >= 2) {
            editTouchStart.current = { ...editTouchStart.current, distance: distanceBetweenComposeTouches(touches), scale: liveTransform.current.scale };
            return;
          }
          const touch = touches[0];
          if (!touch) return;
          editTouchStart.current = { x: touch.pageX, y: touch.pageY, offsetX: liveTransform.current.x, offsetY: liveTransform.current.y, distance: 0, scale: liveTransform.current.scale };
        }}
        onTouchMove={(event) => {
          const touches = event.nativeEvent.touches;
          if (touches.length >= 2) {
            const startDistance = editTouchStart.current.distance || distanceBetweenComposeTouches(touches);
            const nextScale = Math.max(1, Math.min(3, editTouchStart.current.scale * (distanceBetweenComposeTouches(touches) / startDistance)));
            setLiveTransform({ ...liveTransform.current, scale: nextScale });
            return;
          }
          const touch = touches[0];
          if (!touch) return;
          setLiveTransform({
            ...liveTransform.current,
            x: editTouchStart.current.offsetX + touch.pageX - editTouchStart.current.x,
            y: editTouchStart.current.offsetY + touch.pageY - editTouchStart.current.y,
          });
        }}
        onTouchEnd={finishEditGesture}
        onTouchCancel={finishEditGesture}
      >
        <Animated.Image
          source={{ uri: photo.uri }}
          style={[styles.composePreviewImage, { width: imageSize.width, height: imageSize.height, transform: [{ translateX: animatedX }, { translateY: animatedY }, { scale: animatedScale }] }]}
          resizeMode="cover"
        />
        <View pointerEvents="none" style={styles.composeGridOverlay}>
          <View style={[styles.composeGridLineVertical, { left: `${100 / 3}%` }]} />
          <View style={[styles.composeGridLineVertical, { left: `${200 / 3}%` }]} />
          <View style={[styles.composeGridLineHorizontal, { top: `${100 / 3}%` }]} />
          <View style={[styles.composeGridLineHorizontal, { top: `${200 / 3}%` }]} />
        </View>
      </View>
    </View>
  );
}

function PageHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return <View style={styles.pageHeader}><Text style={styles.pageTitle}>{title}</Text><View style={styles.headerAction}>{action}</View></View>;
}

function Input({ label, value, onChangeText, placeholder, secureTextEntry }: { label: string; value: string; onChangeText: (value: string) => void; placeholder: string; secureTextEntry?: boolean }) {
  return <View style={styles.inputGroup}><Text style={styles.inputLabel}>{label}</Text><TextInput style={styles.input} value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor="#9CA3AF" autoCapitalize="none" secureTextEntry={secureTextEntry} /></View>;
}

function DataSelector({ value, onChange }: { value: DataSection; onChange: (value: DataSection) => void }) {
  const options: DataSection[] = ['總覽', '對戰記錄', '進攻數據', '球型表現'];
  const next = () => onChange(options[(options.indexOf(value) + 1) % options.length]);
  return <Pressable style={styles.dropdown} onPress={next}><Text style={styles.dropdownText}>{value}</Text><ChevronDown size={16} color={ink} /></Pressable>;
}

function BottomNav({ active, onChange }: { active: MainTab; onChange: (tab: MainTab) => void }) {
  const items = [['首頁', Home], ['數據', BarChart3], ['掃碼', QrCode], ['好友', Users], ['我的', User]] as const;
  return <View style={styles.bottomNav}>{items.map(([label, Icon]) => <Pressable key={label} style={styles.navItem} onPress={() => onChange(label)}><Icon size={20} color={active === label ? purple : muted} strokeWidth={active === label ? 2.8 : 2.2} /><Text style={[styles.navText, active === label && { color: purple }]}>{label}</Text></Pressable>)}</View>;
}

function Card({ children }: { children: React.ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return <View style={styles.miniStat}><Text style={styles.subText}>{label}</Text><Text style={styles.miniValue}>{value}</Text></View>;
}

function StatCard({ label, value, progress }: { label: string; value: string; progress: number }) {
  return <View style={styles.statCard}><Text style={styles.statLabel}>{label}</Text><Text style={styles.statValue}>{value}</Text><ProgressBar value={progress} /></View>;
}

function ProgressBar({ value }: { value: number }) {
  return <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${Math.max(0, Math.min(100, value))}%` }]} /></View>;
}

function MatchRow({ match, compact = false }: { match: PlayerGame; compact?: boolean }) {
  const isWin = match.result === 'win';
  const resultLabel = match.result === 'draw' ? '平手' : isWin ? '勝利' : '失敗';
  return (
    <View style={styles.matchRow}>
      <View style={{ flex: 1 }}><Text style={styles.rowTitle}>vs {match.opponent || '未知對手'}</Text><Text style={styles.rowMeta}>{new Date(match.date).toLocaleString()}</Text></View>
      <View style={{ alignItems: 'flex-end' }}><Text style={[styles.resultText, { color: isWin ? success : danger }]}>{resultLabel}</Text><Text style={styles.scoreText}>{match.score}</Text></View>
      {!compact && <ChevronRight size={16} color={muted} />}
    </View>
  );
}

function FriendRow({ friend, loading, onStartGame }: { friend: Friend; loading: boolean; onStartGame: (friend: Friend) => void }) {
  return (
    <View style={styles.friendRow}>
      <View style={styles.friendAvatar}><User size={17} color={muted} /></View>
      <View style={{ flex: 1 }}><Text style={styles.rowTitle}>{friend.username}</Text><Text style={styles.rowMeta}>加入於 {new Date(friend.friendship_created_at).toLocaleDateString()}</Text></View>
      <Pressable style={styles.smallButton} disabled={loading} onPress={() => onStartGame(friend)}><Text style={styles.smallButtonText}>開局</Text></Pressable>
    </View>
  );
}

function SettingsRow({ icon, label, danger: isDanger, onPress }: { icon: React.ReactNode; label: string; danger?: boolean; onPress?: () => void }) {
  return <Pressable style={styles.settingsRow} onPress={onPress}><>{icon}</><Text style={[styles.settingsText, isDanger && { color: danger }]}>{label}</Text><ChevronRight size={16} color={muted} /></Pressable>;
}

function LineChartSvg({ height, values }: { height: number; values: number[] }) {
  const width = 310;
  const chartValues = values.length > 1 ? values : [20, 35, 45, 42, 58, 64, 72, 78];
  const points = chartValues.map((v, i) => `${(i / (chartValues.length - 1)) * width},${height - (v / 100) * (height - 18) - 8}`).join(' ');
  return <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}><Path d={`M0 42 H${width} M0 82 H${width} M0 122 H${width}`} stroke="#EEF2F7" strokeWidth="1" /><Polyline points={points} fill="none" stroke={purple} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></Svg>;
}

function Pill({ text }: { text: string }) {
  return <View style={styles.pill}><Text style={styles.pillText}>{text}</Text><ChevronDown size={13} color={ink} /></View>;
}

function Corner({ style }: { style: object }) {
  return <View style={[styles.corner, style]} />;
}

function EmptyState({ text }: { text: string }) {
  return <Text style={styles.emptyText}>{text}</Text>;
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: '#F8FAFC' },
  shellWeb: {
    flex: 1,
    justifyContent: 'flex-start',
    alignItems: 'center',
    backgroundColor: '#0B1120',
    paddingTop: 12,
  },
  phone: { flex: 1, backgroundColor: '#F8FAFC' },
  phoneWeb: {
    width: 430,
    maxWidth: 430,
    height: 900,
    alignSelf: 'center',
    backgroundColor: '#F8FAFC',
    flexGrow: 0,
    flexShrink: 0,
    borderRadius: 32,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: line,
    overflow: 'hidden',
    shadowColor: '#0F172A',
    shadowOpacity: 0.28,
    shadowRadius: 32,
  },
  content: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 96 },
  contentFrame: { flex: 1, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 96 },
  stack: { gap: 16 },
  homeContentFrame: { flex: 1, paddingTop: 18, paddingBottom: 96 },
  homeFeedContent: { paddingHorizontal: 20, paddingBottom: 108 },
  homeHeaderStack: { gap: 14, marginBottom: 10 },
  homeTopBar: { height: 40, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  homeIconButton: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  homeBrand: { ...appTextFont, color: ink, fontSize: 20, fontWeight: '900' },
  homeDivider: { height: 1, backgroundColor: '#EEF2F7', marginHorizontal: -20 },
  caughtUpBanner: { marginHorizontal: -6, marginVertical: 14, paddingVertical: 14, alignItems: 'center', borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#EEF2F7' },
  caughtUpTitle: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  caughtUpText: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '700', marginTop: 4 },
  feedFooter: { paddingVertical: 18, alignItems: 'center' },
  feedErrorBox: { marginTop: 12, marginHorizontal: -6, paddingVertical: 18, paddingHorizontal: 14, alignItems: 'center', borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#FEE2E2', backgroundColor: '#FEF2F2' },
  feedErrorTitle: { ...appTextFont, color: danger, fontSize: 14, fontWeight: '900' },
  feedErrorText: { ...appTextFont, color: '#7F1D1D', fontSize: 12, lineHeight: 18, fontWeight: '700', marginTop: 6, textAlign: 'center' },
  feedErrorHint: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800', marginTop: 8 },
  loginWrap: { flexGrow: 1, justifyContent: 'center', gap: 14 },
  brand: { ...appTextFont, color: purple, fontSize: 18, fontWeight: '900' },
  loginTitle: { ...appTextFont, color: ink, fontSize: 32, fontWeight: '900', letterSpacing: -1 },
  loginCopy: { ...appTextFont, color: muted, fontSize: 14, lineHeight: 21, fontWeight: '700' },
  autoEndpointCard: { backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12, gap: 4 },
  autoEndpointLabel: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  autoEndpointValue: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '800' },
  inputGroup: { gap: 7 },
  inputLabel: { ...appTextFont, color: ink, fontSize: 12, fontWeight: '900' },
  input: { ...appTextFont, height: 48, borderRadius: 15, borderWidth: 1, borderColor: line, backgroundColor: '#fff', paddingHorizontal: 14, color: ink, fontSize: 14, fontWeight: '800' },
  pageHeader: { minHeight: 34, alignItems: 'center', justifyContent: 'center', position: 'relative' },
  pageTitle: { ...appTextFont, maxWidth: '68%', color: ink, fontSize: 18, fontWeight: '900' },
  headerAction: { position: 'absolute', right: 0 },
  headerLeftAction: { position: 'absolute', left: 0 },
  userHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#D1D5DB' },
  avatarLarge: { width: 58, height: 58, borderRadius: 29, backgroundColor: '#D1D5DB' },
  userName: { ...appTextFont, color: ink, fontSize: 17, fontWeight: '900' },
  subText: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '700' },
  scoreCard: { minHeight: 170, borderRadius: 18, backgroundColor: '#111827', padding: 18, shadowColor: '#0F172A', shadowOpacity: 0.18, shadowRadius: 18, elevation: 8 },
  scoreLabel: { ...appTextFont, color: '#CBD5E1', fontSize: 14, fontWeight: '800' },
  scoreValue: { ...appTextFont, color: '#fff', fontSize: 42, fontWeight: '900', letterSpacing: -1 },
  scoreMeta: { ...appTextFont, color: '#CBD5E1', fontSize: 13, fontWeight: '800' },
  badgeCircle: { position: 'absolute', right: 18, top: 24, width: 64, height: 64, borderRadius: 32, backgroundColor: 'rgba(255,255,255,0.09)', alignItems: 'center', justifyContent: 'center' },
  scoreProgressWrap: { position: 'absolute', left: 18, right: 18, bottom: 18, gap: 8 },
  scoreFoot: { ...appTextFont, color: '#CBD5E1', fontSize: 12, fontWeight: '700' },
  spaceBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  threeGrid: { flexDirection: 'row', gap: 10 },
  miniStat: { flex: 1, backgroundColor: '#fff', borderRadius: 16, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: line },
  miniValue: { ...appTextFont, marginTop: 6, color: ink, fontSize: 22, fontWeight: '900' },
  card: { backgroundColor: '#fff', borderRadius: 18, borderWidth: 1, borderColor: line, padding: 16, shadowColor: '#0F172A', shadowOpacity: 0.06, shadowRadius: 14, elevation: 2 },
  sectionTitle: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  linkText: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  greenText: { ...appTextFont, color: success, fontWeight: '900' },
  progressTrack: { height: 5, backgroundColor: '#E5E7EB', borderRadius: 999, overflow: 'hidden' },
  progressFill: { height: 5, backgroundColor: purple, borderRadius: 999 },
  twoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  statCard: { width: '48%', backgroundColor: '#fff', borderRadius: 18, borderWidth: 1, borderColor: line, padding: 15, gap: 10 },
  statLabel: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800' },
  statValue: { ...appTextFont, color: ink, fontSize: 24, fontWeight: '900' },
  dropdown: { height: 40, alignSelf: 'flex-start', paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: line, backgroundColor: '#fff', flexDirection: 'row', alignItems: 'center', gap: 14 },
  dropdownText: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: line, borderRadius: 12, paddingHorizontal: 12, height: 36, backgroundColor: '#fff' },
  pillText: { ...appTextFont, color: ink, fontSize: 12, fontWeight: '800' },
  segment: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: line },
  segmentItem: { flex: 1, alignItems: 'center', paddingBottom: 12 },
  segmentActive: { borderBottomWidth: 2, borderBottomColor: purple },
  segmentText: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '800' },
  segmentTextActive: { color: purple },
  matchRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: line },
  rowTitle: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  rowMeta: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '700', marginTop: 3 },
  resultText: { ...appTextFont, fontSize: 12, fontWeight: '900' },
  scoreText: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900', marginTop: 2 },
  scanStack: { flex: 1, justifyContent: 'center' },
  scanPanel: { alignItems: 'center' },
  scanVisualSlot: { width: '100%', height: 330, marginTop: 20, marginBottom: 16, alignItems: 'center', justifyContent: 'center' },
  qrScanner: { width: 226, height: 226, alignItems: 'center', justifyContent: 'center' },
  corner: { position: 'absolute', width: 34, height: 34, borderColor: purple, borderRadius: 6 },
  cameraFrame: { width: '100%', height: 330, borderRadius: 20, overflow: 'hidden', backgroundColor: '#000' },
  camera: { flex: 1 },
  myQrBox: { width: 226, gap: 10, alignItems: 'center' },
  primaryButton: { width: '100%', height: 50, borderRadius: 14, backgroundColor: purple, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  primaryButtonText: { ...appTextFont, color: '#fff', fontSize: 14, fontWeight: '900' },
  searchBox: { height: 42, borderRadius: 16, backgroundColor: '#fff', flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, gap: 8 },
  searchPlaceholder: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '700' },
  friendRow: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: line },
  friendAvatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center' },
  smallButton: { height: 34, paddingHorizontal: 14, borderRadius: 12, backgroundColor: purple, justifyContent: 'center' },
  smallButtonText: { ...appTextFont, color: '#fff', fontSize: 12, fontWeight: '900' },
  profileHeader: { flexDirection: 'row', alignItems: 'center', gap: 13, backgroundColor: '#fff', borderRadius: 18, padding: 16 },
  profileFlatPage: { flex: 1 },
  profileContentFrame: { flex: 1, paddingTop: 18, paddingBottom: 96 },
  profileScrollContent: { gap: 14, paddingHorizontal: 20 },
  profileFlatSection: { paddingVertical: 12, gap: 18 },
  profileCard: { backgroundColor: '#fff', borderRadius: 22, borderWidth: 1, borderColor: line, padding: 18, gap: 18, shadowColor: '#0F172A', shadowOpacity: 0.07, shadowRadius: 18, elevation: 3 },
  profileTopRow: { flexDirection: 'row', alignItems: 'center', gap: 13 },
  profileHeroRow: { minHeight: 88, flexDirection: 'row', alignItems: 'stretch', gap: 14 },
  profileHeroContent: { flex: 1, minHeight: 88, justifyContent: 'space-between', paddingVertical: 2 },
  profileAvatar: { width: 88, height: 88, borderRadius: 44, backgroundColor: '#EEF2F7', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  profileAvatarImage: { width: '100%', height: '100%' },
  profileName: { ...appTextFont, color: ink, fontSize: 20, fontWeight: '900' },
  profileLevel: { ...appTextFont, alignSelf: 'flex-start', color: purple, backgroundColor: '#EEF2FF', overflow: 'hidden', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4, fontSize: 11, fontWeight: '900' },
  iconButton: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: line, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  profileStatsRow: { flexDirection: 'row' },
  profileStatItem: { flex: 1, alignItems: 'center', gap: 4 },
  profileStatValue: { ...appTextFont, color: ink, fontSize: 18, fontWeight: '900' },
  profileStatLabel: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '800' },
  profileBio: { ...appTextFont, color: '#374151', fontSize: 14, lineHeight: 20, fontWeight: '700' },
  editProfileButton: { height: 38, borderRadius: 10, borderWidth: 1, borderColor: line, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  editProfileText: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  followingProfileButton: { borderColor: '#C7D2FE', backgroundColor: '#EEF2FF' },
  followingProfileText: { color: purple },
  profileStickyTabs: { marginHorizontal: -20, paddingHorizontal: 20, backgroundColor: '#F8FAFC', zIndex: 5, elevation: 5 },
  profileModeTabs: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  profileModeTab: { flex: 1, height: 40, alignItems: 'center', justifyContent: 'center' },
  profileContentDivider: { height: 1, backgroundColor: '#EAECEF', marginHorizontal: -20 },
  profileStatsPanel: { paddingVertical: 4 },
  profileDataRow: { minHeight: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  profileDataLabel: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '800' },
  profileDataValue: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  editProfilePage: { flex: 1, gap: 22 },
  editAvatarBlock: { alignItems: 'center', gap: 10, paddingTop: 14, paddingBottom: 18 },
  editAvatar: { width: 104, height: 104, borderRadius: 52, backgroundColor: '#EEF2F7', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  editAvatarImage: { width: '100%', height: '100%' },
  changeAvatarText: { ...appTextFont, color: purple, fontSize: 14, fontWeight: '900' },
  editFieldRow: { minHeight: 58, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#EAECEF', justifyContent: 'center', gap: 6, paddingVertical: 10 },
  editFieldLabel: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800' },
  editFieldInput: { ...appTextFont, color: ink, fontSize: 16, fontWeight: '800', padding: 0 },
  editBioInput: { ...appTextFont, minHeight: 58, lineHeight: 22, textAlignVertical: 'top' },
  avatarMenuOverlay: { position: 'absolute', left: -20, right: -20, top: -18, bottom: -96, zIndex: 30, justifyContent: 'flex-end' },
  avatarMenuBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(15,23,42,0.28)' },
  avatarMenuSheet: { backgroundColor: '#fff', borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 20, paddingTop: 12, paddingBottom: 30 },
  avatarMenuItem: { minHeight: 52, justifyContent: 'center', borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  avatarMenuCancel: { minHeight: 52, justifyContent: 'center', marginTop: 8 },
  avatarMenuText: { ...appTextFont, color: ink, fontSize: 16, fontWeight: '900', textAlign: 'center' },
  avatarMenuDanger: { ...appTextFont, color: danger, fontSize: 16, fontWeight: '900', textAlign: 'center' },
  avatarPreviewAnimated: { marginHorizontal: -20, overflow: 'hidden', alignItems: 'center' },
  avatarPreviewStatic: { overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  avatarCropPreview: { backgroundColor: '#000', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  avatarCropImage: {},
  avatarSelectedTile: { borderWidth: 3, borderColor: purple, opacity: 0.92 },
  postCard: { marginHorizontal: -20, paddingVertical: 16, gap: 12 },
  postCardInset: { marginHorizontal: 0 },
  postHeader: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingHorizontal: 12, position: 'relative' },
  postAuthorTapArea: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 11 },
  postAvatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#EEF2F7', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  postAvatarImage: { width: '100%', height: '100%' },
  postAuthor: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  postMeta: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '700', marginTop: 2 },
  postBody: { paddingHorizontal: 12, position: 'relative' },
  postBodyMeasure: { ...appTextFont, position: 'absolute', left: 12, right: 12, opacity: 0, color: '#374151', fontSize: 13, lineHeight: 20, fontWeight: '700' },
  postBodyText: { ...appTextFont, flex: 1, color: '#374151', fontSize: 13, lineHeight: 20, fontWeight: '700' },
  postBodyCollapsed: { flexDirection: 'row', alignItems: 'center' },
  postBodyMore: { ...appTextFont, color: purple, fontSize: 13, lineHeight: 20, fontWeight: '900' },
  postMenu: { position: 'absolute', right: 12, top: 30, minWidth: 120, backgroundColor: '#fff', borderWidth: 1, borderColor: line, borderRadius: 12, shadowColor: '#0F172A', shadowOpacity: 0.12, shadowRadius: 12, elevation: 4, zIndex: 10 },
  postMenuItem: { paddingHorizontal: 14, paddingVertical: 12 },
  postMenuDanger: { ...appTextFont, color: danger, fontSize: 13, fontWeight: '900' },
  postImagesFrame: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#E5E7EB', position: 'relative' },
  postImagesRow: { width: '100%' },
  postImage: { aspectRatio: 4 / 5, backgroundColor: '#fff', overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  postImageInner: { backgroundColor: '#fff' },
  likeBurst: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, alignItems: 'center', justifyContent: 'center', shadowColor: '#0F172A', shadowOpacity: 0.25, shadowRadius: 16 },
  postImageDots: { position: 'absolute', left: 0, right: 0, bottom: 10, flexDirection: 'row', justifyContent: 'center', gap: 6 },
  postImageDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D1D5DB' },
  postImageDotActive: { backgroundColor: purple },
  postActions: { flexDirection: 'row', alignItems: 'center', gap: 18, paddingHorizontal: 12 },
  actionCount: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  actionCountText: { ...appTextFont, color: '#374151', fontSize: 12, fontWeight: '900' },
  actionCountTextActive: { color: purple },
  commentSheetRoot: { flex: 1, justifyContent: 'flex-end' },
  commentSheetBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(15,23,42,0.36)' },
  commentBottomFill: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: '#fff', zIndex: 1 },
  commentSheetSafeArea: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'transparent' },
  commentSheet: { backgroundColor: '#fff', borderTopLeftRadius: 24, borderTopRightRadius: 24, overflow: 'hidden', shadowColor: '#0F172A', shadowOpacity: 0.18, shadowRadius: 22, elevation: 8, zIndex: 2 },
  commentSheetHeaderTouch: { backgroundColor: '#fff' },
  commentSheetHandle: { alignSelf: 'center', width: 42, height: 5, borderRadius: 999, backgroundColor: '#D1D5DB', marginTop: 9 },
  commentSheetHeader: { height: 50, paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  commentSheetTitle: { ...appTextFont, textAlign: 'center', color: ink, fontSize: 16, fontWeight: '900' },
  commentSheetBody: { flex: 1 },
  commentSheetBodyContent: { paddingHorizontal: 18, paddingTop: 14, paddingBottom: 118, gap: 16 },
  commentRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  commentAuthorTapArea: { flex: 1, flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  commentAvatar: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#EEF2F7', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  commentAvatarImage: { width: '100%', height: '100%' },
  commentTextBlock: { flex: 1, gap: 3 },
  commentMetaRow: { minHeight: 18, flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  commentAuthor: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  commentLevel: { ...appTextFont, color: purple, fontSize: 11, fontWeight: '900' },
  commentTime: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '700' },
  commentBody: { ...appTextFont, color: '#374151', fontSize: 13, lineHeight: 19, fontWeight: '700' },
  commentLikeButton: { minWidth: 34, alignItems: 'center', justifyContent: 'flex-start', gap: 1 },
  commentLikeIconSlot: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' },
  commentLikeText: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '900' },
  commentComposer: { position: 'absolute', left: 0, right: 0, borderTopWidth: 1, borderTopColor: '#EEF2F7', backgroundColor: '#fff', paddingTop: 8, zIndex: 4 },
  commentEmojiBar: { minHeight: 34, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingBottom: 6 },
  commentEmojiButton: { width: 32, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F3F4F6' },
  commentEmojiText: { ...appTextFont, fontSize: 15 },
  commentInputRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12 },
  commentInput: { ...appTextFont, flex: 1, minHeight: 38, borderRadius: 19, backgroundColor: '#EEF2F7', paddingHorizontal: 14, color: ink, fontSize: 13, fontWeight: '800' },
  commentSendButton: { height: 38, minWidth: 58, borderRadius: 19, backgroundColor: purple, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  commentSendButtonDisabled: { opacity: 0.45 },
  commentSendText: { ...appTextFont, color: '#fff', fontSize: 13, fontWeight: '900' },
  flatMessage: { paddingVertical: 20, borderBottomWidth: 1, borderBottomColor: line },
  flatLogout: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: line },
  creatorPage: { flex: 1, gap: 14 },
  creatorHeader: { minHeight: 36, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  nextText: { ...appTextFont, color: purple, fontSize: 14, fontWeight: '900' },
  photoPickerScroll: { paddingBottom: 20 },
  photoPreview: { alignSelf: 'stretch', aspectRatio: 4 / 5, marginHorizontal: -20, backgroundColor: '#F8FAFC', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  photoPreviewImage: { width: '100%', height: '100%' },
  albumBar: { minHeight: 42, marginHorizontal: -20, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#F8FAFC', borderBottomWidth: 1, borderBottomColor: line, zIndex: 5 },
  albumButton: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 4 },
  albumText: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  photoLimitText: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800', textAlign: 'right' },
  photoGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -20 },
  photoTile: { width: '33.333%', aspectRatio: 1, padding: 1 },
  avatarPhotoGrid: { flexDirection: 'row', flexWrap: 'wrap', alignSelf: 'stretch' },
  avatarPhotoTile: { aspectRatio: 1, padding: 1 },
  photoTileImage: { width: '100%', height: '100%', backgroundColor: '#E5E7EB' },
  photoLoadingMore: { paddingVertical: 18 },
  photoSelectedBadge: { position: 'absolute', right: 8, top: 8, width: 24, height: 24, borderRadius: 12, backgroundColor: purple, alignItems: 'center', justifyContent: 'center' },
  photoSelectedText: { ...appTextFont, color: '#fff', fontSize: 12, fontWeight: '900' },
  albumList: { marginHorizontal: -20 },
  albumRow: { minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 20, borderBottomWidth: 1, borderBottomColor: line },
  albumCover: { width: 52, height: 52, borderRadius: 8, backgroundColor: '#E5E7EB' },
  albumRowTitle: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  albumRowMeta: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '700', marginTop: 3 },
  albumActiveText: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  composePreviewScroll: { marginHorizontal: -20, maxHeight: 538, backgroundColor: '#000' },
  composePreviewFrame: { aspectRatio: 4 / 5, backgroundColor: '#000', overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  composePreviewImage: { backgroundColor: '#000' },
  composeEditorFrame: { alignSelf: 'center', aspectRatio: 4 / 5, backgroundColor: '#000', overflow: 'hidden', alignItems: 'center', justifyContent: 'center', marginHorizontal: -20 },
  composeGridOverlay: { ...StyleSheet.absoluteFillObject },
  composeGridLineVertical: { position: 'absolute', top: 0, bottom: 0, width: 1, backgroundColor: 'rgba(255,255,255,0.82)' },
  composeGridLineHorizontal: { position: 'absolute', left: 0, right: 0, height: 1, backgroundColor: 'rgba(255,255,255,0.82)' },
  composeInput: { ...appTextFont, minHeight: 180, color: ink, fontSize: 16, lineHeight: 24, fontWeight: '700', padding: 16 },
  shareButton: { alignSelf: 'center', minWidth: 150, height: 48, paddingHorizontal: 28, borderRadius: 999, backgroundColor: purple, alignItems: 'center', justifyContent: 'center' },
  shareButtonText: { ...appTextFont, color: '#fff', fontSize: 15, fontWeight: '900' },
  levelBadge: { ...appTextFont, alignSelf: 'flex-start', color: '#047857', backgroundColor: '#ECFDF5', overflow: 'hidden', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3, marginVertical: 4, fontSize: 11, fontWeight: '900' },
  settingsRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 15, borderBottomWidth: 1, borderBottomColor: line },
  settingsText: { ...appTextFont, flex: 1, color: ink, fontSize: 14, fontWeight: '900' },
  emptyText: { ...appTextFont, marginTop: 14, color: muted, fontSize: 13, lineHeight: 20, fontWeight: '700' },
  bottomNav: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 78, backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: line, flexDirection: 'row', paddingHorizontal: 12, paddingTop: 8 },
  navItem: { flex: 1, alignItems: 'center', gap: 4 },
  navText: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '800' },
});
