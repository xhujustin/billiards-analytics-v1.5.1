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
