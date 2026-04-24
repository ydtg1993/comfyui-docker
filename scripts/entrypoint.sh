#!/bin/bash
set -e

# 确保模型目录存在
mkdir -p /app/comfyui/models/checkpoints
mkdir -p /app/comfyui/models/vae
mkdir -p /app/comfyui/models/loras
mkdir -p /app/comfyui/models/controlnet
mkdir -p /app/comfyui/models/clip
# 依此类推...

# 如果 CHECKPOINT_URL 环境变量被设置，自动下载主模型
if [ -n "$CHECKPOINT_URL" ] && [ ! -f "/app/comfyui/models/checkpoints/model.safetensors" ]; then
    echo "Downloading checkpoint from $CHECKPOINT_URL"
    wget -O /app/comfyui/models/checkpoints/model.safetensors "$CHECKPOINT_URL" || true
fi

# 自定义节点集成逻辑
NODE_DIR="/app/comfyui/custom_nodes/ComfyUI-Index-TTS"
if [ ! -d "$NODE_DIR" ]; then
    echo "🔥 首次启动，正在安装 ComfyUI-Index-TTS 插件..."
    git clone https://github.com/chenpipi0807/ComfyUI-Index-TTS.git "$NODE_DIR"
    cd "$NODE_DIR"
    pip install --no-cache-dir -r requirements.txt
    pip install --no-cache-dir pynini==2.1.5
    echo "✅ 插件安装完成。"
else
    echo "✅ 检测到 ComfyUI-Index-TTS 插件已安装。"
fi

# 启动 ComfyUI，绑定 0.0.0.0，允许外部访问
cd /app/comfyui
exec python main.py --listen 0.0.0.0 --port 8188