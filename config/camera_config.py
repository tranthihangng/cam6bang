"""
Camera Configuration Module
===========================

Định nghĩa cấu hình cho từng camera và PLC kết nối.

Mỗi camera có:
- ID duy nhất
- Nguồn video (RTSP URL hoặc file path)
- Cấu hình PLC riêng (IP, DB, addresses)
- Cấu hình ROI riêng
- Cấu hình detection riêng
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import json


@dataclass
class PLCConfig:
    """Cấu hình kết nối PLC cho mỗi camera"""
    
    # Thông tin kết nối
    ip: str = "192.168.0.4"
    port: int = 102
    rack: int = 0
    slot: int = 2
    
    # Data Block
    db_number: int = 300
    
    # Địa chỉ báo động người (Byte.Bit)
    person_alarm_byte: int = 6
    person_alarm_bit: int = 0
    
    # Địa chỉ báo động tắc than (Byte.Bit)
    coal_alarm_byte: int = 6
    coal_alarm_bit: int = 1
    
    # Kết nối
    enabled: bool = True
    reconnect_attempts: int = 3
    health_check_interval: float = 10.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        return {
            "ip": self.ip,
            "port": self.port,
            "rack": self.rack,
            "slot": self.slot,
            "db_number": self.db_number,
            "person_alarm_byte": self.person_alarm_byte,
            "person_alarm_bit": self.person_alarm_bit,
            "coal_alarm_byte": self.coal_alarm_byte,
            "coal_alarm_bit": self.coal_alarm_bit,
            "enabled": self.enabled,
            "reconnect_attempts": self.reconnect_attempts,
            "health_check_interval": self.health_check_interval,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PLCConfig':
        """Tạo instance từ dictionary"""
        return cls(
            ip=data.get("ip", "192.168.0.4"),
            port=data.get("port", 102),
            rack=data.get("rack", 0),
            slot=data.get("slot", 2),
            db_number=data.get("db_number", 300),
            person_alarm_byte=data.get("person_alarm_byte", 6),
            person_alarm_bit=data.get("person_alarm_bit", 0),
            coal_alarm_byte=data.get("coal_alarm_byte", 6),
            coal_alarm_bit=data.get("coal_alarm_bit", 1),
            enabled=data.get("enabled", True),
            reconnect_attempts=data.get("reconnect_attempts", 3),
            health_check_interval=data.get("health_check_interval", 10.0),
        )


@dataclass
class ROIConfig:
    """Cấu hình vùng quan tâm (ROI) cho detection"""
    
    # Độ phân giải tham chiếu (ROI được định nghĩa ở độ phân giải này)
    reference_resolution: Tuple[int, int] = (1920, 1080)
    
    # ROI cho vùng nguy hiểm (phát hiện người)
    roi_person: List[Tuple[int, int]] = field(default_factory=lambda: [
        (393, 333), (541, 333), (553, 292), (628, 292),
        (660, 35), (777, 35), (857, 330), (899, 330),
        (939, 650), (299, 642)
    ])
    
    # ROI cho vùng than (phát hiện tắc than)
    roi_coal: List[Tuple[int, int]] = field(default_factory=lambda: [
        (547, 629), (567, 451), (892, 460), (923, 637)
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        return {
            "reference_resolution": list(self.reference_resolution),
            "roi_person": [list(p) for p in self.roi_person],
            "roi_coal": [list(p) for p in self.roi_coal],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ROIConfig':
        """Tạo instance từ dictionary"""
        ref_res = data.get("reference_resolution", [1920, 1080])
        roi_person = data.get("roi_person", [])
        roi_coal = data.get("roi_coal", [])
        
        return cls(
            reference_resolution=tuple(ref_res),
            roi_person=[tuple(p) for p in roi_person] if roi_person else cls.roi_person,
            roi_coal=[tuple(p) for p in roi_coal] if roi_coal else cls.roi_coal,
        )
    
    def scale_roi(self, roi_points: List[Tuple[int, int]], 
                  target_width: int, target_height: int) -> List[Tuple[int, int]]:
        """Scale ROI từ độ phân giải gốc sang độ phân giải mục tiêu"""
        ref_width, ref_height = self.reference_resolution
        scale_x = target_width / ref_width
        scale_y = target_height / ref_height
        return [(int(x * scale_x), int(y * scale_y)) for (x, y) in roi_points]
    
    def get_scaled_roi_person(self, width: int, height: int) -> List[Tuple[int, int]]:
        """Lấy ROI người đã scale"""
        return self.scale_roi(self.roi_person, width, height)
    
    def get_scaled_roi_coal(self, width: int, height: int) -> List[Tuple[int, int]]:
        """Lấy ROI than đã scale"""
        return self.scale_roi(self.roi_coal, width, height)


@dataclass
class DetectionConfig:
    """Cấu hình detection cho mỗi camera"""
    
    # Ngưỡng tin cậy cho YOLO
    confidence_threshold: float = 0.7
    
    # Phát hiện người
    person_detection_enabled: bool = True
    person_consecutive_threshold: int = 3  # Số frame liên tiếp để BẬT cảnh báo
    person_no_detection_threshold: int = 5  # Số frame để TẮT cảnh báo
    
    # Phát hiện tắc than
    coal_detection_enabled: bool = True
    coal_ratio_threshold: float = 73.0  # Ngưỡng tỷ lệ than (%)
    coal_consecutive_threshold: int = 5  # Số frame liên tiếp để BẬT cảnh báo
    coal_no_blockage_threshold: int = 5  # Số frame để TẮT cảnh báo
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        return {
            "confidence_threshold": self.confidence_threshold,
            "person_detection_enabled": self.person_detection_enabled,
            "person_consecutive_threshold": self.person_consecutive_threshold,
            "person_no_detection_threshold": self.person_no_detection_threshold,
            "coal_detection_enabled": self.coal_detection_enabled,
            "coal_ratio_threshold": self.coal_ratio_threshold,
            "coal_consecutive_threshold": self.coal_consecutive_threshold,
            "coal_no_blockage_threshold": self.coal_no_blockage_threshold,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DetectionConfig':
        """Tạo instance từ dictionary"""
        return cls(
            confidence_threshold=data.get("confidence_threshold", 0.7),
            person_detection_enabled=data.get("person_detection_enabled", True),
            person_consecutive_threshold=data.get("person_consecutive_threshold", 3),
            person_no_detection_threshold=data.get("person_no_detection_threshold", 5),
            coal_detection_enabled=data.get("coal_detection_enabled", True),
            coal_ratio_threshold=data.get("coal_ratio_threshold", 73.0),
            coal_consecutive_threshold=data.get("coal_consecutive_threshold", 5),
            coal_no_blockage_threshold=data.get("coal_no_blockage_threshold", 5),
        )


@dataclass
class CameraConfig:
    """Cấu hình đầy đủ cho một camera"""
    
    # ID duy nhất cho camera
    camera_id: str = "camera_1"
    
    # Số thứ tự camera (dùng để map với model)
    camera_number: int = 1
    
    # Tên hiển thị
    name: str = "Camera 1"
    
    # Nguồn video
    rtsp_url: str = ""
    video_path: str = ""  # Nếu có, ưu tiên video_path hơn rtsp_url
    
    # FPS mục tiêu
    target_fps: int = 22
    
    # Cấu hình các thành phần
    plc: PLCConfig = field(default_factory=PLCConfig)
    roi: ROIConfig = field(default_factory=ROIConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    
    # Trạng thái
    enabled: bool = True
    
    def get_video_source(self) -> str:
        """Trả về nguồn video (ưu tiên video_path nếu có)"""
        if self.video_path:
            return self.video_path
        return self.rtsp_url
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        return {
            "camera_id": self.camera_id,
            "camera_number": self.camera_number,
            "name": self.name,
            "rtsp_url": self.rtsp_url,
            "video_path": self.video_path,
            "target_fps": self.target_fps,
            "plc": self.plc.to_dict(),
            "roi": self.roi.to_dict(),
            "detection": self.detection.to_dict(),
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CameraConfig':
        """Tạo instance từ dictionary"""
        return cls(
            camera_id=data.get("camera_id", "camera_1"),
            camera_number=data.get("camera_number", 1),
            name=data.get("name", "Camera 1"),
            rtsp_url=data.get("rtsp_url", ""),
            video_path=data.get("video_path", ""),
            target_fps=data.get("target_fps", 22),
            plc=PLCConfig.from_dict(data.get("plc", {})),
            roi=ROIConfig.from_dict(data.get("roi", {})),
            detection=DetectionConfig.from_dict(data.get("detection", {})),
            enabled=data.get("enabled", True),
        )
    
    def validate(self) -> List[str]:
        """Kiểm tra cấu hình có hợp lệ không
        
        Returns:
            List các lỗi nếu có, empty list nếu hợp lệ
        """
        errors = []
        
        if not self.camera_id:
            errors.append("camera_id không được để trống")
        
        if not self.rtsp_url and not self.video_path:
            errors.append("Phải có ít nhất rtsp_url hoặc video_path")
        
        if self.target_fps <= 0:
            errors.append("target_fps phải > 0")
        
        if self.detection.confidence_threshold < 0 or self.detection.confidence_threshold > 1:
            errors.append("confidence_threshold phải trong khoảng [0, 1]")
        
        return errors

