"""
Coal Mine Monitoring System - Multi-Camera Support
===================================================

Hệ thống giám sát mỏ than đa camera với khả năng:
- Hỗ trợ nhiều camera (RTSP/Video file)
- Mỗi camera kết nối với 1 PLC riêng
- Phát hiện người trong vùng nguy hiểm
- Phát hiện tắc than
- Giao diện đa camera

Author: NATECH Technology
Version: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "NATECH Technology"

from .core.multi_camera_app import MultiCameraApp
from .core.camera_monitor import CameraMonitor
from .config.system_config import SystemConfig
from .config.camera_config import CameraConfig

__all__ = [
    'MultiCameraApp',
    'CameraMonitor', 
    'SystemConfig',
    'CameraConfig',
]

