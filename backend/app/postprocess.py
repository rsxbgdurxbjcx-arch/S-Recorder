"""后处理流水线引擎 / Post-processing pipeline engine."""
from __future__ import annotations

import os
import re
import json
import subprocess
import threading
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
import uuid

from .events import emitter
from .state import AppState
from .settings import PipelineConfig, PipelineNode
from .recorder import read_video_meta, write_video_meta


MODULES_DIR_NAME = "modules"


def get_modules_dir(state: AppState) -> Path:
    """获取后处理模块目录."""
    return state.base_dir / MODULES_DIR_NAME


def discover_modules(state: AppState) -> List[Dict[str, Any]]:
    """扫描 modules/ 目录发现可用模块."""
    modules_dir = get_modules_dir(state)
    if not modules_dir.exists():
        return []
    modules = []
    for entry in modules_dir.iterdir():
        if not entry.is_file():
            continue
        # 检查是否有可执行权限
        try:
            st = entry.stat()
            if not (st.st_mode & 0o111):
                continue
        except Exception:
            continue
        try:
            proc = subprocess.run(
                [str(entry), "--describe"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                info = json.loads(proc.stdout)
                info["exe_path"] = str(entry)
                modules.append(info)
        except Exception:
            continue
    return modules


def parse_module_progress(line: str) -> Optional[tuple]:
    """解析 PROGRESS:done/total 协议行."""
    m = re.match(r"PROGRESS:(\d+)/(\d+)", line.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def parse_module_status(line: str) -> Optional[str]:
    """解析 STATUS:text 协议行."""
    m = re.match(r"STATUS:(.+)", line.strip())
    if m:
        return m.group(1)
    return None


def parse_module_output(line: str) -> Optional[str]:
    """解析 OUTPUT:path 协议行."""
    m = re.match(r"OUTPUT:(.+)", line.strip())
    if m:
        return m.group(1).strip()
    return None


def run_node(module: Dict[str, Any], node: PipelineNode, input_path: Path, state: AppState,
             on_progress, on_log, on_status) -> Dict[str, Any]:
    """执行单个后处理节点."""
    exe = module.get("exe_path")
    if not exe:
        return {"node_id": node.nodeId, "module_id": node.moduleId, "success": False,
                "message": "模块可执行文件路径缺失", "output": None}

    env = os.environ.copy()
    env["PP_INPUT"] = str(input_path)
    env["PP_EXE_DIR"] = str(state.base_dir)
    max_tmp_mb = int(state.settings.max_tmp_dir_gb * 1024)
    env["PP_MAX_TMP_MB"] = str(max_tmp_mb)
    for key, val in node.params.items():
        env[f"PP_PARAM_{key.upper()}"] = str(val)

    try:
        proc = subprocess.Popen(
            [exe],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        return {"node_id": node.nodeId, "module_id": node.moduleId, "success": False,
                "message": f"启动失败: {e}", "output": None}

    last_message = ""
    output_path: Optional[str] = None
    delete_input = False

    def read_stream(stream, name):
        nonlocal last_message, output_path, delete_input
        for line in stream:
            line = line.rstrip("\n")
            on_log(name, line)
            pp = parse_module_progress(line)
            if pp:
                on_progress(pp[0], pp[1])
                continue
            st = parse_module_status(line)
            if st:
                on_status(st)
                continue
            out = parse_module_output(line)
            if out:
                output_path = out
                continue
            if line.strip() == "DELETE_INPUT":
                delete_input = True
                continue
            if line.strip():
                last_message = line

    t_out = threading.Thread(target=read_stream, args=(proc.stdout, "stdout"), daemon=True)
    t_err = threading.Thread(target=read_stream, args=(proc.stderr, "stderr"), daemon=True)
    t_out.start()
    t_err.start()
    proc.wait()
    t_out.join(timeout=2)
    t_err.join(timeout=2)

    success = proc.returncode == 0
    message = last_message or ("成功" if success else f"退出码 {proc.returncode}")
    result = {
        "node_id": node.nodeId,
        "module_id": node.moduleId,
        "success": success,
        "message": message,
        "output": output_path or str(input_path),
    }

    if delete_input and success:
        try:
            input_path.unlink()
            meta_path = input_path.with_suffix(input_path.suffix + ".json")
            if meta_path.exists():
                meta_path.unlink()
        except Exception as e:
            result["message"] += f" (删除输入失败: {e})"

    return result


def run_pipeline(video_path: Path, pipeline: PipelineConfig, state: AppState) -> List[Dict[str, Any]]:
    """执行流水线."""
    modules = discover_modules(state)
    modules_by_id = {m["id"]: m for m in modules}
    results = []
    current_input = video_path
    enabled_nodes = [n for n in pipeline.nodes if n.enabled]
    total = len(enabled_nodes)

    state.pp_task_start(str(video_path), total)
    emitter.emit("postprocess-started", {"path": str(video_path)})

    for idx, node in enumerate(enabled_nodes):
        if state.is_pp_cancelled(str(video_path)):
            break
        module = modules_by_id.get(node.moduleId)
        if not module:
            results.append({
                "node_id": node.nodeId,
                "module_id": node.moduleId,
                "success": False,
                "message": f"模块 {node.moduleId} 不存在",
                "output": None,
            })
            break

        module_name = module.get("name", node.moduleId)

        def on_progress(done, tot):
            pct = (done / tot * 100) if tot > 0 else 0
            state.pp_task_progress(str(video_path), pct, done, tot, module_name)
            emitter.emit("postprocess-progress", {
                "path": str(video_path),
                "done": idx,
                "total": total,
                "pct": pct,
                "modDone": done,
                "modTotal": tot,
                "moduleName": module_name,
            })

        def on_log(stream, line):
            emitter.emit("postprocess-log", {
                "path": str(video_path),
                "moduleId": node.moduleId,
                "stream": stream,
                "line": line,
            })

        def on_status(text):
            emitter.emit("postprocess-status", {
                "path": str(video_path),
                "moduleId": node.moduleId,
                "status": text,
            })

        result = run_node(module, node, current_input, state, on_progress, on_log, on_status)
        results.append(result)

        if not result["success"]:
            break
        if result["output"]:
            current_input = Path(result["output"])

    all_ok = all(r["success"] for r in results)
    state.pp_task_finish(str(video_path), all_ok)
    emitter.emit("postprocess-done", {"path": str(video_path), "results": results})

    # 更新元数据
    meta = read_video_meta(video_path) or {}
    meta["status"] = "finish" if all_ok else "pp_error"
    meta["pp_results"] = [{"module_id": r["module_id"], "success": r["success"], "message": r["message"]} for r in results]
    module_outputs = meta.get("module_outputs", {})
    for r in results:
        if r["success"] and r["output"] and r["output"] != str(video_path):
            module_outputs[r["module_id"]] = r["output"]
    meta["module_outputs"] = module_outputs
    write_video_meta(video_path, meta)
    if all_ok:
        state.add_pp_result(str(video_path))
    return results


def run_postprocess_for_path(video_path: Path, pipeline: PipelineConfig, state: AppState) -> None:
    """公开入口：将任务入队并在线程中执行."""
    path_str = str(video_path)
    state.pp_task_enqueue(path_str)
    state.pp_task_clear_cancel(path_str)
    emitter.emit("postprocess-waiting", {"path": path_str})
    set_video_meta_status(video_path, "pp_waiting")

    def task():
        with state.pp_lock:
            if state.is_pp_cancelled(path_str):
                state.pp_task_clear_cancel(path_str)
                state.pp_task_remove(path_str)
                return
            set_video_meta_status(video_path, "pp_running")
            run_pipeline(video_path, pipeline, state)

    threading.Thread(target=task, daemon=True).start()


def set_video_meta_status(path: Path, status: str) -> None:
    meta = read_video_meta(path) or {}
    meta["status"] = status
    write_video_meta(path, meta)
