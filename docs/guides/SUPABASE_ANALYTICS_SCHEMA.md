# Supabase Analytics Schema

## 06/15: '新增 Supabase Analytics 備份後更新腳本'

### 功能範圍

手機端數據總覽後續可接 Supabase analytics cloud sync。執行 `C:\Users\User\Documents\billiards-analytics-v1.5.1\scripts\supabase_analytics_backup_and_apply.sql` 前，腳本會先備份受影響資料表，再建立 analytics 相關 schema。

### 規範用法

- 需在 Supabase Dashboard 的 SQL Editor 執行完整 `scripts/supabase_analytics_backup_and_apply.sql`。
- 腳本會建立 `cuevex_backups` schema，並把既有 `mobile_users`、`analytics_recordings`、`analytics_events`、`analytics_shot_events`、`analytics_practice_stats`、`analytics_sync_state` 依執行時間備份成 `*_before_analytics_YYYYMMDD_HHMMSS`。
- 原始更新內容來自 `C:\Users\User\Downloads\supabase_analytics.sql`，目前只包含 `create extension`、`alter table add column if not exists`、`create table if not exists` 與 `create index if not exists`，不包含 `drop`、`delete` 或資料覆寫。
- `mobile_users.user_uuid` 會以 `gen_random_uuid()` 補齊既有使用者，並建立唯一索引，供 analytics 表用 UUID 關聯帳號。
- 腳本採兩段式 transaction：備份成功後會先 `commit`，再進行 schema 更新；若更新失敗，已建立的備份表仍會保留。
- 可在 SQL Editor 查看 `notice` 內的 backup table 名稱。

### 輸出格式

備份表命名格式：

```text
cuevex_backups.mobile_users_before_analytics_YYYYMMDD_HHMMSS
cuevex_backups.analytics_recordings_before_analytics_YYYYMMDD_HHMMSS
```

主要新增資料表：

```text
public.analytics_recordings
public.analytics_events
public.analytics_shot_events
public.analytics_practice_stats
public.analytics_sync_state
```

### 驗證

```sql
select table_schema, table_name
from information_schema.tables
where table_schema in ('public', 'cuevex_backups')
order by table_schema, table_name;

select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public'
  and table_name = 'mobile_users'
  and column_name = 'user_uuid';
```
