"""
System Configuration Module
===========================

Quản lý cấu hình toàn hệ thống bao gồm nhiều camera.

Sử dụng:
    # Load từ file
    config = load_config("system_config.json")
    
    # Truy cập camera
    for camera in config.cameras:
        print(camera.name, camera.plc.ip)
    
    # Lưu cấu hình
    save_config(config, "system_config.json")
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from .camera_config import CameraConfig, PLCConfig, ROIConfig, DetectionConfig


@dataclass
class ModelConfig:
    """Cấu hình cho một model YOLO"""
    model_id: str = "model_1"
    path: str = "best_segment_26_11.pt"
    name: str = "Model Than & Người"
    cameras: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5, 6])  # Camera numbers using this model
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "cameras": self.cameras,
        }
    
    @classmethod
    def from_dict(cls, model_id: str, data: Dict[str, Any]) -> 'ModelConfig':
        return cls(
            model_id=model_id,
            path=data.get("path", "best_segment_26_11.pt"),
            name=data.get("name", "Model"),
            cameras=data.get("cameras", [1, 2, 3, 4, 5, 6]),
        )


@dataclass
class SystemConfig:
    """Cấu hình toàn hệ thống"""
    
    # Thông tin hệ thống
    version: str = "2.0.0"
    app_name: str = "Phần Mềm Giám Sát Sự Cố"
    company: str = "NATECH Technology"
    
    # Đường dẫn model YOLO mặc định (backward compatible)
    model_path: str = "best_segment_26_11.pt"
    
    # Cấu hình multiple models - camera nào dùng model nào
    # Format: {"model_1": ModelConfig, "model_2": ModelConfig, ...}
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    
    # Đường dẫn thư mục lưu trữ
    artifacts_dir: str = "artifacts"
    logs_dir: str = "logs"
    
    # Danh sách camera (hỗ trợ đa camera)
    cameras: List[CameraConfig] = field(default_factory=list)
    
    # Cài đặt UI
    ui_update_interval_ms: int = 100  # Khoảng thời gian cập nhật UI (ms)
    max_log_lines: int = 100  # Số dòng log tối đa hiển thị
    
    # Cài đặt throttling
    alert_display_interval: float = 3.0  # Giây
    image_save_interval: float = 5.0  # Giây
    ui_debounce_interval: float = 1.0  # Giây
    
    def get_model_for_camera(self, camera_number: int) -> Optional[ModelConfig]:
        """Lấy model config cho camera cụ thể
        
        Args:
            camera_number: Số thứ tự camera (1, 2, 3, ...)
            
        Returns:
            ModelConfig hoặc None nếu không tìm thấy
        """
        for model_id, model_cfg in self.models.items():
            if camera_number in model_cfg.cameras:
                return model_cfg
        
        # Fallback: trả về model đầu tiên hoặc tạo từ model_path
        if self.models:
            return list(self.models.values())[0]
        
        # Backward compatible: dùng model_path nếu không có models config
        return ModelConfig(
            model_id="default",
            path=self.model_path,
            name="Default Model",
            cameras=list(range(1, 10))
        )
    
    def get_model_path_for_camera(self, camera_number: int) -> str:
        """Lấy đường dẫn model cho camera
        
        Args:
            camera_number: Số thứ tự camera (1, 2, 3, ...)
            
        Returns:
            Đường dẫn model
        """
        model_cfg = self.get_model_for_camera(camera_number)
        if model_cfg:
            return model_cfg.path
        return self.model_path
    
    def get_all_model_paths(self) -> List[str]:
        """Lấy danh sách tất cả đường dẫn model cần load"""
        paths = set()
        if self.models:
            for model_cfg in self.models.values():
                paths.add(model_cfg.path)
        else:
            paths.add(self.model_path)
        return list(paths)
    
    def get_camera_by_id(self, camera_id: str) -> Optional[CameraConfig]:
        """Lấy cấu hình camera theo ID"""
        for camera in self.cameras:
            if camera.camera_id == camera_id:
                return camera
        return None
    
    def get_enabled_cameras(self) -> List[CameraConfig]:
        """Lấy danh sách camera đang enabled"""
        return [cam for cam in self.cameras if cam.enabled]
    
    def add_camera(self, camera: CameraConfig) -> bool:
        """Thêm camera mới
        
        Returns:
            True nếu thêm thành công, False nếu camera_id đã tồn tại
        """
        if self.get_camera_by_id(camera.camera_id):
            return False
        self.cameras.append(camera)
        return True
    
    def remove_camera(self, camera_id: str) -> bool:
        """Xóa camera theo ID
        
        Returns:
            True nếu xóa thành công, False nếu không tìm thấy
        """
        for i, cam in enumerate(self.cameras):
            if cam.camera_id == camera_id:
                self.cameras.pop(i)
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary để lưu JSON"""
        result = {
            "version": self.version,
            "app_name": self.app_name,
            "company": self.company,
            "model_path": self.model_path,
            "artifacts_dir": self.artifacts_dir,
            "logs_dir": self.logs_dir,
            "cameras": [cam.to_dict() for cam in self.cameras],
            "ui_update_interval_ms": self.ui_update_interval_ms,
            "max_log_lines": self.max_log_lines,
            "alert_display_interval": self.alert_display_interval,
            "image_save_interval": self.image_save_interval,
            "ui_debounce_interval": self.ui_debounce_interval,
        }
        
        # Thêm models nếu có
        if self.models:
            result["models"] = {
                model_id: model_cfg.to_dict() 
                for model_id, model_cfg in self.models.items()
            }
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """Tạo instance từ dictionary"""
        cameras = [CameraConfig.from_dict(cam_data) 
                   for cam_data in data.get("cameras", [])]
        
        # Parse models config
        models = {}
        models_data = data.get("models", {})
        for model_id, model_data in models_data.items():
            models[model_id] = ModelConfig.from_dict(model_id, model_data)
        
        return cls(
            version=data.get("version", "2.0.0"),
            app_name=data.get("app_name", "Phần Mềm Giám Sát Sự Cố"),
            company=data.get("company", "NATECH Technology"),
            model_path=data.get("model_path", "best_segment_26_11.pt"),
            models=models,
            artifacts_dir=data.get("artifacts_dir", "artifacts"),
            logs_dir=data.get("logs_dir", "logs"),
            cameras=cameras,
            ui_update_interval_ms=data.get("ui_update_interval_ms", 100),
            max_log_lines=data.get("max_log_lines", 100),
            alert_display_interval=data.get("alert_display_interval", 3.0),
            image_save_interval=data.get("image_save_interval", 5.0),
            ui_debounce_interval=data.get("ui_debounce_interval", 1.0),
        )
    
    def validate(self) -> List[str]:
        """Kiểm tra cấu hình có hợp lệ không
        
        Returns:
            List các lỗi nếu có, empty list nếu hợp lệ
        """
        errors = []
        
        if not self.cameras:
            errors.append("Phải có ít nhất 1 camera")
        
        # Kiểm tra camera_id trùng
        ids = [cam.camera_id for cam in self.cameras]
        if len(ids) != len(set(ids)):
            errors.append("Có camera_id bị trùng")
        
        # Kiểm tra từng camera
        for cam in self.cameras:
            cam_errors = cam.validate()
            for err in cam_errors:
                errors.append(f"Camera '{cam.name}': {err}")
        
        return errors


def load_config(config_path: str) -> SystemConfig:
    """Load cấu hình từ file JSON
    
    Args:
        config_path: Đường dẫn file JSON
        
    Returns:
        SystemConfig object
        
    Raises:
        FileNotFoundError: Nếu file không tồn tại
        json.JSONDecodeError: Nếu file JSON không hợp lệ
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return SystemConfig.from_dict(data)


def save_config(config: SystemConfig, config_path: str) -> None:
    """Lưu cấu hình ra file JSON
    
    Args:
        config: SystemConfig object
        config_path: Đường dẫn file JSON
    """
    path = Path(config_path)
    
    # Tạo thư mục nếu chưa có
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config.to_dict(), f, indent=4, ensure_ascii=False)


def create_default_config(num_cameras: int = 1) -> SystemConfig:
    """Tạo cấu hình mặc định với số camera chỉ định
    
    Args:
        num_cameras: Số lượng camera (1-6)
        
    Returns:
        SystemConfig với cấu hình mặc định
    """
    config = SystemConfig()
    
    # Tạo models config mặc định
    # Model 1: cho camera 1-5
    # Model 2: cho camera 6
    if num_cameras <= 5:
        config.models = {
            "model_1": ModelConfig(
                model_id="model_1",
                path="best_segment_26_11.pt",
                name="Model Than & Nguoi",
                cameras=list(range(1, num_cameras + 1))
            )
        }
    else:
        config.models = {
            "model_1": ModelConfig(
                model_id="model_1",
                path="best_segment_26_11.pt",
                name="Model Than & Nguoi",
                cameras=[1, 2, 3, 4, 5]
            ),
            "model_2": ModelConfig(
                model_id="model_2",
                path="best_segment_27_11_copy.pt",
                name="Model Khac",
                cameras=[6]
            )
        }
    
    # Tạo các camera với PLC riêng
    for i in range(1, num_cameras + 1):
        # Tính byte và bit cho alarm (mỗi camera dùng 2 bits: person và coal)
        # Camera 1-4: byte 6, bits 0-7
        # Camera 5-8: byte 7, bits 0-7
        byte_offset = 6 + ((i - 1) * 2) // 8
        bit_offset_person = ((i - 1) * 2) % 8
        bit_offset_coal = bit_offset_person + 1
        
        camera = CameraConfig(
            camera_id=f"camera_{i}",
            name=f"Camera {i}",
            rtsp_url=f"rtsp://admin:password@192.168.1.{180+i}:554/Streaming/Channels/102",
            plc=PLCConfig(
                ip=f"192.168.0.{3+i}",  # PLC 1: 192.168.0.4, PLC 2: 192.168.0.5, ...
                db_number=300,
                person_alarm_byte=byte_offset,
                person_alarm_bit=bit_offset_person,
                coal_alarm_byte=byte_offset,
                coal_alarm_bit=bit_offset_coal,
            ),
            roi=ROIConfig(),
            detection=DetectionConfig(),
        )
        config.cameras.append(camera)
    
    return config


def create_sample_config_file(output_path: str, num_cameras: int = 2) -> None:
    """Tạo file cấu hình mẫu
    
    Args:
        output_path: Đường dẫn file output
        num_cameras: Số camera trong file mẫu
    """
    config = create_default_config(num_cameras)
    save_config(config, output_path)
    print(f"Đã tạo file cấu hình mẫu: {output_path}")

