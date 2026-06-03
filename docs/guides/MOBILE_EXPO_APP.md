# Expo Mobile App Guide

## 06/03: '新增留言 Supabase 優先讀取'

### 架構規範

- `GET /api/community/posts/{post_id}/comments` 優先讀 Supabase `community_comments`。
- Supabase 沒有該貼文留言、資料表不可用或讀取失敗時，fallback SQLite。
- 手機端 endpoint 與回傳格式不變。
- 目前此讀取只提供留言 metadata；`likes` 與 `liked_by_me` 尚未切 Supabase，預設為 `0` / `false`。
- `author_avatar_url` 與 `author_player_level` 暫不 join Supabase profile，缺值時由手機端顯示預設使用者 icon。

### 驗證規範

- 另一台電腦只要設定 Supabase env，就能在留言 sheet 讀到已同步到 Supabase 的留言。
- Supabase 讀不到留言時，本機 SQLite 留言仍維持原行為。

## 06/03: '新增個人頁貼文 Supabase 優先讀取'

### 架構規範

- `GET /api/mobile/users/{target_user_id}/posts` 與 `GET /api/mobile/users/{target_user_id}/profile-page` 優先讀 Supabase `community_posts`。
- Supabase 沒有該使用者貼文、資料表不可用或讀取失敗時，fallback SQLite。
- 手機端 endpoint 與回傳格式不變。
- 目前此讀取只提供貼文 metadata；`likes`、`comments`、`liked_by_me`、`bookmarked_by_me` 仍尚未切 Supabase，預設為 `0` / `false`，待反應資料表同步後再補。

### 驗證規範

- 另一台電腦只要設定 Supabase env，就能在個人頁讀到已同步到 Supabase 的貼文。
- Supabase 讀不到資料時，本機 SQLite 個人頁仍維持原行為。

## 06/03: '新增 community_comments Supabase 留言同步'

### 架構規範

- `POST /api/community/posts/{post_id}/comments` 仍先由 SQLite 驗證貼文存在並新增留言。
- SQLite 新增留言成功後，後端嘗試 upsert Supabase `community_comments`。
- Supabase 同步失敗只記錄 warning，不阻斷 App 留言完成；留言讀取仍走 SQLite。
- 留言按讚尚未同步，保留到下一階段。

### Supabase SQL

```sql
create table if not exists public.community_comments (
  id bigint primary key,
  post_id bigint not null,
  user_id bigint,
  author_name text not null default '',
  body text not null default '',
  created_at timestamptz not null
);

create index if not exists idx_community_comments_post_created
on public.community_comments(post_id, created_at);
```

### 驗證規範

- 新增留言後，App 留言 sheet 立即顯示該留言。
- Supabase `community_comments` 出現同 ID 的留言 metadata。
- Supabase 不可用時，App 不顯示留言失敗。

## 06/03: '新增 community_posts Supabase 刪文同步'

### 架構規範

- `DELETE /api/community/posts/{post_id}` 仍先由 SQLite 驗證作者與刪除本機資料。
- SQLite 刪除成功後，後端嘗試刪除 Supabase `community_posts.id = post_id`。
- Supabase 刪除失敗只記錄 warning，不阻斷 App 刪文完成；目前讀取仍走 SQLite。
- 非作者刪文、貼文不存在時，不呼叫 Supabase delete。

### 驗證規範

- 刪除自己的貼文後，SQLite feed 不再顯示該貼文。
- Supabase `community_posts` 對應 ID 應同步移除。
- Supabase 不可用時，App 仍顯示刪文成功。

## 06/03: '新增 community_posts Supabase 第三階段 metadata 同步'

### 架構規範

- 第三階段 A 只在建立 mobile 貼文後同步寫入 Supabase `community_posts`，讀取、分頁、熱門排序、刪除仍維持 SQLite。
- Supabase 同步失敗時只記錄 warning，不阻斷 `POST /api/community/posts` 回傳；SQLite 仍是目前使用中的主資料。
- mobile 貼文沒有標題，`title` 欄位只作相容用途，mobile 建貼文時固定同步為空字串 `''`。
- `image_urls` 與 `image_transforms` 以 JSON array 寫入 Supabase `jsonb` 欄位。

### Supabase SQL

```sql
create table if not exists public.community_posts (
  id bigint primary key,
  user_id bigint,
  author_name text not null default '',
  badge text not null default '',
  title text not null default '',
  body text not null default '',
  preview_type text not null default 'pool-table',
  recording_id text,
  tone text not null default '',
  image_urls jsonb not null default '[]'::jsonb,
  image_transforms jsonb not null default '[]'::jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

### 驗證規範

- mobile 發一篇含文字或圖片的貼文後，SQLite feed 仍立即顯示該貼文。
- Supabase `community_posts` 出現同 ID 的 metadata。
- Supabase 同步失敗時，App 不顯示分享失敗；後端 console 只出現 warning。

## 06/03: '新增 mobile_profiles Supabase 第二階段同步'

### 架構規範

- 第二階段只同步 mobile 公開個人資料，不遷移登入密碼、security question、auth session。
- FastAPI 仍是手機端唯一 API；mobile app 不直接連 Supabase。
- `GET /api/mobile/profile` 與公開 profile API 讀取時，若 Supabase `mobile_profiles` 有資料，會以 Supabase 的 `display_name`、`bio`、`avatar_url` 覆蓋 SQLite 使用者公開欄位。
- `PATCH /api/mobile/profile` 會先更新 SQLite，接著嘗試 upsert Supabase；若 Supabase 失敗，SQLite 結果仍生效並記錄 warning，避免測試期中斷使用流程。
- 貼文作者頭像目前仍由 SQLite `users.avatar_url` join 提供，因此更新 profile 時會同步 SQLite，確保社群列表不破。

### Supabase SQL

在 Supabase SQL Editor 建立資料表：

```sql
create table if not exists public.mobile_profiles (
  user_id bigint primary key,
  display_name text not null default '',
  bio text not null default '',
  avatar_url text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.set_mobile_profiles_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_mobile_profiles_updated_at on public.mobile_profiles;

create trigger trg_mobile_profiles_updated_at
before update on public.mobile_profiles
for each row
execute function public.set_mobile_profiles_updated_at();
```

### API 規範

手機端 endpoint 不變：

```http
GET /api/mobile/profile
PATCH /api/mobile/profile
GET /api/mobile/users/{target_user_id}/profile
GET /api/mobile/users/{target_user_id}/profile-page
```

`PATCH /api/mobile/profile` body 維持：

```json
{
  "display_name": "Lucian039",
  "bio": "九號球練習中",
  "avatar_url": "https://.../avatar.jpg"
}
```

### 驗證規範

- 更新自己的頭像或名稱後，SQLite `users` 與 Supabase `mobile_profiles` 都有同一份公開 profile。
- Supabase `mobile_profiles` 尚未建立或權限錯誤時，App 仍可用 SQLite profile 正常顯示。
- 別人沒有頭像時不得 fallback 成目前登入者頭像，只能顯示預設使用者 icon。

## 06/03: '新增 mobile Supabase 圖片儲存與 Firebase 行動端工具整合'

### 架構規範

- 測試階段 5 人內使用時，mobile 仍只呼叫既有 FastAPI API，不直接操作 Supabase database 或 Firebase Firestore。
- Supabase 第一階段只承接社群圖片與頭像 Storage；未設定 Supabase 環境變數時，`POST /api/community/uploads` 會維持原本本機 `backend/data/community_uploads` 儲存流程。
- Firebase 暫時只保留行動端 runtime config 介面，不載入 `firebase/*` SDK；等 Supabase Storage 實測穩定後，再正式安裝 Firebase SDK 並啟用 Crashlytics、FCM token 預留與 Remote Config。
- 測試期不使用 Firebase Phone Auth、Firestore 主資料庫或 Firebase Storage，避免與 Supabase 職責重疊。

### 環境變數

後端 Supabase Storage：

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_STORAGE_BUCKET=community-uploads
```

手機端 runtime config：

```env
EXPO_PUBLIC_MOBILE_REMOTE_API_URL=
EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=819200
```

### API 規範

`POST /api/community/uploads` endpoint 不變，body 新增可選 `purpose`：

```json
{
  "purpose": "post",
  "images": [
    {
      "filename": "shot.jpg",
      "mime_type": "image/jpeg",
      "data": "<base64>"
    }
  ]
}
```

- `purpose = "post"` 時，Supabase Storage path 為 `users/{user_id}/posts/{uuid}.jpg`。
- `purpose = "avatar"` 時，Supabase Storage path 為 `users/{user_id}/avatars/{uuid}.jpg`。
- 回傳格式維持：

```json
{
  "image_urls": ["https://.../storage/v1/object/public/community-uploads/users/1/posts/abc.jpg"]
}
```

### 免費額度控管

- mobile 發文照片最多 3 張，頭像 1 張。
- mobile 上傳前仍需壓縮：貼文最長邊 `1600px`、品質 `0.8`；頭像最長邊 `512px`、品質 `0.82`。
- mobile 會在讀取 base64 後檢查單張壓縮結果，預設需小於 `819200 bytes`，避免 Supabase Free 的 `1GB Storage` 與 `5GB egress` 太快用完。
- 後端仍保留既有單張 `15MB` 硬上限，作為最後防線。

### 驗證規範

- 未設定 Supabase 時，圖片上傳仍回傳 `/api/community/uploads/{filename}` 並可由 FastAPI 讀取。
- 設定 Supabase 時，圖片上傳回傳 Supabase public object URL，貼文列表與個人頁需可直接顯示。
- Firebase SDK 尚未安裝時，App 不可 import 或動態 import `firebase/app`、`firebase/messaging`、`firebase/remote-config`，避免 Expo Metro 顯示 `Unable to resolve module firebase/app`。
- `initializeMobileFirebaseTools()` 目前只回傳本機 runtime config；API base URL 優先順序仍是網址 `api` 參數、`EXPO_PUBLIC_MOBILE_API_URL`、自動推斷、session，runtime config 只在沒有前述來源時補值。

## 06/03: '新增 mobile 貼文內文單行收合'

### 介面規範

- mobile 貼文卡的內文預設只顯示一行，避免長文字在首頁動態與個人頁貼文列表佔用過多版面。
- 內文實際超過一行時，第一行尾端需顯示省略效果並在同一行提供「更多」操作。
- 使用者點擊「更多」後，該貼文卡顯示完整內文；展開只影響目前貼文卡，不改變其他貼文狀態。
- 單行或空白內文不顯示「更多」；空白內文不渲染內文區塊。

### 範例用法

```tsx
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
```

## 06/03: '新增 mobile 社群圖片上傳前壓縮'

### 介面規範

- mobile 社群圖片上傳前需先在裝置端壓縮，不使用付費雲端圖片服務。
- 發貼文照片與個人頭像都需走共用壓縮流程，壓縮成功後才讀取 base64 並呼叫 `POST /api/community/uploads`。
- 發貼文照片最多 3 張，壓縮後統一輸出 JPEG，最長邊上限為 `1600px`，品質為 `0.8`。
- 個人頭像壓縮後統一輸出 JPEG，最長邊上限為 `512px`，品質為 `0.82`。
- 若原圖短邊或長邊小於壓縮上限，不放大圖片，只重新輸出 JPEG 以控制檔案大小。
- 壓縮失敗或無法取得可上傳的本機照片時，不回退上傳原圖，需中止流程並顯示錯誤，避免大圖造成上傳緩慢或觸發 15MB 限制。
- 發文保存的 `image_transforms` 需使用壓縮後圖片的 `width`、`height` 與發文當下的 `frame_width`，確保貼文列表還原裁切位置一致。

### 範例用法

```tsx
const compressed = await compressPhotoForUpload(photo, 1600, 0.8);
const data = await FileSystem.readAsStringAsync(compressed.uri, {
  encoding: FileSystem.EncodingType.Base64,
});
await uploadCommunityImages(baseUrl, token, [{
  filename: compressed.uploadFilename,
  mime_type: compressed.uploadMimeType,
  data,
}]);
```

## 06/03: '修正 mobile 個人頁貼文滿版與照片預載'

### 介面規範

- 個人頁貼文需與首頁貼文一致，左右兩側圖片滿版貼齊手機畫面，不使用內縮貼文寬度。
- 個人頁的分頁 tab、分隔線與統計面板仍需保留在安全內距內，避免文字與控制項被手機容器裁切。
- 個人頁不可再由外層 `contentFrame` 提供左右 padding；需使用無左右 padding 的 profile frame，並讓 `profileScrollContent` 自己提供安全內距，避免滿版貼文被 ScrollView 可視區裁切。
- 個人頁九宮格 / 統計 sticky tab 固定在上方時，背景與分隔線需滿版覆蓋左右兩側，icon 內容仍保留安全內距，避免滑動時左右露出下方貼文。
- 取得我的貼文或首頁動態流後，mobile 端需對貼文 `image_urls` 使用 `Image.prefetch` 預載，並用記憶體 `Set` 去重，避免同一張貼文照片重複下載。
- 貼文作者頭像仍維持既有頭像預載邏輯；貼文圖片預載與頭像預載分開記錄，避免互相干擾。

## 06/03: '調整 mobile 首頁頂部與積分卡間距'

### 介面規範

- 首頁最上方需使用與「我的」頁一致的 `DualActionHeader` 結構：左側搜尋、中間 `CueVex`、右側鈴鐺或同步 loading。
- 首頁不可同時由外層 `contentFrame` 與 `FlatList.contentContainerStyle` 提供左右 padding，避免積分卡看起來像外面又包了一層卡片。
- 首頁需使用無左右 padding 的 `homeContentFrame`，再由 `homeFeedContent` 統一提供左右安全內距。

## 06/03: '調整 mobile 我的頁個人資訊排列'

### 介面規範

- 「我的」頁頂部標題需顯示目前使用者顯示名稱；若名稱過長，標題單行截斷，避免壓到左右操作按鈕。
- 個人資訊區頭像需放大顯示，頭像右側上方顯示玩家階級。
- `貼文數 / 追蹤者 / 追蹤中` 需放在頭像右側下方，同一欄位上下與頭像高度對齊。
- 個人頁不再於頭像旁重複顯示使用者名稱，避免與頂部標題重複。

## 06/03: '新增 mobile 貼文作者公開主頁與追蹤'

### 介面規範

- 使用者點擊貼文作者頭像、名稱或發文時間區域時，若該貼文有 `user_id`，需進入該作者公開個人主頁。
- 使用者點擊留言區的留言者頭像、名稱、階級或時間區域時，若留言有 `user_id`，需關閉留言 sheet 並進入該留言者公開個人主頁。
- 公開主頁載入期間仍需維持「正在查看別人主頁」狀態，不可因 `viewedProfile` 尚未回傳而回落顯示自己的主頁。
- 前端需使用 `viewedProfileUserId` 作為公開主頁模式的判斷來源；不可只依賴 `viewedProfile` 是否存在，避免 API 尚未回來時顯示自己的主頁。
- 自己的主頁左上角維持發文 `+`，主要操作按鈕為「編輯個人檔案」。
- 別人的主頁左上角顯示關閉按鈕，主要操作按鈕改為「追蹤」或「已追蹤」；點擊後呼叫追蹤/取消追蹤 API 並即時更新追蹤者數。
- 別人的貼文列表仍共用貼文卡、按讚與留言功能，但不可顯示刪除貼文選單。

### API 規範

公開個人主頁：

```http
GET /api/mobile/users/{target_user_id}/profile
Authorization: Bearer <token>
```

回傳 `MobileProfile`，並包含：

```json
{
  "is_following": false,
  "is_self": false
}
```

公開主頁貼文：

```http
GET /api/mobile/users/{target_user_id}/posts?limit=20&offset=0
Authorization: Bearer <token>
```

回傳該使用者公開貼文，`liked_by_me` 需以目前登入者為準。

## 06/03: '修正 mobile 作者主頁在首頁內開啟'

### 介面規範

- 使用者在首頁貼文或留言 sheet 點擊自己或別人的作者區域時，底部導覽需維持在「首頁」，不可切換到「我的」tab。
- 首頁需以 `homeProfileRoute` 作為公開主頁路由狀態；狀態存在時，首頁內容改渲染 `ProfilePage`，狀態清空時回到原本首頁動態流。
- 首頁內公開主頁左上角固定為關閉按鈕，點擊後只清空 `homeProfileRoute` 與公開主頁資料，不切換底部 tab。
- 首頁內查看自己時不顯示編輯個人檔案與設定入口，真正的編輯流程仍從底部「我的」頁進入。
- 留言 sheet 點擊作者時需先觸發作者主頁路由，再關閉 sheet，避免關閉動畫期間回落到「我的」頁。

### 前端狀態範例

```tsx
type HomeProfileRoute = {
  userId: number;
  previewName?: string;
  previewAvatarUrl?: string;
};

const [homeProfileRoute, setHomeProfileRoute] = useState<HomeProfileRoute | null>(null);
```

### 驗證規範

- 首頁點別人貼文作者後，`BottomNav.active` 仍為「首頁」。
- 首頁點自己的貼文作者後，也在首頁位置顯示自己的 profile 版型。
- 留言區點自己或別人的作者後，留言 sheet 關閉且首頁內顯示對應 profile。
- 關閉首頁內 profile 後回到首頁 feed，不切換到「我的」。

## 06/03: '修正 mobile 作者主頁載入中卡住'

### 介面規範

- 作者主頁路由需帶入 `previewName`、`previewAvatarUrl` 與 `previewLevel`，讓首頁內主頁在 API 尚未回來前立即顯示標題、頭像與階級。
- 點自己的貼文或留言作者時，首頁內主頁直接使用既有 `profile + myPosts` 快取資料，不等待公開主頁 API。
- 點別人的作者時，前端使用單一 `profile-page` API 載入 profile 與 posts，避免兩支 API 任一支慢回造成長時間載入。
- 公開主頁請求逾時為 8 秒；逾時後顯示錯誤訊息，不可永久停在 spinner。
- 快速連點不同作者或關閉主頁時，舊請求回應不可覆蓋目前畫面。

### API 規範

```http
GET /api/mobile/users/{target_user_id}/profile-page?limit=20&offset=0
Authorization: Bearer <token>
```

回傳格式：

```json
{
  "profile": {
    "is_following": false,
    "is_self": false
  },
  "posts": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

## 06/03: '修正 mobile 動態載入失敗重複觸發'

### 介面規範

- 首頁動態流 API 載入失敗時，不使用 `Alert.alert` 顯示錯誤，避免 `FlatList.onEndReached` 在內容不足時反覆觸發並造成畫面跳動。
- feed 失敗後需設定 `feedError`，並將 `hasMoreFollowing` 與 `hasMoreRecommended` 設為 `false`，停止自動載入更多。
- `HomePage` 在 `feedError` 存在時需停用 `onEndReached`，錯誤訊息顯示在列表 footer。
- 使用者可透過下拉刷新重新呼叫 `refreshHomeFeed`；刷新開始時需清空 `feedError`。

### 輸出格式

錯誤狀態顯示於首頁動態列表下方：

```tsx
<View style={styles.feedErrorBox}>
  <Text style={styles.feedErrorTitle}>動態載入失敗</Text>
  <Text style={styles.feedErrorText}>{feedError}</Text>
  <Text style={styles.feedErrorHint}>下拉重新整理</Text>
</View>
```

## 06/03: '統一 mobile iOS 內建字體'

### 介面規範

- 手機端所有 `Text` 與 `TextInput` 樣式需套用共用 `appTextFont`。
- iOS 原生環境使用 `System`，英文與數字走 iOS 系統 San Francisco，繁體中文由系統 fallback 到 PingFang TC。
- Web 預覽使用 `-apple-system, BlinkMacSystemFont, "PingFang TC", "Helvetica Neue", Arial, sans-serif`，讓桌面預覽盡量貼近 iOS 內建字體效果。
- 不引入外部字型檔，避免增加 Expo Go 載入成本與字型授權管理。

### 範例用法

```tsx
const iosSystemFontFamily = Platform.select({
  ios: 'System',
  web: '-apple-system, BlinkMacSystemFont, "PingFang TC", "Helvetica Neue", Arial, sans-serif',
});
const appTextFont = iosSystemFontFamily ? { fontFamily: iosSystemFontFamily } : {};

const styles = StyleSheet.create({
  pageTitle: { ...appTextFont, color: ink, fontSize: 18, fontWeight: '900' },
  input: { ...appTextFont, color: ink, fontSize: 14, fontWeight: '800' },
});
```

## 06/03: '新增 mobile 首頁追蹤與熱門動態流'

### 介面規範

- 首頁由單一 `FlatList` 控制滾動與分頁，不再由外層全域 `ScrollView` 包住。
- 首頁版面由上到下固定為：左側搜尋 icon、中間 `CueVex`、右側鈴鐺 icon、淡色分隔線、積分卡、貼文動態流。
- 首頁只保留積分卡，不再顯示三格統計、最近對戰紀錄與本月表現卡。
- 動態流初始 `currentMode = 'FOLLOWING'`，先載入追蹤對象貼文；追蹤貼文滑完後，列表尾端插入 `{ type: 'caught_up_banner', id: 'caught-up-banner' }` 顯示「已看完最新動態」，再切換 `currentMode = 'RECOMMENDED'` 載入全站熱門貼文。
- 前端需維護 `seenPostIds`，所有貼文 append 前先做本地去重；熱門貼文請求需帶入已顯示貼文的 `exclude_ids`，避免追蹤流與熱門流重複。

### 後端 API

單向追蹤使用 `user_follows` 資料表，`follower_user_id` 追蹤 `following_user_id`，不可追蹤自己。

```http
POST /api/mobile/follows/{target_user_id}
DELETE /api/mobile/follows/{target_user_id}
Authorization: Bearer <token>
```

`GET /api/mobile/profile` 的 `followers_count` 與 `following_count` 需回傳 `user_follows` 真實統計。

追蹤中貼文：

```http
GET /api/mobile/feed/following?limit=10&offset=0
Authorization: Bearer <token>
```

- 僅回傳登入使用者追蹤對象在過去 7 天發布的貼文。
- 排序公式：`feed_score = likes + comments * 2`。
- 排序順序：`feed_score DESC, created_at DESC, id DESC`。
- 回傳格式：

```json
{
  "posts": [],
  "total": 0,
  "limit": 10,
  "offset": 0,
  "hasMoreFollowing": false
}
```

全站熱門貼文：

```http
GET /api/mobile/feed/trending?limit=10&offset=0&exclude_ids=1,2,3
Authorization: Bearer <token>
```

- 回傳全站過去 3 天公開貼文；目前專案尚無私密帳號欄位，因此 community posts 視為公開。
- 排序公式：`feed_score = likes + comments * 2`。
- `exclude_ids` 為逗號分隔貼文 id，後端不可回傳這些貼文。
- 回傳格式：

```json
{
  "posts": [],
  "total": 0,
  "limit": 10,
  "offset": 0,
  "hasMoreTrending": false
}
```

## 06/03: '加速貼文與留言頭像載入'

### 介面規範

- 個人頁、貼文作者與留言者頭像需使用共用頭像顯示邏輯；圖片載入失敗或沒有頭像時，需立即顯示預設使用者圖示。
- 取得 profile、貼文列表或留言列表後，mobile 端需使用 `Image.prefetch` 預載頭像 URL，並用記憶體 `Set` 去重，避免同一張頭像重複下載。
- 自己的留言若缺少 `author_avatar_url`，仍需 fallback 使用目前個人檔案頭像。
- `/api/community/uploads/{filename}` 上傳檔案因檔名包含 UUID，可使用長效快取標頭，讓貼文與留言頭像再次出現時更快顯示。

## 06/02: '新增 mobile 貼文互動與作者頭像'

### 介面規範

- 發貼文後，貼文列表需顯示作者頭像；若後端沒有 `author_avatar_url`，使用目前個人檔案頭像作為 fallback。
- 貼文作者名稱下方只顯示發文時間，不顯示「玩家」或玩家等級。
- 按讚數與留言數需可點擊；按讚呼叫 `POST /api/community/posts/{post_id}/like`，留言按鈕展開貼文下方輸入列。
- 點貼文照片兩下時，若該貼文尚未按讚，需自動按讚；若已按讚，不因雙擊取消讚。
- 點貼文照片兩下時需提供短暫震動與中央心形縮放回饋。
- 點留言需由下往上開啟留言 sheet，佔螢幕約 2/3；留言輸入列固定在 sheet 最下方，鍵盤開啟時需由 `KeyboardAvoidingView` 推上，避免被鍵盤遮住。
- 即使貼文已按過讚，雙擊照片仍需提供震動與愛心回饋，但不再呼叫按讚 API，因此按讚數不變。
- 留言 sheet 標題「留言」需置於中上方，內容區不顯示原貼文描述，只顯示留言列表。
- 留言列格式為：左側顯示留言者頭像；若留言者是目前登入者且留言資料沒有頭像，需 fallback 使用目前個人檔案頭像。
- 留言列右側上方顯示名稱、段位與相對留言時間（例如 `Lucian039 新手玩家 I 1 小時前`），讓使用者可依段位判斷留言可信度；下方顯示留言內容。
- 留言列最右側顯示可點擊的留言愛心與按讚數，愛心圖示需使用固定高度槽與左側頭像垂直中心對齊。
- 留言 sheet 頂部需保留狀態列安全距離，避免手機時間、電量區遮擋。
- 留言 sheet 結構固定為：`SafeAreaView` 導覽列、flex 留言列表滾動區、底部輸入區。
- 留言輸入區需包含快捷 emoji 欄與文字輸入列；鍵盤開啟時使用鍵盤高度監聽動態調整 sheet 底部位置，讓整塊輸入區底端貼齊鍵盤頂端，不留下可見空隙。
- 鍵盤未開啟時，留言輸入區底部需填滿 iOS home indicator 安全區，手機最下方不可露出灰色背景。
- 鍵盤開啟時，留言 sheet 下方因鍵盤避讓產生的區域也需使用白色填滿，不可露出遮罩灰色。
- 留言 sheet 開啟時預設高度為螢幕 2/3；標題區往上滑或鍵盤彈出時切換為螢幕 90% 高度。
- 90% 高度時標題區往下滑會先回到 2/3；點擊留言卡片外部遮罩時，不論目前高度皆直接關閉留言 sheet。
- 留言列表區與打字區需拆成不同層：留言列表 sheet 不因鍵盤彈出而位移；打字區獨立浮動並跟隨鍵盤高度，emoji 快捷列在鍵盤開啟後仍可點擊。
- 留言 sheet 不顯示右上角 X，關閉由外部遮罩與標題區下滑手勢處理。

## 06/02: '調整撰寫貼文照片預覽編輯'

### 介面規範

- 撰寫貼文點照片後需進入獨立照片編輯頁；編輯頁可拖曳與縮放裁切照片，並顯示九宮格線。
- 編輯頁底部/右上操作文案使用「完成」；按下後回到撰寫貼文頁。
- 撰寫貼文照片預覽框需與貼文列表圖片同樣使用滿版寬度與 `4/5` 比例。
- 撰寫預覽與照片編輯頁需使用黑色裁切框，方便使用者辨識裁切範圍；貼文列表發出後改用白色留白，維持版面美感。
- 撰寫預覽、照片編輯頁與貼文列表需使用相同 width-fit 圖片尺寸與 transform：圖片寬度固定填滿貼文框，左右不可露出留白。
- 橫向或較扁的長方形照片若高度小於 `4/5` 貼文框，允許上下保留留白，且垂直置中顯示；編輯時留白為黑色，貼文列表留白為白色。
- 直向或高度大於貼文框的照片可上下拖曳裁切；照片拖曳或縮放後若露出非法黑邊，手放開需用 spring 自動彈回合法位置。
- 發文時需將每張照片的裁切 `x/y/scale`、原始寬高與編輯時的 `frame_width` 一起保存到貼文，貼文列表渲染時依目前貼文框寬等比例還原座標，再套用相同 width-fit 尺寸與 clamp 後 transform，確保貼文顯示與編輯預覽一致。
- 貼文列表若遇到舊貼文或 transform metadata 缺少原始寬高，需用實際圖片尺寸回補比例後再渲染，避免 fallback 成 `4/5` 圖片而吃掉上下黑邊。
- 撰寫貼文底部送出按鈕文案使用「完成」。

## 06/02: '調整我的子流程底部導覽列'

### 介面規範

- 使用者停留在登入後主頁面層級時，底部導覽列依原本規則顯示。
- 使用者進入「我的」頁的相簿選圖、發文、選頭像或編輯個人檔案等子流程時，不顯示底部導覽列，避免操作區被底部導覽干擾。
- 離開子流程回到主頁面層級後，底部導覽列恢復顯示。

## 06/02: '調整相簿選擇入口'

### 介面規範

- 相簿選擇清單最上方固定顯示「所有照片」，使用不指定相簿的照片查詢結果，方便使用者回到完整照片列表。
- 「所有照片」與單一相簿載入照片時需使用 `MediaLibrary.getAssetsAsync` 分頁讀取；初次只載入第一批照片，使用者滑到接近底部時預載下一頁，避免開啟相簿時因照片數量過多而卡住。

## 06/01: '新增個人主頁相簿發文流程'

「我的」頁改為扁平版面，統計順序為 `貼文數 / 追蹤者 / 追蹤中`，個人資料與貼文列表不再使用卡片外框。左上角 `+` 會進入相簿選圖流程，使用 Expo 官方 `expo-media-library` 讀取近期照片與 Albums，使用 `expo-file-system` 讀取 base64 後呼叫 `POST /api/community/uploads` 上傳，再呼叫 `POST /api/community/posts` 完成分享。

貼文圖片最多 3 張；在貼文列表中圖片吃滿左右寬度，無圖片時不顯示圖片列。
單張照片上傳限制為 15MB。若手機照片超過限制，後端會回傳 `IMAGE_TOO_LARGE`，前端應顯示「單張照片需小於 15MB」。

iOS 相簿可能回傳 `ph://` asset URI，手機端會先透過 `MediaLibrary.getAssetInfoAsync(..., { shouldDownloadFromNetwork: true })` 轉為可供 React Native 顯示與上傳的本機 URI；若該照片仍無法取得本機檔案，會略過該照片，避免 `No suitable URL request handler found for ph://...`。

## 06/01: '新增 mobile 我的個人主頁'

「我的」頁改為個人主頁，不使用 mock data。頁面會呼叫 `GET /api/mobile/profile` 取得名稱、玩家等級、追蹤者、追蹤中與貼文數，並呼叫 `GET /api/community/posts?tab=following&sort=latest&limit=10&offset=0` 取得目前登入使用者最近貼文。

第一版尚無追蹤資料表，因此追蹤者與追蹤中顯示後端正式回傳的 `0`。貼文圖片欄位目前後端尚未提供，mobile 型別與 UI 已支援 `image_urls`，但資料為空時不顯示圖片列。

## 06/01: '關閉 Expo Go 手機掃碼開發警告覆蓋層'

手機使用 Expo Go 掃描啟動 QR 時，React Native 開發模式可能顯示 `Log 1 of 1` 警告覆蓋層，造成使用者誤以為 App 沒有進入 CueVex 介面。手機端已在入口關閉 LogBox 開發警告顯示；若仍看到舊警告，請關閉 Expo Go 內的舊 CueVex 專案後重新掃描 `start_mobile_remote.bat` 最新輸出的 QR。

## 06/01: '修正 Expo Go 原生環境自動後端位址讀取'

手機 Expo Go 原生環境沒有瀏覽器的 `window.location.search`。後端位址自動帶入邏輯只會在 Web 預覽存在 `window.location` 時讀取網址參數；手機原生環境改用啟動腳本注入的 `EXPO_PUBLIC_MOBILE_API_URL`，避免掃描 QR 後出現 `Render error cannot read property search of undefined`。

## 06/01: '調整 mobile 登入頁後端位址自動帶入'

登入頁保留桌面端帳號與密碼輸入，但不再提供可手動輸入的後端位址欄位，避免使用者誤填 Expo URL、舊 tunnel URL 或 LAN 位址。

App 會依序使用下列來源決定 API base URL：

1. Web 本機預覽網址上的 `?api=http://127.0.0.1:8001`。
2. 啟動腳本注入的 `EXPO_PUBLIC_MOBILE_API_URL`。
3. Web 本機預覽自動推斷的 `http://目前主機:8001`。
4. 已登入 session 中保存的後端位址。

登入頁只需要輸入桌面端既有帳號與密碼。若要切換後端位址，請改用啟動腳本或網址參數，不在登入頁手動輸入。

## 06/01: '調整掃碼頁我的 QR Code 顯示'

### 介面規範

- 掃碼頁預設顯示「掃描好友 QR Code」與置中的掃碼框。
- 使用者按下「產生我的 QR Code」並成功取得 `qr_payload` 後，頁面不再顯示掃碼框或相機預覽。
- 掃碼頁內容需置於畫面可視區中央，不使用外層卡片；相機預覽、掃碼框與「我的 QR Code」共用固定高度顯示區，避免按鈕位置因切換內容而跳動。
- 「我的 QR Code」會置中顯示，QR Code 尺寸為 `226x226`，與原本掃碼框一致。
- 顯示「我的 QR Code」時，原本按鈕改為「恢復掃碼框」，點擊後回到掃描好友 QR Code 畫面。
- 使用者切換到其他底部導覽頁再回到掃碼頁時，頁面需恢復預設掃碼框與「產生我的 QR Code」按鈕，不保留上一個 QR Code 畫面。
- QR Code 下方顯示有效時間提示：`10 分鐘內有效`。

### 輸出格式

`POST /api/friends/invite-qr` 回傳的 `qr_payload` 直接交給 `react-native-qrcode-svg` 產生 QR Code：

```tsx
<QRCode value={invite.qr_payload} size={226} />
```

## 06/01: '新增 Expo mobile 登入同步、好友 QR 與遠端 base URL'

### 目的

`mobile/` 是 CueVex 的 Expo 手機端 companion app。手機端不建立獨立帳號資料庫，而是連到桌面端 FastAPI 後端，使用桌面端已註冊帳號登入並同步資料。

### Expo Go 版本

手機專案目前使用 Expo SDK 54，需搭配最新版 Expo Go。若手機顯示 `Project is incompatible with this version of Expo Go`，請先確認 `mobile/package.json` 的 `expo` 為 `~54.0.35`，再重新執行 `npm install` 與啟動批次檔。

### 介面與資料來源

手機端介面使用白底 iOS 風格卡片與底部導覽，但資料不使用 mock data。登入、首頁數據、對戰紀錄、好友列表、好友 QR 與建立對戰都呼叫桌面端 FastAPI 後端。

目前後端尚未提供進攻細項與球型表現統計 API，因此這些頁面會顯示「後端尚未提供此細項統計」，不顯示假資料。

手機畫面不再繪製假的時間、電量與訊號列；頂部由系統狀態列處理。

手機可以使用兩種連線方式：

- 同 Wi-Fi：`http://桌機IP:8001`
- 不同網路：`https://你的 Cloudflare Tunnel 網域`

### 啟動方式

同 Wi-Fi 開發測試：

```bash
cd mobile
npm install
npm run start
```

遠端跨網路使用：

```bat
start_mobile_remote.bat
```

遠端模式會用 Cloudflare Quick Tunnel 暴露後端 API 與 Expo Metro。Expo Go 請掃描批次檔印出的 `exps://...trycloudflare.com` QR；新版啟動流程會透過 `EXPO_PUBLIC_MOBILE_API_URL` 自動填入後端 API。遠端模式設定請參考 `docs/guides/MOBILE_REMOTE_ACCESS.md`。

### 登入同步規範

- 手機登入使用既有 `POST /api/auth/login`。
- 登入 token 與後端位址保存到 `expo-secure-store`。
- App 重開後會使用保存的 token 呼叫 `GET /api/mobile/dashboard` 與 `GET /api/friends`。
- 若掃描的好友 QR 內含 `baseUrl=https://...`，App 會使用該公開後端接受邀請，成功後保存該 base URL。

### 數據畫面

手機數據頁使用 `GET /api/mobile/dashboard`，資料來源是桌面端同一份 `backend/data/recordings.db`：

- `stats.total_games`
- `stats.total_wins`
- `stats.win_rate`
- `stats.total_practice_sessions`
- `recent_games`
- `recent_practice`

### QR 好友流程

1. A 使用者在手機 App 開啟「我的 QR」。
2. App 呼叫 `POST /api/friends/invite-qr` 取得 `qr_payload`。
3. 若後端設定 `MOBILE_PUBLIC_BASE_URL=https://...`，QR 會包含公開 base URL。
4. B 使用者開啟「掃描」，用 `expo-camera` 掃描 QR。
5. App 用 QR 內的 `baseUrl` 呼叫 `POST /api/friends/accept-qr`。
6. 後端建立雙向好友關係，兩邊 `GET /api/friends` 都可看到對方。

QR payload 範例：

```text
cuevex://friend-invite?token=<short-lived-token>&baseUrl=https%3A%2F%2Fyour-domain.example.com
```

QR 只包含短效好友邀請 token，不包含密碼或登入 token。

### 好友對戰

好友列表的「開局」會呼叫：

```http
POST /api/friends/{friend_user_id}/start-game
Authorization: Bearer <token>
```

後端會檢查雙方是否為好友，通過後以登入者作為 Player 1、好友作為 Player 2 建立九號球對戰。桌面端可用既有 `GET /api/game/state` 查看同一場比賽狀態。

### 限制

- 不同網路必須使用公開 HTTPS 網域。
- 手機端不直接播放回放影片。
- QR 好友邀請預設 10 分鐘有效。
- 對戰仍由同一台球桌後端管理，手機端只負責選好友與建立對戰。
