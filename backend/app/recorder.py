"""录制引擎 / Recording engine."""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List
import shutil

from .events import emitter
from .state import AppState
from .settings import Settings
from .streamers import build_url, get_stream_url


def parse_duration_to_seconds(duration: str) -> int:
    """将 00:00:00 格式转换为秒数."""
    duration = duration.strip()
    if not re.match(r"^\d{1,2}:\d{2}:\d{2}$", duration):
        return 0
    parts = duration.split(":")
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except ValueError:
        return 0


def format_size(size_bytes: int) -> str:
    """人类可读的文件大小."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ["KiB", "MiB", "GiB", "TiB"]:
        size_bytes /= 1024.0
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
    return f"{size_bytes:.2f} PiB"


def run_ffmpeg(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.Popen:
    """启动 ffmpeg 进程."""
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=cwd,
        text=True,
    )


def get_video_duration(path: Path) -> Optional[float]:
    """使用 ffprobe 获取视频时长."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            return float(proc.stdout.strip())
    except Exception:
        pass
    return None


def write_video_meta(path: Path, meta: Dict) -> None:
    """写入与视频同名的 .json 元数据文件."""
    meta_path = path.with_suffix(path.suffix + ".json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_video_meta(path: Path) -> Optional[Dict]:
    """读取视频元数据."""
    meta_path = path.with_suffix(path.suffix + ".json")
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def set_video_status(path: Path, status: str) -> None:
    meta = read_video_meta(path) or {}
    meta["status"] = status
    write_video_meta(path, meta)


class RecordingSession:
    """单个录制会话."""

    def __init__(self, username: str, session_dir: Path, settings: Settings):
        self.username = username
        self.session_dir = session_dir
        self.settings = settings
        self.started_at = datetime.now(timezone.utc)
        self.process: Optional[subprocess.Popen] = None
        self.stopped = False
        self.lock = threading.Lock()
        self.target_path: Path = session_dir.parent / f"{session_dir.name}.{settings.merge_format}"

    def _build_ffmpeg_cmd(self, stream_url: str) -> List[str]:
        slice_secs = parse_duration_to_seconds(self.settings.slice_duration)
        base = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-stats",
            "-i", stream_url,
            "-c", "copy",
        ]
        if slice_secs > 0:
            # 按时间段切片 / segment by time
            pattern = str(self.session_dir / "seg_%03d.ts")
            return base + [
                "-f", "segment",
                "-segment_time", str(slice_secs),
                "-reset_timestamps", "1",
                "-segment_format", "mpegts",
                pattern,
            ]
        else:
            # 直接输出到目标文件
            return base + [str(self.target_path)]

    def start(self, stream_url: str) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        # 预创建 meta 文件
        write_video_meta(self.target_path, {
            "status": "recording",
            "started_at": self.started_at.isoformat(),
            "size_bytes": 0,
            "video_duration_secs": None,
        })
        cmd = self._build_ffmpeg_cmd(stream_url)
        self.process = run_ffmpeg(cmd)
        emitter.emit("recording-started", {
            "username": self.username,
            "session_dir": str(self.session_dir),
            "target_path": str(self.target_path),
        })

    def stop(self) -> None:
        with self.lock:
            self.stopped = True
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


class RecorderManager:
    """录制管理器."""

    def __init__(self, state: AppState):
        self.state = state
        self.sessions: Dict[str, RecordingSession] = {}
        self.lock = threading.Lock()

    def is_recording(self, username: str) -> bool:
        with self.lock:
            sess = self.sessions.get(username)
            return sess is not None and sess.is_running()

    def active_count(self) -> int:
        with self.lock:
            return sum(1 for s in self.sessions.values() if s.is_running())

    def is_file_locked(self, path: Path) -> bool:
        """判断路径是否被活跃录制会话锁定."""
        with self.lock:
            for s in self.sessions.values():
                if not s.is_running():
                    continue
                if path == s.target_path or path.is_relative_to(s.session_dir):
                    return True
        return False

    def get_active_sessions(self) -> List[Dict]:
        with self.lock:
            return [
                {
                    "username": s.username,
                    "session_dir": str(s.session_dir),
                    "started_at": s.started_at.isoformat(),
                    "target_path": str(s.target_path),
                }
                for s in self.sessions.values()
                if s.is_running()
            ]

    def start_recording(self, username: str, playlist_url: Optional[str] = None) -> str:
        username = username.lower().strip()
        with self.lock:
            if username in self.sessions and self.sessions[username].is_running():
                raise ValueError(f"主播 {username} 正在录制中")

        settings = self.state.settings
        if settings.max_concurrent > 0 and self.active_count() >= settings.max_concurrent:
            raise ValueError("已达到最大并发录制数")

        # 获取直播流地址
        if not playlist_url:
            url = build_url(username)
            playlist_url = get_stream_url(url)
        if not playlist_url:
            raise ValueError(f"无法获取 {username} 的直播流地址，可能未开播")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = Path(settings.output_dir) / username / f"{username}_{timestamp}"
        session = RecordingSession(username, session_dir, settings)
        session.start(playlist_url)

        with self.lock:
            self.sessions[username] = session

        # 启动监控线程，录制结束后自动合并与后处理
        threading.Thread(target=self._recording_watcher, args=(session,), daemon=True).start()
        return str(session.session_dir)

    def stop_recording(self, username: str) -> None:
        username = username.lower().strip()
        with self.lock:
            sess = self.sessions.get(username)
            if not sess:
                raise ValueError(f"主播 {username} 未在录制")
            sess.stop()

    def _recording_watcher(self, session: RecordingSession) -> None:
        """监控录制进程，结束后合并并触发后处理."""
        while session.is_running():
            time.sleep(1)

        record_duration = (datetime.now(timezone.utc) - session.started_at).total_seconds()
        with self.lock:
            self.sessions.pop(session.username, None)

        emitter.emit("recording-stopped", {
            "username": session.username,
            "session_dir": str(session.session_dir),
            "target_path": str(session.target_path),
            "record_duration_secs": int(record_duration),
        })

        # 合并片段
        self._merge_session(session)

    def _merge_session(self, session: RecordingSession) -> None:
        """合并录制会话目录中的片段."""
        target = session.target_path
        if not session.session_dir.exists():
            set_video_status(target, "error")
            return

        segments = sorted(session.session_dir.glob("seg_*.ts"))
        if not segments:
            # 无切片模式已直接输出 target
            if target.exists():
                duration = get_video_duration(target)
                meta = read_video_meta(target) or {}
                meta.update({
                    "status": "finish",
                    "size_bytes": target.stat().st_size,
                    "video_duration_secs": duration,
                })
                write_video_meta(target, meta)
                self._trigger_postprocess(target)
            else:
                # 没有输出，删除 meta
                meta_path = target.with_suffix(target.suffix + ".json")
                if meta_path.exists():
                    meta_path.unlink()
                if session.session_dir.exists():
                    shutil.rmtree(session.session_dir, ignore_errors=True)
            return

        # 有切片，合并为最终文件
        concat_file = session.session_dir / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"file '{seg.resolve()}'\n")

        emitter.emit("recording-merging", {
            "username": session.username,
            "session_dir": str(session.session_dir),
            "target_path": str(target),
        })
        set_video_status(target, "merging")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(target),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if proc.returncode != 0 or not target.exists():
                set_video_status(target, "error")
                return
            duration = get_video_duration(target)
            meta = read_video_meta(target) or {}
            meta.update({
                "status": "finish",
                "size_bytes": target.stat().st_size,
                "video_duration_secs": duration,
            })
            write_video_meta(target, meta)
            # 清理临时切片
            shutil.rmtree(session.session_dir, ignore_errors=True)
            self._trigger_postprocess(target)
        except Exception:
            set_video_status(target, "error")

    def _trigger_postprocess(self, video_path: Path) -> None:
        """触发后处理流水线."""
        from .postprocess import run_postprocess_for_path
        pipeline = self.state.pipeline
        if pipeline.nodes:
            run_postprocess_for_path(video_path, pipeline, self.state)
        else:
            set_video_status(video_path, "finish")
