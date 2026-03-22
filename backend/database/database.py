"""
資料庫管理模組 - SQLite 資料庫操作

遵照 v1.5 技術指南:
- 使用 SQLite WAL 模式提升並發效能
- 結構化儲存錄影元資料、事件日誌、統計數據
- 提供完整的 CRUD 操作與事務管理
"""

import sqlite3
import json
import os
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager


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
    # ==================== Recordings CRUD ====================
    
    def insert_recording(self, recording_data: Dict[str, Any]) -> int:
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
            return cursor.lastrowid
    
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
            
            return cursor.rowcount > 0
    
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
            return cursor.rowcount > 0
    
    # ==================== Events CRUD ====================
    
    def insert_event(self, event_data: Dict[str, Any]) -> int:
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
            return cursor.lastrowid
    
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
            params = [game_id]
            
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
    
    # ==================== Practice Stats CRUD ====================
    
    def insert_practice_stats(self, stats_data: Dict[str, Any]) -> int:
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
            return cursor.lastrowid
    
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
    
    def upsert_player(self, player_name: str) -> int:
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
                WHERE game_type IN ('practice_single', 'practice_pattern')
                  AND (player1_name = ? OR player2_name = ?)
                """,
                (player_name, player_name)
            )
            row = cursor.fetchone()
            total_practice_sessions = int(row["total_practice_sessions"] or 0) if row else 0

            # 最近練習（最多 5 筆）
            cursor = conn.execute(
                """
                SELECT game_id, game_type, duration_seconds, start_time
                FROM recordings
                WHERE game_type IN ('practice_single', 'practice_pattern')
                  AND (player1_name = ? OR player2_name = ?)
                ORDER BY start_time DESC
                LIMIT 5
                """,
                (player_name, player_name)
            )
            recent_practice = [
                {
                    "game_id": item["game_id"],
                    "practice_type": "單球練習" if item["game_type"] == "practice_single" else "球型練習",
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
            where_practice = build_where(["game_type IN ('practice_single', 'practice_pattern')"])
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
            profile["mappings"] = json.loads(profile.get("mapping_json") or "{}")
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
            profile["mappings"] = json.loads(profile.get("mapping_json") or "{}")
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







