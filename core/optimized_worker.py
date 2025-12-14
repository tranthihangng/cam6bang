"""
Optimized Camera Worker Module
==============================

Worker tối ưu cho mỗi camera, dựa trên:
- coal_6cam_v1.py: CameraWorker pattern, atomic updates
- VidGear: Thread management, queue handling
- Multi-Camera-Live-Object-Tracking: Producer-consumer pattern

Key features:
1. Atomic frame update (không queue cho display)
2. Separate queue cho detection
3. Connection status tracking
4. Inference statistics
5. Thread-safe operations
"""

import threading
import time
import queue
import numpy as np
import cv2
from typing import Optional, Callable, Any, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .inference_stats import get_stats_manager


class WorkerStatus(Enum):
    """Trạng thái worker"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class WorkerConfig:
    """Cấu hình worker"""
    camera_id: int
    rtsp_url: str
    camera_name: str = ""
    enabled: bool = True
    
    # ROI config
    roi_person: List[Tuple[int, int]] = field(default_factory=list)
    roi_coal: List[Tuple[int, int]] = field(default_factory=list)
    reference_resolution: Tuple[int, int] = (1920, 1080)
    
    # Detection config
    enable_person: bool = True
    enable_coal: bool = True
    person_consecutive_threshold: int = 3
    person_no_detection_threshold: int = 5
    coal_ratio_threshold: float = 73.0
    coal_consecutive_threshold: int = 5
    coal_no_blockage_threshold: int = 5
    detection_confidence: float = 0.7
    
    # Performance config
    target_capture_fps: int = 25
    detection_interval: float = 0.5  # seconds between detection
    buffer_size: int = 1
    enable_grab_pattern: bool = True


class OptimizedCameraWorker:
    """
    Worker tối ưu cho một camera
    
    Features:
    1. Low-latency capture với grab pattern
    2. Atomic frame update cho display (không dùng queue)
    3. Separate queue cho detection
    4. Inference time tracking
    5. ROI-based detection
    6. Automatic reconnection
    
    Usage:
        worker = OptimizedCameraWorker(
            config=WorkerConfig(...),
            model=yolo_model,
            model_lock=threading.Lock(),
            on_alert=lambda cam_id, type, active, val: print(f"Alert: {type}")
        )
        
        worker.start()
        
        # Trong GUI loop:
        frame = worker.get_display_frame()
        if frame is not None:
            display(frame)
        
        # Lấy result detection:
        result = worker.get_latest_result()
        
        worker.stop()
    """
    
    # Constants
    MAX_GRAB_COUNT = 3
    MIN_RECONNECT_INTERVAL = 0.5
    MAX_RECONNECT_INTERVAL = 10.0
    
    def __init__(
        self,
        config: WorkerConfig,
        model: Any,
        model_lock: threading.Lock,
        model_id: str = "default",
        on_alert: Optional[Callable[[int, str, bool, float], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            config: WorkerConfig
            model: YOLO model object
            model_lock: Lock cho thread-safe inference
            model_id: ID của model đang sử dụng
            on_alert: Callback(camera_id, alert_type, is_active, value)
            on_log: Callback(message)
        """
        self.config = config
        self.model = model
        self.model_lock = model_lock
        self.model_id = model_id
        self.on_alert = on_alert
        self.on_log = on_log
        
        # IDs
        self.camera_id = config.camera_id
        
        # State
        self._status = WorkerStatus.STOPPED
        self._is_running = False
        self._stop_event = threading.Event()
        
        # Video capture
        self._cap: Optional[cv2.VideoCapture] = None
        self._cap_lock = threading.Lock()
        self._video_info: Dict[str, Any] = {"width": 0, "height": 0, "fps": 0}
        
        # ===== ATOMIC FRAME STORAGE (key optimization) =====
        self._display_frame: Optional[np.ndarray] = None
        self._display_frame_lock = threading.Lock()
        
        # Detection queue (separate from display)
        self._detection_queue: queue.Queue = queue.Queue(maxsize=2)
        
        # Latest result
        self._latest_result: Optional[Tuple[np.ndarray, Any, bool, float]] = None
        self._latest_result_lock = threading.Lock()
        
        # Threads
        self._capture_thread: Optional[threading.Thread] = None
        self._detection_thread: Optional[threading.Thread] = None
        
        # Reconnection
        self._reconnect_interval = self.MIN_RECONNECT_INTERVAL
        self._last_reconnect_time = 0.0
        self._rtsp_fail_count = 0
        
        # Statistics
        self._frame_count = 0
        self._detection_count = 0
        self._fps_display = 0.0
        self._detection_fps_display = 0.0
        self._last_fps_time = time.time()
        self._fps_frame_counter = 0
        self._fps_detection_counter = 0
        
        # Detection state
        self._person_consecutive_count = 0
        self._person_no_detection_count = 0
        self._coal_consecutive_count = 0
        self._coal_no_blockage_count = 0
        self._last_coal_ratio = 0.0
        
        # Alarm state
        self.person_alarm_active = False
        self.coal_alarm_active = False
        
        # Class IDs
        self.person_class_id = 0
        self.coal_class_id = 1
        
        # Inference stats manager
        self._stats_manager = get_stats_manager()
    
    # ===== PROPERTIES =====
    
    @property
    def status(self) -> WorkerStatus:
        return self._status
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def fps_display(self) -> float:
        return self._fps_display
    
    @property
    def detection_fps(self) -> float:
        return self._detection_fps_display
    
    @property
    def last_coal_ratio(self) -> float:
        return self._last_coal_ratio
    
    @property
    def video_info(self) -> Dict[str, Any]:
        return self._video_info
    
    # ===== PUBLIC METHODS =====
    
    def start(self) -> bool:
        """Bắt đầu worker"""
        if self._is_running:
            return True
        
        if not self.config.rtsp_url:
            self._log(f"❌ Camera {self.camera_id}: Không có RTSP URL")
            return False
        
        self._is_running = True
        self._stop_event.clear()
        self._status = WorkerStatus.STARTING
        
        # Start threads
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name=f"Capture-Cam{self.camera_id}"
        )
        self._detection_thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name=f"Detect-Cam{self.camera_id}"
        )
        
        self._capture_thread.start()
        self._detection_thread.start()
        
        self._log(f"🔄 Camera {self.camera_id}: Đang kết nối...")
        return True
    
    def stop(self) -> None:
        """Dừng worker"""
        self._is_running = False
        self._stop_event.set()
        self._status = WorkerStatus.STOPPED
        
        # Wait for threads
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        if self._detection_thread and self._detection_thread.is_alive():
            self._detection_thread.join(timeout=2.0)
        
        # Release capture
        with self._cap_lock:
            if self._cap:
                self._cap.release()
                self._cap = None
        
        # Reset state
        self.person_alarm_active = False
        self.coal_alarm_active = False
        self._person_consecutive_count = 0
        self._coal_consecutive_count = 0
        self._display_frame = None
        self._latest_result = None
        
        self._log(f"⏹️ Camera {self.camera_id}: Đã dừng")
    
    def get_display_frame(self, copy: bool = True) -> Optional[np.ndarray]:
        """Lấy frame mới nhất cho display (atomic, thread-safe)
        
        Args:
            copy: True để trả về copy (an toàn hơn)
            
        Returns:
            Frame hoặc None
        """
        with self._display_frame_lock:
            if self._display_frame is None:
                return None
            return self._display_frame.copy() if copy else self._display_frame
    
    def get_latest_result(self) -> Optional[Tuple[np.ndarray, Any, bool, float]]:
        """Lấy result detection mới nhất
        
        Returns:
            (frame, yolo_result, coal_blocked, coal_ratio) hoặc None
        """
        with self._latest_result_lock:
            return self._latest_result
    
    def clear_result(self) -> None:
        """Xóa result sau khi đã xử lý"""
        with self._latest_result_lock:
            self._latest_result = None
    
    def update_fps(self) -> None:
        """Cập nhật FPS (gọi từ GUI thread)"""
        current_time = time.time()
        elapsed = current_time - self._last_fps_time
        
        if elapsed >= 2.0:
            self._fps_display = self._fps_frame_counter / elapsed
            self._detection_fps_display = self._fps_detection_counter / elapsed
            self._fps_frame_counter = 0
            self._fps_detection_counter = 0
            self._last_fps_time = current_time
    
    # ===== PRIVATE METHODS =====
    
    def _log(self, message: str) -> None:
        """Log message qua callback"""
        if self.on_log:
            try:
                self.on_log(message)
            except:
                pass
    
    def _alert(self, alert_type: str, is_active: bool, value: float = 0) -> None:
        """Trigger alert callback"""
        if self.on_alert:
            try:
                self.on_alert(self.camera_id, alert_type, is_active, value)
            except:
                pass
    
    def _connect(self) -> bool:
        """Kết nối tới RTSP stream"""
        try:
            with self._cap_lock:
                # Release old
                if self._cap:
                    self._cap.release()
                    self._cap = None
                
                # Open new với FFMPEG backend
                self._cap = cv2.VideoCapture(self.config.rtsp_url, cv2.CAP_FFMPEG)
                
                if not self._cap.isOpened():
                    return False
                
                # ===== KEY OPTIMIZATION: Giảm buffer =====
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
                
                # Get video info
                self._video_info = {
                    "width": int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920),
                    "height": int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080),
                    "fps": float(self._cap.get(cv2.CAP_PROP_FPS) or 25),
                }
            
            self._status = WorkerStatus.RUNNING
            self._rtsp_fail_count = 0
            self._reconnect_interval = self.MIN_RECONNECT_INTERVAL
            self._log(f"✅ Camera {self.camera_id}: Đã kết nối thành công")
            return True
            
        except Exception as e:
            self._log(f"❌ Camera {self.camera_id}: Lỗi kết nối - {str(e)}")
            return False
    
    def _reconnect(self) -> None:
        """Reconnect với exponential backoff"""
        current_time = time.time()
        
        # Tránh reconnect quá nhanh
        if current_time - self._last_reconnect_time < self._reconnect_interval:
            time.sleep(0.1)
            return
        
        self._last_reconnect_time = current_time
        self._status = WorkerStatus.RECONNECTING
        
        self._log(f"🔄 Camera {self.camera_id}: Đang kết nối lại... (chờ {self._reconnect_interval:.0f}s)")
        
        # Release old
        with self._cap_lock:
            if self._cap:
                self._cap.release()
                self._cap = None
        
        time.sleep(0.3)
        
        if self._connect():
            self._reconnect_interval = self.MIN_RECONNECT_INTERVAL
        else:
            # Exponential backoff
            self._reconnect_interval = min(
                self._reconnect_interval * 1.5,
                self.MAX_RECONNECT_INTERVAL
            )
    
    def _capture_loop(self) -> None:
        """Main capture loop - chạy trong thread riêng"""
        while not self._stop_event.is_set() and self._is_running:
            # Check/connect (không giữ lock khi gọi _connect)
            need_connect = False
            with self._cap_lock:
                need_connect = (self._cap is None or not self._cap.isOpened())
            
            if need_connect:
                if not self._connect():
                    time.sleep(self._reconnect_interval)
                    continue
            
            try:
                with self._cap_lock:
                    if self._cap is None:
                        continue
                    
                    # ===== KEY OPTIMIZATION: Grab pattern =====
                    # Skip frame cũ trong buffer
                    if self.config.enable_grab_pattern:
                        for _ in range(self.MAX_GRAB_COUNT - 1):
                            self._cap.grab()
                    
                    # Đọc frame mới nhất
                    ret, frame = self._cap.read()
                
                if ret and frame is not None:
                    # Update frame count
                    self._frame_count += 1
                    self._fps_frame_counter += 1
                    self._rtsp_fail_count = 0
                    
                    if self._status != WorkerStatus.RUNNING:
                        self._status = WorkerStatus.RUNNING
                    
                    # ===== ATOMIC FRAME UPDATE (không copy) =====
                    with self._display_frame_lock:
                        self._display_frame = frame
                    
                    # Put to detection queue (không block)
                    try:
                        if self._detection_queue.full():
                            self._detection_queue.get_nowait()
                        self._detection_queue.put_nowait(frame)
                    except:
                        pass
                else:
                    self._rtsp_fail_count += 1
                    if self._rtsp_fail_count >= 3:
                        self._status = WorkerStatus.RECONNECTING
                        self._reconnect()
                        
            except Exception as e:
                self._rtsp_fail_count += 1
                if self._rtsp_fail_count >= 3:
                    self._reconnect()
            
            # FPS limiting
            time.sleep(max(0, 0.01))  # ~100 FPS max capture
    
    def _detection_loop(self) -> None:
        """Detection loop - chạy trong thread riêng"""
        detection_interval = self.config.detection_interval
        
        while not self._stop_event.is_set() and self._is_running:
            loop_start = time.time()
            
            # Lấy frame mới nhất từ queue
            frame = None
            while not self._detection_queue.empty():
                try:
                    frame = self._detection_queue.get_nowait()
                except:
                    break
            
            if frame is None:
                time.sleep(0.1)
                continue
            
            try:
                # ===== YOLO INFERENCE với timing =====
                inference_start = time.time()
                
                with self.model_lock:
                    results = self.model.predict(
                        frame,
                        conf=self.config.detection_confidence,
                        verbose=False,
                        task='segment'
                    )
                result = results[0] if results else None
                
                inference_time_ms = (time.time() - inference_start) * 1000
                
                # Log inference time (mỗi 20 lần log 1 lần để tránh spam)
                if self._detection_count % 20 == 0:
                    self._log(f"📊 Cam {self.camera_id}: Inference {inference_time_ms:.1f}ms")
                
                # Record inference stats
                self._stats_manager.record_inference(
                    camera_id=self.camera_id,
                    inference_time_ms=inference_time_ms,
                    model_id=self.model_id
                )
                
                # Detect coal blockage
                coal_blocked, coal_ratio = self._detect_coal_blockage(frame, result)
                
                # Store result
                with self._latest_result_lock:
                    self._latest_result = (frame.copy(), result, coal_blocked, coal_ratio)
                
                self._detection_count += 1
                self._fps_detection_counter += 1
                
            except Exception as e:
                print(f"Camera {self.camera_id} detection error: {e}")
            
            # Rate limiting
            elapsed = time.time() - loop_start
            sleep_time = max(0, detection_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _detect_coal_blockage(self, frame: np.ndarray, result: Any) -> Tuple[bool, float]:
        """Phát hiện tắc than"""
        if not self.config.enable_coal:
            return False, 0.0
        
        try:
            h, w = frame.shape[:2]
            roi_coal = self._scale_roi(self.config.roi_coal, w, h)
            
            if not roi_coal:
                return False, 0.0
            
            # Create ROI mask
            roi_mask = np.zeros((h, w), dtype=np.uint8)
            roi_polygon = np.array(roi_coal, dtype=np.int32)
            cv2.fillPoly(roi_mask, [roi_polygon], 255)
            roi_area = cv2.countNonZero(roi_mask)
            
            if roi_area == 0 or result is None or result.masks is None:
                return False, 0.0
            
            # Create coal mask
            coal_mask_total = np.zeros((h, w), dtype=np.uint8)
            
            if result.boxes is not None:
                boxes = result.boxes
                masks = result.masks
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    if cls_id == self.coal_class_id and masks is not None and i < len(masks.data):
                        mask_data = masks.data[i].cpu().numpy()
                        mask_resized = cv2.resize(mask_data, (w, h), interpolation=cv2.INTER_NEAREST)
                        mask_binary = (mask_resized > 0.5).astype(np.uint8) * 255
                        coal_mask_total = cv2.bitwise_or(coal_mask_total, mask_binary)
            
            # Calculate ratio
            intersection = cv2.bitwise_and(coal_mask_total, roi_mask)
            coal_area_in_roi = cv2.countNonZero(intersection)
            coal_ratio = (coal_area_in_roi / roi_area * 100) if roi_area > 0 else 0.0
            
            self._last_coal_ratio = coal_ratio
            
            # Logic đếm liên tiếp
            if coal_ratio >= self.config.coal_ratio_threshold:
                self._coal_no_blockage_count = 0
                self._coal_consecutive_count += 1
                
                if self._coal_consecutive_count >= self.config.coal_consecutive_threshold:
                    if not self.coal_alarm_active:
                        self.coal_alarm_active = True
                        self._alert("coal", True, coal_ratio)
                    self._coal_consecutive_count = 0
                    return True, coal_ratio
            else:
                self._coal_no_blockage_count += 1
                if self._coal_no_blockage_count >= self.config.coal_no_blockage_threshold:
                    self._coal_consecutive_count = 0
                    if self.coal_alarm_active:
                        self.coal_alarm_active = False
                        self._alert("coal", False, coal_ratio)
            
            return False, coal_ratio
            
        except Exception as e:
            print(f"Camera {self.camera_id} coal detection error: {e}")
            return False, 0.0
    
    def _scale_roi(self, roi_points: List[Tuple[int, int]], 
                   target_w: int, target_h: int) -> List[Tuple[int, int]]:
        """Scale ROI theo kích thước frame"""
        if not roi_points:
            return roi_points
        
        ref_w, ref_h = self.config.reference_resolution
        scale_x = target_w / ref_w
        scale_y = target_h / ref_h
        
        return [(int(x * scale_x), int(y * scale_y)) for (x, y) in roi_points]
    
    def get_stats_dict(self) -> Dict[str, Any]:
        """Lấy statistics dạng dict"""
        return {
            "camera_id": self.camera_id,
            "status": self._status.value,
            "frame_count": self._frame_count,
            "detection_count": self._detection_count,
            "fps_display": round(self._fps_display, 1),
            "detection_fps": round(self._detection_fps_display, 1),
            "coal_ratio": round(self._last_coal_ratio, 1),
            "person_alarm": self.person_alarm_active,
            "coal_alarm": self.coal_alarm_active,
            "video_info": self._video_info,
        }

