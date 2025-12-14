# =============================================================
# Coal Mine Monitoring System - Docker Image
# =============================================================
# Hỗ trợ GPU NVIDIA CUDA cho YOLO detection
# 
# Build:
#   docker build -t coal-monitoring .
#
# Run với GPU:
#   docker run --gpus all -v $(pwd)/config:/app/config coal-monitoring
# =============================================================

# Base image với CUDA support cho GPU (YOLO cần GPU để chạy nhanh)
FROM nvidia/cuda:11.8-cudnn8-runtime-ubuntu22.04

# Metadata
LABEL maintainer="NATECH Technology"
LABEL description="Coal Mine Monitoring System with YOLO Detection"
LABEL version="1.0"

# Tránh interactive prompts khi cài đặt
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Ho_Chi_Minh

# Python environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ============================================
# 1. Cài đặt system dependencies
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python
    python3.10 \
    python3-pip \
    python3.10-dev \
    # OpenCV dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Video codecs
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    # Snap7 dependencies (PLC communication)
    build-essential \
    # Network tools (useful for debugging)
    iputils-ping \
    curl \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Symlink python3 to python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

# ============================================
# 2. Cài đặt Python dependencies
# ============================================
WORKDIR /app

# Copy requirements first (tận dụng Docker cache)
COPY requirements.txt .

# Upgrade pip và cài đặt dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# 3. Copy source code
# ============================================
COPY . .

# ============================================
# 4. Tạo thư mục cho logs và artifacts
# ============================================
RUN mkdir -p /app/logs /app/artifacts /app/config

# ============================================
# 5. Volume mounts (có thể mount từ bên ngoài)
# ============================================
# - /app/config: Chứa system_config.json
# - /app/logs: Chứa log files
# - /app/artifacts: Chứa ảnh cảnh báo
# - /app/models: Chứa YOLO models (.pt files)
VOLUME ["/app/config", "/app/logs", "/app/artifacts", "/app/models"]

# ============================================
# 6. Expose port (nếu cần web dashboard sau này)
# ============================================
EXPOSE 8080

# ============================================
# 7. Health check
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import coal_monitoring; print('OK')" || exit 1

# ============================================
# 8. Entry point - Chạy ở chế độ headless
# ============================================
ENTRYPOINT ["python", "main.py"]
CMD ["--config", "/app/config/system_config.json", "--headless"]

