"""FastAPI 后端主入口 / FastAPI backend main entry."""
from __future__ import annotations

import os
import time
import json
import queue
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .state import AppState
from .settings import Settings, PipelineConfig, PipelineNode
from .events import emitter
from .streamers import StatusMonitor, parse_streamer_input, fetch_status, build_url
from .recorder import RecorderManager, format_size
from .recordings import list_recordings, delete_recording
from .postprocess import discover_modules, run_postprocess_for_path, get_modules_dir


# 全局单例 / global singletons
state: AppState = AppState()
monitor = StatusMonitor(state)
recorder = RecorderManager(state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor.start()
    # 启动时扫描默认模块并复制到 modules 目录
    default_modules = state.base_dir / "modules.default"
    modules_dir = get_modules_dir(state)
    modules_dir.mkdir(parents=True, exist_ok=True)
    if default_modules.exists():
        for src in default_modules.iterdir():
            dst = modules_dir / src.name
            if not dst.exists():
                import shutil
                if src.is_file():
                    shutil.copy2(src, dst)
                    dst.chmod(0o755)
    yield
    monitor.stop()


app = FastAPI(title="S-Recorder", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求模型 / Request models ──
class AddStreamerBody(BaseModel):
    input: str


class AutoRecordBody(BaseModel):
    enabled: bool


class SettingsBody(BaseModel):
    output_dir: Optional[str] = None
    poll_interval_secs: int = 30
    auto_record: bool = True
    max_concurrent: int = 0
    merge_format: str = "mp4"
    max_tmp_dir_gb: float = 50.0
    language: str = "zh-CN"
    server_port: int = 24136
    setup_done: bool = True
    slice_duration: str = "00:00:00"

    def to_settings(self) -> Settings:
        return Settings(
            output_dir=self.output_dir or "/app/s-recorder/recordings",
            poll_interval_secs=self.poll_interval_secs,
            auto_record=self.auto_record,
            max_concurrent=self.max_concurrent,
            merge_format=self.merge_format,
            max_tmp_dir_gb=self.max_tmp_dir_gb,
            language=self.language,
            server_port=self.server_port,
            setup_done=self.setup_done,
            slice_duration=self.slice_duration,
        )


class PipelineBody(BaseModel):
    nodes: List[Dict[str, Any]]

    def to_pipeline(self) -> PipelineConfig:
        nodes = [PipelineNode(**n) for n in self.nodes]
        return PipelineConfig(nodes=nodes)


class PathBody(BaseModel):
    path: str


class RunPostprocessBody(BaseModel):
    path: str


# ── 主播 API / Streamer API ──
@app.get("/api/streamers")
def api_list_streamers():
    streamers = state.streamers
    if not any(monitor.get_status(s.username) for s in streamers) and streamers:
        monitor.poll_all()
    result = []
    for s in streamers:
        st = monitor.get_status(s.username)
        result.append({
            "username": s.username,
            "auto_record": s.auto_record,
            "added_at": s.added_at,
            "is_online": st.is_online if st else False,
            "is_recording": recorder.is_recording(s.username),
            "is_recordable": st.is_recordable if st else False,
            "viewers": st.viewers if st else 0,
            "status": st.status if st else "未知",
            "thumbnail_url": st.thumbnail_url if st else None,
        })
    return result


@app.post("/api/streamers")
def api_add_streamer(body: AddStreamerBody):
    parsed = parse_streamer_input(body.input)
    if not parsed:
        raise HTTPException(status_code=400, detail="未解析到有效主播")
    added = []
    failed = []
    for item in parsed:
        username = item["username"]
        try:
            # 验证存在性（可选，不强制阻断）
            st = fetch_status(username, item.get("platform"))
            state.add_streamer(username)
            added.append(username)
            emitter.emit("streamer-added", {"username": username, "status": {
                "is_online": st.is_online,
                "is_recordable": st.is_recordable,
                "status": st.status,
            }})
            # 如果在线且自动录制开启，立即开始
            s = next((x for x in state.streamers if x.username == username), None)
            if s and s.auto_record and st.is_recordable:
                try:
                    recorder.start_recording(username, st.playlist_url)
                except Exception:
                    pass
        except Exception as e:
            failed.append({"username": username, "error": str(e)})
    return {"added": added, "failed": failed}


@app.delete("/api/streamers/{name}")
def api_remove_streamer(name: str):
    if recorder.is_recording(name):
        recorder.stop_recording(name)
    user_dir = Path(state.settings.output_dir) / name
    if user_dir.exists():
        import shutil
        shutil.rmtree(user_dir, ignore_errors=True)
    state.remove_streamer(name)
    emitter.emit("streamer-removed", {"username": name})
    return {"ok": True}


@app.post("/api/streamers/{name}/auto-record")
def api_set_auto_record(name: str, body: AutoRecordBody):
    state.set_auto_record(name, body.enabled)
    emitter.emit("auto-record-changed", {"username": name, "enabled": body.enabled})
    return {"ok": True}


@app.post("/api/streamers/{name}/start")
def api_start_recording(name: str):
    playlist_url = monitor.get_cached_playlist_url(name)
    try:
        path = recorder.start_recording(name, playlist_url)
        return {"path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/streamers/{name}/stop")
def api_stop_recording(name: str):
    try:
        state.set_auto_record(name, False)
        recorder.stop_recording(name)
        emitter.emit("auto-record-changed", {"username": name, "enabled": False})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/streamers/{name}/verify")
def api_verify_streamer(name: str):
    try:
        st = fetch_status(name)
        return {"exists": st.is_online or st.is_recordable or st.status != "离线"}
    except Exception:
        return {"exists": False}


# ── 录制文件 API / Recordings API ──
@app.get("/api/recordings")
def api_list_recordings():
    return list_recordings(state, recorder)


@app.post("/api/recordings/delete")
def api_delete_recording(body: PathBody):
    try:
        delete_recording(body.path, state, recorder)
        emitter.emit("recording-deleted", {"path": body.path})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/recordings/postprocess")
def api_run_postprocess(body: RunPostprocessBody):
    from .postprocess import run_postprocess_for_path
    try:
        run_postprocess_for_path(Path(body.path), state.pipeline, state)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/recordings/postprocess-cancel")
def api_cancel_postprocess(body: PathBody):
    state.pp_task_cancel(body.path)
    return {"ok": True}


@app.get("/api/files")
def api_serve_file(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(p)


# ── 设置 API / Settings API ──
@app.get("/api/settings")
def api_get_settings():
    return state.settings.to_dict()


@app.post("/api/settings")
def api_save_settings(body: SettingsBody):
    try:
        settings = body.to_settings()
        state.update_settings(settings)
        emitter.emit("settings-updated", settings.to_dict())
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/disk-space")
def api_disk_space():
    import shutil
    path = Path(state.settings.output_dir)
    total, used, free = shutil.disk_usage(path)
    return {
        "total_bytes": total,
        "available_bytes": free,
        "used_bytes": used,
    }


# ── 后处理 API / Postprocess API ──
@app.get("/api/modules")
def api_list_modules():
    return discover_modules(state)


@app.get("/api/pipeline")
def api_get_pipeline():
    return {"nodes": [{"nodeId": n.nodeId, "moduleId": n.moduleId, "params": n.params, "enabled": n.enabled} for n in state.pipeline.nodes]}


@app.post("/api/pipeline")
def api_save_pipeline(body: PipelineBody):
    try:
        pipeline = body.to_pipeline()
        state.update_pipeline(pipeline)
        emitter.emit("pipeline-updated", {"nodes": [{"nodeId": n.nodeId, "moduleId": n.moduleId, "params": n.params, "enabled": n.enabled} for n in pipeline.nodes]})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/postprocess-tasks")
def api_postprocess_tasks():
    return state.pp_tasks


# ── SSE 事件流 / SSE events ──
@app.get("/api/events")
def api_events():
    q = emitter.subscribe()

    def event_stream():
        try:
            while True:
                data = q.get(timeout=30)
                yield f"data: {data}\n\n"
        except queue.Empty:
            yield f"data: {json.dumps({'event': 'heartbeat', 'payload': {}})}\n\n"
        finally:
            emitter.unsubscribe(q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# 静态文件 / Static files
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
