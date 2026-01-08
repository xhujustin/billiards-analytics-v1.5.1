"""
Enhanced Pool Tracker with Full Physics Simulation
整合 poolShotPredictor.py 的完整邏輯
遵照 v1.5 技術文檔規範
"""

import math
from typing import Optional, List, Tuple, Dict, Any

import config
import cv2
import numpy as np
from ultralytics import YOLO


class PoolTracker:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = config.MODEL_PATH

        # --- 1. 初始化 YOLO 模型 ---
        print(f"✅ Loading YOLO model from: {model_path}")
        self.model = YOLO(model_path)

        # --- 2. 系統參數 ---
        self.conf_thr = config.CONF_THR
        self.iou_thr = config.IOU_THR
        self.hsv_lower = np.array(config.HSV_LOWER)
        self.hsv_upper = np.array(config.HSV_UPPER)
        self.current_table_color = config.TABLE_CLOTH_COLOR

        # --- 3. 狀態變數 ---
        self.table_roi: Optional[List[int]] = None  # [x, y, w, h]
        self.holes: List[List[int]] = []  # 球袋位置（全圖座標）
        self.hole_bboxes: List[List[int]] = []  # 球袋碰撞箱 [x1,y1,x2,y2]
        self.table_rects: List[List[int]] = []  # 球桌邊界

        # 擊球預測狀態
        self.last_point_history: List[List[int]] = []
        self.radius_mean: List[int] = []
        self.shot_points: List[List[int]] = []
        self.possibility: List[Optional[Dict]] = []
        self.prediction_mode = True

        # --- 4. 顏色映射 (從 poolShotPredictor.py) ---
        self.COLOR_TO_NUM = {
            "Yellow": (1, 9),
            "Blue": (2, 10),
            "Red": (3, 11),
            "Purple": (4, 12),
            "Orange": (5, 13),
            "Green": (6, 14),
            "Brown": (7, 15),
        }

        self.COLORS_BGR = {
            "Yellow": (0, 220, 255),
            "Blue": (255, 120, 0),
            "Red": (0, 0, 230),
            "Purple": (180, 0, 180),
            "Orange": (0, 140, 255),
            "Green": (0, 180, 0),
            "Brown": (30, 60, 120),
            "Black": (0, 0, 0),
            "White": (255, 255, 255),
            "Unknown": (160, 160, 160),
        }

    # ==================== 球桌顏色設定 ====================
    def update_table_color(self, color_name: str) -> bool:
        """
        更新球桌布料顏色設定
        color_name: 顏色名稱 (green, gray, blue, pink, purple, custom)
        返回: 成功與否
        """
        if color_name not in config.TABLE_COLOR_PRESETS:
            print(f"⚠️  Invalid color name: {color_name}")
            return False

        color_preset = config.TABLE_COLOR_PRESETS[color_name]
        self.hsv_lower = color_preset["hsv_lower"].copy()
        self.hsv_upper = color_preset["hsv_upper"].copy()
        self.current_table_color = color_name

        # 清除之前偵測到的球桌區域，強制重新偵測
        self.table_roi = None
        self.holes = []
        self.hole_bboxes = []
        self.table_rects = []

        print(f"✅ Table color updated to: {color_preset['name']} ({color_name})")
        print(f"   HSV_LOWER: {self.hsv_lower}, HSV_UPPER: {self.hsv_upper}")
        return True

    def update_custom_hsv(self, hsv_lower: List[int], hsv_upper: List[int]) -> bool:
        """
        更新自訂 HSV 範圍
        hsv_lower: HSV 下限 [H, S, V]
        hsv_upper: HSV 上限 [H, S, V]
        返回: 成功與否
        """
        try:
            self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
            self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
            self.current_table_color = "custom"

            # 清除之前偵測到的球桌區域，強制重新偵測
            self.table_roi = None
            self.holes = []
            self.hole_bboxes = []
            self.table_rects = []

            print(f"✅ Custom HSV range updated")
            print(f"   HSV_LOWER: {self.hsv_lower}, HSV_UPPER: {self.hsv_upper}")
            return True
        except Exception as e:
            print(f"⚠️  Failed to update custom HSV: {e}")
            return False

    # ==================== 球桌偵測 ====================
    def detect_table(self, frame: np.ndarray) -> Tuple[bool, Optional[List[int]]]:
        """
        使用 HSV 綠色檢測找出球桌區域
        返回: (成功與否, 球桌bbox [x,y,w,h])
        """
        print(f"🔍 Detecting table... Frame shape: {frame.shape}")
        print(f"   HSV_LOWER: {self.hsv_lower}, HSV_UPPER: {self.hsv_upper}")
        print(f"   TABLE_MIN_AREA: {config.TABLE_MIN_AREA}")

        hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_img, self.hsv_lower, self.hsv_upper)

        # 計算綠色像素比例
        green_pixels = np.count_nonzero(mask)
        total_pixels = mask.size
        green_ratio = green_pixels / total_pixels
        print(f"   Green pixels: {green_pixels} / {total_pixels} ({green_ratio*100:.2f}%)")

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        print(f"   Found {len(contours)} contours")

        max_area = 0.0
        best_rect = None
        all_areas = []

        for contour in contours:
            area = cv2.contourArea(contour)
            all_areas.append(area)
            if area > config.TABLE_MIN_AREA:
                if area > max_area:
                    max_area = area
                    best_rect = cv2.boundingRect(contour)

        if all_areas:
            all_areas.sort(reverse=True)
            print(f"   Top 3 areas: {all_areas[:3]}")
            print(f"   Max area: {max_area}, Min required: {config.TABLE_MIN_AREA}")

        if best_rect:
            x, y, w, h = best_rect
            self.table_roi = [x, y, w, h]
            self.table_rects = [[x, y, w, h]]

            # 定義 6 個球袋中心點（全圖座標）
            self.holes = [
                [x + 52, y + 52],                    # 左上
                [x + 52, y + h - 52],                # 左下
                [x + w - 52, y + 52],                # 右上
                [x + w - 52, y + h - 52],            # 右下
                [x + (w - 12) // 2, y + 40],         # 中上
                [x + (w - 12) // 2, y + h - 40],     # 中下
            ]

            # 定義球袋碰撞箱（半徑 50px）
            self.hole_bboxes = []
            for hole in self.holes:
                cx, cy = hole
                radius = 50
                x1, y1 = cx - radius, cy - radius
                x2, y2 = cx + radius, cy + radius
                self.hole_bboxes.append([x1, y1, x2, y2])

            print(f"✅ Table detected: x={x}, y={y}, w={w}, h={h}")
            return True, [x, y, w, h]

        # 備用方案：如果找不到綠色區域，使用整個畫面
        print(f"⚠️  No green table found, using entire frame as fallback")
        h, w = frame.shape[:2]
        # 使用畫面的 90% 作為球桌區域（排除邊緣）
        margin = 50
        x, y = margin, margin
        w_table = w - 2 * margin
        h_table = h - 2 * margin

        self.table_roi = [x, y, w_table, h_table]
        self.table_rects = [[x, y, w_table, h_table]]

        # 定義 6 個球袋中心點（全圖座標）
        self.holes = [
            [x + 52, y + 52],                    # 左上
            [x + 52, y + h_table - 52],          # 左下
            [x + w_table - 52, y + 52],          # 右上
            [x + w_table - 52, y + h_table - 52],# 右下
            [x + (w_table - 12) // 2, y + 40],   # 中上
            [x + (w_table - 12) // 2, y + h_table - 40],  # 中下
        ]

        # 定義球袋碰撞箱（半徑 50px）
        self.hole_bboxes = []
        for hole in self.holes:
            cx, cy = hole
            radius = 50
            x1, y1 = cx - radius, cy - radius
            x2, y2 = cx + radius, cy + radius
            self.hole_bboxes.append([x1, y1, x2, y2])

        print(f"🔄 Using fallback table: x={x}, y={y}, w={w_table}, h={h_table}")
        return True, [x, y, w_table, h_table]

    # ==================== 主處理函式 ====================
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        每幀處理主邏輯：
        1. 偵測球桌（首次）
        2. 裁切 ROI
        3. YOLO 推論
        4. 解析球體並進行物理預測
        5. 繪製結果
        """
        # 1. 檢查球桌
        if not self.table_roi:
            success, _ = self.detect_table(frame)
            if not success:
                print("⚠️  Table not detected, scanning...")
                return frame, {"status": "scanning_table"}
            else:
                print(f"✅ Table detected: {self.table_roi}")

        # 2. 裁切 ROI
        assert self.table_roi is not None
        tx, ty, tw, th = self.table_roi
        roi_img = frame[ty:ty+th, tx:tx+tw].copy()

        # 3. YOLO 推論
        results = self.model.predict(
            roi_img,
            imgsz=config.IMG_SIZE,
            conf=self.conf_thr,
            iou=self.iou_thr,
            verbose=False,
            stream=False
        )

        # 4. 解析球體
        data_packet = self._analyze_balls(results, roi_img, offset=(tx, ty))

        # 5. 繪製到原圖
        final_frame = frame.copy()
        self._draw_annotations(final_frame, data_packet)

        return final_frame, data_packet

    # ==================== 球體解析 ====================
    def _analyze_balls(self, results, roi_img: np.ndarray, offset: Tuple[int, int]) -> Dict[str, Any]:
        """
        整合 poolShotPredictor.py 的 machinelearning() 邏輯
        """
        tx, ty = offset
        white_balls: List[List] = []
        color_balls: List[List] = []
        cue_pos: Optional[List[int]] = None
        cue_center: Optional[Tuple[int, int]] = None

        # 收集所有球體
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                w, h = x2 - x1, y2 - y1
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]

                # 轉換為全圖座標
                gx, gy = x1 + tx, y1 + ty

                if label == "white-ball":
                    white_balls.append([gx, gy, w, h, conf])
                elif label == "color-ball":
                    radius = max(1, min(w, h) // 2)
                    # 執行 HSV 顏色檢測
                    color_info = self._detect_ball_color_hsv(roi_img, [x1, y1, w, h])
                    ball_num = self._classify_ball_number(color_info)

                    color_balls.append([gx, gy, w, h, radius, conf, color_info, ball_num])
                elif label == "cue" and not cue_pos:
                    cue_pos = [gx, gy, w, h]
                    cue_center = (gx + w // 2, gy + h // 2)

        # 選擇主要白球（信心度最高）
        white_primary: Optional[List[int]] = None
        if white_balls:
            white_balls.sort(key=lambda t: t[4], reverse=True)
            x, y, w, h, _ = white_balls[0]
            white_primary = [x, y, w, h]

        # 選擇主要彩球
        color_primary: Optional[List] = None
        if color_balls:
            if cue_center:
                # 若有球桿，選擇離球桿最近的彩球
                def dist2(ball):
                    bx, by, bw, bh = ball[0], ball[1], ball[2], ball[3]
                    cx, cy = bx + bw // 2, by + bh // 2
                    return (cx - cue_center[0])**2 + (cy - cue_center[1])**2
                color_balls.sort(key=dist2)
            else:
                # 否則選信心度最高
                color_balls.sort(key=lambda t: t[5], reverse=True)

            color_primary = color_balls[0]

        # 執行物理預測
        prediction_result = None
        if white_primary and color_primary and cue_pos:
            shot_point = self._find_shot_point(cue_pos, white_primary)
            prediction_result = self._pool_shot_prediction(shot_point, white_primary, color_primary)

        # 構造回傳數據包（遵照 v1.5 規範）
        return {
            "status": "analyzing",
            "white_ball": white_primary,
            "balls": [
                {
                    "x": ball[0],
                    "y": ball[1],
                    "w": ball[2],
                    "h": ball[3],
                    "radius": ball[4],
                    "conf": ball[5],
                    "color": ball[6].get("label", "Unknown"),
                    "style": ball[6].get("style", "Unknown"),
                    "number": ball[7],
                }
                for ball in color_balls
            ],
            "cue": cue_pos,
            "prediction": prediction_result,
            "table_roi": self.table_roi,
            "holes": self.holes,
        }

    # ==================== HSV 顏色檢測 (from poolShotPredictor.py) ====================
    def _safe_crop(self, img: np.ndarray, x: int, y: int, w: int, h: int):
        """安全裁切，避免越界"""
        H, W = img.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return None, (0, 0, 0, 0)
        return img[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)

    def _detect_ball_color_hsv(self, roi_img: np.ndarray, bbox: List[int]) -> Dict[str, Any]:
        """
        使用 HSV 色彩空間辨識球的顏色和條紋/實心
        bbox: [x, y, w, h] (在 roi_img 座標系)
        返回: {'label', 'style', 'hue', 'white_ratio', 'black_ratio'}
        """
        x, y, w, h = map(int, bbox)
        patch, (x0, y0, w2, h2) = self._safe_crop(roi_img, x, y, w, h)
        if patch is None or patch.size == 0:
            return {"label": "Unknown", "style": "Unknown", "hue": None, "white_ratio": 0.0, "black_ratio": 0.0}

        # 建立圓形遮罩（聚焦球中心）
        mask = np.zeros(patch.shape[:2], dtype=np.uint8)
        r = int(0.48 * min(w2, h2))
        cx, cy = w2 // 2, h2 // 2
        cv2.circle(mask, (cx, cy), r, 255, -1)

        # 轉 HSV
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        Hc, Sc, Vc = cv2.split(hsv)

        # 有效像素（排除太暗和過亮）
        valid = (mask == 255) & (Vc > 30) & (Vc < 250)

        # 白/黑粗篩
        white_mask = valid & (Sc < 40) & (Vc > 180)
        black_mask = valid & (Vc < 50)
        color_core = valid & ~white_mask & ~black_mask

        n_valid = np.count_nonzero(valid)
        if n_valid < 50:
            return {"label": "Unknown", "style": "Unknown", "hue": None, "white_ratio": 0.0, "black_ratio": 0.0}

        white_ratio = np.count_nonzero(white_mask) / n_valid
        black_ratio = np.count_nonzero(black_mask) / n_valid
        color_ratio = np.count_nonzero(color_core) / n_valid

        # 白球
        if white_ratio > 0.70 and color_ratio < 0.10:
            return {"label": "White", "style": "Cue", "hue": None, "white_ratio": float(white_ratio), "black_ratio": float(black_ratio)}

        # 黑球
        if black_ratio > 0.60:
            return {"label": "Black", "style": "Solid", "hue": None, "white_ratio": float(white_ratio), "black_ratio": float(black_ratio)}

        if np.count_nonzero(color_core) < 30:
            label = "White" if white_ratio > 0.4 else ("Black" if black_ratio > 0.4 else "Unknown")
            style = "Cue" if label == "White" else ("Solid" if label == "Black" else "Unknown")
            return {"label": label, "style": style, "hue": None, "white_ratio": float(white_ratio), "black_ratio": float(black_ratio)}

        # 計算加權 hue
        Hf = Hc[color_core].astype(np.float32)
        Sf = Sc[color_core].astype(np.float32) / 255.0
        Vf = Vc[color_core].astype(np.float32) / 255.0
        wgt = (Sf * Vf) + 1e-6
        hue_mean = float(np.sum(Hf * wgt) / np.sum(wgt))

        # Hue → 顏色名稱
        color_name = self._hue_to_name(hue_mean, Vc[color_core])

        # Stripe vs Solid
        style = "Stripe" if (white_ratio > 0.35 and color_ratio > 0.15 and color_name not in ["White", "Black", "Unknown"]) else "Solid"

        return {
            "label": color_name,
            "style": style,
            "hue": hue_mean,
            "white_ratio": float(white_ratio),
            "black_ratio": float(black_ratio),
        }

    def _hue_to_name(self, h: float, vc_pixels: np.ndarray) -> str:
        """Hue 值轉顏色名稱"""
        if h < 0 or h > 180:
            return "Unknown"
        # 紅色跨兩端
        if (h <= 10) or (h >= 160):
            return "Red"
        if 10 < h <= 25:
            return "Brown" if np.median(vc_pixels) < 140 else "Orange"
        if 25 < h <= 40:
            return "Yellow"
        if 40 < h <= 80:
            return "Green"
        if 80 < h <= 130:
            return "Blue"
        if 130 < h <= 155:
            return "Purple"
        if 155 < h < 160:
            return "Red"
        return "Unknown"

    def _classify_ball_number(self, color_info: Dict[str, Any]) -> Optional[int]:
        """根據顏色和條紋/實心分類球號（1-15）"""
        label = color_info.get("label", "Unknown")
        style = color_info.get("style", "Unknown")

        if label == "White" or style == "Cue":
            return 0
        if label == "Black":
            return 8

        if label in self.COLOR_TO_NUM:
            solid, stripe = self.COLOR_TO_NUM[label]
            if style == "Stripe":
                return stripe
            elif style == "Solid":
                return solid
            else:
                # 用白色比例猜測
                if color_info.get("white_ratio", 0) > 0.30:
                    return stripe
                else:
                    return solid

        return None

    # ==================== 物理預測 (from poolShotPredictor.py) ====================
    def _find_shot_point(self, cue_pos: List[int], white_ball: List[int]) -> List[int]:
        """計算擊球點（球桿接觸白球的位置）"""
        cue_points = []
        whiteBallX = white_ball[0] + white_ball[2] // 2
        whiteBallY = white_ball[1] + white_ball[3] // 2

        self.radius_mean.append((cue_pos[2] // 2 + cue_pos[3] // 2) // 2)
        radius = sum(self.radius_mean) // max(len(self.radius_mean), 1)

        LX = cue_pos[0] + cue_pos[2] // 2
        LY = cue_pos[1] + cue_pos[3] // 2

        for the in range(0, 360):
            sinus, cosinus = self._find_angle(the)
            DX = int(cosinus * radius)
            DY = int(sinus * radius)
            cue_points.append([LX + DX, LY + DY])

        min_gap = 1000000
        shot_point = [LX, LY]
        for cue_point in cue_points:
            gap = math.hypot(whiteBallX - cue_point[0], whiteBallY - cue_point[1])
            if gap < min_gap:
                min_gap = gap
                shot_point = cue_point

        self.shot_points.append(shot_point)
        sumX = sum(p[0] for p in self.shot_points)
        sumY = sum(p[1] for p in self.shot_points)
        return [sumX // len(self.shot_points), sumY // len(self.shot_points)]

    def _find_angle(self, deg: float) -> Tuple[float, float]:
        """計算角度的 sin, cos"""
        theta = math.radians(deg)
        sinus = math.sin(theta)
        cosinus = math.cos(theta)
        if abs(sinus) < 1e-15:
            sinus = 0
        if abs(cosinus) < 1e-15:
            cosinus = 0
        return sinus, cosinus

    def _find_line(self, p1: List[int], p2: List[int]) -> Tuple[Optional[float], float]:
        """計算兩點間直線的斜率和截距"""
        x1, y1 = p1
        x2, y2 = p2
        try:
            m = (y2 - y1) / (x2 - x1)
        except ZeroDivisionError:
            m = (y2 - y1) / (x2 - x1 + 1)
        c = y1 - (m * x1)
        return m, c

    def _collision(self, white_ball: List[int], color_ball: List) -> Tuple[bool, List[int]]:
        """檢測白球與彩球碰撞"""
        white_ball_list = []
        color_ball_list = []

        # 白球周圍點
        radius = (white_ball[2] - white_ball[0]) // 2
        LX = white_ball[0] + (white_ball[2] - white_ball[0]) // 2
        LY = white_ball[1] + (white_ball[3] - white_ball[1]) // 2
        for the in range(0, 360):
            sinus, cosinus = self._find_angle(the)
            DX = int(cosinus * radius)
            DY = int(sinus * radius)
            white_ball_list.append([LX + DX, LY + DY])

        # 彩球周圍點
        radius = color_ball[4]
        LX = color_ball[0] + color_ball[2] // 2
        LY = color_ball[1] + color_ball[3] // 2
        for the in range(0, 360):
            sinus, cosinus = self._find_angle(the)
            DX = int(cosinus * radius)
            DY = int(sinus * radius)
            color_ball_list.append([LX + DX, LY + DY])

        # 找交集
        colls_points = []
        for point in white_ball_list:
            if point in color_ball_list:
                colls_points.append(point)

        if len(colls_points) > 0:
            xPoint = sum(p[0] for p in colls_points) // len(colls_points)
            yPoint = sum(p[1] for p in colls_points) // len(colls_points)
            return True, [xPoint, yPoint]

        return False, []

    def _bounce_detection(self, point: List[int], radius: int) -> Tuple[Tuple[int, int, int], bool]:
        """檢測球是否進袋"""
        color = (80, 145, 75)
        in_hole = False

        for hole in self.hole_bboxes:
            p = point[0] - radius
            q = point[1] - radius
            r = point[0] + radius
            s = point[1] + radius
            if p >= hole[0] and q >= hole[1] and r <= hole[2] and s <= hole[3]:
                in_hole = True
                color = (80, 145, 75)
                break

        return color, in_hole

    def _path_line(self, colls_point: List[int], color_ball: List, paths: List[List[int]]) -> Tuple[List[List[int]], Tuple, bool]:
        """計算彩球反彈路徑"""
        color = (80, 145, 75)
        in_hole = False

        color_ball_center = [color_ball[0] + color_ball[2] // 2, color_ball[1] + color_ball[3] // 2]
        m2, c2 = self._find_line(colls_point, color_ball_center)

        if not self.table_rects:
            return paths, color, in_hole

        for rects in self.table_rects:
            if colls_point[0] > color_ball_center[0]:
                xLast = rects[0] + 40
            else:
                xLast = rects[0] + rects[2] - 40

            for i in range(0, 2):  # 最多反彈2次
                x2 = xLast
                y2 = int((m2 * x2) + c2)

                # 邊界限制
                if y2 >= rects[1] + rects[3] - 40:
                    y2 = rects[1] + rects[3] - 40
                    x2 = int((y2 - c2) / m2) if m2 != 0 else x2
                if y2 <= rects[1] + 40:
                    y2 = rects[1] + 40
                    x2 = int((y2 - c2) / m2) if m2 != 0 else x2
                if x2 >= rects[0] + rects[2] - 40:
                    x2 = rects[0] + rects[2] - 40
                    y2 = int((m2 * x2) + c2)
                    xLast = rects[0] + 40
                if x2 <= rects[0] + 40:
                    x2 = rects[0] + 40
                    y2 = int((m2 * x2) + c2)
                    xLast = rects[0] + rects[2] - 40

                paths.append([x2, y2])
                color, in_hole = self._bounce_detection(paths[-1], 6)

                if in_hole:
                    return paths, color, in_hole
                else:
                    m2 = -m2
                    c2 = y2 - (m2 * x2)

        return paths, color, in_hole

    def _pool_shot_prediction(self, shot_point: List[int], white_ball: List[int], color_ball: List) -> Optional[Dict]:
        """完整的撞球預測邏輯"""
        try:
            # 1. 白球射線方程
            m1, c1 = self._find_line(
                shot_point,
                [white_ball[0] + white_ball[2] // 2, white_ball[1] + white_ball[3] // 2]
            )

            points = []
            xLast = color_ball[0] + color_ball[2] // 2
            section = 1 if xLast >= white_ball[0] + white_ball[2] // 2 else -1

            for x in range(white_ball[0] + white_ball[2] // 2, xLast, section):
                y = int((m1 * x) + c1)
                points.append([x, y])

            # 2. 碰撞檢測
            for point in points:
                p = point[0] - white_ball[2] // 2
                q = point[1] - white_ball[3] // 2
                r = point[0] + white_ball[2] // 2
                s = point[1] + white_ball[3] // 2
                box = [p, q, r, s]

                color_ball_point = [
                    color_ball[0],
                    color_ball[1],
                    color_ball[0] + color_ball[2],
                    color_ball[1] + color_ball[3],
                    color_ball[4] if len(color_ball) > 4 else 0
                ]

                colls, colls_point = self._collision(box, color_ball_point)

                if colls:
                    # 3. 計算彩球路徑
                    paths = [[color_ball[0] + color_ball[2] // 2, color_ball[1] + color_ball[3] // 2]]
                    paths, color_result, in_hole = self._path_line(colls_point, color_ball, paths)

                    # 4. 取得彩球顏色資訊
                    ball_color_info = color_ball[6] if len(color_ball) > 6 else {"label": "Unknown", "style": "Unknown"}
                    ball_number = color_ball[7] if len(color_ball) > 7 else None

                    return {
                        "prediction": in_hole,
                        "paths": paths,
                        "color": color_result,
                        "collision_point": colls_point,
                        "ball_color": f"{ball_color_info.get('label', 'Unknown')} - {ball_color_info.get('style', 'Unknown')}",
                        "ball_number": ball_number,
                        "ball_color_meta": ball_color_info,
                    }

        except (TypeError, IndexError, ZeroDivisionError) as e:
            print(f"⚠️ Prediction error: {e}")
            return None

        return None

    # ==================== 繪製結果 ====================
    def _draw_annotations(self, img: np.ndarray, data: Dict[str, Any]):
        """在影像上繪製所有標註"""
        # 1. 繪製球桌框
        if self.table_roi:
            tx, ty, tw, th = self.table_roi
            cv2.rectangle(img, (tx, ty), (tx + tw, ty + th), (0, 255, 0), 2)

        # 2. 繪製球袋
        for hole in self.holes:
            cv2.circle(img, tuple(hole), 50, (255, 0, 0), 2)

        # 3. 繪製白球
        if data.get("white_ball"):
            x, y, w, h = data["white_ball"]
            cx, cy = x + w // 2, y + h // 2
            r = max(1, min(w, h) // 2)
            cv2.circle(img, (cx, cy), r + 10, (255, 255, 255), 4)
            cv2.putText(img, "WHITE", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # 4. 繪製彩球（含球號和顏色）
        for ball in data.get("balls", []):
            x, y, w, h = ball["x"], ball["y"], ball["w"], ball["h"]
            cx, cy = x + w // 2, y + h // 2
            r = ball["radius"]

            color_name = ball.get("color", "Unknown")
            ball_num = ball.get("number")
            style = ball.get("style", "Unknown")

            # 選擇顏色
            bgr = self.COLORS_BGR.get(color_name, (160, 160, 160))

            # 繪製圓圈
            cv2.circle(img, (cx, cy), r + 10, bgr, 4)

            # 繪製標籤
            if ball_num is not None:
                label = f"#{ball_num} {color_name[:3]} {style[:3]}"
            else:
                label = f"{color_name[:5]} {style[:3]}"

            cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr, 2)

        # 5. 繪製球桿
        if data.get("cue"):
            x, y, w, h = data["cue"]
            cx, cy = x + w // 2, y + h // 2
            cv2.putText(img, "CUE", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 6. 繪製預測路徑
        prediction = data.get("prediction")
        if prediction:
            paths = prediction.get("paths", [])
            in_hole = prediction.get("prediction", False)

            # 繪製路徑線
            if len(paths) > 1:
                for i in range(len(paths) - 1):
                    cv2.line(img, tuple(paths[i]), tuple(paths[i + 1]), (80, 145, 75), 3)
                    cv2.circle(img, tuple(paths[i]), 8, (80, 145, 75), -1)

            # 顯示預測結果
            text = "PREDICTION: IN" if in_hole else "PREDICTION: OUT"
            text_color = (0, 255, 0) if in_hole else (64, 97, 200)
            cv2.putText(img, text, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, text_color, 3)

            # 顯示球號
            if prediction.get("ball_number"):
                ball_text = f"Ball #{prediction['ball_number']}"
                cv2.putText(img, ball_text, (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
