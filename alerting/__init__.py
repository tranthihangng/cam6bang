"""
Logging Module
==============

Module ghi log và lưu ảnh cảnh báo.

Public API:
- AlertLogger: Ghi log cảnh báo khẩn cấp
- ImageSaver: Lưu ảnh cảnh báo
"""

from .alert_logger import AlertLogger, AlertLogEntry
from .image_saver import ImageSaver

__all__ = [
    'AlertLogger',
    'AlertLogEntry', 
    'ImageSaver',
]

