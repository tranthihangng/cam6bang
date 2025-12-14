"""
Coal Detector Module
====================

Phát hiện tắc than dựa trên segmentation mask.
Logic: Tính tỷ lệ diện tích segment than / diện tích ROI
Nếu tỷ lệ >= ngưỡng trong N frame liên tiếp -> báo tắc than
"""

import cv2
import numpy as np
import time
from dataclasses import dataclass
from typing import Any, Optional, List, Tuple

from .base_detector import BaseDetector, DetectionResult, create_mask_from_polygon, check_mask_intersection


@dataclass
class CoalDetectionResult(DetectionResult):
    """Kết quả phát hiện tắc than"""
    coal_ratio: float = 0.0  # Tỷ lệ than trong ROI (%)
    roi_area: int = 0  # Diện tích ROI (pixels)
    coal_area: int = 0  # Diện tích than trong ROI (pixels)
    is_blocked: bool = False  # Có tắc than không
    consecutive_count: int = 0
    should_alarm: bool = False


class CoalDetector(BaseDetector):
    """
    Phát hiện tắc than dựa trên segmentation
    
    Logic:
    1. Tạo mask cho ROI than
    2. Lấy mask segment than từ YOLO
    3. Tính tỷ lệ = (diện tích than trong ROI) / (diện tích ROI)
    4. Nếu tỷ lệ >= ngưỡng trong N frame liên tiếp -> BẬT cảnh báo
    5. Nếu tỷ lệ < ngưỡng trong M frame liên tiếp -> TẮT cảnh báo
    
    Usage:
        detector = CoalDetector(
            roi_points=[(x1,y1), (x2,y2), ...],
            ratio_threshold=73.0,
            consecutive_threshold=5
        )
        
        result = detector.detect(frame, yolo_result)
        if result.should_alarm:
            send_coal_alarm()
    """
    
    def __init__(
        self,
        roi_points: List[Tuple[int, int]],
        coal_class_id: int = 1,
        ratio_threshold: float = 73.0,
        consecutive_threshold: int = 5,
        no_blockage_threshold: int = 5,
        enabled: bool = True,
    ):
        """
        Args:
            roi_points: Các điểm định nghĩa vùng than
            coal_class_id: Class ID của than trong model
            ratio_threshold: Ngưỡng tỷ lệ than (%) để coi là tắc
            consecutive_threshold: Số frame liên tiếp để BẬT cảnh báo
            no_blockage_threshold: Số frame để TẮT cảnh báo
            enabled: Có bật detection không
        """
        super().__init__()
        
        self.roi_points = roi_points
        self.coal_class_id = coal_class_id
        self.ratio_threshold = ratio_threshold
        self.consecutive_threshold = consecutive_threshold
        self.no_blockage_threshold = no_blockage_threshold
        self.enabled = enabled
        
        # Trạng thái
        self._consecutive_count = 0
        self._no_blockage_count = 0
        self._alarm_state = False
        self._roi_mask: Optional[np.ndarray] = None
        self._roi_area: int = 0
        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_coal_ratio: float = 0.0
        
        self._is_initialized = True
    
    def detect(self, frame: np.ndarray, yolo_result: Any = None) -> CoalDetectionResult:
        """Phát hiện tắc than
        
        Args:
            frame: Frame video (numpy array BGR)
            yolo_result: Kết quả từ YOLO (optional)
            
        Returns:
            CoalDetectionResult
        """
        self._detection_count += 1
        current_time = time.time()
        
        # Nếu disabled, trả về kết quả rỗng
        if not self.enabled:
            return self._create_empty_result(current_time)
        
        h, w = frame.shape[:2]
        
        # Tạo ROI mask nếu chưa có hoặc kích thước thay đổi
        if self._roi_mask is None or self._frame_size != (w, h):
            self._roi_mask = create_mask_from_polygon(self.roi_points, w, h)
            self._roi_area = cv2.countNonZero(self._roi_mask)
            self._frame_size = (w, h)
        
        # Nếu ROI không hợp lệ
        if self._roi_area == 0:
            return self._create_empty_result(current_time)
        
        # Nếu không có YOLO result
        if yolo_result is None or yolo_result.masks is None:
            return self._create_empty_result(current_time)
        
        # Tính toán tỷ lệ than
        coal_area, coal_ratio = self._calculate_coal_ratio(yolo_result, w, h)
        self._last_coal_ratio = coal_ratio
        
        # Cập nhật trạng thái
        is_blocked, should_alarm = self._update_alarm_state(coal_ratio)
        
        result = CoalDetectionResult(
            detected=coal_area > 0,
            confidence=coal_ratio / 100.0,
            timestamp=current_time,
            frame_id=self._detection_count,
            coal_ratio=coal_ratio,
            roi_area=self._roi_area,
            coal_area=coal_area,
            is_blocked=is_blocked,
            consecutive_count=self._consecutive_count,
            should_alarm=should_alarm,
        )
        
        self._last_result = result
        return result
    
    def _calculate_coal_ratio(self, yolo_result: Any, 
                               width: int, height: int) -> Tuple[int, float]:
        """Tính tỷ lệ than trong ROI
        
        Returns:
            (coal_area, coal_ratio%)
        """
        # Tạo mask tổng hợp cho than
        coal_mask_total = np.zeros((height, width), dtype=np.uint8)
        
        boxes = yolo_result.boxes
        masks = yolo_result.masks
        
        if boxes is None or masks is None:
            return 0, 0.0
        
        # Duyệt qua tất cả detections
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i])
            
            if cls_id != self.coal_class_id:
                continue
            
            if i >= len(masks.data):
                continue
            
            # Lấy và resize mask
            mask_data = masks.data[i].cpu().numpy()
            mask_resized = cv2.resize(mask_data, (width, height), 
                                      interpolation=cv2.INTER_NEAREST)
            mask_binary = (mask_resized > 0.5).astype(np.uint8) * 255
            
            # Cộng vào mask tổng hợp
            coal_mask_total = cv2.bitwise_or(coal_mask_total, mask_binary)
        
        # Tính intersection với ROI
        intersection = cv2.bitwise_and(coal_mask_total, self._roi_mask)
        coal_area = cv2.countNonZero(intersection)
        
        # Tính tỷ lệ
        coal_ratio = (coal_area / self._roi_area * 100) if self._roi_area > 0 else 0.0
        
        return coal_area, coal_ratio
    
    def _update_alarm_state(self, coal_ratio: float) -> Tuple[bool, bool]:
        """Cập nhật trạng thái báo động
        
        Returns:
            (is_blocked, should_trigger_new_alarm)
        """
        should_trigger_new_alarm = False
        is_blocked = False
        
        if coal_ratio >= self.ratio_threshold:
            # Phát hiện tỷ lệ cao
            self._no_blockage_count = 0
            self._consecutive_count += 1
            
            if self._consecutive_count >= self.consecutive_threshold:
                is_blocked = True
                
                if not self._alarm_state:
                    # Lần đầu đạt ngưỡng -> trigger alarm
                    self._alarm_state = True
                    should_trigger_new_alarm = True
                
                # Reset counter để đếm lại
                self._consecutive_count = 0
        else:
            # Tỷ lệ thấp
            self._no_blockage_count += 1
            
            # Chỉ reset sau một số frame
            if self._no_blockage_count >= self.no_blockage_threshold:
                self._consecutive_count = 0
                self._alarm_state = False
        
        return is_blocked, should_trigger_new_alarm
    
    def _create_empty_result(self, timestamp: float) -> CoalDetectionResult:
        """Tạo kết quả rỗng"""
        # Cập nhật no_blockage_count
        self._no_blockage_count += 1
        if self._no_blockage_count >= self.no_blockage_threshold:
            self._consecutive_count = 0
            self._alarm_state = False
        
        return CoalDetectionResult(
            detected=False,
            timestamp=timestamp,
            frame_id=self._detection_count,
            coal_ratio=self._last_coal_ratio,
        )
    
    def reset(self) -> None:
        """Reset trạng thái detector"""
        self._consecutive_count = 0
        self._no_blockage_count = 0
        self._alarm_state = False
        self._last_result = None
        self._last_coal_ratio = 0.0
    
    def get_state(self) -> dict:
        """Lấy trạng thái hiện tại"""
        return {
            "alarm_state": self._alarm_state,
            "consecutive_count": self._consecutive_count,
            "no_blockage_count": self._no_blockage_count,
            "last_coal_ratio": self._last_coal_ratio,
            "ratio_threshold": self.ratio_threshold,
            "consecutive_threshold": self.consecutive_threshold,
            "no_blockage_threshold": self.no_blockage_threshold,
            "enabled": self.enabled,
        }
    
    @property
    def alarm_state(self) -> bool:
        """Trạng thái báo động hiện tại"""
        return self._alarm_state
    
    @property
    def last_coal_ratio(self) -> float:
        """Tỷ lệ than cuối cùng đo được"""
        return self._last_coal_ratio
    
    def update_roi(self, roi_points: List[Tuple[int, int]]) -> None:
        """Cập nhật ROI points"""
        self.roi_points = roi_points
        self._roi_mask = None  # Force recreate mask
    
    def update_threshold(self, ratio_threshold: float) -> None:
        """Cập nhật ngưỡng tỷ lệ"""
        self.ratio_threshold = ratio_threshold
    
    def set_enabled(self, enabled: bool) -> None:
        """Bật/tắt detection"""
        self.enabled = enabled
        if not enabled:
            self.reset()
    
    def should_turn_off_alarm(self) -> bool:
        """Kiểm tra có nên TẮT báo động không"""
        return (self._no_blockage_count >= self.no_blockage_threshold and 
                self._alarm_state == False)

