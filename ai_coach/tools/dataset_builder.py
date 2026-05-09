"""
Qwen 訓練資料集建立工具

流程：
1. 從 API 採集遊戲/練習數據 → 原始數據池
2. 數據清理與正規化 → 規範格式
3. 專業教練標註 → 標註品質確保
4. 數據增強 → 提升泛化能力
5. 質量檢測 → 最終驗證
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class BilliardsSample:
    """撞球訓練樣本的統一格式。"""
    
    # 基本信息
    sample_id: str
    source: str  # "game", "practice", "coach_annotation"
    created_at: str
    
    # 場景描述
    game_type: str  # "nine_ball", "practice_single", "practice_pattern"
    
    # 球位信息
    white_ball_position: str  # 語意位置："左上角", "中心位" 等
    target_ball_position: str  # 標靶球位置
    nearby_balls_description: str  # 周圍球的描述
    
    # 建議內容
    instruction: str  # 教練指導信息
    recommendation: str  # AI 建議動作
    expected_outcome: str  # 預期結果
    
    # 玩家背景
    player_name: str = "default_player"
    player_skill_level: str = "intermediate"  # "beginner", "intermediate", "advanced"
    practice_type: Optional[str] = None  # "straight", "cut", "bank", "combo"
    
    # 標註信息
    annotator: str = "coach"
    confidence_score: float = 0.9  # 0-1，表示建議的準確度
    is_verified: bool = False
    
    def to_instruction_format(self) -> Dict:
        """轉換為 instruction 格式（用於 Unsloth 訓練）。"""
        return {
            "instruction": self.instruction,
            "input": f"{self.white_ball_position}→{self.target_ball_position}\n周圍球況：{self.nearby_balls_description}",
            "output": self.recommendation,
        }
    
    def to_chat_format(self) -> Dict:
        """轉換為 chat 格式（用於對話微調）。"""
        return {
            "messages": [
                {
                    "role": "user",
                    "content": f"球況分析：\n{self.instruction}\n\n背景：玩家等級 {self.player_skill_level}"
                },
                {
                    "role": "assistant",
                    "content": self.recommendation
                }
            ],
            "metadata": {
                "source": self.source,
                "confidence": self.confidence_score
            }
        }


class DataCollector:
    """從 API 採集數據。"""
    
    def __init__(self, api_base_url: str = "http://localhost:8001"):
        """初始化數據收集器。
        
        Args:
            api_base_url: 後端 API 基礎 URL
        """
        self.api_base_url = api_base_url
        self.collected_samples = []
    
    def collect_from_game_recordings(
        self,
        game_type: str = "nine_ball",
        limit: int = 100,
    ) -> List[Dict]:
        """從遊戲錄像採集數據。
        
        Args:
            game_type: 遊戲類型篩選
            limit: 採集上限
            
        Returns:
            錄像事件列表
        """
        import requests
        
        try:
            # 查詢錄像列表
            response = requests.get(
                f"{self.api_base_url}/api/recordings",
                params={
                    "game_type": game_type,
                    "limit": min(limit, 100),
                    "offset": 0
                }
            )
            response.raise_for_status()
            
            recordings = response.json().get("recordings", [])
            logger.info(f"Collected {len(recordings)} game recordings")
            
            return recordings
        
        except Exception as e:
            logger.error(f"Failed to collect game recordings: {e}")
            return []
    
    def collect_from_practice_sessions(
        self,
        practice_type: str = "single",
        limit: int = 100,
    ) -> List[Dict]:
        """從練習模式採集數據。
        
        Args:
            practice_type: 練習類型
            limit: 採集上限
            
        Returns:
            練習會話列表
        """
        import requests
        
        try:
            response = requests.get(
                f"{self.api_base_url}/api/recordings",
                params={
                    "game_type": f"practice_{practice_type}",
                    "limit": min(limit, 100),
                    "offset": 0
                }
            )
            response.raise_for_status()
            
            sessions = response.json().get("recordings", [])
            logger.info(f"Collected {len(sessions)} practice sessions")
            
            return sessions
        
        except Exception as e:
            logger.error(f"Failed to collect practice sessions: {e}")
            return []
    
    def collect_player_statistics(self) -> Dict:
        """採集玩家統計數據（用於提取成功/失敗模式）。
        
        Returns:
            玩家統計彙總
        """
        import requests
        
        try:
            response = requests.get(
                f"{self.api_base_url}/api/stats/summary"
            )
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Failed to collect player statistics: {e}")
            return {}


class DataCleaner:
    """數據清理與正規化。"""
    
    @staticmethod
    def normalize_position_description(desc: str) -> str:
        """正規化位置描述。
        
        例如：
            "左上" → "左上角"
            "中" → "中心位"
            "底邊" → "底袋位"
        """
        mapping = {
            "左上": "左上角",
            "上中": "上中袋",
            "右上": "右上角",
            "左中": "左中位",
            "中": "中心位",
            "右中": "右中位",
            "左下": "左下角",
            "底": "底袋位",
            "右下": "右下角",
            "左邊袋": "左邊袋",
            "右邊袋": "右邊袋",
        }
        
        for key, value in mapping.items():
            if key in desc:
                return value
        
        return desc.strip()
    
    @staticmethod
    def clean_recommendation(text: str) -> str:
        """清理建議文本。
        
        移除：
            - 多餘空格
            - 特殊符號
            - 重複短語
        """
        # 移除多餘空格
        text = " ".join(text.split())
        
        # 移除特殊符號
        text = text.replace("\n\n", "。").replace("\n", "")
        
        # 移除冗餘短語
        redundant = ["嗯，", "呃，", "總之，", "好的，"]
        for phrase in redundant:
            text = text.replace(phrase, "")
        
        return text.strip()
    
    @staticmethod
    def validate_sample(sample: BilliardsSample) -> Tuple[bool, str]:
        """驗證樣本完整性。
        
        Returns:
            (is_valid, error_message)
        """
        if not sample.instruction or len(sample.instruction) < 5:
            return False, "指導信息過短"
        
        if not sample.recommendation or len(sample.recommendation) < 10:
            return False, "建議文本過短"
        
        if not (0 <= sample.confidence_score <= 1):
            return False, "置信度分數無效"
        
        valid_positions = {
            "左上角", "上中袋", "右上角",
            "左中位", "中心位", "右中位",
            "左下角", "底袋位", "右下角",
            "左邊袋", "右邊袋"
        }
        
        if sample.white_ball_position not in valid_positions:
            return False, f"無效的白球位置：{sample.white_ball_position}"
        
        return True, ""


class DataAnnotator:
    """專業教練標註工具。"""
    
    @staticmethod
    def annotate_single_ball_practice(
        success: bool,
        attempts: int,
        success_rate: float,
        player_skill: str,
    ) -> str:
        """為單球練習生成建議。
        
        Args:
            success: 是否進球
            attempts: 嘗試次數
            success_rate: 成功率
            player_skill: 玩家等級
            
        Returns:
            建議文本
        """
        if not success:
            suggestions = {
                "beginner": "保持桿身穩定，瞄準母球中心。建議再嘗試，調整角度微小幅度。",
                "intermediate": "力度調整稍大。檢查桿身是否保持水平。預測子球軌跡。",
                "advanced": "考慮力度變化與英文效應。微調角度以應對台面曲率。"
            }
        else:
            suggestions = {
                "beginner": "很好！保持這個姿勢。繼續練習以提升穩定性。",
                "intermediate": "優秀的進球！現在嘗試同一位置的變化角度。",
                "advanced": "完美的力度控制。下一步練習不同的球型組合。"
            }
        
        return suggestions.get(player_skill, suggestions["intermediate"])
    
    @staticmethod
    def annotate_game_situation(
        white_pos: str,
        target_pos: str,
        nearby_count: int,
        player_score: int,
        opponent_score: int,
        rounds_left: int,
    ) -> str:
        """為遊戲局勢生成策略建議。"""
        
        is_leading = player_score > opponent_score
        is_critical = rounds_left <= 2
        
        recommendation = f"目前局勢："
        
        if is_leading:
            recommendation += f"你領先 {player_score - opponent_score} 分，保守進攻。"
        else:
            recommendation += f"落後 {opponent_score - player_score} 分，需要積極進攻。"
        
        if is_critical:
            recommendation += "剩餘回合數有限，每一桿都至關重要。"
        
        if nearby_count > 5:
            recommendation += f"周圍有 {nearby_count} 顆球，小心誤撞。"
        
        recommendation += f"\n瞄準策略：從 {white_pos} 瞄準 {target_pos}。"
        
        return recommendation


class DataAugmenter:
    """數據增強 - 提升訓練集多樣性。"""
    
    @staticmethod
    def augment_position_variations(
        sample: BilliardsSample,
        num_variations: int = 3,
    ) -> List[BilliardsSample]:
        """根據白球/標靶球位置進行變化增強。"""
        
        position_mapping = {
            "左上角": ["上中袋", "左中位"],
            "上中袋": ["左上角", "右上角"],
            "右上角": ["上中袋", "右中位"],
            "左中位": ["左上角", "中心位", "左下角"],
            "中心位": ["左中位", "右中位"],
            "右中位": ["右上角", "中心位", "右下角"],
            "左下角": ["左中位", "底袋位"],
            "底袋位": ["左下角", "右下角"],
            "右下角": ["右中位", "底袋位"],
        }
        
        augmented = []
        for i in range(num_variations):
            new_sample = sample
            new_sample.sample_id = f"{sample.sample_id}_aug{i}"
            new_sample.white_ball_position = random.choice(
                position_mapping.get(sample.white_ball_position, ["中心位"])
            )
            augmented.append(new_sample)
        
        return augmented
    
    @staticmethod
    def augment_skill_levels(
        sample: BilliardsSample,
    ) -> List[BilliardsSample]:
        """為不同玩家等級生成變化版本。"""
        
        augmented = []
        for skill_level in ["beginner", "intermediate", "advanced"]:
            new_sample = sample
            new_sample.sample_id = f"{sample.sample_id}_{skill_level}"
            new_sample.player_skill_level = skill_level
            
            # 根據等級調整建議
            if skill_level == "beginner":
                new_sample.recommendation = "基礎動作為主。" + new_sample.recommendation
            elif skill_level == "advanced":
                new_sample.recommendation = "考慮進階技巧。" + new_sample.recommendation
            
            augmented.append(new_sample)
        
        return augmented


class DatasetBuilder:
    """完整的訓練集構建器。"""
    
    def __init__(self, output_dir: str = "./datasets"):
        """初始化構建器。
        
        Args:
            output_dir: 輸出目錄
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.collector = DataCollector()
        self.cleaner = DataCleaner()
        self.annotator = DataAnnotator()
        self.augmenter = DataAugmenter()
        
        self.samples = []
    
    def build_from_recordings(
        self,
        game_recordings: List[Dict],
        auto_augment: bool = True,
    ) -> List[BilliardsSample]:
        """從遊戲錄像構建訓練集。
        
        流程：
            1. 解析錄像数据
            2. 提取球位信息
            3. 生成建議
            4. 數據清理
            5. 可選數據增強
        """
        
        for idx, recording in enumerate(game_recordings):
            sample = BilliardsSample(
                sample_id=f"game_{recording.get('game_id', idx)}",
                source="game",
                created_at=recording.get("start_time", datetime.now().isoformat()),
                game_type="nine_ball",
                white_ball_position="中心位",  # 實際應從事件中提取
                target_ball_position="底袋位",  # 實際應從事件中提取
                nearby_balls_description="3顆球在周圍",
                instruction="遊戲局勢分析",
                recommendation=self.annotator.annotate_game_situation(
                    white_pos="中心位",
                    target_pos="底袋位",
                    nearby_count=3,
                    player_score=recording.get("player1_score", 0),
                    opponent_score=recording.get("player2_score", 0),
                    rounds_left=2
                ),
                expected_outcome=f"目標進球，帶領玩家得分",
                player_name=recording.get("player1_name", "Player1"),
            )
            
            # 驗證
            is_valid, error = self.cleaner.validate_sample(sample)
            if is_valid:
                self.samples.append(sample)
                
                # 數據增強
                if auto_augment:
                    augmented = self.augmenter.augment_skill_levels(sample)
                    self.samples.extend(augmented)
        
        logger.info(f"Built {len(self.samples)} samples from {len(game_recordings)} recordings")
        return self.samples
    
    def save_as_jsonl(
        self,
        filename: str = "dataset.jsonl",
        format_type: str = "instruction",
    ) -> Path:
        """保存為 JSONL 格式。
        
        Args:
            filename: 輸出文件名
            format_type: "instruction" 或 "chat"
            
        Returns:
            輸出文件路徑
        """
        
        output_file = self.output_dir / filename
        
        with open(output_file, "w", encoding="utf-8") as f:
            for sample in self.samples:
                if format_type == "instruction":
                    data = sample.to_instruction_format()
                else:
                    data = sample.to_chat_format()
                
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        
        logger.info(f"Saved {len(self.samples)} samples to {output_file}")
        return output_file
    
    def generate_statistics_report(self) -> Dict:
        """生成數據集統計報告。"""
        
        if not self.samples:
            return {"error": "No samples in dataset"}
        
        # 統計維度
        skill_level_dist = defaultdict(int)
        source_dist = defaultdict(int)
        game_type_dist = defaultdict(int)
        
        for sample in self.samples:
            skill_level_dist[sample.player_skill_level] += 1
            source_dist[sample.source] += 1
            game_type_dist[sample.game_type] += 1
        
        avg_confidence = sum(s.confidence_score for s in self.samples) / len(self.samples)
        
        report = {
            "total_samples": len(self.samples),
            "skill_level_distribution": dict(skill_level_dist),
            "source_distribution": dict(source_dist),
            "game_type_distribution": dict(game_type_dist),
            "average_confidence": round(avg_confidence, 3),
            "verified_samples": sum(1 for s in self.samples if s.is_verified),
            "created_at": datetime.now().isoformat(),
        }
        
        return report
    
    def save_report(self, filename: str = "dataset_report.json") -> Path:
        """保存統計報告。"""
        
        output_file = self.output_dir / filename
        report = self.generate_statistics_report()
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Statistics report saved to {output_file}")
        return output_file


# ============ 使用範例 ============

def main():
    """完整的數據集構建流程。"""
    
    # 步驟 1: 初始化
    builder = DatasetBuilder(output_dir="./billiards_training_data")
    
    # 步驟 2: 採集數據
    logger.info("Step 1: Collecting data from API...")
    game_recordings = builder.collector.collect_from_game_recordings(limit=50)
    
    # 步驟 3: 構建訓練集
    logger.info("Step 2: Building dataset...")
    samples = builder.build_from_recordings(game_recordings, auto_augment=True)
    
    # 步驟 4: 保存
    logger.info("Step 3: Saving dataset...")
    dataset_file = builder.save_as_jsonl(
        filename="billiards_qwen_dataset.jsonl",
        format_type="instruction"
    )
    
    # 步驟 5: 生成報告
    logger.info("Step 4: Generating report...")
    report_file = builder.save_report()
    
    print(f"\n✅ Dataset construction completed!")
    print(f"   Dataset file: {dataset_file}")
    print(f"   Report file: {report_file}")
    print(f"\n   Total samples: {len(samples)}")
    print(f"   Report: {builder.generate_statistics_report()}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
