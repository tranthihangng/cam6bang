# Coal Mine Monitoring System - 6 Camera GUI


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



## 📝 License

NATECH Technology - All rights reserved.

