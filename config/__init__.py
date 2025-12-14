"""
Configuration Module
====================

Quản lý cấu hình hệ thống và camera.

Public API:
- SystemConfig: Cấu hình chung toàn hệ thống
- CameraConfig: Cấu hình từng camera đơn lẻ
- ModelConfig: Cấu hình model YOLO (multi-model support)
- load_config: Load cấu hình từ JSON file
- save_config: Lưu cấu hình ra JSON file
- create_default_config: Tạo cấu hình mặc định
"""

from .system_config import SystemConfig, ModelConfig, load_config, save_config, create_default_config
from .camera_config import CameraConfig, PLCConfig, ROIConfig, DetectionConfig

__all__ = [
    'SystemConfig',
    'ModelConfig',
    'CameraConfig',
    'PLCConfig',
    'ROIConfig', 
    'DetectionConfig',
    'load_config',
    'save_config',
    'create_default_config',
]

