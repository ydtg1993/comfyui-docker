#!/bin/bash
set -e

echo "=== ComfyUI Docker 自动化部署 ==="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "请先安装 Docker。"
    exit 1
fi

# 检查 NVIDIA Docker
if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "警告：GPU 环境可能未正确配置，请安装 NVIDIA Container Toolkit。"
    # 不强制退出，允许在没有 GPU 的情况下尝试启动（CPU 模式）
fi

# 创建必要的宿主机目录
mkdir -p models/checkpoints models/vae models/loras models/controlnet models/clip models/embeddings models/upscale_models output custom_nodes

# 构建镜像
echo "构建 Docker 镜像..."
docker compose build

# 启动服务
echo "启动 ComfyUI 容器..."
docker compose up -d

echo "ComfyUI 已启动，访问 http://localhost:8188"