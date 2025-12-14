"""
Core Module
===========

Module điều phối chính cho hệ thống giám sát.

Public API:
- CameraMonitor: Giám sát một camera đơn lẻ
- MultiCameraApp: Quản lý nhiều camera
- ProductionMultiCameraApp: Phiên bản production-ready cho 24/7
- OptimizedCameraWorker: Worker tối ưu cho mỗi camera
- InferenceStatsManager: Quản lý thống kê inference
"""

from .camera_monitor import CameraMonitor, MonitoringState
from .multi_camera_app import MultiCameraApp
from .optimized_worker import OptimizedCameraWorker, WorkerConfig, WorkerStatus
from .inference_stats import InferenceStatsManager, get_stats_manager, CameraInferenceStats
from .production_app import ProductionMultiCameraApp, ProductionStats

__all__ = [
    # Original
    'CameraMonitor',
    'MonitoringState',
    'MultiCameraApp',
    # Production (24/7)
    'ProductionMultiCameraApp',
    'ProductionStats',
    # Optimized components
    'OptimizedCameraWorker',
    'WorkerConfig',
    'WorkerStatus',
    'InferenceStatsManager',
    'get_stats_manager',
    'CameraInferenceStats',
]

