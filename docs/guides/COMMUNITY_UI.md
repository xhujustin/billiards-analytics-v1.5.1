# Community UI Guide

## 05/14: '新增 CueVex 社群動態牆頁面'

### 範例

社群頁由頂部導覽進入：

```text
TopBar -> Community -> Dashboard currentPage=community -> CommunityPage
```

畫面採三欄式配置：

```text
左側社群選單 | 中央 Stories + Feed + Posts | 右側 Hot Topics / Popular Clubs / Recommended Events
```

### 導覽規範

- Home 對應既有 `stream` 頁面。
- Analysis 對應回放分析入口，進入 `replay` 的 `player-selection` 狀態。
- Community 對應 `community` 頁面，第一版不顯示既有 Sidebar。
- Training 對應 `practice` 頁面。
- Game 對應 `game` 頁面。
- History 對應 `replay` 的 `entry` 狀態。
- Settings 對應 `settings` 頁面。
- Manage Account 對應 `account` 頁面。
- Log out / Login 使用既有 `onAuthAction` 流程。

### 社群互動

- Add Story：登入後開啟發文 composer；未登入時導向登入流程。
- 貼文卡片：顯示作者、徽章、時間、標題、內容、預覽、按讚數與留言數。
- 留言：點擊貼文或留言按鈕可展開留言區，登入後可送出留言。
- 分享：產生 `#community-post-{id}` 錨點連結，優先寫入 clipboard。
- 熱門話題：切換至 Explore tab 並使用 Popular 排序。
- 推薦球會與本週挑戰：第一版只顯示狀態提示，Club/Event 詳細頁後續接入。

### 輸出格式

`CommunityPage` 使用 `CommunityPost` 型別渲染：

```ts
{
  id: number;
  author_name: string;
  title: string;
  body: string;
  preview_type: 'pool-table' | 'pool-table-alt' | 'pose-analysis' | 'stats';
  likes: number;
  comments: number;
  liked_by_me: boolean;
  bookmarked_by_me: boolean;
  created_at: string;
}
```

預覽畫面依 `preview_type` 對應球桌路線、薄球攻防、姿態分析與數據圖表四種 UI。
