# S-Recorder

S-Recorder 是一个基于 Docker 一键部署的自动化直播录制工具，支持通过 `yt-dlp` 解析直播流并使用 `ffmpeg` 进行录制、切片与合并。

## 主要特性

- **平台无限制**：支持 `yt-dlp` 所能解析的所有直播平台，并针对 Chaturbate、Stripchat、BongaCams 进行优化支持。
- **最高画质**：默认并强制录制最佳画质（Best Quality）。
- **视频切片**：支持按 `00:00:00` 格式设置切片时长，录制结束后自动合并。
- **后处理流水线**：内置 Rclone 上传模块，可按主播名自动分类云盘目录。
- **精美 Web UI**：纯白默认主题，支持自定义主题色，底部四菜单导航，完美适配移动端浏览器。
- **Docker 一键部署**：基于 Debian 13 (trixie) 构建，内置 yt-dlp 与 ffmpeg 8.1.2。

## 技术栈

- 后端：Python 3 + FastAPI + Uvicorn
- 前端：Vue 3 + Vite + Tailwind CSS
- 录制核心：yt-dlp（解析）+ ffmpeg 8.1.2（录制/切片/合并）
- 容器：Debian 13 (trixie) + Docker / docker-compose

## 快速开始

### 1. 克隆或解压项目

```bash
unzip S-Recorder.zip -d /opt
cd /opt/S-Recorder
```

### 2. 使用 Docker Compose 启动

```bash
docker compose up -d --build
```

### 3. 访问 Web UI

打开浏览器访问：http://localhost:24136

默认端口为 `24136`，可在 `docker-compose.yml` 中修改映射。

## 目录说明

```
S-Recorder/
├── backend/              # FastAPI 后端源码
├── frontend/             # Vue 3 前端源码
├── modules/              # 后处理模块（默认包含 rclone_upload）
├── Dockerfile            # Docker 镜像构建文件
├── docker-compose.yml    # Docker Compose 配置
├── README.md             # 本说明文件
└── LICENSE               # 许可证
```

## 配置说明

### 数据持久化

`docker-compose.yml` 默认挂载以下目录到容器：

- `./data/config` → `/app/s-recorder/config`（配置、主播列表、流水线）
- `./data/recordings` → `/app/s-recorder/recordings`（录制文件）
- `./modules` → `/app/s-recorder/modules`（后处理模块）

### 常用设置

在 **设置** 页面可配置：

- 录制输出目录
- 轮询间隔
- 视频切片时长（`00:00:00` 表示不切片）
- 合并格式（mp4/mkv/mov）
- 最大并发录制数
- 默认自动录制
- 主题色

## 添加主播

在 **主播列表** 页面点击“添加主播”，支持：

- 仅输入主播 ID，例如：`Only_KiraRi`
- 输入完整直播间链接，例如：`https://stripchat.com/Only_KiraRi`
- 批量输入，使用英文逗号分隔，例如：`Only_KiraRi,Jap_amelle,youngmin_09`

## 后处理流水线

在 **后处理** 页面：

1. 查看可用模块（默认已包含 Rclone 上传模块）
2. 选择模块并点击“添加”
3. 填写模块参数（如远程名称、目标目录等）
4. 点击“保存”

录制完成后，系统会自动按流水线顺序执行后处理任务。

## 关于 ffmpeg 8.1.2

本项目 Dockerfile 基于 Debian 13 (trixie) 官方软件源安装 `ffmpeg`。截至当前版本，Debian trixie 官方仓库提供 `ffmpeg 8.1.2`，因此可直接通过 `apt-get install ffmpeg` 完成内置，无需手动下载静态编译包。镜像构建时会自动将 `ffmpeg` 与 `ffprobe` 软链接到 `/usr/local/bin/`，确保全局可调用。

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 免责声明

本工具仅供个人合法录制与归档使用。请遵守所在国家/地区的法律法规以及各直播平台的服务条款，不得用于侵犯他人隐私、版权或其他非法用途。
