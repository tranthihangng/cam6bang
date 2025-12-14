"""
Test VRAM peak usage khi 2 models chạy song song liên tục
"""
import threading
import time
import cv2
import numpy as np

# Đường dẫn models
MODEL_1_PATH = r"D:\research2025\than_muc\best_segment_26_11.pt"
MODEL_2_PATH = r"D:\research2025\than_muc\best_segment_27_11_copy.pt"

def get_gpu_memory():
    """Lấy VRAM usage từ nvidia-smi"""
    import subprocess
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
        capture_output=True, text=True
    )
    return int(result.stdout.strip())

def predict_loop(model, model_name, frame, stop_event, results):
    """Loop predict liên tục"""
    count = 0
    start = time.time()
    
    while not stop_event.is_set():
        _ = model.predict(frame, conf=0.7, verbose=False, task='segment')
        count += 1
        
        if count % 10 == 0:
            elapsed = time.time() - start
            fps = count / elapsed
            print(f"  {model_name}: {count} inferences, {fps:.1f} FPS")
    
    results[model_name] = count

def main():
    print("=" * 60)
    print("  TEST VRAM PEAK - 2 MODELS SONG SONG")
    print("=" * 60)
    
    # Kiem tra VRAM ban dau
    initial_vram = get_gpu_memory()
    print(f"\n[0] VRAM ban dau: {initial_vram} MB")
    
    # Import va load models
    print("\n[1] Loading models...")
    from ultralytics import YOLO
    
    model1 = YOLO(MODEL_1_PATH)
    vram_after_model1 = get_gpu_memory()
    print(f"    Sau load Model 1: {vram_after_model1} MB (+{vram_after_model1 - initial_vram} MB)")
    
    model2 = YOLO(MODEL_2_PATH)
    vram_after_model2 = get_gpu_memory()
    print(f"    Sau load Model 2: {vram_after_model2} MB (+{vram_after_model2 - vram_after_model1} MB)")
    
    # Tao fake frame (1920x1080)
    print("\n[2] Tao test frame 1920x1080...")
    frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    
    # Warmup
    print("\n[3] Warmup (1 inference mỗi model)...")
    _ = model1.predict(frame, conf=0.7, verbose=False, task='segment')
    _ = model2.predict(frame, conf=0.7, verbose=False, task='segment')
    vram_after_warmup = get_gpu_memory()
    print(f"    Sau warmup: {vram_after_warmup} MB")
    
    # Chay song song
    print("\n[4] Chay 2 models SONG SONG trong 10 giay...")
    print("    (Ctrl+C de dung som)\n")
    
    stop_event = threading.Event()
    results = {}
    
    thread1 = threading.Thread(
        target=predict_loop, 
        args=(model1, "Model 1", frame, stop_event, results)
    )
    thread2 = threading.Thread(
        target=predict_loop, 
        args=(model2, "Model 2", frame, stop_event, results)
    )
    
    # Bat dau
    thread1.start()
    thread2.start()
    
    # Monitor VRAM trong 10 giay
    peak_vram = vram_after_warmup
    try:
        for i in range(20):  # 10 giay (20 x 0.5s)
            time.sleep(0.5)
            current_vram = get_gpu_memory()
            if current_vram > peak_vram:
                peak_vram = current_vram
            print(f"  [VRAM] Current: {current_vram} MB | Peak: {peak_vram} MB")
    except KeyboardInterrupt:
        print("\n  Dung boi user...")
    
    # Dung threads
    stop_event.set()
    thread1.join()
    thread2.join()
    
    # Ket qua
    final_vram = get_gpu_memory()
    
    print("\n" + "=" * 60)
    print("  KET QUA TEST VRAM")
    print("=" * 60)
    print(f"""
    VRAM USAGE:
    -------------------------------------------
    Ban dau (truoc load):         {initial_vram:6} MB
    Sau load Model 1:             {vram_after_model1:6} MB (+{vram_after_model1-initial_vram} MB)
    Sau load Model 2:             {vram_after_model2:6} MB (+{vram_after_model2-vram_after_model1} MB)
    Sau warmup:                   {vram_after_warmup:6} MB
    -------------------------------------------
    PEAK (2 models song song):    {peak_vram:6} MB
    Final:                        {final_vram:6} MB
    -------------------------------------------
    TONG VRAM CAN:                {peak_vram:6} MB
    % cua 8GB:                    {peak_vram/8192*100:6.1f} %
    """)

if __name__ == "__main__":
    main()

