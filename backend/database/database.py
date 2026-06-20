"""
資料庫管理模組 - SQLite 資料庫操作

遵照 v1.5 技術指南:
- 使用 SQLite WAL 模式提升並發效能
- 結構化儲存錄影元資料、事件日誌、統計數據
- 提供完整的 CRUD 操作與事務管理
"""

import json
import sqlite3
import json
import os
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

from storage.supabase_analytics import SupabaseAnalyticsError, configured_supabase_analytics_repository


class Database:
    """SQLite 資料庫管理器"""
    
    def __init__(self, db_path: str = "./data/recordings.db"):
        """
        初始化資料庫連線
        
        Args:
            db_path: 資料庫檔案路徑
        """
        self.db_path = db_path
        
        # 確保資料目錄存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化資料庫
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        獲取資料庫連線（啟用 WAL 模式）
        
        Returns:
            資料庫連線
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 啟用字典式存取
        
        # 啟用 WAL 模式（Write-Ahead Logging）提升並發效能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")  # 啟用外鍵約束
        
        return conn
    
    @contextmanager
    def transaction(self):
        """
        事務管理上下文管理器
        
        使用範例:
            with db.transaction() as conn:
                conn.execute("INSERT ...")
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化資料庫結構（創建資料表）"""
        with self.transaction() as conn:
            # 1. recordings - 錄影主表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recordings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT UNIQUE NOT NULL,
                    game_type TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration_seconds REAL,
                    
                    -- 玩家資訊
                    player1_name TEXT,
                    player2_name TEXT,
                    winner TEXT,
                    
                    -- 比分
                    player1_score INTEGER DEFAULT 0,
                    player2_score INTEGER DEFAULT 0,
                    target_rounds INTEGER DEFAULT 0,
                    
                    -- 檔案資訊
                    video_path TEXT NOT NULL,
                    video_resolution TEXT,
                    video_fps INTEGER,
                    file_size_mb REAL,
                    
                    -- 元資料
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 創建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_game_type ON recordings(game_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_start_time ON recordings(start_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_player1 ON recordings(player1_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_player2 ON recordings(player2_name)")
            
            # 2. events - 事件日誌表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    
                    -- 事件數據 (JSON格式)
                    data TEXT,
                    
                    -- 球檯狀態快照
                    target_ball INTEGER,
                    potted_ball INTEGER,
                    first_contact INTEGER,
                    
                    FOREIGN KEY (game_id) REFERENCES recordings(game_id) ON DELETE CASCADE
                )
            """)
            
            # 創建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_game_id ON events(game_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS shot_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    player_name TEXT,
                    shot_index INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    mode TEXT,
                    target_ball INTEGER,
                    first_contact INTEGER,
                    potted_balls TEXT NOT NULL DEFAULT '[]',
                    pocket_result TEXT NOT NULL DEFAULT 'missed',
                    cue_ball_potted INTEGER DEFAULT 0,
                    is_foul INTEGER DEFAULT 0,
                    foul_reason TEXT,
                    impact_angle REAL,
                    ideal_angle REAL,
                    thickness_result TEXT NOT NULL DEFAULT 'unknown',
                    distance_bucket TEXT NOT NULL DEFAULT 'unknown',
                    difficulty_level TEXT NOT NULL DEFAULT 'unknown',
                    success_prob REAL,
                    position_success_prob REAL,
                    planned_cue_landing TEXT,
                    actual_cue_landing TEXT,
                    cue_landing_error_px REAL,
                    next_ball_quality TEXT,
                    raw_event_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shot_events_created ON shot_events(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shot_events_player ON shot_events(player_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shot_events_game ON shot_events(game_id)")
            
            # 3. practice_stats - 練習統計表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS practice_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL,
                    practice_type TEXT NOT NULL,
                    pattern TEXT,
                    
                    -- 統計數據
                    total_attempts INTEGER DEFAULT 0,
                    successful_attempts INTEGER DEFAULT 0,
                    success_rate REAL,
                    
                    -- 時間分析
                    avg_shot_time REAL,
                    
                    FOREIGN KEY (game_id) REFERENCES recordings(game_id) ON DELETE CASCADE
                )
            """)
            
            # 創建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_type ON practice_stats(practice_type)")
            
            # 4. players - 玩家表（可選，用於多用戶管理）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 統計數據
                    total_games INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    win_rate REAL
                )
            """)
            
            # 創建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_player_name ON players(name)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(entity_type, entity_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_sync_queue_status ON analytics_sync_queue(status, updated_at)")
    
            # 5. color_calibration_profiles - 顏色校正設定檔
            conn.execute("""
                CREATE TABLE IF NOT EXISTS color_calibration_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    name TEXT NOT NULL,
                    mapping_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(mode, name)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_color_profile_mode ON color_calibration_profiles(mode)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    locale TEXT DEFAULT 'zh-TW',
                    source TEXT,
                    context_signature TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_messages_session ON coach_messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_messages_created ON coach_messages(created_at)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    analysis_type TEXT NOT NULL,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    context_signature TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_analysis_session ON coach_analysis_results(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_analysis_type ON coach_analysis_results(analysis_type)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS community_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    author_name TEXT NOT NULL,
                    badge TEXT NOT NULL DEFAULT '玩家',
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    image_urls TEXT NOT NULL DEFAULT '[]',
                    image_transforms TEXT NOT NULL DEFAULT '[]',
                    preview_type TEXT NOT NULL DEFAULT 'pool-table',
                    recording_id TEXT,
                    tone TEXT NOT NULL DEFAULT 'aqua',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recording_id) REFERENCES recordings(game_id) ON DELETE SET NULL
                )
            """)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(community_posts)").fetchall()
            }
            if "image_urls" not in columns:
                conn.execute("ALTER TABLE community_posts ADD COLUMN image_urls TEXT NOT NULL DEFAULT '[]'")
            if "image_transforms" not in columns:
                conn.execute("ALTER TABLE community_posts ADD COLUMN image_transforms TEXT NOT NULL DEFAULT '[]'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_posts_created ON community_posts(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_posts_user ON community_posts(user_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_follows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    follower_user_id INTEGER NOT NULL,
                    following_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(follower_user_id, following_user_id),
                    CHECK(follower_user_id != following_user_id),
                    FOREIGN KEY (follower_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (following_user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_follows_follower ON user_follows(follower_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_follows_following ON user_follows(following_user_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blocker_user_id INTEGER NOT NULL,
                    blocked_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(blocker_user_id, blocked_user_id),
                    CHECK(blocker_user_id != blocked_user_id),
                    FOREIGN KEY (blocker_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (blocked_user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_blocks_blocker ON user_blocks(blocker_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_blocks_blocked ON user_blocks(blocked_user_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS community_post_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(post_id, user_id),
                    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_reactions_post ON community_post_reactions(post_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS community_post_bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(post_id, user_id),
                    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_bookmarks_post ON community_post_bookmarks(post_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_bookmarks_user ON community_post_bookmarks(user_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS community_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    user_id INTEGER,
                    author_name TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_comments_post ON community_comments(post_id, created_at)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS community_comment_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(comment_id, user_id),
                    FOREIGN KEY (comment_id) REFERENCES community_comments(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_community_comment_reactions_comment ON community_comment_reactions(comment_id)")
            self._seed_default_community_posts(conn)

    def _seed_default_community_posts(self, conn: sqlite3.Connection) -> None:
        """保留 v0 社群頁的初始內容，讓新資料庫啟動後不是空白牆。"""
        row = conn.execute("SELECT COUNT(*) AS total FROM community_posts").fetchone()
        if row and int(row["total"]) > 0:
            return

        posts = [
            (
                "CueVex Official",
                "官方",
                "AI 路線推薦 2.0 已上線",
                "新版路線引擎整合母球控制、進攻角度與安全球策略，讓每一次選擇更清楚。",
                "pool-table",
                "aqua",
            ),
            (
                "Tai the Shooter",
                "進階玩家",
                "這顆薄球你會攻還是守？",
                "母球貼庫，9 號球角度很薄。用 CueVex 分析後，安全球與翻袋成功率差距只有 8%。",
                "pool-table-alt",
                "amber",
            ),
            (
                "Coach Lin",
                "教練",
                "穩定出桿的三個關鍵",
                "橋手、節奏與延伸方向是最容易被忽略的細節。姿態分析可以快速抓出偏移點。",
                "pose-analysis",
                "blue",
            ),
            (
                "9Ball Soul",
                "玩家",
                "今天的開球練習紀錄",
                "連續 30 次開球，最高進球率 64%，但母球控制還需要調整。",
                "stats",
                "rose",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO community_posts (
                author_name, badge, title, body, preview_type, tone, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            posts,
        )

    def _record_analytics_sync_failure(
        self,
        entity_type: str,
        entity_key: str,
        payload: Dict[str, Any],
        error_message: str,
    ) -> None:
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO analytics_sync_queue (
                        entity_type, entity_key, payload_json, status, error_message, updated_at
                    ) VALUES (?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(entity_type, entity_key) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        status = 'pending',
                        error_message = excluded.error_message,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        entity_type,
                        entity_key,
                        json.dumps(payload, ensure_ascii=False),
                        error_message[:1000],
                    ),
                )
        except Exception as exc:
            print(f"WARNING analytics sync queue write failed: {exc}")

    def _sync_analytics_recording(self, recording_data: Dict[str, Any]) -> None:
        repo = configured_supabase_analytics_repository()
        if repo is None:
            return
        key = str(recording_data.get("game_id") or "")
        try:
            repo.upsert_recording(recording_data)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics recording sync failed; queued locally: {exc}")
            self._record_analytics_sync_failure("recording", key, recording_data, str(exc))

    def _sync_analytics_recording_delete(self, game_id: str) -> None:
        repo = configured_supabase_analytics_repository()
        if repo is None:
            return
        try:
            repo.delete_recording(game_id)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics recording delete failed; queued locally: {exc}")
            self._record_analytics_sync_failure("recording_delete", game_id, {"game_id": game_id}, str(exc))

    def _sync_analytics_event(self, event_data: Dict[str, Any]) -> None:
        repo = configured_supabase_analytics_repository()
        if repo is None:
            return
        key = f"{event_data.get('game_id') or 'unknown'}:{event_data.get('timestamp') or datetime.now().isoformat()}:{event_data.get('event_type') or ''}"
        try:
            repo.upsert_event(event_data)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics event sync failed; queued locally: {exc}")
            self._record_analytics_sync_failure("event", key, event_data, str(exc))

    def _sync_analytics_shot_event(self, event_data: Dict[str, Any]) -> None:
        repo = configured_supabase_analytics_repository()
        if repo is None:
            return
        key = f"{event_data.get('game_id') or 'live'}:{event_data.get('shot_index') or datetime.now().isoformat()}"
        try:
            repo.upsert_shot_event(event_data)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics shot event sync failed; queued locally: {exc}")
            self._record_analytics_sync_failure("shot_event", key, event_data, str(exc))

    def _sync_analytics_practice_stats(self, stats_data: Dict[str, Any]) -> None:
        repo = configured_supabase_analytics_repository()
        if repo is None:
            return
        key = f"{stats_data.get('game_id') or 'unknown'}:{stats_data.get('practice_type') or ''}:{stats_data.get('pattern') or ''}"
        try:
            repo.upsert_practice_stats(stats_data)
        except SupabaseAnalyticsError as exc:
            print(f"WARNING Supabase analytics practice stats sync failed; queued locally: {exc}")
            self._record_analytics_sync_failure("practice_stats", key, stats_data, str(exc))

    def get_analytics_sync_queue_status(self) -> Dict[str, Any]:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                SELECT status, entity_type, COUNT(*) AS total
                FROM analytics_sync_queue
                GROUP BY status, entity_type
                ORDER BY status, entity_type
                """
            )
            groups = [dict(row) for row in cursor.fetchall()]
            cursor = conn.execute(
                """
                SELECT id, entity_type, entity_key, status, error_message, updated_at
                FROM analytics_sync_queue
                ORDER BY updated_at DESC, id DESC
                LIMIT 20
                """
            )
            recent = [dict(row) for row in cursor.fetchall()]
            return {"groups": groups, "recent": recent}

    def retry_analytics_sync_queue(self, limit: int = 50) -> Dict[str, Any]:
        repo = configured_supabase_analytics_repository()
        if repo is None:
            return {"ok": False, "error": "Supabase analytics repository is not configured.", "processed": 0, "synced": 0, "failed": 0}

        with self.transaction() as conn:
            cursor = conn.execute(
                """
                SELECT id, entity_type, entity_key, payload_json
                FROM analytics_sync_queue
                WHERE status IN ('pending', 'failed')
                ORDER BY updated_at ASC, id ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        processed = 0
        synced = 0
        failed = 0
        failures: List[Dict[str, Any]] = []
        for row in rows:
            processed += 1
            queue_id = int(row["id"])
            entity_type = str(row["entity_type"])
            entity_key = str(row["entity_key"])
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
                if entity_type == "recording":
                    repo.upsert_recording(payload)
                elif entity_type == "recording_delete":
                    repo.delete_recording(str(payload.get("game_id") or entity_key))
                elif entity_type == "event":
                    repo.upsert_event(payload)
                elif entity_type == "shot_event":
                    repo.upsert_shot_event(payload)
                elif entity_type == "practice_stats":
                    repo.upsert_practice_stats(payload)
                else:
                    raise SupabaseAnalyticsError(f"Unsupported analytics sync entity_type: {entity_type}")
                with self.transaction() as conn:
                    conn.execute(
                        """
                        UPDATE analytics_sync_queue
                        SET status = 'synced', error_message = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (queue_id,),
                    )
                synced += 1
            except Exception as exc:
                failed += 1
                message = str(exc)[:1000]
                failures.append({"id": queue_id, "entity_type": entity_type, "entity_key": entity_key, "error": message})
                with self.transaction() as conn:
                    conn.execute(
                        """
                        UPDATE analytics_sync_queue
                        SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (message, queue_id),
                    )
        return {
            "ok": failed == 0,
            "processed": processed,
            "synced": synced,
            "failed": failed,
            "failures": failures[:10],
        }
    # ==================== Recordings CRUD ====================
    
    def insert_recording(self, recording_data: Dict[str, Any]) -> Optional[int]:
        """
        插入錄影記錄
        
        Args:
            recording_data: 錄影資料字典
        
        Returns:
            插入的記錄 ID
        """
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO recordings (
                    game_id, game_type, start_time, end_time, duration_seconds,
                    player1_name, player2_name, winner,
                    player1_score, player2_score, target_rounds,
                    video_path, video_resolution, video_fps, file_size_mb
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recording_data.get("game_id"),
                recording_data.get("game_type"),
                recording_data.get("start_time"),
                recording_data.get("end_time"),
                recording_data.get("duration_seconds"),
                recording_data.get("player1_name"),
                recording_data.get("player2_name"),
                recording_data.get("winner"),
                recording_data.get("player1_score", 0),
                recording_data.get("player2_score", 0),
                recording_data.get("target_rounds", 0),
                recording_data.get("video_path"),
                recording_data.get("video_resolution"),
                recording_data.get("video_fps"),
                recording_data.get("file_size_mb")
            ))
            row_id = cursor.lastrowid
        self._sync_analytics_recording(recording_data)
        return row_id
    
    def get_recording(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取單一錄影記錄
        
        Args:
            game_id: 遊戲 ID
        
        Returns:
            錄影資料字典，若不存在則返回 None
        """
        with self.transaction() as conn:
            cursor = conn.execute(
                "SELECT * FROM recordings WHERE game_id = ?",
                (game_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_recordings(
        self,
        game_type: Optional[str] = None,
        game_types: Optional[List[str]] = None,
        player: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        查詢錄影列表（支援篩選、分頁）
        
        Args:
            game_type: 單一遊戲類型篩選
            game_types: 多遊戲類型篩選
            player: 玩家名稱篩選
            start_date: 開始日期篩選
            end_date: 結束日期篩選
            limit: 每頁筆數
            offset: 偏移量
        
        Returns:
            (錄影列表, 總筆數)
        """
        with self.transaction() as conn:
            # 構建查詢條件
            conditions = []
            params = []
            
            if game_types:
                placeholders = ", ".join(["?" for _ in game_types])
                conditions.append(f"game_type IN ({placeholders})")
                params.extend(game_types)
            elif game_type:
                conditions.append("game_type = ?")
                params.append(game_type)
            
            if player:
                conditions.append("(player1_name = ? OR player2_name = ?)")
                params.extend([player, player])
            
            if start_date:
                conditions.append("start_time >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("start_time <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 查詢總筆數
            count_cursor = conn.execute(
                f"SELECT COUNT(*) FROM recordings WHERE {where_clause}",
                params
            )
            total = count_cursor.fetchone()[0]
            
            # 查詢資料
            cursor = conn.execute(
                f"""
                SELECT * FROM recordings 
                WHERE {where_clause}
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset]
            )
            
            recordings = [dict(row) for row in cursor.fetchall()]
            return recordings, total

    def update_recording(self, game_id: str, update_data: Dict[str, Any]) -> bool:
        """
        更新錄影記錄
        
        Args:
            game_id: 遊戲 ID
            update_data: 更新資料字典
        
        Returns:
            是否更新成功
        """
        with self.transaction() as conn:
            # 構建 SET 子句
            set_fields = []
            params = []
            
            for key, value in update_data.items():
                if key != "game_id":  # 不允許更新 game_id
                    set_fields.append(f"{key} = ?")
                    params.append(value)
            
            if not set_fields:
                return False
            
            # 添加 updated_at
            set_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(game_id)
            
            cursor = conn.execute(
                f"UPDATE recordings SET {', '.join(set_fields)} WHERE game_id = ?",
                params
            )

            updated = cursor.rowcount > 0

        if updated:
            current = self.get_recording(game_id)
            if current:
                self._sync_analytics_recording(current)
        return updated
    
    def delete_recording(self, game_id: str) -> bool:
        """
        刪除錄影記錄（級聯刪除相關事件和統計）
        
        Args:
            game_id: 遊戲 ID
        
        Returns:
            是否刪除成功
        """
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM recordings WHERE game_id = ?",
                (game_id,)
            )
            deleted = cursor.rowcount > 0
        if deleted:
            self._sync_analytics_recording_delete(game_id)
        return deleted
    
    # ==================== Events CRUD ====================
    
    def insert_event(self, event_data: Dict[str, Any]) -> Optional[int]:
        """
        插入事件記錄
        
        Args:
            event_data: 事件資料字典
        
        Returns:
            插入的記錄 ID
        """
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO events (
                    game_id, timestamp, event_type, data,
                    target_ball, potted_ball, first_contact
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event_data.get("game_id"),
                event_data.get("timestamp"),
                event_data.get("event_type"),
                json.dumps(event_data.get("data", {}), ensure_ascii=False),
                event_data.get("target_ball"),
                event_data.get("potted_ball"),
                event_data.get("first_contact")
            ))
            row_id = cursor.lastrowid
        self._sync_analytics_event({**event_data, "local_event_id": row_id})
        return row_id
    
    def get_events(
        self,
        game_id: str,
        event_type: Optional[str] = None,
        from_time: Optional[float] = None,
        to_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        獲取事件列表
        
        Args:
            game_id: 遊戲 ID
            event_type: 事件類型篩選
            from_time: 開始時間篩選
            to_time: 結束時間篩選
        
        Returns:
            事件列表
        """
        with self.transaction() as conn:
            conditions = ["game_id = ?"]
            params: List[Any] = [game_id]
            
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            
            if from_time is not None:
                conditions.append("timestamp >= ?")
                params.append(from_time)
            
            if to_time is not None:
                conditions.append("timestamp <= ?")
                params.append(to_time)
            
            where_clause = " AND ".join(conditions)
            
            cursor = conn.execute(
                f"SELECT * FROM events WHERE {where_clause} ORDER BY timestamp ASC",
                params
            )
            
            events = []
            for row in cursor.fetchall():
                event = dict(row)
                # 解析 JSON 資料
                if event.get("data"):
                    try:
                        event["data"] = json.loads(event["data"])
                    except json.JSONDecodeError:
                        event["data"] = {}
                events.append(event)
            
            return events

    # ==================== Shot Analytics CRUD ====================

    def insert_shot_event(self, event_data: Dict[str, Any]) -> Optional[int]:
        """保存單次出桿事件，用於數據頁統計。"""
        event_payload = dict(event_data)
        game_id = event_payload.get("game_id")
        if game_id and self.get_recording(str(game_id)) is None:
            raw_event = event_payload.get("raw_event_json")
            raw_event = raw_event if isinstance(raw_event, dict) else {}
            raw_event.setdefault("unresolved_recording_game_id", str(game_id))
            event_payload["raw_event_json"] = raw_event
            event_payload["game_id"] = None
            print(f"WARNING shot analytics recording not found; saved event without game_id: {game_id}")

        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO shot_events (
                    game_id, player_name, shot_index, created_at, mode,
                    target_ball, first_contact, potted_balls, pocket_result,
                    cue_ball_potted, is_foul, foul_reason, impact_angle,
                    ideal_angle, thickness_result, distance_bucket,
                    difficulty_level, success_prob, position_success_prob,
                    planned_cue_landing, actual_cue_landing,
                    cue_landing_error_px, next_ball_quality, raw_event_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_payload.get("game_id"),
                event_payload.get("player_name"),
                int(event_payload.get("shot_index") or 0),
                event_payload.get("created_at") or datetime.now().isoformat(),
                event_payload.get("mode"),
                event_payload.get("target_ball"),
                event_payload.get("first_contact"),
                json.dumps(event_payload.get("potted_balls") or [], ensure_ascii=False),
                event_payload.get("pocket_result") or "missed",
                1 if event_payload.get("cue_ball_potted") else 0,
                1 if event_payload.get("is_foul") else 0,
                event_payload.get("foul_reason"),
                event_payload.get("impact_angle"),
                event_payload.get("ideal_angle"),
                event_payload.get("thickness_result") or "unknown",
                event_payload.get("distance_bucket") or "unknown",
                event_payload.get("difficulty_level") or "unknown",
                event_payload.get("success_prob"),
                event_payload.get("position_success_prob"),
                json.dumps(event_payload.get("planned_cue_landing"), ensure_ascii=False),
                json.dumps(event_payload.get("actual_cue_landing"), ensure_ascii=False),
                event_payload.get("cue_landing_error_px"),
                event_payload.get("next_ball_quality"),
                json.dumps(event_payload.get("raw_event_json") or {}, ensure_ascii=False),
            ))
            row_id = cursor.lastrowid
        self._sync_analytics_shot_event(event_payload)
        return row_id

    def get_shot_events(
        self,
        player_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查詢出桿事件並還原 JSON 欄位。"""
        with self.transaction() as conn:
            conditions: List[str] = []
            params: List[Any] = []
            if player_name:
                conditions.append("player_name = ?")
                params.append(player_name)
            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            cursor = conn.execute(
                f"SELECT * FROM shot_events {where_clause} ORDER BY created_at ASC, id ASC",
                params,
            )
            rows = []
            for row in cursor.fetchall():
                item = dict(row)
                for key, fallback in (
                    ("potted_balls", []),
                    ("planned_cue_landing", None),
                    ("actual_cue_landing", None),
                    ("raw_event_json", {}),
                ):
                    try:
                        item[key] = json.loads(item.get(key) or "null")
                        if item[key] is None:
                            item[key] = fallback
                    except (TypeError, json.JSONDecodeError):
                        item[key] = fallback
                item["cue_ball_potted"] = bool(item.get("cue_ball_potted"))
                item["is_foul"] = bool(item.get("is_foul"))
                rows.append(item)
            return rows

    def get_analytics_period(self, range_name: str) -> Dict[str, str]:
        now = datetime.now()
        normalized = range_name if range_name in {"today", "week", "month", "year"} else "today"
        if normalized == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif normalized == "week":
            start = now - timedelta(days=7)
        elif normalized == "month":
            start = now - timedelta(days=30)
        else:
            start = now - timedelta(days=365)
        return {
            "range": normalized,
            "start": start.isoformat(),
            "end": now.isoformat(),
        }

    def get_analytics_overview(self, player_name: Optional[str], range_name: str) -> Dict[str, Any]:
        period = self.get_analytics_period(range_name)
        events = self.get_shot_events(player_name, period["start"], period["end"])
        summary = self._summarize_shot_events(events)
        return {
            "period": period,
            "player": player_name,
            "has_data": bool(events),
            **summary,
        }

    def get_analytics_offense(self, player_name: Optional[str], range_name: str) -> Dict[str, Any]:
        period = self.get_analytics_period(range_name)
        events = self.get_shot_events(player_name, period["start"], period["end"])
        return {
            "period": period,
            "player": player_name,
            "has_data": bool(events),
            "distance_buckets": self._bucket_rates(events, "distance_bucket", ["near", "mid", "far"]),
            "difficulty_buckets": self._bucket_rates(events, "difficulty_level", ["easy", "medium", "hard"]),
            "thickness": self._count_values(events, "thickness_result", ["too_thick", "too_thin", "on_line", "unknown"]),
            "mistakes": self._mistake_distribution(events),
        }

    def get_analytics_trends(self, player_name: Optional[str], bucket: str) -> Dict[str, Any]:
        normalized = bucket if bucket in {"day", "week", "month", "year"} else "day"
        lookback = {"day": 30, "week": 84, "month": 365, "year": 365 * 3}[normalized]
        end = datetime.now()
        start = end - timedelta(days=lookback)
        events = self.get_shot_events(player_name, start.isoformat(), end.isoformat())
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for event in events:
            label = self._trend_label(event.get("created_at"), normalized)
            grouped.setdefault(label, []).append(event)
        points = []
        for label in sorted(grouped.keys()):
            summary = self._summarize_shot_events(grouped[label])
            points.append({
                "label": label,
                "performance_score": summary["performance_score"],
                "pocket_rate": summary["pocket_rate"],
                "mistake_rate": summary["mistake_rate"],
                "cue_control_score": summary["cue_control_score"],
                "shot_count": summary["today_shots"],
                "confidence": summary["confidence"],
            })
        return {
            "bucket": normalized,
            "player": player_name,
            "has_data": bool(events),
            "points": points,
        }

    def _summarize_shot_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(events)
        made = sum(1 for event in events if self._is_made(event))
        mistakes = self._mistake_distribution(events)
        scratches = sum(1 for event in events if event.get("cue_ball_potted"))
        best_streak = self._best_made_streak(events)
        pocket_rate = made / total if total else None
        mistake_count = sum(item["count"] for item in mistakes)
        mistake_rate = mistake_count / total if total else None
        hard_events = [event for event in events if event.get("difficulty_level") == "hard"]
        hard_success_rate = (
            sum(1 for event in hard_events if self._is_made(event)) / len(hard_events)
            if hard_events else None
        )
        position_values = [
            float(event["position_success_prob"])
            for event in events
            if event.get("position_success_prob") is not None
        ]
        cue_control_rate = (
            sum(1 for value in position_values if value >= 0.5) / len(position_values)
            if position_values else None
        )
        stability = self._stability_score(events)
        score, confidence = self._performance_score(
            pocket_rate=pocket_rate,
            cue_control_rate=cue_control_rate,
            mistake_rate=mistake_rate,
            hard_success_rate=hard_success_rate,
            stability=stability,
        )
        top_mistake = mistakes[0] if mistakes else {"type": "none", "label": "目前沒有明顯失誤", "count": 0}
        recommendation = self._recommendation(events, top_mistake)
        return {
            "today_shots": total,
            "performance_score": score,
            "pocket_rate": self._round_rate(pocket_rate),
            "mistake_rate": self._round_rate(mistake_rate),
            "most_common_mistake": top_mistake,
            "ai_advice": recommendation["advice"],
            "recommended_practice": recommendation["practice"],
            "best_streak": best_streak,
            "scratch_count": scratches,
            "cue_control_rate": self._round_rate(cue_control_rate),
            "cue_control_score": round((cue_control_rate or 0.0) * 100, 1) if cue_control_rate is not None else None,
            "average_cue_landing_error_px": self._average_landing_error(events),
            "next_ball_good_rate": self._next_ball_good_rate(events),
            "training_completion_rate": self._round_rate(total / 50 if total else 0.0),
            "confidence": confidence,
            "data_sources": ["shot_events"],
        }

    def _performance_score(
        self,
        *,
        pocket_rate: Optional[float],
        cue_control_rate: Optional[float],
        mistake_rate: Optional[float],
        hard_success_rate: Optional[float],
        stability: Optional[float],
    ) -> tuple[Optional[int], str]:
        metrics = [
            (pocket_rate, 35.0),
            (cue_control_rate, 25.0),
            (1.0 - mistake_rate if mistake_rate is not None else None, 20.0),
            (hard_success_rate, 10.0),
            (stability, 10.0),
        ]
        available = [(value, weight) for value, weight in metrics if value is not None]
        if not available:
            return None, "empty"
        weight_total = sum(weight for _, weight in available)
        score = sum(max(0.0, min(1.0, float(value))) * weight for value, weight in available) / weight_total
        confidence = "complete" if len(available) == len(metrics) else "partial"
        return int(round(score * 100)), confidence

    def _bucket_rates(self, events: List[Dict[str, Any]], key: str, buckets: List[str]) -> List[Dict[str, Any]]:
        result = []
        for bucket in buckets:
            scoped = [event for event in events if event.get(key) == bucket]
            made = sum(1 for event in scoped if self._is_made(event))
            result.append({
                "bucket": bucket,
                "shots": len(scoped),
                "made": made,
                "rate": self._round_rate(made / len(scoped) if scoped else None),
            })
        return result

    def _count_values(self, events: List[Dict[str, Any]], key: str, values: List[str]) -> List[Dict[str, Any]]:
        return [
            {"type": value, "count": sum(1 for event in events if event.get(key) == value)}
            for value in values
        ]

    def _mistake_distribution(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        labels = {
            "scratch": "洗袋",
            "foul": "犯規",
            "too_thick": "打太厚",
            "too_thin": "打太薄",
            "missed": "未進",
        }
        counts = {key: 0 for key in labels}
        for event in events:
            if event.get("cue_ball_potted"):
                counts["scratch"] += 1
            elif event.get("is_foul"):
                counts["foul"] += 1
            elif event.get("thickness_result") in {"too_thick", "too_thin"}:
                counts[str(event.get("thickness_result"))] += 1
            elif not self._is_made(event):
                counts["missed"] += 1
        return [
            {"type": key, "label": labels[key], "count": value}
            for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
            if value > 0
        ]

    def _recommendation(self, events: List[Dict[str, Any]], top_mistake: Dict[str, Any]) -> Dict[str, str]:
        if not events:
            return {"practice": "累積 3 桿以上資料", "advice": "目前還沒有真實出桿資料，先完成幾次練習後再產生建議。"}
        distance_rates = self._bucket_rates(events, "distance_bucket", ["near", "mid", "far"])
        worst_distance = min(
            [item for item in distance_rates if item["shots"] > 0 and item["rate"] is not None],
            key=lambda item: item["rate"],
            default=None,
        )
        if top_mistake.get("type") == "scratch":
            return {"practice": "母球控制練習", "advice": "洗袋比例偏高，優先練停點與母球速度控制。"}
        if top_mistake.get("type") in {"too_thick", "too_thin"}:
            return {"practice": "薄球 / 角度球練習", "advice": f"{top_mistake.get('label')}是目前最常見失誤，建議用固定角度球重複校正瞄準線。"}
        if worst_distance and worst_distance["bucket"] == "far":
            return {"practice": "遠台準度練習", "advice": "遠距離進球率偏低，先降低力道波動並固定出桿節奏。"}
        if worst_distance and worst_distance["bucket"] == "near":
            return {"practice": "短距離直球練習", "advice": "近距離球仍有失誤，建議先回到直球與中心點控制。"}
        hard_rates = self._bucket_rates(events, "difficulty_level", ["hard"])
        if hard_rates and hard_rates[0]["shots"] > 0 and (hard_rates[0]["rate"] or 0) < 0.45:
            return {"practice": "困難球型拆解", "advice": "困難球成功率偏低，建議先把球型拆成單顆角度球練習。"}
        return {"practice": "綜合穩定度練習", "advice": "目前沒有單一明顯弱項，建議維持固定節奏並累積更多資料。"}

    def _is_made(self, event: Dict[str, Any]) -> bool:
        return event.get("pocket_result") == "made" or bool(event.get("potted_balls"))

    def _best_made_streak(self, events: List[Dict[str, Any]]) -> int:
        best = 0
        current = 0
        for event in events:
            if self._is_made(event):
                current += 1
                best = max(best, current)
            else:
                current = 0
        return best

    def _stability_score(self, events: List[Dict[str, Any]]) -> Optional[float]:
        if len(events) < 3:
            return None
        made_values = [1.0 if self._is_made(event) else 0.0 for event in events]
        avg = sum(made_values) / len(made_values)
        variance = sum((value - avg) ** 2 for value in made_values) / len(made_values)
        return max(0.0, min(1.0, 1.0 - variance * 2.0))

    def _average_landing_error(self, events: List[Dict[str, Any]]) -> Optional[float]:
        values = [
            float(event["cue_landing_error_px"])
            for event in events
            if event.get("cue_landing_error_px") is not None
        ]
        return round(sum(values) / len(values), 1) if values else None

    def _next_ball_good_rate(self, events: List[Dict[str, Any]]) -> Optional[float]:
        values = [event.get("next_ball_quality") for event in events if event.get("next_ball_quality")]
        if not values:
            return None
        good = sum(1 for value in values if value == "good")
        return self._round_rate(good / len(values))

    def _round_rate(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return round(max(0.0, min(1.0, float(value))), 4)

    def _trend_label(self, created_at: Any, bucket: str) -> str:
        try:
            dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now()
        if bucket == "day":
            return dt.strftime("%Y-%m-%d")
        if bucket == "week":
            year, week, _ = dt.isocalendar()
            return f"{year}-W{week:02d}"
        if bucket == "month":
            return dt.strftime("%Y-%m")
        return dt.strftime("%Y")

    # ==================== AI Coach Persistence ====================

    def insert_coach_message(self, message_data: Dict[str, Any]) -> Optional[int]:
        """保存 AI Coach 對話訊息。"""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO coach_messages (
                    session_id, role, message, locale, source,
                    context_signature, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                message_data.get("session_id"),
                message_data.get("role"),
                message_data.get("message"),
                message_data.get("locale", "zh-TW"),
                message_data.get("source"),
                message_data.get("context_signature"),
                json.dumps(message_data.get("metadata", {}), ensure_ascii=False),
            ))
            return cursor.lastrowid

    def insert_coach_analysis_result(self, analysis_data: Dict[str, Any]) -> Optional[int]:
        """保存 AI Coach 分析結果。"""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO coach_analysis_results (
                    session_id, analysis_type, result_json,
                    context_signature, source
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                analysis_data.get("session_id"),
                analysis_data.get("analysis_type", "chat"),
                json.dumps(analysis_data.get("result", {}), ensure_ascii=False),
                analysis_data.get("context_signature"),
                analysis_data.get("source"),
            ))
            return cursor.lastrowid

    # ==================== Community Persistence ====================

    def get_community_posts(
        self,
        tab: str = "all",
        sort: str = "latest",
        limit: int = 20,
        offset: int = 0,
        viewer_user_id: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """查詢社群貼文列表，包含按讚、收藏與留言彙總。"""
        where_clauses = []
        params: List[Any] = []
        if tab == "following":
            if viewer_user_id is None:
                return [], 0
            where_clauses.append("p.user_id = ?")
            params.append(viewer_user_id)
        elif tab not in ("all", "explore"):
            raise ValueError("Invalid tab")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_sql = {
            "latest": "p.created_at DESC, p.id DESC",
            "popular": "likes DESC, p.created_at DESC, p.id DESC",
            "comments": "comments DESC, p.created_at DESC, p.id DESC",
        }.get(sort)
        if order_sql is None:
            raise ValueError("Invalid sort")

        viewer_id = viewer_user_id or 0
        with self.transaction() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS total FROM community_posts p {where_sql}",
                params,
            ).fetchone()
            cursor = conn.execute(
                f"""
                SELECT
                    p.id, p.user_id, COALESCE(u.username, p.author_name) AS author_name, p.badge, p.title, p.body, p.image_urls, p.image_transforms,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    p.preview_type, p.recording_id, p.tone, p.created_at, p.updated_at,
                    COUNT(DISTINCT r.user_id) AS likes,
                    COUNT(DISTINCT c.id) AS comments,
                    CASE WHEN lr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me,
                    CASE WHEN bm.user_id IS NULL THEN 0 ELSE 1 END AS bookmarked_by_me
                FROM community_posts p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN community_post_reactions r ON r.post_id = p.id
                LEFT JOIN community_comments c ON c.post_id = p.id
                LEFT JOIN community_post_reactions lr
                    ON lr.post_id = p.id AND lr.user_id = ?
                LEFT JOIN community_post_bookmarks bm
                    ON bm.post_id = p.id AND bm.user_id = ?
                {where_sql}
                GROUP BY p.id
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                [viewer_id, viewer_id, *params, limit, offset],
            )
            posts = [self._community_post_from_row(row) for row in cursor.fetchall()]
            return posts, int(total_row["total"] if total_row else 0)

    def count_community_posts_for_user(self, user_id: int) -> int:
        """Count community posts authored by a user."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM community_posts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return int(row["total"] if row else 0)

    def get_community_posts_for_user(
        self,
        author_user_id: int,
        viewer_user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return public community posts authored by a specific user."""
        viewer_id = viewer_user_id or 0
        with self.transaction() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) AS total FROM community_posts WHERE user_id = ?",
                (author_user_id,),
            ).fetchone()
            cursor = conn.execute(
                """
                SELECT
                    p.id, p.user_id, COALESCE(u.username, p.author_name) AS author_name, p.badge, p.title, p.body, p.image_urls, p.image_transforms,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    p.preview_type, p.recording_id, p.tone, p.created_at, p.updated_at,
                    COUNT(DISTINCT r.user_id) AS likes,
                    COUNT(DISTINCT c.id) AS comments,
                    CASE WHEN lr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me,
                    CASE WHEN bm.user_id IS NULL THEN 0 ELSE 1 END AS bookmarked_by_me
                FROM community_posts p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN community_post_reactions r ON r.post_id = p.id
                LEFT JOIN community_comments c ON c.post_id = p.id
                LEFT JOIN community_post_reactions lr
                    ON lr.post_id = p.id AND lr.user_id = ?
                LEFT JOIN community_post_bookmarks bm
                    ON bm.post_id = p.id AND bm.user_id = ?
                WHERE p.user_id = ?
                GROUP BY p.id
                ORDER BY p.created_at DESC, p.id DESC
                LIMIT ? OFFSET ?
                """,
                (viewer_id, viewer_id, author_user_id, limit, offset),
            )
            posts = [self._community_post_from_row(row) for row in cursor.fetchall()]
            return posts, int(total_row["total"] if total_row else 0)

    def get_bookmarked_community_posts(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return posts bookmarked by the user, ordered by newest bookmark first."""
        with self.transaction() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) AS total FROM community_post_bookmarks WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            cursor = conn.execute(
                """
                SELECT
                    p.id, p.user_id, COALESCE(u.username, p.author_name) AS author_name, p.badge, p.title, p.body, p.image_urls, p.image_transforms,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    p.preview_type, p.recording_id, p.tone, p.created_at, p.updated_at,
                    COUNT(DISTINCT r.user_id) AS likes,
                    COUNT(DISTINCT c.id) AS comments,
                    CASE WHEN lr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me,
                    1 AS bookmarked_by_me,
                    MAX(bm.created_at) AS bookmarked_at
                FROM community_post_bookmarks bm
                INNER JOIN community_posts p ON p.id = bm.post_id
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN community_post_reactions r ON r.post_id = p.id
                LEFT JOIN community_comments c ON c.post_id = p.id
                LEFT JOIN community_post_reactions lr
                    ON lr.post_id = p.id AND lr.user_id = ?
                WHERE bm.user_id = ?
                GROUP BY p.id
                ORDER BY bookmarked_at DESC, p.id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, user_id, limit, offset),
            )
            posts = [self._community_post_from_row(row) for row in cursor.fetchall()]
            return posts, int(total_row["total"] if total_row else 0)

    def follow_user(self, follower_user_id: int, following_user_id: int) -> Dict[str, Any]:
        """Create a one-way follow relationship."""
        if follower_user_id == following_user_id:
            raise ValueError("Cannot follow yourself")
        with self.transaction() as conn:
            target = conn.execute("SELECT id FROM users WHERE id = ?", (following_user_id,)).fetchone()
            if target is None:
                raise KeyError("User not found")
            conn.execute(
                """
                INSERT OR IGNORE INTO user_follows (follower_user_id, following_user_id, created_at)
                VALUES (?, ?, datetime('now'))
                """,
                (follower_user_id, following_user_id),
            )
        return {
            "follower_user_id": follower_user_id,
            "following_user_id": following_user_id,
            "is_following": True,
        }

    def unfollow_user(self, follower_user_id: int, following_user_id: int) -> Dict[str, Any]:
        """Remove a one-way follow relationship."""
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM user_follows WHERE follower_user_id = ? AND following_user_id = ?",
                (follower_user_id, following_user_id),
            )
        return {
            "follower_user_id": follower_user_id,
            "following_user_id": following_user_id,
            "is_following": False,
        }

    def get_follow_counts(self, user_id: int) -> Dict[str, int]:
        """Return follower and following counts for a user."""
        with self.transaction() as conn:
            followers = conn.execute(
                "SELECT COUNT(*) AS total FROM user_follows WHERE following_user_id = ?",
                (user_id,),
            ).fetchone()
            following = conn.execute(
                "SELECT COUNT(*) AS total FROM user_follows WHERE follower_user_id = ?",
                (user_id,),
            ).fetchone()
            return {
                "followers_count": int(followers["total"] if followers else 0),
                "following_count": int(following["total"] if following else 0),
            }

    def list_follow_refs(self, user_id: int, kind: str, limit: int = 50, offset: int = 0) -> tuple[list[Dict[str, Any]], int]:
        """Return follower or following user refs ordered by newest follow first."""
        if kind not in {"followers", "following"}:
            raise ValueError("Invalid follow list kind")
        id_column = "follower_user_id" if kind == "followers" else "following_user_id"
        filter_column = "following_user_id" if kind == "followers" else "follower_user_id"
        with self.transaction() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS total FROM user_follows WHERE {filter_column} = ?",
                (user_id,),
            ).fetchone()
            rows = conn.execute(
                f"""
                SELECT {id_column} AS user_id, created_at AS followed_at
                FROM user_follows
                WHERE {filter_column} = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
            refs = [{"user_id": int(row["user_id"]), "followed_at": str(row["followed_at"] or "")} for row in rows]
            return refs, int(total_row["total"] if total_row else 0)

    def is_following_user(self, follower_user_id: int, following_user_id: int) -> bool:
        """Return whether follower_user_id follows following_user_id."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT 1 FROM user_follows WHERE follower_user_id = ? AND following_user_id = ?",
                (follower_user_id, following_user_id),
            ).fetchone()
            return row is not None

    def block_user(self, blocker_user_id: int, blocked_user_id: int) -> Dict[str, Any]:
        """Create a one-way user block and remove follow relationships between both users."""
        if int(blocker_user_id) == int(blocked_user_id):
            raise ValueError("Cannot block yourself")
        with self.transaction() as conn:
            target = conn.execute("SELECT id FROM users WHERE id = ?", (blocked_user_id,)).fetchone()
            if target is None:
                raise KeyError("User not found")
            conn.execute(
                """
                INSERT OR IGNORE INTO user_blocks (blocker_user_id, blocked_user_id, created_at)
                VALUES (?, ?, datetime('now'))
                """,
                (blocker_user_id, blocked_user_id),
            )
            conn.execute(
                """
                DELETE FROM user_follows
                WHERE (follower_user_id = ? AND following_user_id = ?)
                   OR (follower_user_id = ? AND following_user_id = ?)
                """,
                (blocker_user_id, blocked_user_id, blocked_user_id, blocker_user_id),
            )
        return {
            "blocker_user_id": int(blocker_user_id),
            "blocked_user_id": int(blocked_user_id),
            "is_blocked": True,
        }

    def unblock_user(self, blocker_user_id: int, blocked_user_id: int) -> Dict[str, Any]:
        """Remove a one-way user block."""
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM user_blocks WHERE blocker_user_id = ? AND blocked_user_id = ?",
                (blocker_user_id, blocked_user_id),
            )
        return {
            "blocker_user_id": int(blocker_user_id),
            "blocked_user_id": int(blocked_user_id),
            "is_blocked": False,
        }

    def get_block_state(self, viewer_user_id: int, target_user_id: int) -> str:
        """Return none, blocked_by_me, or blocked_me for two users."""
        if int(viewer_user_id) == int(target_user_id):
            return "none"
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT blocker_user_id, blocked_user_id
                FROM user_blocks
                WHERE (blocker_user_id = ? AND blocked_user_id = ?)
                   OR (blocker_user_id = ? AND blocked_user_id = ?)
                """,
                (viewer_user_id, target_user_id, target_user_id, viewer_user_id),
            ).fetchall()
            for row in rows:
                blocker_id = int(row["blocker_user_id"])
                blocked_id = int(row["blocked_user_id"])
                if blocker_id == int(viewer_user_id) and blocked_id == int(target_user_id):
                    return "blocked_by_me"
                if blocker_id == int(target_user_id) and blocked_id == int(viewer_user_id):
                    return "blocked_me"
        return "none"

    def has_block_between_users(self, user_a_id: int, user_b_id: int) -> bool:
        """Return whether either user has blocked the other."""
        return self.get_block_state(user_a_id, user_b_id) != "none"

    def list_blocked_user_refs(self, blocker_user_id: int) -> List[Dict[str, Any]]:
        """Return user ids blocked by blocker_user_id."""
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT blocked_user_id AS user_id, created_at AS blocked_at
                FROM user_blocks
                WHERE blocker_user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (blocker_user_id,),
            ).fetchall()
            return [
                {
                    "user_id": int(row["user_id"]),
                    "blocked_at": row["blocked_at"],
                }
                for row in rows
            ]

    def list_block_related_user_ids(self, user_id: int) -> List[int]:
        """Return users who are in either side of a block relation with user_id."""
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT blocker_user_id, blocked_user_id
                FROM user_blocks
                WHERE blocker_user_id = ? OR blocked_user_id = ?
                """,
                (user_id, user_id),
            ).fetchall()
            ids: set[int] = set()
            for row in rows:
                ids.add(int(row["blocker_user_id"]))
                ids.add(int(row["blocked_user_id"]))
            ids.discard(int(user_id))
            return sorted(ids)

    def list_mutual_follow_friend_refs(self, user_id: int) -> List[Dict[str, Any]]:
        """Return users who both follow and are followed by user_id."""
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT
                    outbound.following_user_id AS user_id,
                    CASE
                        WHEN outbound.created_at > inbound.created_at THEN outbound.created_at
                        ELSE inbound.created_at
                    END AS friendship_created_at
                FROM user_follows outbound
                INNER JOIN user_follows inbound
                    ON inbound.follower_user_id = outbound.following_user_id
                    AND inbound.following_user_id = outbound.follower_user_id
                WHERE outbound.follower_user_id = ?
                ORDER BY friendship_created_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [
                {
                    "user_id": int(row["user_id"]),
                    "friendship_created_at": row["friendship_created_at"],
                }
                for row in rows
            ]

    def get_following_feed_posts(
        self,
        viewer_user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return followed users' posts from the last 7 days, sorted by interaction heat."""
        return self._get_scored_feed_posts(
            viewer_user_id=viewer_user_id,
            limit=limit,
            offset=offset,
            days=7,
            followed_only=True,
            exclude_ids=[],
        )

    def get_trending_feed_posts(
        self,
        viewer_user_id: Optional[int],
        limit: int = 20,
        offset: int = 0,
        exclude_ids: Optional[List[int]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return global public posts from the last 3 days, sorted by interaction heat."""
        return self._get_scored_feed_posts(
            viewer_user_id=viewer_user_id,
            limit=limit,
            offset=offset,
            days=3,
            followed_only=False,
            exclude_ids=exclude_ids or [],
        )

    def _get_scored_feed_posts(
        self,
        viewer_user_id: Optional[int],
        limit: int,
        offset: int,
        days: int,
        followed_only: bool,
        exclude_ids: List[int],
    ) -> Tuple[List[Dict[str, Any]], int]:
        where_clauses = [f"p.created_at >= datetime('now', '-{days} days')"]
        params: List[Any] = []
        if followed_only:
            where_clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM user_follows uf
                    WHERE uf.follower_user_id = ? AND uf.following_user_id = p.user_id
                )
                """
            )
            params.append(viewer_user_id)
        sanitized_exclude_ids = [int(post_id) for post_id in exclude_ids if int(post_id) > 0]
        if sanitized_exclude_ids:
            where_clauses.append(f"p.id NOT IN ({','.join('?' for _ in sanitized_exclude_ids)})")
            params.extend(sanitized_exclude_ids)

        where_sql = f"WHERE {' AND '.join(where_clauses)}"
        viewer_id = viewer_user_id or 0
        with self.transaction() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS total FROM community_posts p {where_sql}",
                params,
            ).fetchone()
            cursor = conn.execute(
                f"""
                SELECT
                    p.id, p.user_id, COALESCE(u.username, p.author_name) AS author_name, p.badge, p.title, p.body, p.image_urls, p.image_transforms,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    p.preview_type, p.recording_id, p.tone, p.created_at, p.updated_at,
                    COUNT(DISTINCT r.user_id) AS likes,
                    COUNT(DISTINCT c.id) AS comments,
                    COUNT(DISTINCT r.user_id) + (COUNT(DISTINCT c.id) * 2) AS feed_score,
                    CASE WHEN lr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me,
                    CASE WHEN bm.user_id IS NULL THEN 0 ELSE 1 END AS bookmarked_by_me
                FROM community_posts p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN community_post_reactions r ON r.post_id = p.id
                LEFT JOIN community_comments c ON c.post_id = p.id
                LEFT JOIN community_post_reactions lr
                    ON lr.post_id = p.id AND lr.user_id = ?
                LEFT JOIN community_post_bookmarks bm
                    ON bm.post_id = p.id AND bm.user_id = ?
                {where_sql}
                GROUP BY p.id
                ORDER BY feed_score DESC, p.created_at DESC, p.id DESC
                LIMIT ? OFFSET ?
                """,
                [viewer_id, viewer_id, *params, limit, offset],
            )
            posts = [self._community_post_from_row(row) for row in cursor.fetchall()]
            return posts, int(total_row["total"] if total_row else 0)

    def get_community_post(self, post_id: int, viewer_user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """查詢單一社群貼文。"""
        viewer_id = viewer_user_id or 0
        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT
                    p.id, p.user_id, COALESCE(u.username, p.author_name) AS author_name, p.badge, p.title, p.body, p.image_urls, p.image_transforms,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    p.preview_type, p.recording_id, p.tone, p.created_at, p.updated_at,
                    COUNT(DISTINCT r.user_id) AS likes,
                    COUNT(DISTINCT c.id) AS comments,
                    CASE WHEN lr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me,
                    CASE WHEN bm.user_id IS NULL THEN 0 ELSE 1 END AS bookmarked_by_me
                FROM community_posts p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN community_post_reactions r ON r.post_id = p.id
                LEFT JOIN community_comments c ON c.post_id = p.id
                LEFT JOIN community_post_reactions lr
                    ON lr.post_id = p.id AND lr.user_id = ?
                LEFT JOIN community_post_bookmarks bm
                    ON bm.post_id = p.id AND bm.user_id = ?
                WHERE p.id = ?
                GROUP BY p.id
                """,
                (viewer_id, viewer_id, post_id),
            ).fetchone()
            return self._community_post_from_row(row) if row else None

    def insert_community_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """新增社群貼文。"""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO community_posts (
                    user_id, author_name, badge, title, body, image_urls, image_transforms, preview_type,
                    recording_id, tone, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    post_data.get("user_id"),
                    post_data.get("author_name"),
                    post_data.get("badge", "玩家"),
                    post_data.get("title"),
                    post_data.get("body"),
                    json.dumps(post_data.get("image_urls", []), ensure_ascii=False),
                    json.dumps(post_data.get("image_transforms", []), ensure_ascii=False),
                    post_data.get("preview_type", "pool-table"),
                    post_data.get("recording_id"),
                    post_data.get("tone", "aqua"),
                ),
            )
            post_id = int(cursor.lastrowid)
        post = self.get_community_post(post_id, post_data.get("user_id"))
        if post is None:
            raise RuntimeError("Failed to read created community post")
        return post

    def delete_community_post(self, post_id: int, user_id: int) -> bool:
        """Delete a community post owned by the given user."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT id, user_id FROM community_posts WHERE id = ?",
                (post_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Post not found")
            if int(row["user_id"]) != int(user_id):
                return False
            conn.execute("DELETE FROM community_posts WHERE id = ?", (post_id,))
            return True

    def toggle_community_like(self, post_id: int, user_id: int) -> Dict[str, Any]:
        """切換貼文按讚狀態。"""
        with self.transaction() as conn:
            if conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone() is None:
                raise KeyError("Post not found")
            existing = conn.execute(
                "SELECT id FROM community_post_reactions WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
            if existing:
                conn.execute("DELETE FROM community_post_reactions WHERE post_id = ? AND user_id = ?", (post_id, user_id))
            else:
                conn.execute(
                    "INSERT INTO community_post_reactions (post_id, user_id, created_at) VALUES (?, ?, datetime('now'))",
                    (post_id, user_id),
                )
        post = self.get_community_post(post_id, user_id)
        if post is None:
            raise KeyError("Post not found")
        return post

    def toggle_community_bookmark(self, post_id: int, user_id: int) -> Dict[str, Any]:
        """切換貼文收藏狀態。"""
        with self.transaction() as conn:
            if conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone() is None:
                raise KeyError("Post not found")
            existing = conn.execute(
                "SELECT id FROM community_post_bookmarks WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
            if existing:
                conn.execute("DELETE FROM community_post_bookmarks WHERE post_id = ? AND user_id = ?", (post_id, user_id))
            else:
                conn.execute(
                    "INSERT INTO community_post_bookmarks (post_id, user_id, created_at) VALUES (?, ?, datetime('now'))",
                    (post_id, user_id),
                )
        post = self.get_community_post(post_id, user_id)
        if post is None:
            raise KeyError("Post not found")
        return post

    def get_community_comments(self, post_id: int, viewer_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """查詢貼文留言列表。"""
        viewer_id = viewer_user_id or 0
        with self.transaction() as conn:
            if conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone() is None:
                raise KeyError("Post not found")
            cursor = conn.execute(
                """
                SELECT
                    c.id, c.post_id, c.user_id, COALESCE(u.username, c.author_name) AS author_name, c.body, c.created_at,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    CASE
                        WHEN COALESCE(author_stats.total_games, 0) >= 60 AND (CAST(COALESCE(author_stats.wins, 0) AS REAL) / author_stats.total_games) >= 0.6 THEN '進階玩家 II'
                        WHEN COALESCE(author_stats.total_games, 0) >= 30 THEN '進階玩家 I'
                        WHEN COALESCE(author_stats.total_games, 0) >= 10 THEN '新手玩家 III'
                        WHEN COALESCE(author_stats.total_games, 0) > 0 THEN '新手玩家 II'
                        ELSE '新手玩家 I'
                    END AS author_player_level,
                    COUNT(DISTINCT cr.user_id) AS likes,
                    CASE WHEN my_cr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me
                FROM community_comments c
                LEFT JOIN users u ON u.id = c.user_id
                LEFT JOIN (
                    SELECT player_name, COUNT(*) AS total_games, SUM(CASE WHEN winner = player_name THEN 1 ELSE 0 END) AS wins
                    FROM (
                        SELECT player1_name AS player_name, winner FROM recordings WHERE COALESCE(player1_name, '') != ''
                        UNION ALL
                        SELECT player2_name AS player_name, winner FROM recordings WHERE COALESCE(player2_name, '') != ''
                    )
                    GROUP BY player_name
                ) author_stats ON author_stats.player_name = COALESCE(u.username, c.author_name)
                LEFT JOIN community_comment_reactions cr ON cr.comment_id = c.id
                LEFT JOIN community_comment_reactions my_cr
                    ON my_cr.comment_id = c.id AND my_cr.user_id = ?
                WHERE c.post_id = ?
                GROUP BY c.id
                ORDER BY c.created_at ASC, c.id ASC
                """,
                (viewer_id, post_id),
            )
            return [self._community_comment_from_row(row) for row in cursor.fetchall()]

    def insert_community_comment(self, post_id: int, user_id: int, author_name: str, body: str) -> Dict[str, Any]:
        """新增貼文留言。"""
        with self.transaction() as conn:
            if conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone() is None:
                raise KeyError("Post not found")
            cursor = conn.execute(
                """
                INSERT INTO community_comments (post_id, user_id, author_name, body, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (post_id, user_id, author_name, body),
            )
            row = conn.execute(
                """
                SELECT
                    c.id, c.post_id, c.user_id, COALESCE(u.username, c.author_name) AS author_name, c.body, c.created_at,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    CASE
                        WHEN COALESCE(author_stats.total_games, 0) >= 60 AND (CAST(COALESCE(author_stats.wins, 0) AS REAL) / author_stats.total_games) >= 0.6 THEN '進階玩家 II'
                        WHEN COALESCE(author_stats.total_games, 0) >= 30 THEN '進階玩家 I'
                        WHEN COALESCE(author_stats.total_games, 0) >= 10 THEN '新手玩家 III'
                        WHEN COALESCE(author_stats.total_games, 0) > 0 THEN '新手玩家 II'
                        ELSE '新手玩家 I'
                    END AS author_player_level,
                    0 AS likes,
                    0 AS liked_by_me
                FROM community_comments c
                LEFT JOIN users u ON u.id = c.user_id
                LEFT JOIN (
                    SELECT player_name, COUNT(*) AS total_games, SUM(CASE WHEN winner = player_name THEN 1 ELSE 0 END) AS wins
                    FROM (
                        SELECT player1_name AS player_name, winner FROM recordings WHERE COALESCE(player1_name, '') != ''
                        UNION ALL
                        SELECT player2_name AS player_name, winner FROM recordings WHERE COALESCE(player2_name, '') != ''
                    )
                    GROUP BY player_name
                ) author_stats ON author_stats.player_name = COALESCE(u.username, c.author_name)
                WHERE c.id = ?
                """,
                (int(cursor.lastrowid),),
            ).fetchone()
            return self._community_comment_from_row(row)

    def toggle_community_comment_like(self, comment_id: int, user_id: int) -> Dict[str, Any]:
        """切換留言按讚狀態。"""
        with self.transaction() as conn:
            row = conn.execute("SELECT id FROM community_comments WHERE id = ?", (comment_id,)).fetchone()
            if row is None:
                raise KeyError("Comment not found")
            existing = conn.execute(
                "SELECT id FROM community_comment_reactions WHERE comment_id = ? AND user_id = ?",
                (comment_id, user_id),
            ).fetchone()
            if existing:
                conn.execute("DELETE FROM community_comment_reactions WHERE comment_id = ? AND user_id = ?", (comment_id, user_id))
            else:
                conn.execute(
                    "INSERT INTO community_comment_reactions (comment_id, user_id, created_at) VALUES (?, ?, datetime('now'))",
                    (comment_id, user_id),
                )
            updated = conn.execute(
                """
                SELECT
                    c.id, c.post_id, c.user_id, COALESCE(u.username, c.author_name) AS author_name, c.body, c.created_at,
                    COALESCE(u.avatar_url, '') AS author_avatar_url,
                    CASE
                        WHEN COALESCE(author_stats.total_games, 0) >= 60 AND (CAST(COALESCE(author_stats.wins, 0) AS REAL) / author_stats.total_games) >= 0.6 THEN '進階玩家 II'
                        WHEN COALESCE(author_stats.total_games, 0) >= 30 THEN '進階玩家 I'
                        WHEN COALESCE(author_stats.total_games, 0) >= 10 THEN '新手玩家 III'
                        WHEN COALESCE(author_stats.total_games, 0) > 0 THEN '新手玩家 II'
                        ELSE '新手玩家 I'
                    END AS author_player_level,
                    COUNT(DISTINCT cr.user_id) AS likes,
                    CASE WHEN my_cr.user_id IS NULL THEN 0 ELSE 1 END AS liked_by_me
                FROM community_comments c
                LEFT JOIN users u ON u.id = c.user_id
                LEFT JOIN (
                    SELECT player_name, COUNT(*) AS total_games, SUM(CASE WHEN winner = player_name THEN 1 ELSE 0 END) AS wins
                    FROM (
                        SELECT player1_name AS player_name, winner FROM recordings WHERE COALESCE(player1_name, '') != ''
                        UNION ALL
                        SELECT player2_name AS player_name, winner FROM recordings WHERE COALESCE(player2_name, '') != ''
                    )
                    GROUP BY player_name
                ) author_stats ON author_stats.player_name = COALESCE(u.username, c.author_name)
                LEFT JOIN community_comment_reactions cr ON cr.comment_id = c.id
                LEFT JOIN community_comment_reactions my_cr
                    ON my_cr.comment_id = c.id AND my_cr.user_id = ?
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (user_id, comment_id),
            ).fetchone()
            return self._community_comment_from_row(updated)

    @staticmethod
    def _community_post_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        try:
            image_urls = json.loads(row["image_urls"] or "[]")
        except (TypeError, json.JSONDecodeError):
            image_urls = []
        if not isinstance(image_urls, list):
            image_urls = []
        try:
            image_transforms = json.loads(row["image_transforms"] or "[]") if "image_transforms" in row.keys() else []
        except (TypeError, json.JSONDecodeError):
            image_transforms = []
        if not isinstance(image_transforms, list):
            image_transforms = []
        post = {
            "id": int(row["id"]),
            "user_id": row["user_id"],
            "author_name": row["author_name"],
            "author_avatar_url": row["author_avatar_url"] if "author_avatar_url" in row.keys() else "",
            "badge": row["badge"],
            "title": row["title"],
            "body": row["body"],
            "image_urls": [str(url) for url in image_urls if url],
            "image_transforms": image_transforms,
            "preview_type": row["preview_type"],
            "recording_id": row["recording_id"],
            "tone": row["tone"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "likes": int(row["likes"] or 0),
            "comments": int(row["comments"] or 0),
            "liked_by_me": bool(row["liked_by_me"]),
            "bookmarked_by_me": bool(row["bookmarked_by_me"]),
        }
        if "feed_score" in row.keys():
            post["feed_score"] = int(row["feed_score"] or 0)
        return post

    @staticmethod
    def _community_comment_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "post_id": int(row["post_id"]),
            "user_id": row["user_id"],
            "author_name": row["author_name"],
            "author_avatar_url": row["author_avatar_url"] if "author_avatar_url" in row.keys() else "",
            "author_player_level": row["author_player_level"] if "author_player_level" in row.keys() else "新手玩家 I",
            "body": row["body"],
            "created_at": row["created_at"],
            "likes": int(row["likes"] or 0),
            "liked_by_me": bool(row["liked_by_me"]),
        }
    
    # ==================== Practice Stats CRUD ====================
    
    def insert_practice_stats(self, stats_data: Dict[str, Any]) -> Optional[int]:
        """
        插入練習統計記錄
        
        Args:
            stats_data: 統計資料字典
        
        Returns:
            插入的記錄 ID
        """
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO practice_stats (
                    game_id, practice_type, pattern,
                    total_attempts, successful_attempts, success_rate,
                    avg_shot_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stats_data.get("game_id"),
                stats_data.get("practice_type"),
                stats_data.get("pattern"),
                stats_data.get("total_attempts", 0),
                stats_data.get("successful_attempts", 0),
                stats_data.get("success_rate", 0.0),
                stats_data.get("avg_shot_time")
            ))
            row_id = cursor.lastrowid
        self._sync_analytics_practice_stats(stats_data)
        return row_id
    
    def get_practice_stats(
        self,
        practice_type: Optional[str] = None,
        pattern: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        獲取練習統計
        
        Args:
            practice_type: 練習類型篩選
            pattern: 球型篩選
            start_date: 開始日期篩選
            end_date: 結束日期篩選
        
        Returns:
            統計列表
        """
        with self.transaction() as conn:
            conditions = []
            params = []
            
            if practice_type:
                conditions.append("ps.practice_type = ?")
                params.append(practice_type)
            
            if pattern:
                conditions.append("ps.pattern = ?")
                params.append(pattern)
            
            if start_date:
                conditions.append("r.start_time >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("r.start_time <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor = conn.execute(
                f"""
                SELECT ps.*, r.start_time, r.end_time
                FROM practice_stats ps
                JOIN recordings r ON ps.game_id = r.game_id
                WHERE {where_clause}
                ORDER BY r.start_time DESC
                """,
                params
            )
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== Players CRUD ====================
    
    def upsert_player(self, player_name: str) -> Optional[int]:
        """
        插入或更新玩家記錄
        
        Args:
            player_name: 玩家名稱
        
        Returns:
            玩家 ID
        """
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO players (name, total_games, total_wins, win_rate)
                VALUES (?, 0, 0, 0.0)
                ON CONFLICT(name) DO NOTHING
            """, (player_name,))
            
            # 獲取玩家 ID
            cursor = conn.execute("SELECT id FROM players WHERE name = ?", (player_name,))
            row = cursor.fetchone()
            return row[0] if row else cursor.lastrowid
    
    def update_player_stats(self, player_name: str) -> bool:
        """
        更新玩家統計（從 recordings 表重新計算）
        
        Args:
            player_name: 玩家名稱
        
        Returns:
            是否更新成功
        """
        with self.transaction() as conn:
            # 計算總局數和勝場數
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_games,
                    SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as total_wins
                FROM recordings
                WHERE player1_name = ? OR player2_name = ?
            """, (player_name, player_name, player_name))
            
            row = cursor.fetchone()
            total_games = row[0] or 0
            total_wins = row[1] or 0
            win_rate = (total_wins / total_games) if total_games > 0 else 0.0
            
            # 更新玩家統計
            cursor = conn.execute("""
                UPDATE players
                SET total_games = ?, total_wins = ?, win_rate = ?
                WHERE name = ?
            """, (total_games, total_wins, win_rate, player_name))
            
            return cursor.rowcount > 0
    
    def get_player_stats(self, player_name: str) -> Optional[Dict[str, Any]]:
        """
        獲取玩家統計
        
        Args:
            player_name: 玩家名稱
        
        Returns:
            玩家統計字典
        """
        with self.transaction() as conn:
            cursor = conn.execute(
                "SELECT * FROM players WHERE name = ?",
                (player_name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_player_analytics(self, player_name: str) -> Dict[str, Any]:
        """聚合查詢玩家統計，避免全量載入 recordings。"""
        with self.transaction() as conn:
            normalized_name = player_name.replace(" ", "")
            winner_eq = normalized_name
            winner_like_prefix = f"{normalized_name},%"
            winner_like_middle = f"%,{normalized_name},%"
            winner_like_suffix = f"%,{normalized_name}"

            # 9-ball 對戰總局數 / 勝場數
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_games,
                    SUM(
                        CASE
                            WHEN (
                                REPLACE(COALESCE(winner, ''), ' ', '') = ?
                                OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE ?
                                OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE ?
                                OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE ?
                            ) THEN 1 ELSE 0
                        END
                    ) AS total_wins
                FROM recordings
                WHERE game_type = 'nine_ball'
                  AND (player1_name = ? OR player2_name = ?)
                """,
                (winner_eq, winner_like_prefix, winner_like_middle, winner_like_suffix, player_name, player_name)
            )
            row = cursor.fetchone()
            total_games = int(row["total_games"] or 0) if row else 0
            total_wins = int(row["total_wins"] or 0) if row else 0
            win_rate = (total_wins / total_games) if total_games > 0 else 0.0

            # 最近對戰記錄（最多 5 筆）
            cursor = conn.execute(
                """
                SELECT game_id, player1_name, player2_name, winner, player1_score, player2_score, start_time
                FROM recordings
                WHERE game_type = 'nine_ball'
                  AND (player1_name = ? OR player2_name = ?)
                ORDER BY start_time DESC
                LIMIT 5
                """,
                (player_name, player_name)
            )
            recent_games_formatted: List[Dict[str, Any]] = []
            for game in cursor.fetchall():
                winner_raw = (game["winner"] or "")
                winner_tokens = [token.strip() for token in winner_raw.split(",") if token.strip()]
                is_win = player_name in winner_tokens
                result = "draw" if (is_win and len(winner_tokens) > 1) else ("win" if is_win else "loss")
                opponent = game["player2_name"] if game["player1_name"] == player_name else game["player1_name"]
                score = f"{game['player1_score'] or 0}-{game['player2_score'] or 0}"
                recent_games_formatted.append({
                    "game_id": game["game_id"],
                    "opponent": opponent,
                    "result": result,
                    "score": score,
                    "date": game["start_time"],
                })

            # 練習總場次
            cursor = conn.execute(
                """
                SELECT COUNT(*) AS total_practice_sessions
                FROM recordings
                WHERE game_type IN ('practice_single', 'practice_pattern', 'practice_accuracy')
                  AND (player1_name = ? OR player2_name = ? OR (COALESCE(player1_name, '') = '' AND COALESCE(player2_name, '') = ''))
                """,
                (player_name, player_name)
            )
            row = cursor.fetchone()
            total_practice_sessions = int(row["total_practice_sessions"] or 0) if row else 0

            cursor = conn.execute(
                """
                SELECT COALESCE(SUM(duration_seconds), 0) AS total_practice_seconds
                FROM recordings
                WHERE game_type IN ('practice_single', 'practice_pattern', 'practice_accuracy')
                  AND (player1_name = ? OR player2_name = ? OR (COALESCE(player1_name, '') = '' AND COALESCE(player2_name, '') = ''))
                """,
                (player_name, player_name)
            )
            row = cursor.fetchone()
            total_practice_seconds = float(row["total_practice_seconds"] or 0) if row else 0.0

            # 最近練習（最多 5 筆）
            cursor = conn.execute(
                """
                SELECT game_id, game_type, duration_seconds, start_time
                FROM recordings
                WHERE game_type IN ('practice_single', 'practice_pattern', 'practice_accuracy')
                  AND (player1_name = ? OR player2_name = ? OR (COALESCE(player1_name, '') = '' AND COALESCE(player2_name, '') = ''))
                ORDER BY start_time DESC
                LIMIT 5
                """,
                (player_name, player_name)
            )
            recent_practice = [
                {
                    "game_id": item["game_id"],
                    "practice_type": "單球練習" if item["game_type"] == "practice_single" else "準度訓練" if item["game_type"] == "practice_accuracy" else "球型練習",
                    "duration_seconds": item["duration_seconds"] or 0,
                    "date": item["start_time"],
                }
                for item in cursor.fetchall()
            ]

            return {
                "name": player_name,
                "total_games": total_games,
                "total_wins": total_wins,
                "win_rate": round(win_rate, 2),
                "recent_games": recent_games_formatted,
                "total_practice_sessions": total_practice_sessions,
                "total_practice_seconds": round(total_practice_seconds, 2),
                "recent_practice": recent_practice,
            }

    def get_stats_summary_aggregated(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """聚合查詢統計摘要，避免全量載入 recordings。"""
        with self.transaction() as conn:
            base_conditions: List[str] = []
            base_params: List[Any] = []

            if start_date:
                base_conditions.append("start_time >= ?")
                base_params.append(start_date)
            if end_date:
                base_conditions.append("start_time <= ?")
                base_params.append(end_date)

            def build_where(extra_conditions: Optional[List[str]] = None) -> str:
                conds = list(base_conditions)
                if extra_conditions:
                    conds.extend(extra_conditions)
                return f"WHERE {' AND '.join(conds)}" if conds else ""

            # 總場次
            where_all = build_where()
            cursor = conn.execute(
                f"SELECT COUNT(*) AS total_games FROM recordings {where_all}",
                base_params,
            )
            total_games = int((cursor.fetchone() or {"total_games": 0})["total_games"] or 0)

            # 練習場次
            where_practice = build_where(["game_type IN ('practice_single', 'practice_pattern', 'practice_accuracy')"])
            cursor = conn.execute(
                f"SELECT COUNT(*) AS total_practice_sessions FROM recordings {where_practice}",
                base_params,
            )
            total_practice_sessions = int((cursor.fetchone() or {"total_practice_sessions": 0})["total_practice_sessions"] or 0)

            # 平均時長
            where_duration = build_where(["duration_seconds IS NOT NULL"])
            cursor = conn.execute(
                f"SELECT AVG(duration_seconds) AS avg_duration FROM recordings {where_duration}",
                base_params,
            )
            average_game_duration = float((cursor.fetchone() or {"avg_duration": 0.0})["avg_duration"] or 0.0)

            # 最活躍玩家
            where_p1 = build_where(["player1_name IS NOT NULL", "player1_name <> ''"])

            where_p2 = build_where(["player2_name IS NOT NULL", "player2_name <> ''"])

            cursor = conn.execute(
                f"""
                SELECT name, COUNT(*) AS cnt
                FROM (
                    SELECT player1_name AS name FROM recordings {where_p1}
                    UNION ALL
                    SELECT player2_name AS name FROM recordings {where_p2}
                ) t
                GROUP BY name
                ORDER BY cnt DESC
                LIMIT 1
                """,
                base_params + base_params,
            )
            row = cursor.fetchone()
            most_active_player = row["name"] if row else None

            # 玩家排名（只統計 nine_ball）
            where_nine_ball = build_where(["game_type = 'nine_ball'"])

            cursor = conn.execute(
                f"""
                SELECT name, COUNT(*) AS total_games, SUM(is_win) AS total_wins
                FROM (
                    SELECT
                        player1_name AS name,
                        CASE WHEN player1_name IS NOT NULL AND (
                            REPLACE(COALESCE(winner, ''), ' ', '') = REPLACE(player1_name, ' ', '')
                            OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE REPLACE(player1_name, ' ', '') || ',%'
                            OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE '%,' || REPLACE(player1_name, ' ', '') || ',%'
                            OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE '%,' || REPLACE(player1_name, ' ', '')
                        ) THEN 1 ELSE 0 END AS is_win
                    FROM recordings {where_nine_ball}
                    UNION ALL
                    SELECT
                        player2_name AS name,
                        CASE WHEN player2_name IS NOT NULL AND (
                            REPLACE(COALESCE(winner, ''), ' ', '') = REPLACE(player2_name, ' ', '')
                            OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE REPLACE(player2_name, ' ', '') || ',%'
                            OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE '%,' || REPLACE(player2_name, ' ', '') || ',%'
                            OR REPLACE(COALESCE(winner, ''), ' ', '') LIKE '%,' || REPLACE(player2_name, ' ', '')
                        ) THEN 1 ELSE 0 END AS is_win
                    FROM recordings {where_nine_ball}
                ) t
                WHERE name IS NOT NULL AND name <> ''
                GROUP BY name
                ORDER BY total_games DESC
                """,
                base_params + base_params,
            )
            player_rankings: List[Dict[str, Any]] = []
            for item in cursor.fetchall():
                games = int(item["total_games"] or 0)
                wins = int(item["total_wins"] or 0)
                rate = (wins / games) if games > 0 else 0.0
                player_rankings.append({
                    "name": item["name"],
                    "total_games": games,
                    "total_wins": wins,
                    "win_rate": round(rate, 2),
                })

            return {
                "total_games": total_games,
                "total_practice_sessions": total_practice_sessions,
                "most_active_player": most_active_player,
                "average_game_duration": round(average_game_duration, 2),
                "player_rankings": player_rankings,
            }

    # ==================== Color Calibration Profiles ====================

    def list_color_calibration_profiles(self, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出顏色校正設定檔。"""
        with self.transaction() as conn:
            if mode:
                cursor = conn.execute(
                    """
                    SELECT id, mode, name, created_at, updated_at
                    FROM color_calibration_profiles
                    WHERE mode = ?
                    ORDER BY updated_at DESC, id DESC
                    """,
                    (mode,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, mode, name, created_at, updated_at
                    FROM color_calibration_profiles
                    ORDER BY updated_at DESC, id DESC
                    """
                )
            return [dict(row) for row in cursor.fetchall()]

    def create_color_calibration_profile(self, mode: str, name: str) -> Dict[str, Any]:
        """新增顏色校正設定檔。"""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO color_calibration_profiles (mode, name, mapping_json)
                VALUES (?, ?, ?)
                """,
                (mode, name, json.dumps({}, ensure_ascii=False))
            )
            profile_id = cursor.lastrowid

            cursor = conn.execute(
                "SELECT id, mode, name, mapping_json, created_at, updated_at FROM color_calibration_profiles WHERE id = ?",
                (profile_id,)
            )
            row = cursor.fetchone()
            profile = dict(row) if row else {"id": profile_id, "mode": mode, "name": name, "mapping_json": "{}"}
            mapping_json = profile.get("mapping_json") or "{}"
            profile["mappings"] = json.loads(str(mapping_json))
            return profile

    def get_color_calibration_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """取得單一顏色校正設定檔。"""
        with self.transaction() as conn:
            cursor = conn.execute(
                "SELECT id, mode, name, mapping_json, created_at, updated_at FROM color_calibration_profiles WHERE id = ?",
                (profile_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            profile = dict(row)
            mapping_json = profile.get("mapping_json") or "{}"
            profile["mappings"] = json.loads(str(mapping_json))
            return profile

    def update_color_calibration_profile(self, profile_id: int, mappings: Dict[str, Any]) -> bool:
        """更新設定檔配色映射。"""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE color_calibration_profiles
                SET mapping_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(mappings, ensure_ascii=False), profile_id)
            )
            return cursor.rowcount > 0

    def delete_color_calibration_profile(self, profile_id: int) -> bool:
        """刪除顏色校正設定檔。"""
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM color_calibration_profiles WHERE id = ?",
                (profile_id,)
            )
            return cursor.rowcount > 0





RecordingsDB = Database


def init_db(db_path: str = "./data/recordings.db") -> Database:
    return Database(db_path)


