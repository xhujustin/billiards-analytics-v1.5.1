# CueVex Mobile React Prototype

## 06/04:'修正社群貼文與留言作者頭像回傳'

### 功能說明

手機端社群 feed、個人頁貼文與留言列表的作者頭像，必須由後端依每筆資料的 `user_id` 回傳 `author_avatar_url`。Supabase 讀取路徑不得把作者頭像固定為空字串，也不得由前端用目前登入者或貼文作者資料推測其他留言者頭像。

### 規範用法

- `community_posts` 回應每筆貼文需包含該貼文作者的 `author_avatar_url`。
- `community_comments` 回應每筆留言需包含該留言作者的 `author_avatar_url`。
- Supabase repository 需批次查詢 `mobile_profiles`，以 `user_id` 對應 `avatar_url` 後再組裝貼文與留言回應。
- 前端只可在確認是目前登入者自己的貼文或留言時使用目前使用者頭像作 fallback。

### 輸出格式範例

```json
{
  "id": 201,
  "post_id": 101,
  "user_id": 8,
  "author_name": "PlayerB",
  "author_avatar_url": "https://cdn.example.com/player-b.jpg",
  "author_player_level": "",
  "body": "好球",
  "created_at": "2026-06-04T00:01:00Z",
  "likes": 0,
  "liked_by_me": false
}
```

## 06/03:'新增個人頁貼文/數據固定切換列功能'

### 範例

在 `mobile/App.tsx` 的個人頁面中，使用者停留在「我的」頁或觀看其他人的個人頁時，往下滑貼文列表或數據內容後，「九宮格貼文 / 數據」切換列會固定在頁面內容頂端。

```tsx
<ScrollView stickyHeaderIndices={[2]}>
  <DualActionHeader title="我的" />
  <View style={styles.profileFlatSection} />
  <View style={styles.profileStickyTabs}>
    <View style={styles.profileModeTabs} />
    <View style={styles.profileContentDivider} />
  </View>
</ScrollView>
```

### 規範用法

- 個人頁的貼文/數據切換列必須作為該頁 ScrollView 的直接子層，並用 `stickyHeaderIndices` 指定固定索引。
- sticky 區塊需保留 `backgroundColor`、`zIndex` 與 `elevation`，避免貼文內容滑動時從固定列下方透出。
- 外層 App 不再包覆「我的」個人頁 ScrollView；個人頁由自身管理捲動與固定分頁列。

### 輸出格式

切換列維持兩個 icon 按鈕：`Grid3X3` 代表貼文九宮格，`BarChart3` 代表數據。使用者切換分頁後，固定列不改變高度，不推擠或覆蓋後續內容。

## 06/01: '新增 CueVex 手機版 React TypeScript 原型介面'

### 目的

`frontend/` 內新增一套手機寬度的 CueVex App 原型介面，使用 React + TypeScript、Tailwind CSS、lucide-react 與 Recharts。此版本全部使用 mock data，不串接後端 API，方便先確認產品資訊架構與視覺方向。

### 啟動方式

```bat
cd frontend
npm.cmd install
npm.cmd run dev
```

預設 Vite 服務位址為 `http://127.0.0.1:3000`。本次驗證另以 `http://127.0.0.1:3007` 啟動開發伺服器。

### 頁面與切換

底部導覽列包含：

- 首頁
- 數據
- 掃碼
- 好友
- 我的

目前未使用 React Router，頁面切換由 `frontend/src/MobilePrototypeApp.tsx` 的 local state 控制。為避免影響既有桌面端，手機原型只在網址帶 `?prototype=mobile` 時載入；一般 `/` 仍保留原桌面端 App。

- 總覽
- 對戰記錄
- 進攻數據
- 球型表現

其他數據選項保留在下拉選單中，後續可接續實作對應頁面。

### 查看手機原型

```text
http://127.0.0.1:3000/?prototype=mobile
```

### 元件結構

主要可重用元件位於 `frontend/src/components/`：

- `BottomNav`
- `PageHeader`
- `StatCard`
- `ProgressBar`
- `MatchRow`
- `FriendRow`
- `DonutChart`
- `DropdownSelector`

頁面位於 `frontend/src/pages/`，包含首頁、數據總覽、對戰記錄、掃碼、好友、我的、進攻數據與球型表現。

### 視覺規範

- 手機容器最大寬度約 `390px`。
- 背景使用 `#F8FAFC` 與白色卡片。
- 主色使用 `#4F46E5`。
- 文字色使用 `#111827`，次要文字使用 `#6B7280`。
- 卡片使用圓角、淡邊框與柔和陰影。
- 圖表由 Recharts 繪製，包含折線圖與圓環圖。

## 06/05:'新增手機端社群設定頁介面'

### 功能範圍

`mobile/App.tsx` 於個人頁右上角設定按鈕新增「社群設定」介面。此版本先建立設定入口與列表 UI，尚未串接後端設定 API。

### 顯示順序

由上往下固定為：

1. 帳號管理中心
2. 帳號隱私
3. 通知設定
4. 我的收藏
5. 社群顯示設定
6. 封鎖與安全
7. 登出

### 規範用法

- 點擊個人頁右上角 `Settings` icon 進入獨立的設定頁面。
- 設定頁最上方標題固定為 `設定`，置中位置與 `數據`、`好友` 等一般頁面標題一致。
- 設定頁左側返回鍵使用與設定列右側相同的 `ChevronRight` 圖示，旋轉為向左方向，位置需與主頁放大鏡、個人頁加號一致。
- 設定頁整頁使用白底，左右吃滿手機寬度；header 單獨保留 20px 內距以對齊其他頁面的操作鍵。
- 手機 App 的主背景容器需統一白色，包含 `shell`、`shellWeb`、`phone`、`phoneWeb`、一般內容 frame、首頁 frame、個人頁 frame，避免瀏覽器預覽上下露出灰底。
- 設定頁列表不使用卡片外框或色塊；僅在標題下方與登出上方保留不明顯的滿版分隔線，其餘設定列不畫分隔線。
- 使用者頭像容器需有 `1px` 淡色外框，避免白色頭像照片與白色背景融合；適用於個人頁頭像、編輯頭像、貼文頭像、留言頭像與好友頭像。

## 06/05:'調整帳號管理中心頁面'

### 功能範圍

`mobile/App.tsx` 將設定頁中的 `帳號管理中心` 入口導向帳號管理中心頁面。此版本先建立入口頁 UI，欄位按鈕後續可串接帳號管理 API。

### 顯示順序

由上往下固定為：

1. 頁面標題：帳號管理中心
2. 頭像與更換頭像
3. 姓名
4. 使用者名稱
5. 個人簡介
6. 分隔線
7. 帳號安全與登入
8. 帳號狀態

### 規範用法

- 頭像區保留原本更換頭像流程。
- 除頭像更換外，其餘項目皆以按鈕列呈現。
- `姓名`、`使用者名稱`、`個人簡介` 點擊後需進入獨立編輯頁，頁面標題顯示被點擊的欄位名稱。
- 欄位編輯頁左側需有返回鍵，右側需有 `完成`；打字區放在上方，輸入框右側需有 `X` 清除目前所有文字。
- `使用者名稱` 為登入時的使用者名稱，並顯示於用戶主頁原本名稱標題位置；格式限制為英文小寫、數字、`_`、`.`。
- `姓名` 顯示於用戶等級左側，不限制字元。
- `使用者名稱` 更新會寫入 Supabase `mobile_users`；`姓名` 與 `個人簡介` 會寫入 Supabase `mobile_profiles`。
- 社群貼文與留言顯示作者時，需用 `user_id` 讀取最新 `mobile_users.username`，不可只使用 `community_posts.author_name` 或 `community_comments.author_name` 的舊快照值。
- 更新 `使用者名稱` 時需同步更新 `community_posts.author_name` 與 `community_comments.author_name`，確保舊 bundle 或舊資料路徑仍能顯示新名稱。
- `帳號安全與登入` 與 `帳號狀態` 右側需顯示 `ChevronRight`。
- 版面需與設定頁一致，左右吃滿，不使用卡片外框。
- `帳號管理中心` 目前連到既有個人資料編輯流程。
- 其他設定列先顯示待串接提示，後續可接社群設定 API。
- `登出` 必須維持在設定頁最下方，與其他設定群組分隔。

### 輸出格式

設定列使用 `SettingsRow`，支援：

```ts
{
  icon: React.ReactNode;
  label: string;
  description?: string;
  danger?: boolean;
  onPress?: () => void;
}
```

## 06/05:'新增帳號安全與登入頁面'

### 功能範圍

`mobile/App.tsx` 於帳號管理中心新增 `帳號安全與登入` 子頁，並建立 `修改密碼` 與 `登入裝置管理` 兩個入口。修改密碼已串接 mobile auth API；登入裝置管理讀取 `/api/auth/me` 的登入紀錄後顯示。

### 顯示順序

帳號安全與登入頁由上往下固定為：

1. 頁面標題：帳號安全與登入
2. 修改密碼
3. 登入裝置管理

修改密碼頁由上往下固定為：

1. 頁面標題：修改密碼
2. 密碼
3. 新密碼
4. 確認新密碼
5. 忘記密碼?
6. 登出其他裝置勾選框
7. 更改密碼按鈕

登入裝置管理頁由上往下固定為：

1. 頁面標題：登入裝置管理
2. 帳號登入活動
3. 你目前在此裝置登入
4. 目前裝置卡片
5. 其他裝置登入活動
6. 其他裝置卡片

### 規範用法

- 所有子頁 header 必須沿用設定頁樣式：左側返回鍵、置中頁面標題、右側保留同寬空位。
- `修改密碼` 頁的三個密碼欄位皆使用密碼輸入模式。
- `忘記密碼?` 目前只保留入口提示，尚未串接重設密碼流程。
- 勾選 `登出其他裝置` 後送出更改密碼，前端需帶 `logout_other_devices: true`。
- 後端收到 `logout_other_devices: true` 時，需撤銷同一使用者除了本次 token 以外的其他 session。
- `登入裝置管理` 的目前裝置卡片右側顯示綠色 `此裝置`。
- 登入裝置卡片內容格式為：第一行手機型號，第二行 `城市, 台灣`，右側顯示狀態或粗略時間。
- 其他裝置時間需顯示粗略時間，例如 `三年前`、`2個月前`、`今天`，不顯示精確年月日時分。

### API 輸出格式

修改密碼送出格式：

```json
{
  "old_password": "current-password",
  "new_password": "new-password",
  "logout_other_devices": true
}
```

登入裝置紀錄格式：

```json
{
  "login_history": [
    {
      "created_at": "2026-06-05T12:00:00Z",
      "status": "success",
      "device": "手機型號"
    }
  ]
}
```

## 06/05:'新增帳號隱私私人帳號設定'

### 功能範圍

`mobile/App.tsx` 於設定頁的 `帳號隱私` 新增獨立頁面。頁面沿用設定子頁 header，標題下方保留不明顯分隔線，內容列顯示 `私人帳號`，右側使用開關切換狀態。

### 顯示順序

帳號隱私頁由上往下固定為：

1. 頁面標題：帳號隱私
2. 標題下方不明顯分隔線
3. 私人帳號
4. 右側開關

### 規範用法

- 開啟 `私人帳號` 後，自己的個人頁仍可顯示貼文與數據。
- 其他使用者進入該帳號主頁時，貼文與數據不顯示，頁面顯示 `此帳號為私人帳號`。
- 公開個人頁 API 在非本人查看私人帳號時需回傳 `post_count: 0`。
- 公開個人頁貼文 API 在非本人查看私人帳號時需回傳空陣列。
- 隱私狀態儲存在 mobile profile payload 的 `is_private`。
- 更新私人帳號狀態時，後端只能 PATCH `mobile_profiles.is_private`，不可用空白的 `display_name`、`bio`、`avatar_url` 覆蓋既有 profile 欄位。
- 同步 `mobile_profiles` 時，如果 `mobile_users` 的 profile 欄位為空，必須保留 Supabase `mobile_profiles` 既有非空欄位，避免官方帳號或既有個人資料被清空。

### Supabase 設定

Supabase 需要在 `mobile_profiles` 新增欄位：

```sql
ALTER TABLE mobile_profiles
ADD COLUMN IF NOT EXISTS is_private boolean NOT NULL DEFAULT false;
```

### API 輸出格式

更新私人帳號狀態：

```json
{
  "is_private": true
}
```

公開個人頁回傳：

```json
{
  "profile": {
    "is_private": true,
    "post_count": 0
  },
  "posts": [],
  "total": 0
}
```

## 06/05:'新增帳號狀態頁面'

### 功能範圍

`mobile/App.tsx` 於帳號管理中心的 `帳號狀態` 新增獨立頁面。列表頁只顯示帳號健康狀態、`停用帳號`、`刪除帳號`，不顯示操作說明；點進單一操作後才顯示說明文字，底部固定放操作按鈕。

### 顯示順序

帳號狀態頁由上往下固定為：

1. 頁面標題：帳號狀態
2. 標題下方不明顯分隔線
3. 帳號健康狀態，右側顯示狀態文字
4. 停用帳號
5. 刪除帳號

### 規範用法

- 頁面 header 沿用設定子頁樣式：左側返回鍵、置中標題、右側保留同寬空位。
- 版面需白底滿版，不使用外側卡片。
- `帳號健康狀態` 右側目前固定顯示 `良好`，使用綠色；後續串接狀態 API 後，可依健康狀態改用紅色或其他警示色。
- `停用帳號`、`刪除帳號` 在列表頁是滿版列按鈕，不顯示說明。
- 點進 `停用帳號` 或 `刪除帳號` 後，頁面標題改成該操作名稱，內文顯示對應說明。
- 操作說明頁底部固定放一個有卡片邊框的按鈕；停用使用一般文字色，刪除使用危險色。
- 按下底部操作按鈕後，畫面中央顯示密碼確認框，使用者輸入目前密碼後才能確認。

### API 與資料狀態

- `PATCH /api/auth/me/deactivate` body：

```json
{
  "password": "目前密碼"
}
```

- 密碼正確時，後端將 `mobile_users.is_deactivated` 設為 `true`、寫入 `deactivated_at`，並撤銷該帳號所有有效 session。
- 停用帳號重新登入且密碼正確時，後端自動將 `is_deactivated` 改回 `false`、清空 `deactivated_at`，達成「重新登入即可恢復」。
- 停用帳號對其他用戶公開主頁時，個人檔案數據與貼文數量回傳隱藏狀態，公開貼文列表回空。
- 首頁追蹤動態與推薦動態需過濾 `is_deactivated` 或 `is_private` 的作者貼文。
- `DELETE /api/auth/me` body：

```json
{
  "password": "目前密碼"
}
```

- 密碼正確時，後端會撤銷 session，並清理該帳號相關 Supabase 社群資料：貼文、留言、按讚、收藏、追蹤、profile、好友邀請與好友關係，最後刪除 `mobile_users`。

### Supabase SQL

Supabase 需要在 `mobile_users` 新增欄位：

```sql
alter table public.mobile_users
add column if not exists is_deactivated boolean not null default false;

alter table public.mobile_users
add column if not exists deactivated_at timestamptz;
```

## 06/05:'新增我的收藏頁面'

### 功能範圍

`mobile/App.tsx` 於社群設定的 `我的收藏` 新增獨立頁面。使用者點入後載入目前帳號收藏的社群貼文，列表由最新收藏往下排序。

### 顯示規範

- 頁面 header 沿用設定子頁樣式：左側返回鍵、置中標題 `我的收藏`。
- 收藏列表重用既有 `PostCard`，保持社群貼文互動一致。
- 若尚無收藏，顯示 `尚無收藏`。
- 在收藏頁取消收藏後，該貼文需立即從收藏列表移除。

### API 與資料狀態

- `GET /api/community/bookmarks?limit=20&offset=0` 回傳格式：

```json
{
  "posts": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

- Supabase 使用既有 `community_post_bookmarks` 表，依 `created_at desc, post_id desc` 排序。
- 不需要新增 Supabase 表；若既有 `community_post_bookmarks` 缺少 `created_at`，需補欄位：

```sql
alter table public.community_post_bookmarks
add column if not exists created_at timestamptz not null default now();
```

## 06/05:'通知設定串接 Supabase 與 Expo push token'

### 規範

- `設定 > 通知設定` 進入頁面時，手機端需呼叫 `GET /api/mobile/notifications/settings` 讀取目前使用者設定。
- 任一開關切換後，手機端需呼叫 `PATCH /api/mobile/notifications/settings` 儲存單一欄位變更。
- `推播通知` 為總開關；關閉後下方所有通知設定顯示灰色且不可點擊，但原本各項開關值仍需保留，重新開啟後恢復原設定。
- 手機端在非 Web 平台登入後使用 `expo-notifications` 取得 Expo push token，並呼叫 `POST /api/mobile/notifications/push-token` 寫入 Supabase。
- 若手機端無通知權限、Expo token 取得失敗或正在 Web 預覽，不得中斷登入與設定頁操作。

### API 範例

`GET /api/mobile/notifications/settings` 回傳：

```json
{
  "user_id": 9,
  "push_enabled": true,
  "post_likes_enabled": true,
  "post_comments_enabled": true,
  "comment_replies_enabled": true,
  "comment_likes_enabled": true,
  "new_followers_enabled": true,
  "mutual_follows_enabled": true,
  "account_security_enabled": true,
  "login_changes_enabled": true,
  "service_announcements_enabled": true,
  "show_preview_enabled": true,
  "type_only_enabled": false,
  "quiet_hours_enabled": false,
  "updated_at": "2026-06-05T00:00:00Z"
}
```

`PATCH /api/mobile/notifications/settings` body 範例：

```json
{
  "push_enabled": false
}
```

`POST /api/mobile/notifications/push-token` body 範例：

```json
{
  "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
  "device": "Expo Mobile",
  "platform": "ios"
}
```

### Supabase SQL

```sql
create table if not exists public.user_notification_settings (
  user_id bigint primary key references public.mobile_users(id) on delete cascade,
  push_enabled boolean not null default true,
  post_likes_enabled boolean not null default true,
  post_comments_enabled boolean not null default true,
  comment_replies_enabled boolean not null default true,
  comment_likes_enabled boolean not null default true,
  new_followers_enabled boolean not null default true,
  mutual_follows_enabled boolean not null default true,
  account_security_enabled boolean not null default true,
  login_changes_enabled boolean not null default true,
  service_announcements_enabled boolean not null default true,
  show_preview_enabled boolean not null default true,
  type_only_enabled boolean not null default false,
  quiet_hours_enabled boolean not null default false,
  updated_at timestamptz not null default now()
);

create or replace function public.set_user_notification_settings_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_user_notification_settings_updated_at on public.user_notification_settings;

create trigger trg_user_notification_settings_updated_at
before update on public.user_notification_settings
for each row
execute function public.set_user_notification_settings_updated_at();

create table if not exists public.user_push_tokens (
  id bigint generated by default as identity primary key,
  user_id bigint not null references public.mobile_users(id) on delete cascade,
  expo_push_token text not null,
  device text not null default '',
  platform text not null default '',
  is_active boolean not null default true,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(user_id, expo_push_token)
);

create index if not exists idx_user_push_tokens_user
on public.user_push_tokens(user_id);

create index if not exists idx_user_push_tokens_active
on public.user_push_tokens(is_active, last_seen_at desc);
```

## 06/05:'新增通知設定靜態頁面'

### 功能範圍

`mobile/App.tsx` 於社群設定的 `通知設定` 新增獨立頁面。此版本只做前端本機互動，不串接 API、不寫入 Supabase、不持久化通知偏好。

### 顯示順序

通知設定頁由上往下固定為：

1. 頁面標題：通知設定
2. 標題下方不明顯分隔線
3. 推播通知，右側開關，預設顯示開啟
4. 有人按讚我的貼文，右側開關
5. 有人留言我的貼文，右側開關
6. 有人回覆我的留言，右側開關
7. 有人按讚我的留言，右側開關
8. 有人追蹤我，右側開關
9. 互相關注，右側開關
10. 帳號安全提醒，右側開關
11. 密碼或登入狀態變更，右側開關
12. 服務公告，右側開關
13. 顯示通知預覽，右側開關
14. 只顯示通知類型，不顯示內容，右側開關
15. 靜音時段，右側開關

### 規範用法

- 頁面 header 沿用設定子頁樣式：左側返回鍵、置中標題、右側保留同寬空位。
- 版面需白底滿版，不使用外側卡片。
- 推播通知總開關關閉時，下方所有通知設定文字與開關需變灰且不可點擊。
- 推播通知總開關重新開啟時，下方設定需恢復關閉前的個別開關狀態。
- 此版本只保存於目前 App state，離開或重啟後不保證保留。
- 第一版不需要 Supabase；後續若要儲存通知偏好，再新增通知設定 API 與資料模型。
