"""主播 URL 解析与状态监控 / Streamer URL parsing and status monitoring."""
from __future__ import annotations

import re
import subprocess
import json
import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict, List
from urllib.parse import urlparse

from .events import emitter
from .state import AppState


KNOWN_DOMAINS = {
    "chaturbate.com": "chaturbate",
    "stripchat.com": "stripchat",
    "stripchat.global": "stripchat",
    "bongacams.com": "bongacams",
    "bongacams.xxx": "bongacams",
}


@dataclass
class StreamStatus:
    username: str
    is_online: bool = False
    is_recordable: bool = False
    viewers: int = 0
    status: str = "未知"
    thumbnail_url: Optional[str] = None
    playlist_url: Optional[str] = None
    title: Optional[str] = None


def extract_username(text: str) -> Optional[str]:
    """从主播ID或完整URL中提取主播名."""
    text = text.strip()
    if not text:
        return None
    # 如果是URL，解析路径
    if re.match(r"^https?://", text, re.IGNORECASE):
        parsed = urlparse(text)
        path = parsed.path.strip("/")
        # 常见模式 /modelname/ 或 /modelname
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[-1].lower()
        return None
    # 否则当作ID
    return text.lower()


def guess_platform(url_or_id: str) -> Optional[str]:
    """根据URL猜测平台."""
    text = url_or_id.strip().lower()
    if not text.startswith("http"):
        return None
    parsed = urlparse(text)
    domain = parsed.netloc.replace("www.", "")
    return KNOWN_DOMAINS.get(domain)


def build_url(username: str, platform: Optional[str] = None) -> str:
    """根据用户名和平台构建直播间URL."""
    if platform == "chaturbate":
        return f"https://chaturbate.com/{username}/"
    if platform == "bongacams":
        return f"https://bongacams.com/{username}"
    # default stripchat
    return f"https://stripchat.com/{username}"


def parse_streamer_input(text: str) -> List[Dict[str, str]]:
    """解析用户输入：支持ID、URL、批量逗号分隔."""
    results = []
    seen = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        username = extract_username(part)
        if not username:
            continue
        if username in seen:
            continue
        seen.add(username)
        platform = guess_platform(part)
        results.append({"username": username, "platform": platform})
    return results


def run_ytdlp_info(url: str, timeout: int = 30) -> Optional[Dict]:
    """调用 yt-dlp 获取直播间信息."""
    try:
        proc = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-warnings", "--quiet", url],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        # 可能多行，取第一行有效JSON
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                return json.loads(line)
        return None
    except Exception:
        return None


def get_stream_url(url: str, timeout: int = 30) -> Optional[str]:
    """使用 yt-dlp 获取最佳直播流地址."""
    try:
        proc = subprocess.run(
            ["yt-dlp", "-g", "-f", "best", "--no-warnings", "--quiet", url],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                return line
        return None
    except Exception:
        return None


def fetch_status(username: str, platform: Optional[str] = None) -> StreamStatus:
    """获取单个主播状态."""
    url = build_url(username, platform)
    info = run_ytdlp_info(url)
    status = StreamStatus(username=username)
    if not info:
        status.status = "离线"
        return status
    # 判断直播状态
    is_live = info.get("is_live") or info.get("live_status") == "is_live"
    if not is_live:
        # 有些平台is_live字段不标准，通过formats判断
        formats = info.get("formats", [])
        if formats and any(f.get("url") for f in formats):
            is_live = True
    status.is_online = bool(is_live)
    status.is_recordable = bool(is_live)
    status.viewers = info.get("concurrent_viewers") or info.get("view_count") or 0
    status.status = "直播中" if is_live else "离线"
    status.title = info.get("title")
    status.thumbnail_url = info.get("thumbnail")
    if is_live:
        status.playlist_url = get_stream_url(url)
    return status


class StatusMonitor:
    """主播状态监控器，周期性轮询."""

    def __init__(self, state: AppState):
        self.state = state
        self.statuses: Dict[str, StreamStatus] = {}
        self.lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def get_status(self, username: str) -> Optional[StreamStatus]:
        with self.lock:
            return self.statuses.get(username)

    def get_cached_playlist_url(self, username: str) -> Optional[str]:
        with self.lock:
            s = self.statuses.get(username)
            return s.playlist_url if s else None

    def poll_one(self, username: str, platform: Optional[str] = None) -> StreamStatus:
        status = fetch_status(username, platform)
        with self.lock:
            self.statuses[username] = status
        emitter.emit("streamer-status", {"username": username, "status": {
            "is_online": status.is_online,
            "is_recordable": status.is_recordable,
            "viewers": status.viewers,
            "status": status.status,
            "thumbnail_url": status.thumbnail_url,
        }})
        return status

    def poll_all(self) -> None:
        for s in self.state.streamers:
            try:
                self.poll_one(s.username)
            except Exception:
                pass
            if self._stop_event.is_set():
                break

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()

        def loop():
            while not self._stop_event.is_set():
                self.poll_all()
                # 动态读取轮询间隔
                interval = self.state.settings.poll_interval_secs
                self._stop_event.wait(interval)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
