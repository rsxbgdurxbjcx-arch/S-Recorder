"""应用配置与全局状态模型 / Application settings and global state models."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import json


@dataclass
class PipelineNode:
    """后处理流水线节点 / Post-processing pipeline node."""
    nodeId: str
    moduleId: str
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class PipelineConfig:
    """后处理流水线配置 / Post-processing pipeline config."""
    nodes: List[PipelineNode] = field(default_factory=list)


@dataclass
class Settings:
    """用户可配置的录制器设置 / User-configurable recorder settings."""
    output_dir: str = "/app/s-recorder/recordings"
    poll_interval_secs: int = 30
    auto_record: bool = True
    max_concurrent: int = 0
    merge_format: str = "mp4"
    max_tmp_dir_gb: float = 50.0
    language: str = "zh-CN"
    server_port: int = 24136
    setup_done: bool = False
    # 新增：视频切片时长（严格 00:00:00 格式）/ New: video slice duration in HH:MM:SS
    slice_duration: str = "00:00:00"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        defaults = {f.name: f.default for f in cls.__dataclass_fields__.values()}
        defaults.update(data)
        return cls(**defaults)


@dataclass
class StreamerData:
    """单个主播的持久化数据 / Persisted data for a single streamer."""
    username: str
    auto_record: bool
    added_at: str


@dataclass
class AppData:
    """全部应用数据 / All application data."""
    settings: Settings = field(default_factory=Settings)
    streamers: List[StreamerData] = field(default_factory=list)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    pp_results: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "settings": self.settings.to_dict(),
            "streamers": [asdict(s) for s in self.streamers],
            "pipeline": asdict(self.pipeline),
            "pp_results": self.pp_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppData":
        settings = Settings.from_dict(data.get("settings", {}))
        streamers = [StreamerData(**s) for s in data.get("streamers", [])]
        pipeline_data = data.get("pipeline", {"nodes": []})
        nodes = [PipelineNode(**n) for n in pipeline_data.get("nodes", [])]
        pipeline = PipelineConfig(nodes=nodes)
        pp_results = data.get("pp_results", [])
        return cls(settings=settings, streamers=streamers, pipeline=pipeline, pp_results=pp_results)
