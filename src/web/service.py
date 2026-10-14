"""Local assets and isolated worker processes; no execution in HTTP handlers."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys
import threading
import traceback
import uuid

import numpy as np
import yaml
from biopipe.run_log import append_event

from .graph import GraphError, compile_graph, relative_manifest
from .models import Graph
from .routes import RouteLibrary, expand_routes
from .storage import FileLock, atomic_json


def safe_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(v) for v in value]
    if isinstance(value, np.generic):
        return safe_json(value.item())
    return value


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, value):
    atomic_json(path, safe_json(value))


@dataclass
class Settings:
    root: Path
    data_dir: Path
    dist_dir: Path
    max_upload: int | None = None
    testing: bool = False
    code_root: Path | None = None
    desktop: bool = False
    profile: dict | None = None
    migrate_legacy: bool = False
    builtin_routes: bool = False
    instance_url: str | None = None


class JobService:
    def __init__(self, settings, catalog):
        self.settings, self.base_catalog = settings, catalog
        self.root = settings.root.resolve()
        self.directory = settings.data_dir.resolve()
        from biopipe.plugins import PluginManager
        self.plugins = PluginManager(self.directory)
        self.catalog = self.plugins.extend_catalog(catalog)
        if not self.directory.is_relative_to(self.root):
            raise ValueError("Studio data directory must be inside the project")
        self.jobs_dir = self.directory / "jobs"
        self.assets_dir = self.directory / "assets"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        self.lock = FileLock(self.directory / ".jobs.lock")
        self.processes, self.threads, self.jobs = {}, {}, {}
        import psutil
        self.owner = {"pid": os.getpid(), "created": psutil.Process().create_time()}
        with self.lock:
            self._refresh_jobs()
            self.demo = self._demo()
            write_json(self.directory / "operators.json", self.catalog)
        self.routes = RouteLibrary(self.directory / "workflows", self.catalog, self.root,
                                   lambda graph: self.plugins.catalog_for(graph, self.base_catalog))
        if settings.builtin_routes:
            self.routes.install_builtins()

    def refresh_catalog(self):
        state = self.plugins.state()
        if state["generation"] != self.catalog.get("plugin_generation"):
            value = self.plugins.extend_catalog(self.base_catalog)
            self.catalog.update(value)
            write_json(self.directory / "operators.json", self.catalog)

    def _refresh_jobs(self):
        import psutil
        for record in self.jobs_dir.glob("*/job.json"):
            value = read_json(record)
            if value:
                if value["status"] == "running" or value.get("logs_complete") is False:
                    owner = value.get("owner", {})
                    try:
                        alive = psutil.Process(owner["pid"]).create_time() == owner["created"]
                    except (KeyError, psutil.NoSuchProcess):
                        alive = False
                    except psutil.AccessDenied:
                        alive = True  # Insufficient permission is not proof of a dead worker.
                    if not alive:
                        if value["status"] == "running":
                            value["status"] = "interrupted"
                            value["error"] = "本地服务重启，之前的任务未完成。"
                        self._launcher_event(value, "worker_interrupted", status=value["status"], error=value.get("error"))
                        value["finished_at"] = datetime.now(timezone.utc).isoformat()
                        value["logs_complete"] = True
                        write_json(record, value)
                self.jobs[value["id"]] = value

    def load_draft(self):
        value = read_json(self.directory / "draft.json")
        if value is None:
            return None
        try:
            return Graph.model_validate(value).model_dump(mode="json")
        except ValueError:
            return None

    def save_draft(self, graph: Graph):
        # Incomplete graphs are valid drafts; execution validates connections.
        with self.lock:
            write_json(self.directory / "draft.json", graph.model_dump(mode="json"))

    def _demo(self):
        path = self.assets_dir / "expression-demo.csv"
        if not path.exists():
            rng = np.random.default_rng(42)
            values = rng.normal(size=(128, 24)).astype(np.float32)
            values[:64, :6] += 2
            values[rng.random(values.shape) < .015] = np.nan
            np.savetxt(path, values, delimiter=",", header=",".join(f"gene_{i+1:02d}" for i in range(24)), comments="", fmt="%.5f")
        return {
            "schema_version": 1, "name": "表达矩阵 · 质量控制与降维", "base_dir": ".",
            "memory": {"enabled": True, "auto_spill": True},
            "nodes": [
                {"id": "expression", "kind": "source", "title": "表达矩阵", "position": {"x": 60, "y": 160},
                 "source": {"path": str(path.relative_to(self.root)).replace("\\", "/"), "dims": ["sample", "feature"],
                            "labels": {"sample": "auto", "feature": "builtin"}, "args": {}}},
                {"id": "quality", "kind": "operator", "operator": "missing", "title": "缺失值过滤",
                 "position": {"x": 340, "y": 160}, "params": {"dim": "feature", "threshold": .05, "output": "clean"}},
                {"id": "pca", "kind": "operator", "operator": "pca", "title": "主成分分析",
                 "position": {"x": 620, "y": 60}, "params": {"dim": "feature", "n_components": 2, "output": "pcs"}},
                {"id": "summary", "kind": "operator", "operator": "describe", "title": "数据概览",
                 "position": {"x": 620, "y": 260}, "params": {}}
            ],
            "edges": [{"id": "expression-quality", "source": "expression", "target": "quality", "targetHandle": "in-0", "sourceHandle": "out"},
                      {"id": "quality-pca", "source": "quality", "target": "pca", "targetHandle": "in-0", "sourceHandle": "out"},
                      {"id": "quality-summary", "source": "quality", "target": "summary", "targetHandle": "in-0", "sourceHandle": "out"}]
        }

    def launch(self, graph: Graph):
        graph = self.plugins.pin(graph)
        catalog = self.plugins.catalog_for(graph, self.base_catalog)
        plugin_snapshot = self.plugins.snapshot(graph)
        manifest, order = compile_graph(graph, catalog, self.root, require_files=True)
        with self.lock:
            self._refresh_jobs()
            if any(job["status"] == "running" or job.get("logs_complete") is False for job in self.jobs.values()):
                raise GraphError("已有任务正在运行，请等它结束或先停止。")
            key = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
            directory = self.jobs_dir / key
            directory.mkdir()
            write_json(directory / "plugins.lock.json", plugin_snapshot)
            (directory / "task.yaml").write_text(yaml.safe_dump(relative_manifest(manifest, directory), sort_keys=False, allow_unicode=True), encoding="utf-8")
            job = {"id": key, "name": graph.name, "status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
                   "finished_at": None, "error": None, "exit_code": None, "logs_complete": False,
                   "order": order, "graph": graph.model_dump(mode="json"), "owner": self.owner}
            job["plugins"] = {"generation": plugin_snapshot["generation"], "packages": plugin_snapshot["packages"]}
            if any(node.kind == "route" for node in graph.nodes):
                _, job["node_owners"] = expand_routes(graph, self.catalog)
            self.jobs[key] = job
            write_json(directory / "job.json", job)
            console = None
            try:
                console = open(directory / "console.log", "a", encoding="utf-8")
                temporary = directory / "tmp"
                temporary.mkdir()
                env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONFAULTHANDLER="1", TEMP=str(temporary), TMP=str(temporary),
                           MPLCONFIGDIR=str(self.directory / "matplotlib"))
                code_root = self.settings.code_root or self.root
                python = self.plugins.python_for(plugin_snapshot)
                console.write(f"[BioPipe launcher] Job {key}\nPython: {python}\nTask: {directory}\n")
                console.flush()
                self._launcher_event(job, "worker_launching", python=python, message="Starting analysis worker")
                # stdin belongs to the desktop host's control pipe. Inheriting it
                # can block Python startup on Windows while watch_host reads it.
                process = subprocess.Popen([python, str(code_root / "scripts/run.py"), str(directory)],
                                           cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                           stdout=console, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except Exception as exc:
                job["status"], job["error"] = "failed", f"{type(exc).__name__}: {exc}"
                if console is not None:
                    try:
                        console.write(traceback.format_exc())
                        console.close()
                    except OSError:
                        pass
                self._launcher_event(job, "worker_start_failed", error=job["error"])
                job["finished_at"] = datetime.now(timezone.utc).isoformat()
                job["logs_complete"] = True
                write_json(directory / "job.json", job)
                return self.details(key)
            self._launcher_event(job, "worker_spawned", pid=process.pid)
            self.processes[key] = process
            watcher = threading.Thread(target=self._watch, args=(key, process, console), daemon=True)
            self.threads[key] = watcher
            watcher.start()
            return self.details(key)

    def _watch(self, key, process, console):
        code = process.wait()
        with self.lock:
            job = self.jobs[key]
            summary = read_json(self.jobs_dir / key / "output/run_summary.json", {})
            if job["status"] != "cancelled":
                job["status"] = "complete" if code == 0 and summary.get("status") == "complete" else "failed"
                job["error"] = summary.get("error") or (None if job["status"] == "complete" else
                    f"Worker exited with code {code} (0x{code & 0xffffffff:08X}) "
                    + ("without producing a run summary." if not summary else "without completing the run."))
            job["exit_code"] = code
            try:
                console.write(f"\n[BioPipe launcher] Worker exit code {code} (0x{code & 0xffffffff:08X}); status={job['status']}\n")
                if job.get("error"):
                    console.write(job["error"] + "\n")
            except OSError as exc:
                job["log_error"] = str(exc)
            finally:
                try:
                    console.close()
                except OSError as exc:
                    job["log_error"] = str(exc)
            self._launcher_event(job, "worker_finished", exit_code=code, status=job["status"], error=job.get("error"))
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
            # Publish terminal completion only after both writers have flushed.
            job["logs_complete"] = True
            write_json(self.jobs_dir / key / "job.json", job)
            self.processes.pop(key, None)
            self.threads.pop(key, None)

    def _launcher_event(self, job, event, **details):
        # Separate journal: the parent never competes with the worker's JSONL writer.
        try:
            append_event(self.jobs_dir / job["id"] / "launcher.events.jsonl", event, **details)
        except OSError as exc:
            job["log_error"] = str(exc)

    def require(self, key):
        # Jobs created by the other launcher become visible without restarting.
        value = read_json(self.jobs_dir / key / "job.json") if key.replace("-", "").isalnum() else None
        if value:
            self.jobs[key] = value
        if key not in self.jobs:
            raise KeyError("找不到这次运行。")
        return self.jobs[key]

    def events_path(self, key):
        self.require(key)
        paths = list((self.jobs_dir / key / "output/runs").glob("*/events.jsonl"))
        return paths[0] if paths else None

    def event_paths(self, key):
        self.require(key)
        directory = self.jobs_dir / key
        return [p for p in [directory / "launcher.events.jsonl",
                *sorted((directory / "output/runs").glob("*/events.jsonl"))] if p.is_file()]

    def console_snapshot(self, key, job, previous=None, limit=64 * 1024):
        """A bounded display tail; the downloadable file remains complete."""
        path = self.jobs_dir / key / "console.log"
        try:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns, job.get("status"), job.get("error"))
            if signature == previous:
                return signature, None
            if stat.st_size:
                with path.open("rb") as file:
                    file.seek(max(0, stat.st_size - limit))
                    content = file.read(limit).decode("utf-8", errors="replace")
                return signature, {"console": content, "console_truncated": stat.st_size > limit}
        except FileNotFoundError:
            signature = (None, job.get("status"), job.get("error"))
            if signature == previous:
                return signature, None
        # Old empty files are evidence too: display a fallback without rewriting them.
        content = f"No worker output was captured for this run.\nStatus: {job['status']}\n"
        if job.get("error"):
            content += f"Recorded error: {job['error']}\n"
        return signature, {"console": content, "console_truncated": False}

    def details(self, key):
        with self.lock:
            job = dict(self.require(key))
            summary = read_json(self.jobs_dir / key / "output/run_summary.json")
            job["summary"] = summary
            job["report"] = read_json(self._record_path(key, summary["memory_report"], summary)) if summary and summary.get("memory_report") else None
            if job["report"]:
                # Reports retain original audit locations on disk. API paths follow a moved workspace.
                for artifact in job["report"].get("artifacts", []):
                    if artifact.get("disk_uri"):
                        artifact["disk_uri"] = str(self._record_path(key, artifact["disk_uri"], summary))
                job["spill_counts"] = self.spill_counts(key)
            return safe_json(job)

    def _record_path(self, key, value, summary):
        """Resolve current or historical paths without depending on the original machine."""
        directory = self.jobs_dir / key
        # Read Windows-authored records on POSIX as well as POSIX records on Windows.
        path_type = PureWindowsPath if PureWindowsPath(value).drive or "\\" in value else PurePosixPath
        stored = path_type(value)
        if not stored.is_absolute():
            candidate = directory.joinpath(*stored.parts).resolve()
        else:
            old_task = path_type(summary.get("task_dir", str(directory)))
            old_root = old_task
            for _ in directory.relative_to(self.root).parts:
                old_root = old_root.parent
            try:
                relative = stored.relative_to(old_root)
            except ValueError as exc:
                raise KeyError("记录中的文件不在原工作目录内，请迁移完整工作目录。") from exc
            candidate = self.root.joinpath(*relative.parts).resolve()
        if not candidate.is_relative_to(self.root):
            raise KeyError("记录中的路径超出当前工作目录。")
        return candidate

    def spill_counts(self, key):
        counts = {"planned": 0, "emergency": 0, "final": 0, "correction": 0}
        path = self.events_path(key)
        if path:
            with open(path, encoding="utf-8") as lines:
                for line in lines:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if item.get("event") == "spill":
                        reason = item.get("reason")
                        category = ("final" if reason == "final_output" else "emergency" if reason in ("rss_pressure", "managed_pressure")
                                    else "correction" if reason in ("actual_output_size", "actual_input_size", "step_boundary") else "planned")
                        counts[category] += 1
        return counts

    def history(self):
        with self.lock:
            self._refresh_jobs()
            return [{k: value[k] for k in ("id", "name", "status", "created_at", "finished_at", "error")}
                    for value in sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)[:30]]

    def cancel(self, key):
        with self.lock:
            job = self.require(key)
            if job["status"] == "running":
                if key not in self.processes:
                    raise GraphError("任务由另一个 BioPipe 窗口运行，请在启动它的窗口停止。")
                job["status"] = "cancelled"
                self.processes[key].terminate()
                write_json(self.jobs_dir / key / "job.json", job)
            return self.details(key)

    def shutdown(self):
        for key in list(self.processes):
            self.cancel(key)
        for watcher in list(self.threads.values()):
            watcher.join(timeout=5)

    def artifact(self, key, artifact_id):
        report = self.details(key).get("report")
        match = next((a for a in (report or {}).get("artifacts", []) if a["artifact_id"] == artifact_id), None)
        if not match or not match["disk_uri"]:
            raise KeyError("产物尚未保存，或这次运行没有保留它。")
        path = (Path(match["disk_uri"]) / "data.npy").resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise KeyError("产物文件不可用。")
        return path, match

    def preview(self, key, artifact_id):
        path, descriptor = self.artifact(key, artifact_id)
        data = np.load(path, mmap_mode="r", allow_pickle=False)
        if data.ndim != 2 or data.dtype.kind not in "biuf":
            return {"descriptor": descriptor, "rows": [], "points": []}
        rows = data[:20, :8].tolist()
        points = data[:200, :2].tolist() if data.shape[1] >= 2 else []
        del data
        return safe_json({"descriptor": descriptor, "rows": rows, "points": points})

    def export_file(self, key, index):
        summary = self.details(key).get("summary") or {}
        exports = summary.get("steps", [])
        if not 0 <= index < len(exports):
            raise KeyError("找不到步骤报告。")
        directory = self.jobs_dir / key
        path = (directory / "output" / exports[index]["export_path"]).resolve()
        if not path.is_relative_to(directory):
            raise KeyError("报告路径不可用。")
        return path

    def figure_file(self, key, index):
        content = read_json(self.export_file(key, index), {})
        if not isinstance(content, dict) or not content.get("path"):
            raise KeyError("此步骤没有图像产物。")
        summary = read_json(self.jobs_dir / key / "output/run_summary.json", {})
        path = self._record_path(key, content["path"], summary)
        directory = (self.jobs_dir / key).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise KeyError("图像路径不可用。")
        return path
