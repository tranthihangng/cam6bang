"""
Demo Optimized Components
=========================

Script demo các component đã tối ưu.
Chạy: python -m coal_monitoring.examples.demo_optimized
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import threading
import argparse


def demo_optimized_video_source():
    """Demo OptimizedVideoSource"""
    print("\n" + "=" * 60)
    print("📹 DEMO: OptimizedVideoSource")
    print("=" * 60)
    
    from coal_monitoring.camera import OptimizedVideoSource, ConnectionStatus
    
    # Callback functions
    frame_count = [0]
    
    def on_frame(frame, timestamp):
        frame_count[0] += 1
        if frame_count[0] % 50 == 0:
            print(f"  Received {frame_count[0]} frames")
    
    def on_status(status: ConnectionStatus):
        print(f"  Status changed: {status.value}")
    
    def on_error(msg):
        print(f"  Error: {msg}")
    
    # Test với video file (hoặc RTSP nếu có)
    test_source = "test_video.mp4"  # Thay bằng RTSP URL thực
    
    if not os.path.exists(test_source):
        print(f"  ⚠️ Test file '{test_source}' không tồn tại")
        print(f"  Sử dụng RTSP URL hoặc tạo file test_video.mp4")
        return
    
    source = OptimizedVideoSource(
        source_path=test_source,
        target_fps=25,
        buffer_size=1,
        enable_grab_pattern=False,  # False cho video file
        on_frame=on_frame,
        on_status_change=on_status,
        on_error=on_error,
    )
    
    print(f"  Starting source: {test_source}")
    if source.start():
        print(f"  ✅ Started successfully")
        print(f"  Video info: {source.video_info}")
        
        # Run for 5 seconds
        time.sleep(5)
        
        # Get stats
        print(f"\n  📊 Stats: {source.get_stats_dict()}")
        
        source.stop()
        print(f"  ✅ Stopped")
    else:
        print(f"  ❌ Failed to start")


def demo_inference_stats():
    """Demo InferenceStatsManager"""
    print("\n" + "=" * 60)
    print("📊 DEMO: InferenceStatsManager")
    print("=" * 60)
    
    from coal_monitoring.core import get_stats_manager
    import random
    
    stats = get_stats_manager()
    stats.reset()  # Reset previous data
    
    # Simulate inference for 3 cameras
    print("  Simulating inference for 3 cameras...")
    
    for i in range(50):
        for cam_id in [1, 2, 3]:
            # Simulate different inference times
            if cam_id == 1:
                inference_time = random.uniform(40, 60)  # Fast GPU
            elif cam_id == 2:
                inference_time = random.uniform(45, 70)  # Medium
            else:
                inference_time = random.uniform(200, 300)  # Slow CPU
            
            stats.record_inference(
                camera_id=cam_id,
                inference_time_ms=inference_time,
                model_id=f"model_{cam_id}"
            )
    
    # Print stats
    stats.print_stats()


def demo_optimized_worker():
    """Demo OptimizedCameraWorker"""
    print("\n" + "=" * 60)
    print("🎯 DEMO: OptimizedCameraWorker")
    print("=" * 60)
    
    print("  ⚠️ Worker demo requires YOLO model và video source")
    print("  Xem OPTIMIZATION_GUIDE.md để biết cách sử dụng")
    
    # Example code (không chạy thực)
    example_code = '''
    from coal_monitoring.core import OptimizedCameraWorker, WorkerConfig
    from ultralytics import YOLO
    import threading
    
    # Load model
    model = YOLO("best_segment.pt")
    model_lock = threading.Lock()
    
    # Config
    config = WorkerConfig(
        camera_id=1,
        rtsp_url="rtsp://admin:password@192.168.0.178:554/stream",
        roi_person=[(100, 100), (500, 100), (500, 400), (100, 400)],
        roi_coal=[(200, 300), (600, 300), (600, 500), (200, 500)],
        detection_confidence=0.7,
        target_capture_fps=25,
        detection_interval=0.5,
    )
    
    # Create worker
    worker = OptimizedCameraWorker(
        config=config,
        model=model,
        model_lock=model_lock,
        on_alert=lambda cam, type, active, val: print(f"Alert: {type}={active}"),
        on_log=lambda msg: print(f"Log: {msg}"),
    )
    
    # Start
    worker.start()
    
    # In GUI loop:
    # frame = worker.get_display_frame()
    # result = worker.get_latest_result()
    # worker.update_fps()
    
    # Stop
    worker.stop()
    '''
    
    print("\n  Example code:")
    for line in example_code.strip().split('\n'):
        print(f"    {line}")


def main():
    parser = argparse.ArgumentParser(description="Demo optimized components")
    parser.add_argument(
        "--demo", 
        choices=["source", "stats", "worker", "all"],
        default="all",
        help="Which demo to run"
    )
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("🚀 COAL MONITORING - OPTIMIZED COMPONENTS DEMO")
    print("=" * 60)
    
    if args.demo in ["source", "all"]:
        demo_optimized_video_source()
    
    if args.demo in ["stats", "all"]:
        demo_inference_stats()
    
    if args.demo in ["worker", "all"]:
        demo_optimized_worker()
    
    print("\n✅ Demo completed!")
    print("📚 Xem OPTIMIZATION_GUIDE.md để biết thêm chi tiết")


if __name__ == "__main__":
    main()

