"""
Inference Statistics Module
===========================

Module theo dõi và thống kê hiệu năng inference YOLO.
Dựa trên coal_6cam_v1.py và các best practices từ GitHub repos.

Features:
- Track inference time per camera
- Calculate avg/min/max/fps
- GPU memory monitoring
- Export to dict/JSON
"""

import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class CameraInferenceStats:
    """Thống kê inference cho một camera"""
    camera_id: int
    model_id: str = "default"
    
    # Timing stats
    last_inference_ms: float = 0.0
    avg_inference_ms: float = 0.0
    min_inference_ms: float = float('inf')
    max_inference_ms: float = 0.0
    
    # Counters
    total_inferences: int = 0
    
    # Internal tracking
    _inference_times: List[float] = field(default_factory=list, repr=False)
    _max_samples: int = field(default=100, repr=False)
    
    def update(self, inference_time_ms: float) -> None:
        """Cập nhật với inference time mới"""
        self.last_inference_ms = inference_time_ms
        self.total_inferences += 1
        
        # Track times
        self._inference_times.append(inference_time_ms)
        if len(self._inference_times) > self._max_samples:
            self._inference_times.pop(0)
        
        # Calculate stats
        if self._inference_times:
            self.avg_inference_ms = sum(self._inference_times) / len(self._inference_times)
            self.min_inference_ms = min(self._inference_times)
            self.max_inference_ms = max(self._inference_times)
    
    @property
    def inference_fps(self) -> float:
        """FPS inference (dựa trên avg time)"""
        if self.avg_inference_ms > 0:
            return 1000.0 / self.avg_inference_ms
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Export to dict"""
        return {
            "camera_id": self.camera_id,
            "model_id": self.model_id,
            "last_ms": round(self.last_inference_ms, 2),
            "avg_ms": round(self.avg_inference_ms, 2),
            "min_ms": round(self.min_inference_ms, 2) if self.min_inference_ms != float('inf') else 0,
            "max_ms": round(self.max_inference_ms, 2),
            "total_inferences": self.total_inferences,
            "inference_fps": round(self.inference_fps, 1),
        }


class InferenceStatsManager:
    """
    Manager cho tất cả inference stats
    
    Features:
    - Thread-safe
    - Track stats cho nhiều cameras
    - GPU memory monitoring
    - Summary statistics
    
    Usage:
        manager = InferenceStatsManager()
        
        # Trong detection loop:
        start = time.time()
        result = model.predict(frame)
        elapsed_ms = (time.time() - start) * 1000
        manager.record_inference(camera_id=1, inference_time_ms=elapsed_ms)
        
        # Xem stats:
        stats = manager.get_all_stats()
        summary = manager.get_summary()
    """
    
    def __init__(self):
        self._camera_stats: Dict[int, CameraInferenceStats] = {}
        self._lock = threading.Lock()
        
        # System info cache
        self._gpu_available: Optional[bool] = None
        self._gpu_name: Optional[str] = None
    
    def record_inference(
        self, 
        camera_id: int, 
        inference_time_ms: float,
        model_id: str = "default"
    ) -> None:
        """Ghi lại một inference
        
        Args:
            camera_id: ID camera
            inference_time_ms: Thời gian inference (milliseconds)
            model_id: ID model đã sử dụng
        """
        with self._lock:
            if camera_id not in self._camera_stats:
                self._camera_stats[camera_id] = CameraInferenceStats(
                    camera_id=camera_id,
                    model_id=model_id
                )
            
            self._camera_stats[camera_id].model_id = model_id
            self._camera_stats[camera_id].update(inference_time_ms)
    
    def get_camera_stats(self, camera_id: int) -> Optional[CameraInferenceStats]:
        """Lấy stats cho camera cụ thể"""
        with self._lock:
            return self._camera_stats.get(camera_id)
    
    def get_all_stats(self) -> Dict[int, Dict[str, Any]]:
        """Lấy stats cho tất cả cameras"""
        with self._lock:
            return {
                cam_id: stats.to_dict()
                for cam_id, stats in self._camera_stats.items()
            }
    
    def get_summary(self) -> Dict[str, Any]:
        """Lấy summary statistics"""
        with self._lock:
            if not self._camera_stats:
                return {
                    "active_cameras": 0,
                    "total_inferences": 0,
                    "avg_inference_ms": 0,
                    "total_throughput_fps": 0,
                }
            
            active = len(self._camera_stats)
            total_inferences = sum(s.total_inferences for s in self._camera_stats.values())
            avg_times = [s.avg_inference_ms for s in self._camera_stats.values() if s.avg_inference_ms > 0]
            
            return {
                "active_cameras": active,
                "total_inferences": total_inferences,
                "avg_inference_ms": round(sum(avg_times) / len(avg_times), 2) if avg_times else 0,
                "total_throughput_fps": round(sum(s.inference_fps for s in self._camera_stats.values()), 1),
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Lấy thông tin hệ thống (GPU, CPU, RAM)"""
        info = {
            "gpu_available": False,
            "gpu_name": "N/A",
            "gpu_memory_used_mb": 0,
            "gpu_memory_total_mb": 0,
            "cpu_percent": 0,
            "ram_percent": 0,
            "ram_used_gb": 0,
            "ram_total_gb": 0,
        }
        
        # GPU info
        try:
            import torch
            info["gpu_available"] = torch.cuda.is_available()
            if info["gpu_available"]:
                info["gpu_name"] = torch.cuda.get_device_name(0)
                info["gpu_memory_used_mb"] = round(torch.cuda.memory_allocated() / 1024**2, 1)
                info["gpu_memory_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**2, 1)
        except ImportError:
            pass
        
        # CPU/RAM info
        try:
            import psutil
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            info["ram_percent"] = ram.percent
            info["ram_used_gb"] = round(ram.used / 1024**3, 1)
            info["ram_total_gb"] = round(ram.total / 1024**3, 1)
        except ImportError:
            pass
        
        return info
    
    def print_stats(self, include_system: bool = True) -> None:
        """In statistics ra console"""
        print("\n" + "=" * 70)
        print("📊 INFERENCE STATISTICS")
        print("=" * 70)
        
        all_stats = self.get_all_stats()
        
        if not all_stats:
            print("  No inference data yet.")
        else:
            for cam_id, stats in sorted(all_stats.items()):
                print(f"\n📹 Camera {cam_id} (Model: {stats['model_id']}):")
                print(f"   • Last inference:    {stats['last_ms']:.1f} ms")
                print(f"   • Average:           {stats['avg_ms']:.1f} ms")
                print(f"   • Min/Max:           {stats['min_ms']:.1f} / {stats['max_ms']:.1f} ms")
                print(f"   • Total inferences:  {stats['total_inferences']}")
                print(f"   • Inference FPS:     {stats['inference_fps']:.1f}")
            
            # Summary
            summary = self.get_summary()
            print(f"\n📈 SUMMARY ({summary['active_cameras']} cameras):")
            print(f"   • Avg inference:     {summary['avg_inference_ms']:.1f} ms")
            print(f"   • Total throughput:  {summary['total_throughput_fps']:.1f} FPS")
            print(f"   • Total inferences:  {summary['total_inferences']}")
        
        # System info
        if include_system:
            sys_info = self.get_system_info()
            print(f"\n🔧 SYSTEM:")
            print(f"   • GPU: {'✅ ' + sys_info['gpu_name'] if sys_info['gpu_available'] else '❌ CPU only'}")
            if sys_info['gpu_available']:
                print(f"   • GPU Memory: {sys_info['gpu_memory_used_mb']:.0f} / {sys_info['gpu_memory_total_mb']:.0f} MB")
            print(f"   • CPU Usage: {sys_info['cpu_percent']:.1f}%")
            print(f"   • RAM Usage: {sys_info['ram_percent']:.1f}% ({sys_info['ram_used_gb']:.1f} / {sys_info['ram_total_gb']:.1f} GB)")
        
        print("=" * 70)
        
        # Performance evaluation
        if all_stats:
            avg_ms = self.get_summary()['avg_inference_ms']
            print("\n💡 PERFORMANCE EVALUATION:")
            if avg_ms < 100:
                print("   ✅ EXCELLENT - GPU đang hoạt động hiệu quả")
            elif avg_ms < 200:
                print("   🟡 GOOD - Hiệu năng ổn định")
            elif avg_ms < 500:
                print("   🟠 MODERATE - Có thể đang dùng CPU hoặc GPU yếu")
            else:
                print("   🔴 SLOW - Cần tối ưu hoặc nâng cấp phần cứng")
        
        print()
    
    def reset(self, camera_id: int = None) -> None:
        """Reset statistics
        
        Args:
            camera_id: ID camera cần reset (None = reset tất cả)
        """
        with self._lock:
            if camera_id is not None:
                if camera_id in self._camera_stats:
                    del self._camera_stats[camera_id]
            else:
                self._camera_stats.clear()


# Global singleton instance
_stats_manager: Optional[InferenceStatsManager] = None
_stats_lock = threading.Lock()


def get_stats_manager() -> InferenceStatsManager:
    """Lấy global stats manager instance"""
    global _stats_manager
    
    if _stats_manager is None:
        with _stats_lock:
            if _stats_manager is None:
                _stats_manager = InferenceStatsManager()
    
    return _stats_manager

