# Expo Mobile App Guide

## 06/18: '新增好友對戰 QR Code、好友代碼與現場好友開局'

### 功能規範

- 手機端「掃碼」底部導覽入口改為好友對戰用途，頁面標題顯示 `好友對戰`。
- 頁面保留「掃描好友 QR Code」與「顯示我的 QR Code」切換；我的 QR Code 需呼叫 `POST /api/friends/invite-qr` 產生短效 `friend-invite` QR，不再直接塞 `userId`。
- 掃描 `friend-invite` QR 時呼叫 `POST /api/friends/accept-qr`，成功後建立好友關係並補成雙向 follow，讓好友列表與好友開局檢查同步生效。
- 06/18: '新增 mobile 掃碼加入中浮層'：手機端掃到有效 QR 並開始呼叫加入或開局 API 後，需顯示不可被版面擠壓的懸浮畫面；friend-invite 顯示 `正在搜尋使用者`，friend-match 顯示 `正在加入好友對戰`，舊 userId QR fallback 顯示 `正在建立好友對戰`，API 成功或失敗後關閉。
- 06/19: '修正 mobile QR 頁面入口與載入狀態'：手機端 QR Code 區只保留掃描與顯示我的 QR Code，不顯示 `輸入好友代碼` 與 `現場好友`；掃到 `friend-invite` 時載入文案需是互加好友，掃到 `friend-match` 時載入文案需是加入本機好友對戰。加入本機好友對戰成功送出後，短暫顯示等待本機端更新玩家 2 的浮層後自動關閉，不顯示手動確認按鈕。
- 06/19: '修正 mobile QR 掃描視窗比例'：手機端掃描 QR Code 的相機視窗需維持 1:1 正方形，不得使用橫向或直向長方形比例。
- 06/20: '修正 mobile 個人設定返回與 QR 標題'：個人設定頁與帳號管理中心需顯示明確 `返回` 按鈕；QR Code 掃描區上方不得再顯示 `好友對戰` 頁面標題。
- 06/20: '微調 mobile 返回與 QR 置中'：個人設定返回按鈕需貼近左側操作區；QR Code 掃描頁移除頁面標題後，主要掃描內容需在可用頁面高度置中。
- 06/20: '掃描好友 QR 後開啟對方主頁'：手機端掃描 `friend-invite` QR Code 並接受成功後，需使用 API 回傳的 `friend.id` 直接導向對方公開主頁；若回傳缺少 user id，才退回顯示好友已加入提示。
- 06/20: '優化掃描好友 QR 後導頁速度'：接受 `friend-invite` 成功後需先切換到對方公開主頁，`refreshAll()` 與主頁內容載入需背景執行，不可等待完整 dashboard/feed 同步完成後才導頁。
- 06/20: '優化我的好友 QR 載入速度'：手機端進入掃碼頁時需背景預載自己的 `friend-invite` QR；同一個 API 位址與 session 下需快取 QR 到接近過期，不可在返回掃描或再次顯示時立即清空並重新等待後端。
- 06/20: '修正 mobile 貼文圖片上傳與追蹤名單返回'：新貼文圖片入口只需檢查相簿權限，不要求相機權限；未允許相簿時顯示 `尚未允許相簿權限`。貼文與頭像圖片上傳前端預設限制需對齊後端 15MB；PWA 壓縮後若產生 `data:` 或 `blob:` 圖片 URI，需先轉成 base64 再呼叫 `/api/community/uploads`。追蹤者與追蹤中名單頁需顯示明確 `返回` 按鈕。
- 06/21: '修正 iOS PWA 照片上傳'：PWA/Web 模式不得依賴 `expo-media-library` 列舉相簿或 `expo-image-manipulator` 處理本機相簿 URI；貼文與頭像改用瀏覽器原生 `input[type=file]` 選圖，前端以 Canvas 轉成 JPEG `data:` URI 後再取 base64 上傳。PWA 版本標記需同步更新，避免 iOS 主畫面 App 繼續載入舊 bundle。
- 06/22: '調整 mobile 新貼文撰寫流程'：點擊新增貼文需直接進入 `撰寫貼文`，不再先顯示 `新貼文` 內頁，也不可自動跳出照片選擇器；照片需由撰寫頁內的 `加入/選擇照片` 操作觸發。撰寫頁的 `完成` 送出鍵需移到右上角，文字輸入區需位於照片預覽上方。
- 06/22: '修正 mobile 頭像與撰寫貼文選圖互相影響'：更換頭像不得清空撰寫貼文的 `selectedPhotos` 草稿；相簿切換只有在貼文選圖流程中才可重置貼文選取。撰寫貼文頁需以文字輸入、照片區標題、照片張數與更換照片操作組成，右上 `完成` 在沒有文字且沒有照片時需停用。
- 06/22: '修正 mobile 頭像完成未儲存'：選擇頭像頁按下 `完成` 必須直接執行頭像上傳與 `PATCH /api/mobile/profile`，不可只回到帳號管理中心預覽；移除頭像也需立即儲存空 `avatar_url`。若 `/api/community/uploads` 未回傳圖片 URL，前端需中止並顯示儲存失敗。
- 06/22: '移除 mobile 主頁編輯個人檔案入口'：自己的主頁不得顯示 `編輯個人檔案` 主操作按鈕；個人資料、頭像與帳號管理仍從右上設定齒輪進入 `帳號管理中心`。
- 06/22: '修正 PWA 註冊錯誤不可見'：註冊頁需顯示 inline 錯誤，不可只依賴 `Alert.alert`；送出前需在前端驗證帳號 3-32 碼、密碼至少 10 碼且含英文與數字、安全驗證答案不可空白。註冊 API 成功後若後續資料同步失敗，不得誤報成註冊失敗。
- 掃描好友 QR Code 需依 payload 類型分流；`friend-invite` 是好友互加，`friend-match` 是加入桌面端好友對戰，舊 userId QR fallback 才嘗試建立九號球好友對戰。
- 桌面端「建立好友對戰 > 掃描 QR Code」需先在 Supabase `friend_match_invites` 建立邀請資料；有 `MOBILE_PUBLIC_BASE_URL` 時用 `https://<api-base>/friend-match?token=<token>&baseUrl=<api-base>` 產生 QR Code，沒有後端公開位址時才 fallback `cuevex://friend-match?token=<token>`。
- 若 Supabase 已設定但 `friend_match_invites` REST 或資料表暫時不可用，桌面端需先 fallback 建立本機邀請並顯示 QR Code，回傳 `storage_backend: "sqlite_fallback"` 與 `storage_warning`，避免玩家只看到「無法產生」。
- Supabase 成功建立或接受邀請後，後端需同步鏡像到 SQLite fallback；若後續掃描或輪詢遇到 `WinError 10054` 這類 REST 連線重置，仍可用同一個 token 從本機 fallback 讀取或接受邀請。
- Supabase 尚未建立資料表時，先到 Supabase SQL Editor 執行 `scripts/supabase_friend_match_invites.sql`；未建立前 Supabase REST 會回 `PGRST205`。執行時需啟用 Row Level Security，這張表只由後端 service role 存取，不開放 anon/auth client 直接查詢或寫入。
- 手機端掃描 `cuevex://friend-match?token=<token>` 後呼叫 accept API，成功時資料庫邀請狀態改為 `accepted`，桌面端輪詢後自動把玩家 2 更新為手機登入帳號。
- 桌面端 QR 面板需提供取消按鈕；輸入好友代碼面板需提供「確認加入」與「取消」，且不得覆蓋玩家 2 的等待狀態文字。
- 掃描自己的 QR Code 需擋下並提示不可和自己建立好友對戰。
- `輸入好友代碼` 支援輸入好友 `id`、`@username` 或 `username`，成功後建立好友對戰。
- 帳號好友對戰仍需雙方互相關注；未互相關注時回傳 `FRIEND_REQUIRED`。
- `現場好友` 可直接把玩家 2 設為已加入；已加入卡片內需顯示「取消」按鈕，讓使用者回到等待好友加入狀態。

### API 規範

以好友代碼建立對戰：

```http
POST /api/friends/start-game-by-code
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "player_b"
}
```

成功時回傳桌面端 `start_nine_ball` 結果；若好友不存在回 `USER_NOT_FOUND`，若不是互關好友回 `FRIEND_REQUIRED`。

產生互掃加好友 QR：

```http
POST /api/friends/invite-qr
Authorization: Bearer <token>
Content-Type: application/json

{
  "base_url": "https://apppwaapi.lessleap.com"
}
```

成功時回傳：

```json
{
  "token": "short-lived-token",
  "qr_payload": "https://apppwaapi.lessleap.com/friend-invite?token=short-lived-token&baseUrl=https%3A%2F%2Fapppwaapi.lessleap.com",
  "expires_at": 1781780000000
}
```

接受互掃加好友 QR：

```http
POST /api/friends/accept-qr
Authorization: Bearer <token>
Content-Type: application/json

{
  "payload": "https://apppwaapi.lessleap.com/friend-invite?token=short-lived-token&baseUrl=https%3A%2F%2Fapppwaapi.lessleap.com"
}
```

成功後雙方會成為好友並建立雙向 follow，`GET /api/friends` 應立即回傳對方。

以現場好友建立對戰：

```http
POST /api/friends/start-local-game
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "現場玩家B"
}
```

`name` 長度需為 2 到 32 字元，且不可與目前登入者 username 相同。成功時只建立本機對戰，不寫入好友關係。

建立桌面好友對戰 QR 邀請：

```http
POST /api/friend-match/invites
Content-Type: application/json

{
  "host_player": "PlayerA",
  "game_type": "nine_ball",
  "target_rounds": 5,
  "shot_time_limit": 30
}
```

成功輸出：

```json
{
  "token": "invite-token",
  "qr_payload": "cuevex://friend-match?token=invite-token",
  "host_player": "PlayerA",
  "game_type": "nine_ball",
  "target_rounds": 5,
  "shot_time_limit": 30,
  "status": "pending",
  "guest_user_id": null,
  "guest_player": null,
  "expires_at": 1781780000,
  "storage_backend": "supabase"
}
```

若 Supabase 寫入失敗但本機 fallback 成功，輸出仍需包含 `qr_payload`，並加上：

```json
{
  "storage_backend": "sqlite_fallback",
  "storage_warning": "friend_match_invites table is unavailable"
}
```

手機掃描後接受桌面邀請：

```http
POST /api/friend-match/invites/{token}/accept
Authorization: Bearer <token>
```

接受成功後 `status` 變為 `accepted`，`guest_user_id` 與 `guest_player` 需寫入目前登入手機帳號。桌面端用：

```http
GET /api/friend-match/invites/{token}
```

輪詢狀態；若回傳 `accepted` 且有 `guest_player`，桌面端更新玩家 2 並允許開始對戰。邀請有效期限為 10 分鐘，逾期回 `FRIEND_MATCH_INVITE_EXPIRED` 或查詢狀態 `expired`。

### 驗證

```powershell
cd mobile
npm.cmd run typecheck

C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m py_compile backend\api\mobile_api.py
C:\Users\xhuju\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\test-program\test_mobile_friends.py
```

## 06/15: '新增手機端 AI 教練聊天室導覽'

### 功能規範

- 手機端底部導覽第四個入口由「好友」改為「AI教練聊天室」；底部按鈕顯示兩行 `AI教練 / 聊天室`，避免長文字撐高導覽列或破壞 safe-area 修正。
- `MainTab` 使用完整值 `AI教練聊天室`，頁面標題顯示 `AI 教練聊天室`，避免和原好友頁功能混淆。
- 聊天室需保留底部導覽 overlay 模型，使用獨立 `coachChatContentFrame` 與 `bottomNavOverlayContentInsetStyle`，不可回到 flex footer 或額外 safe-area padding。
- 聊天室送出訊息時優先呼叫 `POST /api/coach/chat/stream`，payload 需帶 `message`、最近對話 `conversation_history`、`locale: zh-TW`、`coach_session_id`，並附上 mobile dashboard stats / analytics 作為 context。
- 後端不可用或 AI Coach 暫停時，聊天室以教練訊息泡泡顯示錯誤或 paused 回覆，不跳出破壞流程的全螢幕錯誤。

## 06/15: '修正 AI 教練聊天室操作區與串流回覆'

### 功能規範

- 手機端底部導覽列只顯示 icon，不顯示文字 label；每個 `Pressable` 仍需保留 `accessibilityLabel` 對應 tab 名稱。
- AI 教練聊天室需使用 `/api/coach/chat/stream` SSE 串流端點；送出後立即建立教練回覆泡泡，收到 `delta` 時更新同一個泡泡，不可等整段完成才顯示。
- 若平台不支援 `response.body.getReader()`，可 fallback 到 `/api/coach/chat` 非串流回覆。
- 快捷問題列必須放在輸入框上方的 `coachBottomDock`，避免快捷問題與輸入框之間出現大面積空白。
- 串流中若尚未收到文字，回覆泡泡顯示 `串流回覆中` 與 loading，不額外新增第二個 loading 泡泡。

## 06/15: '修正 icon-only 底部導覽被 safe-area 裁切'

### 顯示規範

- icon-only 底部導覽不可只用 `bottom: calc(-1 * env(safe-area-inset-bottom))` 下拉 72px 內容列；這會把 icon 一起推進 iPhone home indicator 區域並被裁切。
- Web/PWA 的 `bottomNavWebPullDownStyle` 需同時設定 `height: calc(72px + env(safe-area-inset-bottom))`，讓外層背景延伸到 safe-area，但內層 `bottomNavItems` 仍固定 72px 並停在可視區。

## 06/15: '修正 AI 教練輸入框與 icon-only 導覽位置'

### 顯示規範

- AI 教練聊天室不可沿用一般列表頁的 `bottomNavOverlayContentInsetStyle`；聊天輸入框是固定在頁面底部的操作區，Web/PWA 需使用 `coachChatContentInsetStyle` 預留 88px，避免輸入框被底部導覽列蓋住。
- icon-only 底部導覽可用 `bottom: calc(-1 * env(safe-area-inset-bottom) - 12px)` 微幅下移；若再下移必須實機確認 icon 不會進入 home indicator 區域被裁切。

## 06/15: 'AI 教練輸入時隱藏底部導覽'

### 互動規範

- AI 教練聊天室的輸入框 focus 時需回報 App 層 `aiCoachInputFocused=true`，此時 `shouldShowBottomNav` 必須隱藏底部導覽列，讓 iOS PWA 鍵盤可以完整覆蓋底部區域，不和導航列圖層互卡。
- 輸入框 blur 或離開 AI 教練聊天室時需回復 `aiCoachInputFocused=false`，底部導覽列才恢復顯示。
- 鍵盤模式下聊天室底部 padding 使用 `coachChatKeyboardInsetStyle`，不可保留一般狀態的 88px 導覽列預留高度。

## 06/14: '修正首頁動態錯誤訊息溢出版面'

### 顯示規範

- 首頁動態 footer 不可直接顯示完整 API URL、query string 或 `Load failed` 原始錯誤，避免長字串撐出版面。
- `HomePage` 需透過 `formatHomeFeedError()` 將 `feedError` 轉成短文案；連線失敗顯示「目前無法連線到後端，請下拉重新整理；若仍失敗，請重新掃最新 remote QR。」。
- 完整錯誤仍需保留在 `console.warn`，供開發者確認實際失敗 endpoint 與底層錯誤原因。
- `feedError` 存在時仍停用 `onEndReached`，使用者只能透過下拉重新整理重新嘗試。

### 底部導覽規範

- 首頁底部導覽列不可使用過大的固定白框；`bottomNav` 高度需控制在 `78`，確保圖示與文字完整顯示，同時避免圖示文字下方留下大面積白色 padding。
- 首頁列表 `homeContentFrame` 與 `homeFeedContent` 的底部 padding 需與導覽列高度同步，保留可讀安全距離但不可額外堆疊大面積空白。
- Web/PWA 的 `phoneWeb` 不可使用會被內容撐開的 `minHeight` / `flexGrow` 版面；必須固定 `height: '100%'`、`maxHeight: '100%'`、`minHeight: 0` 與 `overflow: 'hidden'`。
- Web/PWA 的 `phoneWeb` 不可保留桌面預覽用邊框，尤其不可有 `borderBottomWidth`；實機 PWA 會把這條線畫在 bottom nav 與 iPhone home indicator safe-area 之間，看起來像底部白邊。
- Web/PWA 與 native 的 `BottomNav` 必須統一使用 overlay 模型：外層 `bottomNav` 固定 `position: absolute`、`bottom: 0`，不可再讓 web 另走 flex sibling footer，避免不同頁面把導覽列擠到內容下方。
- Web/PWA 的 `bottomNav` 外層不可再加 `paddingBottom: env(safe-area-inset-bottom)`；實機會把 tab row 整體往上推，形成過大的白色 home indicator 區塊。導覽列改由內層 `bottomNavItems` 固定 `72` 高度與 `12` 底部 padding 控制可點擊區。
- iOS PWA 的 React root 底部可能停在 safe-area 上緣；Web/PWA 的 `bottomNav` 需套用 `bottomNavWebPullDownStyle`，用 `bottom: calc(-1 * env(safe-area-inset-bottom))` 將導覽列下拉到 home indicator 區域。
- 會在底部導覽下方延伸的 `FlatList` / `ScrollView` content container 必須套用 `bottomNavOverlayContentInsetStyle`，Web/PWA 使用 `calc(88px - env(safe-area-inset-bottom))` 預留可讀距離；因 `bottomNavWebPullDownStyle` 已把導覽列下拉到 safe-area，內容 padding 不可再把 safe-area 加回去，否則導覽列上方會多出空白。
- Profile 頁不可在外層 `profileContentFrame` 保留 Web/PWA 底部 padding；Web/PWA 必須讓 `profileContentFrame.paddingBottom` 為 `0`，並把 `bottomNavOverlayContentInsetStyle` 套在 `ProfilePage` 內部 `ScrollView.contentContainerStyle`，避免貼文列表和底部導覽之間出現父層空白。
- iOS PWA 使用 `apple-mobile-web-app-status-bar-style=black-translucent` 時，內容會畫到狀態列下方；Web/PWA 的 `phoneWeb` 必須套用 `phoneWebTopSafeAreaStyle`，用 `paddingTop: max(0px, calc(env(safe-area-inset-top) - 8px))` 避開狀態列並保留緊湊頂部距離，避免首頁搜尋 icon 或 Profile header 和時間重疊。
- Web/PWA 的 `getPostMediaWidth()` 不可固定回傳 `430`；必須使用 `Math.min(Dimensions.get('window').width, 430)`，讓資料頁 overview 卡片、貼文圖片與實機 CSS viewport 對齊，避免 iPhone 393px viewport 時右側邊框被裁切。
- `showSplash` loading 階段必須視為全螢幕狀態；`shouldShowBottomNav` 需包含 `!showSplash`，避免已登入使用者重新開啟 PWA 時 splash logo 底下仍顯示底部導覽列。
- PWA export 後的 `index.html` 必須保留 `viewport-fit=cover`，`html`、`body`、`#root` 需使用同一 App 背景色與 `100dvh`，避免 iOS standalone 底部 safe-area 露出白邊。
- `#root` 不可只用 `min-height: 100dvh`；必須有明確 `height: 100dvh`，否則 React Native Web 的 `height: '100%'` 會退回內容高度，造成登入頁按鈕或底部導覽消失。
- `scripts/patch-pwa-html.cjs` 需注入 `body::after`，用 `env(safe-area-inset-bottom)` 補齊 iPhone home indicator 區域背景；補色層只能放在 `z-index: 0`，`#root` 需在 `z-index: 1`，避免白色補色層覆蓋 bottom nav。

## 06/20: '新增 mobile 數據歷史詳情與進攻/球型頁'

### 功能規範

- 手機端「數據 > 歷史紀錄」需同時顯示練習與對戰資料，分頁為 `全部`、`練習`、`對戰`。
- 歷史紀錄列表每列可點擊，練習詳情需顯示類型、日期、時長與紀錄 ID；對戰詳情需顯示對手、結果、比分、時間與紀錄 ID。
- 手機端「數據 > 總覽」順序調整為：累積狀態卡片、練習統計、對戰統計、本週摘要、折線圖。
- 本週摘要單位需和折線圖一致：時間用 `小時`、擊球數用 `顆`；練習趨勢第三欄顯示 `進球數 / 顆`，進球準度第三欄顯示 `進球率 / %`。
- `進球準度` 必須使用折線圖呈現；尚無資料時顯示 `暫無資料`，不可留空白圖表。
- 「進攻數據」需顯示本週擊球、本週進球、進球率、準度分數、出桿穩定與力道控制；若資料不足，需顯示明確空狀態。
- 「球型表現」需顯示能力雷達圖與母球控制、走位能力、出桿穩定拆解；若資料不足，需顯示明確空狀態。
- 06/20: '修正 PWA static server 缺 index 崩潰'：`mobile/scripts/serve-pwa.cjs` 在啟動時若找不到 `mobile/dist/index.html`，需印出明確錯誤並退出；若 request 期間 `dist/index.html` 被刪除或重建中，需回 `503` 與操作提示，不可讓 `ReadStream` 的 `ENOENT` 變成未處理例外。
- 正確啟動 PWA static server 前需先執行 `npm.cmd run export:pwa`，或直接使用 `npm.cmd run web:pwa` 讓流程先 export 再 serve。

### 輸出格式

歷史詳情練習範例：

```json
{
  "type": "practice",
  "practice_type": "準度訓練",
  "date": "2026/06/20",
  "duration": "1 分鐘",
  "game_id": "practice-001"
}
```

歷史詳情對戰範例：

```json
{
  "type": "match",
  "opponent": "現場好友",
  "result": "勝利",
  "score": "5-4",
  "date": "2026/6/16 上午6:57:16",
  "game_id": "match-001"
}
```

## 06/11: '修正 Expo CLI fetch failed 啟動失敗'

### 問題症狀

- 直接在 `mobile` 目錄執行 `npm.cmd run web -- --port 19009 --clear` 時，Metro 啟動後出現 `TypeError: fetch failed`，手機端 Expo Go 或 web preview 無法繼續開啟。
- Debug log 顯示 Expo CLI 在啟動階段嘗試更新 development session 與抓取 bundled native modules；當本機網路或連外請求被限制時，dependency validation 會讓 CLI 直接退出。

### 啟動規範

- `mobile/package.json` 的 `start`、`android`、`ios`、`web` scripts 預設加入 `--offline`，讓直接執行 npm scripts 時與 `mobile.bat`、`start_mobile_remote.bat` 的離線啟動行為一致。
- 本機預覽建議使用：

```powershell
cd C:\Users\User\Documents\billiards-analytics-v1.5.1\mobile
$env:EXPO_PUBLIC_MOBILE_API_URL="http://127.0.0.1:8001"
npm.cmd run web -- --port 19006 --clear
```

- 手機 Expo Go 建議使用專案根目錄的 `mobile.bat`，它會建立 Cloudflare tunnel、產生新的 `exps://...trycloudflare.com` QR，並檢查 Metro `/status`。每次重啟都必須掃新的 QR，不可重用舊 tunnel URL。

### 驗證方式

- `npm.cmd run typecheck` 必須通過。
- 無 `--offline` 啟動會在 `Fetching bundled native modules from the server...` 後失敗；加入 `--offline` 後應顯示 `Waiting on http://localhost:<port>` 與 `Skipping dependency validation in offline mode`，代表 Metro dev server 已持續運行。

## 06/08: '調整 mobile 數據總覽為累積狀態與練習趨勢'

### 功能規範

- 設定頁登出列下方提供 `test` 按鈕；點擊後切換到本機測試帳號並載入測試 dashboard，直接前往「數據 > 總覽」展示折線圖。測試帳號的設定頁同一位置需顯示「切換回原帳號」，點擊後還原進入測試帳號前的本機狀態。
- `test` 按鈕使用前端本機狀態，不寫入後端資料庫，也不代表真實帳號能力。
- 測試 dashboard 依電腦端目前可記錄或可同步的欄位生成展示資料：練習時間、擊球數、進球數、進球率；測試帳號加入日為 `2025-11-25`，累積資料到目前日期。
- 測試 dashboard 的折線圖顯示近三個月週資料；圖表內每週需有垂直線，點擊某週垂直區域後，上方摘要改顯示該週區間，例如 `3月30日 - 4月5日`；預設選中最後一週並顯示 `本週`。
- 折線圖選中值需顯示在圖表上方同一水平線，並帶單位；`練習趨勢` 使用 `顆`，`進球準度` 使用 `%`。
- 上方摘要第三欄需與目前圖表選中的 Y 軸數據一致；`練習趨勢` 顯示同一週 `進球數`，`進球準度` 顯示同一週 `進球率`。
- 折線圖右上角不得顯示 `時間 / 進球率` 類軸標籤；Y 軸刻度需帶單位。
- X 軸只顯示月份，例如近三個月顯示 `4月`、`5月`、`6月`；月份需由圖表點位區間推導，第二條垂直線位置顯示第一個月份，倒數第二條垂直線位置顯示第三個月份。
- 手機端「數據 > 總覽」改為三段式：單張橫向滑動累積狀態卡片、本週摘要、可切換折線圖，最下方保留 AI Coach 建議。
- 數據分類入口取代原本頁首「數據」標題位置，左側顯示目前分類，右側顯示往下箭頭；下方使用首頁同樣淡分隔線，點擊後往下展開左右滿版、無圓角的選單區，選項文字靠左；點擊或滑動其他地方需收起選單；選項中的「對戰記錄」命名為「歷史紀錄」。
- 最上方卡片需一次只顯示一張，可左右滑動，並在下方用圓點顯示目前位置，依序顯示：
  - 加入日期與已加入天數。
  - 總練習次數與對戰次數。
  - 整體能力分數與段位。
- 總覽區塊之間不使用分隔線，靠間距維持閱讀節奏。
- 本週摘要移除卡片外框，從左到右顯示 `時間（小時）`、`擊球數（顆）`、`進球率（%）`；數值與單位需左右排列並靠左對齊。
- `擊球數`、`進球率` 目前尚未有可靠電腦端擊球事件同步時，數值必須顯示 `--`，不可使用假資料，也不可顯示同步提示文字。
- 折線圖上方提供獨立的 `練習趨勢` 與 `進球準度` 切換按鈕；圖表需使用滿版寬度，X 軸與 Y 軸各只顯示三個刻度。
- 若折線圖 `points` 為空，需保留圖表框架並顯示 `暫無資料`，不可畫假折線。
- 遊玩/對戰模式不納入能力分數、練習趨勢或進球準度趨勢；對戰數只作為累積狀態展示。

### API 規範

`GET /api/mobile/dashboard` 的 `analytics_v1` 新增總覽專用欄位：

```json
{
  "analytics_v1": {
    "overview": {
      "joined_at": "2026-06-01T12:00:00",
      "joined_days": 7,
      "total_practice_sessions": 18,
      "total_battle_matches": 5,
      "overall_score": 62,
      "level_label": "新手進階中",
      "score_basis": "根據練習模式紀錄推估，不包含對戰勝負"
    },
    "weekly_summary": {
      "practice_hours": 2.5,
      "shot_count": null,
      "pot_count": null,
      "pot_rate": null,
      "shot_data_status": "pending_desktop_sync"
    },
    "chart_series": {
      "practice_trend": {
        "title": "練習趨勢",
        "x_label": "時間",
        "y_label": "總進球數",
        "status": "pending_desktop_sync",
        "points": []
      },
      "accuracy_trend": {
        "title": "進球準度",
        "x_label": "時間",
        "y_label": "進球率",
        "status": "pending_desktop_sync",
        "points": []
      }
    }
  }
}
```

### 資料來源規則

- `joined_at` 使用目前登入使用者的 `created_at`。
- `joined_days` 由後端依 Asia/Taipei 日期計算，最少為 `1`。
- `total_practice_sessions` 只統計 `practice_single`、`practice_pattern`、`practice_accuracy`。
- `total_battle_matches` 只統計 `nine_ball`，且不影響能力分數。
- `practice_hours` 只加總本週練習模式 `duration_seconds`。
- `shot_count`、`pot_count`、`pot_rate` 在沒有可靠擊球事件前固定回 `null`。
- `chart_series.*.points` 在電腦端未同步擊球事件前固定回空陣列。

## 06/06: '新增 mobile V1 數據能力總覽'

### 功能規範

- 手機端「數據 > 總覽」改為新手可讀的教練看板，優先回答「我目前強不強」、「哪裡最弱」、「本週該練什麼」。
- 頁面需顯示整體能力分數、能力雷達圖、AI Coach 白話解讀、五大能力條、目前最大弱點與本週推薦訓練。
- V1 分數是根據桌面端 `recordings` 的對戰、練習次數與最近練習紀錄做保守推估，不代表單球級精密量測。
- 若尚未累積足夠紀錄，仍需顯示完整看板與低資料可信度提示，不可顯示空白或 `NaN`。
- 「進攻數據」與「球型表現」在 V1 保留入口，但文字需提示「需要更多擊球紀錄後開放」。

### API 規範

`GET /api/mobile/dashboard` 保留既有 `user`、`stats`、`recent_games`、`recent_practice`，並新增 `analytics_v1`：

```json
{
  "analytics_v1": {
    "overall_score": 62,
    "level_label": "新手進階中",
    "score_confidence": "low",
    "score_basis": "根據目前對戰、練習次數與最近練習紀錄推估",
    "ability_scores": [
      { "key": "accuracy", "label": "準度", "score": 68 },
      { "key": "cue_control", "label": "母球控制", "score": 48 },
      { "key": "power_control", "label": "力道控制", "score": 54 },
      { "key": "stroke_stability", "label": "出桿穩定", "score": 56 },
      { "key": "position_play", "label": "走位能力", "score": 50 }
    ],
    "coach_summary": "你的準度目前最穩，但母球控制還需要加強。建議本週先練「定點停球訓練」，讓進球後的下一步更穩。",
    "strongest_ability": "準度",
    "weakest_ability": "母球控制",
    "recommended_trainings": [
      { "title": "定點停球訓練", "reason": "改善母球停位穩定度", "duration_minutes": 10 },
      { "title": "短距離母球控制", "reason": "讓母球停在指定區域內", "duration_minutes": 10 }
    ],
    "recent_trend": {
      "label": "最近已有練習紀錄",
      "summary": "建議維持每週 2 到 3 次短練習，先讓母球控制與力道更穩。"
    }
  }
}
```

### 五大能力定義

- `準度`：由勝率、總場次與最近練習量推估，代表目前把球打進的穩定度。
- `母球控制`：由球型練習與最近練習量推估，代表進球後母球停位是否穩定。
- `力道控制`：由練習持續性、單球練習與近期練習量推估，代表出力是否容易過大或不足。
- `出桿穩定`：由總練習量、近期練習量與對戰經驗推估，代表出桿方向與節奏是否穩定。
- `走位能力`：由球型練習、對戰經驗與勝場推估，代表是否能考慮下一球位置。

### 後續限制

- V1 尚未使用單球角度誤差、力道誤差、母球落點誤差或實際球路資料。
- V2/V3 需補單球擊球事件與擊球詳細分析資料後，才能把 `score_confidence` 提升並支援進攻數據、球型表現與單球詳細分析。

## 06/05: '新增手機端封鎖與安全功能'

### 功能規範

- 手機端「我的 > 設定 > 封鎖與安全」需顯示目前使用者封鎖名單，支援解除封鎖。
- 他人個人頁提供「封鎖使用者」入口；封鎖後需移除雙方追蹤關係，不刪除既有貼文、留言、按讚或收藏資料。
- 封鎖方查看被封鎖方個人頁時，只顯示上方使用者名稱與姓名，貼文數、追蹤者、追蹤中顯示空白，不顯示簡介；貼文/數據區顯示「你已封鎖該用戶」與「解除封鎖」按鈕。
- 被封鎖方查看封鎖方個人頁時，同樣只顯示上方使用者名稱與姓名，貼文數、追蹤者、追蹤中顯示空白，不顯示簡介；貼文/數據區顯示「找不到用戶」。
- following/trending feed、公開個人頁貼文、收藏列表與社群貼文互動需套用雙向封鎖過濾。

### API 規範

- `GET /api/mobile/blocks` 回傳：
  ```json
  {
    "blocked_users": [
      {
        "user": { "id": 2, "username": "player_b" },
        "display_name": "Player B",
        "avatar_url": "https://...",
        "blocked_at": "2026-06-05T00:00:00Z"
      }
    ],
    "total": 1
  }
  ```
- `POST /api/mobile/blocks/{target_user_id}` 會建立封鎖關係並回傳 `{ "is_blocked": true }`；封鎖自己需回 `400 INVALID_BLOCK`。
- `DELETE /api/mobile/blocks/{target_user_id}` 會解除封鎖並回傳 `{ "is_blocked": false }`。
- `GET /api/mobile/users/{target_user_id}/profile` 與 `profile-page` 需新增：
  ```json
  {
    "block_state": "none",
    "is_blocked_by_me": false,
    "has_blocked_me": false
  }
  ```
  `block_state` 只允許 `none`、`blocked_by_me`、`blocked_me`。

### Supabase SQL

```sql
create table if not exists public.user_blocks (
  blocker_user_id bigint not null,
  blocked_user_id bigint not null,
  created_at timestamptz not null default now(),
  primary key (blocker_user_id, blocked_user_id),
  check (blocker_user_id <> blocked_user_id)
);

create index if not exists idx_user_blocks_blocked
on public.user_blocks(blocked_user_id);
```

### 驗證規範

- 封鎖同一使用者兩次需維持冪等，不新增重複資料。
- 封鎖後雙方追蹤關係需被移除，且任一方不可再追蹤對方或開始好友對戰。
- 封鎖方與被封鎖方互看個人頁時，需分別顯示「你已封鎖該用戶」與「找不到用戶」。
- 解除封鎖後重新進入個人頁，公開個人資料與貼文需恢復依原本隱私設定顯示。

## 06/05: '調整帳號管理中心返回導覽'

### 介面規範

- 手機端「設定」進入「帳號管理中心」後，左上角需使用返回箭頭，不使用叉叉關閉圖示。
- 「帳號管理中心」右上角不可顯示「完成」按鈕；帳號欄位仍透過各欄位編輯頁完成儲存。
- Header 右側保留等寬空位，避免移除「完成」後造成標題視覺偏移。

### 驗證規範

- 從「我的」頁進入「設定」再點「帳號管理中心」，左上角返回需回到個人頁。
- 帳號管理中心右上角不可再出現「完成」文字或載入指示。

## 06/04: '修正我的頁貼文錯誤不覆蓋主頁'

### 介面規範

- 「我的」頁個人資料成功載入後，即使貼文 API 回 `HTTP 500`，也不可把 `profileError` 設為貼文錯誤。
- 貼文載入失敗時暫時清空 `myPosts`，讓貼文分頁顯示空狀態；個人資料、追蹤統計、段位與設定入口仍需可見。
- `ProfilePage` 的 `error` 只代表 profile 主資料不可用，不用於貼文列表錯誤。

### 驗證規範

- `/api/diagnostics/mobile-profile/{user_id}` 回 `mobile_profile_payload.ok:true` 時，「我的」頁不可只顯示 HTTP 500。
- 修改後需重新執行 `mobile.bat`，讓 Expo Go 取得新版 bundle。

## 06/04: '新增我的頁 Supabase profile 診斷與 post_count 修正'

### 架構規範

- `GET /api/mobile/profile` 的 `post_count` 改為 Supabase `community_posts` 優先計算，Supabase 不可用時才 fallback SQLite。
- 公開個人頁與自己的個人頁計算 `post_count` 時需沿用目前 viewer user id，避免 liked/bookmarked 欄位用錯觀看者。
- Cloud Run 新增 `GET /api/diagnostics/mobile-profile/{user_id}`，用於不經手機 UI 直接檢查：
  - `mobile_users`
  - `mobile_profiles`
  - `user_follows`
  - `community_posts`
- 此診斷端點不可輸出 Supabase secret，只回傳每段是否可讀與簡短錯誤。

### 驗證規範

- `/api/diagnostics/cloud-mobile` 顯示 `supabase_rest.ok: true` 後，若「我的」頁仍 500，改用 `/api/diagnostics/mobile-profile/{user_id}` 定位 profile 或 posts。
- `test_mobile_friends.py -k "profile or feed"` 需通過。

## 06/04: '修正我的頁貼文改用 Supabase 優先 API'

### 架構規範

- 手機端「我的」頁載入自己的貼文時，優先使用 `GET /api/mobile/users/{user_id}/posts?limit=20&offset=0`。
- 不再以 `/api/community/posts?tab=following...` 作為「我的」頁主要貼文來源，避免 Cloud Run mobile-lite 環境落回本機 SQLite 查詢造成 500 或資料不同步。
- 若登入 session 暫時沒有 user id，才 fallback 舊的 `getMyCommunityPosts`。
- 「我的」頁個人資料與貼文維持分開載入；貼文失敗時不可阻斷個人資料顯示。

### 驗證規範

- 登入後點「我的」，貼文 API 應走 `/api/mobile/users/{自己的 id}/posts`。
- Supabase `community_posts` 有該使用者貼文時，換電腦或 Cloud Run 重啟後仍可顯示。
- 修改 mobile bundle 後需重新執行 `mobile.bat` 並重新掃 QR。

## 06/04: '修正我的頁面 HTTP 500 降級顯示'

### 架構規範

- 手機端「我的」頁載入時，個人資料 `GET /api/mobile/profile` 與貼文列表 `GET /api/community/posts?...` 必須分開請求與分開錯誤處理。
- 個人資料成功但貼文 API 失敗時，仍需顯示個人主頁基本資料，貼文區清空並顯示錯誤訊息，不可讓整個「我的」頁跑不出來。
- `backend/api/mobile_api.py` 與 `backend/api/community_api.py` 驗證 token 時若 Supabase account store 發生 REST 錯誤，需回傳 JSON detail：
  - `code: ACCOUNT_STORE_ERROR`
  - `message: Supabase ... HTTP ...`
- 若仍看到 `HTTP 500`，優先檢查手機端顯示的 `message`，再對照 Cloud Run logs。

### 驗證規範

- `/api/mobile/profile` 正常、貼文列表失敗時，「我的」頁仍需顯示名稱、頭像、段位與統計。
- Supabase session 查詢失敗時，API 不應回空白 500，需回傳 `ACCOUNT_STORE_ERROR` JSON。
- 修改後需通過 mobile typecheck 與 `test_mobile_friends.py` profile/feed/auth 測試。

## 06/04: '修正登入 HTTP 500 顯示 Supabase 帳號儲存錯誤'

### 架構規範

- `POST /api/auth/login` 與 `POST /api/auth/register` 若 Supabase account store 發生 REST 錯誤，需回傳 JSON detail，不可只讓手機端看到 `HTTP 500 Internal Server Error`。
- 錯誤格式使用 `ACCOUNT_STORE_ERROR`，`message` 保留 Supabase request 的 HTTP status 與簡短內容，用於判斷：
  - Secret Manager 內 service role key 是否錯誤。
  - `SUPABASE_URL` 是否指到正確專案。
  - `mobile_users`、`mobile_auth_sessions`、`mobile_login_history` 等帳號資料表是否存在。
- 重新部署時不可使用文件中的 `https://你的-project.supabase.co` 或 `sb_secret_你的_service_role_key` 範例值；必須使用實際 Supabase 專案設定。

### 重新部署範例

```powershell
cd C:\Users\User\Documents\billiards-analytics-v1.5.1

$vars = @{}
Get-Content .\mobile-remote.env | ForEach-Object {
  if ($_ -match '^\s*([^#=]+)=(.*)$') { $vars[$matches[1].Trim()] = $matches[2].Trim() }
}
$env:SUPABASE_URL = $vars["SUPABASE_URL"]
$env:SUPABASE_SERVICE_ROLE_KEY = $vars["SUPABASE_SERVICE_ROLE_KEY"]

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_cloudrun_mobile.ps1 `
  -ProjectId "cuevex-mobile" `
  -Region "asia-east1" `
  -ServiceName "cuevex-mobile-api"
```

### API 錯誤格式

```json
{
  "detail": {
    "code": "ACCOUNT_STORE_ERROR",
    "message": "Supabase account request failed with HTTP 401: ..."
  }
}
```

### 驗證規範

- 部署後 `/api/diagnostics/cloud-mobile` 應顯示 `account_store_backend: supabase` 與 `supabase_configured: true`。
- 登入錯誤若仍為 500，手機端應顯示 `ACCOUNT_STORE_ERROR` 與 Supabase HTTP 錯誤內容。
- 若訊息包含 `HTTP 401` 或 `Invalid API key`，重新設定 Secret Manager 中的 service role key 並重新部署。

## 06/04: '修正 mobile.bat Expo Go QR 改用 exps'

### 架構規範

- `mobile.bat` 仍會同時列出 `Expo exp:` 與 `Expo exps:`，但終端 QR 改為直接使用 `exps://...trycloudflare.com`。
- iOS Expo Go 若顯示 `There was a problem running the requested app`，優先重新執行 `mobile.bat` 並掃最後輸出的新版 QR。
- Cloudflare Quick Tunnel 每次啟動都可能換網址，舊 QR、舊 `exp://` 或舊 `exps://` 都不可沿用。
- 若目前 tunnel 在電腦端也無法開啟 `/status`，代表 tunnel 已失效，需重新執行 `mobile.bat` 建立新的 tunnel。

### 驗證規範

- `mobile.bat` 最後輸出的 QR 應對應 `Expo exps:` 這一行。
- 重新掃 QR 前，需先在 Expo Go 關閉舊的 CueVex 專案 session。

## 06/04: '修正 request failed 錯誤訊息與 Supabase REST 驗證 header'

### 架構規範

- 手機端 `mobile/src/api.ts` 讀取錯誤回應時，需先讀 raw text，再嘗試解析 JSON，避免非 JSON 錯誤只顯示 `Request failed`。
- 錯誤訊息需包含 HTTP status，例如 `HTTP 500: Internal Server Error` 或 `HTTP 401: Invalid API key`，方便定位 Cloud Run、Supabase 或 API endpoint 問題。
- 後端所有 Supabase server-side request header 需同時帶：
  - `apikey: <SUPABASE_SERVICE_ROLE_KEY>`
  - `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`
- `SUPABASE_SERVICE_ROLE_KEY` 仍只允許存在 Cloud Run Secret Manager 或本機 env，不可傳到手機端。

### 範例錯誤輸出

```text
HTTP 500: Internal Server Error
HTTP 401: Invalid API key
```

### 驗證規範

- Supabase REST 端點不應因缺少 `Authorization` header 回 401。
- 後端回非 JSON 錯誤時，手機端不可再只顯示 `Request failed`。
- 若仍出現 HTTP 500，需依手機端顯示的 status/body 對照 Cloud Run logs。

## 06/04: '修正手機端首頁動態載入失敗降級'

### 架構規範

- `GET /api/mobile/feed/trending` 改為 Supabase 優先讀取；Supabase 不可用、未設定或回傳空資料時才 fallback SQLite。
- Supabase 熱門動態會讀取 `community_posts`，並補齊 `community_post_reactions`、`community_comments`、`community_post_bookmarks` 的互動欄位。
- 手機端首頁刷新時若 following feed 載入失敗，會先改載 trending feed 並顯示「已看完最新動態」，避免單一路徑異常直接讓首頁只顯示「動態載入失敗」。
- 只有 following 與 trending 皆載入失敗時，首頁才顯示錯誤 footer，並停用 `onEndReached`；使用者仍可下拉重新整理。
- 分頁狀態的 `hasMoreFollowing`、`hasMoreTrending` 需轉為布林值，避免後端缺欄位或舊版回應造成重複載入。

### API 回傳格式

```json
{
  "posts": [
    {
      "id": 2001,
      "user_id": 7,
      "body": "supabase trending post",
      "likes": 4,
      "comments": 2,
      "liked_by_me": false,
      "bookmarked_by_me": false
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0,
  "hasMoreTrending": false
}
```

### 驗證規範

- Cloud Run 設定 Supabase env 後，首頁熱門動態應可讀取 Supabase `community_posts`。
- following feed 失敗但 trending feed 正常時，首頁不可顯示「動態載入失敗」。
- following 與 trending 都失敗時，錯誤仍顯示於首頁列表 footer，且下拉重新整理可重新嘗試。

## 06/04: '修正 Cloud Run Supabase secret 與手機登入錯誤提示'

### 架構規範

- Cloud Run 帳號主庫使用 Secret Manager 的 `cuevex-supabase-service-role-key` 注入 `SUPABASE_SERVICE_ROLE_KEY`。
- 若 Cloud Run logs 出現 `Supabase account request failed with HTTP 401` 與 `Invalid API key`，代表 Secret Manager 內的 Supabase key 不是目前有效的 service role key。
- Supabase 新版 service role key 應為 `sb_secret_...` 開頭；舊版 `eyJ...` JWT key 若已被輪替或停用，Cloud Run 登入會失敗。
- 更新 Secret Manager 後需讓 Cloud Run 建新 revision，確保服務重新讀取 `latest` secret。
- 手機端 `mobile/src/api.ts` 的連線錯誤訊息維持可讀中文，避免編碼損壞時只顯示不明亂碼。

### 修復指令

```powershell
$env:SUPABASE_SERVICE_ROLE_KEY="sb_secret_..."
gcloud secrets versions add cuevex-supabase-service-role-key `
  --project cuevex-mobile `
  --data-file=-

gcloud run services update cuevex-mobile-api `
  --project cuevex-mobile `
  --region asia-east1 `
  --update-secrets SUPABASE_SERVICE_ROLE_KEY=cuevex-supabase-service-role-key:latest
```

### 驗證規範

- Cloud Run 最新 revision 應正常通過 startup TCP probe。
- 手機端重新啟動 Expo 後，登入不應再出現 Supabase `Invalid API key`。
- 若仍登入失敗，先查 Cloud Run logs 的 `/api/auth/login` 狀態碼；`401` 多半是帳密錯，`500` 才是後端設定或服務端錯誤。

## 06/04: '改為 Supabase 帳號主庫預設啟動'

### 架構規範

- `mobile-remote.env.example` 的 `ACCOUNT_STORE_BACKEND` 預設改為 `supabase`。
- `start_mobile_remote.bat` 的帳號資料來源預設改為 Supabase，避免重建 env 或換電腦時回到 SQLite 帳號。
- 當 `ACCOUNT_STORE_BACKEND=supabase` 時，啟動腳本會檢查：
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- 若上述 Supabase env 缺少任一項，腳本會停止並提示錯誤，不會啟動半套帳號環境。
- `SUPABASE_SERVICE_ROLE_KEY` 只允許放在本機 env 或雲端 Secret Manager，不提交到 repo，不傳到手機端。

### 範例設定

```env
ACCOUNT_STORE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<local-only-service-role-key>
SUPABASE_STORAGE_BUCKET=community-uploads
```

### 驗證規範

- 執行 `start_mobile_remote.bat` 後，後端應以 Supabase account store 啟動。
- 登入成功後，Supabase `mobile_auth_sessions` 應新增 token hash。
- 新註冊帳號應寫入 Supabase `mobile_users`。
- 若暫時要回 SQLite 測試，需在 `mobile-remote.env` 明確設定 `ACCOUNT_STORE_BACKEND=sqlite`。

## 06/04: '重新製作 mobile 登入與歡迎頁'

### 介面規範

- App 啟動時先以白底顯示 `mobile/assets/cuevex-logo.png`，Logo 置中放大顯示，約 2.5 秒後淡出。
- 未登入時進入歡迎頁，版面順序為「歡迎使用」、置中 Logo、「使用現有帳號」、「註冊新帳號」。
- 歡迎頁與登入/註冊頁不使用卡片容器，維持白底與直接排版。
- 點「使用現有帳號」進入登入頁，左上顯示「登入CueVex」，欄位順序為「帳號名稱」、「密碼」。
- 登入頁不顯示後端自動連線位址；base URL 仍沿用啟動腳本、網址參數與既有 session 的自動解析邏輯。
- 登入與註冊表單使用 `KeyboardAvoidingView` 搭配可捲動內容，鍵盤彈起時可繼續查看與輸入帳密欄位。
- 點「註冊新帳號」進入註冊頁，呼叫既有 `POST /api/auth/register`，不新增後端 API。

### 範例流程

```text
啟動 App
-> 白底 Logo splash
-> 歡迎頁
-> 使用現有帳號
-> 登入CueVex
-> 輸入帳號名稱與密碼
-> 登入後進入手機端主頁
```

### 輸出格式

註冊仍使用既有 auth response：

```json
{
  "token": "session-token",
  "user": {
    "id": 1,
    "username": "Player001"
  }
}
```

## 06/04: '新增 Cloud Run mobile-lite API 部署'

### 架構規範

- 專案根目錄新增 `mobile.bat`，用於啟動 Expo mobile 開發環境並直接連 Cloud Run API。
- `mobile.bat` 不啟動本機 FastAPI、不建立 Cloudflare API tunnel；API 固定注入 `EXPO_PUBLIC_MOBILE_API_URL=https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app`。
- `mobile.bat` 只會替 Expo Metro `18181` 建立 Cloudflare Quick Tunnel，輸出 `exp://...trycloudflare.com` QR，並同時列出 `exps://...trycloudflare.com` 與 HTTPS tunnel URL，避免手機無法連到本機 LAN IP 時打不開專案。
- `mobile.bat` 會以 `REACT_NATIVE_PACKAGER_HOSTNAME` 與 `EXPO_PACKAGER_PROXY_URL` 啟動 Metro，確保 manifest/bundle URL 使用 Cloudflare 位址。
- `mobile.bat` 只顯示一個可掃描 QR；API 仍走 Cloud Run。
- 若需要 web preview，可在 Expo Metro 視窗按 `w` 開啟。
- `mobile.bat` 使用 offline 模式，避免 Expo CLI 線上 SDK 檢查拿到空回應時出現 `Unexpected end of JSON input`。
- `mobile.bat` 會將 `TEMP/TMP` 指到專案內 `runtime\metro-temp`，避免 Windows `%TEMP%\metro-cache` 被舊 Node/Metro 程序鎖住時出現 `EPERM, Permission denied`。
- 啟動前會停止 command line 指向本專案 `mobile` 目錄的舊 `node.exe`，並清理 `19006`、`18181` port，避免舊 web preview 或 Metro 殘留造成啟動失敗。
- 手機 Expo Go 掃 `mobile.bat` 最後輸出的 QR 即可測 Cloud Run API；若 iOS 顯示 `there was a problem running the requested app`，請在 Expo Go 內用 `Enter URL manually` 改輸入批次檔列出的 `Expo exps:` URL。
- Cloud Run 入口為 `backend/cloud_mobile_app.py`，只掛載 auth、community、mobile API。
- Cloud Run 入口不 import `backend/main.py`，避免載入 YOLO、相機、投影、MJPEG 與本機硬體流程。
- Cloud Run 專用 requirements 為 `backend/requirements-cloudrun.txt`。
- Cloud Run 容器使用 `backend/Dockerfile.cloudrun`，啟動命令為 `uvicorn cloud_mobile_app:app --host 0.0.0.0 --port $PORT`。
- 第一階段 Cloud Run 定位為 mobile-lite：帳號、Session、好友 QR、Supabase Storage 與已 Supabase 化的社群資料可用；球桌即時分析、錄影、投影與相機串流仍留本機。
- `SUPABASE_SERVICE_ROLE_KEY` 部署時應放 Secret Manager，不放手機端或前端。

### 部署指令

Cloud Run API 已部署後，本機只開 Expo 測試：

```bat
mobile.bat
```

Expo Go QR 為開發 QR，不是永久 QR；正式安裝版需使用 EAS iOS/Android build。

Cloud Run 部署：

```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="sb_secret_..."

.\scripts\deploy_cloudrun_mobile.ps1 `
  -ProjectId "your-gcp-project-id" `
  -Region "asia-east1" `
  -ServiceName "cuevex-mobile-api"
```

部署腳本會：

- 使用 `cloudbuild.mobile.yaml` 建置 `backend/Dockerfile.cloudrun`。
- 建立或更新 Secret Manager secret `cuevex-supabase-service-role-key`。
- 部署 Cloud Run 並設定 `ACCOUNT_STORE_BACKEND=supabase`。
- 設定 `min-instances=1`，讓手機端 API 維持常駐。

### 驗證規範

- Cloud Run URL 的 `/health` 回傳 `status: ok`。
- `/api/diagnostics/cloud-mobile` 顯示 `account_store_backend: supabase` 且 `supabase_configured: true`。
- 手機端設定 `EXPO_PUBLIC_MOBILE_API_URL` 指向 Cloud Run URL 後，可重新登入既有帳號。
- 登入後 Supabase `mobile_auth_sessions` 會新增資料。

## 06/04: '新增 Supabase 帳號資料主庫'

### 架構規範

- 後端新增 `ACCOUNT_STORE_BACKEND` 切換帳號資料來源。
- `ACCOUNT_STORE_BACKEND=sqlite` 或未設定時，維持既有本機 SQLite `backend/data/recordings.db` 帳號流程。
- `ACCOUNT_STORE_BACKEND=supabase` 時，`POST /api/auth/register`、`POST /api/auth/login`、Session 驗證、登入紀錄、好友列表與好友 QR token 會改用 Supabase。
- Supabase 帳號模式不 fallback SQLite，避免 Cloud Run 與本機資料分裂。
- 手機端 endpoint 與 request/response 格式不變，App 不直接讀寫 Supabase 帳號表。
- 舊本機 auth sessions 不匯入 Supabase；遷移後使用者需重新登入一次。

### Supabase SQL

```sql
create table if not exists public.mobile_users (
  id bigint generated by default as identity primary key,
  username text not null,
  username_key text not null unique,
  password_hash text not null,
  security_question text not null,
  security_answer_hash text not null,
  display_name text not null default '',
  bio text not null default '',
  avatar_url text not null default '',
  is_deactivated boolean not null default false,
  deactivated_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.mobile_auth_sessions (
  id bigint generated by default as identity primary key,
  user_id bigint not null references public.mobile_users(id) on delete cascade,
  token_hash text not null unique,
  expires_at bigint not null,
  created_at timestamptz not null,
  revoked_at timestamptz
);

create index if not exists idx_mobile_auth_sessions_token
on public.mobile_auth_sessions(token_hash);

create index if not exists idx_mobile_auth_sessions_user
on public.mobile_auth_sessions(user_id);

create table if not exists public.mobile_login_history (
  id bigint generated by default as identity primary key,
  user_id bigint references public.mobile_users(id) on delete set null,
  username text not null,
  status text not null check (status in ('success', 'failed')),
  device text not null default '',
  created_at timestamptz not null
);

create index if not exists idx_mobile_login_history_user
on public.mobile_login_history(user_id, id desc);

create table if not exists public.mobile_friendships (
  id bigint generated by default as identity primary key,
  user_low_id bigint not null references public.mobile_users(id) on delete cascade,
  user_high_id bigint not null references public.mobile_users(id) on delete cascade,
  created_at timestamptz not null,
  unique(user_low_id, user_high_id),
  check(user_low_id < user_high_id)
);

create index if not exists idx_mobile_friendships_low
on public.mobile_friendships(user_low_id);

create index if not exists idx_mobile_friendships_high
on public.mobile_friendships(user_high_id);

create table if not exists public.mobile_friend_invite_tokens (
  id bigint generated by default as identity primary key,
  owner_user_id bigint not null references public.mobile_users(id) on delete cascade,
  token_hash text not null unique,
  expires_at bigint not null,
  created_at timestamptz not null,
  used_at timestamptz,
  used_by_user_id bigint references public.mobile_users(id) on delete set null
);

create index if not exists idx_mobile_friend_invite_hash
on public.mobile_friend_invite_tokens(token_hash);

create index if not exists idx_mobile_friend_invite_owner
on public.mobile_friend_invite_tokens(owner_user_id);
```

### 匯入流程

```powershell
python scripts/migrate_sqlite_accounts_to_supabase.py
python scripts/migrate_sqlite_accounts_to_supabase.py --apply
```

- 第一行只做 dry-run，輸出 users、login history、friendships 筆數與 username 衝突。
- 第二行寫入 Supabase，需要先設定 `SUPABASE_URL` 與 `SUPABASE_SERVICE_ROLE_KEY`。
- 匯入會保留原本 `mobile_users.id`，確保既有社群貼文 `user_id` 仍可對應。
- 匯入不搬 `auth_sessions`，避免長期 token 從本機直接沿用到 Cloud Run。

### 驗證規範

- 設定 `ACCOUNT_STORE_BACKEND=supabase` 後，手機端可重新登入既有帳號。
- 登入成功後，Supabase `mobile_auth_sessions` 應出現 token hash。
- 登出後，該 session 的 `revoked_at` 應被填入。
- 產生好友 QR 後，`mobile_friend_invite_tokens` 應出現短效 token hash。
- 掃描好友 QR 後，`mobile_friendships` 應出現排序後的 `(user_low_id, user_high_id)`。

## 06/04: '新增 following feed Supabase 優先讀取'

### 架構規範

- `GET /api/mobile/feed/following` 會優先讀 Supabase。
- 後端先從 Supabase `user_follows` 取得目前使用者追蹤的 `following_user_id`。
- 再從 Supabase `community_posts` 讀取追蹤者貼文，依 `created_at desc, id desc` 排序。
- Supabase following feed 會補齊貼文互動欄位：
  - `likes`
  - `comments`
  - `liked_by_me`
  - `bookmarked_by_me`
- Supabase 無資料、資料表不可用或讀取失敗時 fallback SQLite。
- `GET /api/mobile/feed/trending` 尚未切 Supabase，仍保留 SQLite scoring。
- 目前 Supabase following feed 使用時間排序；SQLite 舊版 following feed 的 `feed_score` 熱度排序保留在 fallback。正式多人部署前再評估是否將 scoring 搬到 Postgres function 或 view。

### API 回傳格式

```json
{
  "posts": [
    {
      "id": 1,
      "user_id": 2,
      "body": "practice clip",
      "likes": 2,
      "comments": 1,
      "liked_by_me": true,
      "bookmarked_by_me": false
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0,
  "hasMoreFollowing": false
}
```

### 驗證規範

- Supabase 已建立並同步 `user_follows`、`community_posts`、`community_post_reactions`、`community_comments`、`community_post_bookmarks`。
- 手機端追蹤某使用者後，該使用者已同步到 Supabase 的貼文會出現在 following feed。
- 換電腦或重啟後端後，只要 Supabase env 正確，following feed 仍可顯示追蹤者貼文。
- Supabase 不可用時，following feed fallback SQLite 舊行為。

## 06/04: '新增 user_follows Supabase 追蹤同步與個人頁狀態讀取'

### 架構規範

- `POST /api/mobile/follows/{target_user_id}` 仍先由 SQLite 驗證使用者存在、避免自己追蹤自己，並寫入追蹤關係。
- `DELETE /api/mobile/follows/{target_user_id}` 仍先由 SQLite 刪除追蹤關係。
- SQLite 操作成功後，後端嘗試同步 Supabase `user_follows`。
- 後端同步採「先刪除同一組 follow，再依目前 following 狀態重新 insert」。
- Supabase follows 同步失敗只記錄 warning，不阻斷 App 追蹤流程。
- `GET /api/mobile/profile`、`GET /api/mobile/users/{target_user_id}/profile`、`GET /api/mobile/users/{target_user_id}/profile-page` 會優先用 Supabase `user_follows` 補：
  - `followers_count`
  - `following_count`
  - `is_following`
- Supabase follows 讀取失敗時 fallback SQLite。
- following feed 尚未切 Supabase，仍保留 SQLite 查詢，下一階段再處理。

### Supabase SQL

```sql
create table if not exists public.user_follows (
  follower_user_id bigint not null,
  following_user_id bigint not null,
  created_at timestamptz not null default now(),
  primary key (follower_user_id, following_user_id),
  check (follower_user_id <> following_user_id)
);

create index if not exists idx_user_follows_following
on public.user_follows(following_user_id);
```

### API 回傳格式

追蹤 API 仍維持既有格式：

```json
{
  "follower_user_id": 1,
  "following_user_id": 2,
  "is_following": true
}
```

個人頁 profile 重點欄位如下：

```json
{
  "followers_count": 1,
  "following_count": 2,
  "is_following": true,
  "is_self": false
}
```

### 驗證規範

- 在 Supabase SQL Editor 建立 `user_follows`。
- 手機端追蹤其他使用者後，Supabase `user_follows` 出現 `(follower_user_id, following_user_id)`。
- 手機端取消追蹤後，該列會被刪除。
- 重新開 App 或換電腦後，公開個人頁的 `is_following`、followers/following count 以 Supabase 結果顯示。
- Supabase 不可用時，App 追蹤仍走 SQLite 本機流程。

## 06/04: '新增 community_post_bookmarks Supabase 收藏同步'

### 架構規範

- `POST /api/community/posts/{post_id}/bookmark` 仍先由 SQLite 驗證貼文存在並切換收藏。
- SQLite 切換成功後，後端嘗試同步 Supabase `community_post_bookmarks`。
- 後端同步採「先刪除同一組 user bookmark，再依目前 bookmarked 狀態重新 insert」。
- Supabase bookmarks 同步失敗只記錄 warning，不阻斷 App 收藏流程。
- Supabase 個人頁貼文讀取會用 `community_post_bookmarks` 補 `bookmarked_by_me`。
- 手機端 Bookmark icon 現在會呼叫既有收藏 API，並用 API 回傳更新列表狀態。

### Supabase SQL

```sql
create table if not exists public.community_post_bookmarks (
  post_id bigint not null,
  user_id bigint not null,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);

create index if not exists idx_community_post_bookmarks_user
on public.community_post_bookmarks(user_id);
```

### API 回傳格式

貼文收藏後仍回傳完整貼文物件，重點欄位如下：

```json
{
  "id": 1,
  "bookmarked_by_me": true
}
```

### 驗證規範

- 在 Supabase SQL Editor 建立 `community_post_bookmarks`。
- 手機端對貼文按 Bookmark 後，Supabase `community_post_bookmarks` 出現 `(post_id, user_id)`。
- 再按一次 Bookmark 後，該列會被刪除。
- 重新開 App 或換電腦後，個人頁貼文的 `bookmarked_by_me` 以 Supabase 結果顯示。
- Supabase 不可用時，App 收藏仍走 SQLite 本機流程。

## 06/04: '修正手機端遠端啟動順序與舊 Expo port 清理'

### 架構規範

- `start_mobile_remote.bat` 啟動手機端前會先清理舊的 Expo web preview port 與 Metro port。
- 批次檔會先關閉舊的 `cloudflared.exe`，避免使用失效的 trycloudflare URL。
- Expo Cloudflare Quick Tunnel 建立後，Metro 會用 `EXPO_PACKAGER_PROXY_URL=%EXPO_PUBLIC_URL%` 啟動，確保 Expo manifest 回傳 tunnel 位址。
- Metro 啟動後會檢查本機 `%EXPO_METRO_PORT%/status`。
- 後端 health check 與 API tunnel 流程維持不變。

### 驗證規範

- 執行 `start_mobile_remote.bat` 後，畫面需先顯示 `OK Expo URL: exps://...trycloudflare.com`。
- 接著畫面需顯示 `OK Expo Metro is ready.`。
- 手機 Expo Go 只掃最後輸出的 QR code；舊 QR code 會因 trycloudflare URL 變更而失效。

## 06/04: '新增 community reactions Supabase 按讚同步與統計讀取'

### 架構規範

- `POST /api/community/posts/{post_id}/like` 仍先由 SQLite 驗證貼文存在並切換按讚。
- SQLite 切換成功後，後端嘗試同步 Supabase `community_post_reactions`。
- `POST /api/community/comments/{comment_id}/like` 仍先由 SQLite 驗證留言存在並切換按讚。
- SQLite 切換成功後，後端嘗試同步 Supabase `community_comment_reactions`。
- 後端同步採「先刪除同一組 user reaction，再依目前 liked 狀態重新 insert」；測試期不依賴 PostgREST composite upsert。
- Supabase reactions 同步失敗只記錄 warning，不阻斷 App 按讚流程。
- Supabase 個人頁貼文讀取會用 `community_post_reactions` 補 `likes` 與 `liked_by_me`，並用 `community_comments` 補 `comments`。
- Supabase 留言讀取會用 `community_comment_reactions` 補 `likes` 與 `liked_by_me`。
- `bookmarked_by_me` 尚未切 Supabase，仍固定為 `false`，待收藏資料表遷移後再補。

### Supabase SQL

```sql
create table if not exists public.community_post_reactions (
  post_id bigint not null,
  user_id bigint not null,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);

create index if not exists idx_community_post_reactions_user
on public.community_post_reactions(user_id);

create table if not exists public.community_comment_reactions (
  comment_id bigint not null,
  user_id bigint not null,
  created_at timestamptz not null default now(),
  primary key (comment_id, user_id)
);

create index if not exists idx_community_comment_reactions_user
on public.community_comment_reactions(user_id);
```

### API 回傳格式

貼文仍維持既有欄位：

```json
{
  "id": 1,
  "likes": 3,
  "comments": 2,
  "liked_by_me": true,
  "bookmarked_by_me": false
}
```

留言仍維持既有欄位：

```json
{
  "id": 10,
  "post_id": 1,
  "likes": 1,
  "liked_by_me": true
}
```

### 驗證規範

- 在 Supabase SQL Editor 建立 `community_post_reactions` 與 `community_comment_reactions`。
- 手機端對貼文按讚後，Supabase `community_post_reactions` 出現 `(post_id, user_id)`；取消按讚後該列消失。
- 手機端對留言按讚後，Supabase `community_comment_reactions` 出現 `(comment_id, user_id)`；取消按讚後該列消失。
- 重新開 App 或換電腦後，個人頁貼文與留言 sheet 的 `likes`、`liked_by_me` 以 Supabase 結果顯示。
- Supabase 不可用時，App 按讚仍走 SQLite 本機流程。

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
EXPO_PUBLIC_MOBILE_UPLOAD_TARGET_BYTES=15728640
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
- 自己的主頁左上角維持發文 `+`，不顯示「編輯個人檔案」主操作按鈕；個人資料編輯入口由右上設定齒輪進入。
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
## 06/04: '改為互相關注即好友'

### 規範

- 手機端好友不再使用 QR Code 邀請、`friendships` 或 `friend_invite_tokens` 建立關係。
- `GET /api/friends` 會從 `user_follows` 計算：A 追蹤 B 且 B 追蹤 A 時，雙方才會出現在好友列表。
- `POST /api/friends/{friend_user_id}/start-game` 的好友檢查同樣使用互相關注規則。
- 手機端保留「掃碼」分頁，但功能改為個人主頁 QR：掃到 `cuevex://user?userId=...` 後開啟對方主頁。
- 手機端移除好友 QR 產生/接受流程；使用者在個人頁互相按「追蹤」後即成為好友。
- 有 `SUPABASE_URL` 與 `SUPABASE_SERVICE_ROLE_KEY` 時，手機端 follow/unfollow 直接寫入 Supabase `user_follows`；SQLite 只作本機測試或未設定 Supabase 時的 fallback。

### API 回傳格式

```json
{
  "friends": [
    {
      "id": 2,
      "username": "PlayerB",
      "display_name": "PlayerB",
      "bio": "",
      "avatar_url": "",
      "friendship_created_at": "2026-06-04T12:00:00Z"
    }
  ]
}
```
## 06/05: '新增 CueVex 官方帳號顯示規則'

### 規範

- username 或 display name 為 `CueVex` / `CueVex 官方` 時，手機端 profile `player_level` 回傳 `官方帳號`。
- 官方帳號新貼文的 `community_posts.badge` 寫入 `官方帳號`。
- 舊貼文即使 `badge` 仍為 `玩家`，只要 `author_name` 為 `CueVex`，API 回傳時顯示 `官方帳號`。
- 官方帳號留言的 `author_player_level` 顯示 `官方帳號`。
- 手機端官方 badge 使用色票 `#1D9BF0`。

## 06/05: '修正留言頭像 fallback 不可使用貼文作者'

### 規範

- `PostCard.fallbackAvatarUrl` 只代表貼文作者頭像 fallback，不可用於目前登入者留言頭像。
- `CommentSheet.currentAvatarUrl` 必須由目前登入者的 `mobile profile avatar_url` 傳入。
- 在對方個人頁或對方貼文下留言時，若新留言回傳暫時缺 `author_avatar_url`，前端只能 fallback 目前登入者頭像，不可 fallback 貼文作者頭像。
- 後端 Supabase-first 建立貼文/留言後，若 repository 尚未讀到 profile avatar，回傳時可用目前 token 使用者的 `avatar_url` 補 `author_avatar_url`。

## 06/04: '修正貼文與留言作者頭像 fallback'

### 規範

- 貼文與留言的 `author_avatar_url` 讀取 Supabase 作者資料時，優先使用 `mobile_profiles.avatar_url`。
- 若 `mobile_profiles` 沒有該使用者資料，或 `avatar_url` 為空，需 fallback 到 `mobile_users.avatar_url`。
- `display_name` 與 `bio` 同樣維持 `mobile_profiles` 優先、`mobile_users` fallback，避免帳號已有頭像但社群卡片仍顯示預設圖示。
- 公開 profile 合併時不得用空的 `mobile_profiles.avatar_url` 覆蓋 `mobile_users.avatar_url`。

## 06/04: '社群寫入改為 Supabase-first'

### 規範

- 手機端社群寫入在 Supabase env 存在時，不再先寫 SQLite。
- `POST /api/community/posts` 直接寫 Supabase `community_posts`，由後端產生相容 `bigint` id，回傳既有 `CommunityPost` 格式。
- `POST /api/community/posts/{post_id}/comments` 直接寫 Supabase `community_comments`，並重新讀取貼文統計後回傳 `{ comment, post }`。
- `POST /api/community/posts/{post_id}/like` 直接切換 Supabase `community_post_reactions`。
- `POST /api/community/comments/{comment_id}/like` 直接切換 Supabase `community_comment_reactions`。
- `POST /api/community/posts/{post_id}/bookmark` 直接切換 Supabase `community_post_bookmarks`。
- `DELETE /api/community/posts/{post_id}` 在 Supabase 可用時先用 Supabase 貼文作者驗證，再刪除 Supabase `community_posts`。
- SQLite 只作本機測試、未設定 Supabase env，或舊測試 fake repository 不支援 direct create/read 方法時的 fallback。

### API 回傳格式

既有手機端 API endpoint 與回傳欄位不變：

```json
{
  "id": 1760000000000123,
  "user_id": 1,
  "author_name": "PlayerA",
  "title": "",
  "body": "練球紀錄",
  "image_urls": [],
  "likes": 0,
  "comments": 0,
  "liked_by_me": false,
  "bookmarked_by_me": false
}
```

## 06/05: '新增手機端帳號停用與刪除確認'

### 規範

- `PATCH /api/auth/me/deactivate` 需驗證目前密碼，成功後將 `mobile_users.is_deactivated` 設為 `true`、寫入 `deactivated_at`，並撤銷該帳號所有有效 session。
- 已停用帳號重新登入且密碼正確時，後端需自動恢復帳號，將 `is_deactivated` 設為 `false` 並清空 `deactivated_at`。
- 停用帳號不可刪除資料；公開個人頁、貼文列表、追蹤動態與推薦動態需對其他使用者隱藏該帳號的資料與貼文。
- `DELETE /api/auth/me` 需驗證目前密碼，成功後清理該帳號在 Supabase 的社群資料、profile、追蹤與好友關係，再刪除 `mobile_users`。
- 手機端 `帳號狀態` 操作需先進入說明頁，再由底部按鈕開啟密碼確認框；不得在列表頁顯示長說明。

### Supabase SQL

```sql
alter table public.mobile_users
add column if not exists is_deactivated boolean not null default false;

alter table public.mobile_users
add column if not exists deactivated_at timestamptz;
```

### API 範例

```json
{
  "password": "目前密碼"
}
```

## 06/05: '新增社群我的收藏列表'

### 規範

- `GET /api/community/bookmarks` 回傳目前登入使用者收藏的貼文。
- 排序需依收藏時間由新到舊：`community_post_bookmarks.created_at desc, post_id desc`。
- 回傳貼文格式需與既有社群貼文列表一致，包含 `likes`、`comments`、`liked_by_me`、`bookmarked_by_me`、`author_avatar_url`。
- 手機端設定頁 `我的收藏` 需開啟獨立頁面，並重用既有貼文卡片互動。
- 使用者在收藏頁取消收藏後，該貼文需從收藏頁即時移除。

### API 範例

```json
{
  "posts": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

### Supabase SQL

既有 `community_post_bookmarks` 需有 `created_at` 才能依收藏時間排序：

```sql
alter table public.community_post_bookmarks
add column if not exists created_at timestamptz not null default now();
```

## 06/05: '新增通知設定 Supabase 串接'

### 規範

- 手機端使用 `expo-notifications` 取得 Expo push token，僅在非 Web 平台登入後嘗試註冊。
- 通知設定由 `user_notification_settings` 保存，每位 `mobile_users.id` 對應一筆設定。
- Push token 由 `user_push_tokens` 保存，同一使用者與同一 token 重複註冊時更新 `last_seen_at`、`device`、`platform` 與 `is_active`。
- 目前只完成設定儲存與 token 登錄；實際發送推播需後續由事件服務讀取設定後送出。

### API

- `GET /api/mobile/notifications/settings`
- `PATCH /api/mobile/notifications/settings`
- `POST /api/mobile/notifications/push-token`

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

## 06/06: '新增 Firebase / Expo 推播產品化事件發送'

### 規範

- 手機端維持 Expo managed workflow，使用 `expo-notifications` 取得 Expo Push Token，不直接使用 Firebase Messaging SDK。
- Firebase Console 只用於 Android / iOS 推播憑證設定；後端實際透過 Expo Push API 發送。
- App 在登入成功、恢復既有 session、推播通知總開關重新開啟時嘗試註冊 Expo Push Token。
- 手機端需設定 `Notifications.setNotificationHandler`，讓 App 在前景收到推播時仍顯示 banner/list 並播放聲音。
- Android 需在 `app.json` 宣告 `POST_NOTIFICATIONS` 權限並建立 `default` notification channel，importance 使用 `MAX`。
- 後端 Expo Push message 需帶 `channelId: "default"`、`priority: "high"` 與 `sound: "default"`，確保 Android 使用同一個高優先通知 channel。
- `Notifications.getExpoPushTokenAsync` 需帶入 EAS project id，確保 token 綁定到目前 EAS 專案。
- EAS build profile 仍需設定 `EXPO_PUBLIC_MOBILE_API_URL`；手機端 `getConfiguredApiBaseUrl()` 另保留 Cloud Run fallback，避免 production APK 因 env 未嵌入而出現「後端位址未設定」。
- Web 預覽、通知權限未開、token 取得失敗時，不得阻斷登入與設定頁操作。
- 後端需依 `user_notification_settings` 判斷是否發送，並讀取 `user_push_tokens.is_active=true` 的 token。
- 後端送出 Expo Push 後需保存 ticket id 到 `user_notification_events.expo_ticket_ids`；若手機未收到但事件狀態為 `sent`，需透過 Expo receipt 查詢實際投遞結果。
- `GET /api/mobile/notifications/events?check_receipts=true` 回傳目前使用者最近通知事件，並對已送出的 ticket 查 receipt。
- `POST /api/mobile/notifications/test-push` 會對目前登入使用者送出測試推播，用於排除社群事件觸發問題。
- `GET /api/diagnostics/mobile-push-receipts` 會檢查最近 `sent` 事件的 Expo receipt，不輸出 Expo Push Token，用於 Cloud Run 部署後定位投遞問題。
- 第一版事件：
  - `post_liked`：有人按讚我的貼文。
  - `post_commented`：有人留言我的貼文。
  - `comment_liked`：有人按讚我的留言。
  - `new_follower`：有人追蹤我。
  - `mutual_follow`：達成互相關注。
- 自己對自己的貼文、留言或追蹤事件不發推播。
- Expo 回 `DeviceNotRegistered` 或 `InvalidCredentials` 時，後端需將 token 標記為 inactive。

### Supabase SQL

在 Supabase SQL Editor 執行：

```sql
-- 專案檔案：scripts/supabase_mobile_push_notifications.sql
```

此 SQL 會建立或補齊：

- `user_notification_settings`
- `user_push_tokens`
- `user_notification_events`
  - `expo_ticket_ids jsonb`
  - `expo_receipts jsonb`
  - `receipt_checked_at timestamptz`

### Firebase / Expo 設定

- Firebase Console 建立 Android app 與 iOS app。
- Android 使用 package：`com.cuevex.mobile`；iOS 使用 bundle identifier：`com.cuevex.mobile`。
- Android 下載 `google-services.json`，iOS 下載 `GoogleService-Info.plist`。
- Android `mobile/app.json` 需在 `expo.android` 設定 `"googleServicesFile": "./google-services.json"`，讓 EAS Build 將 Firebase app 設定帶入正式 Android build。
- iOS `mobile/app.json` 需在 `expo.ios` 設定 `"googleServicesFile": "./GoogleService-Info.plist"`，讓 EAS Build 將 Firebase iOS app 設定帶入正式 iOS build。
- 使用 EAS credentials 或 Expo push credentials 將 Firebase Cloud Messaging FCM V1 服務帳戶憑證綁定到正式 build；不可使用 `Push Notifications (Legacy)`。
- Firebase Admin SDK 服務帳戶私鑰 JSON 只用於上傳 EAS credentials，需排除在 Git 版控外；`google-services.json` 則可提交，因其是 Android app 公開設定檔。
- 根目錄 `.easignore` 與 `mobile/.easignore` 需排除 `.pytest_cache/`、`**/.pytest_cache/`、`pytest-cache-files-*/`、`.venv/`、`runtime/`、Firebase Admin 私鑰與本機錄影資料，避免 EAS Build 壓縮專案時掃到本機快取或私密檔造成 `EPERM` / archive upload 失敗。
- 若 Windows 上仍出現 `EPERM: operation not permitted, opendir/scandir '.pytest_cache'` 或 `pytest-cache-files-*`，可直接刪除專案內所有 pytest 快取；這些資料夾是 pytest 可再生快取，不屬於必要 build 內容。
- 根目錄 `pytest.ini` 需設定 `addopts = -p no:cacheprovider`，避免本機執行 pytest 後重新產生 `.pytest_cache/`，造成下一次 EAS Build 壓縮失敗。
- 若 Supabase `user_push_tokens` 已有 token 但收不到推播，先檢查 `/api/diagnostics/cloud-mobile` 的 `supabase_rest.notifications.ok`；若 `user_notification_events` 回 404，代表尚未執行 `scripts/supabase_mobile_push_notifications.sql`，後端會在送推播前寫事件紀錄時失敗。
- Expo Go 可驗證通知設定與 token 註冊；正式實機推播以 EAS build 驗收。

### Diagnostics

- `GET /api/diagnostics/cloud-mobile` 的 `supabase_rest.notifications` 需顯示：
  - `user_notification_settings`
  - `user_push_tokens`
  - `user_notification_events`
  - Expo Push API endpoint

### 驗收規範

- 登入後 Supabase `user_push_tokens` 需出現目前裝置的 Expo Push Token。
- 關閉 `push_enabled` 時，社群互動只記錄 skipped event，不發送推播。
- 其他帳號按讚貼文、留言貼文、按讚留言、追蹤時，符合設定的接收者需收到推播。
- `user_notification_events` 需記錄 `pending`、`sent`、`failed` 或 `skipped` 狀態。
- 若 `status=sent` 但手機未收到，呼叫 `GET /api/mobile/notifications/events?check_receipts=true`；若 receipt 仍為 `ok`，再檢查裝置通知權限、Android 背景限制、是否安裝最新 EAS build 與 token 是否更新。

## 06/05: '新增 Supabase 社群 RPC 效能優化'

### 規範

- 手機端仍只呼叫 FastAPI，不直接連 Supabase。
- 社群讀寫在 Supabase env 存在時優先使用 RPC，減少多次 PostgREST 往返。
- RPC 尚未部署、找不到 function 或執行失敗時，後端需 fallback 既有 REST / SQLite 流程，不可中斷 App。
- `POST /api/community/posts/{post_id}/like` 與 `POST /api/community/posts/{post_id}/bookmark` 回傳格式維持既有 `CommunityPost`。
- `GET /api/community/posts/{post_id}/comments`、`POST /api/community/posts/{post_id}/comments`、`POST /api/community/comments/{comment_id}/like` 優先使用留言 RPC。
- following feed、trending feed、個人頁貼文與收藏貼文需維持既有 API response shape。
- `/api/diagnostics/cloud-mobile` 需回傳 `supabase_rpc`，用來確認 RPC 是否部署與各 function 回應毫秒數。

### Supabase SQL

在 Supabase SQL Editor 執行：

```sql
-- 專案檔案：scripts/supabase_mobile_social_rpc.sql
```

此 SQL 會建立：

- `mobile_hydrated_posts`
- `mobile_toggle_post_like`
- `mobile_toggle_post_bookmark`
- `mobile_following_feed`
- `mobile_trending_feed`
- `mobile_user_posts`
- `mobile_bookmarked_posts`
- `mobile_hydrated_comments`
- `mobile_comments_for_post`
- `mobile_create_comment`
- `mobile_toggle_comment_like`
- 社群貼文、按讚、留言、收藏、追蹤、封鎖相關索引

### 驗收規範

- 執行 SQL 後，`GET /api/diagnostics/cloud-mobile` 的 `supabase_rpc.ok` 應為 `true`。
- 按貼文愛心時，畫面需立即顯示新狀態，重新整理後狀態仍正確。
- 收藏與我的收藏列表需依 Supabase 結果維持一致。
- 留言列表需顯示最新 Supabase 留言、留言按讚需寫入 `community_comment_reactions`，重新開啟留言 sheet 後狀態仍正確。
- 首頁 following / trending feed 需能回傳作者頭像、作者名稱、讚數、留言數、收藏狀態。
- 若暫時移除 RPC function，App 仍可 fallback 使用既有流程。

## 06/06: '手機端 RPC 接線完整體驗檢查'

### 目前已接 RPC 的手機端路徑

- `GET /api/mobile/feed/following`：後端優先呼叫 `mobile_following_feed`，一次回傳貼文、作者、讚數、留言數、`liked_by_me`、`bookmarked_by_me`。
- `GET /api/mobile/feed/trending`：後端優先呼叫 `mobile_trending_feed`。
- `GET /api/mobile/users/{user_id}/posts` 與「我的」頁貼文：後端優先呼叫 `mobile_user_posts`。
- `POST /api/community/posts/{post_id}/like`：後端優先呼叫 `mobile_toggle_post_like`，回傳 hydrated post，支援前端 optimistic UI 後用後端結果校正。
- `POST /api/community/posts/{post_id}/bookmark`：後端優先呼叫 `mobile_toggle_post_bookmark`。
- `GET /api/community/bookmarks`：後端已寫 `mobile_bookmarked_posts` 優先路徑，但 Supabase function 必須先部署。
- `GET /api/community/posts/{post_id}/comments`：後端已寫 `mobile_comments_for_post` 優先路徑，但 Supabase function 必須先部署。
- `POST /api/community/posts/{post_id}/comments`：後端已寫 `mobile_create_comment` 優先路徑，但 Supabase function 必須先部署。
- `POST /api/community/comments/{comment_id}/like`：後端已寫 `mobile_toggle_comment_like` 優先路徑，但 Supabase function 必須先部署。

### 目前 live diagnostics 缺口

`GET /api/diagnostics/cloud-mobile` 目前顯示以下 function 仍為 `404 / PGRST202`：

- `mobile_bookmarked_posts`
- `mobile_hydrated_comments`
- `mobile_comments_for_post`
- `mobile_create_comment`
- `mobile_toggle_comment_like`

這代表 App 功能會 fallback 到 REST / SQLite 路徑，短期可用，但「我的收藏、留言列表、留言送出、留言愛心」仍不是最佳體驗；在網路延遲或資料量增加時，較容易出現慢、狀態校正晚、留言愛心不即時等感受。

### 立即處理

- 在 Supabase SQL Editor 執行完整 `scripts/supabase_mobile_social_rpc.sql`。
- 執行後重新打：

```powershell
$r = Invoke-WebRequest "https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app/api/diagnostics/cloud-mobile" -UseBasicParsing
$r.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

- 驗收標準：`supabase_rpc.ok` 需為 `true`，且上述五個 function 都需 `ok: true`。

### 下一波產品化 RPC 建議

- `mobile_profile_page(viewer_user_id, target_user_id, page_limit, page_offset)`：一次回傳公開/私人/封鎖狀態、profile、follow stats、relationship、第一頁貼文，取代目前個人頁多段 REST 查詢。
- `mobile_follow_list(viewer_user_id, target_user_id, kind, page_limit, page_offset)`：一次回傳追蹤者/追蹤中清單、頭像、名稱、是否已追蹤、是否本人，取代 follow refs + profiles 多段查詢。
- `mobile_toggle_follow(viewer_user_id, target_user_id)`：原子追蹤/取消追蹤，回傳 `is_following`、followers/following count、是否互相關注，避免追蹤按鈕與統計短暫不同步。
- `mobile_block_user(viewer_user_id, target_user_id)` / `mobile_unblock_user(...)`：封鎖與解除封鎖時在資料庫端同步移除追蹤關係並回傳 block state。
- `mobile_dashboard(viewer_user_id)`：一次回傳 profile、好友/互關摘要與必要統計，降低登入後首頁/好友頁初載請求數。

### 使用者體驗驗收

- 首頁 following/trending 首屏載入目標 p95 < 1000ms。
- 貼文按讚、收藏、留言按讚需立即反應，重新整理後狀態仍一致。
- 留言送出後留言列表與貼文留言數需同時更新，不可等待多段 REST 校正。
- 我的收藏需依收藏時間由新到舊排序，取消收藏後立即從列表移除。
- 個人頁切換、追蹤/取消追蹤、封鎖/解除封鎖後，上方數據與貼文可見性需一次更新，不出現短暫舊狀態。

## 06/06: '新增手機端追蹤名單頁'

### 規範

- 手機端個人主頁的「追蹤者」與「追蹤中」數字可點擊。
- 從「追蹤者」點入時，追蹤名單頁預設選中「追蹤者」；從「追蹤中」點入時，預設選中「追蹤中」。
- 追蹤名單頁頂部標題為「追蹤名單」，左上返回回到原個人主頁。
- 頁面內提供「追蹤者」與「追蹤中」兩個切換按鈕，點擊後重新載入同一使用者的對應名單。
- 名單列顯示使用者頭像、顯示名稱與追蹤狀態，點擊列可開啟該使用者個人主頁。
- 私人帳號的追蹤名單不可被未追蹤者查看；本人或已追蹤該私人帳號的使用者可查看。
- 封鎖與被封鎖狀態仍優先於私人帳號規則，雙方不可查看追蹤名單。
- SQLite 與 Supabase `user_follows` 需維持相同 API response shape；Supabase 不可用時 fallback SQLite。

### API

```http
GET /api/mobile/users/{target_user_id}/follows?kind=followers&limit=50&offset=0
Authorization: Bearer <token>
```

`kind` 可為 `followers` 或 `following`。

### 輸出格式

```json
{
  "users": [
    {
      "user": {
        "id": 2,
        "username": "PlayerB"
      },
      "display_name": "PlayerB",
      "avatar_url": "",
      "player_level": "新手玩家 I",
      "is_following": true,
      "is_self": false,
      "followed_at": "2026-06-06T12:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0,
  "kind": "followers"
}
```

私人帳號未授權查看時回傳：

```json
{
  "detail": {
    "code": "PRIVATE_PROFILE",
    "message": "Follow lists are private for this account."
  }
}
```
## 06/11:'修正手機端過期 bearer token 的動態載入失敗'

### 功能範圍

手機端啟動時會從 `SecureStore` 或 web `localStorage` 還原登入 session。若後端回傳 `HTTP 401: Invalid or expired bearer token`，代表本機保存的 token 已過期、被登出或後端 session 已失效。

### 規範用法

- `mobile/App.tsx` 會在 `refreshAll()` 偵測 `HTTP 401` 或 `Invalid or expired bearer token`。
- 偵測到過期 token 時，App 會清除本機 session、使用者資料、個人頁、好友、動態牆、追蹤清單與測試帳號快照。
- 清理完成後顯示「登入已過期」，並回到未登入狀態，讓使用者重新登入。
- 一般登出也共用同一套本機清理流程，避免不同登出路徑漏清狀態。

### 輸出格式

使用者看到的提示：

```text
登入已過期
請重新登入後再載入手機端資料。
```

### 驗證

```powershell
cd mobile
npm.cmd run typecheck
```

## 06/12:'新增手機 PWA LAN 直連模式'

### 功能範圍

手機端若無法使用 Cloudflare Quick Tunnel 或 Expo Go remote，可改用同一個區域網路內的 PWA 模式。PWA 模式不走 proxy、不掃 Expo Go QR，手機直接開啟 `http://<LAN_IP>:19006/?api=http://<LAN_IP>:8001&v=pwa-lan`，並透過網址 `api` 參數固定指向本機 FastAPI backend。

### 規範用法

- 使用 `start_mobile_pwa_lan.bat` 啟動 PWA LAN 模式。
- `mobile/package.json` 提供 `web:pwa` script，實際仍使用 Expo web preview 離線模式。
- `mobile-remote.env` 可記錄 `PWA_API_BASE_URL`、`PWA_PUBLIC_URL` 與 `PWA_WEB_PORT`，供人工檢查目前 LAN PWA 入口。
- `mobile/App.tsx` 的 web 容器改為 `width: 100%`、`maxWidth: 430`，手機瀏覽器不再固定 430px 寬與 900px 高，避免 PWA 頁面在真機上水平溢出或高度卡住。
- `mobile/app.json` 的 web favicon 使用 `assets/cuevex-logo.png`，讓 PWA / browser preview 有一致的 CueVex 圖示。

### 輸出格式

啟動成功後批次檔會印出：

```text
API:       http://<LAN_IP>:8001
PC View:   http://127.0.0.1:19006/?api=http://127.0.0.1:8001&v=pwa-local
Phone PWA: http://<LAN_IP>:19006/?api=http://<LAN_IP>:8001&v=pwa-lan
Mode:      PWA LAN, no proxy
```

### 驗證

```powershell
cd mobile
npm.cmd run typecheck
Invoke-WebRequest "http://127.0.0.1:19006/?api=http://127.0.0.1:8001&v=pwa-local" -UseBasicParsing
Invoke-WebRequest "http://<LAN_IP>:19006/?api=http://<LAN_IP>:8001&v=pwa-lan" -UseBasicParsing
```

手機與電腦必須在同一個網路；若手機無法開啟，優先檢查 Windows Firewall 是否允許 `19006` 與 `8001`。

## 06/12:'新增手機 PWA Cloudflare 固定域名模式'

### 功能範圍

若手機不在同一個 LAN，或需要使用正式固定網址，可使用 Cloudflare Named Tunnel 暴露 PWA 與 API。這個模式仍走 Cloudflare tunnel，但不使用隨機 `trycloudflare.com`，改由自己的 domain 提供固定入口。

### 規範用法

- 使用 `start_mobile_pwa_cloudflare.bat` 啟動固定域名 PWA 模式。
- `mobile-remote.env` 必須設定 `CLOUDFLARE_TUNNEL_MODE=named`、`CLOUDFLARE_TUNNEL_NAME`、`PWA_PUBLIC_URL`、`PWA_API_BASE_URL`。
- `PWA_PUBLIC_URL` 是手機瀏覽器開啟的 PWA 網址，例如 `https://app.example.com`。
- `PWA_API_BASE_URL` 是手機端 API base URL，例如 `https://api.example.com`。
- Cloudflare ingress 需將 PWA domain 轉到 `http://127.0.0.1:19006`，API domain 轉到 `http://127.0.0.1:8001`。
- 啟動時會把 `EXPO_PUBLIC_MOBILE_API_URL` 注入為 `PWA_API_BASE_URL`，PWA 頁面不需要再靠 LAN IP 或 Cloud Run fallback。

### `mobile-remote.env` 範例

```text
CLOUDFLARE_TUNNEL_MODE=named
CLOUDFLARE_TUNNEL_NAME=cuevex-mobile
PWA_PUBLIC_URL=https://app.example.com
PWA_API_BASE_URL=https://api.example.com
PWA_WEB_PORT=19006
MOBILE_PUBLIC_BASE_URL=https://api.example.com
MOBILE_REQUIRE_HTTPS_QR=true
```

### Cloudflare ingress 範例

```yaml
tunnel: cuevex-mobile
credentials-file: C:\Users\User\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: app.example.com
    service: http://127.0.0.1:19006
  - hostname: api.example.com
    service: http://127.0.0.1:8001
  - service: http_status:404
```

### 輸出格式

啟動成功後批次檔會印出：

```text
PWA:       https://app.example.com
API:       https://api.example.com
Local PWA: http://127.0.0.1:19006/?api=http://127.0.0.1:8001&v=pwa-local
Mode:      Cloudflare Named Tunnel, domain PWA
```

### 驗證

```powershell
Invoke-WebRequest "http://127.0.0.1:19006/?api=http://127.0.0.1:8001&v=pwa-local" -UseBasicParsing
Invoke-WebRequest "https://app.example.com" -UseBasicParsing
Invoke-WebRequest "https://api.example.com/health" -UseBasicParsing
```

若 `https://app.example.com` 可開，但動態載入失敗，先檢查 `PWA_API_BASE_URL` 是否填成 API domain，並確認 Cloudflare ingress 的 API hostname 有轉到 `127.0.0.1:8001`。

## 06/19:'修正 PWA 固定域名 named tunnel 名稱檢查'

### 功能範圍

固定域名模式啟動前會先檢查 `CLOUDFLARE_TUNNEL_NAME` 是否對應 Cloudflare 帳號內實際存在的 named tunnel。若 tunnel 已由 Windows `cloudflared` service 連線，批次檔會沿用既有連線，不再強制結束所有 `cloudflared.exe` 後重開，避免中斷已安裝的 service connector。

### 規範用法

- `mobile-remote.env` 的 `CLOUDFLARE_TUNNEL_NAME` 必須完全等於 `cloudflared tunnel list` 顯示的 `NAME` 或直接填 tunnel UUID。
- 本專案固定 PWA domain 使用的 tunnel 名稱為 `CueVex PWA`。
- 若 log 出現 `error parsing tunnel ID`，代表名稱或 ID 不存在，不是 PWA 或 API 程式啟動失敗。
- 若 tunnel 已顯示 `CONNECTOR ID`，表示 Cloudflare 端已有 connector 連線，啟動流程會直接進入後端與 PWA preview 檢查。

### 範例

```text
CLOUDFLARE_TUNNEL_MODE=named
CLOUDFLARE_TUNNEL_NAME=CueVex PWA
PWA_PUBLIC_URL=https://apppwa.lessleap.com
PWA_API_BASE_URL=https://apppwaapi.lessleap.com
```

### 驗證

```powershell
cloudflared tunnel list
cloudflared tunnel info "CueVex PWA"
.\start_mobile_pwa_cloudflare.bat
```

## 06/12:'修正 iOS 17 加到主畫面仍顯示 Safari 搜尋欄'

### 功能範圍

iOS Safari 只有在網頁以 Home Screen web app 模式啟動時，才會隱藏 Safari 下方搜尋欄。若 HTML 沒有 Apple standalone meta，或使用 Expo dev server 的臨時 HTML，加入主畫面後仍可能以一般 Safari 分頁開啟。

### 規範用法

- PWA 模式不再直接用 Expo web dev server 作為對外入口；`mobile/package.json` 的 `web:pwa` 會先 `expo export --platform web`，再 patch `dist/index.html`，最後用本機 static server 服務 `dist`。
- `scripts/patch-pwa-html.cjs` 必須注入：
  - `apple-mobile-web-app-capable=yes`
  - `mobile-web-app-capable=yes`
  - `apple-mobile-web-app-title=CueVex`
  - `apple-mobile-web-app-status-bar-style=black-translucent`
  - `theme-color=#ffffff`
  - `manifest.webmanifest`
  - `apple-touch-icon`
- PWA icon 使用 `mobile/assets/cuevex-logo.png`，export 後會以 Expo hashed asset 形式寫入 `manifest.webmanifest` 與 `apple-touch-icon`。
- `scripts/serve-pwa.cjs` 服務 `mobile/dist`，非檔案路由 fallback 到 `index.html`。
- Cloudflare 固定域名模式需將 PWA domain 轉到 static server `http://127.0.0.1:19006`，不可轉到 Expo dev server。

### 驗證

```powershell
cd mobile
npm.cmd run export:pwa
Select-String -Path dist/index.html -Pattern "apple-mobile-web-app-capable","manifest.webmanifest"
```

iPhone 需刪除舊的主畫面圖示，重新用 Safari 開啟 `PWA_PUBLIC_URL` 後再「加入主畫面」。舊圖示可能保留舊 manifest/HTML 快取，不能用來驗證本次修正。

## 06/12:'修正 iOS PWA 輸入放大與外層頁面滑動'

### 功能範圍

iOS Safari / PWA 在聚焦小於 16px 的 input 時會自動放大頁面。PWA 外層 HTML 若仍可滾動，也會出現整個頁面上下滑動或橡皮筋回彈。

### 規範用法

- 所有手機端 `TextInput` 可聚焦文字欄位字級不得小於 16px。
- `scripts/patch-pwa-html.cjs` 會將 viewport 改為 `initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover`。
- PWA HTML 的 `html`、`body` 與 `#root` 固定為 100% 高寬並 `overflow: hidden`，避免外層 document 捲動。
- App 內部列表仍使用 React Native `ScrollView` / `FlatList` 處理內容滾動，不依賴 body scroll。

### 驗證

```powershell
cd mobile
npm.cmd run export:pwa
Select-String -Path dist/index.html -Pattern "maximum-scale=1","overscroll-behavior","apple-mobile-web-app-capable"
npm.cmd run typecheck
```

若 iPhone 已加過舊版主畫面圖示，需刪除後重新加入；舊 PWA icon 可能仍使用舊 HTML 與 viewport 設定。

## 06/12:'修正 PWA 固定域名登入與鍵盤留白'

### 功能範圍

PWA static export 不可依賴瀏覽器 hostname fallback 推算 API，否則固定域名 `https://apppwa.lessleap.com` 會被推成 `http://apppwa.lessleap.com:8001`，造成登入失敗。iOS PWA 的鍵盤高度也不可再疊加 `KeyboardAvoidingView` 與 `body position: fixed`，避免輸入帳密時整體畫面上移並留下過多底部空白。

### 規範用法

- `npm.cmd run export:pwa` 由 `scripts/export-pwa.cjs` 執行，會讀取根目錄 `mobile-remote.env`。
- PWA export 時必須使用 `PWA_API_BASE_URL` 注入 `EXPO_PUBLIC_MOBILE_API_URL`。
- `scripts/patch-pwa-html.cjs` 會在 `dist/index.html` 注入 `<meta name="cuevex-api-base-url" content="...">`。
- `mobile/src/env.ts` 讀取 API base URL 的優先序為：網址 `api` 參數、`cuevex-api-base-url` meta、PWA runtime global、`EXPO_PUBLIC_MOBILE_API_URL`、web hostname fallback。
- 固定 PWA host `apppwa.lessleap.com` 會直接映射到 `https://apppwaapi.lessleap.com`，作為 meta/cache 讀取失敗時的保險。
- Web/PWA 登入頁不使用 `KeyboardAvoidingView`。
- PWA HTML 的 `body` 使用 `position: relative` 與 `overflow: hidden`，不可使用 `position: fixed`。
- PWA HTML 使用 `height: 100%` 與 `min-height: -webkit-fill-available` 管理 iOS standalone 高度；不可用 JS 鎖 `visualViewport.height`，避免 iOS 鍵盤後留下錯誤底部空白。
- Web/PWA 登入與註冊頁的 `ScrollView` content 需垂直置中，不可把剩餘高度全部留在表單下方。
- 根路徑 `https://apppwa.lessleap.com/` 會自動補上最新 `v` 參數，避免使用者手動輸入無版本 URL 時吃到舊快取。
- iOS PWA 的 bottom nav 高度需包含 home indicator safe-area 視覺空間；tab bar 背景必須延伸到底部，避免 nav 下方出現獨立白色留白。
- `manifest.webmanifest` 回應必須使用 `Cache-Control: no-store`，且 `start_url` 帶版本參數，避免 iOS 主畫面圖示長時間保留舊 manifest。

### 驗證

```powershell
cd mobile
npm.cmd run export:pwa
Select-String -Path dist/index.html -Pattern "cuevex-api-base-url","apppwaapi.lessleap.com","position: relative"
npm.cmd run typecheck
Invoke-WebRequest "https://apppwaapi.lessleap.com/health" -UseBasicParsing
```

## 06/11:'修正 Supabase 登入紀錄主鍵重複造成 HTTP 500'

### 功能範圍

Supabase mobile 帳號資料表的 `mobile_users`、`mobile_auth_sessions` 與 `mobile_login_history` 使用 `generated by default as identity` 主鍵。登入與建立 session 時不應由應用程式手動推算下一個 `id`，否則當 Supabase sequence 與既有資料不同步時，會發生 `duplicate key value violates unique constraint "mobile_login_history_pkey"`，並讓 `/api/auth/login` 回傳 HTTP 500。

### 規範用法

- `SupabaseAccountStore.create_user()` 新增一般使用者時不送 `id`，由 Supabase identity 產生。
- `SupabaseAccountStore.create_session()` 新增 `mobile_auth_sessions` 時不送 `id`。
- `SupabaseAccountStore.record_login()` 新增 `mobile_login_history` 時不送 `id`。
- 若 Supabase identity sequence 落後、導致 `mobile_users`、`mobile_auth_sessions` 或 `mobile_login_history` 自動產生既有 `id`，只針對主鍵碰撞以目前最大 `id + 1` 重試一次。
- `username` 唯一鍵衝突仍回傳 `USERNAME_TAKEN`，不可被主鍵 sequence fallback 吃掉。
- 匯入舊資料的 `import_user()`、`import_login_history()` 仍可指定既有 `id`，保留 migration 能力。
- 下拉重新載入需確認 `/api/mobile/dashboard`、`/api/friends`、`/api/mobile/profile`、`/api/mobile/users/{id}/posts`、`/api/mobile/feed/following` 與 `/api/mobile/feed/trending` 均不因帳號主鍵 sequence 不同步回 HTTP 500。

### 輸出格式

登入成功仍維持既有格式：

```json
{
  "token": "session-token",
  "user": {"id": 1, "username": "player001"},
  "expires_at": 1760000000000
}
```

### 驗證

```powershell
python -m py_compile backend/storage/supabase_accounts.py
python -m pytest backend/test-program/test_account_store.py
```

重新載入流程可用臨時帳號逐一驗證：

```powershell
Invoke-WebRequest http://127.0.0.1:8001/api/mobile/dashboard -Headers @{Authorization="Bearer <token>"}
Invoke-WebRequest http://127.0.0.1:8001/api/friends -Headers @{Authorization="Bearer <token>"}
Invoke-WebRequest http://127.0.0.1:8001/api/mobile/profile -Headers @{Authorization="Bearer <token>"}
```

## 06/11:'修正 Expo Go remote manifest 離線簽章失敗'

### 功能範圍

手機 remote 使用 Cloudflare Quick Tunnel 供 Expo Go 掃描 `exps://...trycloudflare.com`。Expo Go 需要可簽章的 development manifest；若 Metro 以 `--offline` 啟動且本機沒有 cached development certificate，會出現：

```text
Warning: Unable to resolve manifest assets. Icons and fonts might not work. This operation was aborted.
Offline and no cached development certificate found, unable to sign manifest
```

### 規範用法

- `mobile/package.json` 保留 `start`、`android`、`ios`、`web` 的 `--offline` 預設，供本機離線 web preview 使用。
- 新增 `start:remote` 使用 `expo start` 線上模式，專供 `start_mobile_remote.bat` 啟動手機 Expo Go remote。
- `start_mobile_remote.bat` 的 Expo Metro 必須呼叫 `npm.cmd run start:remote -- --port %EXPO_METRO_PORT% --clear`，不可加 `--offline`。
- Expo Cloudflare tunnel 必須在 Metro 本機 `/status` 通過後才建立，並且要同時通過 `Resolve-DnsName <host>` 與 `https://<host>/status` 檢查後才能輸出 QR。
- 若 cloudflared log 印出 `trycloudflare.com` URL，但 DNS 查詢回 `DNS name does not exist` 或公開 `/status` 不通，該 URL 不可寫入 `mobile-remote.env`，需重試建立新的 tunnel。
- `expo-notifications`、media library、`SafeAreaView` 相關訊息是 Expo Go / React Native 限制或 deprecation warning，不是 HTTP 500 根因。
- App 端只用 `LogBox.ignoreLogs()` 收斂上述已知非阻斷 warning；不可使用 `LogBox.ignoreAllLogs(true)`，避免隱藏 `HTTP 500`、`fetch failed`、render error 等真正需要追查的錯誤。

### 驗證

```powershell
cd mobile
npm.cmd run typecheck
```

重新啟動 `start_mobile_remote.bat` 後，Expo Go log 不應再出現 `Offline and no cached development certificate found, unable to sign manifest`。
若仍看到 media library、expo-notifications 或 SafeAreaView warning，可先視為 Expo Go 限制；完整相簿權限與遠端推播需 development build 驗證。

公開 tunnel 驗證：

```powershell
Resolve-DnsName <expo-host>.trycloudflare.com
Invoke-WebRequest https://<expo-host>.trycloudflare.com/status -UseBasicParsing
```

## 06/11:'修正手機端 API fallback 覆蓋 remote session'

### 功能範圍

手機原生環境沒有 web preview 的 `window.location.search`。若 `EXPO_PUBLIC_MOBILE_API_URL` 沒有注入，`getConfiguredApiBaseUrl()` 會使用 Cloud Run fallback：`https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app`。這個 fallback 只能作為沒有 session 時的預設值，不可覆蓋已儲存在 SecureStore 的 tunnel 或 LAN backend URL。

### 規範用法

- `getExplicitApiBaseUrl()` 只回傳明確來源：網址 `api` 參數、`EXPO_PUBLIC_MOBILE_API_URL`、或 web hostname 推導。
- `getConfiguredApiBaseUrl()` 在 production 仍保留 Cloud Run fallback，供沒有 session 的 production / demo 啟動使用。
- development / Expo Go 模式沒有 explicit URL 時不可自動 fallback 到 Cloud Run，避免 remote 測試誤打 `cuevex-mobile-api-k4ha7h3ykq-de.a.run.app`。
- App 還原既有 session 時，只能用 explicit URL 覆蓋 `stored.baseUrl`；Cloud Run fallback 不可覆蓋 `stored.baseUrl`。
- 若錯誤訊息顯示 `https://cuevex-mobile-api-k4ha7h3ykq-de.a.run.app/...`，代表目前 app 正在走 Cloud Run fallback，不是本機 `8001` 或 Cloudflare remote tunnel。
- API 連線失敗訊息需依 URL 類型給 next step：local/LAN backend 才提示檢查 `:8001`；Cloud Run 或 tunnel 則提示重新掃最新 remote QR 或確認 `EXPO_PUBLIC_MOBILE_API_URL`。

### 驗證

```powershell
cd mobile
npm.cmd run typecheck
```
