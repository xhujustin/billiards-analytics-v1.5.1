"""
錄影管理器 - 處理遊戲錄影和事件記錄

遵照 v1.5 技術指南:
- 錄製後端合成的 burn-in 串流
- 記錄遊戲事件時間軸
- 檔案結構化儲存
- 預留回放分析接口
- 自動同步至資料庫
"""

import os
import json
import cv2
import time
import subprocess
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Full, Queue

# 導入資料庫
from database.database import Database


@dataclass
class RecordingMetadata:
    """錄影元資料"""
    game_id: str
    game_type: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0
    players: Optional[List[str]] = None
    final_score: Optional[List[int]] = None
    winner: Optional[str] = None
    total_rounds: int = 0
    video_resolution: str = "1280x720"
    video_fps: int = 30
    file_size_mb: float = 0


class RecordingManager:
    """遊戲錄影管理器"""
    
    def __init__(self, recordings_dir: str = "./recordings", db_path: str = "./data/recordings.db"):
        """
        初始化錄影管理器
        
        Args:
            recordings_dir: 錄影檔案儲存目錄
            db_path: 資料庫路徑
        """
        self.recordings_dir = recordings_dir
        os.makedirs(recordings_dir, exist_ok=True)
        
        # 初始化資料庫連接
        self.db = Database(db_path)
        
        self.current_recording: Optional[Dict[str, Any]] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.events_file: Optional[Any] = None
        self.recording_lock = threading.Lock()
        self.postprocess_executor = ThreadPoolExecutor(max_workers=1)
        self.postprocess_status: Dict[str, Dict[str, Any]] = {}
        self.postprocess_lock = threading.Lock()
        self.frame_queue: Queue = Queue(maxsize=90)
        self.writer_thread: Optional[threading.Thread] = None
        self.writer_stop_event = threading.Event()
        self.writer_resolution: tuple = (1280, 720)
        self.dropped_frames = 0
        self.written_frame_count = 0
    
    def start_recording(
        self, 
        game_type: str,
        players: Optional[List[str]] = None,
        resolution: tuple = (1280, 720),
        fps: int = 30
    ) -> str:
        """
        開始錄影
        
        Args:
            game_type: 遊戲類型 ("nine_ball", "practice_single", "practice_pattern")
            players: 玩家名單 (可選)
            resolution: 影片解析度
            fps: 影片幀率
        
        Returns:
            game_id: 遊戲ID
        
        Raises:
            RuntimeError: 如果已經在錄影中
        """
        with self.recording_lock:
            if self.current_recording:
                raise RuntimeError("Already recording")
            
            # 生成遊戲 ID (時間戳)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            game_id = f"game_{timestamp}"
            
            # 根據遊戲類型建立分類資料夾
            category_path = self._get_category_path(game_type)
            recording_dir = os.path.join(self.recordings_dir, category_path, game_id)
            os.makedirs(recording_dir, exist_ok=True)
            
            # 初始化影片寫入
            # 使用 mp4v 編碼（OpenCV 兼容性好），錄影完成後會自動轉換為 H.264
            video_path = os.path.join(recording_dir, "video.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(video_path, fourcc, fps, resolution)
            
            if not self.video_writer.isOpened():
                raise RuntimeError(f"Failed to open video writer: {video_path}")
            
            # 初始化事件日誌
            events_path = os.path.join(recording_dir, "events.jsonl")
            self.events_file = open(events_path, 'w', encoding='utf-8')
            
            # 記錄元資料
            metadata = RecordingMetadata(
                game_id=game_id,
                game_type=game_type,
                start_time=datetime.now().isoformat(),
                players=players or [],
                video_resolution=f"{resolution[0]}x{resolution[1]}",
                video_fps=fps
            )
            
            self.current_recording = {
                "game_id": game_id,
                "recording_dir": recording_dir,
                "metadata": metadata,
                "start_time": time.time(),
                "frame_count": 0
            }
            self.writer_resolution = resolution
            self.dropped_frames = 0
            self.written_frame_count = 0
            self.frame_queue = Queue(maxsize=90)
            self.writer_stop_event.clear()
            self.writer_thread = threading.Thread(
                target=self._writer_loop,
                name=f"RecordingWriter-{game_id}",
                daemon=True,
            )
            self.writer_thread.start()

            try:
                self.db.insert_recording({
                    "game_id": metadata.game_id,
                    "game_type": metadata.game_type,
                    "start_time": metadata.start_time,
                    "end_time": None,
                    "duration_seconds": None,
                    "player1_name": metadata.players[0] if metadata.players and len(metadata.players) > 0 else None,
                    "player2_name": metadata.players[1] if metadata.players and len(metadata.players) > 1 else None,
                    "winner": None,
                    "player1_score": 0,
                    "player2_score": 0,
                    "target_rounds": 0,
                    "video_path": video_path,
                    "video_resolution": metadata.video_resolution,
                    "video_fps": metadata.video_fps,
                    "file_size_mb": 0.0,
                })
            except Exception as e:
                print(f"[Recording] Initial database sync warning: {e}")
            
            # 記錄開始事件
            self._log_event("game_start", {
                "game_type": game_type,
                "players": players or []
            })
            
            print(f"[Recording] Started: {game_id} (Category: {category_path})")
            return game_id
    
    def _get_category_path(self, game_type: str) -> str:
        """
        根據遊戲類型取得分類資料夾路徑
        
        Args:
            game_type: 遊戲類型
        
        Returns:
            分類路徑 (例如: "practice/single", "game/nine_ball")
        """
        # 練習模式分類
        if game_type == "practice_single":
            return os.path.join("practice", "single")
        elif game_type == "practice_pattern":
            return os.path.join("practice", "pattern")
        elif game_type == "practice_accuracy":
            return os.path.join("practice", "accuracy")
        # 遊戲模式分類
        elif game_type == "nine_ball":
            return os.path.join("game", "nine_ball")
        elif game_type == "eight_ball":
            return os.path.join("game", "eight_ball")
        elif game_type == "ten_ball":
            return os.path.join("game", "ten_ball")
        elif game_type == "snooker":
            return os.path.join("game", "snooker")
        # 未知類型使用 other
        else:
            return os.path.join("other", game_type)
    
    def write_frame(self, frame) -> bool:
        """
        寫入一幀影像
        
        Args:
            frame: OpenCV 影像 (numpy array)
        
        Returns:
            是否成功寫入
        """
        with self.recording_lock:
            if not self.current_recording or not self.video_writer:
                return False

        try:
            self.frame_queue.put_nowait(frame.copy())
            return True
        except Full:
            self.dropped_frames += 1
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.task_done()
                self.frame_queue.put_nowait(frame.copy())
                return True
            except Exception:
                return False
        except Exception as e:
            print(f"[Recording] Frame enqueue error: {e}")
            return False

    def _writer_loop(self) -> None:
        """背景寫入錄影幀，避免主影像迴圈等待 VideoWriter。"""
        while not self.writer_stop_event.is_set() or not self.frame_queue.empty():
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except Exception:
                continue

            try:
                writer = self.video_writer
                if writer is None:
                    continue

                target_w, target_h = self.writer_resolution
                if frame.shape[1] != target_w or frame.shape[0] != target_h:
                    frame = cv2.resize(frame, (target_w, target_h))

                writer.write(frame)
                with self.recording_lock:
                    self.written_frame_count += 1
                    if self.current_recording:
                        self.current_recording["frame_count"] += 1
            except Exception as e:
                print(f"[Recording] Background frame write error: {e}")
            finally:
                self.frame_queue.task_done()
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        記錄遊戲事件
        
        Args:
            event_type: 事件類型
            data: 事件數據
        """
        self._log_event(event_type, data)
    
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """內部事件記錄方法"""
        if not self.events_file:
            return
        
        event = {
            "timestamp": time.time(),
            "event": event_type,
            "data": data
        }
        
        try:
            self.events_file.write(json.dumps(event, ensure_ascii=False) + '\n')
            self.events_file.flush()
        except Exception as e:
            print(f"[Recording] Event log error: {e}")
    
    def stop_recording(
        self,
        final_score: Optional[List[int]] = None,
        winner: Optional[str] = None,
        total_rounds: int = 0
    ) -> Dict[str, Any]:
        """
        停止錄影並保存。

        採用快回應策略：
        - 同步階段僅釋放 writer / file 與快照必要資訊
        - 縮圖、codec 檢查、FFmpeg、DB 同步改由背景執行
        """
        with self.recording_lock:
            if not self.current_recording:
                raise RuntimeError("No active recording")

            self._log_event("game_end", {
                "winner": winner,
                "final_score": final_score,
                "total_rounds": total_rounds
            })

            current_recording = self.current_recording
            recording_dir = current_recording["recording_dir"]
            metadata = current_recording["metadata"]
            video_writer = self.video_writer
            events_file = self.events_file

            self.current_recording = None
            self.events_file = None
            writer_thread = self.writer_thread
            self.writer_thread = None

        self.writer_stop_event.set()
        if writer_thread:
            writer_thread.join(timeout=5.0)
        with self.recording_lock:
            frame_count = self.written_frame_count
            self.video_writer = None
        if video_writer:
            video_writer.release()
        if events_file:
            events_file.close()

        metadata.end_time = datetime.now().isoformat()
        metadata.duration_seconds = time.time() - current_recording["start_time"]
        metadata.final_score = final_score
        metadata.winner = winner
        metadata.total_rounds = total_rounds

        game_id = current_recording["game_id"]
        with self.postprocess_lock:
            self.postprocess_status[game_id] = {
                "status": "queued",
                "started_at": time.time(),
                "recording_dir": recording_dir,
            }

        self.postprocess_executor.submit(
            self._finalize_recording,
            game_id,
            recording_dir,
            metadata
        )

        result = {
            "status": "stopped_pending_finalize",
            "game_id": game_id,
            "duration": metadata.duration_seconds,
            "frame_count": frame_count,
            "dropped_frames": self.dropped_frames,
            "file_size_mb": 0.0,
        }

        print(f"[Recording] Stopped (background finalize queued): {result}")
        return result

    def _update_postprocess_status(self, game_id: str, status: str, error: Optional[str] = None):
        with self.postprocess_lock:
            snapshot = self.postprocess_status.get(game_id, {})
            snapshot["status"] = status
            snapshot["updated_at"] = time.time()
            if error:
                snapshot["error"] = error
            self.postprocess_status[game_id] = snapshot

    def _resolve_ffmpeg_path(self) -> Optional[str]:
        configured_path = os.environ.get("FFMPEG_PATH")
        if configured_path and os.path.exists(configured_path):
            return configured_path
        return shutil.which("ffmpeg")

    def _finalize_recording(self, game_id: str, recording_dir: str, metadata: RecordingMetadata) -> None:
        self._update_postprocess_status(game_id, "processing")
        video_path = os.path.join(recording_dir, "video.mp4")

        try:
            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                file_size_bytes = os.path.getsize(video_path)
                metadata.file_size_mb = file_size_bytes / (1024 * 1024)

                # 生成縮圖（提取前幾幀中第一個有效幀）
                try:
                    cap = cv2.VideoCapture(video_path)
                    if cap.isOpened():
                        for _ in range(5):
                            ret, frame = cap.read()
                            if ret and frame is not None and frame.size > 0:
                                thumbnail_path = os.path.join(recording_dir, "thumbnail.jpg")
                                thumbnail = cv2.resize(frame, (640, 360))
                                cv2.imwrite(thumbnail_path, thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                print(f"[Recording] Thumbnail generated: {thumbnail_path}")
                                break
                        cap.release()
                    else:
                        print(f"[Recording] Could not open video for thumbnail: {video_path}")
                except Exception as e:
                    print(f"[Recording] Thumbnail generation error: {e}")

                # 轉換影片為 H.264（若來源為 mp4v / fmp4）
                try:
                    cap = cv2.VideoCapture(video_path)
                    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                    codec_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
                    cap.release()

                    if codec_str.upper() in ["MP4V", "FMP4"]:
                        print(f"[Recording] Converting {codec_str} to H.264...")
                        temp_path = video_path + ".tmp.mp4"
                        ffmpeg_path = self._resolve_ffmpeg_path()

                        if not ffmpeg_path:
                            message = "FFmpeg not found; set FFMPEG_PATH or install ffmpeg to convert recordings to H.264"
                            print(f"[Recording] {message}")
                            self._update_postprocess_status(game_id, "done_unconverted", message)
                            raise FileNotFoundError(message)

                        cmd = [
                            ffmpeg_path,
                            "-i", video_path,
                            "-c:v", "libx264",
                            "-preset", "fast",
                            "-crf", "23",
                            "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart",
                            "-y",
                            temp_path
                        ]

                        conversion_timeout = max(120, min(900, int(metadata.duration_seconds * 4) if metadata.duration_seconds else 120))
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=conversion_timeout)

                        if result.returncode == 0 and os.path.exists(temp_path):
                            os.remove(video_path)
                            os.rename(temp_path, video_path)
                            print("[Recording] Video converted to H.264")
                            file_size_bytes = os.path.getsize(video_path)
                            metadata.file_size_mb = file_size_bytes / (1024 * 1024)
                        else:
                            stderr_tail = (result.stderr or "")[-1000:]
                            message = f"FFmpeg conversion failed, keeping mp4v. stderr: {stderr_tail}"
                            print(f"[Recording] {message}")
                            self._update_postprocess_status(game_id, "done_unconverted", message)
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                    else:
                        print(f"[Recording] Video codec: {codec_str} (no conversion needed)")

                except FileNotFoundError:
                    print("[Recording] FFmpeg not found, keeping mp4v format")
                except subprocess.TimeoutExpired:
                    message = "FFmpeg conversion timeout, keeping mp4v format"
                    print(f"[Recording] {message}")
                    self._update_postprocess_status(game_id, "done_unconverted", message)
                    temp_path = video_path + ".tmp.mp4"
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as e:
                    print(f"[Recording] Video conversion error: {e}")
            else:
                print(f"[Recording] Video file empty or missing: {video_path}")
                metadata.file_size_mb = 0

            metadata_path = os.path.join(recording_dir, "metadata.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)

            try:
                recording_data = {
                    "game_id": metadata.game_id,
                    "game_type": metadata.game_type,
                    "start_time": metadata.start_time,
                    "end_time": metadata.end_time,
                    "duration_seconds": metadata.duration_seconds,
                    "player1_name": metadata.players[0] if metadata.players and len(metadata.players) > 0 else None,
                    "player2_name": metadata.players[1] if metadata.players and len(metadata.players) > 1 else None,
                    "winner": metadata.winner,
                    "player1_score": metadata.final_score[0] if metadata.final_score and len(metadata.final_score) > 0 else 0,
                    "player2_score": metadata.final_score[1] if metadata.final_score and len(metadata.final_score) > 1 else 0,
                    "target_rounds": metadata.total_rounds,
                    "video_path": video_path,
                    "video_resolution": metadata.video_resolution,
                    "video_fps": metadata.video_fps,
                    "file_size_mb": metadata.file_size_mb
                }

                if self.db.get_recording(metadata.game_id):
                    self.db.update_recording(metadata.game_id, recording_data)
                else:
                    self.db.insert_recording(recording_data)
                print(f"[Recording] Synced to database: {metadata.game_id}")
            except Exception as e:
                print(f"[Recording] Database sync error: {e}")

            with self.postprocess_lock:
                current_status = self.postprocess_status.get(game_id, {}).get("status")
            if current_status != "done_unconverted":
                self._update_postprocess_status(game_id, "done")
        except Exception as e:
            print(f"[Recording] Finalize error ({game_id}): {e}")
            self._update_postprocess_status(game_id, "failed", str(e))
    def get_recordings_list(self) -> List[Dict[str, Any]]:
        """
        獲取所有錄影列表（支援分類資料夾）
        
        Returns:
            錄影元資料列表 (按時間排序,最新在前)
        """
        recordings = []
        
        if not os.path.exists(self.recordings_dir):
            return recordings
        
        try:
            # 遞迴搜尋所有 metadata.json 檔案
            for root, dirs, files in os.walk(self.recordings_dir):
                if "metadata.json" in files:
                    metadata_path = os.path.join(root, "metadata.json")
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            recordings.append(metadata)
                    except Exception as e:
                        print(f"[Recording] Failed to read {metadata_path}: {e}")
            
        except Exception as e:
            print(f"[Recording] List error: {e}")
        
        # 按時間排序 (最新在前)
        recordings.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return recordings
    
    def get_recording_metadata(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取特定錄影的元資料（支援分類資料夾）
        
        Args:
            game_id: 遊戲ID
        
        Returns:
            元資料字典,若不存在則返回None
        """
        # 在所有分類資料夾中搜尋
        if not os.path.exists(self.recordings_dir):
            return None
        
        try:
            for root, dirs, files in os.walk(self.recordings_dir):
                if "metadata.json" in files:
                    # 檢查這個 metadata.json 是否屬於該 game_id
                    metadata_path = os.path.join(root, "metadata.json")
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        if metadata.get("game_id") == game_id:
                            return metadata
        except Exception as e:
            print(f"[Recording] Metadata read error: {e}")
        
        return None
    
    def get_recording_events(self, game_id: str) -> List[Dict[str, Any]]:
        """
        獲取錄影的事件日誌（支援分類資料夾）
        
        Args:
            game_id: 遊戲ID
        
        Returns:
            事件列表
        """
        # 在所有分類資料夾中搜尋
        if not os.path.exists(self.recordings_dir):
            return []
        
        events_path = None
        try:
            for root, dirs, files in os.walk(self.recordings_dir):
                if "metadata.json" in files:
                    metadata_path = os.path.join(root, "metadata.json")
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        if metadata.get("game_id") == game_id:
                            events_path = os.path.join(root, "events.jsonl")
                            break
        except Exception as e:
            print(f"[Recording] Events search error: {e}")
            return []
        
        if not events_path or not os.path.exists(events_path):
            return []
        
        events = []
        try:
            with open(events_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception as e:
            print(f"[Recording] Events read error: {e}")
        
        return events
    
    def get_postprocess_status(self, game_id: str) -> Dict[str, Any]:
        """取得錄影後處理狀態。"""
        with self.postprocess_lock:
            snapshot = self.postprocess_status.get(game_id)
            if not snapshot:
                return {"status": "unknown", "game_id": game_id}
            return {"game_id": game_id, **snapshot}

    @property
    def is_recording(self) -> bool:
        """檢查是否正在錄影"""
        return self.current_recording is not None






