"""
Session Manager for Billiards Analytics System (v1.5)
管理 session 生命週期、權限與多連線競爭
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class SessionState(str, Enum):
    """Session 狀態"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Role(str, Enum):
    """用戶角色"""
    VIEWER = "viewer"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    ADMIN = "admin"


@dataclass
class Session:
    """Session 資料結構"""
    session_id: str
    stream_id: str
    role: Role = Role.OPERATOR
    permission_flags: list[str] = field(default_factory=lambda: ["view", "control"])
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    last_heartbeat: float = field(default_factory=time.time)
    ws_connection_id: Optional[str] = None  # 追蹤當前 WS 連線
    state: SessionState = SessionState.ACTIVE
    client_info: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.expires_at == 0:
            from config import SESSION_TTL
            self.expires_at = self.created_at + SESSION_TTL

    def is_expired(self) -> bool:
        """檢查是否過期"""
        return time.time() > self.expires_at or self.state == SessionState.EXPIRED

    def should_renew(self) -> bool:
        """檢查是否應該續期"""
        from config import SESSION_RENEW_WINDOW, SESSION_MIN_RENEW_WINDOW, SESSION_TTL
        
        time_left = self.expires_at - time.time()
        ttl = SESSION_TTL
        
        # 計算續期視窗
        renew_window = max(ttl * SESSION_RENEW_WINDOW, SESSION_MIN_RENEW_WINDOW)
        
        return time_left < renew_window and not self.is_expired()

    def renew(self) -> None:
        """續期 session"""
        from config import SESSION_TTL
        self.expires_at = time.time() + SESSION_TTL

    def update_heartbeat(self) -> None:
        """更新心跳時間"""
        self.last_heartbeat = time.time()


class SessionManager:
    """
    Session 管理器
    - 創建/刪除 session
    - Kick-Old 策略（同一 session_id 僅允許一條控制型 WS）
    - 自動清理過期 session
    """

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self._last_cleanup = time.time()

    def create_session(
        self,
        stream_id: str,
        role: Role = Role.OPERATOR,
        client_info: Optional[Dict] = None
    ) -> Session:
        """創建新 session"""
        session_id = f"s-{uuid.uuid4().hex[:12]}"
        
        session = Session(
            session_id=session_id,
            stream_id=stream_id,
            role=role,
            permission_flags=self._get_default_permissions(role),
            client_info=client_info or {}
        )
        
        self.sessions[session_id] = session
        print(f"✅ Session created: {session_id} for stream {stream_id}")
        
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """獲取 session，自動過濾過期的"""
        session = self.sessions.get(session_id)
        if session and session.is_expired():
            session.state = SessionState.EXPIRED
            return None
        return session

    def renew_session(self, session_id: str) -> bool:
        """續期 session"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.renew()
        print(f"🔄 Session renewed: {session_id}, new expiry: {session.expires_at}")
        return True

    def revoke_session(self, session_id: str, reason: str = "manual") -> bool:
        """撤銷 session"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.state = SessionState.REVOKED
        print(f"⛔ Session revoked: {session_id}, reason: {reason}")
        return True

    def delete_session(self, session_id: str) -> bool:
        """刪除 session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"🗑️  Session deleted: {session_id}")
            return True
        return False

    def switch_stream(self, session_id: str, new_stream_id: str) -> bool:
        """切換 session 的 stream"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        old_stream = session.stream_id
        session.stream_id = new_stream_id
        print(f"🔀 Session {session_id} switched stream: {old_stream} -> {new_stream_id}")
        return True

    def register_ws_connection(self, session_id: str, connection_id: str) -> Optional[str]:
        """
        註冊 WebSocket 連線到 session（Kick-Old 策略）
        
        Returns:
            如果有舊連線被踢掉，返回舊連線 ID；否則返回 None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        old_connection_id = session.ws_connection_id
        session.ws_connection_id = connection_id
        session.update_heartbeat()
        
        if old_connection_id and old_connection_id != connection_id:
            print(f"⚠️  Kick-Old: {old_connection_id} replaced by {connection_id} for session {session_id}")
            return old_connection_id
        
        return None

    def unregister_ws_connection(self, session_id: str, connection_id: str) -> bool:
        """解除 WebSocket 連線註冊"""
        session = self.get_session(session_id)
        if not session or session.ws_connection_id != connection_id:
            return False
        
        session.ws_connection_id = None
        return True

    def update_heartbeat(self, session_id: str) -> bool:
        """更新 session 心跳"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.update_heartbeat()
        return True

    def cleanup_expired_sessions(self) -> int:
        """清理過期 session"""
        now = time.time()
        
        # 每 60 秒執行一次清理
        if now - self._last_cleanup < 60:
            return 0
        
        self._last_cleanup = now
        expired = [sid for sid, s in self.sessions.items() if s.is_expired()]
        
        for sid in expired:
            del self.sessions[sid]
        
        if expired:
            print(f"🧹 Cleaned up {len(expired)} expired sessions")
        
        return len(expired)

    def get_active_sessions(self) -> Dict[str, Session]:
        """獲取所有活躍 session"""
        self.cleanup_expired_sessions()
        return {sid: s for sid, s in self.sessions.items() if s.state == SessionState.ACTIVE}

    def _get_default_permissions(self, role: Role) -> list[str]:
        """根據角色獲取默認權限"""
        base_permissions = {
            Role.VIEWER: ["view"],
            Role.OPERATOR: ["view", "control"],
            Role.DEVELOPER: ["view", "control", "calibrate", "dev_ui"],
            Role.ADMIN: ["view", "control", "calibrate", "dev_ui", "score_control", "admin"],
        }
        return base_permissions.get(role, ["view"])


# 全局 session 管理器實例
session_manager = SessionManager()
