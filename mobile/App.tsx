import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Animated, Dimensions, FlatList, Image, ImageStyle, Keyboard as RNKeyboard, KeyboardAvoidingView, LogBox, Modal, NativeScrollEvent, NativeSyntheticEvent, Platform, Pressable, SafeAreaView, ScrollView, StatusBar, StyleProp, StyleSheet, Switch, Text, TextInput, TextStyle, View, ViewStyle, Vibration } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as FileSystem from 'expo-file-system/legacy';
import * as ImageManipulator from 'expo-image-manipulator';
import * as MediaLibrary from 'expo-media-library';
import * as Notifications from 'expo-notifications';
import {
  BarChart3,
  Bell,
  Bookmark,
  ChevronDown,
  ChevronRight,
  Grid3X3,
  Heart,
  Home,
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
  Users,
  X,
} from 'lucide-react-native';
import Svg, { Circle, Line, Path, Polygon, Polyline, Text as SvgText } from 'react-native-svg';
import QRCode from 'react-native-qrcode-svg';

import {
  acceptFriendInviteQr,
  acceptFriendMatchInvite,
  changePassword,
  createFriendInviteQr,
  createCommunityComment,
  createCommunityPost,
  deactivateAccount,
  deleteAccount,
  deleteCommunityPost,
  getCommunityComments,
  getCommunityBookmarks,
  getDashboard,
  getFriends,
  getAuthMe,
  getMobileBlocks,
  getMobileFollowingFeed,
  getMobileFollowList,
  getMobileNotificationSettings,
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
  parseUserProfileQrPayload,
  register,
  registerMobilePushToken,
  sendCoachChatStream,
  startFriendGame,
  startFriendGameByCode,
  toggleCommunityBookmark,
  toggleCommunityCommentLike,
  toggleCommunityLike,
  unblockMobileUser,
  unfollowMobileUser,
  uploadCommunityImages,
  updateAuthProfile,
  updateMobileNotificationSettings,
  updateMobileProfile,
} from './src/api';
import { getConfiguredApiBaseUrl, getExplicitApiBaseUrl } from './src/env';
import { initializeMobileFirebaseTools } from './src/firebase';
import { clearSession, loadSession, saveSession, StoredSession } from './src/storage';
import { AuthUser, CommunityComment, CommunityPost, DashboardResponse, Friend, LoginHistoryEntry, MobileBlockedUser, MobileFollowUser, MobileNotificationSettings, MobileNotificationSettingsUpdate, MobileProfile, PlayerGame, PracticeRecord } from './src/types';

const EAS_PROJECT_ID = '3dc631c2-2519-445c-8730-d8523b22e7d5';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

type MainTab = '首頁' | '數據' | '掃碼' | 'AI教練聊天室' | '我的';
type DataSection = '總覽' | '歷史紀錄' | '進攻數據' | '球型表現';
type HistoryFilter = '全部' | '練習' | '對戰';
type HistoryDetailItem =
  | { kind: 'practice'; id: string; record: PracticeRecord }
  | { kind: 'match'; id: string; record: PlayerGame };
type ProfileMode = 'profile' | 'picker' | 'albums' | 'compose' | 'editProfile' | 'avatarPicker' | 'settings' | 'accountField' | 'accountSecurity' | 'changePassword' | 'loginDevices' | 'accountPrivacy' | 'accountStatus' | 'favorites' | 'followList' | 'notificationSettings' | 'notificationPostInteraction' | 'notificationCommentInteraction' | 'notificationFriends' | 'notificationSystem' | 'notificationDisplayMode' | 'notificationQuietHours' | 'blockedSafety';
type AccountEditField = 'name' | 'username' | 'bio';
type AccountStatusActionType = 'deactivate' | 'delete';
type AiCoachChatMessage = {
  id: string;
  role: 'user' | 'coach';
  text: string;
  timestamp: string;
  status?: string;
};
type AiCoachSendResult = {
  reply: string;
  timestamp?: string;
  status?: string;
};
type AiCoachSendDelta = (delta: string) => void;
type NotificationSettingKey =
  | 'postLikes'
  | 'postComments'
  | 'commentReplies'
  | 'commentLikes'
  | 'newFollowers'
  | 'mutualFollows'
  | 'accountSecurity'
  | 'loginChanges'
  | 'serviceAnnouncements'
  | 'showPreview'
  | 'typeOnly'
  | 'quietHours';
type NotificationSettingsState = Record<NotificationSettingKey, boolean>;
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
type FollowListKind = 'followers' | 'following';
type CaughtUpBannerItem = { type: 'caught_up_banner'; id: string };
type HomeFeedItem = CommunityPost | CaughtUpBannerItem;
type HomeProfileRoute = { userId: number; previewName?: string; previewAvatarUrl?: string; previewLevel?: string };
type AuthorProfileTarget = number | null | undefined | HomeProfileRoute;
type AuthMode = 'welcome' | 'login' | 'register';

const purple = '#4F46E5';
const officialBlue = '#1D9BF0';
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
const MOBILE_UPLOAD_TARGET_BYTES = 15 * 1024 * 1024;
const DEFAULT_NOTIFICATION_SETTINGS: NotificationSettingsState = {
  postLikes: true,
  postComments: true,
  commentReplies: true,
  commentLikes: true,
  newFollowers: true,
  mutualFollows: true,
  accountSecurity: true,
  loginChanges: true,
  serviceAnnouncements: true,
  showPreview: true,
  typeOnly: false,
  quietHours: false,
};
const NOTIFICATION_SETTING_PAYLOAD_KEYS: Record<NotificationSettingKey, keyof MobileNotificationSettingsUpdate> = {
  postLikes: 'post_likes_enabled',
  postComments: 'post_comments_enabled',
  commentReplies: 'comment_replies_enabled',
  commentLikes: 'comment_likes_enabled',
  newFollowers: 'new_followers_enabled',
  mutualFollows: 'mutual_follows_enabled',
  accountSecurity: 'account_security_enabled',
  loginChanges: 'login_changes_enabled',
  serviceAnnouncements: 'service_announcements_enabled',
  showPreview: 'show_preview_enabled',
  typeOnly: 'type_only_enabled',
  quietHours: 'quiet_hours_enabled',
};
const iosSystemFontFamily = Platform.select({
  ios: 'System',
  web: '-apple-system, BlinkMacSystemFont, "PingFang TC", "Helvetica Neue", Arial, sans-serif',
});
const appTextFont: Pick<TextStyle, 'fontFamily'> = iosSystemFontFamily ? { fontFamily: iosSystemFontFamily } : {};
const cueVexLogo = require('./assets/cuevex-logo.png');

const isOfficialLevel = (value?: string) => (value || '').trim() === '官方帳號';
const isOfficialName = (value?: string) => (value || '').trim().toLowerCase() === 'cuevex';

LogBox.ignoreLogs([
  'Due to changes in Androids permission requirements, Expo Go can no longer provide full access to the media library.',
  'expo-notifications: Android Push notifications (remote notifications) functionality provided by expo-notifications was removed from Expo Go',
  '`expo-notifications` functionality is not fully supported in Expo Go',
  'SafeAreaView has been deprecated',
]);

function mimeTypeForFilename(filename = ''): string {
  const normalized = filename.toLowerCase();
  if (normalized.endsWith('.png')) return 'image/png';
  if (normalized.endsWith('.webp')) return 'image/webp';
  if (normalized.endsWith('.heic')) return 'image/heic';
  if (normalized.endsWith('.heif')) return 'image/heif';
  return 'image/jpeg';
}

function jpegFilenameForPhoto(photo: LocalPhoto): string {
  const source = photo.filename || `${photo.id}.jpg`;
  const withoutExtension = source.replace(/\.[^.]+$/, '');
  return `${withoutExtension || photo.id}.jpg`;
}

function canUseWebPhotoPicker(): boolean {
  return Platform.OS === 'web' && typeof document !== 'undefined' && typeof window !== 'undefined';
}

function readWebFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const fallbackMimeType = file.type && file.type.startsWith('image/') ? file.type : mimeTypeForFilename(file.name);
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('照片讀取失敗，請重新選擇照片。'));
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : '';
      if (/^data:image\/[a-zA-Z0-9.+-]+;base64,/.test(result)) {
        resolve(result);
        return;
      }
      const base64Match = result.match(/^data:[^;]*;base64,(.+)$/);
      if (base64Match?.[1]) {
        resolve(`data:${fallbackMimeType};base64,${base64Match[1].replace(/\s/g, '')}`);
        return;
      }
      reject(new Error('不支援的照片格式，請改選 JPG、PNG 或 HEIC 照片。'));
    };
    reader.readAsDataURL(file);
  });
}

function measureWebImage(uri: string): Promise<{ width?: number; height?: number }> {
  return new Promise((resolve, reject) => {
    if (!canUseWebPhotoPicker()) {
      resolve({});
      return;
    }
    const image = document.createElement('img');
    image.onload = () => resolve({
      width: image.naturalWidth || image.width || undefined,
      height: image.naturalHeight || image.height || undefined,
    });
    image.onerror = () => reject(new Error('照片解析失敗，請重新選擇照片。'));
    image.src = uri;
  });
}

function pickWebPhotoFiles(maxFiles: number): Promise<LocalPhoto[] | null> {
  if (!canUseWebPhotoPicker()) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = maxFiles > 1;
    input.style.position = 'fixed';
    input.style.left = '-9999px';
    input.style.top = '-9999px';
    input.style.opacity = '0';

    let settled = false;
    const cleanup = () => {
      window.removeEventListener('focus', handleFocus);
      input.remove();
    };
    const finish = (value: LocalPhoto[] | null) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(value);
    };
    const fail = (error: Error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };
    const handleFocus = () => {
      window.setTimeout(() => {
        if (!settled && (!input.files || input.files.length === 0)) {
          finish(null);
        }
      }, 500);
    };

    input.onchange = async () => {
      try {
        const files = Array.from(input.files || [])
          .filter((file) => !file.type || file.type.startsWith('image/') || mimeTypeForFilename(file.name).startsWith('image/'))
          .slice(0, maxFiles);
        if (!files.length) {
          finish(null);
          return;
        }
        const photos = await Promise.all(files.map(async (file, index) => {
          const uri = await readWebFileAsDataUrl(file);
          const size = await measureWebImage(uri);
          return {
            id: `web-${Date.now()}-${index}-${file.name || 'photo'}`,
            uri,
            filename: file.name || `photo-${index + 1}.jpg`,
            mimeType: file.type || mimeTypeForFilename(file.name),
            width: size.width,
            height: size.height,
          };
        }));
        finish(photos);
      } catch (error) {
        fail(error instanceof Error ? error : new Error('照片讀取失敗，請重新選擇照片。'));
      }
    };

    input.onerror = () => fail(new Error('照片選擇器開啟失敗，請重新整理後再試。'));
    document.body.appendChild(input);
    window.addEventListener('focus', handleFocus);
    input.click();
  });
}

function isNearPhotoListBottom(event: NativeSyntheticEvent<NativeScrollEvent>): boolean {
  const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
  return contentOffset.y + layoutMeasurement.height >= contentSize.height - 900;
}

function isCaughtUpBannerItem(item: HomeFeedItem): item is CaughtUpBannerItem {
  return 'type' in item && item.type === 'caught_up_banner';
}

function applyNotificationSettingsFromApi(settings: MobileNotificationSettings): {
  pushEnabled: boolean;
  settings: NotificationSettingsState;
} {
  return {
    pushEnabled: settings.push_enabled,
    settings: {
      postLikes: settings.post_likes_enabled,
      postComments: settings.post_comments_enabled,
      commentReplies: settings.comment_replies_enabled,
      commentLikes: settings.comment_likes_enabled,
      newFollowers: settings.new_followers_enabled,
      mutualFollows: settings.mutual_follows_enabled,
      accountSecurity: settings.account_security_enabled,
      loginChanges: settings.login_changes_enabled,
      serviceAnnouncements: settings.service_announcements_enabled,
      showPreview: settings.show_preview_enabled,
      typeOnly: settings.type_only_enabled,
      quietHours: settings.quiet_hours_enabled,
    },
  };
}

function getPostMediaWidth(): number {
  const windowWidth = Dimensions.get('window').width;
  return Platform.OS === 'web' ? Math.min(windowWidth, 430) : windowWidth;
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
  if (canUseWebPhotoPicker()) {
    const size = await measureWebImage(photo.uri);
    const width = size.width || photo.width || 0;
    const height = size.height || photo.height || 0;
    if (width <= 0 || height <= 0) {
      throw new Error('照片解析失敗，請重新選擇照片。');
    }
    const longestEdge = Math.max(width, height);
    const scale = longestEdge > maxEdge ? maxEdge / longestEdge : 1;
    const outputWidth = Math.max(1, Math.round(width * scale));
    const outputHeight = Math.max(1, Math.round(height * scale));
    const image = document.createElement('img');
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('照片壓縮失敗，請重新選擇照片。'));
      image.src = photo.uri;
    });
    const canvas = document.createElement('canvas');
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('照片壓縮失敗，請重新整理後再試。');
    context.drawImage(image, 0, 0, outputWidth, outputHeight);
    const uri = canvas.toDataURL('image/jpeg', quality);
    if (!/^data:image\/jpeg;base64,/.test(uri)) {
      throw new Error('照片壓縮失敗，請重新選擇照片。');
    }
    return {
      ...photo,
      uri,
      filename: jpegFilenameForPhoto(photo),
      mimeType: 'image/jpeg',
      width: outputWidth,
      height: outputHeight,
      uploadFilename: jpegFilenameForPhoto(photo),
      uploadMimeType: 'image/jpeg',
    };
  }
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
    throw new Error(`單張圖片壓縮後需小於 ${targetKb}KB，請換較小圖片或降低解析度。`);
  }
}

async function readUploadPhotoBase64(uri: string): Promise<string> {
  const dataUriMatch = uri.match(/^data:image\/[a-zA-Z0-9.+-]+;base64,(.+)$/);
  if (dataUriMatch?.[1]) return dataUriMatch[1].replace(/\s/g, '');
  if (Platform.OS === 'web' && /^(blob:|https?:)/i.test(uri)) {
    const response = await fetch(uri);
    if (!response.ok) throw new Error('無法讀取照片資料，請重新選擇照片。');
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('照片轉換失敗，請重新選擇照片。'));
      reader.onload = () => {
        const result = typeof reader.result === 'string' ? reader.result : '';
        const match = result.match(/^data:[^;]+;base64,(.+)$/);
        match?.[1] ? resolve(match[1].replace(/\s/g, '')) : reject(new Error('照片轉換失敗，請重新選擇照片。'));
      };
      reader.readAsDataURL(blob);
    });
  }
  return FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
}

function isExpiredAuthError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error || '');
  return message.includes('HTTP 401') || message.includes('Invalid or expired bearer token');
}

function formatLoginError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || '');
  if (
    message.includes('INVALID_LOGIN') ||
    message.includes('USER_NOT_FOUND') ||
    message.includes('Username or password') ||
    message.includes('User not found')
  ) {
    return '帳號/密碼有誤';
  }
  return message || '請確認後端位址可連線。';
}

function formatRegisterError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || '');
  if (message.includes('INVALID_USERNAME')) return '帳號名稱需為 3-32 個英文字母、數字或底線。';
  if (message.includes('INVALID_PASSWORD')) return '密碼需至少 10 碼，且只能包含英文與數字，並同時包含英文和數字。';
  if (message.includes('USERNAME_TAKEN')) return '此帳號名稱已被使用。';
  if (message.includes('ACCOUNT_STORE_ERROR')) return '帳號服務暫時無法寫入，請稍後再試。';
  return message || '請確認帳號資料後再試一次。';
}

function showLoginFailurePrompt(message: string): void {
  if (Platform.OS === 'web' && typeof window !== 'undefined' && typeof window.alert === 'function') {
    window.alert(`登入失敗\n${message}`);
    return;
  }
  Alert.alert('登入失敗', message);
}

function formatHomeFeedError(error: string): string {
  const message = error.trim();
  if (!message) return '目前無法載入動態，請下拉重新整理後再試。';
  if (message.includes('HTTP 401') || message.includes('Invalid or expired bearer token')) {
    return '登入狀態已過期，請重新登入後再試。';
  }
  if (
    /^https?:\/\//i.test(message) ||
    message.includes('無法連線到後端') ||
    message.includes('Load failed') ||
    message.includes('Network request failed')
  ) {
    return '目前無法連線到後端，請下拉重新整理；若仍失敗，請重新掃最新 remote QR。';
  }
  if (message.includes('載入逾時')) return '載入逾時，請下拉重新整理後再試。';
  if (message.includes('HTTP 500')) return '後端暫時無法載入動態，請稍後再試。';
  if (message.length > 72) return '目前無法載入動態，請下拉重新整理後再試。';
  return message;
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
  const [showSplash, setShowSplash] = useState(true);
  const [authMode, setAuthMode] = useState<AuthMode>('welcome');
  const [tab, setTab] = useState<MainTab>('首頁');
  const [dataSection, setDataSection] = useState<DataSection>('總覽');
  const [historyDetailItem, setHistoryDetailItem] = useState<HistoryDetailItem | null>(null);
  const [baseUrl, setBaseUrl] = useState(() => getConfiguredApiBaseUrl());
  const [uploadTargetBytes, setUploadTargetBytes] = useState(MOBILE_UPLOAD_TARGET_BYTES);
  const [token, setToken] = useState('');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [registerError, setRegisterError] = useState('');
  const [registerSecurityAnswer, setRegisterSecurityAnswer] = useState('');
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
  const [followListKind, setFollowListKind] = useState<FollowListKind>('followers');
  const [followListProfile, setFollowListProfile] = useState<MobileProfile | null>(null);
  const [followListUsers, setFollowListUsers] = useState<MobileFollowUser[]>([]);
  const [followListError, setFollowListError] = useState('');
  const [loadingFollowList, setLoadingFollowList] = useState(false);
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
  const pendingPostLikeIds = useRef<Set<number>>(new Set());
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
  const [pushNotificationsEnabled, setPushNotificationsEnabled] = useState(true);
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettingsState>(DEFAULT_NOTIFICATION_SETTINGS);
  const [loadingNotificationSettings, setLoadingNotificationSettings] = useState(false);
  const [savingNotificationSettings, setSavingNotificationSettings] = useState(false);
  const registeredPushTokenRef = useRef('');
  const [accountEditField, setAccountEditField] = useState<AccountEditField>('name');
  const [accountEditDraft, setAccountEditDraft] = useState('');
  const [passwordCurrent, setPasswordCurrent] = useState('');
  const [passwordNext, setPasswordNext] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [logoutOtherDevices, setLogoutOtherDevices] = useState(false);
  const [loginHistory, setLoginHistory] = useState<LoginHistoryEntry[]>([]);
  const [loadingLoginHistory, setLoadingLoginHistory] = useState(false);
  const [accountStatusConfirmAction, setAccountStatusConfirmAction] = useState<AccountStatusActionType | null>(null);
  const [accountStatusPassword, setAccountStatusPassword] = useState('');
  const [accountStatusSubmitting, setAccountStatusSubmitting] = useState(false);
  const [favoritePosts, setFavoritePosts] = useState<CommunityPost[]>([]);
  const [loadingFavorites, setLoadingFavorites] = useState(false);
  const [blockedUsers, setBlockedUsers] = useState<MobileBlockedUser[]>([]);
  const [loadingBlockedUsers, setLoadingBlockedUsers] = useState(false);
  const [blockUpdating, setBlockUpdating] = useState(false);
  const [avatarPhoto, setAvatarPhoto] = useState<LocalPhoto | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [showProfileQr, setShowProfileQr] = useState(false);
  const [friendInviteQrPayload, setFriendInviteQrPayload] = useState('');
  const [friendInviteQrExpiresAt, setFriendInviteQrExpiresAt] = useState(0);
  const [friendInviteQrCacheKey, setFriendInviteQrCacheKey] = useState('');
  const [friendInviteQrError, setFriendInviteQrError] = useState('');
  const [friendInviteQrLoading, setFriendInviteQrLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [scanLocked, setScanLocked] = useState(false);
  const [scanJoiningStatus, setScanJoiningStatus] = useState<{ title: string; detail: string } | null>(null);
  const [aiCoachInputFocused, setAiCoachInputFocused] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const photoLoadingMoreRef = useRef(false);
  const feedLoadingRef = useRef(false);
  const publicProfileRequestId = useRef(0);
  const friendInviteQrRequestRef = useRef('');
  const splashOpacity = useRef(new Animated.Value(1)).current;
  const seenPostIds = useRef<Set<number>>(new Set());
  const prefetchedAvatarUrls = useRef<Set<string>>(new Set());
  const prefetchedPostImageUrls = useRef<Set<string>>(new Set());

  const normalizedBaseUrl = useMemo(() => normalizeBaseUrl(baseUrl), [baseUrl]);
  const isSignedIn = Boolean(token && user);

  useEffect(() => {
    if (!token || !normalizedBaseUrl) {
      setFriendInviteQrPayload('');
      setFriendInviteQrExpiresAt(0);
      setFriendInviteQrCacheKey('');
      setFriendInviteQrError('');
      setFriendInviteQrLoading(false);
      return;
    }
    if (!isSignedIn || (tab !== '掃碼' && !showProfileQr)) return;

    const requestKey = `${normalizedBaseUrl}|${token}`;
    const now = Math.floor(Date.now() / 1000);
    const hasFreshQr = friendInviteQrCacheKey === requestKey && Boolean(friendInviteQrPayload) && friendInviteQrExpiresAt > now + 90;
    if (hasFreshQr) {
      setFriendInviteQrError('');
      setFriendInviteQrLoading(false);
      return;
    }
    if (friendInviteQrRequestRef.current === requestKey) return;

    let cancelled = false;
    const loadFriendInviteQr = async () => {
      friendInviteQrRequestRef.current = requestKey;
      if (showProfileQr && !friendInviteQrPayload) setFriendInviteQrLoading(true);
      setFriendInviteQrError('');
      try {
        const invite = await createFriendInviteQr(normalizedBaseUrl, token);
        if (!cancelled) {
          setFriendInviteQrPayload(invite.qr_payload);
          setFriendInviteQrExpiresAt(Number(invite.expires_at || 0));
          setFriendInviteQrCacheKey(requestKey);
        }
      } catch (error) {
        if (!cancelled) {
          if (showProfileQr && !friendInviteQrPayload) setFriendInviteQrPayload('');
          setFriendInviteQrError(error instanceof Error ? error.message : '無法產生好友 QR Code。');
        }
      } finally {
        if (friendInviteQrRequestRef.current === requestKey) friendInviteQrRequestRef.current = '';
        if (!cancelled) setFriendInviteQrLoading(false);
      }
    };
    void loadFriendInviteQr();
    return () => {
      cancelled = true;
    };
  }, [friendInviteQrCacheKey, friendInviteQrExpiresAt, friendInviteQrPayload, isSignedIn, normalizedBaseUrl, showProfileQr, tab, token]);

  useEffect(() => {
    const holdTimer = setTimeout(() => {
      Animated.timing(splashOpacity, {
        toValue: 0,
        duration: 300,
        useNativeDriver: true,
      }).start(() => setShowSplash(false));
    }, 2500);
    return () => clearTimeout(holdTimer);
  }, [splashOpacity]);

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

  const registerPushTokenIfAvailable = async (sessionBaseUrl: string, sessionToken: string) => {
    if (Platform.OS === 'web' || !sessionBaseUrl || !sessionToken) return;
    try {
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'CueVex',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#2563EB',
          sound: 'default',
        });
      }
      const permissions = await Notifications.getPermissionsAsync();
      let status = permissions.status;
      if (status !== 'granted') {
        const requested = await Notifications.requestPermissionsAsync();
        status = requested.status;
      }
      if (status !== 'granted') return;
      const tokenResponse = await Notifications.getExpoPushTokenAsync({ projectId: EAS_PROJECT_ID });
      const expoPushToken = tokenResponse.data;
      if (!expoPushToken || registeredPushTokenRef.current === expoPushToken) return;
      await registerMobilePushToken(sessionBaseUrl, sessionToken, {
        expo_push_token: expoPushToken,
        device: Platform.OS,
        platform: Platform.OS,
      });
      registeredPushTokenRef.current = expoPushToken;
    } catch {
      // Push registration should never block login or settings flows.
    }
  };

  useEffect(() => {
    initializeMobileFirebaseTools().then((runtimeConfig) => {
      setUploadTargetBytes(runtimeConfig.uploadTargetBytes || MOBILE_UPLOAD_TARGET_BYTES);
      if (runtimeConfig.apiBaseUrl && !getExplicitApiBaseUrl()) {
        setBaseUrl((current) => current || runtimeConfig.apiBaseUrl);
      }
    }).catch(() => {
      setUploadTargetBytes(MOBILE_UPLOAD_TARGET_BYTES);
    });
  }, []);

  useEffect(() => {
    loadSession().then((stored) => {
      const configuredBaseUrl = getExplicitApiBaseUrl();
      if (!stored) {
        setBaseUrl(configuredBaseUrl || getConfiguredApiBaseUrl());
        return;
      }
      const effectiveBaseUrl = configuredBaseUrl || stored.baseUrl;
      setBaseUrl(effectiveBaseUrl);
      setToken(stored.token);
      setUser(stored.user);
      if (effectiveBaseUrl !== stored.baseUrl) {
        void saveSession({ ...stored, baseUrl: effectiveBaseUrl });
      }
      void registerPushTokenIfAvailable(effectiveBaseUrl, stored.token);
      void refreshAll({ ...stored, baseUrl: effectiveBaseUrl });
    });
  }, []);

  useEffect(() => {
    if (tab === '\u9996\u9801') return;
    if (tab !== 'AI教練聊天室') setAiCoachInputFocused(false);
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
    setHasMoreRecommended(Boolean(response.hasMoreTrending));
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
      setHasMoreFollowing(Boolean(following.hasMoreFollowing));
      if (!following.hasMoreFollowing) {
        nextItems.push({ type: 'caught_up_banner', id: CAUGHT_UP_BANNER_ID });
        setCurrentMode('RECOMMENDED');
        const trending = await getMobileTrendingFeed(activeBaseUrl, activeToken, FEED_PAGE_SIZE, 0, Array.from(seenPostIds.current));
        const trendingPosts = takeUniqueFeedPosts(trending.posts);
        nextItems.push(...trendingPosts);
        setRecommendedOffset(trending.offset + trending.limit);
        setHasMoreRecommended(Boolean(trending.hasMoreTrending));
      }
      setFeedItems(nextItems);
    } catch (error) {
      try {
        seenPostIds.current = new Set();
        const trending = await getMobileTrendingFeed(activeBaseUrl, activeToken, FEED_PAGE_SIZE, 0, []);
        const trendingPosts = takeUniqueFeedPosts(trending.posts);
        setFeedItems([{ type: 'caught_up_banner', id: CAUGHT_UP_BANNER_ID }, ...trendingPosts]);
        setCurrentMode('RECOMMENDED');
        setFollowingOffset(0);
        setRecommendedOffset(trending.offset + trending.limit);
        setHasMoreFollowing(false);
        setHasMoreRecommended(Boolean(trending.hasMoreTrending));
      } catch (fallbackError) {
        console.warn('Home feed refresh failed', fallbackError);
        setFeedItems([]);
        setCurrentMode('RECOMMENDED');
        setHasMoreFollowing(false);
        setHasMoreRecommended(false);
        setFeedError(fallbackError instanceof Error ? fallbackError.message : '\u7121\u6cd5\u8f09\u5165\u9996\u9801\u52d5\u614b\u3002');
      }
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
        setHasMoreFollowing(Boolean(response.hasMoreFollowing));
        if (!response.hasMoreFollowing) {
          appendCaughtUpBanner();
          setCurrentMode('RECOMMENDED');
          await loadRecommendedFeedPage(normalizedBaseUrl, token, recommendedOffset);
        }
        return;
      }
      await loadRecommendedFeedPage(normalizedBaseUrl, token, recommendedOffset);
    } catch (error) {
      if (currentMode === 'FOLLOWING') {
        try {
          appendCaughtUpBanner();
          setCurrentMode('RECOMMENDED');
          setHasMoreFollowing(false);
          await loadRecommendedFeedPage(normalizedBaseUrl, token, recommendedOffset);
          return;
        } catch (fallbackError) {
          console.warn('Home feed load more fallback failed', fallbackError);
          setHasMoreRecommended(false);
          setFeedError(fallbackError instanceof Error ? fallbackError.message : '\u7121\u6cd5\u8f09\u5165\u66f4\u591a\u8cbc\u6587\u3002');
          return;
        }
      }
      console.warn('Home feed load more failed', error);
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
    void registerPushTokenIfAvailable(normalized, sessionToken);
  };

  const clearLocalSessionState = async () => {
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
    setFollowListProfile(null);
    setFollowListUsers([]);
    setFollowListError('');
    setFeedItems([]);
    setCurrentMode('FOLLOWING');
    setFollowingOffset(0);
    setRecommendedOffset(0);
    setHasMoreFollowing(true);
    setHasMoreRecommended(true);
    seenPostIds.current = new Set();
    setProfileError('');
    setFeedError('');
    setProfileMode('profile');
    setAlbumReturnMode('picker');
    setSelectedPhotos([]);
    setPreviewPhoto(null);
    setAvatarPhoto(null);
    setEditDisplayName('');
    setEditBio('');
    setEditAvatarUrl('');
    setComposeText('');
    await clearSession();
  };

  const refreshAll = async (session?: StoredSession) => {
    const activeBaseUrl = normalizeBaseUrl(session?.baseUrl || normalizedBaseUrl);
    const activeToken = session?.token || token;
    const activeUser = session?.user || user;
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
        const profileData = await getMobileProfile(activeBaseUrl, activeToken);
        setProfile(profileData);
      } catch (profileLoadError) {
        setProfile(null);
        setProfileError(profileLoadError instanceof Error ? profileLoadError.message : '無法載入個人主頁。');
      }
      try {
        const postsData = await getOwnProfilePosts(activeBaseUrl, activeToken, activeUser?.id);
        setMyPosts(postsData.posts);
      } catch (postsLoadError) {
        setMyPosts([]);
      }
      await refreshHomeFeed(activeBaseUrl, activeToken);
    } catch (error) {
      if (isExpiredAuthError(error)) {
        await clearLocalSessionState();
        Alert.alert('登入已過期', '請重新登入後再載入手機端資料。');
        return;
      }
      Alert.alert('同步失敗', error instanceof Error ? error.message : '無法連線到後端。');
    } finally {
      setRefreshing(false);
    }
  };

  const handleLogin = async () => {
    setLoading(true);
    setLoginError('');
    setRegisterError('');
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
      const message = formatLoginError(error);
      setLoginError(message);
      showLoginFailurePrompt(message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    setLoading(true);
    setRegisterError('');
    try {
      const nextUsername = username.trim();
      const nextSecurityAnswer = registerSecurityAnswer.trim();
      if (!/^[A-Za-z0-9_]{3,32}$/.test(nextUsername)) {
        throw new Error('帳號名稱需為 3-32 個英文字母、數字或底線。');
      }
      if (!/^[A-Za-z0-9]{10,}$/.test(password) || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        throw new Error('密碼需至少 10 碼，且只能包含英文與數字，並同時包含英文和數字。');
      }
      if (!nextSecurityAnswer) {
        throw new Error('請輸入安全驗證答案。');
      }
      const activeBaseUrl = normalizeBaseUrl(normalizedBaseUrl || getConfiguredApiBaseUrl());
      if (activeBaseUrl && activeBaseUrl !== baseUrl) {
        setBaseUrl(activeBaseUrl);
      }
      const response = await register(activeBaseUrl, nextUsername, password, 'CueVex 安全驗證', nextSecurityAnswer);
      await persistSession(activeBaseUrl, response.token, response.user);
      setPassword('');
      setRegisterSecurityAnswer('');
      try {
        await refreshAll({ baseUrl: activeBaseUrl, token: response.token, user: response.user });
      } catch (syncError) {
        setRegisterError(syncError instanceof Error ? `帳號已建立，但同步資料失敗：${syncError.message}` : '帳號已建立，但同步資料失敗。');
      }
    } catch (error) {
      const message = formatRegisterError(error);
      setRegisterError(message);
      Alert.alert('註冊失敗', message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      if (token && normalizedBaseUrl) await logout(normalizedBaseUrl, token);
    } catch {
      // Local session cleanup must still run even if the server already revoked the token.
    }
    await clearLocalSessionState();
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

  const startGameFromFriendCode = async (rawCode: string, sourceLabel: string) => {
    const code = rawCode.trim();
    if (!token || !normalizedBaseUrl || !code) {
      Alert.alert('QR Code 無效', '請掃描有效的好友 QR Code。');
      return;
    }
    setLoading(true);
    try {
      await startFriendGameByCode(normalizedBaseUrl, token, code);
      Alert.alert('對戰已建立', `已透過${sourceLabel}建立好友對戰。`);
      await refreshAll();
    } catch (error) {
      Alert.alert('建立對戰失敗', error instanceof Error ? error.message : '請確認好友關係與桌面端後端狀態。');
    } finally {
      setLoading(false);
    }
  };

  const handleSendAiCoachMessage = async (message: string, history: AiCoachChatMessage[], onDelta: AiCoachSendDelta): Promise<AiCoachSendResult> => {
    if (!token || !normalizedBaseUrl) {
      throw new Error('尚未連線到後端，請重新登入或確認 remote QR。');
    }
    const response = await sendCoachChatStream(normalizedBaseUrl, token, {
      message,
      conversation_history: history
        .filter((item) => item.text.trim())
        .slice(-8)
        .map((item) => ({
          role: item.role,
          text: item.text,
          timestamp: item.timestamp,
        })),
      context: {
        source: 'mobile_pwa',
        active_screen: 'ai_coach_chat',
        user: user ? { id: user.id, username: user.username } : null,
        dashboard_stats: dashboard?.stats || null,
        analytics_v1: dashboard?.analytics_v1 || null,
      },
      locale: 'zh-TW',
      coach_session_id: user ? `mobile-${user.id}` : 'mobile-pwa',
      onDelta,
    });
    return response;
  };

  const handleScanProfileQr = async (payload: string) => {
    if (!token || scanLocked) return;
    setScanLocked(true);
    try {
      const parsed = parseUserProfileQrPayload(payload);
      if (parsed.friendInviteToken) {
        const inviteBaseUrl = normalizeBaseUrl(parsed.baseUrl || normalizedBaseUrl);
        if (!inviteBaseUrl) {
          throw new Error('尚未設定後端位址，無法加入好友。');
        }
        setScanJoiningStatus({ title: '正在搜尋使用者', detail: '正在搜尋使用者，完成後會開啟對方主頁。' });
        const acceptedInvite = await acceptFriendInviteQr(inviteBaseUrl, token, payload);
        const acceptedFriend = acceptedInvite.friend as {
          id?: number | string;
          username?: string;
          display_name?: string;
          avatar_url?: string;
          player_level?: string;
        } | undefined;
        const acceptedFriendId = Number(acceptedFriend?.id || 0);
        setScanJoiningStatus(null);
        if (acceptedFriendId) {
          void openPublicProfile({
            userId: acceptedFriendId,
            previewName: acceptedFriend?.display_name || acceptedFriend?.username,
            previewAvatarUrl: acceptedFriend?.avatar_url,
            previewLevel: acceptedFriend?.player_level,
          });
          void refreshAll();
        } else {
          Alert.alert('好友已加入', '你們已成為好友，可以從好友列表建立對戰。');
          void refreshAll();
        }
        return;
      }
      if (parsed.friendMatchToken) {
        const inviteBaseUrl = normalizeBaseUrl(parsed.baseUrl || normalizedBaseUrl);
        if (!inviteBaseUrl) {
          throw new Error('尚未設定後端位址，無法加入桌面端好友對戰。');
        }
        setScanJoiningStatus({ title: '正在加入好友對戰', detail: '正在通知本機端把你加入玩家 2。' });
        await acceptFriendMatchInvite(inviteBaseUrl, token, parsed.friendMatchToken);
        setScanJoiningStatus({
          title: '等待本機端更新',
          detail: '已送出加入請求，正在等待本機端載入玩家 2。',
        });
        await new Promise((resolve) => setTimeout(resolve, 2500));
        setScanJoiningStatus(null);
        return;
      }
      if (!parsed.userId) {
        throw new Error('這不是有效的 CueVex 個人頁 QR。');
      }
      if (parsed.userId === user?.id) {
        throw new Error('不能和自己建立好友對戰。');
      }
      setScanJoiningStatus({ title: '正在建立好友對戰', detail: '正在用 QR Code 建立好友對戰。' });
      await startGameFromFriendCode(String(parsed.userId), 'QR Code');
      setScanJoiningStatus(null);
    } catch (error) {
      setScanJoiningStatus(null);
      Alert.alert('掃描失敗', error instanceof Error ? error.message : '無法建立好友對戰。');
    } finally {
      setTimeout(() => setScanLocked(false), 1200);
    }
  };

  const refreshProfileContent = async (activeBaseUrl = normalizedBaseUrl, activeToken = token) => {
    if (!activeBaseUrl || !activeToken) return;
    setProfileError('');
    try {
      const profileData = await getMobileProfile(activeBaseUrl, activeToken);
      setProfile(profileData);
    } catch (profileLoadError) {
      setProfile(null);
      setProfileError(profileLoadError instanceof Error ? profileLoadError.message : '無法載入個人主頁。');
    }
    try {
      const postsData = await getOwnProfilePosts(activeBaseUrl, activeToken, user?.id);
      setMyPosts(postsData.posts);
    } catch (postsLoadError) {
      setMyPosts([]);
    }
  };

  const getOwnProfilePosts = (activeBaseUrl: string, activeToken: string, activeUserId?: number) => {
    return activeUserId
      ? getMobilePublicProfilePosts(activeBaseUrl, activeToken, activeUserId, 20, 0)
      : getMyCommunityPosts(activeBaseUrl, activeToken);
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
    setFollowListProfile(null);
    setFollowListUsers([]);
    setFollowListError('');
  };

  const closeFollowList = () => {
    setProfileMode('profile');
    setFollowListError('');
  };

  const openFollowList = async (targetProfile: MobileProfile | null, kind: FollowListKind) => {
    if (!targetProfile || !token || !normalizedBaseUrl) return;
    setFollowListKind(kind);
    setFollowListProfile(targetProfile);
    setFollowListUsers([]);
    setFollowListError('');
    setLoadingFollowList(true);
    setProfileMode('followList');
    try {
      const response = await getMobileFollowList(normalizedBaseUrl, token, targetProfile.user.id, kind, 50, 0);
      setFollowListUsers(response.users);
    } catch (error) {
      setFollowListUsers([]);
      setFollowListError(error instanceof Error ? error.message : '無法載入追蹤名單。');
    } finally {
      setLoadingFollowList(false);
    }
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

  const applyPostPhotoSelection = (pickedPhotos: LocalPhoto[]) => {
    setPhotos(pickedPhotos);
    setSelectedPhotos(pickedPhotos);
    setPreviewPhoto(pickedPhotos[0] || null);
    setAlbumOptions(pickedPhotos.length ? [{
      id: 'web-selected',
      title: '已選照片',
      album: null,
      count: pickedPhotos.length,
      coverUri: pickedPhotos[0]?.uri,
    }] : []);
    setPhotoEndCursor(undefined);
    setPhotoHasNextPage(false);
    photoLoadingMoreRef.current = false;
    setPhotoLoadingMore(false);
  };

  const startNewPost = async () => {
    setProfileMode('compose');
    setAlbumReturnMode('picker');
    setSelectedPhotos([]);
    setPreviewPhoto(null);
    setComposeText('');
    setComposePhotoTransforms({});
    setEditingComposePhotoId('');
    setPhotos([]);
    setAlbums([]);
    setAlbumOptions([]);
    setActiveAlbum(null);
    setMediaError('');
  };

  const openPhotoPicker = async () => {
    setAlbumReturnMode('picker');
    setEditingComposePhotoId('');
    setActiveAlbum(null);
    setMediaError('');
    try {
      if (canUseWebPhotoPicker()) {
        const pickedPhotos = await pickWebPhotoFiles(3);
        if (pickedPhotos?.length) applyPostPhotoSelection(pickedPhotos);
        setProfileMode('compose');
        return;
      }
      setProfileMode('picker');
      const mediaPermission = await MediaLibrary.requestPermissionsAsync();
      if (!mediaPermission.granted) {
        setPhotos([]);
        setPhotoEndCursor(undefined);
        setPhotoHasNextPage(false);
        photoLoadingMoreRef.current = false;
        setPhotoLoadingMore(false);
        setMediaError('尚未允許相簿權限。請允許相簿權限後再上傳貼文圖片。');
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
    setEditDisplayName(profile?.display_name?.trim() || '');
    setEditBio(profile?.bio?.trim() || '');
    setEditAvatarUrl(profile?.avatar_url || '');
    setAvatarPhoto(null);
    setProfileMode('editProfile');
  };

  const openAccountEditField = (field: AccountEditField) => {
    setAccountEditField(field);
    if (field === 'name') setAccountEditDraft(editDisplayName);
    if (field === 'username') setAccountEditDraft(user?.username || '');
    if (field === 'bio') setAccountEditDraft(editBio);
    setProfileMode('accountField');
  };

  const openAvatarPicker = async () => {
    setProfileMode('avatarPicker');
    setAlbumReturnMode('avatarPicker');
    setPreviewPhoto(null);
    setActiveAlbum(null);
    setMediaError('');
    try {
      if (canUseWebPhotoPicker()) {
        const pickedPhotos = await pickWebPhotoFiles(1);
        setAlbums([]);
        setPhotoEndCursor(undefined);
        setPhotoHasNextPage(false);
        photoLoadingMoreRef.current = false;
        setPhotoLoadingMore(false);
        if (!pickedPhotos?.length) {
          setPhotos([]);
          setAlbumOptions([]);
          return;
        }
        setPhotos(pickedPhotos);
        setPreviewPhoto(pickedPhotos[0] || null);
        setAlbumOptions([{
          id: 'web-selected',
          title: '已選照片',
          album: null,
          count: pickedPhotos.length,
          coverUri: pickedPhotos[0]?.uri,
        }]);
        return;
      }
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

  const saveMobileProfile = async (nextAvatarPhoto: LocalPhoto | null = avatarPhoto, nextEditAvatarUrl = editAvatarUrl) => {
    if (!token || savingProfile) return;
    setSavingProfile(true);
    try {
      let avatarUrl = nextEditAvatarUrl;
      if (nextAvatarPhoto) {
        const compressedAvatar = await compressPhotoForUpload(nextAvatarPhoto, AVATAR_IMAGE_MAX_EDGE, AVATAR_IMAGE_COMPRESS_QUALITY);
        const data = await readUploadPhotoBase64(compressedAvatar.uri);
        assertWithinMobileUploadTarget(data, uploadTargetBytes);
        const uploaded = await uploadCommunityImages(normalizedBaseUrl, token, [{
          filename: compressedAvatar.uploadFilename,
          mime_type: compressedAvatar.uploadMimeType,
          data,
        }], 'avatar');
        avatarUrl = uploaded.image_urls[0] || '';
        if (!avatarUrl) {
          throw new Error('頭像上傳未回傳圖片網址，請重新選擇照片。');
        }
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

  const saveSelectedAvatarPhoto = async (photo: LocalPhoto) => {
    setAvatarPhoto(photo);
    setPreviewPhoto(photo);
    await saveMobileProfile(photo, editAvatarUrl);
  };

  const removeMobileAvatar = async () => {
    setAvatarPhoto(null);
    setEditAvatarUrl('');
    await saveMobileProfile(null, '');
  };

  const selectAlbum = async (album: MediaLibrary.Album | null) => {
    setActiveAlbum(album);
    if (albumReturnMode !== 'avatarPicker') setSelectedPhotos([]);
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
        const data = await readUploadPhotoBase64(uri);
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
    setFavoritePosts((current) => current.map((post) => (post.id === nextPost.id ? nextPost : post)));
    setFeedItems((current) => current.map((item) => {
      if (isCaughtUpBannerItem(item)) return item;
      return item.id === nextPost.id ? nextPost : item;
    }));
  };

  const updatePostInLists = (postId: number, updater: (post: CommunityPost) => CommunityPost) => {
    setMyPosts((current) => current.map((post) => (post.id === postId ? updater(post) : post)));
    setViewedPosts((current) => current.map((post) => (post.id === postId ? updater(post) : post)));
    setFavoritePosts((current) => current.map((post) => (post.id === postId ? updater(post) : post)));
    setFeedItems((current) => current.map((item) => {
      if (isCaughtUpBannerItem(item)) return item;
      return item.id === postId ? updater(item) : item;
    }));
  };

  const handleTogglePostLike = async (post: CommunityPost) => {
    if (!token) return;
    if (pendingPostLikeIds.current.has(post.id)) return;
    pendingPostLikeIds.current.add(post.id);
    const nextLiked = !post.liked_by_me;
    const nextLikes = Math.max(0, Number(post.likes || 0) + (nextLiked ? 1 : -1));
    const optimisticPost = {
      ...post,
      liked_by_me: nextLiked,
      likes: nextLikes,
    };
    updatePostInLists(post.id, (current) => ({
      ...current,
      liked_by_me: optimisticPost.liked_by_me,
      likes: optimisticPost.likes,
    }));
    try {
      const serverPost = await toggleCommunityLike(normalizedBaseUrl, token, post.id);
      updatePostInList({
        ...serverPost,
        liked_by_me: nextLiked,
        likes: typeof serverPost.likes === 'number' ? serverPost.likes : nextLikes,
      });
    } catch (error) {
      updatePostInLists(post.id, (current) => ({
        ...current,
        liked_by_me: post.liked_by_me,
        likes: post.likes,
      }));
      Alert.alert('按讚失敗', error instanceof Error ? error.message : '無法更新貼文按讚。');
    } finally {
      pendingPostLikeIds.current.delete(post.id);
    }
  };

  const handleTogglePostBookmark = async (post: CommunityPost) => {
    if (!token) return;
    updatePostInLists(post.id, (current) => ({
      ...current,
      bookmarked_by_me: !post.bookmarked_by_me,
    }));
    try {
      updatePostInList(await toggleCommunityBookmark(normalizedBaseUrl, token, post.id));
    } catch (error) {
      updatePostInLists(post.id, (current) => ({
        ...current,
        bookmarked_by_me: post.bookmarked_by_me,
      }));
      Alert.alert('收藏失敗', error instanceof Error ? error.message : '無法更新貼文收藏');
    }
  };

  const saveAccountEditField = async () => {
    if (!token || savingProfile) return;
    const nextValue = accountEditField === 'username' ? accountEditDraft.trim().toLowerCase() : accountEditDraft.trim();
    if (accountEditField === 'username' && !/^[a-z0-9_.]+$/.test(nextValue)) {
      Alert.alert('使用者名稱格式錯誤', '只能使用英文小寫、數字、底線與句點。');
      return;
    }
    setSavingProfile(true);
    try {
      if (accountEditField === 'username') {
        const response = await updateAuthProfile(normalizedBaseUrl, token, nextValue);
        setUser(response.user);
        await saveSession({ baseUrl: normalizedBaseUrl, token, user: response.user });
      } else {
        const nextDisplayName = accountEditField === 'name' ? nextValue : editDisplayName;
        const nextBio = accountEditField === 'bio' ? nextValue : editBio;
        const updatedProfile = await updateMobileProfile(normalizedBaseUrl, token, {
          display_name: nextDisplayName,
          bio: nextBio,
          avatar_url: editAvatarUrl,
        });
        setProfile(updatedProfile);
        setEditDisplayName(updatedProfile.display_name || '');
        setEditBio(updatedProfile.bio || '');
      }
      setProfileMode('editProfile');
      await refreshProfileContent();
    } catch (error) {
      Alert.alert('儲存失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setSavingProfile(false);
    }
  };

  const openAccountSecurity = () => {
    setProfileMode('accountSecurity');
  };

  const openAccountStatus = () => {
    setAccountStatusConfirmAction(null);
    setAccountStatusPassword('');
    setProfileMode('accountStatus');
  };

  const openFavorites = async () => {
    setProfileMode('favorites');
    if (!token || !normalizedBaseUrl) return;
    setLoadingFavorites(true);
    try {
      const response = await getCommunityBookmarks(normalizedBaseUrl, token, 50, 0);
      setFavoritePosts(response.posts || []);
    } catch (error) {
      Alert.alert('收藏載入失敗', error instanceof Error ? error.message : '請稍後再試。');
      setFavoritePosts([]);
    } finally {
      setLoadingFavorites(false);
    }
  };

  const openBlockedSafety = async () => {
    setProfileMode('blockedSafety');
    if (!token || !normalizedBaseUrl) return;
    setLoadingBlockedUsers(true);
    try {
      const response = await getMobileBlocks(normalizedBaseUrl, token);
      setBlockedUsers(response.blocked_users || []);
    } catch (error) {
      Alert.alert('封鎖名單載入失敗', error instanceof Error ? error.message : '請稍後再試。');
      setBlockedUsers([]);
    } finally {
      setLoadingBlockedUsers(false);
    }
  };

  const openNotificationSettings = async () => {
    setProfileMode('notificationSettings');
    if (!token || !normalizedBaseUrl) return;
    setLoadingNotificationSettings(true);
    try {
      const response = await getMobileNotificationSettings(normalizedBaseUrl, token);
      const mapped = applyNotificationSettingsFromApi(response);
      setPushNotificationsEnabled(mapped.pushEnabled);
      setNotificationSettings(mapped.settings);
    } catch (error) {
      Alert.alert('通知設定載入失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setLoadingNotificationSettings(false);
    }
  };

  const applySavedNotificationSettings = (response: MobileNotificationSettings) => {
    const mapped = applyNotificationSettingsFromApi(response);
    setPushNotificationsEnabled(mapped.pushEnabled);
    setNotificationSettings(mapped.settings);
  };

  const togglePushNotificationEnabled = async () => {
    if (!token || !normalizedBaseUrl || savingNotificationSettings) return;
    const previousPush = pushNotificationsEnabled;
    const nextPush = !previousPush;
    setPushNotificationsEnabled(nextPush);
    setSavingNotificationSettings(true);
    try {
      const response = await updateMobileNotificationSettings(normalizedBaseUrl, token, { push_enabled: nextPush });
      applySavedNotificationSettings(response);
      if (nextPush) void registerPushTokenIfAvailable(normalizedBaseUrl, token);
    } catch (error) {
      setPushNotificationsEnabled(previousPush);
      Alert.alert('通知設定儲存失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setSavingNotificationSettings(false);
    }
  };

  const toggleNotificationSetting = async (key: NotificationSettingKey) => {
    if (!token || !normalizedBaseUrl || savingNotificationSettings || !pushNotificationsEnabled) return;
    const previousSettings = notificationSettings;
    const nextValue = !previousSettings[key];
    setNotificationSettings((current) => ({ ...current, [key]: nextValue }));
    setSavingNotificationSettings(true);
    try {
      const response = await updateMobileNotificationSettings(normalizedBaseUrl, token, {
        [NOTIFICATION_SETTING_PAYLOAD_KEYS[key]]: nextValue,
      });
      applySavedNotificationSettings(response);
    } catch (error) {
      setNotificationSettings(previousSettings);
      Alert.alert('通知設定儲存失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setSavingNotificationSettings(false);
    }
  };

  const confirmAccountStatusAction = (action: AccountStatusActionType) => {
    setAccountStatusPassword('');
    setAccountStatusConfirmAction(action);
  };

  const submitAccountStatusAction = async () => {
    if (!token || !accountStatusConfirmAction || accountStatusSubmitting) return;
    if (!accountStatusPassword) {
      Alert.alert('請輸入密碼', '需要輸入密碼才能繼續。');
      return;
    }
    setAccountStatusSubmitting(true);
    try {
      if (accountStatusConfirmAction === 'deactivate') {
        await deactivateAccount(normalizedBaseUrl, token, accountStatusPassword);
        Alert.alert('帳號已停用', '重新登入即可恢復使用。');
      } else {
        await deleteAccount(normalizedBaseUrl, token, accountStatusPassword);
        Alert.alert('帳號已刪除', '此帳號資料已完成刪除。');
      }
      await clearSession();
      setToken('');
      setUser(null);
      setProfile(null);
      setProfileMode('profile');
      setAccountStatusConfirmAction(null);
      setAccountStatusPassword('');
    } catch (error) {
      Alert.alert(accountStatusConfirmAction === 'deactivate' ? '停用帳號失敗' : '刪除帳號失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setAccountStatusSubmitting(false);
    }
  };

  const unblockUser = async (targetUserId: number) => {
    if (!token || blockUpdating) return;
    setBlockUpdating(true);
    try {
      await unblockMobileUser(normalizedBaseUrl, token, targetUserId);
      setBlockedUsers((current) => current.filter((item) => item.user.id !== targetUserId));
    } catch (error) {
      Alert.alert('解除封鎖失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setBlockUpdating(false);
    }
  };

  const openChangePassword = () => {
    setPasswordCurrent('');
    setPasswordNext('');
    setPasswordConfirm('');
    setLogoutOtherDevices(false);
    setProfileMode('changePassword');
  };

  const submitPasswordChange = async () => {
    if (!token || savingProfile) return;
    if (!passwordCurrent || !passwordNext || !passwordConfirm) {
      Alert.alert('請完整填寫', '請輸入密碼、新密碼與確認新密碼。');
      return;
    }
    if (passwordNext !== passwordConfirm) {
      Alert.alert('新密碼不一致', '請確認兩次輸入的新密碼相同。');
      return;
    }
    setSavingProfile(true);
    try {
      await changePassword(normalizedBaseUrl, token, passwordCurrent, passwordNext, logoutOtherDevices);
      Alert.alert('密碼已更新', logoutOtherDevices ? '密碼已更新，其他裝置已登出。' : '密碼已更新。');
      setProfileMode('accountSecurity');
    } catch (error) {
      Alert.alert('更改密碼失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setSavingProfile(false);
    }
  };

  const openLoginDevices = async () => {
    setProfileMode('loginDevices');
    if (!token || !normalizedBaseUrl) return;
    setLoadingLoginHistory(true);
    try {
      const response = await getAuthMe(normalizedBaseUrl, token);
      setLoginHistory((response.login_history || []).filter((entry) => entry.status === 'success'));
    } catch {
      setLoginHistory([]);
    } finally {
      setLoadingLoginHistory(false);
    }
  };

  const toggleAccountPrivacy = async (nextIsPrivate: boolean) => {
    if (!token || savingProfile) return;
    const previousProfile = profile;
    setProfile((current) => current ? { ...current, is_private: nextIsPrivate } : current);
    setSavingProfile(true);
    try {
      const updatedProfile = await updateMobileProfile(normalizedBaseUrl, token, {
        is_private: nextIsPrivate,
      });
      if (updatedProfile.is_private !== nextIsPrivate) {
        throw new Error('後端尚未回傳新的私人帳號狀態，請重新啟動或部署 mobile API。');
      }
      setProfile(updatedProfile);
      setEditDisplayName(updatedProfile.display_name || '');
      setEditBio(updatedProfile.bio || '');
      setEditAvatarUrl(updatedProfile.avatar_url || '');
    } catch (error) {
      setProfile(previousProfile);
      Alert.alert('隱私設定失敗', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setSavingProfile(false);
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
    if (showSplash) {
      return <SplashPage opacity={splashOpacity} />;
    }
    if (!isSignedIn) {
      if (authMode === 'login') {
        return (
          <AuthLoginPage
            username={username}
            setUsername={(value) => {
              setUsername(value);
              setLoginError('');
            }}
            password={password}
            setPassword={(value) => {
              setPassword(value);
              setLoginError('');
            }}
            error={loginError}
            loading={loading}
            onBack={() => setAuthMode('welcome')}
            onLogin={handleLogin}
          />
        );
      }
      if (authMode === 'register') {
        return (
          <RegisterPage
            username={username}
            setUsername={(value) => {
              setUsername(value);
              setRegisterError('');
            }}
            password={password}
            setPassword={(value) => {
              setPassword(value);
              setRegisterError('');
            }}
            securityAnswer={registerSecurityAnswer}
            setSecurityAnswer={(value) => {
              setRegisterSecurityAnswer(value);
              setRegisterError('');
            }}
            error={registerError}
            loading={loading}
            onBack={() => {
              setRegisterError('');
              setAuthMode('welcome');
            }}
            onRegister={handleRegister}
          />
        );
      }
      return <WelcomePage onLogin={() => {
        setLoginError('');
        setRegisterError('');
        setAuthMode('login');
      }} onRegister={() => {
        setLoginError('');
        setRegisterError('');
        setAuthMode('register');
      }} />;
    }
    if (profileMode === 'albums') return <AlbumSelectionPage albums={albumOptions} activeAlbumId={activeAlbum?.id || 'all'} onClose={() => setProfileMode(albumReturnMode === 'avatarPicker' ? 'avatarPicker' : 'picker')} onSelect={(album) => void selectAlbum(album)} />;
    if (profileMode === 'followList') {
      return <FollowListPage profile={followListProfile} activeKind={followListKind} users={followListUsers} loading={loadingFollowList} error={followListError} onBack={closeFollowList} onChangeKind={(kind) => void openFollowList(followListProfile, kind)} onUserPress={openPublicProfile} />;
    }
    if (tab === '首頁') {
      return homeProfileRoute ? (
          <ProfilePage
            user={user}
            profile={(viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? profile : viewedProfile}
            dashboard={dashboard}
            posts={(viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? myPosts : viewedPosts}
            loading={(viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? false : loadingViewedProfile}
            error={viewedProfileError}
            currentAvatarUrl={profile?.avatar_url || ''}
            isOwnProfile={viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId}
            previewName={homeProfileRoute.previewName}
            previewAvatarUrl={homeProfileRoute.previewAvatarUrl}
            previewLevel={homeProfileRoute.previewLevel}
            preferBackButton
            showOwnEditButton={false}
            followUpdating={followUpdating}
            onBack={closePublicProfile}
            onAddPost={startNewPost}
            onRefresh={() => openPublicProfile(homeProfileRoute.userId)}
            onOpenFollowList={(kind) => openFollowList((viewedProfile?.is_self ?? user?.id === homeProfileRoute.userId) ? profile : viewedProfile, kind)}
            onToggleFollow={handleToggleFollowViewedProfile}
            onAuthorPress={openPublicProfile}
            onDeletePost={handleDeletePost}
            onTogglePostLike={handleTogglePostLike}
            onTogglePostBookmark={handleTogglePostBookmark}
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
          onTogglePostBookmark={handleTogglePostBookmark}
          onCreatePostComment={handleCreatePostComment}
          onLoadPostComments={handleLoadPostComments}
          onToggleCommentLike={handleToggleCommentLike}
        />
      );
    }
    if (tab === '掃碼') {
      return (
        <ScanPage
          user={user}
          showProfileQr={showProfileQr}
          setShowProfileQr={setShowProfileQr}
          loading={loading}
          permissionGranted={Boolean(permission?.granted)}
          requestPermission={requestPermission}
          onScan={handleScanProfileQr}
          scanLocked={scanLocked}
          scanJoiningStatus={scanJoiningStatus}
          friendInviteQrPayload={friendInviteQrPayload}
          friendInviteQrLoading={friendInviteQrLoading}
          friendInviteQrError={friendInviteQrError}
        />
      );
    }
    if (tab === 'AI教練聊天室') return <AiCoachChatPage dashboard={dashboard} onSend={handleSendAiCoachMessage} onComposerFocusChange={setAiCoachInputFocused} />;
    if (tab === '我的' && profileMode === 'picker') return <PhotoPickerPage photos={photos} selected={selectedPhotos} albumTitle={activeAlbum?.title || '所有照片'} albumsAvailable={albums.length > 0} error={mediaError} hasMorePhotos={photoHasNextPage} loadingMorePhotos={photoLoadingMore} onLoadMorePhotos={loadMorePhotos} onClose={() => setProfileMode('compose')} onNext={() => selectedPhotos.length && setProfileMode('compose')} onSelect={togglePhoto} onCycleAlbum={cycleAlbum} />;
    if (tab === '我的' && profileMode === 'avatarPicker') return <AvatarPickerPage photos={photos} preview={previewPhoto || avatarPhoto} albumTitle={activeAlbum?.title || '所有照片'} albumsAvailable={albums.length > 0} error={mediaError} hasMorePhotos={photoHasNextPage} loadingMorePhotos={photoLoadingMore} saving={savingProfile} onLoadMorePhotos={loadMorePhotos} onClose={() => setProfileMode('editProfile')} onUse={(photo) => void saveSelectedAvatarPhoto(photo)} onSelect={(photo) => setPreviewPhoto(photo)} onCycleAlbum={cycleAlbum} />;
    if (tab === '我的' && profileMode === 'compose' && editingComposePhotoId) {
      const editingPhoto = selectedPhotos.find((photo) => photo.id === editingComposePhotoId) || selectedPhotos[0];
      if (!editingPhoto) {
        return <ComposePostPage photos={selectedPhotos} transforms={composePhotoTransforms} text={composeText} setText={setComposeText} loading={publishing} error={mediaError} canShare={Boolean(composeText.trim() || selectedPhotos.length)} onClose={() => setProfileMode('profile')} onPickPhotos={openPhotoPicker} onEditPhoto={setEditingComposePhotoId} onShare={sharePost} />;
      }
      return <ComposePhotoEditorPage photo={editingPhoto} transform={composePhotoTransforms[editingPhoto.id] || { x: 0, y: 0, scale: 1 }} onChangeTransform={(nextTransform) => setComposePhotoTransforms((current) => ({ ...current, [editingPhoto.id]: nextTransform }))} onDone={() => setEditingComposePhotoId('')} />;
    }
    if (tab === '我的' && profileMode === 'compose') return <ComposePostPage photos={selectedPhotos} transforms={composePhotoTransforms} text={composeText} setText={setComposeText} loading={publishing} error={mediaError} canShare={Boolean(composeText.trim() || selectedPhotos.length)} onClose={() => setProfileMode('profile')} onPickPhotos={openPhotoPicker} onEditPhoto={setEditingComposePhotoId} onShare={sharePost} />;
    if (tab === '我的' && profileMode === 'editProfile') return <EditProfilePage displayName={editDisplayName} username={user?.username || ''} bio={editBio} avatarUrl={avatarPhoto?.uri || editAvatarUrl} loading={savingProfile} onClose={() => setProfileMode('profile')} onSave={() => void saveMobileProfile()} onPickAvatar={openAvatarPicker} onRemoveAvatar={() => void removeMobileAvatar()} onEditField={openAccountEditField} onOpenSecurity={openAccountSecurity} onOpenStatus={openAccountStatus} />;
    if (tab === '我的' && profileMode === 'accountField') return <AccountFieldEditPage field={accountEditField} value={accountEditDraft} loading={savingProfile} onChangeValue={setAccountEditDraft} onBack={() => setProfileMode('editProfile')} onSave={saveAccountEditField} />;
    if (tab === '我的' && profileMode === 'accountSecurity') return <AccountSecurityPage onBack={() => setProfileMode('editProfile')} onChangePassword={openChangePassword} onLoginDevices={openLoginDevices} />;
    if (tab === '我的' && profileMode === 'changePassword') return <ChangePasswordPage currentPassword={passwordCurrent} nextPassword={passwordNext} confirmPassword={passwordConfirm} logoutOtherDevices={logoutOtherDevices} loading={savingProfile} onChangeCurrent={setPasswordCurrent} onChangeNext={setPasswordNext} onChangeConfirm={setPasswordConfirm} onToggleLogoutOthers={() => setLogoutOtherDevices((current) => !current)} onBack={() => setProfileMode('accountSecurity')} onSubmit={submitPasswordChange} />;
    if (tab === '我的' && profileMode === 'loginDevices') return <LoginDevicesPage history={loginHistory} loading={loadingLoginHistory} onBack={() => setProfileMode('accountSecurity')} />;
    if (tab === '我的' && profileMode === 'accountPrivacy') return <AccountPrivacyPage isPrivate={Boolean(profile?.is_private)} loading={savingProfile} onBack={() => setProfileMode('settings')} onToggle={toggleAccountPrivacy} />;
    if (tab === '我的' && profileMode === 'accountStatus') return <AccountStatusPage confirming={accountStatusConfirmAction} password={accountStatusPassword} loading={accountStatusSubmitting} onBack={() => setProfileMode('editProfile')} onChangePassword={setAccountStatusPassword} onCancelConfirm={() => setAccountStatusConfirmAction(null)} onConfirmAction={confirmAccountStatusAction} onSubmitConfirm={submitAccountStatusAction} />;
    if (tab === '我的' && profileMode === 'favorites') return <FavoritesPage posts={favoritePosts} loading={loadingFavorites} currentUserId={user?.id || 0} currentAvatarUrl={profile?.avatar_url || ''} currentPlayerLevel={profile?.player_level || ''} onBack={() => setProfileMode('settings')} onDelete={handleDeletePost} onAuthorPress={openPublicProfile} onToggleLike={handleTogglePostLike} onToggleBookmark={handleTogglePostBookmark} onCreateComment={handleCreatePostComment} onLoadComments={handleLoadPostComments} onToggleCommentLike={handleToggleCommentLike} />;
    if (tab === '我的' && profileMode === 'blockedSafety') return <BlockedSafetyPage users={blockedUsers} loading={loadingBlockedUsers} updating={blockUpdating} onBack={() => setProfileMode('settings')} onUnblock={unblockUser} />;
    if (tab === '我的' && profileMode === 'notificationSettings') return <NotificationSettingsPage pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('settings')} onTogglePush={togglePushNotificationEnabled} onOpenPost={() => setProfileMode('notificationPostInteraction')} onOpenComment={() => setProfileMode('notificationCommentInteraction')} onOpenFriends={() => setProfileMode('notificationFriends')} onOpenSystem={() => setProfileMode('notificationSystem')} onOpenDisplay={() => setProfileMode('notificationDisplayMode')} onOpenQuietHours={() => setProfileMode('notificationQuietHours')} />;
    if (tab === '我的' && profileMode === 'notificationPostInteraction') return <NotificationSectionTogglePage title="貼文互動" items={[{ key: 'postLikes', label: '有人按讚我的貼文' }, { key: 'postComments', label: '有人留言我的貼文' }]} settings={notificationSettings} pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('notificationSettings')} onToggleSetting={toggleNotificationSetting} />;
    if (tab === '我的' && profileMode === 'notificationCommentInteraction') return <NotificationSectionTogglePage title="留言互動" items={[{ key: 'commentReplies', label: '有人回覆我的留言' }, { key: 'commentLikes', label: '有人按讚我的留言' }]} settings={notificationSettings} pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('notificationSettings')} onToggleSetting={toggleNotificationSetting} />;
    if (tab === '我的' && profileMode === 'notificationFriends') return <NotificationSectionTogglePage title="追蹤與好友" items={[{ key: 'newFollowers', label: '有人追蹤我' }, { key: 'mutualFollows', label: '互相關注' }]} settings={notificationSettings} pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('notificationSettings')} onToggleSetting={toggleNotificationSetting} />;
    if (tab === '我的' && profileMode === 'notificationSystem') return <NotificationSectionTogglePage title="系統通知" items={[{ key: 'accountSecurity', label: '帳號安全提醒' }, { key: 'loginChanges', label: '密碼或登入狀態變更' }, { key: 'serviceAnnouncements', label: '服務公告' }]} settings={notificationSettings} pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('notificationSettings')} onToggleSetting={toggleNotificationSetting} />;
    if (tab === '我的' && profileMode === 'notificationDisplayMode') return <NotificationSectionTogglePage title="通知顯示方式" items={[{ key: 'showPreview', label: '顯示通知預覽' }, { key: 'typeOnly', label: '只顯示通知類型，不顯示內容' }]} settings={notificationSettings} pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('notificationSettings')} onToggleSetting={toggleNotificationSetting} />;
    if (tab === '我的' && profileMode === 'notificationQuietHours') return <NotificationSectionTogglePage title="靜音時段" items={[{ key: 'quietHours', label: '靜音時段' }]} settings={notificationSettings} pushEnabled={pushNotificationsEnabled} loading={loadingNotificationSettings} saving={savingNotificationSettings} onBack={() => setProfileMode('notificationSettings')} onToggleSetting={toggleNotificationSetting} />;
    if (tab === '我的' && profileMode === 'settings') return <CommunitySettingsPage onBack={() => setProfileMode('profile')} onEditProfile={openEditProfile} onOpenPrivacy={() => setProfileMode('accountPrivacy')} onOpenNotifications={openNotificationSettings} onOpenFavorites={openFavorites} onOpenBlockedSafety={openBlockedSafety} onLogout={handleLogout} />;
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
          currentAvatarUrl={profile?.avatar_url || ''}
          isOwnProfile={!isViewingOtherProfile}
          followUpdating={followUpdating}
          onBack={isViewingOtherProfile ? closePublicProfile : undefined}
          onAddPost={startNewPost}
          onRefresh={() => isViewingOtherProfile ? openPublicProfile(viewedProfileUserId) : refreshAll()}
          onOpenSettings={() => setProfileMode('settings')}
          onOpenFollowList={(kind) => openFollowList(profile, kind)}
          onToggleFollow={handleToggleFollowViewedProfile}
          onAuthorPress={openPublicProfile}
          onDeletePost={handleDeletePost}
          onTogglePostLike={handleTogglePostLike}
          onTogglePostBookmark={handleTogglePostBookmark}
          onCreatePostComment={handleCreatePostComment}
          onLoadPostComments={handleLoadPostComments}
          onToggleCommentLike={handleToggleCommentLike}
          onLogout={handleLogout}
        />
      );
    }
    if (dataSection === '歷史紀錄') {
      return historyDetailItem
        ? <HistoryDetailPage item={historyDetailItem} onBack={() => setHistoryDetailItem(null)} />
        : <MatchHistoryPage value={dataSection} onChange={setDataSection} dashboard={dashboard} onOpenDetail={setHistoryDetailItem} />;
    }
    if (dataSection === '進攻數據') return <OffenseDataPage value={dataSection} onChange={setDataSection} dashboard={dashboard} />;
    if (dataSection === '球型表現') return <BallShapePerformancePage value={dataSection} onChange={setDataSection} dashboard={dashboard} />;
    return <DataOverviewPageV2 value={dataSection} onChange={setDataSection} dashboard={dashboard} />;
  };

  const RootView = Platform.OS === 'web' ? View : SafeAreaView;
  const isCreatorMode = isSignedIn && (profileMode === 'followList' || (tab === '我的' && (profileMode === 'picker' || profileMode === 'albums' || profileMode === 'compose' || profileMode === 'editProfile' || profileMode === 'avatarPicker' || profileMode === 'settings' || profileMode === 'accountField' || profileMode === 'accountSecurity' || profileMode === 'changePassword' || profileMode === 'loginDevices' || profileMode === 'accountPrivacy' || profileMode === 'accountStatus' || profileMode === 'favorites' || profileMode === 'blockedSafety' || profileMode === 'notificationSettings' || profileMode === 'notificationPostInteraction' || profileMode === 'notificationCommentInteraction' || profileMode === 'notificationFriends' || profileMode === 'notificationSystem' || profileMode === 'notificationDisplayMode' || profileMode === 'notificationQuietHours')));
  const isHomeScrollManaged = isSignedIn && tab === '首頁';
  const isProfileScrollManaged = isSignedIn && tab === '我的' && profileMode === 'profile';
  const isCoachChatManaged = isSignedIn && tab === 'AI教練聊天室';
  const shouldShowBottomNav = isSignedIn && !showSplash && !isCreatorMode && !(isCoachChatManaged && aiCoachInputFocused);
  const isAuthMode = showSplash || !isSignedIn;
  const contentNode = renderContent();

  return (
    <RootView style={[styles.shell, Platform.OS === 'web' && styles.shellWeb]}>
      <StatusBar barStyle="dark-content" />
      <View style={Platform.OS === 'web' ? [styles.phoneWeb, phoneWebTopSafeAreaStyle] : styles.phone}>
        {isAuthMode ? (
          <View style={styles.authContentFrame}>{contentNode}</View>
        ) : isHomeScrollManaged ? (
          <View style={styles.homeContentFrame}>{contentNode}</View>
        ) : isProfileScrollManaged ? (
          <View style={styles.profileContentFrame}>{contentNode}</View>
        ) : isCoachChatManaged ? (
          <View style={[styles.coachChatContentFrame, aiCoachInputFocused ? coachChatKeyboardInsetStyle : coachChatContentInsetStyle]}>{contentNode}</View>
        ) : isCreatorMode ? (
          <View style={styles.contentFrame}>{contentNode}</View>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[styles.content, bottomNavOverlayContentInsetStyle]}>
            {contentNode}
          </ScrollView>
        )}
        {shouldShowBottomNav ? <BottomNav active={tab} onChange={setTab} /> : null}
      </View>
    </RootView>
  );
}

function SplashPage({ opacity }: { opacity: Animated.Value }) {
  return (
    <Animated.View style={[styles.splashPage, { opacity }]}>
      <Image source={cueVexLogo} style={styles.splashLogo} resizeMode="contain" />
    </Animated.View>
  );
}

function WelcomePage({ onLogin, onRegister }: { onLogin: () => void; onRegister: () => void }) {
  return (
    <View style={styles.welcomePage}>
      <View style={styles.welcomeTop}>
        <Text style={styles.welcomeTitle}>歡迎使用</Text>
        <Image source={cueVexLogo} style={styles.welcomeLogo} resizeMode="contain" />
      </View>
      <View style={styles.authActions}>
        <Pressable style={styles.authPrimaryButton} onPress={onLogin}>
          <Text style={styles.authPrimaryButtonText}>使用現有帳號</Text>
        </Pressable>
        <Pressable style={styles.authSecondaryButton} onPress={onRegister}>
          <Text style={styles.authSecondaryButtonText}>註冊新帳號</Text>
        </Pressable>
      </View>
    </View>
  );
}

function AuthKeyboardPage({ children }: { children: React.ReactNode }) {
  if (Platform.OS === 'web') {
    return (
      <View style={styles.authKeyboardPage}>
        <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false} contentContainerStyle={[styles.authScrollContent, styles.authScrollContentWeb]}>
          {children}
        </ScrollView>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.authKeyboardPage} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false} contentContainerStyle={styles.authScrollContent}>
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function AuthLoginPage(props: {
  username: string;
  setUsername: (value: string) => void;
  password: string;
  setPassword: (value: string) => void;
  error: string;
  loading: boolean;
  onBack: () => void;
  onLogin: () => void;
}) {
  return (
    <AuthKeyboardPage>
      <View style={styles.authTopRow}>
        <Pressable onPress={props.onBack} hitSlop={12}>
          <Text style={styles.authBackText}>返回</Text>
        </Pressable>
      </View>
      <View style={styles.authForm}>
        <Text style={styles.loginTitle}>登入CueVex</Text>
        <Input label="帳號名稱" value={props.username} onChangeText={props.setUsername} placeholder="Player001" />
        <Input label="密碼" value={props.password} onChangeText={props.setPassword} placeholder="Password123" secureTextEntry />
        {props.error ? (
          <View style={styles.authErrorBox}>
            <Text style={styles.authErrorText}>{props.error}</Text>
          </View>
        ) : null}
        <Pressable style={styles.authPrimaryButton} onPress={props.onLogin} disabled={props.loading}>
          {props.loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.authPrimaryButtonText}>登入</Text>}
        </Pressable>
      </View>
    </AuthKeyboardPage>
  );
}

function RegisterPage(props: {
  username: string;
  setUsername: (value: string) => void;
  password: string;
  setPassword: (value: string) => void;
  securityAnswer: string;
  setSecurityAnswer: (value: string) => void;
  error: string;
  loading: boolean;
  onBack: () => void;
  onRegister: () => void;
}) {
  return (
    <AuthKeyboardPage>
      <View style={styles.authTopRow}>
        <Pressable onPress={props.onBack} hitSlop={12}>
          <Text style={styles.authBackText}>返回</Text>
        </Pressable>
      </View>
      <View style={styles.authForm}>
        <Text style={styles.loginTitle}>註冊CueVex</Text>
        <Input label="帳號名稱" value={props.username} onChangeText={props.setUsername} placeholder="Player001" />
        <Input label="密碼" value={props.password} onChangeText={props.setPassword} placeholder="Password123" secureTextEntry />
        <Input label="安全驗證答案" value={props.securityAnswer} onChangeText={props.setSecurityAnswer} placeholder="輸入日後驗證用答案" secureTextEntry />
        <Text style={styles.authHelperText}>帳號 3-32 碼，可用英文、數字與底線。密碼至少 10 碼，需同時包含英文與數字。</Text>
        {props.error ? (
          <View style={styles.authErrorBox}>
            <Text style={styles.authErrorText}>{props.error}</Text>
          </View>
        ) : null}
        <Pressable style={styles.authPrimaryButton} onPress={props.onRegister} disabled={props.loading}>
          {props.loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.authPrimaryButtonText}>建立帳號</Text>}
        </Pressable>
      </View>
    </AuthKeyboardPage>
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
  onTogglePostBookmark,
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
  onTogglePostBookmark: (post: CommunityPost) => void;
  onCreatePostComment: (post: CommunityPost, body: string) => Promise<CommunityComment | undefined>;
  onLoadPostComments: (post: CommunityPost) => Promise<CommunityComment[]>;
  onToggleCommentLike: (comment: CommunityComment) => Promise<CommunityComment>;
}) {
  const stats = dashboard?.stats;
  const score = Math.round((stats?.total_wins || 0) * 25 + (stats?.total_games || 0) * 5);
  const winRate = stats ? `${Math.round(stats.win_rate * 100)}%` : '--';
  const displayName = user?.username || 'CueVex';
  const avatarUrl = profile?.avatar_url || '';
  const feedErrorMessage = formatHomeFeedError(feedError);
  const playerLevel = profile?.player_level || '新手玩家 I';
  return (
    <FlatList
      data={feedItems}
      keyExtractor={(item) => (isCaughtUpBannerItem(item) ? item.id : `post-${item.id}`)}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={[styles.homeFeedContent, bottomNavOverlayContentInsetStyle]}
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
            currentAvatarUrl={avatarUrl}
            currentUserId={user?.id || 0}
            currentPlayerLevel={playerLevel}
            onDelete={onDeletePost}
            onAuthorPress={onAuthorPress}
            onToggleLike={onTogglePostLike}
            onToggleBookmark={onTogglePostBookmark}
            onCreateComment={onCreatePostComment}
            onLoadComments={onLoadPostComments}
            onToggleCommentLike={onToggleCommentLike}
          />
        );
      }}
      ListFooterComponent={feedError ? (
        <View style={styles.feedErrorBox}>
          <Text style={styles.feedErrorTitle}>{'\u52d5\u614b\u8f09\u5165\u5931\u6557'}</Text>
          <Text style={styles.feedErrorText}>{feedErrorMessage}</Text>
          <Text style={styles.feedErrorHint}>{'\u4e0b\u62c9\u91cd\u65b0\u6574\u7406'}</Text>
        </View>
      ) : loadingFeed ? <View style={styles.feedFooter}><ActivityIndicator color={purple} /></View> : null}
    />
  );
}

type OverviewChartKey = 'practice_trend' | 'accuracy_trend';
type OverviewChartPointData = {
  x: string;
  y: number;
  label?: string;
  week_start_label?: string;
  week_end_label?: string;
  practice_hours?: number;
  shot_count?: number;
  pot_count?: number;
  pot_rate?: number;
};
type OverviewChartSeriesData = {
  title: string;
  x_label: string;
  y_label: string;
  status: string;
  points: OverviewChartPointData[];
};

function formatOverviewDate(value?: string) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`;
}

function formatMetricValue(value: number | null | undefined, suffix = '') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
  return `${value}${suffix}`;
}

function formatDurationHours(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return '--';
  const hours = Number(seconds) / 3600;
  return `${hours.toFixed(hours >= 10 ? 0 : 1)} 小時`;
}

function monthLabelFromChartPoint(point?: OverviewChartPointData, fallback = '') {
  const source = point?.week_start_label || point?.label || point?.x || fallback;
  const match = String(source).match(/(\d{1,2})月|^(\d{1,2})\//);
  const month = match?.[1] || match?.[2];
  return month ? `${Number(month)}月` : fallback;
}

function DataOverviewPageV2({ value, onChange, dashboard }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null }) {
  const [activeChart, setActiveChart] = useState<OverviewChartKey>('practice_trend');
  const [activeOverviewCard, setActiveOverviewCard] = useState(0);
  const [selectedChartPointIndex, setSelectedChartPointIndex] = useState(-1);
  const analytics = dashboard?.analytics_v1;
  const overview = analytics?.overview;
  const weekly = analytics?.weekly_summary;
  const chartSeries = analytics?.chart_series;
  const overviewCardWidth = Math.min(getPostMediaWidth() - 40, 390);
  const currentChart: OverviewChartSeriesData = chartSeries?.[activeChart] || {
    title: activeChart === 'practice_trend' ? '練習趨勢' : '進球準度',
    x_label: '時間',
    y_label: activeChart === 'practice_trend' ? '練習次數' : '進球率',
    status: 'pending_desktop_sync',
    points: [],
  };
  const chartPoints = Array.isArray(currentChart.points) ? currentChart.points : [];
  const activeSelectedIndex = chartPoints.length ? (selectedChartPointIndex >= 0 ? Math.min(selectedChartPointIndex, chartPoints.length - 1) : chartPoints.length - 1) : -1;
  const selectedPoint = activeSelectedIndex >= 0 ? chartPoints[activeSelectedIndex] : undefined;
  const isLatestSelectedPoint = chartPoints.length > 0 && activeSelectedIndex === chartPoints.length - 1;
  const selectedWeekRange = selectedPoint?.week_start_label && selectedPoint?.week_end_label
    ? (isLatestSelectedPoint ? '本週' : `${selectedPoint.week_start_label} - ${selectedPoint.week_end_label}`)
    : '';
  const summaryPracticeHours = selectedPoint?.practice_hours ?? weekly?.practice_hours ?? null;
  const summaryShotCount = selectedPoint?.shot_count ?? weekly?.shot_count ?? null;
  const summaryChartValue = activeChart === 'practice_trend'
    ? selectedPoint?.pot_count ?? weekly?.pot_count ?? null
    : selectedPoint?.pot_rate ?? weekly?.pot_rate ?? null;
  const summaryChartLabel = activeChart === 'practice_trend' ? '進球數' : '進球率';
  const summaryChartUnit = activeChart === 'practice_trend' ? '顆' : '%';
  const scoreBasis = overview?.score_basis || analytics?.score_basis || '根據練習模式紀錄推估，不包含對戰勝負';
  const recentGames = dashboard?.recent_games || [];
  const recentPractice = dashboard?.recent_practice || [];
  const totalGames = dashboard?.stats?.total_games ?? overview?.total_battle_matches ?? 0;
  const totalWins = dashboard?.stats?.total_wins ?? 0;
  const winRate = dashboard?.stats?.win_rate ?? 0;
  const overviewCards = [
    (
      <View style={[styles.overviewSwipeCard, { width: overviewCardWidth }]} key="joined">
        <Text style={styles.overviewCardLabel}>加入日期</Text>
        <Text style={styles.overviewCardValue}>{formatOverviewDate(overview?.joined_at || dashboard?.user?.created_at)}</Text>
        <View style={styles.overviewCardPair}>
          <Text style={styles.overviewCardSubLabel}>已加入</Text>
          <Text style={styles.overviewCardSubValue}>{formatMetricValue(overview?.joined_days, ' 天')}</Text>
        </View>
      </View>
    ),
    (
      <View style={[styles.overviewSwipeCard, { width: overviewCardWidth }]} key="status">
        <Text style={styles.overviewCardLabel}>累積狀態</Text>
        <View style={styles.overviewTwoCols}>
          <View>
            <Text style={styles.overviewCardValue}>{formatMetricValue(overview?.total_practice_sessions ?? dashboard?.stats?.total_practice_sessions, ' 次')}</Text>
            <Text style={styles.overviewCardSubLabel}>總練習次數</Text>
          </View>
          <View>
            <Text style={styles.overviewCardValue}>{formatMetricValue(overview?.total_battle_matches ?? dashboard?.stats?.total_games, ' 場')}</Text>
            <Text style={styles.overviewCardSubLabel}>對戰次數</Text>
          </View>
        </View>
      </View>
    ),
    (
      <View style={[styles.overviewSwipeCard, { width: overviewCardWidth }]} key="rank">
        <Text style={styles.overviewCardLabel}>積分與段位</Text>
        <View style={styles.overviewScoreLine}>
          <Text style={styles.overviewScoreValue}>{overview?.overall_score ?? analytics?.overall_score ?? '--'}</Text>
          <Text style={styles.overviewScoreMax}>/ 100</Text>
        </View>
        <Text style={styles.overviewCardSubValue}>{overview?.level_label || analytics?.level_label || '等待練習資料'}</Text>
        <Text style={styles.overviewBasis} numberOfLines={2}>{scoreBasis}</Text>
      </View>
    ),
  ];
  const handleOverviewScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const offsetX = event.nativeEvent.contentOffset.x;
    const index = Math.max(0, Math.min(overviewCards.length - 1, Math.round(offsetX / overviewCardWidth)));
    setActiveOverviewCard(index);
  };

  useEffect(() => {
    setSelectedChartPointIndex(chartPoints.length ? chartPoints.length - 1 : -1);
  }, [activeChart, chartPoints.length]);

  return (
    <View style={styles.stack}>
      <DataSelector value={value} onChange={onChange} />

      <ScrollView
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={handleOverviewScrollEnd}
        contentContainerStyle={styles.overviewCardStrip}
      >
        {overviewCards}
      </ScrollView>
      <View style={styles.overviewDots}>
        {overviewCards.map((_, index) => (
          <View key={index} style={[styles.overviewDot, activeOverviewCard === index && styles.overviewDotActive]} />
        ))}
      </View>

      <Card>
        <Text style={styles.sectionTitle}>練習統計</Text>
        <View style={styles.weeklyMetricGrid}>
          <WeeklyMetric label="練習" unit="次" value={dashboard?.stats?.total_practice_sessions ?? overview?.total_practice_sessions ?? 0} />
          <View style={styles.weeklyMetricItem}>
            <Text style={styles.weeklyMetricLabel}>總時長</Text>
            <Text style={styles.weeklyMetricValue}>{formatDurationHours(dashboard?.stats?.total_practice_seconds)}</Text>
          </View>
          <WeeklyMetric label="本週" unit="小時" value={weekly?.practice_hours ?? null} />
        </View>
        {recentPractice.length ? (
          <View style={styles.trainingList}>
            {recentPractice.slice(0, 3).map((practice) => (
              <View key={practice.game_id} style={styles.trainingRow}>
                <View style={styles.trainingBadge}>
                  <Text style={styles.trainingBadgeText}>{Math.max(1, Math.round((practice.duration_seconds || 0) / 60))}</Text>
                </View>
                <View style={styles.trainingCopy}>
                  <Text style={styles.trainingTitle}>{practice.practice_type}</Text>
                  <Text style={styles.trainingReason}>{formatOverviewDate(practice.date)}</Text>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.overviewBasis}>目前尚無練習紀錄，完成練習後會顯示在這裡。</Text>
        )}
      </Card>

      <Card>
        <Text style={styles.sectionTitle}>對戰統計</Text>
        <View style={styles.weeklyMetricGrid}>
          <WeeklyMetric label="對戰" unit="場" value={totalGames} />
          <WeeklyMetric label="勝場" unit="場" value={totalWins} />
          <WeeklyMetric label="勝率" unit="%" value={Math.round(winRate * 100)} />
        </View>
        {recentGames.length ? (
          <View style={styles.trainingList}>
            {recentGames.slice(0, 3).map((game) => (
              <View key={game.game_id} style={styles.trainingRow}>
                <View style={styles.trainingBadge}>
                  <Text style={styles.trainingBadgeText}>{game.result === 'win' ? '勝' : game.result === 'loss' ? '敗' : '和'}</Text>
                </View>
                <View style={styles.trainingCopy}>
                  <Text style={styles.trainingTitle}>{game.score || '-'}</Text>
                  <Text style={styles.trainingReason}>對手：{game.opponent || '未知'}</Text>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.overviewBasis}>目前尚無對戰紀錄，完成一場對戰後會顯示在這裡。</Text>
        )}
      </Card>

      <View style={styles.weeklySummaryBlock}>
        <Text style={styles.sectionTitle}>{selectedWeekRange || '本週摘要'}</Text>
        <View style={styles.weeklyMetricGrid}>
          <WeeklyMetric label="時間" unit="小時" value={summaryPracticeHours} />
          <WeeklyMetric label="擊球數" unit="顆" value={summaryShotCount} />
          <WeeklyMetric label={summaryChartLabel} unit={summaryChartUnit} value={summaryChartValue} />
        </View>
      </View>

      <View style={styles.chartSection}>
        <View style={styles.chartTabs}>
          {(['practice_trend', 'accuracy_trend'] as const).map((chartKey) => (
            <Pressable key={chartKey} style={[styles.chartTab, activeChart === chartKey && styles.chartTabActive]} onPress={() => setActiveChart(chartKey)}>
              <Text style={[styles.chartTabText, activeChart === chartKey && styles.chartTabTextActive]}>
                {chartKey === 'practice_trend' ? '練習趨勢' : '進球準度'}
              </Text>
            </Pressable>
          ))}
        </View>
        <OverviewLineChart series={currentChart} selectedIndex={activeSelectedIndex} onSelectPoint={setSelectedChartPointIndex} />
      </View>

    </View>
  );
}

function WeeklyMetric({ label, unit, value }: { label: string; unit: string; value: number | null }) {
  return (
    <View style={styles.weeklyMetricItem}>
      <Text style={styles.weeklyMetricLabel}>{label}</Text>
      <View style={styles.weeklyMetricValueRow}>
        <Text style={styles.weeklyMetricValue}>{value === null ? '--' : value}</Text>
        <Text style={styles.weeklyMetricUnit}>{unit}</Text>
      </View>
    </View>
  );
}

function OverviewLineChart({ series, selectedIndex, onSelectPoint }: { series: OverviewChartSeriesData; selectedIndex: number; onSelectPoint: (index: number) => void }) {
  const width = Math.min(getPostMediaWidth() - 40, 390);
  const height = 190;
  const chartLeft = 30;
  const chartTop = 20;
  const chartWidth = width - 42;
  const chartHeight = 118;
  const points = Array.isArray(series.points) ? series.points : [];
  const hasPoints = points.length > 0 && series.status === 'ready';
  const yValues = points.map((point) => Number(point.y)).filter((point) => Number.isFinite(point));
  const minY = yValues.length ? Math.min(...yValues, 0) : 0;
  const maxY = yValues.length ? Math.max(...yValues, 1) : 1;
  const yRange = maxY - minY || 1;
  const chartPoints = points.map((point, index) => {
    const x = chartLeft + (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
    const y = chartTop + chartHeight - ((Number(point.y) - minY) / yRange) * chartHeight;
    return `${x},${y}`;
  }).join(' ');
  const pointPositions = points.map((point, index) => {
    const x = chartLeft + (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
    const y = chartTop + chartHeight - ((Number(point.y) - minY) / yRange) * chartHeight;
    return { x, y, value: Math.round(Number(point.y)) };
  });
  const activePoint = hasPoints && selectedIndex >= 0 ? pointPositions[Math.min(selectedIndex, pointPositions.length - 1)] : undefined;
  const unit = series.y_label.includes('率') ? '%' : '顆';
  const firstMonthIndex = hasPoints ? Math.min(1, points.length - 1) : 1;
  const middleMonthIndex = hasPoints ? Math.floor((points.length - 1) / 2) : 6;
  const lastMonthIndex = hasPoints ? Math.max(0, points.length - 2) : 11;
  const xMonthTicks = hasPoints
    ? [
      { index: firstMonthIndex, label: monthLabelFromChartPoint(points[firstMonthIndex], '4月') },
      { index: middleMonthIndex, label: monthLabelFromChartPoint(points[middleMonthIndex], '5月') },
      { index: lastMonthIndex, label: monthLabelFromChartPoint(points[lastMonthIndex], '6月') },
    ]
    : [
      { index: 1, label: '4月' },
      { index: 6, label: '5月' },
      { index: 11, label: '6月' },
    ];
  const yTickValues = hasPoints
    ? [maxY, minY + yRange / 2, minY].map((item) => Math.round(item))
    : ['高', '中', '低'];
  const valueLabel = activePoint ? `${activePoint.value}${unit}` : '';

  return (
    <View style={styles.overviewChartWrap}>
      <View>
        <Text style={styles.sectionTitle}>{series.title}</Text>
      </View>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        {[0, 0.5, 1].map((ratio, index) => {
          const y = chartTop + chartHeight * ratio;
          return (
            <React.Fragment key={`grid-${ratio}`}>
              <Line x1={chartLeft} y1={y} x2={chartLeft + chartWidth} y2={y} stroke="#EEF2F7" strokeWidth="1" />
              <SvgText x={chartLeft - 10} y={y + 4} fill="#6B7280" fontSize="10" textAnchor="end">
                {hasPoints ? `${String(yTickValues[index])}${unit}` : String(yTickValues[index])}
              </SvgText>
            </React.Fragment>
          );
        })}
        <Line x1={chartLeft} y1={chartTop} x2={chartLeft} y2={chartTop + chartHeight} stroke="#E5E7EB" strokeWidth="1" />
        <Line x1={chartLeft} y1={chartTop + chartHeight} x2={chartLeft + chartWidth} y2={chartTop + chartHeight} stroke="#E5E7EB" strokeWidth="1" />
        {hasPoints ? (
          <>
            {pointPositions.map((point, index) => {
              const active = index === selectedIndex;
              return (
                <Line
                  key={`v-${index}`}
                  x1={point.x}
                  y1={chartTop}
                  x2={point.x}
                  y2={chartTop + chartHeight}
                  stroke={active ? purple : '#E5E7EB'}
                  strokeWidth={active ? '2' : '1'}
                />
              );
            })}
            <Polyline points={chartPoints} fill="none" stroke={purple} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            {points.map((point, index) => {
              const [cx, cy] = chartPoints.split(' ')[index].split(',').map(Number);
              return <Circle key={`${point.x}-${index}`} cx={cx} cy={cy} r="3.5" fill={purple} />;
            })}
            {activePoint ? (
              <SvgText x={activePoint.x} y={chartTop - 6} fill={purple} fontSize="11" fontWeight="900" textAnchor="middle">
                {valueLabel}
              </SvgText>
            ) : null}
          </>
        ) : null}
        {xMonthTicks.map((tick) => {
          const x = chartLeft + (points.length > 1 ? (tick.index / (points.length - 1)) * chartWidth : chartWidth / 2);
          return (
          <SvgText key={tick.label} x={x} y={chartTop + chartHeight + 24} fill="#6B7280" fontSize="10" textAnchor="middle">
            {tick.label}
          </SvgText>
          );
        })}
      </Svg>
      {hasPoints ? (
        <View style={styles.chartTouchLayer} pointerEvents="box-none">
          {pointPositions.map((point, index) => {
            const left = index === 0
              ? chartLeft - 8
              : (pointPositions[index - 1].x + point.x) / 2;
            const right = index === pointPositions.length - 1
              ? chartLeft + chartWidth + 8
              : (point.x + pointPositions[index + 1].x) / 2;
            return (
              <Pressable
                key={`touch-${index}`}
                style={[styles.chartTouchZone, { left, width: Math.max(18, right - left) }]}
                onPress={() => onSelectPoint(index)}
              />
            );
          })}
        </View>
      ) : null}
      {!hasPoints ? <Text style={styles.chartEmptyText}>暫無資料</Text> : null}
    </View>
  );
}

function weaknessDescription(label?: string) {
  if (label === '準度') return '先把直球與固定角度練穩，讓每次瞄準都有一致基準。';
  if (label === '母球控制') return '你需要讓母球停得更準，進球後才更容易接下一球。';
  if (label === '力道控制') return '目前要先建立固定出力感，避免母球跑過頭或停太短。';
  if (label === '出桿穩定') return '先把出桿方向與節奏穩住，減少左右偏移造成的失誤。';
  if (label === '走位能力') return '開始練習進球後的下一球位置，不只看眼前這一球。';
  return '先累積更多練習紀錄，系統會逐步找出最需要加強的能力。';
}

function DataOverviewPage({ value, onChange, dashboard }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null }) {
  const analytics = dashboard?.analytics_v1;
  const abilityScores = analytics?.ability_scores?.length ? analytics.ability_scores : [];
  const overallScore = analytics?.overall_score;
  const confidenceText = analytics?.score_confidence === 'medium' ? '資料可信度中' : '資料可信度低';
  return (
    <View style={styles.stack}>
      <DataSelector value={value} onChange={onChange} />
      <View style={styles.abilityHero}>
        <View style={styles.spaceBetween}>
          <Text style={styles.abilityHeroLabel}>你的能力分數</Text>
          <Pill text={confidenceText} />
        </View>
        <View style={styles.abilityScoreRow}>
          <Text style={styles.abilityScoreValue}>{overallScore ?? '--'}</Text>
          <Text style={styles.abilityScoreMax}>/ 100</Text>
        </View>
        <Text style={styles.abilityLevel}>{analytics?.level_label || '等待分析資料'}</Text>
        <Text style={styles.abilityBasis}>{analytics?.score_basis || '登入並完成練習後，系統會根據紀錄建立能力總覽。'}</Text>
      </View>

      <Card>
        <View style={styles.spaceBetween}><Text style={styles.sectionTitle}>能力輪廓</Text><Pill text="V1 推估" /></View>
        {abilityScores.length ? <AbilityRadarChart scores={abilityScores} /> : <EmptyState text="目前尚無能力分析資料。" />}
      </Card>

      <Card>
        <Text style={styles.sectionTitle}>五大能力</Text>
        {abilityScores.length ? (
          <View style={styles.abilityList}>
            {abilityScores.map((item) => (
              <View key={item.key} style={styles.abilityRow}>
                <View style={styles.abilityRowTop}>
                  <Text style={styles.abilityName}>{item.label}</Text>
                  <Text style={styles.abilityValue}>{Math.round(item.score)}</Text>
                </View>
                <ProgressBar value={item.score} />
              </View>
            ))}
          </View>
        ) : (
          <EmptyState text="完成練習並同步後才會建立能力分數。" />
        )}
      </Card>

      <Card>
        <View style={styles.spaceBetween}><Text style={styles.sectionTitle}>目前最大弱點</Text><Pill text={analytics?.weakest_ability || '分析中'} /></View>
        <Text style={styles.weaknessTitle}>{analytics?.weakest_ability || '等待資料'}</Text>
        <Text style={styles.weaknessText}>{weaknessDescription(analytics?.weakest_ability)}</Text>
      </Card>

    </View>
  );
}

function AbilityRadarChart({ scores }: { scores: Array<{ key: string; label: string; score: number }> }) {
  const width = 320;
  const height = 250;
  const centerX = width / 2;
  const centerY = 120;
  const radius = 82;
  const normalizedScores = scores.slice(0, 5);
  const pointFor = (index: number, value: number) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / normalizedScores.length;
    const distance = radius * Math.max(0, Math.min(100, value)) / 100;
    return {
      x: centerX + Math.cos(angle) * distance,
      y: centerY + Math.sin(angle) * distance,
    };
  };
  const axisPointFor = (index: number, distance = radius) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / normalizedScores.length;
    return {
      x: centerX + Math.cos(angle) * distance,
      y: centerY + Math.sin(angle) * distance,
    };
  };
  const polygonPoints = normalizedScores.map((item, index) => pointFor(index, item.score)).map((point) => `${point.x},${point.y}`).join(' ');
  const gridLevels = [0.25, 0.5, 0.75, 1];

  return (
    <View style={styles.radarWrap}>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        {gridLevels.map((level) => (
          <Polygon
            key={level}
            points={normalizedScores.map((_, index) => axisPointFor(index, radius * level)).map((point) => `${point.x},${point.y}`).join(' ')}
            fill="none"
            stroke="#E5E7EB"
            strokeWidth="1"
          />
        ))}
        {normalizedScores.map((_, index) => {
          const point = axisPointFor(index);
          return <Line key={`axis-${index}`} x1={centerX} y1={centerY} x2={point.x} y2={point.y} stroke="#EEF2F7" strokeWidth="1" />;
        })}
        <Polygon points={polygonPoints} fill="rgba(79,70,229,0.18)" stroke={purple} strokeWidth="3" />
        {normalizedScores.map((item, index) => {
          const point = pointFor(index, item.score);
          const labelPoint = axisPointFor(index, radius + 32);
          return (
            <React.Fragment key={item.key}>
              <Circle cx={point.x} cy={point.y} r="4" fill={purple} />
              <SvgText x={labelPoint.x} y={labelPoint.y} fill={ink} fontSize="12" fontWeight="800" textAnchor="middle">
                {item.label}
              </SvgText>
            </React.Fragment>
          );
        })}
      </Svg>
    </View>
  );
}

function MatchHistoryPage({ value, onChange, dashboard, onOpenDetail }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null; onOpenDetail: (item: HistoryDetailItem) => void }) {
  const [filter, setFilter] = useState<HistoryFilter>('全部');
  const historyItems = useMemo<HistoryDetailItem[]>(() => {
    const practices = (dashboard?.recent_practice || []).map((record) => ({
      kind: 'practice' as const,
      id: `practice-${record.game_id}`,
      record,
    }));
    const matches = (dashboard?.recent_games || []).map((record) => ({
      kind: 'match' as const,
      id: `match-${record.game_id}`,
      record,
    }));
    return [...practices, ...matches].sort((a, b) => {
      const aDate = new Date(a.record.date).getTime();
      const bDate = new Date(b.record.date).getTime();
      return (Number.isFinite(bDate) ? bDate : 0) - (Number.isFinite(aDate) ? aDate : 0);
    });
  }, [dashboard?.recent_games, dashboard?.recent_practice]);
  const filtered = historyItems.filter((item) => filter === '全部' || (filter === '練習' ? item.kind === 'practice' : item.kind === 'match'));
  return (
    <View style={styles.stack}>
      <DataSelector value={value} onChange={onChange} />
      <View style={styles.segment}>
        {(['全部', '練習', '對戰'] as const).map((item) => (
          <Pressable key={item} style={[styles.segmentItem, filter === item && styles.segmentActive]} onPress={() => setFilter(item)}>
            <Text style={[styles.segmentText, filter === item && styles.segmentTextActive]}>{item}</Text>
          </Pressable>
        ))}
      </View>
      <Card>{filtered.length ? filtered.map((item) => <HistoryRow key={item.id} item={item} onPress={() => onOpenDetail(item)} />) : <EmptyState text="沒有符合條件的歷史紀錄。" />}</Card>
    </View>
  );
}

function HistoryRow({ item, onPress }: { item: HistoryDetailItem; onPress: () => void }) {
  if (item.kind === 'practice') {
    const minutes = Math.max(1, Math.round((item.record.duration_seconds || 0) / 60));
    return (
      <Pressable style={styles.historyRow} onPress={onPress}>
        <View style={styles.historyTypeBadge}><Text style={styles.historyTypeBadgeText}>練</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={styles.rowTitle}>{item.record.practice_type || '練習紀錄'}</Text>
          <Text style={styles.rowMeta}>{formatOverviewDate(item.record.date)} · {minutes} 分鐘</Text>
        </View>
        <ChevronRight size={16} color={muted} />
      </Pressable>
    );
  }
  const isWin = item.record.result === 'win';
  const resultLabel = item.record.result === 'draw' ? '平手' : isWin ? '勝利' : '失敗';
  return (
    <Pressable style={styles.historyRow} onPress={onPress}>
      <View style={[styles.historyTypeBadge, isWin ? styles.historyTypeBadgeWin : styles.historyTypeBadgeLoss]}>
        <Text style={styles.historyTypeBadgeText}>{isWin ? '勝' : item.record.result === 'draw' ? '和' : '敗'}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle}>vs {item.record.opponent || '未知對手'}</Text>
        <Text style={styles.rowMeta}>{new Date(item.record.date).toLocaleString()}</Text>
      </View>
      <View style={{ alignItems: 'flex-end' }}>
        <Text style={[styles.resultText, { color: isWin ? success : danger }]}>{resultLabel}</Text>
        <Text style={styles.scoreText}>{item.record.score || '-'}</Text>
      </View>
      <ChevronRight size={16} color={muted} />
    </Pressable>
  );
}

function HistoryDetailPage({ item, onBack }: { item: HistoryDetailItem; onBack: () => void }) {
  const isPractice = item.kind === 'practice';
  const title = isPractice ? item.record.practice_type || '練習詳情' : `vs ${item.record.opponent || '未知對手'}`;
  const rows = isPractice
    ? [
      { label: '類型', value: item.record.practice_type || '練習' },
      { label: '日期', value: formatOverviewDate(item.record.date) },
      { label: '時長', value: `${Math.max(1, Math.round((item.record.duration_seconds || 0) / 60))} 分鐘` },
      { label: '紀錄 ID', value: item.record.game_id },
    ]
    : [
      { label: '對手', value: item.record.opponent || '未知對手' },
      { label: '結果', value: item.record.result === 'win' ? '勝利' : item.record.result === 'loss' ? '失敗' : '平手' },
      { label: '比分', value: item.record.score || '-' },
      { label: '時間', value: new Date(item.record.date).toLocaleString() },
      { label: '紀錄 ID', value: item.record.game_id },
    ];
  return (
    <View style={styles.stack}>
      <Pressable style={styles.detailBackButton} onPress={onBack}>
        <ChevronRight size={18} color={ink} strokeWidth={2.4} style={styles.settingsBackIcon} />
        <Text style={styles.backLabelText}>返回</Text>
      </Pressable>
      <Card>
        <View style={styles.historyDetailHero}>
          <View style={styles.historyDetailBadge}><Text style={styles.historyDetailBadgeText}>{isPractice ? '練習' : '對戰'}</Text></View>
          <Text style={styles.historyDetailTitle}>{title}</Text>
          <Text style={styles.historyDetailMeta}>{isPractice ? formatOverviewDate(item.record.date) : new Date(item.record.date).toLocaleString()}</Text>
        </View>
        <View style={styles.detailList}>
          {rows.map((row) => (
            <View key={row.label} style={styles.detailRow}>
              <Text style={styles.detailLabel}>{row.label}</Text>
              <Text style={styles.detailValue}>{row.value}</Text>
            </View>
          ))}
        </View>
      </Card>
    </View>
  );
}

function formatPercentMetric(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
  return `${Math.round(Number(value))}%`;
}

function formatOffenseResultLabel(value: string) {
  return value === 'made' ? '進球' : '未進';
}

function formatOffenseMeta(record: { target_ball?: number | null; difficulty_level?: string; distance_bucket?: string; is_foul?: boolean }) {
  const parts = [
    record.target_ball ? `目標 ${record.target_ball} 號` : null,
    record.difficulty_level && record.difficulty_level !== 'unknown' ? record.difficulty_level : null,
    record.distance_bucket && record.distance_bucket !== 'unknown' ? record.distance_bucket : null,
    record.is_foul ? '犯規' : null,
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : '出桿紀錄';
}

function OffenseDataPage({ value, onChange, dashboard }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null }) {
  const analytics = dashboard?.analytics_v1;
  const offense = analytics?.offense_summary;
  const records = offense?.recent_records || [];
  const hasOffenseData = Boolean(offense && offense.status === 'ready' && offense.total_shot_count > 0);
  return (
    <View style={styles.stack}>
      <DataSelector value={value} onChange={onChange} />
      <Card>
        <View style={styles.spaceBetween}>
          <Text style={styles.sectionTitle}>進攻數據</Text>
          <Pill text={hasOffenseData ? '真實出桿紀錄' : '尚無資料'} />
        </View>
        {hasOffenseData ? (
          <>
            <View style={styles.offenseHeroGrid}>
              <View style={styles.offenseHeroMetric}>
                <Text style={styles.weeklyMetricLabel}>本週擊球</Text>
                <View style={styles.weeklyMetricValueRow}>
                  <Text style={styles.weeklyMetricValue}>{offense?.weekly_shot_count ?? 0}</Text>
                  <Text style={styles.weeklyMetricUnit}>顆</Text>
                </View>
              </View>
              <View style={styles.offenseHeroMetric}>
                <Text style={styles.weeklyMetricLabel}>本週進球</Text>
                <View style={styles.weeklyMetricValueRow}>
                  <Text style={styles.weeklyMetricValue}>{offense?.weekly_made_count ?? 0}</Text>
                  <Text style={styles.weeklyMetricUnit}>顆</Text>
                </View>
              </View>
            </View>
            <View style={styles.abilityList}>
              <View style={styles.abilityRow}>
                <View style={styles.abilityRowTop}>
                  <Text style={styles.abilityName}>本週進球率</Text>
                  <Text style={styles.abilityValue}>{formatPercentMetric(offense?.weekly_pot_rate)}</Text>
                </View>
                <ProgressBar value={offense?.weekly_pot_rate ?? 0} />
              </View>
              <View style={styles.weeklyMetricGrid}>
                <WeeklyMetric label="累積擊球" unit="顆" value={offense?.total_shot_count ?? 0} />
                <WeeklyMetric label="本週犯規" unit="次" value={offense?.foul_count ?? 0} />
                <WeeklyMetric label="本週洗袋" unit="次" value={offense?.scratch_count ?? 0} />
              </View>
            </View>
            <Text style={styles.overviewBasis}>只統計已同步的 shot_events，不使用能力分數推估。</Text>
          </>
        ) : (
          <EmptyState text="目前沒有可追溯的進攻出桿紀錄。完成練習並同步 shot_events 後才會顯示數據。" />
        )}
      </Card>
      {hasOffenseData ? (
        <Card>
          <Text style={styles.sectionTitle}>最近進攻紀錄</Text>
          {records.length ? (
            <View style={styles.trainingList}>
              {records.map((record, index) => (
                <View key={`${record.game_id || 'shot'}-${record.shot_index}-${index}`} style={styles.trainingRow}>
                  <View style={[styles.trainingBadge, record.pocket_result === 'made' ? null : styles.historyTypeBadgeLoss]}>
                    <Text style={styles.trainingBadgeText}>{record.pocket_result === 'made' ? '進' : '失'}</Text>
                  </View>
                  <View style={styles.trainingCopy}>
                    <Text style={styles.trainingTitle}>{formatOffenseResultLabel(record.pocket_result)}</Text>
                    <Text style={styles.trainingReason}>{formatOverviewDate(record.created_at)} · {formatOffenseMeta(record)}</Text>
                  </View>
                </View>
              ))}
            </View>
          ) : (
            <Text style={styles.overviewBasis}>目前沒有最近進攻紀錄明細。</Text>
          )}
        </Card>
      ) : null}
    </View>
  );
}

function BallShapePerformancePage({ value, onChange, dashboard }: { value: DataSection; onChange: (value: DataSection) => void; dashboard: DashboardResponse | null }) {
  const analytics = dashboard?.analytics_v1;
  const summary = analytics?.ball_shape_summary;
  const records = summary?.recent_records || [];
  const hasBallShapeData = Boolean(summary && summary.status === 'ready' && summary.total_sessions > 0);
  return (
    <View style={styles.stack}>
      <DataSelector value={value} onChange={onChange} />
      <Card>
        <View style={styles.spaceBetween}>
          <Text style={styles.sectionTitle}>球型表現</Text>
          <Pill text={hasBallShapeData ? '真實練習紀錄' : '尚無資料'} />
        </View>
        {hasBallShapeData ? (
          <>
            <View style={styles.weeklyMetricGrid}>
              <WeeklyMetric label="總練習" unit="次" value={summary?.total_sessions ?? 0} />
              <WeeklyMetric label="本週" unit="次" value={summary?.weekly_sessions ?? 0} />
              <View style={styles.weeklyMetricItem}>
                <Text style={styles.weeklyMetricLabel}>總時長</Text>
                <Text style={styles.weeklyMetricValue}>{formatDurationHours(summary?.total_duration_seconds)}</Text>
              </View>
            </View>
            <Text style={styles.overviewBasis}>只統計電腦端同步的球型練習紀錄，不使用能力分數推估。</Text>
          </>
        ) : (
          <EmptyState text="目前沒有可追溯的球型練習紀錄。完成球型練習並同步後才會顯示數據。" />
        )}
      </Card>
      {hasBallShapeData ? (
        <Card>
          <Text style={styles.sectionTitle}>最近球型練習</Text>
          {records.length ? (
            <View style={styles.trainingList}>
              {records.map((record) => (
                <View key={record.game_id} style={styles.trainingRow}>
                  <View style={styles.trainingBadge}>
                    <Text style={styles.trainingBadgeText}>{Math.max(1, Math.round((record.duration_seconds || 0) / 60))}</Text>
                  </View>
                  <View style={styles.trainingCopy}>
                    <Text style={styles.trainingTitle}>球型練習</Text>
                    <Text style={styles.trainingReason}>{formatOverviewDate(record.date)} · {record.game_id}</Text>
                  </View>
                </View>
              ))}
            </View>
          ) : (
            <Text style={styles.overviewBasis}>目前沒有最近球型練習明細。</Text>
          )}
        </Card>
      ) : null}
    </View>
  );
}

function UnsupportedDataPage({ title, value, onChange }: { title: string; value: DataSection; onChange: (value: DataSection) => void }) {
  return (
    <View style={styles.stack}>
      <DataSelector value={value} onChange={onChange} />
      <Card><Text style={styles.sectionTitle}>{title}</Text><EmptyState text="需要更多擊球紀錄後開放。V1 先提供能力總覽與對戰統計。" /></Card>
    </View>
  );
}

function ScanPage(props: {
  user: AuthUser | null;
  showProfileQr: boolean;
  setShowProfileQr: (value: boolean) => void;
  loading: boolean;
  permissionGranted: boolean;
  requestPermission: () => void;
  onScan: (payload: string) => void;
  scanLocked: boolean;
  scanJoiningStatus: { title: string; detail: string } | null;
  friendInviteQrPayload: string;
  friendInviteQrLoading: boolean;
  friendInviteQrError: string;
}) {
  const primaryButtonText = props.showProfileQr ? '返回掃描' : props.permissionGranted ? '顯示我的 QR Code' : '允許相機掃描';
  const handlePrimaryPress = () => {
    if (props.showProfileQr) {
      props.setShowProfileQr(false);
      return;
    }
    if (props.permissionGranted) {
      props.setShowProfileQr(true);
      return;
    }
    props.requestPermission();
  };

  return (
    <View style={[styles.stack, styles.scanStack]}>
      <View style={styles.scanPanel}>
        <Text style={styles.sectionTitle}>{props.showProfileQr ? '我的好友 QR Code' : '掃描好友 QR Code'}</Text>
        <View style={styles.scanVisualSlot}>
          {props.showProfileQr && props.friendInviteQrPayload ? (
            <View style={styles.myQrBox}>
              <QRCode value={props.friendInviteQrPayload} size={226} />
              <Text style={styles.subText}>好友掃描後會加入好友列表，再建立好友對戰</Text>
            </View>
          ) : props.showProfileQr ? (
            <View style={styles.qrScanner}>
              {props.friendInviteQrLoading ? (
                <ActivityIndicator color={purple} />
              ) : (
                <Text style={styles.emptyText}>{props.friendInviteQrError || '無法產生好友 QR Code'}</Text>
              )}
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
          <Grid3X3 size={17} color="#fff" />
          <Text style={styles.primaryButtonText}>{primaryButtonText}</Text>
        </Pressable>
      </View>
      <Modal visible={Boolean(props.scanJoiningStatus)} transparent animationType="fade">
        <View style={styles.scanJoiningOverlay}>
          <View style={styles.scanJoiningCard}>
            <ActivityIndicator color={purple} />
            <Text style={styles.scanJoiningTitle}>{props.scanJoiningStatus?.title}</Text>
            <Text style={styles.scanJoiningText}>{props.scanJoiningStatus?.detail}</Text>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function FriendsPage({ friends, loading, onStartGame }: { friends: Friend[]; loading: boolean; onStartGame: (friend: Friend) => void }) {
  return (
    <View style={styles.stack}>
      <PageHeader title="好友" />
      <View style={styles.searchBox}><Search size={17} color={muted} /><Text style={styles.searchPlaceholder}>搜尋好友</Text></View>
      <Card>{friends.length ? friends.map((friend) => <FriendRow key={friend.id} friend={friend} loading={loading} onStartGame={onStartGame} />) : <EmptyState text="互相關注後會自動成為好友。" />}</Card>
    </View>
  );
}

function FollowListPage({
  profile,
  activeKind,
  users,
  loading,
  error,
  onBack,
  onChangeKind,
  onUserPress,
}: {
  profile: MobileProfile | null;
  activeKind: FollowListKind;
  users: MobileFollowUser[];
  loading: boolean;
  error: string;
  onBack: () => void;
  onChangeKind: (kind: FollowListKind) => void;
  onUserPress: (target?: AuthorProfileTarget) => void;
}) {
  const titleName = profile?.display_name?.trim() || profile?.user?.username || '';
  const emptyText = activeKind === 'followers' ? '尚無追蹤者' : '尚未追蹤任何人';
  return (
    <ScrollView showsVerticalScrollIndicator={false} style={styles.profileFlatPage} contentContainerStyle={styles.followListContent}>
      <DualActionHeader title="追蹤名單" left={<BackLabelContent />} onLeft={onBack} />
      {titleName ? <Text style={styles.followListOwner} numberOfLines={1}>{titleName}</Text> : null}
      <View style={styles.followListTabs}>
        <Pressable style={[styles.followListTab, activeKind === 'followers' && styles.followListTabActive]} onPress={() => onChangeKind('followers')}>
          <Text style={[styles.followListTabText, activeKind === 'followers' && styles.followListTabTextActive]}>追蹤者</Text>
        </Pressable>
        <Pressable style={[styles.followListTab, activeKind === 'following' && styles.followListTabActive]} onPress={() => onChangeKind('following')}>
          <Text style={[styles.followListTabText, activeKind === 'following' && styles.followListTabTextActive]}>追蹤中</Text>
        </Pressable>
      </View>
      {loading ? <View style={styles.flatMessage}><ActivityIndicator color={purple} /></View> : null}
      {!loading && error ? <FlatMessage text={error} /> : null}
      {!loading && !error && users.length === 0 ? <FlatMessage text={emptyText} /> : null}
      {!loading && !error && users.map((item) => (
        <FollowUserRow key={`${activeKind}-${item.user.id}`} item={item} onPress={onUserPress} />
      ))}
    </ScrollView>
  );
}

function ProfilePage({
  user,
  profile,
  dashboard,
  posts,
  loading,
  error,
  currentAvatarUrl,
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
  onOpenSettings,
  onOpenFollowList,
  onToggleFollow,
  onAuthorPress,
  onDeletePost,
  onTogglePostLike,
  onTogglePostBookmark,
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
  currentAvatarUrl: string;
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
  onOpenSettings?: () => void;
  onOpenFollowList?: (kind: FollowListKind) => void;
  onToggleFollow?: () => void;
  onAuthorPress?: (target?: AuthorProfileTarget) => void;
  onDeletePost: (post: CommunityPost) => void;
  onTogglePostLike: (post: CommunityPost) => void;
  onTogglePostBookmark: (post: CommunityPost) => void;
  onCreatePostComment: (post: CommunityPost, body: string) => Promise<CommunityComment | undefined>;
  onLoadPostComments: (post: CommunityPost) => Promise<CommunityComment[]>;
  onToggleCommentLike: (comment: CommunityComment) => Promise<CommunityComment>;
  onLogout: () => void;
}) {
  const [profileTab, setProfileTab] = useState<'posts' | 'stats'>('posts');
  const profileUsername = profile?.user?.username?.trim() || (isOwnProfile ? user?.username : '') || previewName.trim();
  const displayName = profileUsername || (isOwnProfile ? '尚未設定名稱' : '載入中');
  const accountName = profile?.display_name?.trim() || '';
  const playerLevel = profile?.player_level || '新手玩家 I';
  const bio = profile?.bio?.trim() || '';
  const avatarUrl = profile?.avatar_url || '';
  const resolvedDisplayName = profileUsername || previewName.trim() || displayName;
  const resolvedPlayerLevel = profile?.player_level || previewLevel || playerLevel;
  const isOfficialProfile = isOfficialLevel(resolvedPlayerLevel) || isOfficialName(resolvedDisplayName);
  const resolvedAvatarUrl = profile?.avatar_url || previewAvatarUrl || avatarUrl;
  const followers = profile?.followers_count ?? 0;
  const following = profile?.following_count ?? 0;
  const isPrivateBlocked = !isOwnProfile && Boolean(profile?.is_private) && !Boolean(profile?.is_following);
  const postCount = isPrivateBlocked ? 0 : profile?.post_count ?? posts.length;
  const stats = dashboard?.stats;

  return (
    <ScrollView
      showsVerticalScrollIndicator={false}
      stickyHeaderIndices={[2]}
      style={styles.profileFlatPage}
      contentContainerStyle={[styles.profileScrollContent, bottomNavOverlayContentInsetStyle]}
    >
      <DualActionHeader
        title={resolvedDisplayName}
        left={!preferBackButton && isOwnProfile ? <Plus size={22} color={ink} /> : <X size={22} color={ink} />}
        right={isOwnProfile && showOwnEditButton ? (loading ? <ActivityIndicator color={purple} /> : <Settings size={20} color={ink} />) : null}
        onLeft={!preferBackButton && isOwnProfile ? onAddPost : onBack}
        onRight={isOwnProfile && showOwnEditButton ? onOpenSettings : undefined}
      />
      <View style={styles.profileFlatSection}>
        <View style={styles.profileHeroRow}>
          <View style={styles.profileAvatar}><AvatarImage uri={resolvedAvatarUrl} imageStyle={styles.profileAvatarImage} iconSize={38} /></View>
          <View style={styles.profileHeroContent}>
            <View style={styles.profileIdentityRow}>
              {accountName ? <Text style={styles.profileAccountName} numberOfLines={1}>{accountName}</Text> : null}
              <Text style={[styles.profileLevel, isOfficialProfile && styles.officialLevel]}>{isOfficialProfile ? '官方帳號' : resolvedPlayerLevel}</Text>
            </View>
            <View style={styles.profileStatsRow}>
              <ProfileStat label="貼文數" value={postCount} />
              <ProfileStat label="追蹤者" value={followers} onPress={() => onOpenFollowList?.('followers')} />
              <ProfileStat label="追蹤中" value={following} onPress={() => onOpenFollowList?.('following')} />
            </View>
          </View>
          <Pressable style={styles.iconButton} onPress={onRefresh}>
            <Bell size={18} color={muted} />
          </Pressable>
        </View>
        {bio ? <Text style={styles.profileBio}>{bio}</Text> : null}
        {!isOwnProfile ? <Pressable
          style={[styles.editProfileButton, !isOwnProfile && profile?.is_following && styles.followingProfileButton]}
          onPress={onToggleFollow}
          disabled={!isOwnProfile && followUpdating}
        >
          {followUpdating ? (
            <ActivityIndicator color={!profile?.is_following ? ink : purple} />
          ) : (
            <Text style={[styles.editProfileText, !isOwnProfile && profile?.is_following && styles.followingProfileText]}>
              {profile?.is_following ? '已追蹤' : '追蹤'}
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
      {!error && isPrivateBlocked ? <FlatMessage text="此帳號為私人帳號" /> : null}
      {!error && !isPrivateBlocked && loading && profileTab === 'posts' ? <View style={styles.flatMessage}><ActivityIndicator color={purple} /></View> : null}
      {!error && !isPrivateBlocked && !loading && profileTab === 'posts' && posts.length === 0 ? <FlatMessage text="尚無貼文" /> : null}
      {!error && !isPrivateBlocked && !loading && profileTab === 'posts' && posts.map((post) => (
        <PostCard key={post.id} post={post} fallbackAuthor={resolvedDisplayName} fallbackAvatarUrl={resolvedAvatarUrl} currentAvatarUrl={currentAvatarUrl} currentUserId={user?.id || 0} currentPlayerLevel={resolvedPlayerLevel} onDelete={onDeletePost} onAuthorPress={onAuthorPress} onToggleLike={onTogglePostLike} onToggleBookmark={onTogglePostBookmark} onCreateComment={onCreatePostComment} onLoadComments={onLoadPostComments} onToggleCommentLike={onToggleCommentLike} />
      ))}
      {!error && !isPrivateBlocked && profileTab === 'stats' ? (
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

function BackLabelButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.backLabelButton} onPress={onPress}>
      <BackLabelContent />
    </Pressable>
  );
}

function BackLabelContent() {
  return (
    <View style={styles.backLabelButton}>
      <ChevronRight size={22} color={ink} strokeWidth={2.4} style={styles.settingsBackIcon} />
      <Text style={styles.backLabelText}>返回</Text>
    </View>
  );
}

function FlatMessage({ text }: { text: string }) {
  return <View style={styles.flatMessage}><Text style={styles.emptyText}>{text}</Text></View>;
}

function ProfileStat({ label, value, onPress }: { label: string; value: number; onPress?: () => void }) {
  const content = (
    <>
      <Text style={styles.profileStatValue}>{value}</Text>
      <Text style={styles.profileStatLabel}>{label}</Text>
    </>
  );
  if (onPress) {
    return (
      <Pressable style={styles.profileStatItem} onPress={onPress}>
        {content}
      </Pressable>
    );
  }
  return (
    <View style={styles.profileStatItem}>
      {content}
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
  username,
  bio,
  avatarUrl,
  loading,
  onClose,
  onSave,
  onPickAvatar,
  onRemoveAvatar,
  onEditField,
  onOpenSecurity,
  onOpenStatus,
}: {
  displayName: string;
  username: string;
  bio: string;
  avatarUrl: string;
  loading: boolean;
  onClose: () => void;
  onSave: () => void;
  onPickAvatar: () => void;
  onRemoveAvatar: () => void;
  onEditField: (field: AccountEditField) => void;
  onOpenSecurity: () => void;
  onOpenStatus: () => void;
}) {
  const [showAvatarMenu, setShowAvatarMenu] = useState(false);
  const showComingSoon = (label: string) => Alert.alert(label, '此項目介面已建立，後續可串接帳號管理 API。');
  return (
    <View style={styles.editProfilePage}>
      <View style={styles.creatorHeader}>
        <BackLabelButton onPress={onClose} />
        <Text style={styles.pageTitle}>帳號管理中心</Text>
        <View style={styles.headerSpacer} />
      </View>
      <View style={styles.editAvatarBlock}>
        <View style={styles.editAvatar}><AvatarImage uri={avatarUrl} imageStyle={styles.editAvatarImage} iconSize={42} /></View>
        <Pressable onPress={() => setShowAvatarMenu(true)}><Text style={styles.changeAvatarText}>更換頭像</Text></Pressable>
      </View>
      <View style={styles.accountCenterGroup}>
        <AccountCenterRow label="姓名" value={displayName || '尚未設定'} onPress={() => onEditField('name')} />
        <AccountCenterRow label="使用者名稱" value={username || '尚未設定'} onPress={() => onEditField('username')} />
        <AccountCenterRow label="個人簡介" value={bio || '尚未設定'} onPress={() => onEditField('bio')} />
      </View>
      <View style={styles.accountCenterDivider} />
      <View style={styles.accountCenterGroup}>
        <AccountCenterRow label="帳號安全與登入" onPress={onOpenSecurity} showChevron />
        <AccountCenterRow label="帳號狀態" onPress={onOpenStatus} showChevron />
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

function AccountCenterRow({ label, value, showChevron = false, onPress }: { label: string; value?: string; showChevron?: boolean; onPress: () => void }) {
  return (
    <Pressable style={styles.accountCenterRow} onPress={onPress}>
      <Text style={styles.accountCenterLabel}>{label}</Text>
      <View style={styles.accountCenterRight}>
        {value ? <Text style={styles.accountCenterValue} numberOfLines={1}>{value}</Text> : null}
        {showChevron ? <ChevronRight size={16} color={muted} /> : null}
      </View>
    </Pressable>
  );
}

function AccountFieldEditPage({
  field,
  value,
  loading,
  onChangeValue,
  onBack,
  onSave,
}: {
  field: AccountEditField;
  value: string;
  loading: boolean;
  onChangeValue: (value: string) => void;
  onBack: () => void;
  onSave: () => void;
}) {
  const title = field === 'name' ? '姓名' : field === 'username' ? '使用者名稱' : '個人簡介';
  const placeholder = field === 'name' ? '輸入姓名' : field === 'username' ? '輸入使用者名稱' : '輸入個人簡介';
  const handleChange = (nextValue: string) => {
    onChangeValue(field === 'username' ? nextValue.toLowerCase().replace(/[^a-z0-9_.]/g, '') : nextValue);
  };
  return (
    <View style={styles.accountFieldPage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onBack}>
          <ChevronRight size={22} color={ink} strokeWidth={2.4} style={styles.settingsBackIcon} />
        </Pressable>
        <Text style={styles.pageTitle}>{title}</Text>
        <Pressable onPress={onSave} disabled={loading}>
          {loading ? <ActivityIndicator color={purple} /> : <Text style={styles.nextText}>完成</Text>}
        </Pressable>
      </View>
      <View style={styles.accountFieldInputWrap}>
        <TextInput
          style={[styles.accountFieldInput, field === 'bio' && styles.accountFieldBioInput]}
          value={value}
          onChangeText={handleChange}
          placeholder={placeholder}
          placeholderTextColor="#9CA3AF"
          autoCapitalize="none"
          multiline={field === 'bio'}
        />
        {value ? (
          <Pressable style={styles.accountFieldClear} onPress={() => onChangeValue('')} hitSlop={10}>
            <X size={17} color={muted} />
          </Pressable>
        ) : null}
      </View>
      {field === 'username' ? <Text style={styles.accountFieldHint}>只能使用英文小寫、數字、底線與句點。</Text> : null}
    </View>
  );
}

function AccountSecurityPage({ onBack, onChangePassword, onLoginDevices }: { onBack: () => void; onChangePassword: () => void; onLoginDevices: () => void }) {
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title="帳號安全與登入" onBack={onBack} />
      <View style={styles.accountCenterGroup}>
        <AccountCenterRow label="修改密碼" onPress={onChangePassword} showChevron />
        <AccountCenterRow label="登入裝置管理" onPress={onLoginDevices} showChevron />
      </View>
    </View>
  );
}

function ChangePasswordPage({
  currentPassword,
  nextPassword,
  confirmPassword,
  logoutOtherDevices,
  loading,
  onChangeCurrent,
  onChangeNext,
  onChangeConfirm,
  onToggleLogoutOthers,
  onBack,
  onSubmit,
}: {
  currentPassword: string;
  nextPassword: string;
  confirmPassword: string;
  logoutOtherDevices: boolean;
  loading: boolean;
  onChangeCurrent: (value: string) => void;
  onChangeNext: (value: string) => void;
  onChangeConfirm: (value: string) => void;
  onToggleLogoutOthers: () => void;
  onBack: () => void;
  onSubmit: () => void;
}) {
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title="修改密碼" onBack={onBack} />
      <View style={styles.passwordFieldGroup}>
        <PasswordField label="密碼" value={currentPassword} onChangeText={onChangeCurrent} />
        <PasswordField label="新密碼" value={nextPassword} onChangeText={onChangeNext} />
        <PasswordField label="確認新密碼" value={confirmPassword} onChangeText={onChangeConfirm} />
      </View>
      <Pressable onPress={() => Alert.alert('忘記密碼', '此功能先保留，後續可串接密碼重設流程。')}>
        <Text style={styles.forgotPasswordText}>忘記密碼?</Text>
      </Pressable>
      <Pressable style={styles.logoutOtherDevicesRow} onPress={onToggleLogoutOthers}>
        <View style={[styles.checkboxBox, logoutOtherDevices && styles.checkboxBoxChecked]}>
          {logoutOtherDevices ? <Text style={styles.checkboxCheck}>✓</Text> : null}
        </View>
        <Text style={styles.logoutOtherDevicesText}>登出其他裝置</Text>
      </Pressable>
      <Pressable style={styles.changePasswordButton} onPress={onSubmit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.changePasswordButtonText}>更改密碼</Text>}
      </Pressable>
    </View>
  );
}

function LoginDevicesPage({ history, loading, onBack }: { history: LoginHistoryEntry[]; loading: boolean; onBack: () => void }) {
  const current = history[0] || { device: '手機型號', status: 'success', created_at: new Date().toISOString() };
  const others = history.slice(1);
  return (
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.loginDevicesPage}>
      <SimpleSubPageHeader title="登入裝置管理" onBack={onBack} />
      <Text style={styles.loginActivityTitle}>帳號登入活動</Text>
      <Text style={styles.loginActivitySection}>你目前在此裝置登入</Text>
      <LoginDeviceCard entry={current} right={<Text style={styles.currentDeviceBadge}>此裝置</Text>} />
      <Text style={styles.loginActivitySection}>其他裝置登入活動</Text>
      {loading ? <ActivityIndicator color={purple} /> : null}
      {!loading && others.length === 0 ? (
        <LoginDeviceCard entry={{ device: '手機型號', status: 'success', created_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 365 * 3).toISOString() }} right={<Text style={styles.loginDeviceTime}>三年前</Text>} />
      ) : null}
      {!loading && others.map((entry, index) => (
        <LoginDeviceCard key={`${entry.created_at}-${index}`} entry={entry} right={<Text style={styles.loginDeviceTime}>{coarseTimeAgo(entry.created_at)}</Text>} />
      ))}
    </ScrollView>
  );
}

function SimpleSubPageHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <View style={styles.creatorHeader}>
      <Pressable onPress={onBack}>
        <ChevronRight size={22} color={ink} strokeWidth={2.4} style={styles.settingsBackIcon} />
      </Pressable>
      <Text style={styles.pageTitle}>{title}</Text>
      <View style={styles.headerSpacer} />
    </View>
  );
}

function PasswordField({ label, value, onChangeText }: { label: string; value: string; onChangeText: (value: string) => void }) {
  return (
    <View style={styles.passwordFieldRow}>
      <Text style={styles.passwordFieldLabel}>{label}</Text>
      <TextInput style={styles.passwordFieldInput} value={value} onChangeText={onChangeText} secureTextEntry placeholder={label} placeholderTextColor="#9CA3AF" />
    </View>
  );
}

function LoginDeviceCard({ entry, right }: { entry: LoginHistoryEntry; right: React.ReactNode }) {
  const device = entry.device?.trim() || '手機型號';
  return (
    <View style={styles.loginDeviceCard}>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={styles.loginDeviceName} numberOfLines={1}>{device}</Text>
        <Text style={styles.loginDeviceMeta}>城市, 台灣</Text>
      </View>
      {right}
    </View>
  );
}

function coarseTimeAgo(value: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return '三年前';
  const diffMs = Math.max(0, Date.now() - timestamp);
  const day = 1000 * 60 * 60 * 24;
  const days = Math.floor(diffMs / day);
  const years = Math.floor(days / 365);
  if (years >= 1) return `${years}年前`;
  const months = Math.floor(days / 30);
  if (months >= 1) return `${months}個月前`;
  if (days >= 1) return `${days}天前`;
  return '今天';
}

function AvatarPickerPage({
  photos,
  preview,
  albumTitle,
  albumsAvailable,
  error,
  hasMorePhotos,
  loadingMorePhotos,
  saving,
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
  saving: boolean;
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
        <Pressable onPress={onClose} disabled={saving}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>選擇頭像</Text>
        <Pressable onPress={() => activePreview && onUse(activePreview)} disabled={!activePreview || saving}>
          {saving ? <ActivityIndicator color={purple} /> : <Text style={[styles.nextText, (!activePreview || saving) && { color: muted }]}>完成</Text>}
        </Pressable>
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
  currentAvatarUrl,
  currentUserId,
  currentPlayerLevel,
  onDelete,
  onAuthorPress,
  onToggleLike,
  onToggleBookmark,
  onCreateComment,
  onLoadComments,
  onToggleCommentLike,
  edgeToEdge = true,
}: {
  post: CommunityPost;
  fallbackAuthor: string;
  fallbackAvatarUrl: string;
  currentAvatarUrl: string;
  currentUserId: number;
  currentPlayerLevel: string;
  onDelete: (post: CommunityPost) => void;
  onAuthorPress?: (target?: AuthorProfileTarget) => void;
  onToggleLike: (post: CommunityPost) => void;
  onToggleBookmark: (post: CommunityPost) => void;
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
  const pendingCommentLikeIds = useRef<Set<number>>(new Set());
  const isOwnPost = currentUserId > 0 && Number(post.user_id) === currentUserId;
  const avatarUrl = post.author_avatar_url || (isOwnPost ? fallbackAvatarUrl : '');
  const isOfficialPostAuthor = isOfficialLevel(post.badge) || isOfficialName(post.author_name);
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
    if (pendingCommentLikeIds.current.has(comment.id)) return;
    pendingCommentLikeIds.current.add(comment.id);
    const nextLiked = !comment.liked_by_me;
    const nextLikes = Math.max(0, Number(comment.likes || 0) + (nextLiked ? 1 : -1));
    setComments((current) => current.map((item) => (
      item.id === comment.id ? { ...item, liked_by_me: nextLiked, likes: nextLikes } : item
    )));
    try {
      const updated = await onToggleCommentLike(comment);
      setComments((current) => current.map((item) => (
        item.id === updated.id ? { ...updated, liked_by_me: nextLiked, likes: updated.likes } : item
      )));
    } catch (error) {
      setComments((current) => current.map((item) => (
        item.id === comment.id ? { ...item, liked_by_me: comment.liked_by_me, likes: comment.likes } : item
      )));
      Alert.alert('按讚失敗', error instanceof Error ? error.message : '無法更新留言按讚。');
    } finally {
      pendingCommentLikeIds.current.delete(comment.id);
    }
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
          <View style={styles.postAuthorRow}>
            <Text style={styles.postAuthor}>{post.author_name || fallbackAuthor}</Text>
            {isOfficialPostAuthor ? <Text style={styles.officialInlineBadge}>官方帳號</Text> : null}
          </View>
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
        <Pressable onPress={() => onToggleBookmark(post)} hitSlop={10}>
          <Bookmark size={18} color={post.bookmarked_by_me ? purple : muted} fill={post.bookmarked_by_me ? purple : 'transparent'} />
        </Pressable>
      </View>
      <CommentSheet
        visible={showCommentSheet}
        post={post}
        comments={comments}
        loadingComments={loadingComments}
        commentText={commentText}
        submitting={submittingComment}
        currentUserId={currentUserId}
        currentAvatarUrl={currentAvatarUrl}
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
              const isOfficialCommentAuthor = isOfficialLevel(commentPlayerLevel) || isOfficialName(comment.author_name);
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
                      {(commentPlayerLevel || isOfficialCommentAuthor) ? <Text style={[styles.commentLevel, isOfficialCommentAuthor && styles.officialCommentLevel]}>{isOfficialCommentAuthor ? '官方帳號' : commentPlayerLevel}</Text> : null}
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
        <Text style={styles.pageTitle}>選擇照片</Text>
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
  error,
  canShare,
  onClose,
  onPickPhotos,
  onEditPhoto,
  onShare,
}: {
  photos: LocalPhoto[];
  transforms: Record<string, { x: number; y: number; scale: number }>;
  text: string;
  setText: (value: string) => void;
  loading: boolean;
  error: string;
  canShare: boolean;
  onClose: () => void;
  onPickPhotos: () => void;
  onEditPhoto: (photoId: string) => void;
  onShare: () => void;
}) {
  const mediaWidth = getPostMediaWidth();
  return (
    <View style={styles.creatorPage}>
      <View style={styles.creatorHeader}>
        <Pressable onPress={onClose}><X size={24} color={ink} /></Pressable>
        <Text style={styles.pageTitle}>撰寫貼文</Text>
        <Pressable onPress={onShare} disabled={loading || !canShare}>
          {loading ? <ActivityIndicator color={purple} /> : <Text style={[styles.nextText, !canShare && { color: muted }]}>完成</Text>}
        </Pressable>
      </View>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.composeScrollContent}>
        <View style={styles.composeTextPanel}>
          <TextInput
            style={styles.composeInput}
            value={text}
            onChangeText={setText}
            placeholder="寫下今天的練習、球館或對戰心得..."
            placeholderTextColor="#9CA3AF"
            multiline
            textAlignVertical="top"
          />
        </View>
        {error ? <FlatMessage text={error} /> : null}
        <View style={styles.composeSectionHeader}>
          <View>
            <Text style={styles.composeSectionTitle}>照片</Text>
            <Text style={styles.composeSectionMeta}>{photos.length ? `${photos.length} / 3 張，點照片可調整裁切` : '可選擇最多 3 張照片'}</Text>
          </View>
          <Pressable style={styles.composePhotoActionButton} onPress={onPickPhotos}>
            <Plus size={17} color={purple} />
            <Text style={styles.composePhotoActionText}>{photos.length ? '更換' : '加入'}</Text>
          </Pressable>
        </View>
        {photos.length ? (
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
        ) : (
          <Pressable style={styles.composeEmptyPhoto} onPress={onPickPhotos}>
            <Plus size={22} color={purple} />
            <Text style={styles.composePhotoActionText}>選擇照片</Text>
          </Pressable>
        )}
      </ScrollView>
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
  const [open, setOpen] = useState(false);
  const options: DataSection[] = ['總覽', '歷史紀錄', '進攻數據', '球型表現'];
  return (
    <View style={styles.dataSelectorWrap}>
      <Pressable style={styles.dataSelectorButton} onPress={() => setOpen((current) => !current)}>
        <Text style={styles.dataSelectorText}>{value}</Text>
        <ChevronDown size={18} color={ink} />
      </Pressable>
      {open ? (
        <>
          <View style={styles.dataSelectorDismissLayer} onTouchMove={() => setOpen(false)}>
            <Pressable style={styles.dataSelectorDismissPressable} onPress={() => setOpen(false)} />
          </View>
          <View style={styles.dataSelectorMenu}>
            {options.map((option) => (
              <Pressable
                key={option}
                style={[styles.dataSelectorOption, value === option && styles.dataSelectorOptionActive]}
                onPress={() => {
                  onChange(option);
                  setOpen(false);
                }}
              >
                <Text style={[styles.dataSelectorOptionText, value === option && styles.dataSelectorOptionTextActive]}>{option}</Text>
              </Pressable>
            ))}
          </View>
        </>
      ) : null}
    </View>
  );
}

const bottomNavOverlayContentInsetStyle = Platform.OS === 'web'
  ? ({ paddingBottom: 'calc(88px - env(safe-area-inset-bottom))' } as unknown as ViewStyle)
  : null;

const bottomNavWebPullDownStyle = Platform.OS === 'web'
  ? ({ bottom: 'calc(-1 * env(safe-area-inset-bottom) - 12px)', height: 'calc(72px + env(safe-area-inset-bottom))' } as unknown as ViewStyle)
  : null;

const coachChatContentInsetStyle = Platform.OS === 'web'
  ? ({ paddingBottom: 88 } as unknown as ViewStyle)
  : null;

const coachChatKeyboardInsetStyle = Platform.OS === 'web'
  ? ({ paddingBottom: 12 } as unknown as ViewStyle)
  : null;

const phoneWebTopSafeAreaStyle = Platform.OS === 'web'
  ? ({ paddingTop: 'max(0px, calc(env(safe-area-inset-top) - 8px))' } as unknown as ViewStyle)
  : null;

function BottomNav({ active, onChange }: { active: MainTab; onChange: (tab: MainTab) => void }) {
  const items = [
    { tab: '首頁', Icon: Home },
    { tab: '數據', Icon: BarChart3 },
    { tab: '掃碼', Icon: QrCode },
    { tab: 'AI教練聊天室', Icon: MessageCircle },
    { tab: '我的', Icon: User },
  ] as const;
  const navItems = items.map(({ tab, Icon }) => <Pressable key={tab} style={styles.navItem} onPress={() => onChange(tab)} accessibilityLabel={tab}><Icon size={24} color={active === tab ? purple : muted} strokeWidth={active === tab ? 2.9 : 2.2} /></Pressable>);
  return <View style={[styles.bottomNav, bottomNavWebPullDownStyle]}><View style={styles.bottomNavItems}>{navItems}</View></View>;
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

function buildAiCoachOpening(dashboard: DashboardResponse | null): string {
  const analytics = dashboard?.analytics_v1;
  const summary = analytics?.coach_summary?.trim();
  if (summary) return `我是 CueVex AI 教練。先用你目前的數據當背景：${summary}`;
  return '我是 CueVex AI 教練。你可以直接問我今天該練什麼、哪個能力最需要補強，或把球局問題描述給我。';
}

function AiCoachChatPage({ dashboard, onSend, onComposerFocusChange }: { dashboard: DashboardResponse | null; onSend: (message: string, history: AiCoachChatMessage[], onDelta: AiCoachSendDelta) => Promise<AiCoachSendResult>; onComposerFocusChange: (focused: boolean) => void }) {
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<AiCoachChatMessage[]>(() => [{
    id: 'coach-opening',
    role: 'coach',
    text: buildAiCoachOpening(dashboard),
    timestamp: new Date().toISOString(),
  }]);
  const messageScrollRef = useRef<ScrollView>(null);
  const analytics = dashboard?.analytics_v1;
  const quickPrompts = ['本週先練什麼？', '幫我看弱點', '給我 10 分鐘菜單'];

  useEffect(() => {
    const timer = setTimeout(() => messageScrollRef.current?.scrollToEnd({ animated: true }), 80);
    return () => clearTimeout(timer);
  }, [messages.length, sending]);

  useEffect(() => () => onComposerFocusChange(false), [onComposerFocusChange]);

  const submitMessage = async (rawText = draft) => {
    const text = rawText.trim();
    if (!text || sending) return;
    const userMessage: AiCoachChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      text,
      timestamp: new Date().toISOString(),
    };
    const coachMessageId = `coach-${Date.now()}`;
    const coachMessage: AiCoachChatMessage = {
      id: coachMessageId,
      role: 'coach',
      text: '',
      timestamp: new Date().toISOString(),
    };
    const nextMessages = [...messages, userMessage, coachMessage];
    setMessages(nextMessages);
    setDraft('');
    setSending(true);
    RNKeyboard.dismiss();
    try {
      const result = await onSend(text, nextMessages, (delta) => {
        setMessages((current) => current.map((message) => (
          message.id === coachMessageId ? { ...message, text: `${message.text}${delta}` } : message
        )));
      });
      setMessages((current) => current.map((message) => {
        if (message.id !== coachMessageId) return message;
        return {
          ...message,
          text: result.reply || message.text || '我沒有收到有效回覆，請再問一次。',
          timestamp: result.timestamp || message.timestamp,
          status: result.status,
        };
      }));
    } catch (error) {
      setMessages((current) => current.map((message) => (
        message.id === coachMessageId
          ? { ...message, text: error instanceof Error ? `連線失敗：${error.message}` : '連線失敗，請稍後再試。', status: 'error' }
          : message
      )));
    } finally {
      setSending(false);
    }
  };

  return (
    <View style={styles.coachChatPage}>
      <DualActionHeader
        title="AI 教練聊天室"
        left={<MessageCircle size={22} color={ink} strokeWidth={2.4} />}
        right={sending ? <ActivityIndicator color={purple} /> : <ShieldCheck size={20} color={success} strokeWidth={2.4} />}
      />
      <View style={styles.homeDivider} />
      <View style={styles.coachChatInsight}>
        <Text style={styles.coachChatInsightLabel}>目前背景</Text>
        <Text style={styles.coachChatInsightText} numberOfLines={3}>
          {analytics?.coach_summary || '資料還少也可以直接聊天，AI 教練會先用通用撞球訓練邏輯回答。'}
        </Text>
      </View>
      <ScrollView
        ref={messageScrollRef}
        style={styles.coachMessageScroll}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.coachChatMessages}
        keyboardShouldPersistTaps="handled"
      >
        {messages.map((message) => {
          const isUser = message.role === 'user';
          return (
            <View key={message.id} style={[styles.coachMessageRow, isUser && styles.coachMessageRowUser]}>
              <View style={[styles.coachMessageBubble, isUser ? styles.coachMessageBubbleUser : styles.coachMessageBubbleCoach, message.status === 'error' && styles.coachMessageBubbleError]}>
                {message.text ? <Text style={[styles.coachMessageText, isUser && styles.coachMessageTextUser]}>{message.text}</Text> : (
                  <View style={styles.coachTypingBubble}>
                    <ActivityIndicator color={purple} size="small" />
                    <Text style={styles.coachTypingText}>串流回覆中</Text>
                  </View>
                )}
              </View>
            </View>
          );
        })}
      </ScrollView>
      <View style={styles.coachBottomDock}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.coachPromptStrip} keyboardShouldPersistTaps="handled">
          {quickPrompts.map((prompt) => (
            <Pressable key={prompt} style={styles.coachPromptChip} onPress={() => submitMessage(prompt)} disabled={sending}>
              <Text style={styles.coachPromptText}>{prompt}</Text>
            </Pressable>
          ))}
        </ScrollView>
        <View style={styles.coachComposer}>
          <TextInput
            style={styles.coachInput}
            value={draft}
            onChangeText={setDraft}
            placeholder="問 AI 教練..."
            placeholderTextColor="#9CA3AF"
            multiline
            maxLength={500}
            returnKeyType="send"
            onFocus={() => onComposerFocusChange(true)}
            onBlur={() => onComposerFocusChange(false)}
          />
          <Pressable style={[styles.coachSendButton, (!draft.trim() || sending) && styles.coachSendButtonDisabled]} onPress={() => submitMessage()} disabled={!draft.trim() || sending}>
            <Send size={18} color="#fff" strokeWidth={2.6} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function FollowUserRow({ item, onPress }: { item: MobileFollowUser; onPress: (target: AuthorProfileTarget) => void }) {
  const displayName = item.display_name?.trim() || item.user.username;
  const meta = item.is_self ? '你' : item.is_following ? '已追蹤' : item.player_level || 'CueVex 玩家';
  return (
    <Pressable
      style={styles.followUserRow}
      onPress={() => onPress({
        userId: item.user.id,
        previewName: displayName,
        previewAvatarUrl: item.avatar_url || '',
        previewLevel: item.player_level || '',
      })}
    >
      <View style={styles.followUserAvatar}><AvatarImage uri={item.avatar_url || ''} imageStyle={styles.followUserAvatarImage} iconSize={18} /></View>
      <View style={styles.followUserCopy}>
        <Text style={styles.rowTitle} numberOfLines={1}>{displayName}</Text>
        <Text style={styles.rowMeta} numberOfLines={1}>{meta}</Text>
      </View>
      <ChevronRight size={16} color={muted} />
    </Pressable>
  );
}

function CommunitySettingsPage({ onBack, onEditProfile, onOpenPrivacy, onOpenNotifications, onOpenFavorites, onOpenBlockedSafety, onLogout }: { onBack: () => void; onEditProfile: () => void; onOpenPrivacy: () => void; onOpenNotifications: () => void; onOpenFavorites: () => void; onOpenBlockedSafety: () => void; onLogout: () => void }) {
  return (
    <ScrollView showsVerticalScrollIndicator={false} style={[styles.profileFlatPage, styles.settingsPage]} contentContainerStyle={styles.settingsPageContent}>
      <View style={styles.settingsHeaderWrap}>
        <DualActionHeader
          title="設定"
          left={<BackLabelContent />}
          onLeft={onBack}
        />
      </View>
      <View style={styles.settingsTopDivider} />
        <CommunitySettingsPanel onEditProfile={onEditProfile} onOpenPrivacy={onOpenPrivacy} onOpenNotifications={onOpenNotifications} onOpenFavorites={onOpenFavorites} onOpenBlockedSafety={onOpenBlockedSafety} onLogout={onLogout} />
    </ScrollView>
  );
}

function CommunitySettingsPanel({ onEditProfile, onOpenPrivacy, onOpenNotifications, onOpenFavorites, onOpenBlockedSafety, onLogout }: { onEditProfile: () => void; onOpenPrivacy: () => void; onOpenNotifications: () => void; onOpenFavorites: () => void; onOpenBlockedSafety: () => void; onLogout: () => void }) {
  const showComingSoon = (label: string) => Alert.alert(label, '此設定項目介面已建立，後續可串接社群設定 API。');
  return (
    <View style={styles.settingsPanel}>
      <View style={styles.settingsGroup}>
        <SettingsRow icon={<User size={18} color={purple} />} label="帳號管理中心" onPress={onEditProfile} />
        <SettingsRow icon={<Lock size={18} color={purple} />} label="帳號隱私" onPress={onOpenPrivacy} />
        <SettingsRow icon={<Bell size={18} color={purple} />} label="通知設定" onPress={onOpenNotifications} />
        <SettingsRow icon={<Bookmark size={18} color={purple} />} label="我的收藏" onPress={onOpenFavorites} />
        <SettingsRow icon={<Users size={18} color={purple} />} label="社群顯示設定" onPress={() => showComingSoon('社群顯示設定')} />
        <SettingsRow icon={<ShieldCheck size={18} color={purple} />} label="封鎖與安全" onPress={onOpenBlockedSafety} />
      </View>
      <View style={styles.settingsLogoutGroup}>
        <SettingsRow icon={<LogOut size={18} color={danger} />} label="登出" danger onPress={onLogout} />
      </View>
    </View>
  );
}

function AccountPrivacyPage({ isPrivate, loading, onBack, onToggle }: { isPrivate: boolean; loading: boolean; onBack: () => void; onToggle: (value: boolean) => void }) {
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title="帳號隱私" onBack={onBack} />
      <View style={styles.accountPrivacyDivider} />
      <Pressable style={styles.accountPrivacyRow} onPress={() => onToggle(!isPrivate)} disabled={loading}>
        <Text style={styles.accountPrivacyLabel}>私人帳號</Text>
        <View style={[styles.accountPrivacySwitch, isPrivate && styles.accountPrivacySwitchOn, loading && styles.accountPrivacySwitchDisabled]}>
          {loading ? (
            <ActivityIndicator color={isPrivate ? '#fff' : purple} size="small" />
          ) : (
            <View style={[styles.accountPrivacySwitchThumb, isPrivate && styles.accountPrivacySwitchThumbOn]} />
          )}
        </View>
      </Pressable>
      <Text style={styles.accountPrivacyDescription}>
        切換為私人帳號後，只有你同意的用戶才能追蹤你，並觀看你的數據。你的個人貼文也不會出現在公共推薦頁面中，這不會影響你現有的追蹤者。
      </Text>
    </View>
  );
}

function AccountStatusPage({
  confirming,
  password,
  loading,
  onBack,
  onChangePassword,
  onCancelConfirm,
  onConfirmAction,
  onSubmitConfirm,
}: {
  confirming: AccountStatusActionType | null;
  password: string;
  loading: boolean;
  onBack: () => void;
  onChangePassword: (value: string) => void;
  onCancelConfirm: () => void;
  onConfirmAction: (action: AccountStatusActionType) => void;
  onSubmitConfirm: () => void;
}) {
  const title = confirming === 'delete' ? '刪除帳號' : '停用帳號';
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title="帳號狀態" onBack={onBack} />
      <View style={styles.accountPrivacyDivider} />
      <View style={styles.accountCenterGroup}>
        <View style={styles.accountCenterRow}>
          <Text style={styles.accountCenterLabel}>帳號健康狀態</Text>
          <Text style={styles.accountStatusGood}>良好</Text>
        </View>
      </View>
      <View style={styles.accountStatusActions}>
        <Pressable style={styles.accountStatusCardButton} onPress={() => onConfirmAction('deactivate')}>
          <Text style={styles.accountStatusButtonText}>停用帳號</Text>
        </Pressable>
        <Pressable style={[styles.accountStatusCardButton, styles.accountStatusDangerButton]} onPress={() => onConfirmAction('delete')}>
          <Text style={[styles.accountStatusButtonText, styles.accountStatusDangerText]}>刪除帳號</Text>
        </Pressable>
      </View>
      <Modal visible={Boolean(confirming)} transparent animationType="fade" onRequestClose={onCancelConfirm}>
        <View style={styles.confirmModalOverlay}>
          <View style={styles.confirmModalBox}>
            <Text style={styles.confirmModalTitle}>{title}</Text>
            <Text style={styles.confirmModalText}>
              {confirming === 'delete'
                ? '此操作將永久註銷您的帳號。系統將刪除您所有的個人資料、歷史戰績、軌跡數據與發佈貼文，且所有數據一經清空即無法復原。'
                : '啟用後，您的帳號將進入暫時停權狀態。您的個人檔案、數據與貼文將會被安全封存並對外隱藏。此操作不會刪除任何資料，您只需重新登入帳號即可隨時恢復使用。'}
            </Text>
            <TextInput style={styles.confirmPasswordInput} value={password} onChangeText={onChangePassword} placeholder="輸入密碼" placeholderTextColor="#9CA3AF" secureTextEntry />
            <View style={styles.confirmModalActions}>
              <Pressable style={styles.confirmCancelButton} onPress={onCancelConfirm} disabled={loading}>
                <Text style={styles.confirmCancelText}>取消</Text>
              </Pressable>
              <Pressable style={styles.confirmSubmitButton} onPress={onSubmitConfirm} disabled={loading}>
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.confirmSubmitText}>確認</Text>}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function FavoritesPage({
  posts,
  loading,
  currentUserId,
  currentAvatarUrl,
  currentPlayerLevel,
  onBack,
  onDelete,
  onAuthorPress,
  onToggleLike,
  onToggleBookmark,
  onCreateComment,
  onLoadComments,
  onToggleCommentLike,
}: {
  posts: CommunityPost[];
  loading: boolean;
  currentUserId: number;
  currentAvatarUrl: string;
  currentPlayerLevel: string;
  onBack: () => void;
  onDelete: (post: CommunityPost) => void;
  onAuthorPress: (target: AuthorProfileTarget) => void;
  onToggleLike: (post: CommunityPost) => void;
  onToggleBookmark: (post: CommunityPost) => void;
  onCreateComment: (post: CommunityPost, body: string) => Promise<CommunityComment | undefined>;
  onLoadComments: (post: CommunityPost) => Promise<CommunityComment[]>;
  onToggleCommentLike: (comment: CommunityComment) => Promise<CommunityComment>;
}) {
  return (
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.settingsSubPageContent}>
      <SimpleSubPageHeader title="我的收藏" onBack={onBack} />
      <View style={styles.accountPrivacyDivider} />
      {loading ? <ActivityIndicator color={purple} /> : null}
      {!loading && posts.length === 0 ? <FlatMessage text="目前沒有收藏的貼文。" /> : null}
      {posts.map((post) => (
        <PostCard key={post.id} post={post} fallbackAuthor="" fallbackAvatarUrl="" currentUserId={currentUserId} currentAvatarUrl={currentAvatarUrl} currentPlayerLevel={currentPlayerLevel} onDelete={onDelete} onAuthorPress={onAuthorPress} onToggleLike={onToggleLike} onToggleBookmark={onToggleBookmark} onCreateComment={onCreateComment} onLoadComments={onLoadComments} onToggleCommentLike={onToggleCommentLike} />
      ))}
    </ScrollView>
  );
}

function BlockedSafetyPage({ users, loading, updating, onBack, onUnblock }: { users: MobileBlockedUser[]; loading: boolean; updating: boolean; onBack: () => void; onUnblock: (userId: number) => void }) {
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title="封鎖與安全" onBack={onBack} />
      <View style={styles.accountPrivacyDivider} />
      {loading ? <ActivityIndicator color={purple} /> : null}
      {!loading && users.length === 0 ? <FlatMessage text="目前沒有封鎖的用戶。" /> : null}
      <View style={styles.accountCenterGroup}>
        {users.map((item) => (
          <View key={item.user.id} style={styles.blockedUserRow}>
            <View style={styles.blockedUserAvatar}>
              <AvatarImage uri={item.avatar_url || ''} imageStyle={styles.blockedUserAvatarImage} iconSize={18} />
            </View>
            <View style={styles.blockedUserCopy}>
              <Text style={styles.blockedUserName}>{item.display_name || item.user.username}</Text>
              <Text style={styles.blockedUserMeta}>@{item.user.username}</Text>
            </View>
            <Pressable style={styles.unblockButton} onPress={() => onUnblock(item.user.id)} disabled={updating}>
              <Text style={styles.unblockButtonText}>解除封鎖</Text>
            </Pressable>
          </View>
        ))}
      </View>
    </View>
  );
}

function NotificationSettingsPage({
  pushEnabled,
  loading,
  saving,
  onBack,
  onTogglePush,
  onOpenPost,
  onOpenComment,
  onOpenFriends,
  onOpenSystem,
  onOpenDisplay,
  onOpenQuietHours,
}: {
  pushEnabled: boolean;
  loading: boolean;
  saving: boolean;
  onBack: () => void;
  onTogglePush: () => void;
  onOpenPost: () => void;
  onOpenComment: () => void;
  onOpenFriends: () => void;
  onOpenSystem: () => void;
  onOpenDisplay: () => void;
  onOpenQuietHours: () => void;
}) {
  const locked = loading || saving;
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title="通知設定" onBack={onBack} />
      <View style={styles.accountPrivacyDivider} />
      <View style={styles.accountCenterGroup}>
        {loading ? <ActivityIndicator color={purple} /> : null}
        <NotificationSettingSwitchRow label="推播通知" value={pushEnabled} disabled={locked} onToggle={onTogglePush} />
        <View style={styles.accountPrivacyDivider} />
        <NotificationCategoryRow label="貼文互動" disabled={locked || !pushEnabled} dimmed={!pushEnabled} onPress={onOpenPost} />
        <NotificationCategoryRow label="留言互動" disabled={locked || !pushEnabled} dimmed={!pushEnabled} onPress={onOpenComment} />
        <NotificationCategoryRow label="追蹤與好友" disabled={locked || !pushEnabled} dimmed={!pushEnabled} onPress={onOpenFriends} />
        <NotificationCategoryRow label="系統通知" disabled={locked || !pushEnabled} dimmed={!pushEnabled} onPress={onOpenSystem} />
        <NotificationCategoryRow label="通知顯示方式" disabled={locked || !pushEnabled} dimmed={!pushEnabled} onPress={onOpenDisplay} />
        <NotificationCategoryRow label="靜音時段" disabled={locked || !pushEnabled} dimmed={!pushEnabled} onPress={onOpenQuietHours} />
      </View>
    </View>
  );
}

function NotificationSectionTogglePage({
  title,
  items,
  settings,
  pushEnabled,
  loading,
  saving,
  onBack,
  onToggleSetting,
}: {
  title: string;
  items: Array<{ key: NotificationSettingKey; label: string }>;
  settings: NotificationSettingsState;
  pushEnabled: boolean;
  loading: boolean;
  saving: boolean;
  onBack: () => void;
  onToggleSetting: (key: NotificationSettingKey) => void;
}) {
  const locked = loading || saving || !pushEnabled;
  return (
    <View style={styles.accountFieldPage}>
      <SimpleSubPageHeader title={title} onBack={onBack} />
      <View style={styles.accountPrivacyDivider} />
      <View style={styles.accountCenterGroup}>
        {loading ? <ActivityIndicator color={purple} /> : null}
        {items.map((item) => (
          <NotificationSettingSwitchRow key={item.key} label={item.label} value={settings[item.key]} disabled={locked} dimmed={!pushEnabled} onToggle={() => onToggleSetting(item.key)} />
        ))}
      </View>
    </View>
  );
}

function NotificationCategoryRow({ label, disabled, dimmed = false, onPress }: { label: string; disabled: boolean; dimmed?: boolean; onPress: () => void }) {
  return (
    <Pressable style={styles.accountCenterRow} onPress={onPress} disabled={disabled}>
      <Text style={[styles.accountCenterLabel, dimmed && styles.notificationMutedText]}>{label}</Text>
      <ChevronRight size={18} color={dimmed ? '#9CA3AF' : muted} strokeWidth={2.2} />
    </Pressable>
  );
}

function NotificationSettingSwitchRow({ label, value, disabled = false, dimmed = false, onToggle }: { label: string; value: boolean; disabled?: boolean; dimmed?: boolean; onToggle: () => void }) {
  return (
    <View style={styles.accountCenterRow}>
      <Text style={[styles.accountCenterLabel, dimmed && styles.notificationMutedText]}>{label}</Text>
      <Switch value={value} disabled={disabled} onValueChange={onToggle} onTintColor={purple} ios_backgroundColor="#CBD5E1" thumbColor="#fff" trackColor={{ false: '#CBD5E1', true: purple }} />
    </View>
  );
}

function SettingsRow({ icon, label, description, danger: isDanger, onPress }: { icon: React.ReactNode; label: string; description?: string; danger?: boolean; onPress?: () => void }) {
  return (
    <Pressable style={styles.settingsRow} onPress={onPress}>
      <View style={[styles.settingsIconSlot, isDanger && styles.settingsIconDanger]}><>{icon}</></View>
      <View style={styles.settingsCopy}>
        <Text style={[styles.settingsText, isDanger && { color: danger }]}>{label}</Text>
        {description ? <Text style={styles.settingsDescription}>{description}</Text> : null}
      </View>
      <ChevronRight size={16} color={muted} />
    </Pressable>
  );
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
  shell: { flex: 1, backgroundColor: '#fff' },
  shellWeb: {
    flex: 1,
    height: '100%',
    maxHeight: '100%',
    justifyContent: 'flex-start',
    alignItems: 'center',
    backgroundColor: '#fff',
    paddingTop: 0,
    overflow: 'hidden',
  },
  phone: { flex: 1, backgroundColor: '#fff', position: 'relative' },
  phoneWeb: {
    width: '100%',
    maxWidth: 430,
    height: '100%',
    maxHeight: '100%',
    alignSelf: 'center',
    backgroundColor: '#fff',
    flex: 1,
    flexShrink: 1,
    minHeight: 0,
    position: 'relative',
    borderRadius: 0,
    borderLeftWidth: 0,
    borderRightWidth: 0,
    borderTopWidth: 0,
    borderBottomWidth: 0,
    borderColor: line,
    overflow: 'hidden',
    shadowColor: '#0F172A',
    shadowOpacity: 0.28,
    shadowRadius: 32,
  },
  content: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 132, backgroundColor: '#fff' },
  contentFrame: { flex: 1, minHeight: 0, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 96, backgroundColor: '#fff' },
  authContentFrame: { flex: 1, minHeight: 0, backgroundColor: '#fff' },
  stack: { gap: 16 },
  homeContentFrame: { flex: 1, minHeight: 0, paddingTop: 18, paddingBottom: Platform.OS === 'web' ? 0 : 88, backgroundColor: '#fff' },
  homeFeedContent: { paddingHorizontal: 20, paddingBottom: 90 },
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
  splashPage: { flex: 1, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  splashLogo: { width: 240, height: 240 },
  welcomePage: { flex: 1, backgroundColor: '#fff', paddingHorizontal: 28, paddingTop: 86, paddingBottom: 48, justifyContent: 'space-between' },
  welcomeTop: { alignItems: 'center', gap: 42 },
  welcomeTitle: { ...appTextFont, color: ink, fontSize: 30, fontWeight: '900', letterSpacing: 0 },
  welcomeLogo: { width: 240, height: 240 },
  authActions: { gap: 14 },
  authPrimaryButton: { width: '100%', height: 54, borderRadius: 14, backgroundColor: ink, alignItems: 'center', justifyContent: 'center' },
  authPrimaryButtonText: { ...appTextFont, color: '#fff', fontSize: 15, fontWeight: '900' },
  authSecondaryButton: { width: '100%', height: 54, borderRadius: 14, borderWidth: 1, borderColor: line, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  authSecondaryButtonText: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  authKeyboardPage: { flex: 1, backgroundColor: '#fff' },
  authScrollContent: { flexGrow: 1, paddingHorizontal: 28, paddingTop: 18, paddingBottom: 18 },
  authScrollContentWeb: { justifyContent: 'center', paddingTop: 12, paddingBottom: 12 },
  authTopRow: { minHeight: 44, alignItems: 'flex-start', justifyContent: 'center' },
  authBackText: { ...appTextFont, color: muted, fontSize: 14, fontWeight: '800' },
  authForm: { flexGrow: 0, justifyContent: 'flex-start', gap: 18, paddingTop: 18, paddingBottom: 12 },
  authHelperText: { ...appTextFont, color: muted, fontSize: 12, lineHeight: 18, fontWeight: '700', textAlign: 'center' },
  authErrorBox: { width: '100%', borderRadius: 12, borderWidth: 1, borderColor: '#FECACA', backgroundColor: '#FEF2F2', paddingHorizontal: 14, paddingVertical: 12 },
  authErrorText: { ...appTextFont, color: '#991B1B', fontSize: 14, lineHeight: 20, fontWeight: '900', textAlign: 'center' },
  loginWrap: { flexGrow: 1, justifyContent: 'center', gap: 14 },
  brand: { ...appTextFont, color: purple, fontSize: 18, fontWeight: '900' },
  loginTitle: { ...appTextFont, color: ink, fontSize: 32, fontWeight: '900', letterSpacing: 0 },
  loginCopy: { ...appTextFont, color: muted, fontSize: 14, lineHeight: 21, fontWeight: '700' },
  autoEndpointCard: { backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12, gap: 4 },
  autoEndpointLabel: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  autoEndpointValue: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '800' },
  inputGroup: { gap: 7 },
  inputLabel: { ...appTextFont, color: ink, fontSize: 12, fontWeight: '900' },
  input: { ...appTextFont, height: 48, borderRadius: 15, borderWidth: 1, borderColor: line, backgroundColor: '#fff', paddingHorizontal: 14, color: ink, fontSize: 16, fontWeight: '800' },
  pageHeader: { minHeight: 34, alignItems: 'center', justifyContent: 'center', position: 'relative' },
  pageTitle: { ...appTextFont, maxWidth: '68%', color: ink, fontSize: 18, fontWeight: '900' },
  headerAction: { position: 'absolute', right: 0 },
  headerLeftAction: { position: 'absolute', left: -8 },
  backLabelButton: { minWidth: 64, height: 34, flexDirection: 'row', alignItems: 'center', gap: 2 },
  backLabelText: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
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
  abilityHero: { minHeight: 194, borderRadius: 18, backgroundColor: '#111827', padding: 18, gap: 10, shadowColor: '#0F172A', shadowOpacity: 0.18, shadowRadius: 18, elevation: 8 },
  abilityHeroLabel: { ...appTextFont, color: '#CBD5E1', fontSize: 13, fontWeight: '900' },
  abilityScoreRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, marginTop: 2 },
  abilityScoreValue: { ...appTextFont, color: '#fff', fontSize: 54, lineHeight: 60, fontWeight: '900', letterSpacing: 0 },
  abilityScoreMax: { ...appTextFont, color: '#CBD5E1', fontSize: 18, lineHeight: 30, fontWeight: '900' },
  abilityLevel: { ...appTextFont, color: '#fff', fontSize: 17, fontWeight: '900' },
  abilityBasis: { ...appTextFont, color: '#CBD5E1', fontSize: 12, lineHeight: 18, fontWeight: '700' },
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
  overviewCardStrip: { alignItems: 'stretch' },
  overviewSwipeCard: { minHeight: 132, borderRadius: 16, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#fff', padding: 16, justifyContent: 'space-between' },
  overviewCardLabel: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '900' },
  overviewCardValue: { ...appTextFont, color: ink, fontSize: 24, fontWeight: '900', letterSpacing: 0 },
  overviewCardPair: { gap: 4 },
  overviewCardSubLabel: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '800' },
  overviewCardSubValue: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  overviewTwoCols: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 20 },
  overviewScoreLine: { flexDirection: 'row', alignItems: 'flex-end', gap: 5 },
  overviewScoreValue: { ...appTextFont, color: ink, fontSize: 36, lineHeight: 40, fontWeight: '900' },
  overviewScoreMax: { ...appTextFont, color: muted, fontSize: 14, lineHeight: 24, fontWeight: '900' },
  overviewBasis: { ...appTextFont, color: muted, fontSize: 11, lineHeight: 16, fontWeight: '700', marginTop: 6 },
  overviewDots: { flexDirection: 'row', alignSelf: 'center', alignItems: 'center', gap: 6, marginTop: -6 },
  overviewDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D1D5DB' },
  overviewDotActive: { width: 18, backgroundColor: purple },
  weeklySummaryBlock: { gap: 12 },
  weeklyMetricGrid: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14 },
  weeklyMetricItem: { flex: 1, alignItems: 'flex-start', gap: 4, minWidth: 0 },
  weeklyMetricLabel: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '900' },
  weeklyMetricValueRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 3 },
  weeklyMetricValue: { ...appTextFont, color: ink, fontSize: 24, lineHeight: 30, fontWeight: '900' },
  weeklyMetricUnit: { ...appTextFont, color: muted, fontSize: 11, lineHeight: 20, fontWeight: '800' },
  chartSection: { gap: 12 },
  chartTabs: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chartTab: { flex: 1, height: 40, borderRadius: 12, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  chartTabActive: { borderColor: purple, backgroundColor: '#F5F3FF' },
  chartTabText: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '900' },
  chartTabTextActive: { color: purple },
  overviewChartWrap: { marginTop: 2 },
  chartTouchLayer: { position: 'absolute', left: 0, right: 0, top: 34, height: 144 },
  chartTouchZone: { position: 'absolute', top: 0, bottom: 0 },
  chartEmptyText: { ...appTextFont, position: 'absolute', left: 0, right: 0, top: 104, color: muted, fontSize: 12, fontWeight: '900', textAlign: 'center' },
  radarWrap: { height: 250, alignItems: 'center', justifyContent: 'center', marginTop: 6 },
  coachSummaryText: { ...appTextFont, color: '#1F2937', fontSize: 14, lineHeight: 22, fontWeight: '800', marginTop: 10 },
  coachChatPage: { flex: 1, minHeight: 0, backgroundColor: '#fff' },
  coachChatInsight: { marginTop: 14, borderRadius: 16, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#F8FAFC', padding: 14, gap: 5 },
  coachChatInsightLabel: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  coachChatInsightText: { ...appTextFont, color: ink, fontSize: 13, lineHeight: 19, fontWeight: '800' },
  coachMessageScroll: { flex: 1, minHeight: 0 },
  coachChatMessages: { flexGrow: 1, paddingTop: 14, paddingBottom: 12, gap: 10 },
  coachMessageRow: { width: '100%', alignItems: 'flex-start' },
  coachMessageRowUser: { alignItems: 'flex-end' },
  coachMessageBubble: { maxWidth: '86%', borderRadius: 16, paddingHorizontal: 13, paddingVertical: 10 },
  coachMessageBubbleCoach: { backgroundColor: '#F3F4F6', borderTopLeftRadius: 6 },
  coachMessageBubbleUser: { backgroundColor: purple, borderTopRightRadius: 6 },
  coachMessageBubbleError: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA' },
  coachMessageText: { ...appTextFont, color: ink, fontSize: 13, lineHeight: 20, fontWeight: '800' },
  coachMessageTextUser: { color: '#fff' },
  coachTypingBubble: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  coachTypingText: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800' },
  coachBottomDock: { gap: 8, paddingTop: 6 },
  coachPromptStrip: { gap: 8, paddingBottom: 0 },
  coachPromptChip: { height: 34, borderRadius: 17, borderWidth: 1, borderColor: '#DDD6FE', backgroundColor: '#F5F3FF', paddingHorizontal: 12, alignItems: 'center', justifyContent: 'center' },
  coachPromptText: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  coachComposer: { minHeight: 50, flexDirection: 'row', alignItems: 'flex-end', gap: 10, borderRadius: 16, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#fff', paddingHorizontal: 10, paddingVertical: 8 },
  coachInput: { ...appTextFont, flex: 1, maxHeight: 92, minHeight: 32, color: ink, fontSize: 14, lineHeight: 20, fontWeight: '800', paddingHorizontal: 0, paddingVertical: 6 },
  coachSendButton: { width: 34, height: 34, borderRadius: 17, backgroundColor: purple, alignItems: 'center', justifyContent: 'center' },
  coachSendButtonDisabled: { backgroundColor: '#C4B5FD' },
  trendBox: { marginTop: 14, borderRadius: 12, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E5E7EB', padding: 12, gap: 4 },
  trendLabel: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  trendSummary: { ...appTextFont, color: muted, fontSize: 12, lineHeight: 18, fontWeight: '700' },
  abilityList: { gap: 14, marginTop: 12 },
  abilityRow: { gap: 8 },
  abilityRowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  abilityName: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  abilityValue: { ...appTextFont, color: purple, fontSize: 14, fontWeight: '900' },
  weaknessTitle: { ...appTextFont, color: ink, fontSize: 24, fontWeight: '900', marginTop: 10 },
  weaknessText: { ...appTextFont, color: muted, fontSize: 13, lineHeight: 20, fontWeight: '800', marginTop: 6 },
  trainingList: { gap: 12, marginTop: 12 },
  trainingRow: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 12, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#F8FAFC', padding: 12 },
  trainingBadge: { width: 42, height: 42, borderRadius: 21, backgroundColor: purple, alignItems: 'center', justifyContent: 'center' },
  trainingBadgeText: { ...appTextFont, color: '#fff', fontSize: 15, fontWeight: '900' },
  trainingCopy: { flex: 1, minWidth: 0 },
  trainingTitle: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  trainingReason: { ...appTextFont, color: muted, fontSize: 12, lineHeight: 18, fontWeight: '700', marginTop: 3 },
  dataSelectorWrap: { position: 'relative', zIndex: 20, marginHorizontal: -20, paddingHorizontal: 20, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  dataSelectorButton: { width: '100%', minHeight: 34, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  dataSelectorText: { ...appTextFont, color: ink, fontSize: 18, fontWeight: '900' },
  dataSelectorDismissLayer: { position: 'absolute', top: 42, left: 0, right: 0, bottom: -1000, zIndex: 25 },
  dataSelectorDismissPressable: { flex: 1 },
  dataSelectorMenu: { position: 'absolute', top: 42, left: 0, right: 0, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#EEF2F7', backgroundColor: '#fff', paddingVertical: 8, paddingHorizontal: 20, zIndex: 30 },
  dataSelectorOption: { minHeight: 40, justifyContent: 'center', alignItems: 'flex-start' },
  dataSelectorOptionActive: { backgroundColor: '#F8FAFC', paddingHorizontal: 10, marginHorizontal: -10 },
  dataSelectorOptionText: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '800' },
  dataSelectorOptionTextActive: { color: purple, fontWeight: '900' },
  dropdown: { height: 40, alignSelf: 'flex-start', paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: line, backgroundColor: '#fff', flexDirection: 'row', alignItems: 'center', gap: 14 },
  dropdownText: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: line, borderRadius: 12, paddingHorizontal: 12, height: 36, backgroundColor: '#fff' },
  pillText: { ...appTextFont, color: ink, fontSize: 12, fontWeight: '800' },
  segment: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: line },
  segmentItem: { flex: 1, alignItems: 'center', paddingBottom: 12 },
  segmentActive: { borderBottomWidth: 2, borderBottomColor: purple },
  segmentText: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '800' },
  segmentTextActive: { color: purple },
  historyRow: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: line },
  historyTypeBadge: { width: 42, height: 42, borderRadius: 21, backgroundColor: purple, alignItems: 'center', justifyContent: 'center' },
  historyTypeBadgeWin: { backgroundColor: success },
  historyTypeBadgeLoss: { backgroundColor: purple },
  historyTypeBadgeText: { ...appTextFont, color: '#fff', fontSize: 14, fontWeight: '900' },
  detailBackButton: { alignSelf: 'flex-start', minHeight: 34, flexDirection: 'row', alignItems: 'center', gap: 2 },
  historyDetailHero: { alignItems: 'center', gap: 8, paddingVertical: 8 },
  historyDetailBadge: { minWidth: 52, height: 28, paddingHorizontal: 10, borderRadius: 14, backgroundColor: '#EEF2FF', alignItems: 'center', justifyContent: 'center' },
  historyDetailBadgeText: { ...appTextFont, color: purple, fontSize: 12, fontWeight: '900' },
  historyDetailTitle: { ...appTextFont, color: ink, fontSize: 20, fontWeight: '900', textAlign: 'center' },
  historyDetailMeta: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800', textAlign: 'center' },
  detailList: { marginTop: 12, borderTopWidth: 1, borderTopColor: line },
  detailRow: { minHeight: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  detailLabel: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '900' },
  detailValue: { ...appTextFont, flex: 1, color: ink, fontSize: 13, fontWeight: '900', textAlign: 'right' },
  offenseHeroGrid: { flexDirection: 'row', gap: 12, marginTop: 14 },
  offenseHeroMetric: { flex: 1, borderRadius: 14, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#F8FAFC', padding: 12 },
  shapeRow: { gap: 8 },
  matchRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: line },
  rowTitle: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  rowMeta: { ...appTextFont, color: muted, fontSize: 11, fontWeight: '700', marginTop: 3 },
  resultText: { ...appTextFont, fontSize: 12, fontWeight: '900' },
  scoreText: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900', marginTop: 2 },
  scanStack: { flex: 1, justifyContent: 'center' },
  scanPanel: { width: '100%', alignItems: 'center' },
  scanVisualSlot: { width: '100%', aspectRatio: 1, marginTop: 16, marginBottom: 14, alignItems: 'center', justifyContent: 'center' },
  qrScanner: { width: 226, height: 226, alignItems: 'center', justifyContent: 'center' },
  corner: { position: 'absolute', width: 34, height: 34, borderColor: purple, borderRadius: 6 },
  cameraFrame: { width: '100%', aspectRatio: 1, borderRadius: 20, overflow: 'hidden', backgroundColor: '#000' },
  camera: { flex: 1 },
  myQrBox: { width: 226, gap: 10, alignItems: 'center' },
  primaryButton: { width: '100%', height: 50, borderRadius: 14, backgroundColor: purple, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  primaryButtonText: { ...appTextFont, color: '#fff', fontSize: 14, fontWeight: '900' },
  scanJoiningOverlay: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24, backgroundColor: 'rgba(15,23,42,0.42)' },
  scanJoiningCard: { width: '100%', maxWidth: 320, minHeight: 142, borderRadius: 16, alignItems: 'center', justifyContent: 'center', gap: 12, paddingHorizontal: 22, paddingVertical: 22, backgroundColor: '#fff' },
  scanJoiningTitle: { ...appTextFont, color: ink, fontSize: 18, fontWeight: '900', textAlign: 'center' },
  scanJoiningText: { ...appTextFont, color: muted, fontSize: 13, lineHeight: 20, fontWeight: '800', textAlign: 'center' },
  disabledButton: { opacity: 0.55 },
  searchBox: { height: 42, borderRadius: 16, backgroundColor: '#fff', flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, gap: 8 },
  searchPlaceholder: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '700' },
  friendRow: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: line },
  friendAvatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#E5E7EB', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center' },
  smallButton: { height: 34, paddingHorizontal: 14, borderRadius: 12, backgroundColor: purple, justifyContent: 'center' },
  smallButtonText: { ...appTextFont, color: '#fff', fontSize: 12, fontWeight: '900' },
  profileHeader: { flexDirection: 'row', alignItems: 'center', gap: 13, backgroundColor: '#fff', borderRadius: 18, padding: 16 },
  profileFlatPage: { flex: 1 },
  profileContentFrame: { flex: 1, minHeight: 0, paddingTop: 18, paddingBottom: Platform.OS === 'web' ? 0 : 132, backgroundColor: '#fff' },
  coachChatContentFrame: { flex: 1, minHeight: 0, paddingHorizontal: 20, paddingTop: 18, paddingBottom: Platform.OS === 'web' ? 0 : 116, backgroundColor: '#fff' },
  profileScrollContent: { gap: 14, paddingHorizontal: 20 },
  profileFlatSection: { paddingVertical: 12, gap: 18 },
  profileCard: { backgroundColor: '#fff', borderRadius: 22, borderWidth: 1, borderColor: line, padding: 18, gap: 18, shadowColor: '#0F172A', shadowOpacity: 0.07, shadowRadius: 18, elevation: 3 },
  profileTopRow: { flexDirection: 'row', alignItems: 'center', gap: 13 },
  profileHeroRow: { minHeight: 88, flexDirection: 'row', alignItems: 'stretch', gap: 14 },
  profileHeroContent: { flex: 1, minHeight: 88, justifyContent: 'space-between', paddingVertical: 2 },
  profileAvatar: { width: 88, height: 88, borderRadius: 44, backgroundColor: '#EEF2F7', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  profileAvatarImage: { width: '100%', height: '100%' },
  profileName: { ...appTextFont, color: ink, fontSize: 20, fontWeight: '900' },
  profileIdentityRow: { flexDirection: 'row', alignItems: 'center', gap: 8, minWidth: 0, flexWrap: 'wrap' },
  profileAccountName: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900', maxWidth: 138 },
  profileLevel: { ...appTextFont, alignSelf: 'flex-start', color: purple, backgroundColor: '#EEF2FF', overflow: 'hidden', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4, fontSize: 11, fontWeight: '900' },
  officialLevel: { color: '#fff', backgroundColor: officialBlue },
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
  profileStickyTabs: { marginHorizontal: -20, paddingHorizontal: 20, backgroundColor: '#fff', zIndex: 5, elevation: 5 },
  profileModeTabs: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  profileModeTab: { flex: 1, height: 40, alignItems: 'center', justifyContent: 'center' },
  profileContentDivider: { height: 1, backgroundColor: '#EAECEF', marginHorizontal: -20 },
  profileStatsPanel: { paddingVertical: 4 },
  profileDataRow: { minHeight: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  profileDataLabel: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '800' },
  profileDataValue: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  followListContent: { flexGrow: 1, gap: 12, paddingHorizontal: 20, paddingBottom: 96, backgroundColor: '#fff' },
  followListOwner: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '800', marginTop: -4 },
  followListTabs: { height: 42, flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: '#EAECEF' },
  followListTab: { flex: 1, height: 42, alignItems: 'center', justifyContent: 'center', borderBottomWidth: 2, borderBottomColor: 'transparent' },
  followListTabActive: { borderBottomColor: purple },
  followListTabText: { ...appTextFont, color: muted, fontSize: 14, fontWeight: '900' },
  followListTabTextActive: { color: purple },
  followUserRow: { minHeight: 62, flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: '#EEF2F7', paddingVertical: 10 },
  followUserAvatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: '#EEF2F7', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  followUserAvatarImage: { width: '100%', height: '100%' },
  followUserCopy: { flex: 1, minWidth: 0 },
  editProfilePage: { flex: 1, gap: 22, backgroundColor: '#fff' },
  editAvatarBlock: { alignItems: 'center', gap: 10, paddingTop: 14, paddingBottom: 18 },
  editAvatar: { width: 104, height: 104, borderRadius: 52, backgroundColor: '#EEF2F7', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  editAvatarImage: { width: '100%', height: '100%' },
  changeAvatarText: { ...appTextFont, color: purple, fontSize: 14, fontWeight: '900' },
  editFieldRow: { minHeight: 58, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#EAECEF', justifyContent: 'center', gap: 6, paddingVertical: 10 },
  editFieldLabel: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800' },
  editFieldInput: { ...appTextFont, color: ink, fontSize: 16, fontWeight: '800', padding: 0 },
  editBioInput: { ...appTextFont, minHeight: 58, lineHeight: 22, textAlignVertical: 'top' },
  accountCenterGroup: { marginHorizontal: -20, backgroundColor: '#fff' },
  accountCenterRow: { minHeight: 58, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 16, paddingHorizontal: 20, paddingVertical: 12 },
  accountCenterLabel: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  accountCenterRight: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 8, minWidth: 0 },
  accountCenterValue: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '700', flexShrink: 1, textAlign: 'right' },
  accountCenterDivider: { height: 1, marginHorizontal: -20, backgroundColor: '#F1F5F9' },
  accountFieldPage: { flex: 1, gap: 18, backgroundColor: '#fff' },
  accountFieldInputWrap: { minHeight: 52, marginHorizontal: -20, paddingLeft: 20, paddingRight: 48, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#F1F5F9', justifyContent: 'center', position: 'relative' },
  accountFieldInput: { ...appTextFont, minHeight: 50, color: ink, fontSize: 16, fontWeight: '800', paddingVertical: 12, paddingHorizontal: 0 },
  accountFieldBioInput: { minHeight: 112, lineHeight: 22, textAlignVertical: 'top' },
  accountFieldClear: { position: 'absolute', right: 18, top: 0, bottom: 0, width: 28, alignItems: 'center', justifyContent: 'center' },
  accountFieldHint: { ...appTextFont, color: muted, fontSize: 12, lineHeight: 18, fontWeight: '700' },
  accountPrivacyDivider: { height: 1, marginHorizontal: -20, backgroundColor: '#F1F5F9' },
  accountPrivacyRow: { minHeight: 62, marginHorizontal: -20, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#fff' },
  accountPrivacyLabel: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  accountPrivacyDescription: { ...appTextFont, marginHorizontal: -20, paddingHorizontal: 20, color: muted, fontSize: 12, lineHeight: 18, fontWeight: '700' },
  accountPrivacySwitch: { width: 48, height: 28, borderRadius: 14, padding: 3, alignItems: 'flex-start', justifyContent: 'center', backgroundColor: '#CBD5E1' },
  accountPrivacySwitchOn: { alignItems: 'flex-end', backgroundColor: purple },
  accountPrivacySwitchDisabled: { opacity: 0.72 },
  accountPrivacySwitchThumb: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff', shadowColor: '#0F172A', shadowOpacity: 0.18, shadowRadius: 4, elevation: 2 },
  accountPrivacySwitchThumbOn: { backgroundColor: '#fff' },
  settingsSubPageContent: { flexGrow: 1, gap: 18, paddingBottom: 96, backgroundColor: '#fff' },
  accountStatusGood: { ...appTextFont, color: success, fontSize: 14, fontWeight: '900' },
  accountStatusActions: { marginTop: 'auto', gap: 12, paddingBottom: 12 },
  accountStatusCardButton: { minHeight: 50, borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  accountStatusDangerButton: { borderColor: '#FECACA', backgroundColor: '#FEF2F2' },
  accountStatusButtonText: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  accountStatusDangerText: { color: danger },
  confirmModalOverlay: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 26, backgroundColor: 'rgba(15,23,42,0.36)' },
  confirmModalBox: { width: '100%', borderRadius: 12, backgroundColor: '#fff', padding: 18, gap: 14 },
  confirmModalTitle: { ...appTextFont, color: ink, fontSize: 18, fontWeight: '900' },
  confirmModalText: { ...appTextFont, color: '#374151', fontSize: 13, lineHeight: 20, fontWeight: '700' },
  confirmPasswordInput: { ...appTextFont, height: 46, borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', paddingHorizontal: 12, color: ink, fontSize: 16, fontWeight: '800' },
  confirmModalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10 },
  confirmCancelButton: { minWidth: 72, height: 40, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F3F4F6' },
  confirmCancelText: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  confirmSubmitButton: { minWidth: 72, height: 40, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: purple },
  confirmSubmitText: { ...appTextFont, color: '#fff', fontSize: 14, fontWeight: '900' },
  blockedUserRow: { minHeight: 64, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 20, paddingVertical: 10 },
  blockedUserAvatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#EEF2F7', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  blockedUserAvatarImage: { width: '100%', height: '100%' },
  blockedUserCopy: { flex: 1, minWidth: 0 },
  blockedUserName: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  blockedUserMeta: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '700', marginTop: 2 },
  unblockButton: { minHeight: 34, borderRadius: 8, paddingHorizontal: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F3F4F6' },
  unblockButtonText: { ...appTextFont, color: ink, fontSize: 12, fontWeight: '900' },
  notificationMutedText: { color: '#9CA3AF' },
  headerSpacer: { width: 40 },
  passwordFieldGroup: { marginHorizontal: -20, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#F1F5F9', backgroundColor: '#fff' },
  passwordFieldRow: { minHeight: 58, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 20 },
  passwordFieldLabel: { ...appTextFont, width: 96, color: ink, fontSize: 15, fontWeight: '900' },
  passwordFieldInput: { ...appTextFont, flex: 1, minHeight: 54, color: ink, fontSize: 16, fontWeight: '800', paddingVertical: 10, paddingHorizontal: 0 },
  forgotPasswordText: { ...appTextFont, alignSelf: 'flex-start', color: purple, fontSize: 14, fontWeight: '900' },
  logoutOtherDevicesRow: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 12 },
  checkboxBox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: '#CBD5E1', alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  checkboxBoxChecked: { borderColor: purple, backgroundColor: purple },
  checkboxCheck: { ...appTextFont, color: '#fff', fontSize: 14, fontWeight: '900', lineHeight: 18 },
  logoutOtherDevicesText: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '800' },
  changePasswordButton: { marginTop: 'auto', minHeight: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: purple },
  changePasswordButtonText: { ...appTextFont, color: '#fff', fontSize: 15, fontWeight: '900' },
  loginDevicesPage: { flexGrow: 1, gap: 14, paddingBottom: 96, backgroundColor: '#fff' },
  loginActivityTitle: { ...appTextFont, color: ink, fontSize: 17, fontWeight: '900' },
  loginActivitySection: { ...appTextFont, color: muted, fontSize: 13, fontWeight: '800', marginTop: 4 },
  loginDeviceCard: { minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff' },
  currentDeviceBadge: { ...appTextFont, color: '#16A34A', fontSize: 12, fontWeight: '900' },
  loginDeviceTime: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800' },
  loginDeviceName: { ...appTextFont, color: ink, fontSize: 15, fontWeight: '900' },
  loginDeviceMeta: { ...appTextFont, color: muted, fontSize: 12, fontWeight: '800', marginTop: 4 },
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
  postAvatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#EEF2F7', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  postAvatarImage: { width: '100%', height: '100%' },
  postAuthorRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  postAuthor: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  officialInlineBadge: { ...appTextFont, color: '#fff', backgroundColor: officialBlue, overflow: 'hidden', borderRadius: 999, paddingHorizontal: 7, paddingVertical: 2, fontSize: 10, fontWeight: '900' },
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
  commentAvatar: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#EEF2F7', borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  commentAvatarImage: { width: '100%', height: '100%' },
  commentTextBlock: { flex: 1, gap: 3 },
  commentMetaRow: { minHeight: 18, flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  commentAuthor: { ...appTextFont, color: ink, fontSize: 13, fontWeight: '900' },
  commentLevel: { ...appTextFont, color: purple, fontSize: 11, fontWeight: '900' },
  officialCommentLevel: { color: officialBlue },
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
  commentInput: { ...appTextFont, flex: 1, minHeight: 38, borderRadius: 19, backgroundColor: '#EEF2F7', paddingHorizontal: 14, color: ink, fontSize: 16, fontWeight: '800' },
  commentSendButton: { height: 38, minWidth: 58, borderRadius: 19, backgroundColor: purple, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  commentSendButtonDisabled: { opacity: 0.45 },
  commentSendText: { ...appTextFont, color: '#fff', fontSize: 13, fontWeight: '900' },
  flatMessage: { paddingVertical: 20, borderBottomWidth: 1, borderBottomColor: line },
  flatLogout: { display: 'none' },
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
  composeScrollContent: { paddingBottom: 28, gap: 14 },
  composeTextPanel: { minHeight: 154, borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 12, backgroundColor: '#fff', overflow: 'hidden' },
  composeInput: { ...appTextFont, minHeight: 154, color: ink, fontSize: 16, lineHeight: 24, fontWeight: '700', padding: 16 },
  composeSectionHeader: { minHeight: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  composeSectionTitle: { ...appTextFont, color: ink, fontSize: 16, fontWeight: '900' },
  composeSectionMeta: { ...appTextFont, color: muted, fontSize: 12, lineHeight: 18, fontWeight: '700', marginTop: 2 },
  composePhotoActionButton: { minHeight: 38, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: '#C7D2FE', backgroundColor: '#EEF2FF' },
  composePhotoActionText: { ...appTextFont, color: purple, fontSize: 13, fontWeight: '900' },
  composeEmptyPhoto: { minHeight: 180, marginHorizontal: -20, borderTopWidth: 1, borderBottomWidth: 1, borderColor: line, backgroundColor: '#F8FAFC', alignItems: 'center', justifyContent: 'center', gap: 8 },
  levelBadge: { ...appTextFont, alignSelf: 'flex-start', color: '#047857', backgroundColor: '#ECFDF5', overflow: 'hidden', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3, marginVertical: 4, fontSize: 11, fontWeight: '900' },
  settingsPage: { marginHorizontal: -20, marginBottom: -96, backgroundColor: '#fff' },
  settingsPageContent: { paddingTop: 0, paddingBottom: 32, backgroundColor: '#fff' },
  settingsHeaderWrap: { paddingHorizontal: 20 },
  settingsBackIcon: { transform: [{ rotate: '180deg' }] },
  settingsTopDivider: { height: 1, marginTop: 12, backgroundColor: '#F1F5F9' },
  settingsPanel: { paddingTop: 12, paddingBottom: 24, gap: 18 },
  settingsPanelHeader: { gap: 6, paddingHorizontal: 20, paddingTop: 6, paddingBottom: 2 },
  settingsPanelTitle: { ...appTextFont, color: ink, fontSize: 22, fontWeight: '900' },
  settingsPanelSubtitle: { ...appTextFont, color: muted, fontSize: 13, lineHeight: 19, fontWeight: '700' },
  settingsGroup: { backgroundColor: '#fff' },
  settingsLogoutGroup: { backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  settingsRow: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 20, paddingVertical: 10 },
  settingsIconSlot: { width: 34, height: 34, flexShrink: 0, borderRadius: 17, backgroundColor: '#EEF2FF', alignItems: 'center', justifyContent: 'center' },
  settingsIconDanger: { backgroundColor: '#FEF2F2' },
  settingsCopy: { flex: 1, minWidth: 0, justifyContent: 'center' },
  settingsText: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '900' },
  settingsDescription: { ...appTextFont, color: muted, fontSize: 11, lineHeight: 16, fontWeight: '700' },
  emptyText: { ...appTextFont, marginTop: 14, color: muted, fontSize: 13, lineHeight: 20, fontWeight: '700' },
  bottomNav: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: line },
  bottomNavItems: { height: 72, flexDirection: 'row', paddingHorizontal: 12, paddingTop: 5, paddingBottom: 12 },
  navItem: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
