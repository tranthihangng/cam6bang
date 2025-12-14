"""
Base Detector Module
====================

Base class cho các detector.
Định nghĩa interface chung cho PersonDetector và CoalDetector.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List, Tuple
import numpy as np


@dataclass
class DetectionResult:
    """Kết quả detection cơ bản"""
    detected: bool = False
    confidence: float = 0.0
    timestamp: float = 0.0
    frame_id: int = 0
    extra_data: dict = field(default_factory=dict)


class BaseDetector(ABC):
    """
    Abstract base class cho các detector
    
    Định nghĩa interface chung mà các detector con phải implement:
    - detect(): Phát hiện đối tượng
    - reset(): Reset trạng thái
    - get_state(): Lấy trạng thái hiện tại
    """
    
    def __init__(self):
        """Initialize base detector"""
        self._is_initialized = False
        self._detection_count = 0
        self._last_result: Optional[DetectionResult] = None
    
    @abstractmethod
    def detect(self, frame: np.ndarray, yolo_result: Any = None) -> DetectionResult:
        """Phát hiện đối tượng trong frame
        
        Args:
            frame: Frame video (numpy array, BGR format)
            yolo_result: Kết quả từ YOLO (optional, để reuse)
            
        Returns:
            DetectionResult với kết quả phát hiện
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset trạng thái detector"""
        pass
    
    @abstractmethod
    def get_state(self) -> dict:
        """Lấy trạng thái hiện tại của detector
        
        Returns:
            Dictionary chứa trạng thái
        """
        pass
    
    @property
    def detection_count(self) -> int:
        """Số lần detect đã thực hiện"""
        return self._detection_count
    
    @property
    def last_result(self) -> Optional[DetectionResult]:
        """Kết quả detection cuối cùng"""
        return self._last_result


def create_mask_from_polygon(polygon: List[Tuple[int, int]], 
                             width: int, height: int) -> np.ndarray:
    """Tạo binary mask từ polygon
    
    Args:
        polygon: List các điểm [(x1, y1), (x2, y2), ...]
        width: Chiều rộng mask
        height: Chiều cao mask
        
    Returns:
        Binary mask (numpy array uint8)
    """
    import cv2
    
    mask = np.zeros((height, width), dtype=np.uint8)
    polygon_np = np.array(polygon, dtype=np.int32)
    cv2.fillPoly(mask, [polygon_np], 255)
    return mask


def check_mask_intersection(mask1: np.ndarray, mask2: np.ndarray) -> Tuple[bool, int]:
    """Kiểm tra giao nhau giữa 2 mask
    
    Args:
        mask1: Mask thứ nhất
        mask2: Mask thứ hai
        
    Returns:
        (has_intersection, intersection_area)
    """
    import cv2
    
    intersection = cv2.bitwise_and(mask1, mask2)
    area = cv2.countNonZero(intersection)
    return area > 0, area

