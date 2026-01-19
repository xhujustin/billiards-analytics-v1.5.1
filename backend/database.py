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
        player: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        查詢錄影列表（支援篩選、分頁）
        
        Args:
            game_type: 遊戲類型篩選
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
            
            if game_type:
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
