# 📋 Hướng dẫn phát triển & Đề xuất cải tiến

## 🎯 Mục tiêu
1. Dễ dàng cấu hình cho người không biết code
2. Đóng gói exe chạy trên máy khác không cần rebuild
3. Cấu hình trực tiếp trên giao diện

---

## ✅ Đã triển khai

### 1. Kiến trúc Module hóa
```
coal_monitoring/
├── config/      # Cấu hình JSON-based
├── camera/      # Video capture
├── detection/   # YOLO detection
├── plc/         # PLC communication
├── alerting/    # Logging
├── ui/          # Giao diện
└── core/        # Orchestration
```

### 2. Multi-Model Support
- Mỗi camera có thể dùng model khác nhau
- Cấu hình trong `system_config.json`

### 3. UI Components (mới thêm)
- `ui/config_panel.py` - Panel cấu hình tổng quát
- `ui/roi_editor.py` - Vẽ ROI trực quan

---

## 📝 Đề xuất cần triển khai thêm

### 1. **Hot-reload Config** ⭐ Quan trọng
Cho phép thay đổi cấu hình mà không cần restart:

```python
# Thêm vào CameraMonitor
def reload_config(self, new_config: CameraConfig):
    """Reload config không cần restart"""
    self._stop_detection_thread()
    self.config = new_config
    self._reinit_detectors()
    self._start_detection_thread()
```

### 2. **Config Validation với Error Messages thân thiện**
```python
def validate_config_friendly(config) -> List[str]:
    """Validate và trả về lỗi tiếng Việt"""
    errors = []
    
    for cam in config.cameras:
        if not cam.rtsp_url:
            errors.append(f"Camera {cam.name}: Chưa nhập địa chỉ RTSP")
        
        if not cam.plc.ip:
            errors.append(f"Camera {cam.name}: Chưa nhập IP PLC")
        
        if len(cam.roi.roi_person) < 3:
            errors.append(f"Camera {cam.name}: Vùng phát hiện người cần ít nhất 3 điểm")
    
    return errors
```

### 3. **Auto-save Config khi thay đổi trên UI**
```python
class ConfigManager:
    """Quản lý config với auto-save"""
    
    def __init__(self, config_path: str):
        self.path = config_path
        self.config = load_config(config_path)
        self._watchers = []
    
    def update(self, key: str, value: Any):
        """Cập nhật và auto-save"""
        setattr(self.config, key, value)
        self._save()
        self._notify_watchers()
    
    def _save(self):
        save_config(self.config, self.path)
```

### 4. **Test Connection Buttons**
Thêm các nút test trong UI:
- ✅ Test Camera (đã có trong config_panel.py)
- ✅ Test PLC (đã có)
- 🆕 Test Model (load và inference 1 frame)

### 5. **Wizard cho người dùng mới**
Hướng dẫn từng bước khi chạy lần đầu:

```
Bước 1: Thêm camera
  → Nhập tên, địa chỉ RTSP
  → Test kết nối
  
Bước 2: Cấu hình PLC
  → Nhập IP, DB, địa chỉ alarm
  → Test kết nối

Bước 3: Vẽ vùng ROI
  → Vẽ vùng phát hiện người
  → Vẽ vùng phát hiện than

Bước 4: Hoàn thành
  → Lưu cấu hình
  → Bắt đầu giám sát
```

---

## 🔧 PyInstaller - Đóng gói EXE

### File `build.spec` đề xuất:
```python
# build.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Collect all module files
added_files = [
    ('system_config.json', '.'),           # Config file
    ('roi_config.json', '.'),              # ROI config
    ('*.pt', '.'),                          # Model files
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'ultralytics',
        'snap7',
        'cv2',
        'PIL',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CoalMonitoring',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Ẩn console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # Icon cho exe
)
```

### Cấu trúc thư mục sau khi đóng gói:
```
CoalMonitoring/
├── CoalMonitoring.exe          # File chạy
├── system_config.json          # Config (người dùng có thể sửa)
├── roi_config.json             # ROI config
├── best_segment_26_11.pt       # Model file
├── artifacts/                  # Thư mục ảnh cảnh báo
└── logs/                       # Thư mục log
```

### Xử lý đường dẫn trong code:
```python
def get_base_dir() -> str:
    """Lấy thư mục gốc (hỗ trợ cả script và exe)"""
    if getattr(sys, 'frozen', False):
        # Chạy từ exe
        return os.path.dirname(sys.executable)
    else:
        # Chạy từ script
        return os.path.dirname(os.path.abspath(__file__))

def get_config_path() -> str:
    """Lấy đường dẫn config"""
    return os.path.join(get_base_dir(), 'system_config.json')
```

---

## 🖥️ Cải tiến UI để dễ dùng

### 1. Menu Bar với các tác vụ chính
```
┌─────────────────────────────────────────────────┐
│ File │ Cấu hình │ Cameras │ Trợ giúp           │
├─────────────────────────────────────────────────┤
│  📹 Camera 1    📹 Camera 2    📹 Camera 3     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │  Video   │   │  Video   │   │  Video   │   │
│  │  Feed    │   │  Feed    │   │  Feed    │   │
│  └──────────┘   └──────────┘   └──────────┘   │
│  [⚙️ Config]    [⚙️ Config]    [⚙️ Config]    │
└─────────────────────────────────────────────────┘
```

### 2. Right-click Context Menu
```
Click phải vào camera:
├── 🔄 Restart camera
├── ⚙️ Cấu hình camera này
├── 🎯 Vẽ lại ROI người
├── ⬛ Vẽ lại ROI than
├── 🔌 Test PLC
└── ❌ Tắt camera
```

### 3. Status Bar chi tiết
```
Camera 1: ✅ Đang chạy | FPS: 22.1 | PLC: Kết nối | Than: 45.2% | Người: Không
```

---

## 📊 Logging & Diagnostics

### 1. Log Viewer trong UI
```python
class LogViewer(tk.Frame):
    """Widget hiển thị log real-time"""
    
    def __init__(self, parent):
        # Text widget với màu sắc theo level
        # ERROR: đỏ, WARNING: vàng, INFO: trắng
        pass
    
    def add_log(self, level: str, message: str):
        # Thêm log với timestamp và màu
        pass
```

### 2. Export Log
```python
def export_logs(date_range: Tuple[date, date], output_path: str):
    """Xuất log ra file Excel/CSV"""
    pass
```

---

## 🔐 Security Considerations

### 1. Mã hóa thông tin nhạy cảm
```python
# Không lưu password dạng plain text
# Sử dụng keyring hoặc mã hóa
import keyring

def save_rtsp_password(camera_id: str, password: str):
    keyring.set_password("coal_monitoring", camera_id, password)

def get_rtsp_password(camera_id: str) -> str:
    return keyring.get_password("coal_monitoring", camera_id)
```

### 2. Config Backup tự động
```python
def backup_config():
    """Backup config trước khi thay đổi"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"config_backup_{timestamp}.json"
    shutil.copy("system_config.json", backup_path)
```

---

## 📱 Roadmap đề xuất

### Phase 1: UI Enhancement (1-2 tuần)
- [ ] Hoàn thiện Config Panel
- [ ] Hoàn thiện ROI Editor
- [ ] Thêm Test buttons
- [ ] Right-click context menu

### Phase 2: UX Improvement (1 tuần)
- [ ] Wizard cho người dùng mới
- [ ] Validation với error messages tiếng Việt
- [ ] Auto-save config

### Phase 3: Packaging (1 tuần)
- [ ] Tạo build script
- [ ] Tối ưu kích thước exe
- [ ] Tạo installer (NSIS/InnoSetup)

### Phase 4: Advanced Features (2 tuần)
- [ ] Hot-reload config
- [ ] Log viewer & export
- [ ] Remote monitoring (web dashboard)

---

## 💡 Tips cho người dùng không biết code

1. **Config file `system_config.json`**
   - Có thể mở bằng Notepad
   - Cẩn thận với dấu phẩy và ngoặc
   - Backup trước khi sửa

2. **Thêm camera mới**
   - Mở Config Panel từ menu
   - Nhấn "Thêm camera"
   - Điền thông tin theo form

3. **Vẽ ROI**
   - Không cần nhập tọa độ
   - Click trực tiếp trên video
   - Có thể hoàn tác nếu sai

4. **Khi gặp lỗi**
   - Kiểm tra log trong thư mục `logs/`
   - Chụp màn hình lỗi
   - Liên hệ support

---

## 📞 Cấu trúc Support

```
Cấp 1: Người dùng tự khắc phục
  ├── Đọc hướng dẫn trong app
  ├── Kiểm tra kết nối camera/PLC
  └── Restart ứng dụng

Cấp 2: IT Support
  ├── Kiểm tra file log
  ├── Sửa config file
  └── Reinstall nếu cần

Cấp 3: Developer
  ├── Debug code
  ├── Fix bug
  └── Release bản mới
```

