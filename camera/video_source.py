"""
Video Source Module
===================

Quản lý nguồn video từ RTSP stream hoặc video file.
Hỗ trợ:
- RTSP streaming với auto-reconnect
- Video file với loop playback
- Frame rate limiting
"""

import cv2
import time
import threading
from dataclasses import dataclass
from typing import Optional, Tuple, Callable
from enum import Enum


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
        """Kiểm tra thông tin video có hợp lệ không"""
        return self.width > 0 and self.height > 0


class VideoSource:
    """
    Quản lý nguồn video từ RTSP hoặc file
    
    Features:
    - Thread-safe
    - Auto reconnect cho RTSP
    - Frame rate limiting
    - Callback khi có frame mới
    
    Usage:
        source = VideoSource(
            source_path="rtsp://...",
            target_fps=22,
            on_frame_callback=lambda frame, ts: process(frame)
        )
        source.start()
        ...
        source.stop()
    """
    
    def __init__(
        self,
        source_path: str,
        target_fps: int = 22,
        on_frame_callback: Optional[Callable[[any, float], None]] = None,
        on_error_callback: Optional[Callable[[str], None]] = None,
        reconnect_interval: float = 1.0,
        max_reconnect_attempts: int = -1,  # -1 = unlimited
    ):
        """
        Args:
            source_path: Đường dẫn RTSP URL hoặc file video
            target_fps: FPS mục tiêu
            on_frame_callback: Callback khi có frame mới (frame, timestamp)
            on_error_callback: Callback khi có lỗi (error_message)
            reconnect_interval: Thời gian chờ giữa các lần reconnect (giây)
            max_reconnect_attempts: Số lần reconnect tối đa (-1 = không giới hạn)
        """
        self.source_path = source_path
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps if target_fps > 0 else 0
        self.on_frame_callback = on_frame_callback
        self.on_error_callback = on_error_callback
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # Internal state
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_running = False
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._video_info = VideoInfo()
        self._lock = threading.Lock()
        
        # Statistics
        self._frame_count = 0
        self._fail_count = 0
        self._last_frame_time = 0.0
        self._reconnect_count = 0
        
        # Detect source type
        self._source_type = self._detect_source_type(source_path)
    
    def _detect_source_type(self, path: str) -> VideoSourceType:
        """Xác định loại nguồn video"""
        if not path:
            return VideoSourceType.UNKNOWN
        
        path_lower = path.lower()
        if path_lower.startswith("rtsp://") or path_lower.startswith("http://"):
            return VideoSourceType.RTSP
        else:
            return VideoSourceType.FILE
    
    @property
    def video_info(self) -> VideoInfo:
        """Lấy thông tin video"""
        with self._lock:
            return self._video_info
    
    @property
    def is_running(self) -> bool:
        """Kiểm tra đang chạy không"""
        return self._is_running
    
    @property
    def frame_count(self) -> int:
        """Số frame đã capture"""
        return self._frame_count
    
    def start(self) -> bool:
        """Bắt đầu capture video
        
        Returns:
            True nếu thành công, False nếu thất bại
        """
        if self._is_running:
            return True
        
        # Mở video source
        if not self._open_source():
            return False
        
        # Bắt đầu capture thread
        self._is_running = True
        self._stop_event.clear()
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        
        return True
    
    def stop(self) -> None:
        """Dừng capture video"""
        if not self._is_running:
            return
        
        self._is_running = False
        self._stop_event.set()
        
        # Đợi thread kết thúc
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        
        # Giải phóng tài nguyên
        self._release_source()
    
    def read_frame(self) -> Tuple[bool, Optional[any]]:
        """Đọc một frame từ source
        
        Returns:
            (success, frame) - success=True nếu đọc được frame
        """
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return False, None
            
            ret, frame = self._cap.read()
            if ret:
                self._frame_count += 1
                self._fail_count = 0
            else:
                self._fail_count += 1
            
            return ret, frame
    
    def _open_source(self) -> bool:
        """Mở nguồn video"""
        try:
            self._release_source()
            
            self._cap = cv2.VideoCapture(self.source_path)
            
            if not self._cap.isOpened():
                self._report_error(f"Không thể mở nguồn video: {self.source_path}")
                return False
            
            # Lấy thông tin video
            with self._lock:
                self._video_info = VideoInfo(
                    width=int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                    height=int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
                    fps=float(self._cap.get(cv2.CAP_PROP_FPS) or 0),
                    frame_count=int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
                    source_type=self._source_type,
                    source_path=self.source_path,
                )
            
            self._fail_count = 0
            return True
            
        except Exception as e:
            self._report_error(f"Lỗi mở nguồn video: {str(e)}")
            return False
    
    def _release_source(self) -> None:
        """Giải phóng nguồn video"""
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except:
                    pass
                self._cap = None
    
    def _capture_loop(self) -> None:
        """Vòng lặp capture frame chạy trong thread riêng"""
        while not self._stop_event.is_set() and self._is_running:
            loop_start = time.time()
            
            # Đọc frame
            ret, frame = self.read_frame()
            
            if ret and frame is not None:
                # Gọi callback nếu có
                if self.on_frame_callback:
                    try:
                        self.on_frame_callback(frame, time.time())
                    except Exception as e:
                        self._report_error(f"Lỗi callback: {str(e)}")
            else:
                # Xử lý lỗi
                self._handle_read_failure()
            
            # Frame rate limiting
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _handle_read_failure(self) -> None:
        """Xử lý khi đọc frame thất bại"""
        if self._source_type == VideoSourceType.FILE:
            # Video file: tua về đầu để phát lại
            with self._lock:
                if self._cap is not None:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            time.sleep(0.05)
        else:
            # RTSP: thử reconnect
            if self._fail_count == 1 or self._fail_count % 10 == 0:
                self._try_reconnect()
            else:
                time.sleep(0.05)
    
    def _try_reconnect(self) -> bool:
        """Thử kết nối lại RTSP"""
        # Kiểm tra giới hạn reconnect
        if self.max_reconnect_attempts >= 0:
            if self._reconnect_count >= self.max_reconnect_attempts:
                self._report_error(f"Đã vượt quá số lần reconnect tối đa ({self.max_reconnect_attempts})")
                return False
        
        self._reconnect_count += 1
        self._report_error(f"Đang thử reconnect RTSP (lần {self._reconnect_count})...")
        
        # Thả kết nối cũ
        self._release_source()
        time.sleep(0.2)
        
        # Tạo kết nối mới
        if self._open_source():
            self._reconnect_count = 0
            return True
        else:
            time.sleep(self.reconnect_interval)
            return False
    
    def _report_error(self, message: str) -> None:
        """Báo lỗi qua callback"""
        if self.on_error_callback:
            try:
                self.on_error_callback(message)
            except:
                pass
    
    def update_target_fps(self, fps: int) -> None:
        """Cập nhật FPS mục tiêu
        
        Args:
            fps: FPS mới
        """
        if fps > 0:
            self.target_fps = fps
            self.frame_interval = 1.0 / fps

