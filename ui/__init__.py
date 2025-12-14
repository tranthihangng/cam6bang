"""
UI Module
=========

Giao diện người dùng cho hệ thống giám sát.

Public API:
- MainWindow: Cửa sổ chính hiển thị multi-camera
- ConfigPanel: Panel cấu hình hệ thống (cho người không biết code)
- ROIEditor: Vẽ ROI trực quan trên video
"""

from .main_window import MainWindow
from .config_panel import ConfigPanel
from .roi_editor import ROIEditor, open_roi_editor

__all__ = [
    'MainWindow',
    'ConfigPanel',
    'ROIEditor',
    'open_roi_editor',
]

