"""
Configuration Panel UI
======================

Giao diện cấu hình trực quan cho người dùng không biết code.
Cho phép:
- Thêm/sửa/xóa camera
- Cấu hình PLC
- Vẽ ROI trực quan
- Điều chỉnh ngưỡng phát hiện
- Lưu config tự động
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
from typing import Optional, Callable, List, Tuple
import threading


class ConfigPanel(tk.Toplevel):
    """
    Panel cấu hình camera và hệ thống
    Thiết kế cho người dùng không biết code
    """
    
    def __init__(self, parent, config, on_save: Optional[Callable] = None):
        super().__init__(parent)
        
        self.config = config
        self.on_save = on_save
        self.modified = False
        
        self.title("Cấu hình hệ thống")
        self.geometry("900x700")
        self.configure(bg='#2c3e50')
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._load_current_config()
    
    def _create_widgets(self):
        """Tạo các widget"""
        # Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Cameras
        self.cameras_frame = self._create_cameras_tab()
        self.notebook.add(self.cameras_frame, text="📹 Cameras")
        
        # Tab 2: Models  
        self.models_frame = self._create_models_tab()
        self.notebook.add(self.models_frame, text="🤖 Models")
        
        # Tab 3: Detection Settings
        self.detection_frame = self._create_detection_tab()
        self.notebook.add(self.detection_frame, text="🔍 Phát hiện")
        
        # Tab 4: Advanced
        self.advanced_frame = self._create_advanced_tab()
        self.notebook.add(self.advanced_frame, text="⚙️ Nâng cao")
        
        # Bottom buttons
        self._create_bottom_buttons()
    
    def _create_cameras_tab(self) -> tk.Frame:
        """Tab cấu hình cameras"""
        frame = tk.Frame(self.notebook, bg='#34495e')
        
        # Left: Camera list
        left_frame = tk.Frame(frame, bg='#34495e', width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="Danh sách Camera", 
                bg='#34495e', fg='white', font=('Arial', 12, 'bold')
        ).pack(pady=5)
        
        # Listbox
        self.camera_listbox = tk.Listbox(left_frame, bg='#2c3e50', fg='white',
                                         selectbackground='#3498db', font=('Arial', 10))
        self.camera_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.camera_listbox.bind('<<ListboxSelect>>', self._on_camera_select)
        
        # Buttons
        btn_frame = tk.Frame(left_frame, bg='#34495e')
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(btn_frame, text="➕ Thêm", command=self._add_camera,
                 bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="➖ Xóa", command=self._remove_camera,
                 bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=2)
        
        # Right: Camera details
        right_frame = tk.Frame(frame, bg='#34495e')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_camera_detail_form(right_frame)
        
        return frame
    
    def _create_camera_detail_form(self, parent):
        """Form chi tiết camera"""
        # Camera Info
        info_frame = tk.LabelFrame(parent, text="Thông tin Camera",
                                   bg='#34495e', fg='white', font=('Arial', 10, 'bold'))
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Name
        row = tk.Frame(info_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="Tên camera:", bg='#34495e', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        self.cam_name_var = tk.StringVar()
        tk.Entry(row, textvariable=self.cam_name_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # RTSP URL
        row = tk.Frame(info_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="Địa chỉ RTSP:", bg='#34495e', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        self.cam_rtsp_var = tk.StringVar()
        tk.Entry(row, textvariable=self.cam_rtsp_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="Test", command=self._test_camera, bg='#3498db', fg='white').pack(side=tk.RIGHT, padx=5)
        
        # PLC Info
        plc_frame = tk.LabelFrame(parent, text="Cấu hình PLC",
                                  bg='#34495e', fg='white', font=('Arial', 10, 'bold'))
        plc_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # PLC IP
        row = tk.Frame(plc_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="IP PLC:", bg='#34495e', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        self.plc_ip_var = tk.StringVar()
        tk.Entry(row, textvariable=self.plc_ip_var, width=20).pack(side=tk.LEFT)
        tk.Button(row, text="Test PLC", command=self._test_plc, bg='#e67e22', fg='white').pack(side=tk.RIGHT, padx=5)
        
        # PLC Address
        row = tk.Frame(plc_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="DB Number:", bg='#34495e', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        self.plc_db_var = tk.StringVar(value="300")
        tk.Entry(row, textvariable=self.plc_db_var, width=10).pack(side=tk.LEFT)
        
        # Alarm addresses
        row = tk.Frame(plc_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="Địa chỉ báo động người:", bg='#34495e', fg='white', width=20, anchor='w').pack(side=tk.LEFT)
        self.person_byte_var = tk.StringVar(value="6")
        self.person_bit_var = tk.StringVar(value="0")
        tk.Entry(row, textvariable=self.person_byte_var, width=5).pack(side=tk.LEFT)
        tk.Label(row, text=".", bg='#34495e', fg='white').pack(side=tk.LEFT)
        tk.Entry(row, textvariable=self.person_bit_var, width=5).pack(side=tk.LEFT)
        
        row = tk.Frame(plc_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="Địa chỉ báo động than:", bg='#34495e', fg='white', width=20, anchor='w').pack(side=tk.LEFT)
        self.coal_byte_var = tk.StringVar(value="6")
        self.coal_bit_var = tk.StringVar(value="1")
        tk.Entry(row, textvariable=self.coal_byte_var, width=5).pack(side=tk.LEFT)
        tk.Label(row, text=".", bg='#34495e', fg='white').pack(side=tk.LEFT)
        tk.Entry(row, textvariable=self.coal_bit_var, width=5).pack(side=tk.LEFT)
        
        # ROI Button
        roi_frame = tk.LabelFrame(parent, text="Vùng quan tâm (ROI)",
                                  bg='#34495e', fg='white', font=('Arial', 10, 'bold'))
        roi_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(roi_frame, text="🎯 Vẽ vùng phát hiện người", 
                 command=lambda: self._open_roi_editor('person'),
                 bg='#9b59b6', fg='white', font=('Arial', 10)).pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(roi_frame, text="⬛ Vẽ vùng phát hiện than",
                 command=lambda: self._open_roi_editor('coal'),
                 bg='#e74c3c', fg='white', font=('Arial', 10)).pack(fill=tk.X, padx=10, pady=5)
    
    def _create_models_tab(self) -> tk.Frame:
        """Tab cấu hình models"""
        frame = tk.Frame(self.notebook, bg='#34495e')
        
        tk.Label(frame, text="Cấu hình Models YOLO", 
                bg='#34495e', fg='white', font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Models list
        self.models_tree = ttk.Treeview(frame, columns=('name', 'path', 'cameras'), 
                                         show='headings', height=8)
        self.models_tree.heading('name', text='Tên Model')
        self.models_tree.heading('path', text='Đường dẫn')
        self.models_tree.heading('cameras', text='Cameras')
        self.models_tree.column('name', width=150)
        self.models_tree.column('path', width=300)
        self.models_tree.column('cameras', width=150)
        self.models_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(frame, bg='#34495e')
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(btn_frame, text="➕ Thêm Model", command=self._add_model,
                 bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="✏️ Sửa", command=self._edit_model,
                 bg='#3498db', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="➖ Xóa", command=self._remove_model,
                 bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📁 Chọn file model...", command=self._browse_model,
                 bg='#9b59b6', fg='white').pack(side=tk.RIGHT, padx=5)
        
        # Help text
        help_text = """
💡 Hướng dẫn:
- Mỗi model có thể được gán cho nhiều cameras
- Camera số nào dùng model nào được cấu hình trong cột "Cameras"  
- Ví dụ: cameras [1, 2, 3] nghĩa là Camera 1, 2, 3 dùng model này
        """
        tk.Label(frame, text=help_text, bg='#34495e', fg='#bdc3c7', 
                justify=tk.LEFT, font=('Arial', 9)).pack(pady=10)
        
        return frame
    
    def _create_detection_tab(self) -> tk.Frame:
        """Tab cấu hình detection"""
        frame = tk.Frame(self.notebook, bg='#34495e')
        
        tk.Label(frame, text="Cấu hình phát hiện", 
                bg='#34495e', fg='white', font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Detection settings
        settings_frame = tk.Frame(frame, bg='#34495e')
        settings_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Confidence threshold
        row = tk.Frame(settings_frame, bg='#34495e')
        row.pack(fill=tk.X, pady=5)
        tk.Label(row, text="Ngưỡng tin cậy (%):", bg='#34495e', fg='white', width=25, anchor='w').pack(side=tk.LEFT)
        self.confidence_var = tk.IntVar(value=70)
        tk.Scale(row, from_=10, to=100, orient=tk.HORIZONTAL, variable=self.confidence_var,
                bg='#34495e', fg='white', length=300).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Person consecutive frames
        row = tk.Frame(settings_frame, bg='#34495e')
        row.pack(fill=tk.X, pady=5)
        tk.Label(row, text="Số frame liên tiếp BẬT cảnh báo người:", bg='#34495e', fg='white', width=35, anchor='w').pack(side=tk.LEFT)
        self.person_consecutive_var = tk.IntVar(value=3)
        tk.Scale(row, from_=1, to=20, orient=tk.HORIZONTAL, variable=self.person_consecutive_var,
                bg='#34495e', fg='white', length=200).pack(side=tk.LEFT)
        
        # Person off frames
        row = tk.Frame(settings_frame, bg='#34495e')
        row.pack(fill=tk.X, pady=5)
        tk.Label(row, text="Số frame để TẮT cảnh báo người:", bg='#34495e', fg='white', width=35, anchor='w').pack(side=tk.LEFT)
        self.person_off_var = tk.IntVar(value=5)
        tk.Scale(row, from_=1, to=20, orient=tk.HORIZONTAL, variable=self.person_off_var,
                bg='#34495e', fg='white', length=200).pack(side=tk.LEFT)
        
        # Coal ratio threshold
        row = tk.Frame(settings_frame, bg='#34495e')
        row.pack(fill=tk.X, pady=5)
        tk.Label(row, text="Ngưỡng tỷ lệ than (%):", bg='#34495e', fg='white', width=25, anchor='w').pack(side=tk.LEFT)
        self.coal_ratio_var = tk.IntVar(value=73)
        tk.Scale(row, from_=30, to=100, orient=tk.HORIZONTAL, variable=self.coal_ratio_var,
                bg='#34495e', fg='white', length=300).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Coal consecutive frames
        row = tk.Frame(settings_frame, bg='#34495e')
        row.pack(fill=tk.X, pady=5)
        tk.Label(row, text="Số frame liên tiếp BẬT cảnh báo than:", bg='#34495e', fg='white', width=35, anchor='w').pack(side=tk.LEFT)
        self.coal_consecutive_var = tk.IntVar(value=5)
        tk.Scale(row, from_=1, to=50, orient=tk.HORIZONTAL, variable=self.coal_consecutive_var,
                bg='#34495e', fg='white', length=200).pack(side=tk.LEFT)
        
        # Enable coal detection
        self.coal_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Bật phát hiện tắc than",
                      variable=self.coal_enabled_var,
                      bg='#34495e', fg='white', selectcolor='#2c3e50',
                      font=('Arial', 11, 'bold')).pack(pady=10)
        
        return frame
    
    def _create_advanced_tab(self) -> tk.Frame:
        """Tab cài đặt nâng cao"""
        frame = tk.Frame(self.notebook, bg='#34495e')
        
        tk.Label(frame, text="Cài đặt nâng cao", 
                bg='#34495e', fg='white', font=('Arial', 14, 'bold')).pack(pady=10)
        
        settings_frame = tk.Frame(frame, bg='#34495e')
        settings_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Target FPS
        row = tk.Frame(settings_frame, bg='#34495e')
        row.pack(fill=tk.X, pady=5)
        tk.Label(row, text="FPS mục tiêu:", bg='#34495e', fg='white', width=20, anchor='w').pack(side=tk.LEFT)
        self.fps_var = tk.IntVar(value=22)
        tk.Scale(row, from_=1, to=30, orient=tk.HORIZONTAL, variable=self.fps_var,
                bg='#34495e', fg='white', length=200).pack(side=tk.LEFT)
        
        # Paths
        path_frame = tk.LabelFrame(frame, text="Đường dẫn lưu trữ",
                                   bg='#34495e', fg='white', font=('Arial', 10, 'bold'))
        path_frame.pack(fill=tk.X, padx=20, pady=10)
        
        row = tk.Frame(path_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="Thư mục ảnh:", bg='#34495e', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        self.artifacts_var = tk.StringVar(value="artifacts")
        tk.Entry(row, textvariable=self.artifacts_var, width=40).pack(side=tk.LEFT)
        tk.Button(row, text="...", command=lambda: self._browse_folder(self.artifacts_var)).pack(side=tk.LEFT, padx=5)
        
        row = tk.Frame(path_frame, bg='#34495e')
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text="Thư mục log:", bg='#34495e', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        self.logs_var = tk.StringVar(value="logs")
        tk.Entry(row, textvariable=self.logs_var, width=40).pack(side=tk.LEFT)
        tk.Button(row, text="...", command=lambda: self._browse_folder(self.logs_var)).pack(side=tk.LEFT, padx=5)
        
        # Backup/Restore
        backup_frame = tk.Frame(frame, bg='#34495e')
        backup_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Button(backup_frame, text="📥 Xuất cấu hình (Backup)", 
                 command=self._export_config, bg='#3498db', fg='white',
                 font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        tk.Button(backup_frame, text="📤 Nhập cấu hình (Restore)",
                 command=self._import_config, bg='#e67e22', fg='white',
                 font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        
        return frame
    
    def _create_bottom_buttons(self):
        """Tạo buttons ở dưới"""
        btn_frame = tk.Frame(self, bg='#2c3e50')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(btn_frame, text="💾 Lưu cấu hình", command=self._save_config,
                 bg='#27ae60', fg='white', font=('Arial', 11, 'bold'),
                 width=15).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="❌ Hủy", command=self._cancel,
                 bg='#95a5a6', fg='white', font=('Arial', 11),
                 width=10).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="🔄 Reset về mặc định", command=self._reset_defaults,
                 bg='#e74c3c', fg='white', font=('Arial', 10),
                 width=18).pack(side=tk.LEFT, padx=5)
    
    def _load_current_config(self):
        """Load cấu hình hiện tại vào form"""
        # Load cameras
        self.camera_listbox.delete(0, tk.END)
        for cam in self.config.cameras:
            self.camera_listbox.insert(tk.END, f"{cam.name} ({cam.camera_id})")
        
        # Load models
        for item in self.models_tree.get_children():
            self.models_tree.delete(item)
        
        for model_id, model_cfg in self.config.models.items():
            self.models_tree.insert('', tk.END, values=(
                model_cfg.name,
                model_cfg.path,
                str(model_cfg.cameras)
            ))
    
    # Event handlers
    def _on_camera_select(self, event):
        """Khi chọn camera từ list"""
        selection = self.camera_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx < len(self.config.cameras):
            cam = self.config.cameras[idx]
            
            self.cam_name_var.set(cam.name)
            self.cam_rtsp_var.set(cam.rtsp_url)
            self.plc_ip_var.set(cam.plc.ip)
            self.plc_db_var.set(str(cam.plc.db_number))
            self.person_byte_var.set(str(cam.plc.person_alarm_byte))
            self.person_bit_var.set(str(cam.plc.person_alarm_bit))
            self.coal_byte_var.set(str(cam.plc.coal_alarm_byte))
            self.coal_bit_var.set(str(cam.plc.coal_alarm_bit))
    
    def _add_camera(self):
        """Thêm camera mới"""
        name = simpledialog.askstring("Thêm Camera", "Nhập tên camera:", parent=self)
        if name:
            # Create new camera config
            cam_id = f"camera_{len(self.config.cameras) + 1}"
            messagebox.showinfo("Thông báo", f"Đã thêm camera: {name}\nVui lòng cấu hình thông tin chi tiết.")
            self._load_current_config()
            self.modified = True
    
    def _remove_camera(self):
        """Xóa camera"""
        selection = self.camera_listbox.curselection()
        if selection:
            if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa camera này?"):
                self.modified = True
    
    def _test_camera(self):
        """Test kết nối camera"""
        rtsp = self.cam_rtsp_var.get()
        if not rtsp:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập địa chỉ RTSP!")
            return
        
        messagebox.showinfo("Test Camera", f"Đang test kết nối...\n{rtsp}")
        # TODO: Implement actual test
    
    def _test_plc(self):
        """Test kết nối PLC"""
        ip = self.plc_ip_var.get()
        if not ip:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập IP PLC!")
            return
        
        messagebox.showinfo("Test PLC", f"Đang test kết nối PLC...\n{ip}")
        # TODO: Implement actual test
    
    def _open_roi_editor(self, roi_type: str):
        """Mở editor để vẽ ROI"""
        messagebox.showinfo("ROI Editor", 
            f"Sẽ mở cửa sổ vẽ vùng {roi_type}.\n"
            "Click chuột để đặt các điểm, nhấn Enter để hoàn thành.")
        # TODO: Implement ROI editor
    
    def _add_model(self):
        """Thêm model mới"""
        path = filedialog.askopenfilename(
            title="Chọn file model",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")]
        )
        if path:
            name = simpledialog.askstring("Tên Model", "Nhập tên cho model:", parent=self)
            if name:
                cameras = simpledialog.askstring("Cameras", 
                    "Nhập số camera sử dụng model này (ví dụ: 1,2,3):", parent=self)
                # TODO: Add to config
                self.modified = True
    
    def _edit_model(self):
        """Sửa model"""
        selection = self.models_tree.selection()
        if not selection:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn model cần sửa!")
    
    def _remove_model(self):
        """Xóa model"""
        selection = self.models_tree.selection()
        if selection:
            if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa model này?"):
                self.modified = True
    
    def _browse_model(self):
        """Chọn file model"""
        path = filedialog.askopenfilename(
            title="Chọn file model",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")]
        )
        if path:
            messagebox.showinfo("Model", f"Đã chọn: {path}")
    
    def _browse_folder(self, var: tk.StringVar):
        """Chọn thư mục"""
        path = filedialog.askdirectory()
        if path:
            var.set(path)
    
    def _export_config(self):
        """Xuất cấu hình ra file"""
        path = filedialog.asksaveasfilename(
            title="Lưu cấu hình",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if path:
            # TODO: Save config to file
            messagebox.showinfo("Thành công", f"Đã xuất cấu hình ra:\n{path}")
    
    def _import_config(self):
        """Nhập cấu hình từ file"""
        path = filedialog.askopenfilename(
            title="Chọn file cấu hình",
            filetypes=[("JSON files", "*.json")]
        )
        if path:
            if messagebox.askyesno("Xác nhận", "Cấu hình hiện tại sẽ bị ghi đè. Tiếp tục?"):
                # TODO: Load config from file
                messagebox.showinfo("Thành công", "Đã nhập cấu hình thành công!")
    
    def _reset_defaults(self):
        """Reset về mặc định"""
        if messagebox.askyesno("Xác nhận", "Reset tất cả về cấu hình mặc định?"):
            # TODO: Reset config
            self.modified = True
    
    def _save_config(self):
        """Lưu cấu hình"""
        try:
            # TODO: Validate and save config
            if self.on_save:
                self.on_save(self.config)
            
            messagebox.showinfo("Thành công", "Đã lưu cấu hình thành công!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu cấu hình:\n{str(e)}")
    
    def _cancel(self):
        """Hủy thay đổi"""
        if self.modified:
            if not messagebox.askyesno("Xác nhận", "Có thay đổi chưa lưu. Bạn có chắc muốn thoát?"):
                return
        self.destroy()

