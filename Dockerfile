# S-Recorder Dockerfile
# 基于 Debian 13 (trixie) 的一键部署镜像 / One-click deployment image based on Debian 13 (trixie)
FROM debian:trixie-slim

LABEL maintainer="S-Recorder" \
      description="Automated live stream recorder with yt-dlp and ffmpeg 8.1.2"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=production \
    SRECORDER_DATA_DIR=/app/s-recorder

WORKDIR /app

# 安装系统依赖：ffmpeg 8.1.2（含 ffprobe）、Python、Node.js、构建工具 / Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        python3 \
        python3-pip \
        nodejs \
        npm \
        ca-certificates \
        curl \
        wget \
        git \
        procps \
        rclone \
    && rm -rf /var/lib/apt/lists/*

# 确保 ffmpeg/ffprobe 在 /usr/local/bin/ 可用 / Symlink to /usr/local/bin
RUN ln -sf $(which ffmpeg) /usr/local/bin/ffmpeg && \
    ln -sf $(which ffprobe) /usr/local/bin/ffprobe && \
    ffmpeg -version | head -1

# 安装最新版 yt-dlp 到 /usr/local/bin/yt-dlp / Install latest yt-dlp
RUN pip install --no-cache-dir -U yt-dlp --break-system-packages && \
    ln -sf $(which yt-dlp) /usr/local/bin/yt-dlp && \
    yt-dlp --version

# 复制后处理模块 / Copy post-processing modules
COPY modules /app/s-recorder/modules.default
RUN chmod +x /app/s-recorder/modules.default/*

# 复制并构建前端 / Copy and build frontend
COPY frontend /app/frontend
WORKDIR /app/frontend
RUN npm install && npm run build

# 安装后端 Python 依赖 / Install backend Python dependencies
WORKDIR /app/backend
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

# 复制后端源码 / Copy backend source
COPY backend /app/backend

# 创建数据目录 / Create data directory
RUN mkdir -p /app/s-recorder/recordings /app/s-recorder/config /app/s-recorder/modules

# 暴露端口 / Expose port
EXPOSE 24136

# 健康检查 / Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -fs http://localhost:24136/api/settings >/dev/null 2>&1 || exit 1

# 启动命令 / Start command
WORKDIR /app/backend
CMD ["python3", "run.py"]
