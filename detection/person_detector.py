"""
Person Detector Module
======================

Phát hiện người trong vùng nguy hiểm (ROI).
Hỗ trợ:
- Phát hiện bằng segmentation mask
- Đếm frame liên tiếp để tránh false positive
- Debouncing để tránh tắt/bật liên tục
"""

import cv2
import numpy as np
import time
from dataclasses import dataclass, field
from typing import Any, Optional, List, Tuple

from .base_detector import BaseDetector, DetectionResult, create_mask_from_polygon, check_mask_intersection
from .model_loader import ModelLoader


@dataclass
class PersonBox:
    """Thông tin một người được phát hiện"""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    person_id: Optional[int]
    mask: Optional[np.ndarray]
    in_roi: bool = False


@dataclass
class PersonDetectionResult(DetectionResult):
    """Kết quả phát hiện người"""
    person_count: int = 0
    person_in_roi: bool = False
    person_boxes: List[PersonBox] = field(default_factory=list)
    consecutive_count: int = 0
    should_alarm: bool = False


class PersonDetector(BaseDetector):
    """
    Phát hiện người trong vùng nguy hiểm
    
    Features:
    - Sử dụng segmentation mask để kiểm tra ROI chính xác
    - Đếm frame liên tiếp trước khi báo động
    - Debouncing khi người rời ROI
    
    Usage:
        detector = PersonDetector(
            roi_points=[(x1,y1), (x2,y2), ...],
            consecutive_threshold=3,
            no_detection_threshold=5
        )
        
        result = detector.detect(frame, yolo_result)
        if result.should_alarm:
            send_alarm()
    """
    
    def __init__(
        self,
        roi_points: List[Tuple[int, int]],
        person_class_id: int = 0,
        consecutive_threshold: int = 3,
        no_detection_threshold: int = 5,
    ):
        """
        Args:
            roi_points: Các điểm định nghĩa vùng nguy hiểm
            person_class_id: Class ID của người trong model
            consecutive_threshold: Số frame liên tiếp để BẬT cảnh báo
            no_detection_threshold: Số frame để TẮT cảnh báo
        """
        super().__init__()
        
        self.roi_points = roi_points
        self.person_class_id = person_class_id
        self.consecutive_threshold = consecutive_threshold
        self.no_detection_threshold = no_detection_threshold
        
        # Trạng thái
        self._consecutive_count = 0
        self._no_detection_count = 0
        self._alarm_state = False
        self._alerted_ids: set = set()
        self._roi_mask: Optional[np.ndarray] = None
        self._frame_size: Optional[Tuple[int, int]] = None
        
        self._is_initialized = True
    
    def detect(self, frame: np.ndarray, yolo_result: Any = None) -> PersonDetectionResult:
        """Phát hiện người trong ROI
        
        Args:
            frame: Frame video (numpy array BGR)
            yolo_result: Kết quả từ YOLO (optional)
            
        Returns:
            PersonDetectionResult
        """
        self._detection_count += 1
        current_time = time.time()
        
        h, w = frame.shape[:2]
        
        # Tạo ROI mask nếu chưa có hoặc kích thước thay đổi
        if self._roi_mask is None or self._frame_size != (w, h):
            self._roi_mask = create_mask_from_polygon(self.roi_points, w, h)
            self._frame_size = (w, h)
        
        # Nếu không có YOLO result, trả về kết quả rỗng
        if yolo_result is None or yolo_result.boxes is None:
            return self._create_empty_result(current_time)
        
        # Xử lý detection
        person_boxes = self._extract_person_boxes(yolo_result, w, h)
        person_in_roi = self._check_persons_in_roi(person_boxes)
        
        # Cập nhật trạng thái
        should_alarm = self._update_alarm_state(person_in_roi)
        
        result = PersonDetectionResult(
            detected=len(person_boxes) > 0,
            confidence=max((pb.confidence for pb in person_boxes), default=0.0),
            timestamp=current_time,
            frame_id=self._detection_count,
            person_count=len(person_boxes),
            person_in_roi=person_in_roi,
            person_boxes=person_boxes,
            consecutive_count=self._consecutive_count,
            should_alarm=should_alarm,
        )
        
        self._last_result = result
        return result
    
    def _extract_person_boxes(self, yolo_result: Any, 
                               width: int, height: int) -> List[PersonBox]:
        """Trích xuất thông tin người từ YOLO result"""
        person_boxes = []
        
        boxes = yolo_result.boxes
        masks = yolo_result.masks
        ids = getattr(boxes, 'id', None)
        
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i])
            
            if cls_id != self.person_class_id:
                continue
            
            x1, y1, x2, y2 = boxes.xyxy[i]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            conf = float(boxes.conf[i])
            person_id = int(ids[i]) if ids is not None and i < len(ids) else None
            
            # Lấy mask
            person_mask = None
            if masks is not None and i < len(masks.data):
                mask_data = masks.data[i].cpu().numpy()
                mask_resized = cv2.resize(mask_data, (width, height), 
                                          interpolation=cv2.INTER_NEAREST)
                person_mask = (mask_resized > 0.5).astype(np.uint8) * 255
            
            person_boxes.append(PersonBox(
                bbox=(x1, y1, x2, y2),
                confidence=conf,
                person_id=person_id,
                mask=person_mask,
            ))
        
        return person_boxes
    
    def _check_persons_in_roi(self, person_boxes: List[PersonBox]) -> bool:
        """Kiểm tra có người trong ROI không"""
        for pb in person_boxes:
            if pb.mask is not None:
                # Kiểm tra bằng mask
                has_intersection, _ = check_mask_intersection(pb.mask, self._roi_mask)
                if has_intersection:
                    pb.in_roi = True
                    return True
            else:
                # Fallback: kiểm tra bằng bbox
                if self._check_bbox_in_roi(pb.bbox):
                    pb.in_roi = True
                    return True
        
        return False
    
    def _check_bbox_in_roi(self, bbox: Tuple[int, int, int, int]) -> bool:
        """Kiểm tra bbox có trong ROI không"""
        x1, y1, x2, y2 = bbox
        
        # Tạo mask cho bbox
        h, w = self._frame_size[1], self._frame_size[0]
        bbox_polygon = np.array([
            [x1, y1], [x2, y1], [x2, y2], [x1, y2]
        ], dtype=np.int32)
        
        bbox_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(bbox_mask, [bbox_polygon], 255)
        
        # Kiểm tra giao nhau
        has_intersection, _ = check_mask_intersection(bbox_mask, self._roi_mask)
        return has_intersection
    
    def _update_alarm_state(self, person_in_roi: bool) -> bool:
        """Cập nhật trạng thái báo động
        
        Returns:
            True nếu nên BẬT báo động mới (lần đầu đạt ngưỡng)
        """
        should_trigger_new_alarm = False
        
        if person_in_roi:
            # Reset counter tắt
            self._no_detection_count = 0
            self._consecutive_count += 1
            
            # Kiểm tra đạt ngưỡng
            if self._consecutive_count >= self.consecutive_threshold:
                if not self._alarm_state:
                    # Lần đầu đạt ngưỡng -> trigger alarm
                    self._alarm_state = True
                    should_trigger_new_alarm = True
                
                # Reset counter để đếm lại
                self._consecutive_count = 0
        else:
            # Không có người trong ROI
            self._no_detection_count += 1
            
            # Chỉ reset consecutive_count sau một số frame
            if self._no_detection_count >= self.no_detection_threshold:
                self._consecutive_count = 0
                self._alarm_state = False
        
        return should_trigger_new_alarm
    
    def _create_empty_result(self, timestamp: float) -> PersonDetectionResult:
        """Tạo kết quả rỗng khi không có detection"""
        # Vẫn cập nhật no_detection_count
        self._no_detection_count += 1
        if self._no_detection_count >= self.no_detection_threshold:
            self._consecutive_count = 0
            self._alarm_state = False
        
        return PersonDetectionResult(
            detected=False,
            timestamp=timestamp,
            frame_id=self._detection_count,
        )
    
    def reset(self) -> None:
        """Reset trạng thái detector"""
        self._consecutive_count = 0
        self._no_detection_count = 0
        self._alarm_state = False
        self._alerted_ids.clear()
        self._last_result = None
    
    def get_state(self) -> dict:
        """Lấy trạng thái hiện tại"""
        return {
            "alarm_state": self._alarm_state,
            "consecutive_count": self._consecutive_count,
            "no_detection_count": self._no_detection_count,
            "consecutive_threshold": self.consecutive_threshold,
            "no_detection_threshold": self.no_detection_threshold,
        }
    
    @property
    def alarm_state(self) -> bool:
        """Trạng thái báo động hiện tại"""
        return self._alarm_state
    
    def update_roi(self, roi_points: List[Tuple[int, int]]) -> None:
        """Cập nhật ROI points
        
        Args:
            roi_points: Danh sách điểm ROI mới
        """
        self.roi_points = roi_points
        self._roi_mask = None  # Force recreate mask
    
    def should_turn_off_alarm(self) -> bool:
        """Kiểm tra có nên TẮT báo động không
        
        Returns:
            True nếu đã không phát hiện đủ số frame
        """
        return (self._no_detection_count >= self.no_detection_threshold and 
                self._alarm_state == False)

