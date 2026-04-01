"""
AI Coach Manager - 整合靜止偵測、座標語意化、vLLM API 互動。

核心功能：
1. 使用 StabilityDetector 偵測球的靜止狀態
2. 將 (x, y) 座標轉換為『左上、中袋、底袋』等語意描述
3. 非同步發送 POST 請求到 A100 vLLM API 伺服器
4. 接收建議並存入全域變數供 UI 顯示
"""

import threading
import requests
import json
import time
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
from datetime import datetime
import logging

# 導入本地模組
from ai_coach.core.overlay import StabilityDetector


logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析結果數據結構。"""
    timestamp: str
    ball_positions: Dict[str, str]  # 球號到位置的映射
    semantic_description: str  # 語意描述
    recommendation: str  # AI 建議
    confidence: float  # 置信度 (0-1)
    processing_time: float  # 處理時間（秒）


class CoordinateSemanticizer:
    """將 (x, y) 座標轉換為方位語意描述。"""
    
    def __init__(self, table_width: int = 1920, table_height: int = 1080):
        """
        初始化語意化器。
        
        Args:
            table_width: 球桌寬度（像素）
            table_height: 球桌高度（像素）
        """
        self.table_width = table_width
        self.table_height = table_height
        
        # 定義球桌的 9 個區域（3x3 網格）
        self.cols = self.table_width / 3
        self.rows = self.table_height / 3
        
        # 方位名稱映射
        self.region_names = {
            (0, 0): "左上角",
            (1, 0): "上中袋",
            (2, 0): "右上角",
            (0, 1): "左中位",
            (1, 1): "中心位",
            (2, 1): "右中位",
            (0, 2): "左下角",
            (1, 2): "底袋位",
            (2, 2): "右下角",
        }
        
        # 特殊位置名稱（邊線、袋口等）
        self.special_zones = {
            "left_pocket": {"name": "左邊袋", "x_range": (0, 0.15), "y_range": (0.4, 0.6)},
            "right_pocket": {"name": "右邊袋", "x_range": (0.85, 1.0), "y_range": (0.4, 0.6)},
            "top_left_pocket": {"name": "左上角袋", "x_range": (0, 0.1), "y_range": (0, 0.1)},
            "top_right_pocket": {"name": "右上角袋", "x_range": (0.9, 1.0), "y_range": (0, 0.1)},
            "bottom_left_pocket": {"name": "左下角袋", "x_range": (0, 0.1), "y_range": (0.9, 1.0)},
            "bottom_right_pocket": {"name": "右下角袋", "x_range": (0.9, 1.0), "y_range": (0.9, 1.0)},
        }
    
    def pixel_to_normalized(self, x: float, y: float) -> Tuple[float, float]:
        """
        將像素座標轉換為標準化座標 (0-1)。
        
        Args:
            x: 像素 X 座標
            y: 像素 Y 座標
            
        Returns:
            (norm_x, norm_y) 標準化座標
        """
        norm_x = max(0, min(1, x / self.table_width))
        norm_y = max(0, min(1, y / self.table_height))
        return norm_x, norm_y
    
    def get_special_zone(self, norm_x: float, norm_y: float) -> Optional[str]:
        """檢查是否在特殊區域（袋口等）。"""
        for zone_key, zone_info in self.special_zones.items():
            x_range = zone_info["x_range"]
            y_range = zone_info["y_range"]
            if x_range[0] <= norm_x <= x_range[1] and y_range[0] <= norm_y <= y_range[1]:
                return zone_info["name"]
        return None
    
    def coordinate_to_semantic(self, x: float, y: float) -> str:
        """
        將座標轉換為語意描述。
        
        Args:
            x: 像素 X 座標
            y: 像素 Y 座標
            
        Returns:
            語意描述字符串，如『左上角』、『中心位』等
        """
        norm_x, norm_y = self.pixel_to_normalized(x, y)
        
        # 優先檢查特殊位置（袋口）
        special = self.get_special_zone(norm_x, norm_y)
        if special:
            return special
        
        # 劃分為 3x3 網格
        col = int(norm_x * 3)
        row = int(norm_y * 3)
        col = min(2, col)
        row = min(2, row)
        
        return self.region_names.get((col, row), "未知位置")
    
    def balls_to_semantic_description(self, balls: List[Tuple[float, float]]) -> str:
        """
        將球的座標列表轉換為語意描述。
        
        Args:
            balls: 球的座標列表 [(x1, y1), (x2, y2), ...]
            
        Returns:
            語意描述，例如『3顆球聚集在中心位，1顆球在左下角』
        """
        if not balls:
            return "檯面上沒有球"
        
        # 統計每個區域的球數
        region_counts = defaultdict(int)
        for x, y in balls:
            semantic = self.coordinate_to_semantic(x, y)
            region_counts[semantic] += 1
        
        # 生成描述
        descriptions = []
        for region, count in sorted(region_counts.items(), key=lambda x: -x[1]):
            if count == 1:
                descriptions.append(f"1顆球在{region}")
            else:
                descriptions.append(f"{count}顆球在{region}")
        
        return "，".join(descriptions)


class AICoachManager:
    """
    AI Coach 管理器 - 整合靜止偵測、語意化、API 互動。
    
    流程：
    1. 接收 YOLO 球座標
    2. StabilityDetector 偵測靜止
    3. CoordinateSemanticizer 語意化
    4. 非同步發送到 vLLM API
    5. 存儲結果到全域變數
    """
    
    # 全域分析結果（線程安全）
    _global_results = {}
    _results_lock = threading.Lock()
    
    def __init__(
        self,
        vllm_api_url: str = "http://localhost:8000/v1/chat/completions",
        vllm_model: str = "meta-llama/Llama-2-7b-chat-hf",
        table_width: int = 1920,
        table_height: int = 1080,
        frame_rate: int = 60,
    ):
        """
        初始化 AI Coach Manager。
        
        Args:
            vllm_api_url: vLLM API 端點 URL
            vllm_model: vLLM 模型名稱
            table_width: 球桌寬度（像素）
            table_height: 球桌高度（像素）
            frame_rate: 幀率（用於計算幀與秒的轉換）
        """
        self.vllm_api_url = vllm_api_url
        self.vllm_model = vllm_model
        self.frame_rate = frame_rate
        
        # 初始化穩定性偵測器
        self.stability_detector = StabilityDetector()
        
        # 初始化座標語意化器
        self.semanticizer = CoordinateSemanticizer(table_width, table_height)
        
        # 線程池用於非同步請求
        self.thread_pool = []
        self.active_threads = set()
        
        # 設定日誌
        logger.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def update(self, current_balls: List[Tuple[float, float]], session_id: str = "default") -> bool:
        """
        更新球位置,並檢查是否觸發穩定偵測。
        
        Args:
            current_balls: 當前幀的球座標列表 [(x1, y1), (x2, y2), ...]
            session_id: 會話 ID（用於區分不同遊戲數據）
            
        Returns:
            是否觸發穩定偵測（可啟動分析）
        """
        # 檢查穩定性
        is_stable = self.stability_detector.is_stable(current_balls)
        
        if is_stable and current_balls:
            # 穩定觸發！開始分析
            logger.info(f"✅ Stability triggered for session {session_id}")
            self._trigger_analysis(current_balls, session_id)
        
        return is_stable
    
    def _trigger_analysis(self, balls: List[Tuple[float, float]], session_id: str):
        """
        觸發 AI 分析流程。
        
        Args:
            balls: 球座標列表
            session_id: 會話 ID
        """
        # 1. 語意化球位置
        semantic_desc = self.semanticizer.balls_to_semantic_description(balls)
        logger.info(f"Semantic description: {semantic_desc}")
        
        # 2. 構建提示詞
        prompt = self._build_prompt(balls, semantic_desc)
        
        # 3. 非同步發送 API 請求
        thread = threading.Thread(
            target=self._async_api_request,
            args=(prompt, balls, semantic_desc, session_id),
            daemon=True,
        )
        thread.start()
        self.active_threads.add(thread)
    
    def _build_prompt(self, balls: List[Tuple[float, float]], semantic_desc: str) -> str:
        """
        構建發送給 vLLM 的提示詞。
        
        Args:
            balls: 球座標列表
            semantic_desc: 語意描述
            
        Returns:
            提示詞字符串
        """
        coordinates_str = ", ".join([f"({x:.0f}, {y:.0f})" for x, y in balls])
        
        prompt = f"""
你是一個專業的台球教練。根據以下球位資訊，提供一個簡明而可行的擊球建議。

球位資訊：
- 語意位置：{semantic_desc}
- 座標數據：{coordinates_str}
- 球數量：{len(balls)}

請提供：
1. 當前局面分析（1-2句）
2. 最優進球建議（具體球號或推薦動作）
3. 位置控制提示（走位建議）

回應應簡潔且實用，便於在遊戲中快速參考。
"""
        return prompt.strip()
    
    def _async_api_request(
        self,
        prompt: str,
        balls: List[Tuple[float, float]],
        semantic_desc: str,
        session_id: str,
    ):
        """
        非同步發送 API 請求到 vLLM。
        
        Args:
            prompt: 提示詞
            balls: 球座標列表
            semantic_desc: 語意描述
            session_id: 會話 ID
        """
        start_time = time.time()
        
        try:
            logger.info(f"Sending request to vLLM API: {self.vllm_api_url}")
            
            # 構建請求
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.vllm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一個專業的台球教練。回複應簡潔且實用。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 256,
            }
            
            # 發送請求（設定超時）
            response = requests.post(
                self.vllm_api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                result_data = response.json()
                recommendation = result_data.get(
                    "choices", [{}]
                )[0].get("message", {}).get("content", "無回複")
                
                # 建立分析結果
                analysis_result = AnalysisResult(
                    timestamp=datetime.now().isoformat(),
                    ball_positions={f"ball_{i}": self.semanticizer.coordinate_to_semantic(x, y)
                                   for i, (x, y) in enumerate(balls)},
                    semantic_description=semantic_desc,
                    recommendation=recommendation,
                    confidence=0.85,
                    processing_time=processing_time,
                )
                
                # 儲存到全域變數
                self._set_global_result(session_id, asdict(analysis_result))
                
                logger.info(f"✅ API response received in {processing_time:.2f}s")
                logger.info(f"Recommendation: {recommendation[:100]}...")
            else:
                logger.error(f"❌ API error: {response.status_code} - {response.text}")
                self._set_global_result(session_id, {
                    "error": f"API error: {response.status_code}",
                    "timestamp": datetime.now().isoformat(),
                })
        
        except requests.exceptions.Timeout:
            logger.error("❌ API request timeout (30s)")
            self._set_global_result(session_id, {
                "error": "Request timeout",
                "timestamp": datetime.now().isoformat(),
            })
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Connection error: Cannot reach {self.vllm_api_url}")
            self._set_global_result(session_id, {
                "error": f"Cannot connect to {self.vllm_api_url}",
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error(f"❌ Unexpected error: {str(e)}")
            self._set_global_result(session_id, {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
    
    @classmethod
    def _set_global_result(cls, session_id: str, result: Dict[str, Any]):
        """
        線程安全地設置全域分析結果。
        
        Args:
            session_id: 會話 ID
            result: 結果字典
        """
        with cls._results_lock:
            cls._global_results[session_id] = result
    
    @classmethod
    def get_global_result(cls, session_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        線程安全地獲取全域分析結果供 UI 顯示。
        
        Args:
            session_id: 會話 ID
            
        Returns:
            結果字典或 None
        """
        with cls._results_lock:
            return cls._global_results.get(session_id)
    
    @classmethod
    def clear_result(cls, session_id: str = "default"):
        """清除特定會話的結果。"""
        with cls._results_lock:
            if session_id in cls._global_results:
                del cls._global_results[session_id]
    
    def get_detector_state(self) -> Dict[str, Any]:
        """獲取穩定性偵測器狀態（用於調試）。"""
        return self.stability_detector.get_state()
    
    def reset_detector(self):
        """重置穩定性偵測器。"""
        self.stability_detector.reset()
