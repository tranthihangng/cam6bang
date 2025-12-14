# Hướng Dẫn Docker - Coal Mine Monitoring System

## 📚 Docker Là Gì?

**Docker** là công nghệ "đóng gói" ứng dụng cùng với tất cả dependencies vào một "container" để chạy được trên bất kỳ máy nào.

### Tại sao cần Docker?

| Vấn đề thường gặp | Docker giải quyết |
|-------------------|-------------------|
| "Máy tôi chạy được, máy bạn không" | Container chạy giống nhau trên mọi máy |
| Cài đặt Python, CUDA, thư viện phức tạp | Tất cả đã cài sẵn trong image |
| Xung đột phiên bản thư viện | Mỗi container có môi trường riêng |
| Deploy lên server mới mất thời gian | Chỉ cần `docker run` là xong |

### Thuật ngữ cơ bản

```
┌─────────────────────────────────────────────────────────────┐
│  Dockerfile  →  Docker Image  →  Docker Container          │
│  (Công thức)    (Bánh đã nướng)   (Bánh đang ăn)            │
└─────────────────────────────────────────────────────────────┘
```

- **Dockerfile**: File text chứa các lệnh để xây dựng image
- **Image**: "Ảnh chụp" hoàn chỉnh của ứng dụng (giống như file .iso)
- **Container**: Instance đang chạy của image (giống như máy ảo nhẹ)
- **Docker Hub**: Kho lưu trữ images online (như GitHub cho code)

---

## 🔧 Cài Đặt Docker

### Windows

1. **Yêu cầu hệ thống:**
   - Windows 10/11 64-bit
   - CPU hỗ trợ virtualization (Hyper-V hoặc WSL2)
   - RAM tối thiểu 8GB

2. **Cài đặt Docker Desktop:**
   ```powershell
   # Tải từ: https://www.docker.com/products/docker-desktop/
   # Hoặc dùng winget:
   winget install Docker.DockerDesktop
   ```

3. **Kích hoạt WSL2 (khuyến nghị):**
   ```powershell
   wsl --install
   wsl --set-default-version 2
   ```

4. **Khởi động lại máy và mở Docker Desktop**

5. **Kiểm tra:**
   ```powershell
   docker --version
   docker run hello-world
   ```

### Linux (Ubuntu/Debian)

```bash
# Cài đặt Docker
curl -fsSL https://get.docker.com | sh

# Thêm user vào group docker (không cần sudo)
sudo usermod -aG docker $USER

# Đăng xuất và đăng nhập lại
# Kiểm tra
docker --version
docker run hello-world
```

---

## 🎮 Cài Đặt NVIDIA Container Toolkit (Cho GPU)

**BẮT BUỘC** vì YOLO cần GPU NVIDIA để chạy nhanh.

### Windows
Docker Desktop tự động hỗ trợ GPU nếu bạn có:
- NVIDIA GPU với driver mới nhất
- WSL2 backend

### Linux
```bash
# Thêm repo
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Cài đặt
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker

# Kiểm tra GPU
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
```

---

## 🚀 Triển Khai Coal Monitoring

### Bước 1: Chuẩn bị thư mục

```powershell
# Tạo cấu trúc thư mục
cd D:\research2025\than_muc\coal_monitoring
mkdir config, models, logs, artifacts
```

### Bước 2: Copy files cần thiết

```powershell
# Copy config
cp system_config.json config/

# Copy YOLO models
cp *.pt models/
# Ví dụ: cp best_segment_26_11.pt models/
```

### Bước 3: Chỉnh sửa config cho Docker

Mở `config/system_config.json` và cập nhật đường dẫn model:

```json
{
    "models": {
        "model_1": {
            "path": "/app/models/best_segment_26_11.pt",  // ← Đường dẫn trong container
            "name": "Model Than & Nguoi",
            "cameras": [1, 2, 3, 4, 5]
        }
    },
    "cameras": [
        {
            "camera_id": "camera_1",
            "rtsp_url": "rtsp://admin:password@192.168.0.179:554/...",  // ← IP camera
            "plc": {
                "ip": "192.168.0.4"  // ← IP PLC
            }
        }
    ]
}
```

### Bước 4: Build Docker Image

```powershell
# Build image (lần đầu mất ~10-15 phút)
docker-compose build

# Hoặc không dùng docker-compose:
docker build -t coal-monitoring .
```

### Bước 5: Chạy Container

```powershell
# Chạy với docker-compose (khuyến nghị)
docker-compose up -d

# Hoặc chạy trực tiếp:
docker run -d --gpus all \
  --name coal-monitoring \
  --network host \
  -v ${PWD}/config:/app/config:ro \
  -v ${PWD}/models:/app/models:ro \
  -v ${PWD}/logs:/app/logs \
  -v ${PWD}/artifacts:/app/artifacts \
  --restart unless-stopped \
  coal-monitoring
```

### Bước 6: Xem logs

```powershell
# Xem logs realtime
docker-compose logs -f

# Hoặc:
docker logs -f coal-monitoring
```

### Bước 7: Dừng container

```powershell
# Dừng
docker-compose down

# Hoặc:
docker stop coal-monitoring
docker rm coal-monitoring
```

---

## 📦 Chuyển Image Sang Máy Khác

### Cách 1: Export/Import Image (Offline)

**Trên máy gốc (có internet):**
```powershell
# Build image
docker-compose build

# Export thành file .tar
docker save coal-monitoring:latest -o coal-monitoring.tar

# Nén lại (giảm ~50% dung lượng)
gzip coal-monitoring.tar
# Tạo ra file: coal-monitoring.tar.gz (~3-5GB)
```

**Copy sang máy mới:**
- Dùng USB, ổ cứng di động, hoặc mạng nội bộ
- Copy file: `coal-monitoring.tar.gz`
- Copy thư mục: `config/`, `models/`

**Trên máy mới:**
```powershell
# Giải nén
gunzip coal-monitoring.tar.gz

# Import image
docker load -i coal-monitoring.tar

# Kiểm tra
docker images
# Sẽ thấy: coal-monitoring:latest

# Chạy
docker-compose up -d
```

### Cách 2: Docker Hub (Online)

**Đăng ký tài khoản Docker Hub:** https://hub.docker.com

```powershell
# Đăng nhập
docker login

# Tag image với username của bạn
docker tag coal-monitoring:latest yourusername/coal-monitoring:latest

# Push lên Docker Hub
docker push yourusername/coal-monitoring:latest
```

**Trên máy mới:**
```powershell
# Pull image
docker pull yourusername/coal-monitoring:latest

# Chạy
docker-compose up -d
```

### Cách 3: Private Registry (Nội bộ)

Nếu công ty có private Docker registry:
```powershell
# Tag với registry URL
docker tag coal-monitoring:latest registry.company.com/coal-monitoring:latest

# Push
docker push registry.company.com/coal-monitoring:latest
```

---

## 🛠️ Các Lệnh Docker Thường Dùng

### Quản lý Container

```powershell
# Xem containers đang chạy
docker ps

# Xem tất cả containers (cả đã dừng)
docker ps -a

# Dừng container
docker stop coal-monitoring

# Khởi động lại
docker restart coal-monitoring

# Xóa container
docker rm coal-monitoring

# Vào shell trong container (debug)
docker exec -it coal-monitoring bash
```

### Quản lý Image

```powershell
# Xem images
docker images

# Xóa image
docker rmi coal-monitoring:latest

# Xóa images không dùng
docker image prune
```

### Xem Logs

```powershell
# Xem logs
docker logs coal-monitoring

# Xem logs realtime
docker logs -f coal-monitoring

# Xem 100 dòng cuối
docker logs --tail 100 coal-monitoring
```

### Kiểm tra Tài nguyên

```powershell
# Xem CPU/RAM usage
docker stats

# Xem chi tiết container
docker inspect coal-monitoring
```

---

## 🔍 Troubleshooting

### 1. Container không start

```powershell
# Xem logs lỗi
docker logs coal-monitoring

# Kiểm tra config file
docker run --rm -v ${PWD}/config:/app/config coal-monitoring cat /app/config/system_config.json
```

### 2. Không thấy GPU

```powershell
# Kiểm tra GPU
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi

# Nếu lỗi: Cài lại nvidia-container-toolkit
```

### 3. Không kết nối được Camera RTSP

```powershell
# Kiểm tra network mode
# Đảm bảo dùng: network_mode: host trong docker-compose.yml

# Test RTSP từ trong container
docker exec -it coal-monitoring python -c "
import cv2
cap = cv2.VideoCapture('rtsp://admin:password@192.168.0.179:554/...')
print('Connected:', cap.isOpened())
"
```

### 4. Không kết nối được PLC

```powershell
# Đảm bảo network_mode: host
# Kiểm tra IP PLC có đúng không
# Kiểm tra firewall

# Test từ container
docker exec -it coal-monitoring ping 192.168.0.4
```

### 5. Out of Memory

```powershell
# Giảm số camera hoặc tăng RAM limit
# Trong docker-compose.yml:
# mem_limit: 8g
```

---

## 📋 Checklist Deploy Máy Mới

- [ ] Cài Docker Desktop / Docker Engine
- [ ] Cài NVIDIA Driver (nếu dùng GPU)
- [ ] Cài nvidia-container-toolkit (nếu dùng GPU)
- [ ] Copy image file `coal-monitoring.tar.gz` hoặc pull từ registry
- [ ] Copy thư mục `config/` với `system_config.json`
- [ ] Copy thư mục `models/` với các file `.pt`
- [ ] Cập nhật đường dẫn model trong config thành `/app/models/...`
- [ ] Cập nhật RTSP URLs và PLC IPs cho môi trường mới
- [ ] Import image: `docker load -i coal-monitoring.tar`
- [ ] Chạy: `docker-compose up -d`
- [ ] Kiểm tra logs: `docker-compose logs -f`

---

## 📞 Liên hệ hỗ trợ

NATECH Technology

