"""
個性化撞球建議引擎

核心：
1. 玩家畫像 - 多維度特徵提取
2. 成功率追蹤 - 球型、位置、玩家維度
3. 風格匹配 - 推薦適合玩家的建議方式
4. A/B 測試 - 持續優化建議品質

算法：
  個性化建議分 = 基礎分 × (1 + 玩家畫像加成) × 成功率因子 × 新鮮度因子
"""

import json
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


# ============ 玩家畫像構建 ============

@dataclass
class PlayerProfile:
    """玩家綜合畫像。"""
    
    # 基本信息
    player_id: str
    player_name: str
    created_at: str
    
    # 技能水平評估
    skill_level: str  # "beginner", "intermediate", "advanced", "expert"
    estimated_skill_score: float = 50.0  # 0-100
    
    # 風格特徵
    preferred_shot_types: List[str] = field(default_factory=list)  # ["straight", "cut", "bank", "combo"]
    strong_positions: List[str] = field(default_factory=list)  # 擅長的球位
    weak_positions: List[str] = field(default_factory=list)  # 劣勢球位
    
    # 學習偏好
    prefers_verbose_advice: bool = True  # 喜歡詳細建議
    prefers_quick_tips: bool = True  # 喜歡簡潔建議
    response_to_confidence: str = "neutral"  # "conservative", "neutral", "aggressive"
    
    # 統計數據
    total_games: int = 0
    total_practices: int = 0
    overall_success_rate: float = 0.5
    
    # 最近表現（30 天）
    recent_games_count: int = 0
    recent_success_rate: float = 0.5
    recent_trend: str = "stable"  # "improving", "stable", "declining"
    
    # 個性化建議計數
    suggestions_given: int = 0
    suggestions_acted_upon: int = 0
    suggestion_adoption_rate: float = 0.0
    
    def is_improving(self) -> bool:
        """是否成績提升中。"""
        return self.recent_trend == "improving"
    
    def is_struggling(self) -> bool:
        """是否表現不佳。"""
        return self.recent_success_rate < 0.4 and self.recent_trend == "declining"


class PlayerProfileBuilder:
    """從歷史数據構建玩家畫像。"""
    
    def __init__(self, api_base_url: str = "http://localhost:8001"):
        """初始化構建器。
        
        Args:
            api_base_url: 後端 API 基礎 URL
        """
        self.api_base_url = api_base_url
    
    def build_profile(self, player_name: str) -> PlayerProfile:
        """為玩家構建完整畫像。
        
        數據來源：
            1. /api/stats/player/{player_name} - 統計數據
            2. /api/recordings?player=... - 遊戲記錄
            3. /api/practice/records - 練習記錄
        """
        import requests
        
        try:
            # 獲取玩家統計
            resp = requests.get(
                f"{self.api_base_url}/api/stats/player/{player_name}"
            )
            resp.raise_for_status()
            stats = resp.json()
            
            profile = PlayerProfile(
                player_id=f"player_{player_name}",
                player_name=player_name,
                created_at=datetime.now().isoformat(),
                skill_level=self._estimate_skill_level(stats),
                estimated_skill_score=self._estimate_skill_score(stats),
                total_games=stats.get("total_games", 0),
                overall_success_rate=stats.get("win_rate", 0.5),
                recent_games_count=len(stats.get("recent_games", [])),
                recent_success_rate=self._calculate_recent_success_rate(
                    stats.get("recent_games", [])
                ),
            )
            
            # 分析遊戲風格
            profile = self._analyze_play_style(profile, stats)
            
            # 分析學習偏好
            profile = self._analyze_learning_preference(profile, stats)
            
            logger.info(f"Profile built for {player_name}: {profile.skill_level}")
            
            return profile
        
        except Exception as e:
            logger.error(f"Failed to build profile for {player_name}: {e}")
            
            # 返回默認玩家
            return PlayerProfile(
                player_id=f"player_{player_name}",
                player_name=player_name,
                created_at=datetime.now().isoformat(),
                skill_level="intermediate",
            )
    
    def _estimate_skill_level(self, stats: Dict) -> str:
        """根據統計數據估計技能等級。"""
        
        win_rate = stats.get("win_rate", 0.5)
        total_games = stats.get("total_games", 0)
        
        # 需要足夠的樣本量
        if total_games < 5:
            return "beginner"
        
        if win_rate < 0.35:
            return "beginner"
        elif win_rate < 0.50:
            return "intermediate"
        elif win_rate < 0.70:
            return "advanced"
        else:
            return "expert"
    
    def _estimate_skill_score(self, stats: Dict) -> float:
        """估計技能分數（0-100）。"""
        
        win_rate = stats.get("win_rate", 0.5)
        total_games = stats.get("total_games", 0)
        
        # 基於勝率的分數
        base_score = win_rate * 100
        
        # 根據遊戲數量調整（樣本量越大，分數越穩定）
        if total_games > 50:
            confidence = 1.0
        elif total_games > 20:
            confidence = 0.8
        else:
            confidence = 0.5
        
        # 加入信心度調整
        adjusted_score = base_score * confidence + 50 * (1 - confidence)
        
        return round(adjusted_score, 1)
    
    def _calculate_recent_success_rate(self, recent_games: List[Dict]) -> float:
        """計算最近成功率。"""
        
        if not recent_games:
            return 0.5
        
        wins = sum(1 for game in recent_games if game.get("result") == "win")
        return wins / len(recent_games)
    
    def _analyze_play_style(
        self,
        profile: PlayerProfile,
        stats: Dict
    ) -> PlayerProfile:
        """分析玩家遊戲風格。"""
        
        # 從最近遊戲提取球型偏好
        recent_games = stats.get("recent_games", [])
        
        shot_counts = defaultdict(int)
        position_wins = defaultdict(lambda: {"wins": 0, "total": 0})
        
        for game in recent_games:
            # 這是簡化版本，實際需要從詳細事件中提取
            # game.events 包含每一桿的詳細信息
            pass
        
        # 設定擅長位置
        if profile.skill_level in ["advanced", "expert"]:
            profile.strong_positions = ["中心位", "底袋位", "邊袋"]
            profile.weak_positions = ["角落"]
        else:
            profile.strong_positions = ["標準距離", "直線"]
            profile.weak_positions = ["複雜角度", "長距離"]
        
        return profile
    
    def _analyze_learning_preference(
        self,
        profile: PlayerProfile,
        stats: Dict
    ) -> PlayerProfile:
        """分析玩家學習偏好。"""
        
        win_rate = stats.get("win_rate", 0.5)
        
        # 根據技能等級設定偏好
        if profile.skill_level == "beginner":
            profile.prefers_verbose_advice = True
            profile.prefers_quick_tips = False
            profile.response_to_confidence = "conservative"
        
        elif profile.skill_level == "intermediate":
            profile.prefers_verbose_advice = True
            profile.prefers_quick_tips = True
            profile.response_to_confidence = "neutral"
        
        else:
            profile.prefers_verbose_advice = False
            profile.prefers_quick_tips = True
            profile.response_to_confidence = "aggressive"
        
        return profile


# ============ 成功率追蹤系統 ============

class SuccessRateTracker:
    """多維度成功率追蹤。"""
    
    def __init__(self):
        """初始化追蹤器。"""
        
        # 按球型追蹤
        self.shot_type_stats = defaultdict(lambda: {"attempts": 0, "successes": 0})
        
        # 按位置追蹤
        self.position_stats = defaultdict(lambda: {"attempts": 0, "successes": 0})
        
        # 按玩家等級追蹤
        self.skill_level_stats = defaultdict(lambda: {"attempts": 0, "successes": 0})
        
        # 按建議方式追蹤
        self.advice_style_stats = defaultdict(lambda: {"attempts": 0, "successes": 0})
    
    def record_attempt(
        self,
        shot_type: str,
        position: str,
        player_skill_level: str,
        advice_style: str,
        success: bool,
    ):
        """記錄一次嘗試。
        
        Args:
            shot_type: 球型（"straight", "cut", "bank", "combo"）
            position: 球位（"左上角", "中心位" 等）
            player_skill_level: 玩家等級
            advice_style: 建議方式（"verbose", "quick"）
            success: 是否成功
        """
        
        # 更新各維度統計
        for stats_dict, key in [
            (self.shot_type_stats, shot_type),
            (self.position_stats, position),
            (self.skill_level_stats, player_skill_level),
            (self.advice_style_stats, advice_style),
        ]:
            stats_dict[key]["attempts"] += 1
            if success:
                stats_dict[key]["successes"] += 1
    
    def get_success_rate(self, dimension: str, key: str) -> float:
        """獲取特定維度的成功率。
        
        Args:
            dimension: 維度（"shot_type", "position", "skill_level", "advice_style"）
            key: 鍵值
            
        Returns:
            成功率（0-1）
        """
        
        stats_dict = {
            "shot_type": self.shot_type_stats,
            "position": self.position_stats,
            "skill_level": self.skill_level_stats,
            "advice_style": self.advice_style_stats,
        }.get(dimension, {})
        
        if key not in stats_dict or stats_dict[key]["attempts"] == 0:
            return 0.5  # 默認概率
        
        stats = stats_dict[key]
        return stats["successes"] / stats["attempts"]


# ============ 個性化建議生成 ============

class PersonalizedAdvisor:
    """個性化建議生成器。"""
    
    def __init__(
        self,
        base_advisor,  # 基礎建議引擎
        profile_builder: PlayerProfileBuilder,
        success_tracker: SuccessRateTracker,
    ):
        """初始化個性化顧問。
        
        Args:
            base_advisor: 基礎建議生成器
            profile_builder: 玩家畫像構建器
            success_tracker: 成功率追蹤器
        """
        self.base_advisor = base_advisor
        self.profile_builder = profile_builder
        self.success_tracker = success_tracker
        
        self.player_profiles: Dict[str, PlayerProfile] = {}
    
    def generate_personalized_advice(
        self,
        game_state: Dict,
        player_name: str,
        shot_type: str = "straight",
    ) -> Dict:
        """生成個性化建議。
        
        Args:
            game_state: 遊戲狀態
            player_name: 玩家名稱
            shot_type: 球型
            
        Returns:
            個性化建議
        """
        
        # 獲取或構建玩家畫像
        if player_name not in self.player_profiles:
            self.player_profiles[player_name] = \
                self.profile_builder.build_profile(player_name)
        
        profile = self.player_profiles[player_name]
        
        # 基礎建議
        base_advice = self.base_advisor.generate_advice(game_state)
        
        # 應用個性化調整
        personalized = self._apply_personalization(
            base_advice,
            profile,
            game_state,
            shot_type,
        )
        
        return personalized
    
    def _apply_personalization(
        self,
        base_advice: Dict,
        profile: PlayerProfile,
        game_state: Dict,
        shot_type: str,
    ) -> Dict:
        """應用個性化調整。"""
        
        advice_text = base_advice.get("text", "")
        confidence_score = base_advice.get("confidence", 0.5)
        
        # 調整 1: 根據技能等級調整詳細度
        if profile.prefers_quick_tips:
            advice_text = self._shorten_advice(advice_text)
        elif profile.prefers_verbose_advice:
            advice_text = self._expand_advice(advice_text, profile)
        
        # 調整 2: 根據位置風格調整建議方向
        position = game_state.get("white_ball_pos", "中心位")
        if position in profile.weak_positions:
            advice_text = f"⚠️ 注意：你在 {position} 時成功率較低。{advice_text}"
        
        # 調整 3: 根據最近表現調整態度
        if profile.is_improving():
            advice_text += "  💪 保持這個勢頭！"
        elif profile.is_struggling():
            advice_text += "  💡 建議檢查基本功。"
        
        # 調整 4: 計算個性化置信度
        position_success_rate = self.success_tracker.get_success_rate(
            "position", position
        )
        shot_success_rate = self.success_tracker.get_success_rate(
            "shot_type", shot_type
        )
        
        # 組合多個因子
        combined_confidence = (
            confidence_score * 0.5 +  # 基礎模型置信度
            position_success_rate * 0.25 +  # 位置成功率
            shot_success_rate * 0.25  # 球型成功率
        )
        
        return {
            "text": advice_text,
            "confidence": combined_confidence,
            "personalized": True,
            "profile_adjustments": {
                "skill_level": profile.skill_level,
                "weak_positions": profile.weak_positions,
                "recent_trend": profile.recent_trend,
            }
        }
    
    def _shorten_advice(self, text: str) -> str:
        """縮減建議文本（適合進階玩家）。"""
        
        # 移除詳細說明，只保留核心
        if "。" in text:
            sentences = text.split("。")
            return sentences[0] + "。"  # 只保留第一句
        
        return text[:50] + "..." if len(text) > 50 else text
    
    def _expand_advice(self, text: str, profile: PlayerProfile) -> str:
        """擴展建議文本（適合初學者）。"""
        
        expansion = ""
        
        if profile.skill_level == "beginner":
            expansion = (
                "\n\n📚 初學者提示：\n"
                "- 保持杆身穩定\n"
                "- 瞄準母球中心\n"
                "- 力度適中"
            )
        
        return text + expansion


# ============ A/B 測試框架 ============

class ABTestFramework:
    """A/B 測試建議方案。"""
    
    @dataclass
    class TestVariant:
        """測試變體。"""
        variant_id: str
        name: str
        description: str
        is_control: bool = False
        
        # 統計
        total_impressions: int = 0
        total_conversions: int = 0
        conversion_rate: float = 0.0
    
    def __init__(self):
        """初始化 A/B 測試框架。"""
        self.variants: Dict[str, "ABTestFramework.TestVariant"] = {}
        self.user_variant_assignments: Dict[str, str] = {}
    
    def register_variant(
        self,
        variant_id: str,
        name: str,
        description: str,
        is_control: bool = False,
    ):
        """註冊測試變體。
        
        Args:
            variant_id: 變體 ID
            name: 變體名稱
            description: 變體描述
            is_control: 是否為對照組
        """
        
        variant = self.TestVariant(
            variant_id=variant_id,
            name=name,
            description=description,
            is_control=is_control,
        )
        
        self.variants[variant_id] = variant
        logger.info(f"Registered test variant: {name}")
    
    def assign_user_variant(self, user_id: str, variant_id: str):
        """為用戶分配測試變體。
        
        Args:
            user_id: 用戶 ID
            variant_id: 變體 ID
        """
        
        self.user_variant_assignments[user_id] = variant_id
    
    def record_impression(self, user_id: str):
        """記錄展示。"""
        
        variant_id = self.user_variant_assignments.get(user_id)
        if variant_id and variant_id in self.variants:
            self.variants[variant_id].total_impressions += 1
    
    def record_conversion(self, user_id: str, success: bool):
        """記錄轉化（用戶是否採納建議）。
        
        Args:
            user_id: 用戶 ID
            success: 是否成功
        """
        
        variant_id = self.user_variant_assignments.get(user_id)
        if variant_id and variant_id in self.variants:
            variant = self.variants[variant_id]
            if success:
                variant.total_conversions += 1
            
            # 更新轉化率
            if variant.total_impressions > 0:
                variant.conversion_rate = (
                    variant.total_conversions / variant.total_impressions
                )
    
    def get_statistical_significance(
        self,
        variant_a_id: str,
        variant_b_id: str,
    ) -> Dict:
        """計算統計顯著性（Chi-Square 檢定）。
        
        Args:
            variant_a_id: 變體 A ID
            variant_b_id: 變體 B ID
            
        Returns:
            顯著性分析結果
        """
        
        from scipy.stats import chi2_contingency
        
        variant_a = self.variants[variant_a_id]
        variant_b = self.variants[variant_b_id]
        
        # 構建 2x2 列聯表
        # [[A成功, A失敗], [B成功, B失敗]]
        contingency_table = [
            [variant_a.total_conversions, 
             variant_a.total_impressions - variant_a.total_conversions],
            [variant_b.total_conversions, 
             variant_b.total_impressions - variant_b.total_conversions],
        ]
        
        chi2, p_value, dof, expected = chi2_contingency(contingency_table)
        
        # p_value < 0.05 表示 95% 置信度下有顯著差異
        is_significant = p_value < 0.05
        winner = (
            variant_a_id if variant_a.conversion_rate > variant_b.conversion_rate
            else variant_b_id
        )
        
        return {
            "chi2_statistic": chi2,
            "p_value": p_value,
            "is_significant": is_significant,
            "winner": winner if is_significant else None,
            "variant_a_rate": variant_a.conversion_rate,
            "variant_b_rate": variant_b.conversion_rate,
        }
    
    def generate_report(self) -> Dict:
        """生成 A/B 測試報告。"""
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "variants": [],
        }
        
        for variant_id, variant in self.variants.items():
            report["variants"].append({
                "id": variant_id,
                "name": variant.name,
                "is_control": variant.is_control,
                "total_impressions": variant.total_impressions,
                "total_conversions": variant.total_conversions,
                "conversion_rate": round(variant.conversion_rate, 4),
            })
        
        return report


# ============ 使用範例 ============

def main():
    """個性化建議引擎演示。"""
    
    logger.info("="*60)
    logger.info("Personalized Billiards Advisor System")
    logger.info("="*60)
    
    # 01. 構建玩家畫像
    logger.info("\n[01] Building Player Profile")
    logger.info("-" * 40)
    
    profile_builder = PlayerProfileBuilder()
    player1_profile = profile_builder.build_profile("Player1")
    
    logger.info(f"Player: {player1_profile.player_name}")
    logger.info(f"Skill Level: {player1_profile.skill_level}")
    logger.info(f"Recent Success Rate: {player1_profile.recent_success_rate:.2%}")
    
    # 02. 成功率追蹤
    logger.info("\n[02] Success Rate Tracking")
    logger.info("-" * 40)
    
    tracker = SuccessRateTracker()
    
    # 模擬一些歷史數據
    tracker.record_attempt("straight", "中心位", "intermediate", "verbose", True)
    tracker.record_attempt("cut", "中心位", "intermediate", "verbose", False)
    tracker.record_attempt("straight", "角落", "intermediate", "quick", True)
    
    logger.info(f"Straight shot success: {tracker.get_success_rate('shot_type', 'straight'):.2%}")
    logger.info(f"Center position success: {tracker.get_success_rate('position', '中心位'):.2%}")
    
    # 03. A/B 測試
    logger.info("\n[03] A/B Testing")
    logger.info("-" * 40)
    
    ab_test = ABTestFramework()
    
    ab_test.register_variant(
        "variant_a",
        "Verbose Advice",
        "Detailed guidance with explanations",
        is_control=True
    )
    ab_test.register_variant(
        "variant_b",
        "Quick Tips",
        "Short, actionable advice",
        is_control=False
    )
    
    # 模擬用戶數據
    for i in range(100):
        variant = "variant_a" if i % 2 == 0 else "variant_b"
        ab_test.assign_user_variant(f"user_{i}", variant)
        ab_test.record_impression(f"user_{i}")
        
        # 假設 variant_b 有更好的轉化率
        success = (variant == "variant_b")
        ab_test.record_conversion(f"user_{i}", success)
    
    report = ab_test.generate_report()
    logger.info(f"Test Report: {json.dumps(report, indent=2)}")
    
    # 顯著性檢定
    significance = ab_test.get_statistical_significance("variant_a", "variant_b")
    logger.info(f"Significance: {significance}")
    
    logger.info("\n✅ Personalized Advisor System demo completed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
