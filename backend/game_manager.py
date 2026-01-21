"""
遊戲管理器 - 處理練習模式和遊玩模式的狀態管理

遵照 v1.5 技術指南:
- 所有狀態在後端管理
- 前端僅顯示狀態,不進行邏輯處理
- 使用 REST API 進行狀態更新
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import time


class GameMode(Enum):
    """遊戲模式"""
    PRACTICE_SINGLE = "practice_single"      # 單球練習
    PRACTICE_PATTERN = "practice_pattern"    # 球型練習
    NINE_BALL = "nine_ball"                  # 9球
    EIGHT_BALL = "eight_ball"                # 8球 (預留)
    TEN_BALL = "ten_ball"                    # 10球 (預留)
    SNOOKER = "snooker"                      # 斯諾克 (預留)


class PracticePattern(Enum):
    """練習球型"""
    STRAIGHT = "straight"    # 直線球
    CUT = "cut"             # 切球
    BANK = "bank"           # 反彈球
    COMBO = "combo"         # 組合球 (預留)


@dataclass
class GameState:
    """遊戲狀態 (9球為主)"""
    mode: GameMode
    is_active: bool = False
    
    # 玩家資訊
    player_names: List[str] = field(default_factory=lambda: ["玩家1", "玩家2"])
    current_player: int = 1  # 1 or 2
    
    # 比分
    scores: List[int] = field(default_factory=lambda: [0, 0])
    target_rounds: int = 5  # 目標局數
    
    # 球檯狀態
    remaining_balls: List[int] = field(default_factory=lambda: list(range(1, 10)))
    target_ball: int = 1
    
    # 犯規追蹤
    foul_detected: bool = False
    foul_reason: Optional[str] = None
    
    # ⭐ v1.5 新增: 計時器相關
    shot_time_limit: int = 0  # 出手時間限制 (秒, 0=無限制)
    remaining_time: int = 0   # 當前剩餘時間 (秒)
    delay_used: List[bool] = field(default_factory=lambda: [False, False])  # 每人延時是否已用
    last_update_time: float = 0  # 計時器最後更新時間戳
    game_start_time: float = 0   # 遊戲開始時間戳


@dataclass
class PracticeState:
    """練習模式狀態"""
    mode: GameMode = GameMode.PRACTICE_SINGLE
    pattern: Optional[PracticePattern] = None
    is_active: bool = False
    player_name: Optional[str] = None  # 玩家名稱
    
    # 統計
    attempts: int = 0
    successes: int = 0
    target_balls: int = 1


class GameManager:
    """遊戲管理器"""
    
    def __init__(self):
        self.game_state: Optional[GameState] = None
        self.practice_state: Optional[PracticeState] = None
    
    # ==================== 9球遊戲邏輯 ====================
    
    def start_nine_ball(
        self, 
        player1: str = "玩家1",
        player2: str = "玩家2",
        target_rounds: int = 5,
        shot_time_limit: int = 0  # ⭐ v1.5 新增
    ) -> Dict[str, Any]:
        """
        開始9球遊戲
        
        Args:
            player1: 玩家1名稱
            player2: 玩家2名稱
            target_rounds: 目標局數
            shot_time_limit: 出手時間限制 (秒, 0=無限制)
        
        Returns:
            遊戲初始狀態
        """
        self.game_state = GameState(
            mode=GameMode.NINE_BALL,
            is_active=True,
            player_names=[player1, player2],
            current_player=1,
            scores=[0, 0],
            target_rounds=target_rounds,
            remaining_balls=list(range(1, 10)),
            target_ball=1,
            shot_time_limit=shot_time_limit,  # ⭐ 新增
            remaining_time=shot_time_limit,    # ⭐ 新增
            delay_used=[False, False],         # ⭐ 新增
            last_update_time=time.time(),      # ⭐ 新增
            game_start_time=time.time()        # ⭐ 新增
        )
        
        return {
            "status": "game_started",
            "mode": "nine_ball",
            "players": [player1, player2],
            "target_rounds": target_rounds,
            "current_player": 1,
            "target_ball": 1,
            "shot_time_limit": shot_time_limit  # ⭐ 新增
        }
    
    def check_nine_ball_rules(
        self, 
        first_contact: Optional[int],
        potted_ball: Optional[int]
    ) -> Dict[str, Any]:
        """
        檢查9球規則
        
        Args:
            first_contact: 母球最先碰到的球號 (None表示沒碰到球)
            potted_ball: 進袋的球號 (None表示沒進球)
        
        Returns:
            {
                "is_foul": bool,
                "foul_reason": str,
                "continue_turn": bool,
                "game_over": bool,
                "winner": int
            }
        """
        if not self.game_state or not self.game_state.is_active:
            return {"error": "No active game"}
        
        result = {
            "is_foul": False,
            "foul_reason": None,
            "continue_turn": False,
            "game_over": False,
            "winner": None,
            "round_over": False
        }
        
        # 規則1: 必須先打目標球
        if first_contact is None or first_contact != self.game_state.target_ball:
            result["is_foul"] = True
            result["foul_reason"] = f"未先擊中目標球 #{self.game_state.target_ball}"
            self.game_state.foul_detected = True
            self.game_state.foul_reason = result["foul_reason"]
            return result
        
        # 規則2: 檢查進球
        if potted_ball:
            if potted_ball == 9:
                # 9號球進袋,當前回合結束,得分
                self._add_score(self.game_state.current_player)
                result["round_over"] = True
                
                # 檢查是否遊戲結束
                if self.game_state.scores[self.game_state.current_player - 1] >= self.game_state.target_rounds:
                    result["game_over"] = True
                    result["winner"] = self.game_state.current_player
                    self.game_state.is_active = False
                else:
                    # 重置球檯
                    self.game_state.remaining_balls = list(range(1, 10))
                    self.game_state.target_ball = 1
                
                return result
            
            if potted_ball == self.game_state.target_ball:
                # 進了目標球,繼續打
                if potted_ball in self.game_state.remaining_balls:
                    self.game_state.remaining_balls.remove(potted_ball)
                
                # 更新目標球
                if self.game_state.remaining_balls:
                    self.game_state.target_ball = min(self.game_state.remaining_balls)
                else:
                    self.game_state.target_ball = 9
                
                result["continue_turn"] = True
            else:
                # 進了其他球,算犯規
                result["is_foul"] = True
                result["foul_reason"] = f"進錯球 (#{potted_ball})"
                self.game_state.foul_detected = True
                self.game_state.foul_reason = result["foul_reason"]
        
        return result
    
    def switch_player(self):
        """換人"""
        if self.game_state:
            self.game_state.current_player = 2 if self.game_state.current_player == 1 else 1
            self.game_state.foul_detected = False
            self.game_state.foul_reason = None
    
    def _add_score(self, player: int):
        """加分"""
        if self.game_state and 1 <= player <= 2:
            self.game_state.scores[player - 1] += 1
    
    def get_game_state(self) -> Optional[Dict[str, Any]]:
        """獲取遊戲狀態"""
        if not self.game_state:
            return None
        
        return {
            "mode": self.game_state.mode.value,
            "is_active": self.game_state.is_active,
            "players": self.game_state.player_names,
            "current_player": self.game_state.current_player,
            "scores": self.game_state.scores,
            "target_rounds": self.game_state.target_rounds,
            "target_ball": self.game_state.target_ball,
            "remaining_balls": self.game_state.remaining_balls,
            "foul_detected": self.game_state.foul_detected,
            "foul_reason": self.game_state.foul_reason,
            # ⭐ v1.5 新增計時器狀態
            "shot_time_limit": self.game_state.shot_time_limit,
            "remaining_time": self.game_state.remaining_time,
            "delay_used": self.game_state.delay_used,
            "game_start_time": self.game_state.game_start_time,
            "game_duration": self.get_game_duration()
        }
    
    def end_game(self):
        """結束遊戲"""
        if self.game_state:
            self.game_state.is_active = False
    
    # ==================== 練習模式 ====================
    
    def start_practice(
        self, 
        mode: str = "single",
        pattern: Optional[str] = None,
        player_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        開始練習
        
        Args:
            mode: "single" 單球練習, "pattern" 球型練習
            pattern: 球型類型 ("straight", "cut", "bank", "combo")
            player_name: 玩家名稱（可選，用於統計）
        
        Returns:
            練習初始狀態
        """
        if mode == "single":
            self.practice_state = PracticeState(
                mode=GameMode.PRACTICE_SINGLE,
                is_active=True,
                player_name=player_name
            )
        else:  # pattern
            if pattern not in ["straight", "cut", "bank", "combo"]:
                return {"error": "Invalid pattern"}
            
            self.practice_state = PracticeState(
                mode=GameMode.PRACTICE_PATTERN,
                pattern=PracticePattern(pattern),
                is_active=True,
                player_name=player_name
            )
        
        return {
            "status": "practice_started",
            "mode": mode,
            "pattern": pattern,
            "player_name": player_name,
            "attempts": 0,
            "successes": 0
        }
    
    def record_practice_attempt(self, success: bool) -> Dict[str, Any]:
        """
        記錄練習嘗試
        
        Args:
            success: 是否成功
        
        Returns:
            練習統計
        """
        if not self.practice_state:
            return {"error": "No active practice"}
        
        self.practice_state.attempts += 1
        if success:
            self.practice_state.successes += 1
        
        success_rate = (
            self.practice_state.successes / self.practice_state.attempts 
            if self.practice_state.attempts > 0 else 0
        )
        
        return {
            "attempts": self.practice_state.attempts,
            "successes": self.practice_state.successes,
            "success_rate": round(success_rate, 2)
        }
    
    def get_practice_state(self) -> Optional[Dict[str, Any]]:
        """獲取練習狀態"""
        if not self.practice_state:
            return None
        
        success_rate = (
            self.practice_state.successes / self.practice_state.attempts
            if self.practice_state.attempts > 0 else 0
        )
        
        return {
            "mode": self.practice_state.mode.value,
            "pattern": self.practice_state.pattern.value if self.practice_state.pattern else None,
            "is_active": self.practice_state.is_active,
            "attempts": self.practice_state.attempts,
            "successes": self.practice_state.successes,
            "success_rate": round(success_rate, 2)
        }
    
    def end_practice(self):
        """結束練習"""
        if self.practice_state:
            self.practice_state.is_active = False
    
    # ==================== v1.5 新增:計時器功能 ====================
    
    def start_timer(self, time_limit: int):
        """開始計時器"""
        if self.game_state:
            self.game_state.shot_time_limit = time_limit
            self.game_state.remaining_time = time_limit
            self.game_state.last_update_time = time.time()
    
    def update_timer(self) -> bool:
        """更新計時器,返回是否超時"""
        if not self.game_state or self.game_state.shot_time_limit == 0:
            return False
        
        now = time.time()
        elapsed = now - self.game_state.last_update_time
        self.game_state.remaining_time = max(0, int(self.game_state.remaining_time - elapsed))
        self.game_state.last_update_time = now
        
        return self.game_state.remaining_time == 0
    
    def apply_delay(self, player: int) -> Dict[str, Any]:
        """應用延時 (+30秒)"""
        if not self.game_state:
            return {"error": "No active game"}
        
        if player < 1 or player > 2:
            return {"error": "Invalid player"}
        
        if self.game_state.delay_used[player - 1]:
            return {"error": "Delay already used"}
        
        # 加30秒
        self.game_state.remaining_time += 30
        self.game_state.delay_used[player - 1] = True
        
        return {
            "status": "delay_applied",
            "remaining_time": self.game_state.remaining_time,
            "delay_used": self.game_state.delay_used
        }
    
    def get_timer_state(self) -> Dict[str, Any]:
        """獲取計時器狀態"""
        if not self.game_state:
            return {"error": "No active game"}
        
        self.update_timer()
        
        return {
            "remaining_time": self.game_state.remaining_time,
            "delay_used": self.game_state.delay_used,
            "is_timeout": self.game_state.remaining_time == 0 and self.game_state.shot_time_limit > 0
        }
    
    def get_game_duration(self) -> int:
        """獲取對戰時長 (秒)"""
        if not self.game_state or self.game_state.game_start_time == 0:
            return 0
        
        return int(time.time() - self.game_state.game_start_time)
