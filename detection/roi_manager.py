"""
ROI Manager Module
==================

Quản lý ROI (Region of Interest) với khả năng:
- Load ROI từ file JSON
- Auto-reload khi file thay đổi
- Scale ROI theo độ phân giải video
"""

import os
import json
import threading
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ROIData:
    """Container cho ROI data"""
    reference_resolution: Tuple[int, int]
    roi_person: List[Tuple[int, int]]
    roi_coal: List[Tuple[int, int]]


class ROIManager:
    """
    Quản lý ROI configuration
    
    Features:
    - Load từ JSON file
    - Auto-reload khi file thay đổi
    - Scale ROI theo độ phân giải
    - Thread-safe
    
    Usage:
        manager = ROIManager("roi_config.json")
        
        # Lấy ROI đã scale
        roi_person = manager.get_scaled_roi_person(1280, 720)
        roi_coal = manager.get_scaled_roi_coal(1280, 720)
        
        # Kiểm tra thay đổi (trong loop)
        if manager.check_and_reload():
            # ROI đã được cập nhật
            update_detectors()
    """
    
    # Default ROI values
    DEFAULT_REFERENCE_RESOLUTION = (1920, 1080)
    DEFAULT_ROI_PERSON = [
        (393, 333), (541, 333), (553, 292), (628, 292),
        (660, 35), (777, 35), (857, 330), (899, 330),
        (939, 650), (299, 642)
    ]
    DEFAULT_ROI_COAL = [
        (547, 629), (567, 451), (892, 460), (923, 637)
    ]
    
    def __init__(self, config_path: Optional[str] = None, auto_create: bool = True):
        """
        Args:
            config_path: Đường dẫn file JSON (None = chỉ dùng default)
            auto_create: Tự động tạo file config nếu chưa có
        """
        self.config_path = config_path
        self._lock = threading.Lock()
        self._file_mtime: float = 0
        
        # ROI data
        self._roi_data = ROIData(
            reference_resolution=self.DEFAULT_REFERENCE_RESOLUTION,
            roi_person=list(self.DEFAULT_ROI_PERSON),
            roi_coal=list(self.DEFAULT_ROI_COAL),
        )
        
        # Load từ file nếu có
        if config_path:
            self._load_from_file(auto_create)
    
    def _load_from_file(self, auto_create: bool = True) -> bool:
        """Load ROI từ file JSON
        
        Returns:
            True nếu load thành công
        """
        if not self.config_path:
            return False
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                with self._lock:
                    self._parse_config(data)
                    self._file_mtime = os.path.getmtime(self.config_path)
                
                return True
            elif auto_create:
                # Tạo file mặc định
                self._create_default_config()
                return True
            
        except Exception as e:
            print(f"Lỗi load ROI config: {e}")
        
        return False
    
    def _parse_config(self, data: Dict[str, Any]) -> None:
        """Parse config data"""
        if 'reference_resolution' in data:
            self._roi_data.reference_resolution = tuple(data['reference_resolution'])
        
        if 'roi_person' in data:
            self._roi_data.roi_person = [tuple(p) for p in data['roi_person']]
        
        if 'roi_coal' in data:
            self._roi_data.roi_coal = [tuple(p) for p in data['roi_coal']]
    
    def _create_default_config(self) -> None:
        """Tạo file config mặc định"""
        if not self.config_path:
            return
        
        try:
            config = {
                "reference_resolution": list(self.DEFAULT_REFERENCE_RESOLUTION),
                "roi_person": [list(p) for p in self.DEFAULT_ROI_PERSON],
                "roi_coal": [list(p) for p in self.DEFAULT_ROI_COAL],
            }
            
            # Tạo thư mục nếu cần
            os.makedirs(os.path.dirname(self.config_path) or '.', exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            self._file_mtime = os.path.getmtime(self.config_path)
            
        except Exception as e:
            print(f"Lỗi tạo ROI config: {e}")
    
    def check_and_reload(self) -> bool:
        """Kiểm tra và reload nếu file thay đổi
        
        Returns:
            True nếu đã reload
        """
        if not self.config_path or not os.path.exists(self.config_path):
            return False
        
        try:
            current_mtime = os.path.getmtime(self.config_path)
            
            if current_mtime != self._file_mtime:
                self._load_from_file(auto_create=False)
                return True
                
        except Exception:
            pass
        
        return False
    
    def scale_roi(self, roi_points: List[Tuple[int, int]], 
                  target_width: int, target_height: int) -> List[Tuple[int, int]]:
        """Scale ROI từ độ phân giải gốc sang mục tiêu
        
        Args:
            roi_points: Danh sách điểm ROI
            target_width: Chiều rộng mục tiêu
            target_height: Chiều cao mục tiêu
            
        Returns:
            Danh sách điểm ROI đã scale
        """
        with self._lock:
            ref_w, ref_h = self._roi_data.reference_resolution
        
        scale_x = target_width / ref_w
        scale_y = target_height / ref_h
        
        return [(int(x * scale_x), int(y * scale_y)) for (x, y) in roi_points]
    
    def get_roi_person(self) -> List[Tuple[int, int]]:
        """Lấy ROI người (chưa scale)"""
        with self._lock:
            return list(self._roi_data.roi_person)
    
    def get_roi_coal(self) -> List[Tuple[int, int]]:
        """Lấy ROI than (chưa scale)"""
        with self._lock:
            return list(self._roi_data.roi_coal)
    
    def get_scaled_roi_person(self, width: int, height: int) -> List[Tuple[int, int]]:
        """Lấy ROI người đã scale"""
        return self.scale_roi(self.get_roi_person(), width, height)
    
    def get_scaled_roi_coal(self, width: int, height: int) -> List[Tuple[int, int]]:
        """Lấy ROI than đã scale"""
        return self.scale_roi(self.get_roi_coal(), width, height)
    
    def get_reference_resolution(self) -> Tuple[int, int]:
        """Lấy độ phân giải tham chiếu"""
        with self._lock:
            return self._roi_data.reference_resolution
    
    def update_roi_person(self, roi_points: List[Tuple[int, int]], 
                          save: bool = True) -> None:
        """Cập nhật ROI người
        
        Args:
            roi_points: Danh sách điểm ROI mới
            save: Lưu vào file không
        """
        with self._lock:
            self._roi_data.roi_person = list(roi_points)
        
        if save and self.config_path:
            self._save_to_file()
    
    def update_roi_coal(self, roi_points: List[Tuple[int, int]], 
                        save: bool = True) -> None:
        """Cập nhật ROI than"""
        with self._lock:
            self._roi_data.roi_coal = list(roi_points)
        
        if save and self.config_path:
            self._save_to_file()
    
    def _save_to_file(self) -> bool:
        """Lưu config ra file"""
        if not self.config_path:
            return False
        
        try:
            with self._lock:
                config = {
                    "reference_resolution": list(self._roi_data.reference_resolution),
                    "roi_person": [list(p) for p in self._roi_data.roi_person],
                    "roi_coal": [list(p) for p in self._roi_data.roi_coal],
                }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            self._file_mtime = os.path.getmtime(self.config_path)
            return True
            
        except Exception as e:
            print(f"Lỗi lưu ROI config: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        with self._lock:
            return {
                "reference_resolution": list(self._roi_data.reference_resolution),
                "roi_person": [list(p) for p in self._roi_data.roi_person],
                "roi_coal": [list(p) for p in self._roi_data.roi_coal],
            }

