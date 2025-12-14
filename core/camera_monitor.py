"""
Camera Monitor Module
=====================

Module giám sát cho một camera đơn lẻ.
Tích hợp: Video capture, Detection, PLC, Logging

Mỗi CameraMonitor instance quản lý:
- 1 VideoSource (RTSP/file)
- 1 PersonDetector
- 1 CoalDetector  
- 1 PLCClient + AlarmManager
- 1 AlertLogger + ImageSaver
"""

import threading
import time
import queue
from enum import Enum
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass

import re

from ..config import CameraConfig
from ..camera import VideoSource, VideoInfo, DualFrameBuffer
from ..detection import MultiModelLoader, PersonDetector, CoalDetector, ROIManager
from ..plc import PLCClient, AlarmManager, AlarmConfig, AlarmType, AlarmState
from ..alerting import AlertLogger, ImageSaver


class MonitoringState(Enum):
    """Trạng thái giám sát"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class MonitoringStats:
    """Thống kê giám sát"""
    frame_count: int = 0
    detection_count: int = 0
    person_alerts: int = 0
    coal_alerts: int = 0
    fps_capture: float = 0.0
    fps_detection: float = 0.0
    uptime_seconds: float = 0.0
    last_coal_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_count": self.frame_count,
            "detection_count": self.detection_count,
            "person_alerts": self.person_alerts,
            "coal_alerts": self.coal_alerts,
            "fps_capture": round(self.fps_capture, 1),
            "fps_detection": round(self.fps_detection, 1),
            "uptime_seconds": round(self.uptime_seconds, 0),
            "last_coal_ratio": round(self.last_coal_ratio, 1),
        }


class CameraMonitor:
    """
    Giám sát một camera đơn lẻ
    
    Tích hợp tất cả module:
    - Video capture (VideoSource)
    - Detection (PersonDetector, CoalDetector)
    - PLC communication (PLCClient, AlarmManager)
    - Logging (AlertLogger, ImageSaver)
    
    Usage:
        config = CameraConfig.from_dict({...})
        
        monitor = CameraMonitor(
            config=config,
            model_loader=ModelLoader.get_instance(),
            on_frame=lambda frame: display(frame),
            on_alert=lambda msg: log(msg)
        )
        
        monitor.start()
        ...
        monitor.stop()
    """
    
    def __init__(
        self,
        config: CameraConfig,
        model_loader: MultiModelLoader,
        logs_dir: str = "logs",
        artifacts_dir: str = "artifacts",
        on_frame: Optional[Callable[[Any, 'CameraMonitor'], None]] = None,
        on_detection: Optional[Callable[[Any, 'CameraMonitor'], None]] = None,
        on_alert: Optional[Callable[[str, 'CameraMonitor'], None]] = None,
        on_state_change: Optional[Callable[[MonitoringState, 'CameraMonitor'], None]] = None,
    ):
        """
        Args:
            config: Cấu hình camera
            model_loader: Multi-model loader (shared, supports different models per camera)
            logs_dir: Thư mục log
            artifacts_dir: Thư mục ảnh
            on_frame: Callback khi có frame mới
            on_detection: Callback khi có detection result
            on_alert: Callback khi có cảnh báo
            on_state_change: Callback khi trạng thái thay đổi
        """
        self.config = config
        self.model_loader = model_loader
        
        # Extract camera number from camera_id (e.g., "camera_1" -> 1)
        self._camera_number = self._extract_camera_number(config.camera_id)
        self.on_frame = on_frame
        self.on_detection = on_detection
        self.on_alert = on_alert
        self.on_state_change = on_state_change
        
        # Trạng thái
        self._state = MonitoringState.STOPPED
        self._stop_event = threading.Event()
        self._stats = MonitoringStats()
        self._start_time: Optional[float] = None
        
        # Components - sẽ được khởi tạo khi start()
        self._video_source: Optional[VideoSource] = None
        self._frame_buffer: Optional[DualFrameBuffer] = None
        self._person_detector: Optional[PersonDetector] = None
        self._coal_detector: Optional[CoalDetector] = None
        self._roi_manager: Optional[ROIManager] = None
        self._plc_client: Optional[PLCClient] = None
        self._alarm_manager: Optional[AlarmManager] = None
        self._alert_logger: Optional[AlertLogger] = None
        self._image_saver: Optional[ImageSaver] = None
        
        # Threads
        self._capture_thread: Optional[threading.Thread] = None
        self._detection_thread: Optional[threading.Thread] = None
        
        # Result queue
        self._result_queue: queue.Queue = queue.Queue(maxsize=1)
        
        # Lưu paths
        self._logs_dir = logs_dir
        self._artifacts_dir = artifacts_dir
        
        # Latest frame và result
        self._latest_frame: Optional[Any] = None
        self._latest_result: Optional[Any] = None
        
        # FPS tracking
        self._fps_frame_count = 0
        self._fps_detection_count = 0
        self._fps_last_time = 0.0
    
    @property
    def camera_id(self) -> str:
        """ID của camera"""
        return self.config.camera_id
    
    @property
    def camera_number(self) -> int:
        """Số thứ tự camera (1, 2, 3, ...)"""
        return self._camera_number
    
    def _extract_camera_number(self, camera_id: str) -> int:
        """Extract số từ camera_id (e.g., 'camera_1' -> 1)"""
        match = re.search(r'(\d+)', camera_id)
        if match:
            return int(match.group(1))
        return 1  # Default
    
    @property
    def state(self) -> MonitoringState:
        """Trạng thái hiện tại"""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Đang chạy không"""
        return self._state == MonitoringState.RUNNING
    
    @property
    def stats(self) -> MonitoringStats:
        """Thống kê"""
        if self._start_time:
            self._stats.uptime_seconds = time.time() - self._start_time
        return self._stats
    
    @property
    def latest_frame(self) -> Optional[Any]:
        """Frame mới nhất"""
        return self._latest_frame
    
    @property
    def video_info(self) -> Optional[VideoInfo]:
        """Thông tin video"""
        if self._video_source:
            return self._video_source.video_info
        return None
    
    def start(self) -> bool:
        """Bắt đầu giám sát
        
        Returns:
            True nếu khởi động thành công
        """
        if self._state == MonitoringState.RUNNING:
            return True
        
        self._set_state(MonitoringState.STARTING)
        self._add_alert(f"🔄 Đang khởi động camera: {self.config.name}")
        
        try:
            # Khởi tạo components
            self._init_components()
            
            # Kết nối PLC
            if self.config.plc.enabled:
                self._connect_plc()
            
            # Bắt đầu video source
            if not self._video_source.start():
                raise Exception("Không thể mở nguồn video")
            
            # Bắt đầu threads
            self._stop_event.clear()
            self._start_time = time.time()
            self._fps_last_time = time.time()
            
            self._capture_thread = threading.Thread(
                target=self._capture_loop, 
                daemon=True,
                name=f"Capture-{self.camera_id}"
            )
            self._detection_thread = threading.Thread(
                target=self._detection_loop, 
                daemon=True,
                name=f"Detection-{self.camera_id}"
            )
            
            self._capture_thread.start()
            self._detection_thread.start()
            
            self._set_state(MonitoringState.RUNNING)
            self._add_alert(f"✅ Camera {self.config.name} đã khởi động")
            
            return True
            
        except Exception as e:
            self._set_state(MonitoringState.ERROR)
            self._add_alert(f"❌ Lỗi khởi động camera {self.config.name}: {str(e)}")
            self._cleanup()
            return False
    
    def stop(self) -> None:
        """Dừng giám sát"""
        if self._state == MonitoringState.STOPPED:
            return
        
        self._set_state(MonitoringState.STOPPING)
        self._add_alert(f"⏹️ Đang dừng camera: {self.config.name}")
        
        # Tắt báo động trước
        if self._alarm_manager:
            self._alarm_manager.turn_off_all()
        
        # Dừng threads
        self._stop_event.set()
        
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        
        if self._detection_thread and self._detection_thread.is_alive():
            self._detection_thread.join(timeout=2.0)
        
        # Cleanup
        self._cleanup()
        
        self._set_state(MonitoringState.STOPPED)
        self._add_alert(f"⏹️ Camera {self.config.name} đã dừng")
    
    def _init_components(self) -> None:
        """Khởi tạo các component"""
        cfg = self.config
        
        # ROI Manager
        self._roi_manager = ROIManager(config_path=None, auto_create=False)
        self._roi_manager._roi_data.roi_person = list(cfg.roi.roi_person)
        self._roi_manager._roi_data.roi_coal = list(cfg.roi.roi_coal)
        self._roi_manager._roi_data.reference_resolution = cfg.roi.reference_resolution
        
        # Video Source
        video_path = cfg.get_video_source()
        self._video_source = VideoSource(
            source_path=video_path,
            target_fps=cfg.target_fps,
            on_frame_callback=self._on_video_frame,
            on_error_callback=self._on_video_error,
        )
        
        # Frame Buffer
        self._frame_buffer = DualFrameBuffer(
            display_maxsize=1,
            detection_maxsize=2
        )
        
        # Person Detector
        # Lấy model info cho camera này (hỗ trợ multi-model)
        model_info = self.model_loader.get_model_info_for_camera(self._camera_number)
        person_class_id = model_info.person_class_id if model_info else 0
        
        self._person_detector = PersonDetector(
            roi_points=list(cfg.roi.roi_person),
            person_class_id=person_class_id,
            consecutive_threshold=cfg.detection.person_consecutive_threshold,
            no_detection_threshold=cfg.detection.person_no_detection_threshold,
        )
        
        # Coal Detector
        coal_class_id = model_info.coal_class_id if model_info else 1
        
        self._coal_detector = CoalDetector(
            roi_points=list(cfg.roi.roi_coal),
            coal_class_id=coal_class_id,
            ratio_threshold=cfg.detection.coal_ratio_threshold,
            consecutive_threshold=cfg.detection.coal_consecutive_threshold,
            no_blockage_threshold=cfg.detection.coal_no_blockage_threshold,
            enabled=cfg.detection.coal_detection_enabled,
        )
        
        # Log model info
        if model_info:
            self._add_alert(f"📋 Camera {self._camera_number} sử dụng model: {model_info.name}")
        
        # Alert Logger
        self._alert_logger = AlertLogger(
            logs_dir=self._logs_dir,
            camera_id=cfg.camera_id,
            camera_ip=cfg.rtsp_url.split('@')[1].split(':')[0] if '@' in cfg.rtsp_url else "",
        )
        
        # Image Saver
        self._image_saver = ImageSaver(
            artifacts_dir=self._artifacts_dir,
            camera_id=cfg.camera_id,
        )
    
    def _connect_plc(self) -> None:
        """Kết nối PLC"""
        plc_cfg = self.config.plc
        
        self._plc_client = PLCClient(
            ip=plc_cfg.ip,
            rack=plc_cfg.rack,
            slot=plc_cfg.slot,
            max_reconnect_attempts=plc_cfg.reconnect_attempts,
            health_check_interval=plc_cfg.health_check_interval,
            on_state_change=self._on_plc_state_change,
            on_error=lambda msg: self._add_alert(f"❌ PLC: {msg}"),
        )
        
        if self._plc_client.connect():
            self._add_alert(f"✅ Đã kết nối PLC: {plc_cfg.ip}")
        else:
            self._add_alert(f"⚠️ Không thể kết nối PLC: {plc_cfg.ip}")
        
        # Alarm Manager
        self._alarm_manager = AlarmManager(
            plc_client=self._plc_client,
            person_alarm=AlarmConfig(
                db_number=plc_cfg.db_number,
                byte_offset=plc_cfg.person_alarm_byte,
                bit_offset=plc_cfg.person_alarm_bit,
            ),
            coal_alarm=AlarmConfig(
                db_number=plc_cfg.db_number,
                byte_offset=plc_cfg.coal_alarm_byte,
                bit_offset=plc_cfg.coal_alarm_bit,
            ),
            on_alarm_change=self._on_alarm_change,
            on_error=lambda msg: self._add_alert(f"❌ Alarm: {msg}"),
        )
    
    def _cleanup(self) -> None:
        """Giải phóng tài nguyên"""
        if self._video_source:
            self._video_source.stop()
            self._video_source = None
        
        if self._plc_client:
            self._plc_client.disconnect()
            self._plc_client = None
        
        self._frame_buffer = None
        self._person_detector = None
        self._coal_detector = None
    
    def _capture_loop(self) -> None:
        """Vòng lặp capture frame (chạy trong thread riêng)"""
        # VideoSource đã xử lý capture trong callback
        # Loop này chỉ để giữ thread alive và theo dõi
        while not self._stop_event.is_set():
            time.sleep(0.1)
    
    def _on_video_frame(self, frame: Any, timestamp: float) -> None:
        """Callback khi có frame mới từ VideoSource"""
        self._latest_frame = frame.copy()
        self._stats.frame_count += 1
        self._fps_frame_count += 1
        
        # Đưa vào buffer
        if self._frame_buffer:
            self._frame_buffer.put(frame, timestamp)
        
        # Callback
        if self.on_frame:
            try:
                self.on_frame(frame, self)
            except:
                pass
    
    def _on_video_error(self, message: str) -> None:
        """Callback khi có lỗi video"""
        self._add_alert(f"⚠️ Video: {message}")
    
    def _detection_loop(self) -> None:
        """Vòng lặp detection (chạy trong thread riêng)"""
        detection_interval = 0.5  # 2 FPS detection
        
        while not self._stop_event.is_set():
            loop_start = time.time()
            
            # Lấy frame từ buffer
            if self._frame_buffer:
                frame_data = self._frame_buffer.get_for_detection()
                
                if frame_data and frame_data.frame is not None:
                    self._process_frame(frame_data.frame)
            
            # FPS tracking
            current_time = time.time()
            if current_time - self._fps_last_time >= 2.0:
                elapsed = current_time - self._fps_last_time
                self._stats.fps_capture = self._fps_frame_count / elapsed
                self._stats.fps_detection = self._fps_detection_count / elapsed
                self._fps_frame_count = 0
                self._fps_detection_count = 0
                self._fps_last_time = current_time
            
            # Rate limiting
            elapsed = time.time() - loop_start
            sleep_time = max(0, detection_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _process_frame(self, frame: Any) -> None:
        """Xử lý detection trên frame"""
        try:
            # YOLO inference (sử dụng model tương ứng với camera number)
            yolo_result = self.model_loader.predict(
                camera_number=self._camera_number,
                frame=frame,
                conf=self.config.detection.confidence_threshold,
            )
            
            self._stats.detection_count += 1
            self._fps_detection_count += 1
            
            # Person detection
            person_result = self._person_detector.detect(frame, yolo_result)
            
            # Coal detection
            coal_result = self._coal_detector.detect(frame, yolo_result)
            self._stats.last_coal_ratio = coal_result.coal_ratio
            
            # Xử lý alarm
            self._handle_person_alarm(person_result, frame)
            self._handle_coal_alarm(coal_result, frame)
            
            # Lưu result
            self._latest_result = {
                "yolo_result": yolo_result,
                "person_result": person_result,
                "coal_result": coal_result,
            }
            
            # Callback
            if self.on_detection:
                try:
                    self.on_detection(self._latest_result, self)
                except:
                    pass
                    
        except Exception as e:
            self._add_alert(f"❌ Lỗi detection: {str(e)}")
    
    def _handle_person_alarm(self, result, frame) -> None:
        """Xử lý cảnh báo người"""
        if result.should_alarm:
            self._stats.person_alerts += 1
            
            # Gửi PLC
            if self._alarm_manager:
                self._alarm_manager.turn_on_person_alarm()
            
            # Log
            self._alert_logger.log_person_alert(
                frames_detected=result.consecutive_count,
                threshold=self.config.detection.person_consecutive_threshold,
            )
            
            # Lưu ảnh
            self._image_saver.save_person_alert(
                frame=frame,
                roi_person=self._roi_manager.get_roi_person(),
                consecutive_count=result.consecutive_count,
            )
            
            self._add_alert(f"🚨 CẢNH BÁO: Phát hiện người trong vùng nguy hiểm")
        
        # Tắt alarm nếu cần
        elif self._person_detector.should_turn_off_alarm():
            if self._alarm_manager and self._alarm_manager.person_alarm_state == AlarmState.ON:
                self._alarm_manager.turn_off_person_alarm()
    
    def _handle_coal_alarm(self, result, frame) -> None:
        """Xử lý cảnh báo tắc than"""
        if result.should_alarm:
            self._stats.coal_alerts += 1
            
            # Gửi PLC
            if self._alarm_manager:
                self._alarm_manager.turn_on_coal_alarm()
            
            # Log
            self._alert_logger.log_coal_alert(
                coal_ratio=result.coal_ratio,
                threshold=self.config.detection.coal_ratio_threshold,
            )
            
            # Lưu ảnh
            self._image_saver.save_coal_alert(
                frame=frame,
                roi_coal=self._roi_manager.get_roi_coal(),
                coal_ratio=result.coal_ratio,
                threshold=self.config.detection.coal_ratio_threshold,
            )
            
            self._add_alert(f"🚨 CẢNH BÁO: Tắc than! Tỷ lệ: {result.coal_ratio:.1f}%")
        
        # Tắt alarm nếu cần
        elif self._coal_detector.should_turn_off_alarm():
            if self._alarm_manager and self._alarm_manager.coal_alarm_state == AlarmState.ON:
                self._alarm_manager.turn_off_coal_alarm()
    
    def _on_plc_state_change(self, state) -> None:
        """Callback khi trạng thái PLC thay đổi"""
        self._add_alert(f"🔌 PLC: {state.value}")
    
    def _on_alarm_change(self, alarm_type: AlarmType, state: AlarmState) -> None:
        """Callback khi trạng thái alarm thay đổi"""
        status = "BẬT" if state == AlarmState.ON else "TẮT"
        alarm_name = "Người" if alarm_type == AlarmType.PERSON else "Tắc than"
        self._add_alert(f"🔔 Báo động {alarm_name}: {status}")
    
    def _set_state(self, new_state: MonitoringState) -> None:
        """Cập nhật trạng thái"""
        if self._state != new_state:
            self._state = new_state
            if self.on_state_change:
                try:
                    self.on_state_change(new_state, self)
                except:
                    pass
    
    def _add_alert(self, message: str) -> None:
        """Thêm cảnh báo"""
        if self.on_alert:
            try:
                self.on_alert(message, self)
            except:
                pass
    
    def get_alarm_states(self) -> Dict[str, str]:
        """Lấy trạng thái các alarm"""
        if self._alarm_manager:
            return {
                "person": self._alarm_manager.person_alarm_state.name,
                "coal": self._alarm_manager.coal_alarm_state.name,
            }
        return {"person": "OFF", "coal": "OFF"}
    
    def get_plc_connected(self) -> bool:
        """Kiểm tra PLC có kết nối không"""
        if self._plc_client:
            return self._plc_client.is_connected
        return False

