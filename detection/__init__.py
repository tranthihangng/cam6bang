"""
Detection Module
================

Module phát hiện người và tắc than sử dụng YOLO Segmentation.

Public API:
- MultiModelLoader: Load và quản lý nhiều YOLO models (multi-camera support)
- ModelLoader: Alias cho MultiModelLoader (backward compatible)
- PersonDetector: Phát hiện người trong ROI
- CoalDetector: Phát hiện tắc than
- ROIManager: Quản lý vùng quan tâm (ROI)
- DetectionResult: Kết quả detection
"""

from .model_loader import MultiModelLoader, ModelLoader, ModelInfo
from .person_detector import PersonDetector, PersonDetectionResult
from .coal_detector import CoalDetector, CoalDetectionResult
from .roi_manager import ROIManager
from .base_detector import DetectionResult

__all__ = [
    'MultiModelLoader',
    'ModelLoader',
    'ModelInfo',
    'PersonDetector',
    'PersonDetectionResult',
    'CoalDetector',
    'CoalDetectionResult',
    'ROIManager',
    'DetectionResult',
]

