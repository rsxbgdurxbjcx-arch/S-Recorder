"""应用全局状态与持久化 / Application global state and persistence."""
from __future__ import annotations

import os
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .settings import AppData, Settings, StreamerData, PipelineConfig, PipelineNode


class AppState:
    """全局状态，负责配置加载、保存与线程安全访问."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.environ.get("SRECORDER_DATA_DIR", "/app/s-recorder")
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._data = self._load()
        # 后处理任务状态（内存中）/ pp task status in memory
        self.pp_tasks: Dict[str, Dict[str, Any]] = {}
        self.pp_cancel_flags: Dict[str, bool] = {}
        self.pp_lock = threading.Lock()

    def _file_path(self, name: str) -> Path:
        return self.config_dir / name

    def _load(self) -> AppData:
        files = {
            "settings.json": "settings",
            "streamers.json": "streamers",
            "pipeline.json": "pipeline",
            "pp_results.json": "pp_results",
        }
        raw: Dict[str, Any] = {}
        for fname, key in files.items():
            path = self._file_path(fname)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw[key] = json.load(f)
                except Exception:
                    raw[key] = None
        # 兼容旧格式
        data = AppData()
        if raw.get("settings"):
            data.settings = Settings.from_dict(raw["settings"])
        if raw.get("streamers"):
            data.streamers = [StreamerData(**s) for s in raw["streamers"]]
        if raw.get("pipeline"):
            pl = raw["pipeline"]
            nodes = [PipelineNode(**n) for n in pl.get("nodes", [])]
            data.pipeline = PipelineConfig(nodes=nodes)
        if raw.get("pp_results"):
            pp = raw["pp_results"]
            if isinstance(pp, list):
                data.pp_results = pp
            elif isinstance(pp, dict):
                data.pp_results = list(pp.keys())
        # 确保输出目录存在
        Path(data.settings.output_dir).mkdir(parents=True, exist_ok=True)
        return data

    def save(self) -> None:
        with self.lock:
            self._file_path("settings.json").write_text(
                json.dumps(self._data.settings.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._file_path("streamers.json").write_text(
                json.dumps([{"username": s.username, "auto_record": s.auto_record, "added_at": s.added_at} for s in self._data.streamers], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._file_path("pipeline.json").write_text(
                json.dumps({"nodes": [{"nodeId": n.nodeId, "moduleId": n.moduleId, "params": n.params, "enabled": n.enabled} for n in self._data.pipeline.nodes]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._file_path("pp_results.json").write_text(
                json.dumps(self._data.pp_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    @property
    def settings(self) -> Settings:
        with self.lock:
            return self._data.settings

    def update_settings(self, settings: Settings) -> None:
        with self.lock:
            Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
            self._data.settings = settings
            self.save()

    @property
    def streamers(self) -> List[StreamerData]:
        with self.lock:
            return list(self._data.streamers)

    def add_streamer(self, username: str) -> None:
        username = username.strip().lower()
        if not username:
            raise ValueError("用户名不能为空")
        with self.lock:
            if any(s.username == username for s in self._data.streamers):
                raise ValueError(f"主播 {username} 已存在")
            self._data.streamers.append(StreamerData(
                username=username,
                auto_record=self._data.settings.auto_record,
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
            self.save()

    def remove_streamer(self, username: str) -> None:
        with self.lock:
            self._data.streamers = [s for s in self._data.streamers if s.username != username]
            self.save()

    def set_auto_record(self, username: str, enabled: bool) -> None:
        with self.lock:
            for s in self._data.streamers:
                if s.username == username:
                    s.auto_record = enabled
                    break
            self.save()

    @property
    def pipeline(self) -> PipelineConfig:
        with self.lock:
            return self._data.pipeline

    def update_pipeline(self, pipeline: PipelineConfig) -> None:
        with self.lock:
            self._data.pipeline = pipeline
            self.save()

    def pp_task_enqueue(self, path: str) -> None:
        self.pp_tasks[path] = {"status": "waiting", "pct": 0.0}

    def pp_task_start(self, path: str, total: int) -> None:
        self.pp_tasks[path] = {"status": "running", "pct": 0.0, "total": total, "done": 0}

    def pp_task_progress(self, path: str, pct: float, done: int, total: int, module_name: str) -> None:
        if path in self.pp_tasks:
            self.pp_tasks[path].update({"pct": pct, "done": done, "total": total, "module_name": module_name})

    def pp_task_finish(self, path: str, success: bool) -> None:
        if path in self.pp_tasks:
            self.pp_tasks[path]["status"] = "done" if success else "error"
            self.pp_tasks[path]["pct"] = 100.0

    def pp_task_remove(self, path: str) -> None:
        self.pp_tasks.pop(path, None)

    def pp_task_cancel(self, path: str) -> None:
        self.pp_cancel_flags[path] = True

    def pp_task_clear_cancel(self, path: str) -> None:
        self.pp_cancel_flags.pop(path, None)

    def is_pp_cancelled(self, path: str) -> bool:
        return self.pp_cancel_flags.get(path, False)

    def add_pp_result(self, path: str) -> None:
        with self.lock:
            if path not in self._data.pp_results:
                self._data.pp_results.append(path)
                self.save()

    def remove_pp_result(self, path: str) -> None:
        with self.lock:
            if path in self._data.pp_results:
                self._data.pp_results.remove(path)
                self.save()
