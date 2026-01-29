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



## 🚀 Sử dụng



### 1. Chỉnh sửa config
Mở file `system_config.json` và cập nhật:
- RTSP URLs cho từng camera
- PLC IPs và addresses
- ROI points
- Detection thresholds

### 2. Chạy ứng dụng

**Với GUI:**
```bash
python main.py --config system_config.json
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



## 📦 Dependencies

```
ultralytics>=8.0.0
opencv-python>=4.8.0
python-snap7>=1.3
pillow>=10.0.0
numpy>=1.24.0
```

## 📝 License

NATECH Technology - All rights reserved.

