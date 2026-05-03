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
    visual_remaining_balls: List[int] = field(default_factory=list)
    remaining_balls_source: str = "rules"
    
    # 犯規追蹤
    foul_detected: bool = False
    foul_reason: Optional[str] = None
    last_shot_result: Optional[Dict[str, Any]] = None
    game_options: Dict[str, bool] = field(default_factory=lambda: {
        "auto_pot_detection": True,
        "foul_detection": True,
        "auto_scoring": True,
        "target_ar_hint_enabled": True,
    })
    
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
    pattern_layout: Optional[Dict[str, Any]] = None
    guide_options: Dict[str, Any] = field(default_factory=lambda: {"cue_laser_enabled": True})
    
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
        shot_time_limit: int = 0,  # ⭐ v1.5 新增
        game_options: Optional[Dict[str, Any]] = None
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
        sanitized_options = self._sanitize_game_options(game_options)

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
            game_start_time=time.time(),       # ⭐ 新增
            game_options=sanitized_options
        )
        
        return {
            "status": "game_started",
            "mode": "nine_ball",
            "players": [player1, player2],
            "target_rounds": target_rounds,
            "current_player": 1,
            "target_ball": 1,
            "shot_time_limit": shot_time_limit,  # ⭐ 新增
            "game_options": sanitized_options
        }

    def _sanitize_game_options(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """整理遊玩模式功能開關，未提供時採用預設全開。"""
        raw = options if isinstance(options, dict) else {}
        auto_pot_and_score = bool(raw.get("auto_pot_detection", raw.get("auto_scoring", True)))
        return {
            "auto_pot_detection": auto_pot_and_score,
            "foul_detection": bool(raw.get("foul_detection", True)),
            "auto_scoring": auto_pot_and_score,
            "target_ar_hint_enabled": bool(raw.get("target_ar_hint_enabled", True)),
        }

    def update_game_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """更新遊玩模式功能開關。"""
        if not self.game_state or not self.game_state.is_active:
            return {"error": "No active game"}

        current = dict(self.game_state.game_options)
        current.update(options if isinstance(options, dict) else {})
        self.game_state.game_options = self._sanitize_game_options(current)
        return {
            "status": "game_options_updated",
            "game_options": self.game_state.game_options,
        }

    def apply_visual_remaining_balls(self, visual_ball_numbers: List[int]) -> Dict[str, Any]:
        """用穩定視覺辨識球號修正 9 球剩餘球與目前目標球。"""
        if not self.game_state or not self.game_state.is_active:
            return {"error": "No active game"}
        if self.game_state.mode != GameMode.NINE_BALL:
            return {"error": "Visual correction is only available in nine_ball"}

        corrected = sorted({
            int(number)
            for number in visual_ball_numbers
            if isinstance(number, int) and 1 <= int(number) <= 9
        })
        if not corrected:
            return {"status": "visual_remaining_ignored", "reason": "empty_visual_set"}

        self.game_state.visual_remaining_balls = corrected
        if corrected != self.game_state.remaining_balls:
            self.game_state.remaining_balls = corrected
            self.game_state.target_ball = min(corrected)
            self.game_state.remaining_balls_source = "vision"
        else:
            self.game_state.remaining_balls_source = "rules+vision"

        return {
            "status": "visual_remaining_applied",
            "remaining_balls": self.game_state.remaining_balls,
            "target_ball": self.game_state.target_ball,
            "remaining_balls_source": self.game_state.remaining_balls_source,
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

    def apply_auto_shot_result(
        self,
        first_contact: Optional[int],
        potted_balls: List[int],
        cue_ball_potted: bool = False,
    ) -> Dict[str, Any]:
        """依據自動偵測結果套用 9 球犯規、進球、換人與計分。"""
        if not self.game_state or not self.game_state.is_active:
            return {"error": "No active game"}

        options = self.game_state.game_options
        potted_unique = []
        for ball in potted_balls:
            if isinstance(ball, int) and ball not in potted_unique:
                potted_unique.append(ball)

        result: Dict[str, Any] = {
            "is_foul": False,
            "foul_reason": None,
            "continue_turn": False,
            "game_over": False,
            "winner": None,
            "round_over": False,
            "first_contact": first_contact,
            "potted_balls": potted_unique,
            "cue_ball_potted": bool(cue_ball_potted),
            "auto_applied": True,
        }

        if options.get("foul_detection", True):
            if cue_ball_potted:
                result["is_foul"] = True
                result["foul_reason"] = "母球進袋"
            elif first_contact is None:
                result["is_foul"] = True
                result["foul_reason"] = f"未先擊中目標球 #{self.game_state.target_ball}"
            elif first_contact != self.game_state.target_ball:
                result["is_foul"] = True
                result["foul_reason"] = f"未先擊中目標球 #{self.game_state.target_ball}"

        if result["is_foul"]:
            self.switch_player()
            self.game_state.foul_detected = True
            self.game_state.foul_reason = result["foul_reason"]
            self._reset_shot_timer()
            self.game_state.last_shot_result = result
            return result

        self.game_state.foul_detected = False
        self.game_state.foul_reason = None

        if 9 in potted_unique:
            if options.get("auto_scoring", True):
                self._add_score(self.game_state.current_player)
            result["round_over"] = True
            if self.game_state.scores[self.game_state.current_player - 1] >= self.game_state.target_rounds:
                result["game_over"] = True
                result["winner"] = self.game_state.current_player
                self.game_state.is_active = False
            else:
                self._reset_nine_ball_rack()
            self._reset_shot_timer()
            self.game_state.last_shot_result = result
            return result

        legal_potted = False
        for ball in potted_unique:
            if ball in self.game_state.remaining_balls:
                self.game_state.remaining_balls.remove(ball)
                legal_potted = True

        if self.game_state.remaining_balls:
            self.game_state.target_ball = min(self.game_state.remaining_balls)
        else:
            self.game_state.target_ball = 9

        if legal_potted:
            result["continue_turn"] = True
        else:
            self.switch_player()

        self._reset_shot_timer()
        self.game_state.last_shot_result = result
        return result

    def _reset_nine_ball_rack(self):
        if self.game_state:
            self.game_state.remaining_balls = list(range(1, 10))
            self.game_state.target_ball = 1
            self.game_state.visual_remaining_balls = []
            self.game_state.remaining_balls_source = "rules"
            self.game_state.foul_detected = False
            self.game_state.foul_reason = None

    def _reset_shot_timer(self):
        if self.game_state and self.game_state.shot_time_limit > 0:
            self.game_state.remaining_time = self.game_state.shot_time_limit
            self.game_state.last_update_time = time.time()
    
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
            "visual_remaining_balls": self.game_state.visual_remaining_balls,
            "remaining_balls_source": self.game_state.remaining_balls_source,
            "foul_detected": self.game_state.foul_detected,
            "foul_reason": self.game_state.foul_reason,
            "last_shot_result": self.game_state.last_shot_result,
            "game_options": self.game_state.game_options,
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
        player_name: Optional[str] = None,
        pattern_layout: Optional[Dict[str, Any]] = None,
        guide_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        開始練習
        
        Args:
            mode: "single" 單球練習, "pattern" 球型練習
            pattern: 球型類型 ("straight", "cut", "bank", "combo")
            player_name: 玩家名稱（可選，用於統計）
            pattern_layout: 球型練習的自訂球位、路線與桿法設定
        
        Returns:
            練習初始狀態
        """
        sanitized_guides = {
            "cue_laser_enabled": bool((guide_options or {}).get("cue_laser_enabled", True)),
        }

        if mode == "single":
            self.practice_state = PracticeState(
                mode=GameMode.PRACTICE_SINGLE,
                is_active=True,
                player_name=player_name,
                guide_options=sanitized_guides
            )
        else:  # pattern
            if pattern not in ["straight", "cut", "bank", "combo"]:
                return {"error": "Invalid pattern"}
            if isinstance(pattern_layout, dict):
                layout_guides = pattern_layout.get("guide_options") if isinstance(pattern_layout.get("guide_options"), dict) else {}
                sanitized_guides = {
                    "cue_laser_enabled": bool(layout_guides.get("cue_laser_enabled", sanitized_guides["cue_laser_enabled"])),
                    "ball_guides_enabled": bool(layout_guides.get("ball_guides_enabled", True)),
                }
            
            self.practice_state = PracticeState(
                mode=GameMode.PRACTICE_PATTERN,
                pattern=PracticePattern(pattern),
                is_active=True,
                player_name=player_name,
                pattern_layout=pattern_layout,
                guide_options=sanitized_guides
            )
        
        return {
            "status": "practice_started",
            "mode": mode,
            "pattern": pattern,
            "player_name": player_name,
            "pattern_layout": pattern_layout,
            "guide_options": sanitized_guides,
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

    def update_practice_guide_options(self, guide_options: Dict[str, Any]) -> Dict[str, Any]:
        """更新練習模式的投影指引選項。"""
        if not self.practice_state or not self.practice_state.is_active:
            return {"error": "No active practice"}

        sanitized = {
            "cue_laser_enabled": bool(guide_options.get("cue_laser_enabled", True)),
        }
        pattern_layout = self.practice_state.pattern_layout
        if self.practice_state.mode == GameMode.PRACTICE_PATTERN:
            sanitized["ball_guides_enabled"] = bool(guide_options.get("ball_guides_enabled", True))
            pattern_layout = dict(self.practice_state.pattern_layout or {})
            pattern_layout["guide_options"] = sanitized
            self.practice_state.pattern_layout = pattern_layout

        self.practice_state.guide_options = sanitized

        return {
            "status": "practice_guides_updated",
            "guide_options": sanitized,
            "pattern_layout": pattern_layout,
        }

    def update_pattern_guide_options(self, guide_options: Dict[str, Any]) -> Dict[str, Any]:
        """相容舊 API：更新球型練習的投影指引選項。"""
        if not self.practice_state or self.practice_state.mode != GameMode.PRACTICE_PATTERN:
            return {"error": "Pattern guide options are only available in pattern practice"}
        return self.update_practice_guide_options(guide_options)
    
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
            "pattern_layout": self.practice_state.pattern_layout,
            "guide_options": self.practice_state.guide_options,
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
