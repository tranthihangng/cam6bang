# Coal Mine Monitoring System - Multi-Camera Architecture

Hệ thống giám sát mỏ than đa camera với kiến trúc module hóa.

## 📁 Cấu trúc thư mục

```
coal_monitoring/
├── __init__.py              # Package exports
├── main.py                  # Entry point
├── README.md               
│
├── config/                  # ⚙️ Configuration Module
│   ├── __init__.py
│   ├── system_config.py     # SystemConfig, load/save config
│   ├── camera_config.py     # CameraConfig, PLCConfig, ROIConfig
│   └── sample_6cam_config.json  # Cấu hình mẫu 6 camera
│
├── camera/                  # 📹 Camera/Video Module
│   ├── __init__.py
│   ├── video_source.py      # VideoSource - RTSP/file handling
│   └── frame_buffer.py      # FrameBuffer - thread-safe queue
│
├── detection/               # 🔍 Detection Module
│   ├── __init__.py
│   ├── model_loader.py      # ModelLoader - YOLO singleton
│   ├── base_detector.py     # BaseDetector interface
│   ├── person_detector.py   # PersonDetector
│   ├── coal_detector.py     # CoalDetector
│   └── roi_manager.py       # ROIManager
│
├── plc/                     # 🔌 PLC Communication Module
│   ├── __init__.py
│   ├── plc_client.py        # PLCClient - Snap7 wrapper
│   └── alarm_manager.py     # AlarmManager - alarm state management
│
├── alerting/                # 📝 Alerting Module (renamed from logging)
│   ├── __init__.py
│   ├── alert_logger.py      # AlertLogger - JSON logging
│   └── image_saver.py       # ImageSaver - save alert images
│
├── ui/                      # 🖥️ UI Module
│   ├── __init__.py
│   └── main_window.py       # MainWindow - Tkinter GUI
│
└── core/                    # 🎯 Core/Orchestration Module
    ├── __init__.py
    ├── camera_monitor.py    # CameraMonitor - single camera
    └── multi_camera_app.py  # MultiCameraApp - multiple cameras
```

## 🎯 Module Architecture

### 1. Config Module (`config/`)
- **SystemConfig**: Cấu hình toàn hệ thống
- **CameraConfig**: Cấu hình từng camera (RTSP, PLC, ROI, Detection)
- Load/Save từ JSON file

### 2. Camera Module (`camera/`)
- **VideoSource**: Quản lý nguồn video (RTSP/file) với auto-reconnect
- **FrameBuffer**: Thread-safe frame queue

### 3. Detection Module (`detection/`)
- **MultiModelLoader**: Quản lý nhiều YOLO models (camera nào dùng model nào)
- **PersonDetector**: Phát hiện người trong ROI với consecutive frame logic
- **CoalDetector**: Phát hiện tắc than với ratio threshold
- **ROIManager**: Quản lý và scale ROI

### 4. PLC Module (`plc/`)
- **PLCClient**: Snap7 wrapper với auto-reconnect
- **AlarmManager**: Quản lý trạng thái ON/OFF báo động

### 5. Alerting Module (`alerting/`)
- **AlertLogger**: Ghi log cảnh báo ra JSON
- **ImageSaver**: Lưu ảnh cảnh báo với ROI

### 6. Core Module (`core/`)
- **CameraMonitor**: Giám sát một camera đơn lẻ
- **MultiCameraApp**: Quản lý nhiều cameras

### 7. UI Module (`ui/`)
- **MainWindow**: Giao diện Tkinter đa camera

## 🚀 Sử dụng

### 1. Tạo file config
```bash
python main.py --create-config 6
```

### 2. Chỉnh sửa config
Mở file `system_config.json` và cập nhật:
- RTSP URLs cho từng camera
- PLC IPs và addresses
- ROI points
- Detection thresholds

### 3. Chạy ứng dụng

**Với GUI:**
```bash
python main.py --config system_config.json
```

**Không có GUI (headless):**
```bash
python main.py --config system_config.json --headless
```

## 📋 Config Format

```json
{
    "models": {
        "model_1": {
            "path": "best_segment_26_11.pt",
            "name": "Model Than & Nguoi",
            "cameras": [1, 2, 3, 4, 5]
        },
        "model_2": {
            "path": "best_segment_27_11_copy.pt",
            "name": "Model Khac",
            "cameras": [6]
        }
    },
    "cameras": [
        {
            "camera_id": "camera_1",
            "name": "Camera 1",
            "rtsp_url": "rtsp://admin:password@192.168.0.179:554/...",
            "plc": {
                "ip": "192.168.0.4",
                "db_number": 300,
                "person_alarm_byte": 6,
                "person_alarm_bit": 0,
                "coal_alarm_byte": 6,
                "coal_alarm_bit": 1
            },
            "roi": {
                "reference_resolution": [1920, 1080],
                "roi_person": [[x1, y1], [x2, y2], ...],
                "roi_coal": [[x1, y1], [x2, y2], ...]
            },
            "detection": {
                "confidence_threshold": 0.7,
                "person_consecutive_threshold": 3,
                "coal_ratio_threshold": 73.0
            }
        }
    ]
}
```

### Multi-Model Support 🆕

Hệ thống hỗ trợ nhiều model YOLO, mỗi camera có thể dùng model khác nhau:

```json
"models": {
    "model_1": {
        "path": "best_segment_26_11.pt",    
        "name": "Model Than & Nguoi",       
        "cameras": [1, 2, 3, 4, 5]          
    },
    "model_2": {
        "path": "best_segment_special.pt",
        "name": "Model Dac Biet",
        "cameras": [6]
    }
}
```

- `path`: Đường dẫn file model (.pt)
- `name`: Tên hiển thị
- `cameras`: Danh sách số camera sử dụng model này (1, 2, 3, ...)

## 🔧 Tái sử dụng Module

### Sử dụng từng module độc lập:

```python
# Config
from coal_monitoring.config import CameraConfig, load_config

# Camera
from coal_monitoring.camera import VideoSource

# Detection
from coal_monitoring.detection import ModelLoader, PersonDetector

# PLC
from coal_monitoring.plc import PLCClient, AlarmManager

# Core
from coal_monitoring.core import CameraMonitor, MultiCameraApp
```

### Ví dụ sử dụng PersonDetector độc lập:

```python
from coal_monitoring.detection import MultiModelLoader, PersonDetector

# Load model (multi-model support)
loader = MultiModelLoader.get_instance()
loader.load(
    model_id="model_1",
    model_path="best_segment.pt",
    model_name="Main Model",
    cameras=[1, 2, 3]  # Cameras 1, 2, 3 dùng model này
)

# Create detector
detector = PersonDetector(
    roi_points=[(100, 100), (500, 100), (500, 400), (100, 400)],
    person_class_id=0,
    consecutive_threshold=3
)

# Detect (specify camera_number để dùng đúng model)
result = loader.predict(camera_number=1, frame=frame)
detection = detector.detect(frame, result)

if detection.should_alarm:
    print("ALARM!")
```

### Ví dụ load nhiều models:

```python
from coal_monitoring.config import load_config
from coal_monitoring.detection import MultiModelLoader

# Load config
config = load_config("system_config.json")

# Load tất cả models từ config
loader = MultiModelLoader.get_instance()
results = loader.load_from_config(config)
# results = {"model_1": True, "model_2": True}

# Inference cho camera cụ thể (tự động dùng đúng model)
result_cam1 = loader.predict(camera_number=1, frame=frame1)  # Dùng model_1
result_cam6 = loader.predict(camera_number=6, frame=frame6)  # Dùng model_2
```

## 📦 Dependencies

```
ultralytics>=8.0.0
opencv-python>=4.8.0
python-snap7>=1.3
pillow>=10.0.0
numpy>=1.24.0
```

## 🎯 Multi-Camera Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       MultiCameraApp                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ ┌──────────┐ │
│  │CameraMonitor│  │CameraMonitor│  │CameraMonitor│ │CameraM...│ │
│  │  Camera 1   │  │  Camera 2   │  │  Camera 5   │ │Camera 6  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ └────┬─────┘ │
│         │                │                │             │       │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐ ┌────┴─────┐ │
│  │ VideoSource │  │ VideoSource │  │ VideoSource │ │VideoSrc  │ │
│  │ Detectors   │  │ Detectors   │  │ Detectors   │ │Detectors │ │
│  │ PLCClient   │  │ PLCClient   │  │ PLCClient   │ │PLCClient │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ └──────────┘ │
│         │                │                │              │       │
│         └────────┬───────┴────────────────┘              │       │
│                  ▼                                       ▼       │
│         ┌───────────────┐                      ┌───────────────┐ │
│         │   Model 1     │                      │   Model 2     │ │
│         │ (Cam 1,2,3,4,5│                      │   (Cam 6)     │ │
│         └───────────────┘                      └───────────────┘ │
│                          │                    │                  │
│                    ┌─────┴────────────────────┴─────┐            │
│                    │    MultiModelLoader (Singleton) │            │
│                    └────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────────┘
```

## 📝 License

NATECH Technology - All rights reserved.

