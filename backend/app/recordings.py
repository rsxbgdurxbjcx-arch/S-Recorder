"""录制文件管理 / Recording file management."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from .state import AppState
from .recorder import read_video_meta, format_size


def parse_timestamp_from_stem(stem: str) -> Optional[str]:
    """从文件名 stem 解析时间戳，格式 {name}_{YYYYMMDD}_{HHMMSS}."""
    parts = stem.rsplit("_", 2)
    if len(parts) < 3:
        return None
    date_str, time_str = parts[-2], parts[-1]
    if len(date_str) == 8 and date_str.isdigit() and len(time_str) == 6 and time_str.isdigit():
        try:
            dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
            return dt.isoformat()
        except ValueError:
            return None
    return None


def list_recordings(state: AppState, recorder) -> List[Dict[str, Any]]:
    """列出所有录制文件."""
    output_dir = Path(state.settings.output_dir)
    if not output_dir.exists():
        return []

    active_targets = {s["target_path"] for s in recorder.get_active_sessions()}
    files = []

    for user_dir in output_dir.iterdir():
        if not user_dir.is_dir() or user_dir.name.startswith("."):
            continue
        for video_path in user_dir.iterdir():
            if video_path.is_file() and video_path.suffix in (".mp4", ".mkv", ".ts", ".mov"):
                meta = read_video_meta(video_path)
                if not meta:
                    # 没有 meta 的老文件，尝试从文件名解析
                    started_at = parse_timestamp_from_stem(video_path.stem) or datetime.fromtimestamp(video_path.stat().st_mtime).isoformat()
                    meta = {
                        "status": "finish",
                        "started_at": started_at,
                        "size_bytes": video_path.stat().st_size,
                        "video_duration_secs": None,
                        "pp_results": None,
                        "module_outputs": None,
                    }
                is_recording = str(video_path) in active_targets
                record_duration = None
                if is_recording:
                    # 查找活跃会话的开始时间
                    for s in recorder.get_active_sessions():
                        if s["target_path"] == str(video_path):
                            started = datetime.fromisoformat(s["started_at"])
                            record_duration = int((datetime.now() - started).total_seconds())
                            break
                files.append({
                    "name": video_path.name,
                    "path": str(video_path),
                    "size_bytes": video_path.stat().st_size if not is_recording else meta.get("size_bytes", 0),
                    "started_at": meta.get("started_at", ""),
                    "is_recording": is_recording,
                    "record_duration_secs": record_duration,
                    "video_duration_secs": meta.get("video_duration_secs"),
                    "status": "recording" if is_recording else meta.get("status", "finish"),
                    "pp_results": meta.get("pp_results"),
                    "module_outputs": meta.get("module_outputs"),
                })

    files.sort(key=lambda x: x["started_at"], reverse=True)
    return files


def delete_recording(path: str, state: AppState, recorder) -> None:
    """删除单个录制文件及相关元数据、预览图."""
    p = Path(path)
    if recorder.is_file_locked(p):
        raise ValueError("录制中，无法删除")
    # 取消后处理
    state.pp_task_cancel(path)
    state.pp_task_remove(path)

    if p.is_file():
        p.unlink(missing_ok=True)
        # 删除 meta
        meta_path = p.with_suffix(p.suffix + ".json")
        if meta_path.exists():
            meta_path.unlink()
        # 删除 sidecar 图片
        for ext in ["webp", "jpg", "jpeg", "png"]:
            sidecar = p.with_suffix(f".{ext}")
            if sidecar.exists():
                sidecar.unlink()
    elif p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    state.remove_pp_result(path)
