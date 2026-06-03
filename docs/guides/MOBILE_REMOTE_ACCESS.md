# Mobile Remote Access with Cloudflare Quick Tunnel

## 06/01: '新增 Cloudflare Quick Tunnel 一鍵啟動'

### 目的

讓 Expo 手機 App 在不同網路也能登入桌面端帳號、查看數據、掃描 QR 加好友。預設使用 Cloudflare Quick Tunnel，不需要購買網域，也不需要先建立 Named Tunnel。

桌面端 FastAPI 仍跑在本機 `127.0.0.1:8001`，`start_mobile_remote.bat` 會自動取得臨時 `https://*.trycloudflare.com` 網址，並讓後端用這個網址產生手機 QR。Expo Metro 也會另外開一條 Cloudflare Quick Tunnel，避免依賴 Expo/ngrok tunnel。

### 一鍵啟動

```bat
start_mobile_remote.bat
```

腳本會自動：

- 檢查 `.venv`、Node.js、`cloudflared`。
- 若缺少 `cloudflared`，呼叫 `install_cloudflared.bat`。
- 若沒有 `winget`，下載 portable `cloudflared.exe` 到 `tools/cloudflared/`。
- 啟動 `cloudflared tunnel --url http://127.0.0.1:8001`。
- 從 log 擷取 `https://*.trycloudflare.com`。
- 寫入 `mobile-remote.env`。
- 用該公開 URL 啟動 FastAPI 後端。
- 啟動第二條 `cloudflared tunnel --url http://127.0.0.1:18181`，產生 `exps://*.trycloudflare.com` 給 Expo Go 掃描。
- 以 `EXPO_PACKAGER_PROXY_URL=https://...trycloudflare.com` 搭配 `expo start --port 18181 --offline --clear` 啟動 Expo Metro，確保 manifest 與 bundle URL 不會帶本機 port，並避免 Expo Go 快取舊介面。
- 同時注入 `EXPO_PUBLIC_MOBILE_API_URL=https://...trycloudflare.com`，讓 App 開啟後自動填入後端 API 位址。

### 手機使用方式

啟動完成後，批次檔會顯示：

```text
Public API: https://xxxx.trycloudflare.com
Expo URL:  exps://yyyy.trycloudflare.com
PC View:   http://127.0.0.1:19006
```

先用 Expo Go 掃描批次檔印出的 Expo QR。App 開啟後會自動填入 `Public API`，通常只需要輸入桌面端已註冊帳號與密碼即可登入。若要在電腦上檢查同一套手機介面，開啟 `PC View`。

手機端使用 Expo SDK 54，請使用最新版 Expo Go 掃描新的啟動 QR。若曾開過 SDK 51 的舊 QR，請先關掉 Expo Go 裡的舊專案，再重新掃描 `start_mobile_remote.bat` 這次輸出的 QR。

若 Expo Go 顯示 `Could not connect to the server`，請確認 `start_mobile_remote.bat` 有顯示 `Expo URL: exps://...trycloudflare.com`，並掃描批次檔下方的 QR。不要掃描 Expo Metro 視窗內的 LAN QR。

若 Expo Go 顯示 `the request timed out`，通常代表掃到舊 QR 或 Metro manifest 內仍有舊 port。請關閉所有舊的 CueVex Expo Metro / Expo Cloudflare Tunnel 視窗，重新執行 `start_mobile_remote.bat`，只掃描主批次檔新印出的 QR。

```bat
cd mobile
npm.cmd run start -- --port 18181 --offline --clear
```

### QR 好友流程

1. A 手機登入 `https://xxxx.trycloudflare.com`。
2. A 手機產生好友 QR。
3. B 手機在不同網路掃描 QR。
4. B 手機會使用 QR 內的 `baseUrl=https://xxxx.trycloudflare.com` 接受好友邀請。
5. 成功後 B 手機保存該公開 URL，Dashboard 與好友列表會走同一個遠端後端。

### 重要限制

- Quick Tunnel 網址可能每次重啟都不同。
- 每次重啟 `start_mobile_remote.bat` 後，請重新產生好友 QR。
- 若要固定網址，才需要購買/綁定網域並改用 Cloudflare Named Tunnel。
- QR 只包含短效好友邀請 token，不包含密碼或登入 token。
- Expo App 載入 URL 與後端 API URL 是兩個不同 tunnel；登入頁請填 `Public API`，不是 `Expo URL`。
- 手機 Expo 專案使用 `cuevex-mobile-prototype` slug 與 `18181` Metro port，避免和其他 Expo 專案使用同一個 dev server。

### 進階：固定網域 Named Tunnel

若之後要固定網域，可以建立 Named Tunnel：

```bat
cloudflared tunnel login
cloudflared tunnel create cuevex-mobile
cloudflared tunnel route dns cuevex-mobile your-domain.example.com
```

並建立 `%USERPROFILE%\.cloudflared\config.yml`：

```yaml
tunnel: cuevex-mobile
credentials-file: C:\Users\User\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: your-domain.example.com
    service: http://127.0.0.1:8001
  - service: http_status:404
```

目前 `start_mobile_remote.bat` 預設走 Quick Tunnel；固定網域可另行新增 Named Tunnel 啟動腳本。
