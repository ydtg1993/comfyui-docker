# Dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    COMFYUI_VERSION=master

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    git \
    wget \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    ffmpeg \
    build-essential \
    ca-certificates \
    libfst-dev \
    && rm -rf /var/lib/apt/lists/*

# 设置 python3 为默认
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    python -m pip install --upgrade pip setuptools wheel

# 创建工作目录
WORKDIR /app

# 克隆 ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/comfyui

RUN pip install --no-cache-dir pynini==2.1.6

# 安装 ComfyUI 基础依赖
RUN cd /app/comfyui && \
    pip install --no-cache-dir -r requirements.txt

# 安装 PyTorch（CUDA 12.1 版本）
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 创建 custom_nodes 目录
RUN mkdir -p /app/comfyui/custom_nodes

# 安装 ComfyUI-Manager
RUN cd /app/comfyui/custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install --no-cache-dir -r requirements.txt

# 复制启动脚本
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露 ComfyUI 默认端口
EXPOSE 8188

# 使用非 root 用户运行（可选，提升安全性）
RUN useradd -m -s /bin/bash comfy && \
    chown -R comfy:comfy /app
USER comfy

ENTRYPOINT ["/entrypoint.sh"]