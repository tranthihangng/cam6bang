"""
Frame Buffer Module
===================

Quản lý buffer frame thread-safe cho xử lý video.
Hỗ trợ:
- Queue-based buffer với size limit
- Thread-safe operations
- Multiple consumers
"""

import queue
import threading
from typing import Optional, Any, Tuple
from dataclasses import dataclass
import time


@dataclass
class FrameData:
    """Container cho frame và metadata"""
    frame: Any  # numpy array
    timestamp: float
    frame_id: int = 0
    
    def copy(self) -> 'FrameData':
        """Tạo copy của frame data"""
        return FrameData(
            frame=self.frame.copy() if self.frame is not None else None,
            timestamp=self.timestamp,
            frame_id=self.frame_id,
        )


class FrameBuffer:
    """
    Buffer thread-safe cho frame video
    
    Features:
    - Maxsize để tránh memory leak
    - Non-blocking put (drop frame cũ nếu đầy)
    - Multiple get modes (blocking/non-blocking)
    - Statistics tracking
    
    Usage:
        buffer = FrameBuffer(maxsize=2)
        
        # Producer thread
        buffer.put(frame)
        
        # Consumer thread
        frame_data = buffer.get(timeout=0.1)
        if frame_data:
            process(frame_data.frame)
    """
    
    def __init__(self, maxsize: int = 2):
        """
        Args:
            maxsize: Số frame tối đa trong buffer. Nếu đầy, frame cũ sẽ bị drop
        """
        self._maxsize = maxsize
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._frame_counter = 0
        self._dropped_count = 0
        self._latest_frame: Optional[FrameData] = None
    
    def put(self, frame: Any, timestamp: Optional[float] = None) -> bool:
        """Đặt frame vào buffer
        
        Nếu buffer đầy, frame cũ nhất sẽ bị drop.
        
        Args:
            frame: Frame video (numpy array)
            timestamp: Timestamp của frame (mặc định: time.time())
            
        Returns:
            True nếu thành công
        """
        if frame is None:
            return False
        
        with self._lock:
            self._frame_counter += 1
            frame_data = FrameData(
                frame=frame,
                timestamp=timestamp or time.time(),
                frame_id=self._frame_counter,
            )
            
            # Nếu queue đầy, drop frame cũ
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    self._dropped_count += 1
                except queue.Empty:
                    pass
            
            try:
                self._queue.put_nowait(frame_data)
                self._latest_frame = frame_data
                return True
            except queue.Full:
                self._dropped_count += 1
                return False
    
    def get(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """Lấy frame từ buffer
        
        Args:
            timeout: Thời gian chờ (giây). None = non-blocking
            
        Returns:
            FrameData hoặc None nếu không có frame
        """
        try:
            if timeout is None:
                return self._queue.get_nowait()
            else:
                return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_latest(self) -> Optional[FrameData]:
        """Lấy frame mới nhất, bỏ qua các frame cũ
        
        Returns:
            FrameData mới nhất hoặc None
        """
        latest = None
        while not self._queue.empty():
            try:
                latest = self._queue.get_nowait()
            except queue.Empty:
                break
        return latest
    
    def peek_latest(self) -> Optional[FrameData]:
        """Xem frame mới nhất mà không lấy ra khỏi buffer
        
        Returns:
            Copy của FrameData mới nhất hoặc None
        """
        with self._lock:
            if self._latest_frame:
                return self._latest_frame.copy()
            return None
    
    def clear(self) -> int:
        """Xóa tất cả frame trong buffer
        
        Returns:
            Số frame đã xóa
        """
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        
        with self._lock:
            self._latest_frame = None
        
        return count
    
    def is_empty(self) -> bool:
        """Kiểm tra buffer có rỗng không"""
        return self._queue.empty()
    
    def size(self) -> int:
        """Số frame hiện tại trong buffer"""
        return self._queue.qsize()
    
    @property
    def maxsize(self) -> int:
        """Kích thước tối đa của buffer"""
        return self._maxsize
    
    @property
    def total_frames(self) -> int:
        """Tổng số frame đã put vào buffer"""
        return self._frame_counter
    
    @property
    def dropped_frames(self) -> int:
        """Số frame đã bị drop"""
        return self._dropped_count
    
    def get_stats(self) -> dict:
        """Lấy thống kê buffer"""
        return {
            "current_size": self.size(),
            "max_size": self._maxsize,
            "total_frames": self._frame_counter,
            "dropped_frames": self._dropped_count,
            "drop_rate": self._dropped_count / self._frame_counter if self._frame_counter > 0 else 0,
        }


class DualFrameBuffer:
    """
    Dual buffer cho display và detection
    
    Tách biệt buffer hiển thị (cần frame mới nhất) và 
    buffer detection (có thể xử lý chậm hơn).
    """
    
    def __init__(self, display_maxsize: int = 1, detection_maxsize: int = 2):
        """
        Args:
            display_maxsize: Size buffer cho display
            detection_maxsize: Size buffer cho detection
        """
        self.display_buffer = FrameBuffer(maxsize=display_maxsize)
        self.detection_buffer = FrameBuffer(maxsize=detection_maxsize)
    
    def put(self, frame: Any, timestamp: Optional[float] = None) -> None:
        """Đặt frame vào cả 2 buffer"""
        ts = timestamp or time.time()
        self.display_buffer.put(frame, ts)
        self.detection_buffer.put(frame.copy(), ts)  # Copy để tránh race condition
    
    def get_for_display(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """Lấy frame cho display"""
        return self.display_buffer.get_latest()
    
    def get_for_detection(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """Lấy frame cho detection"""
        return self.detection_buffer.get_latest()
    
    def clear(self) -> Tuple[int, int]:
        """Xóa cả 2 buffer
        
        Returns:
            (display_cleared, detection_cleared)
        """
        return (self.display_buffer.clear(), self.detection_buffer.clear())

