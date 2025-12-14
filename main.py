"""
Coal Mine Monitoring System - Entry Point
==========================================

Khởi chạy ứng dụng giám sát mỏ than đa camera.

Sử dụng:
    # Chạy với GUI (mặc định)
    python main.py
    
    # Chạy với config cụ thể
    python main.py --config system_config.json
    
    # Tạo config mẫu
    python main.py --create-config 6
    
    # Chạy headless (không có GUI)
    python main.py --headless
"""

import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def safe_print(msg: str) -> None:
    """Print với fallback cho Windows console"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Fallback: loại bỏ emoji
        import re
        cleaned = re.sub(r'[^\x00-\x7F]+', '', msg)
        print(cleaned)


def create_sample_config(num_cameras: int, output_path: str) -> None:
    """Tạo file config mẫu"""
    from coal_monitoring.config import create_default_config, save_config
    
    config = create_default_config(num_cameras)
    save_config(config, output_path)
    safe_print(f"[OK] Da tao file config mau: {output_path}")
    safe_print(f"   - So camera: {num_cameras}")
    safe_print(f"   - Cameras: {[cam.camera_id for cam in config.cameras]}")


def run_gui(config) -> None:
    """Chạy ứng dụng với GUI"""
    import tkinter as tk
    from coal_monitoring.ui import MainWindow
    
    root = tk.Tk()
    window = MainWindow(root, config)
    window.run()


def run_headless(config) -> None:
    """Chạy ứng dụng không có GUI"""
    from coal_monitoring.core import MultiCameraApp
    import time
    import signal
    
    print("=" * 50)
    print("Coal Mine Monitoring System - Headless Mode")
    print("=" * 50)
    
    # Setup signal handler
    running = [True]
    
    def signal_handler(sig, frame):
        print("\n⏹️ Nhận tín hiệu dừng...")
        running[0] = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Callback functions
    def on_alert(message, monitor):
        print(f"[{monitor.config.name}] {message}")
    
    def on_global_alert(message):
        print(f"[SYSTEM] {message}")
    
    # Create app
    app = MultiCameraApp(
        config=config,
        on_alert=on_alert,
        on_global_alert=on_global_alert,
    )
    
    # Load model
    print(f"🔄 Đang load model: {config.model_path}")
    if not app.load_model():
        print("❌ Không thể load model!")
        return
    
    # Start all cameras
    print(f"🔄 Đang khởi động {len(config.cameras)} cameras...")
    results = app.start_all()
    
    success_count = sum(1 for r in results.values() if r)
    print(f"✅ Đã khởi động {success_count}/{len(results)} cameras")
    
    # Main loop
    print("\nĐang giám sát... (Nhấn Ctrl+C để dừng)")
    print("-" * 50)
    
    try:
        while running[0] and app.is_any_running:
            stats = app.get_stats()
            print(f"\r⏱️ Running: {stats.running_cameras}/{stats.total_cameras} | "
                  f"Person: {stats.total_person_alerts} | Coal: {stats.total_coal_alerts}",
                  end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    # Stop all
    print("\n\n⏹️ Đang dừng...")
    app.stop_all()
    print("✅ Đã dừng tất cả cameras")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Coal Mine Monitoring System - Multi-Camera Support"
    )
    parser.add_argument(
        "--config", 
        type=str, 
        default="system_config.json",
        help="Đường dẫn file cấu hình JSON"
    )
    parser.add_argument(
        "--create-config",
        type=int,
        metavar="NUM_CAMERAS",
        help="Tạo file config mẫu với số camera chỉ định (1-6)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Chạy không có GUI (command line only)"
    )
    
    args = parser.parse_args()
    
    # Tạo config mẫu
    if args.create_config:
        if 1 <= args.create_config <= 6:
            create_sample_config(args.create_config, args.config)
        else:
            print("❌ Số camera phải trong khoảng 1-6")
        return
    
    # Load config
    from coal_monitoring.config import load_config, save_config, create_default_config
    
    try:
        if os.path.exists(args.config):
            config = load_config(args.config)
            print(f"✅ Đã load config từ: {args.config}")
        else:
            print(f"⚠️ Không tìm thấy file config: {args.config}")
            print("   Đang tạo config mặc định với 2 cameras...")
            config = create_default_config(2)
            save_config(config, args.config)
            print(f"✅ Đã tạo file config mặc định: {args.config}")
    except Exception as e:
        print(f"❌ Lỗi load config: {e}")
        return
    
    # Validate config
    errors = config.validate()
    if errors:
        print("❌ Config không hợp lệ:")
        for err in errors:
            print(f"   - {err}")
        return
    
    print(f"📋 Số cameras: {len(config.cameras)}")
    for cam in config.cameras:
        print(f"   - {cam.name}: {cam.plc.ip}")
    
    # Run
    if args.headless:
        run_headless(config)
    else:
        run_gui(config)


if __name__ == "__main__":
    main()

