"""
ROI Editor UI
=============

Giao diện vẽ ROI trực quan trên video/hình ảnh.
Cho phép người dùng click để đặt các điểm ROI thay vì nhập tọa độ.
"""

import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import numpy as np
from typing import List, Tuple, Optional, Callable


class ROIEditor(tk.Toplevel):
    """
    Editor để vẽ ROI trên frame video
    
    Usage:
        editor = ROIEditor(
            parent=root,
            frame=cv2_frame,
            initial_points=[(100, 100), (500, 100), ...],
            on_save=lambda points: save_roi(points)
        )
    """
    
    def __init__(
        self, 
        parent, 
        frame: np.ndarray,
        roi_type: str = "person",  # "person" or "coal"
        initial_points: List[Tuple[int, int]] = None,
        on_save: Optional[Callable[[List[Tuple[int, int]]], None]] = None
    ):
        super().__init__(parent)
        
        self.frame = frame
        self.roi_type = roi_type
        self.points: List[Tuple[int, int]] = initial_points.copy() if initial_points else []
        self.on_save = on_save
        
        # Display size
        self.display_width = 960
        self.display_height = 540
        
        # Calculate scale
        h, w = frame.shape[:2]
        self.scale_x = self.display_width / w
        self.scale_y = self.display_height / h
        self.original_size = (w, h)
        
        # UI setup
        self.title(f"Vẽ vùng ROI - {roi_type.upper()}")
        self.geometry(f"{self.display_width + 200}x{self.display_height + 100}")
        self.configure(bg='#1a1a2e')
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._draw_frame()
    
    def _create_widgets(self):
        """Tạo widgets"""
        # Main container
        main_frame = tk.Frame(self, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left: Canvas
        canvas_frame = tk.Frame(main_frame, bg='#1a1a2e')
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Instructions
        color = '#e94560' if self.roi_type == 'coal' else '#0f4c75'
        tk.Label(
            canvas_frame, 
            text=f"🎯 Click chuột trái để đặt điểm | Click phải để xóa điểm cuối | Nhấn ENTER để lưu",
            bg='#1a1a2e', fg='#eee', font=('Arial', 10)
        ).pack(pady=5)
        
        # Canvas for drawing
        self.canvas = tk.Canvas(
            canvas_frame, 
            width=self.display_width, 
            height=self.display_height,
            bg='#16213e',
            highlightthickness=2,
            highlightbackground=color
        )
        self.canvas.pack(pady=5)
        
        # Bind events
        self.canvas.bind('<Button-1>', self._on_left_click)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.bind('<Return>', self._on_enter)
        self.bind('<Escape>', self._on_escape)
        
        # Right panel
        right_frame = tk.Frame(main_frame, bg='#1a1a2e', width=180)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        right_frame.pack_propagate(False)
        
        # Points list
        tk.Label(right_frame, text="Các điểm ROI:", bg='#1a1a2e', fg='white',
                font=('Arial', 10, 'bold')).pack(pady=5)
        
        self.points_listbox = tk.Listbox(
            right_frame, bg='#16213e', fg='white',
            selectbackground='#e94560', font=('Courier', 9),
            height=15
        )
        self.points_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(right_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(
            btn_frame, text="🗑️ Xóa tất cả", 
            command=self._clear_all,
            bg='#e74c3c', fg='white'
        ).pack(fill=tk.X, pady=2)
        
        tk.Button(
            btn_frame, text="↩️ Hoàn tác", 
            command=self._undo,
            bg='#f39c12', fg='white'
        ).pack(fill=tk.X, pady=2)
        
        # Bottom buttons
        bottom_frame = tk.Frame(self, bg='#1a1a2e')
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            bottom_frame, text="✅ Lưu ROI", 
            command=self._save,
            bg='#27ae60', fg='white', font=('Arial', 11, 'bold'),
            width=12
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            bottom_frame, text="❌ Hủy", 
            command=self._cancel,
            bg='#95a5a6', fg='white', font=('Arial', 10),
            width=10
        ).pack(side=tk.RIGHT, padx=5)
        
        # Info
        self.info_label = tk.Label(
            bottom_frame, text=f"Điểm: 0 | Kích thước gốc: {self.original_size[0]}x{self.original_size[1]}",
            bg='#1a1a2e', fg='#bdc3c7', font=('Arial', 9)
        )
        self.info_label.pack(side=tk.LEFT)
    
    def _draw_frame(self):
        """Vẽ frame lên canvas"""
        # Resize frame
        frame_resized = cv2.resize(
            self.frame, 
            (self.display_width, self.display_height),
            interpolation=cv2.INTER_AREA
        )
        
        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        
        # Draw existing points and lines
        if len(self.points) > 0:
            # Scale points for display
            display_points = [
                (int(x * self.scale_x), int(y * self.scale_y)) 
                for (x, y) in self.points
            ]
            
            # Draw filled polygon (semi-transparent)
            overlay = frame_rgb.copy()
            pts = np.array(display_points, dtype=np.int32)
            color = (233, 69, 96) if self.roi_type == 'coal' else (15, 76, 117)
            cv2.fillPoly(overlay, [pts], color)
            frame_rgb = cv2.addWeighted(frame_rgb, 0.7, overlay, 0.3, 0)
            
            # Draw polygon outline
            outline_color = (255, 100, 100) if self.roi_type == 'coal' else (100, 200, 255)
            cv2.polylines(frame_rgb, [pts], isClosed=True, color=outline_color, thickness=2)
            
            # Draw points
            for i, (x, y) in enumerate(display_points):
                cv2.circle(frame_rgb, (x, y), 6, (255, 255, 255), -1)
                cv2.circle(frame_rgb, (x, y), 6, outline_color, 2)
                cv2.putText(frame_rgb, str(i+1), (x+10, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Convert to PhotoImage
        pil_image = Image.fromarray(frame_rgb)
        self.photo = ImageTk.PhotoImage(pil_image)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # Update points list
        self.points_listbox.delete(0, tk.END)
        for i, (x, y) in enumerate(self.points):
            self.points_listbox.insert(tk.END, f"{i+1}: ({x}, {y})")
        
        # Update info
        self.info_label.config(
            text=f"Điểm: {len(self.points)} | Kích thước gốc: {self.original_size[0]}x{self.original_size[1]}"
        )
    
    def _on_left_click(self, event):
        """Thêm điểm khi click trái"""
        # Convert display coordinates to original
        x = int(event.x / self.scale_x)
        y = int(event.y / self.scale_y)
        
        # Clamp to valid range
        x = max(0, min(x, self.original_size[0] - 1))
        y = max(0, min(y, self.original_size[1] - 1))
        
        self.points.append((x, y))
        self._draw_frame()
    
    def _on_right_click(self, event):
        """Xóa điểm cuối khi click phải"""
        if self.points:
            self.points.pop()
            self._draw_frame()
    
    def _on_enter(self, event):
        """Lưu khi nhấn Enter"""
        self._save()
    
    def _on_escape(self, event):
        """Hủy khi nhấn Escape"""
        self._cancel()
    
    def _clear_all(self):
        """Xóa tất cả điểm"""
        if messagebox.askyesno("Xác nhận", "Xóa tất cả các điểm?"):
            self.points.clear()
            self._draw_frame()
    
    def _undo(self):
        """Hoàn tác điểm cuối"""
        if self.points:
            self.points.pop()
            self._draw_frame()
    
    def _save(self):
        """Lưu ROI"""
        if len(self.points) < 3:
            messagebox.showwarning("Cảnh báo", "Cần ít nhất 3 điểm để tạo ROI!")
            return
        
        if self.on_save:
            self.on_save(self.points.copy())
        
        messagebox.showinfo("Thành công", f"Đã lưu ROI với {len(self.points)} điểm!")
        self.destroy()
    
    def _cancel(self):
        """Hủy"""
        if self.points and messagebox.askyesno("Xác nhận", "Hủy thay đổi ROI?"):
            self.destroy()
        elif not self.points:
            self.destroy()


def open_roi_editor(
    parent,
    video_source: str,
    roi_type: str = "person",
    initial_points: List[Tuple[int, int]] = None,
    on_save: Callable = None
):
    """
    Helper function để mở ROI editor
    
    Args:
        parent: Parent window
        video_source: RTSP URL hoặc video file path
        roi_type: "person" hoặc "coal"
        initial_points: Các điểm ROI ban đầu
        on_save: Callback khi lưu
    """
    # Capture one frame
    cap = cv2.VideoCapture(video_source)
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        messagebox.showerror("Lỗi", f"Không thể kết nối đến camera:\n{video_source}")
        return None
    
    # Open editor
    editor = ROIEditor(
        parent=parent,
        frame=frame,
        roi_type=roi_type,
        initial_points=initial_points,
        on_save=on_save
    )
    
    return editor

