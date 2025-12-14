"""
Alert Logger Module
===================

Ghi log cảnh báo khẩn cấp ra file JSON.

Features:
- Tự động tạo thư mục theo ngày
- Thread-safe
- Throttling để tránh spam
"""

import os
import json
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AlertLogEntry:
    """Entry cho log cảnh báo"""
    timestamp: str
    alert_type: str
    camera_id: str
    severity: str = "HIGH"
    description: str = ""
    location: str = ""
    camera_ip: str = ""
    action_taken: str = ""
    extra_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        data = asdict(self)
        # Flatten extra_data
        if data.get('extra_data'):
            data.update(data.pop('extra_data'))
        else:
            data.pop('extra_data', None)
        return data


class AlertLogger:
    """
    Ghi log cảnh báo khẩn cấp
    
    Features:
    - Tự động tạo thư mục theo ngày
    - Thread-safe
    - Throttling để tránh spam log
    - JSON format
    
    Usage:
        logger = AlertLogger(
            logs_dir="logs",
            camera_id="camera_1",
            throttle_interval=5.0
        )
        
        # Ghi log người
        logger.log_person_alert(
            description="Phát hiện người trong vùng nguy hiểm",
            extra_data={"frames_detected": 3}
        )
        
        # Ghi log than
        logger.log_coal_alert(
            coal_ratio=85.5,
            threshold=73.0
        )
    """
    
    def __init__(
        self,
        logs_dir: str = "logs",
        camera_id: str = "camera_1",
        camera_ip: str = "",
        location: str = "Vùng giám sát",
        throttle_interval: float = 5.0,
    ):
        """
        Args:
            logs_dir: Thư mục gốc chứa log
            camera_id: ID của camera
            camera_ip: IP của camera
            location: Vị trí camera
            throttle_interval: Khoảng thời gian tối thiểu giữa các log cùng loại (giây)
        """
        self.logs_dir = logs_dir
        self.camera_id = camera_id
        self.camera_ip = camera_ip
        self.location = location
        self.throttle_interval = throttle_interval
        
        self._lock = threading.Lock()
        self._last_log_time: Dict[str, float] = {}  # {alert_type: timestamp}
        
        # Tạo thư mục logs
        os.makedirs(logs_dir, exist_ok=True)
    
    def _get_daily_log_path(self) -> str:
        """Lấy đường dẫn file log theo ngày"""
        day = datetime.now().strftime("%Y%m%d")
        day_dir = os.path.join(self.logs_dir, day)
        os.makedirs(day_dir, exist_ok=True)
        return os.path.join(day_dir, f"alerts_{self.camera_id}_{day}.log")
    
    def _should_log(self, alert_type: str) -> bool:
        """Kiểm tra có nên ghi log không (throttling)"""
        current_time = time.time()
        
        with self._lock:
            last_time = self._last_log_time.get(alert_type, 0)
            
            if current_time - last_time >= self.throttle_interval:
                self._last_log_time[alert_type] = current_time
                return True
            
            return False
    
    def log(self, entry: AlertLogEntry, force: bool = False) -> bool:
        """Ghi log entry
        
        Args:
            entry: Log entry
            force: Bỏ qua throttling
            
        Returns:
            True nếu ghi thành công
        """
        # Kiểm tra throttling
        if not force and not self._should_log(entry.alert_type):
            return False
        
        try:
            log_path = self._get_daily_log_path()
            
            with self._lock:
                with open(log_path, "a", encoding="utf-8") as f:
                    json.dump(entry.to_dict(), f, ensure_ascii=False)
                    f.write("\n")
            
            return True
            
        except Exception as e:
            print(f"Lỗi ghi log: {e}")
            return False
    
    def log_person_alert(
        self,
        description: str = "",
        frames_detected: int = 0,
        threshold: int = 3,
        extra_data: Dict[str, Any] = None,
        force: bool = False,
    ) -> bool:
        """Ghi log cảnh báo người
        
        Args:
            description: Mô tả cảnh báo
            frames_detected: Số frame liên tiếp phát hiện
            threshold: Ngưỡng frame
            extra_data: Dữ liệu bổ sung
            force: Bỏ qua throttling
            
        Returns:
            True nếu ghi thành công
        """
        if not description:
            description = f"Phát hiện người trong vùng nguy hiểm ({frames_detected} frame liên tiếp)"
        
        data = extra_data or {}
        data.update({
            "frames_detected": frames_detected,
            "threshold": threshold,
        })
        
        entry = AlertLogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            alert_type="person_detection",
            camera_id=self.camera_id,
            severity="HIGH",
            description=description,
            location=self.location,
            camera_ip=self.camera_ip,
            action_taken="Gửi tín hiệu báo động PLC và lưu ảnh",
            extra_data=data,
        )
        
        return self.log(entry, force)
    
    def log_coal_alert(
        self,
        coal_ratio: float,
        threshold: float = 73.0,
        description: str = "",
        extra_data: Dict[str, Any] = None,
        force: bool = False,
    ) -> bool:
        """Ghi log cảnh báo tắc than
        
        Args:
            coal_ratio: Tỷ lệ than đo được (%)
            threshold: Ngưỡng tỷ lệ
            description: Mô tả cảnh báo
            extra_data: Dữ liệu bổ sung
            force: Bỏ qua throttling
            
        Returns:
            True nếu ghi thành công
        """
        if not description:
            description = f"Phát hiện tắc than với tỷ lệ {coal_ratio:.2f}% >= {threshold:.1f}%"
        
        data = extra_data or {}
        data.update({
            "coal_ratio": coal_ratio,
            "threshold": threshold,
        })
        
        entry = AlertLogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            alert_type="coal_blockage",
            camera_id=self.camera_id,
            severity="HIGH",
            description=description,
            location=self.location,
            camera_ip=self.camera_ip,
            action_taken="Gửi tín hiệu báo động PLC và lưu ảnh",
            extra_data=data,
        )
        
        return self.log(entry, force)
    
    def log_system_event(
        self,
        event_type: str,
        description: str,
        severity: str = "INFO",
        extra_data: Dict[str, Any] = None,
        force: bool = True,
    ) -> bool:
        """Ghi log sự kiện hệ thống
        
        Args:
            event_type: Loại sự kiện
            description: Mô tả
            severity: Mức độ (INFO, WARNING, ERROR)
            extra_data: Dữ liệu bổ sung
            force: Bỏ qua throttling
            
        Returns:
            True nếu ghi thành công
        """
        entry = AlertLogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            alert_type=event_type,
            camera_id=self.camera_id,
            severity=severity,
            description=description,
            location=self.location,
            camera_ip=self.camera_ip,
            extra_data=extra_data or {},
        )
        
        return self.log(entry, force)
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Lấy thống kê log"""
        log_path = self._get_daily_log_path()
        
        stats = {
            "log_path": log_path,
            "exists": os.path.exists(log_path),
            "size_bytes": 0,
            "line_count": 0,
        }
        
        if stats["exists"]:
            try:
                stats["size_bytes"] = os.path.getsize(log_path)
                with open(log_path, "r", encoding="utf-8") as f:
                    stats["line_count"] = sum(1 for _ in f)
            except:
                pass
        
        return stats

