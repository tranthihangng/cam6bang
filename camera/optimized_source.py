"""
Optimized Video Source Module
=============================

Phiên bản tối ưu của VideoSource dựa trên:
- VidGear: Buffer optimization, thread management
- Multi-Camera-Live-Object-Tracking: Grab pattern
- coal_6cam_v1.py: Atomic frame updates, connection handling

Key optimizations:
1. Buffer size = 1 để giảm latency
2. Grab pattern để skip frame cũ trong buffer
3. Exponential backoff cho reconnection
4. Connection status tracking chi tiết
5. Atomic frame update thay vì queue
"""

import cv2
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict
from enum import Enum


class ConnectionStatus(Enum):
    """Trạng thái kết nối chi tiết"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class VideoSourceType(Enum):
    """Loại nguồn video"""
    RTSP = "rtsp"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass
class VideoInfo:
    """Thông tin video"""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frame_count: int = 0
    source_type: VideoSourceType = VideoSourceType.UNKNOWN
    source_path: str = ""
    
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


@dataclass
class CaptureStats:
    """Thống kê capture"""
    frame_count: int = 0
    fail_count: int = 0
    reconnect_count: int = 0
    last_frame_time: float = 0.0
    fps: float = 0.0
    avg_capture_time_ms: float = 0.0
    
    # FPS calculation
    _fps_frame_count: int = field(default=0, repr=False)
    _fps_last_time: float = field(default=0.0, repr=False)
    _capture_times: list = field(default_factory=list, repr=False)


class OptimizedVideoSource:
    """
    Optimized Video Source với các tính năng:
    
    1. Low-latency capture (buffer = 1)
    2. Grab pattern để skip frame cũ
    3. Exponential backoff reconnection
    4. Atomic frame update (không dùng queue cho display)
    5. Connection status tracking
    6. Capture statistics
    
    Usage:
        source = OptimizedVideoSource(
            source_path="rtsp://...",
            on_frame=lambda frame, ts: display(frame)
        )
        source.start()
        
        # Lấy frame mới nhất (atomic, không copy)
        frame = source.get_latest_frame()
        
        source.stop()
    """
    
    # ===== CONSTANTS =====
    DEFAULT_BUFFER_SIZE = 1  # Giảm buffer để giảm latency
    MAX_GRAB_COUNT = 3  # Số lần grab để skip frame cũ
    MIN_RECONNECT_INTERVAL = 0.5
    MAX_RECONNECT_INTERVAL = 10.0
    RECONNECT_BACKOFF_MULTIPLIER = 1.5
    
    def __init__(
        self,
        source_path: str,
        target_fps: int = 25,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        enable_grab_pattern: bool = True,
        on_frame: Optional[Callable[[Any, float], None]] = None,
        on_status_change: Optional[Callable[[ConnectionStatus], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            source_path: RTSP URL hoặc đường dẫn file video
            target_fps: FPS mục tiêu cho capture
            buffer_size: Kích thước buffer của VideoCapture (1 = lowest latency)
            enable_grab_pattern: Bật grab pattern để skip frame cũ
            on_frame: Callback khi có frame mới (frame, timestamp)
            on_status_change: Callback khi trạng thái kết nối thay đổi
            on_error: Callback khi có lỗi
        """
        self.source_path = source_path
        self.target_fps = target_fps
        self.buffer_size = buffer_size
        self.enable_grab_pattern = enable_grab_pattern
        self.on_frame = on_frame
        self.on_status_change = on_status_change
        self.on_error = on_error
        
        # Frame interval
        self.frame_interval = 1.0 / target_fps if target_fps > 0 else 0.04
        
        # Detect source type
        self._source_type = self._detect_source_type(source_path)
        
        # Internal state
        self._cap: Optional[cv2.VideoCapture] = None
        self._cap_lock = threading.Lock()
        self._is_running = False
        self._stop_event = threading.Event()
        
        # Connection status
        self._status = ConnectionStatus.DISCONNECTED
        self._reconnect_interval = self.MIN_RECONNECT_INTERVAL
        self._last_reconnect_time = 0.0
        
        # Atomic frame storage (thay cho queue)
        self._latest_frame: Optional[Any] = None
        self._latest_frame_lock = threading.Lock()
        self._latest_timestamp: float = 0.0
        
        # Video info
        self._video_info = VideoInfo()
        
        # Statistics
        self._stats = CaptureStats()
        self._stats._fps_last_time = time.time()
        
        # Threads
        self._capture_thread: Optional[threading.Thread] = None
    
    def _detect_source_type(self, path: str) -> VideoSourceType:
        """Xác định loại nguồn video"""
        if not path:
            return VideoSourceType.UNKNOWN
        
        path_lower = path.lower()
        if path_lower.startswith(("rtsp://", "http://", "https://")):
            return VideoSourceType.RTSP
        return VideoSourceType.FILE
    
    # ===== PROPERTIES =====
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def status(self) -> ConnectionStatus:
        return self._status
    
    @property
    def video_info(self) -> VideoInfo:
        return self._video_info
    
    @property
    def stats(self) -> CaptureStats:
        return self._stats
    
    @property
    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED
    
    # ===== PUBLIC METHODS =====
    
    def start(self) -> bool:
        """Bắt đầu capture video
        
        Returns:
            True nếu khởi động thành công
        """
        if self._is_running:
            return True
        
        self._set_status(ConnectionStatus.CONNECTING)
        
        # Mở source
        if not self._open_source():
            self._set_status(ConnectionStatus.ERROR)
            return False
        
        # Start capture thread
        self._is_running = True
        self._stop_event.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name=f"Capture-{self.source_path[-20:]}"
        )
        self._capture_thread.start()
        
        return True
    
    def stop(self) -> None:
        """Dừng capture video"""
        if not self._is_running:
            return
        
        self._is_running = False
        self._stop_event.set()
        
        # Wait for thread
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        
        # Release resources
        self._release_source()
        self._set_status(ConnectionStatus.DISCONNECTED)
    
    def get_latest_frame(self, copy: bool = True) -> Optional[Any]:
        """Lấy frame mới nhất (atomic, thread-safe)
        
        Args:
            copy: True để trả về copy, False để trả về reference (faster)
            
        Returns:
            Frame hoặc None
        """
        with self._latest_frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy() if copy else self._latest_frame
    
    def get_latest_frame_with_timestamp(self, copy: bool = True):
        """Lấy frame và timestamp mới nhất
        
        Returns:
            (frame, timestamp) hoặc (None, 0)
        """
        with self._latest_frame_lock:
            if self._latest_frame is None:
                return None, 0.0
            frame = self._latest_frame.copy() if copy else self._latest_frame
            return frame, self._latest_timestamp
    
    # ===== PRIVATE METHODS =====
    
    def _set_status(self, new_status: ConnectionStatus) -> None:
        """Cập nhật và notify status change"""
        if self._status != new_status:
            self._status = new_status
            if self.on_status_change:
                try:
                    self.on_status_change(new_status)
                except:
                    pass
    
    def _report_error(self, message: str) -> None:
        """Report error qua callback"""
        if self.on_error:
            try:
                self.on_error(message)
            except:
                pass
    
    def _open_source(self) -> bool:
        """Mở nguồn video với tối ưu buffer"""
        try:
            self._release_source()
            
            with self._cap_lock:
                # Sử dụng FFMPEG backend cho RTSP
                if self._source_type == VideoSourceType.RTSP:
                    self._cap = cv2.VideoCapture(self.source_path, cv2.CAP_FFMPEG)
                else:
                    self._cap = cv2.VideoCapture(self.source_path)
                
                if not self._cap.isOpened():
                    self._report_error(f"Không thể mở nguồn video: {self.source_path}")
                    return False
                
                # ===== KEY OPTIMIZATION: Giảm buffer =====
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
                
                # Set codec cho RTSP
                if self._source_type == VideoSourceType.RTSP:
                    self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
                
                # Lấy thông tin video
                self._video_info = VideoInfo(
                    width=int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920),
                    height=int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080),
                    fps=float(self._cap.get(cv2.CAP_PROP_FPS) or 25),
                    frame_count=int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
                    source_type=self._source_type,
                    source_path=self.source_path,
                )
            
            # Reset reconnect interval on success
            self._reconnect_interval = self.MIN_RECONNECT_INTERVAL
            self._stats.fail_count = 0
            self._set_status(ConnectionStatus.CONNECTED)
            
            return True
            
        except Exception as e:
            self._report_error(f"Lỗi mở nguồn video: {str(e)}")
            return False
    
    def _release_source(self) -> None:
        """Giải phóng nguồn video"""
        with self._cap_lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except:
                    pass
                self._cap = None
    
    def _capture_loop(self) -> None:
        """Main capture loop với optimizations"""
        while not self._stop_event.is_set() and self._is_running:
            loop_start = time.time()
            
            # Check connection
            with self._cap_lock:
                if self._cap is None or not self._cap.isOpened():
                    self._handle_disconnection()
                    continue
            
            try:
                capture_start = time.time()
                
                with self._cap_lock:
                    if self._cap is None:
                        continue
                    
                    # ===== KEY OPTIMIZATION: Grab pattern =====
                    # Skip frame cũ trong buffer để lấy frame mới nhất
                    if self.enable_grab_pattern and self._source_type == VideoSourceType.RTSP:
                        for _ in range(self.MAX_GRAB_COUNT - 1):
                            self._cap.grab()
                    
                    # Đọc frame mới nhất
                    ret, frame = self._cap.read()
                
                capture_time = (time.time() - capture_start) * 1000
                
                if ret and frame is not None:
                    # Update statistics
                    self._update_stats(capture_time)
                    
                    # Atomic frame update
                    current_time = time.time()
                    with self._latest_frame_lock:
                        self._latest_frame = frame
                        self._latest_timestamp = current_time
                    
                    # Callback
                    if self.on_frame:
                        try:
                            self.on_frame(frame, current_time)
                        except:
                            pass
                    
                    # Reset fail count
                    self._stats.fail_count = 0
                    
                    if self._status != ConnectionStatus.CONNECTED:
                        self._set_status(ConnectionStatus.CONNECTED)
                else:
                    self._stats.fail_count += 1
                    if self._stats.fail_count >= 3:
                        self._handle_disconnection()
                        
            except Exception as e:
                self._report_error(f"Capture error: {str(e)}")
                self._stats.fail_count += 1
                if self._stats.fail_count >= 3:
                    self._handle_disconnection()
            
            # Frame rate limiting
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _handle_disconnection(self) -> None:
        """Xử lý mất kết nối với exponential backoff"""
        if self._source_type == VideoSourceType.FILE:
            # Video file: tua về đầu
            with self._cap_lock:
                if self._cap is not None:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            time.sleep(0.05)
            return
        
        # RTSP: Reconnect với exponential backoff
        current_time = time.time()
        
        # Tránh reconnect quá nhanh
        if current_time - self._last_reconnect_time < self._reconnect_interval:
            time.sleep(0.1)
            return
        
        self._last_reconnect_time = current_time
        self._set_status(ConnectionStatus.RECONNECTING)
        self._stats.reconnect_count += 1
        
        self._report_error(
            f"Đang kết nối lại... (lần {self._stats.reconnect_count}, "
            f"chờ {self._reconnect_interval:.1f}s)"
        )
        
        # Release và reconnect
        self._release_source()
        time.sleep(0.3)
        
        if self._open_source():
            self._report_error("Kết nối lại thành công!")
            self._reconnect_interval = self.MIN_RECONNECT_INTERVAL
        else:
            # Exponential backoff
            self._reconnect_interval = min(
                self._reconnect_interval * self.RECONNECT_BACKOFF_MULTIPLIER,
                self.MAX_RECONNECT_INTERVAL
            )
    
    def _update_stats(self, capture_time_ms: float) -> None:
        """Cập nhật statistics"""
        self._stats.frame_count += 1
        self._stats.last_frame_time = time.time()
        self._stats._fps_frame_count += 1
        
        # Track capture times (keep last 50)
        self._stats._capture_times.append(capture_time_ms)
        if len(self._stats._capture_times) > 50:
            self._stats._capture_times.pop(0)
        self._stats.avg_capture_time_ms = sum(self._stats._capture_times) / len(self._stats._capture_times)
        
        # Calculate FPS
        current_time = time.time()
        elapsed = current_time - self._stats._fps_last_time
        if elapsed >= 2.0:
            self._stats.fps = self._stats._fps_frame_count / elapsed
            self._stats._fps_frame_count = 0
            self._stats._fps_last_time = current_time
    
    def get_stats_dict(self) -> Dict[str, Any]:
        """Lấy statistics dạng dict"""
        return {
            "frame_count": self._stats.frame_count,
            "fps": round(self._stats.fps, 1),
            "avg_capture_ms": round(self._stats.avg_capture_time_ms, 2),
            "fail_count": self._stats.fail_count,
            "reconnect_count": self._stats.reconnect_count,
            "status": self._status.value,
        }

