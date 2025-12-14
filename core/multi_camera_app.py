"""
Multi-Camera Application Module
===============================

Module quản lý nhiều camera đồng thời.
Tích hợp với UI hoặc chạy headless.
"""

import threading
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from ..config import SystemConfig, CameraConfig
from ..detection import MultiModelLoader
from .camera_monitor import CameraMonitor, MonitoringState


@dataclass
class MultiCameraStats:
    """Thống kê tổng hợp nhiều camera"""
    total_cameras: int = 0
    running_cameras: int = 0
    total_person_alerts: int = 0
    total_coal_alerts: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cameras": self.total_cameras,
            "running_cameras": self.running_cameras,
            "total_person_alerts": self.total_person_alerts,
            "total_coal_alerts": self.total_coal_alerts,
        }


class MultiCameraApp:
    """
    Quản lý nhiều camera đồng thời
    
    Features:
    - Quản lý nhiều CameraMonitor instances
    - Share YOLO model giữa các camera
    - Aggregated statistics
    - Start/stop all hoặc từng camera
    
    Usage:
        # Load config
        config = load_config("system_config.json")
        
        # Tạo app
        app = MultiCameraApp(
            config=config,
            on_alert=lambda msg, cam: print(f"[{cam.camera_id}] {msg}")
        )
        
        # Khởi động tất cả
        app.start_all()
        
        # Hoặc khởi động từng camera
        app.start_camera("camera_1")
        
        # Lấy thống kê
        stats = app.get_stats()
        
        # Dừng
        app.stop_all()
    """
    
    def __init__(
        self,
        config: SystemConfig,
        on_frame: Optional[Callable[[Any, CameraMonitor], None]] = None,
        on_detection: Optional[Callable[[Any, CameraMonitor], None]] = None,
        on_alert: Optional[Callable[[str, CameraMonitor], None]] = None,
        on_state_change: Optional[Callable[[MonitoringState, CameraMonitor], None]] = None,
        on_global_alert: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            config: Cấu hình hệ thống
            on_frame: Callback khi có frame mới
            on_detection: Callback khi có detection
            on_alert: Callback khi có cảnh báo (từ camera)
            on_state_change: Callback khi trạng thái camera thay đổi
            on_global_alert: Callback cảnh báo toàn cục
        """
        self.config = config
        self.on_frame = on_frame
        self.on_detection = on_detection
        self.on_alert = on_alert
        self.on_state_change = on_state_change
        self.on_global_alert = on_global_alert
        
        # Model loader (shared, supports multiple models)
        self._model_loader = MultiModelLoader.get_instance()
        self._model_loaded = False
        
        # Camera monitors
        self._monitors: Dict[str, CameraMonitor] = {}
        self._lock = threading.Lock()
        
        # Stats
        self._stats = MultiCameraStats()
        
        # Initialize monitors
        self._init_monitors()
    
    def _init_monitors(self) -> None:
        """Khởi tạo các CameraMonitor từ config"""
        for cam_config in self.config.cameras:
            if not cam_config.enabled:
                continue
            
            monitor = CameraMonitor(
                config=cam_config,
                model_loader=self._model_loader,
                logs_dir=self.config.logs_dir,
                artifacts_dir=self.config.artifacts_dir,
                on_frame=self.on_frame,
                on_detection=self.on_detection,
                on_alert=self._handle_camera_alert,
                on_state_change=self._handle_state_change,
            )
            
            self._monitors[cam_config.camera_id] = monitor
        
        self._stats.total_cameras = len(self._monitors)
    
    def _handle_camera_alert(self, message: str, monitor: CameraMonitor) -> None:
        """Xử lý cảnh báo từ camera"""
        # Forward to callback
        if self.on_alert:
            try:
                self.on_alert(message, monitor)
            except:
                pass
    
    def _handle_state_change(self, state: MonitoringState, monitor: CameraMonitor) -> None:
        """Xử lý thay đổi trạng thái camera"""
        # Update running count
        self._update_running_count()
        
        # Forward to callback
        if self.on_state_change:
            try:
                self.on_state_change(state, monitor)
            except:
                pass
    
    def _update_running_count(self) -> None:
        """Cập nhật số camera đang chạy"""
        count = sum(1 for m in self._monitors.values() if m.is_running)
        self._stats.running_cameras = count
    
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """Load YOLO model(s)
        
        Hỗ trợ multi-model: load tất cả models từ config.models
        Mỗi camera có thể dùng model khác nhau.
        
        Args:
            model_path: Đường dẫn model đơn lẻ (None = dùng từ config.models)
            
        Returns:
            True nếu load thành công (ít nhất 1 model)
        """
        if self._model_loaded:
            return True
        
        try:
            if model_path:
                # Load single model (backward compatible)
                self._model_loader.load(
                    model_id="default",
                    model_path=model_path,
                    model_name="Default Model",
                    cameras=list(range(1, 10))
                )
                self._global_alert(f"✅ Đã load model: {model_path}")
            else:
                # Load từ config (hỗ trợ multi-model)
                results = self._model_loader.load_from_config(self.config)
                
                success_count = sum(1 for v in results.values() if v)
                fail_count = len(results) - success_count
                
                if success_count > 0:
                    self._global_alert(f"✅ Đã load {success_count} model(s)")
                    
                    # Log chi tiết models
                    for model_id, success in results.items():
                        model_info = self._model_loader.get_model_info(model_id)
                        if model_info:
                            self._global_alert(
                                f"   - {model_info.name}: cameras {model_info.cameras}"
                            )
                
                if fail_count > 0:
                    self._global_alert(f"⚠️ {fail_count} model(s) load thất bại")
                
                if success_count == 0:
                    return False
            
            self._model_loaded = True
            return True
            
        except Exception as e:
            self._global_alert(f"❌ Lỗi load model: {str(e)}")
            return False
    
    def start_all(self) -> Dict[str, bool]:
        """Khởi động tất cả camera
        
        Returns:
            Dict {camera_id: success}
        """
        # Load model nếu chưa
        if not self._model_loaded:
            if not self.load_model():
                return {cam_id: False for cam_id in self._monitors.keys()}
        
        results = {}
        
        for camera_id, monitor in self._monitors.items():
            success = monitor.start()
            results[camera_id] = success
        
        self._update_running_count()
        return results
    
    def stop_all(self) -> None:
        """Dừng tất cả camera"""
        for monitor in self._monitors.values():
            monitor.stop()
        
        self._update_running_count()
    
    def start_camera(self, camera_id: str) -> bool:
        """Khởi động một camera
        
        Args:
            camera_id: ID của camera
            
        Returns:
            True nếu khởi động thành công
        """
        # Load model nếu chưa
        if not self._model_loaded:
            if not self.load_model():
                return False
        
        monitor = self._monitors.get(camera_id)
        if not monitor:
            self._global_alert(f"❌ Không tìm thấy camera: {camera_id}")
            return False
        
        success = monitor.start()
        self._update_running_count()
        return success
    
    def stop_camera(self, camera_id: str) -> bool:
        """Dừng một camera
        
        Args:
            camera_id: ID của camera
            
        Returns:
            True nếu dừng thành công
        """
        monitor = self._monitors.get(camera_id)
        if not monitor:
            return False
        
        monitor.stop()
        self._update_running_count()
        return True
    
    def get_monitor(self, camera_id: str) -> Optional[CameraMonitor]:
        """Lấy CameraMonitor theo ID"""
        return self._monitors.get(camera_id)
    
    def get_all_monitors(self) -> List[CameraMonitor]:
        """Lấy tất cả monitors"""
        return list(self._monitors.values())
    
    def get_running_monitors(self) -> List[CameraMonitor]:
        """Lấy các monitors đang chạy"""
        return [m for m in self._monitors.values() if m.is_running]
    
    def get_stats(self) -> MultiCameraStats:
        """Lấy thống kê tổng hợp"""
        # Update aggregated stats
        total_person = 0
        total_coal = 0
        
        for monitor in self._monitors.values():
            stats = monitor.stats
            total_person += stats.person_alerts
            total_coal += stats.coal_alerts
        
        self._stats.total_person_alerts = total_person
        self._stats.total_coal_alerts = total_coal
        self._update_running_count()
        
        return self._stats
    
    def get_camera_stats(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thống kê của một camera"""
        monitor = self._monitors.get(camera_id)
        if monitor:
            return monitor.stats.to_dict()
        return None
    
    def get_all_camera_stats(self) -> Dict[str, Dict[str, Any]]:
        """Lấy thống kê tất cả cameras"""
        return {
            cam_id: monitor.stats.to_dict()
            for cam_id, monitor in self._monitors.items()
        }
    
    def add_camera(self, cam_config: CameraConfig) -> bool:
        """Thêm camera mới
        
        Args:
            cam_config: Cấu hình camera
            
        Returns:
            True nếu thêm thành công
        """
        with self._lock:
            if cam_config.camera_id in self._monitors:
                return False
            
            monitor = CameraMonitor(
                config=cam_config,
                model_loader=self._model_loader,
                logs_dir=self.config.logs_dir,
                artifacts_dir=self.config.artifacts_dir,
                on_frame=self.on_frame,
                on_detection=self.on_detection,
                on_alert=self._handle_camera_alert,
                on_state_change=self._handle_state_change,
            )
            
            self._monitors[cam_config.camera_id] = monitor
            self._stats.total_cameras = len(self._monitors)
            
            return True
    
    def remove_camera(self, camera_id: str) -> bool:
        """Xóa camera
        
        Args:
            camera_id: ID của camera
            
        Returns:
            True nếu xóa thành công
        """
        with self._lock:
            monitor = self._monitors.pop(camera_id, None)
            if monitor:
                monitor.stop()
                self._stats.total_cameras = len(self._monitors)
                return True
            return False
    
    def _global_alert(self, message: str) -> None:
        """Gửi cảnh báo toàn cục"""
        if self.on_global_alert:
            try:
                self.on_global_alert(message)
            except:
                pass
    
    @property
    def is_any_running(self) -> bool:
        """Có camera nào đang chạy không"""
        return any(m.is_running for m in self._monitors.values())
    
    @property
    def camera_ids(self) -> List[str]:
        """Danh sách ID các camera"""
        return list(self._monitors.keys())
    
    def update_config(self, new_config: SystemConfig) -> None:
        """Cập nhật cấu hình
        
        Lưu ý: Phải stop tất cả camera trước khi update
        """
        if self.is_any_running:
            raise RuntimeError("Phải dừng tất cả camera trước khi update config")
        
        self.config = new_config
        self._monitors.clear()
        self._init_monitors()

