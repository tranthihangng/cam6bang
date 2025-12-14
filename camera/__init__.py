"""
Camera Module
=============

Quản lý nguồn video và frame buffer.

Public API:
- VideoSource: Lớp quản lý nguồn video (RTSP/file)
- OptimizedVideoSource: Phiên bản tối ưu với low-latency
- FrameBuffer: Lớp quản lý buffer frame với thread-safe
- DualFrameBuffer: Dual buffer cho display và detection
"""

from .video_source import VideoSource, VideoInfo
from .frame_buffer import FrameBuffer, DualFrameBuffer, FrameData
from .optimized_source import (
    OptimizedVideoSource, 
    ConnectionStatus, 
    CaptureStats,
    VideoSourceType,
)

__all__ = [
    # Original
    'VideoSource',
    'VideoInfo',
    'FrameBuffer',
    'DualFrameBuffer',
    'FrameData',
    # Optimized
    'OptimizedVideoSource',
    'ConnectionStatus',
    'CaptureStats',
    'VideoSourceType',
]

