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
import time
import traceback
import uuid

import yaml
from biopipe.run_log import append_event

from .graph import GraphError, compile_graph, relative_manifest
from .models import Graph
from .routes import RouteLibrary, expand_routes
from .storage import FileLock, atomic_json
from .admission import HostAdmission, MIB, process_alive, process_identity


def safe_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(v) for v in value]
    numpy = sys.modules.get("numpy")
    scalar_type = vars(numpy).get("generic") if numpy is not None else None
    if scalar_type is not None and isinstance(value, scalar_type):
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
    builtin_routes: bool = False
    instance_url: str | None = None
    input_roots: list[Path] | None = None
    admission_dir: Path | None = None


class JobService:
    def __init__(self, settings, catalog):
        self.settings, self.base_catalog = settings, catalog
        self.remotes = None
        self.root = settings.root.resolve()
        self.directory = settings.data_dir.resolve()
        from biopipe.plugins import PluginManager
        self.plugins = PluginManager(self.directory)
        from biopipe.dependencies import DependencySession
        self.dependencies = DependencySession(self.plugins)
        self.dependencies.sync(self.plugins.state())
        self.catalog = self.plugins.extend_catalog(catalog)
        if not self.directory.is_relative_to(self.root):
            raise ValueError("Studio data directory must be inside the project")
        self.jobs_dir = self.directory / "jobs"
        self.assets_dir = self.directory / "assets"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        self.lock = FileLock(self.directory / ".jobs.lock")
        self.processes, self.threads, self.jobs = {}, {}, {}
        self._closed = threading.Event()
        self._wake = threading.Event()
        import psutil
        self.owner = {"pid": os.getpid(), "created": psutil.Process().create_time(), "service_id": uuid.uuid4().hex}
        admission_dir = settings.admission_dir or (self.root / '.admission' if settings.testing else None)
        self.admission = HostAdmission(admission_dir)
        with self.lock:
            self._refresh_jobs()
            self.demo = self._demo()
            write_json(self.directory / "operators.json", self.catalog)
        self.routes = RouteLibrary(self.directory / "workflows", self.catalog, self.root,
                                   self.graph_catalog)
        if settings.builtin_routes:
            self.routes.install_builtins()
        self.scheduler = threading.Thread(target=self._schedule, name='biopipe-admission', daemon=True)
        self.scheduler.start()

    def graph_catalog(self, graph):
        from .source_paths import remote_profile
        if self.remotes and remote_profile(graph):
            return self.remotes.catalog(graph)
        return self.plugins.catalog_for(graph, self.base_catalog)

    def prepare_graph(self, graph):
        from .source_paths import remote_profile
        from .parameters import freeze_graph
        from .routes import prepare_interface
        if self.remotes and remote_profile(graph):
            return self.remotes.prepare(graph)
        graph = self.plugins.pin(graph)
        catalog = self.graph_catalog(graph)
        return prepare_interface(freeze_graph(graph, catalog, self.root), catalog, self.root)

    def validate_graph(self, graph, require_files=True):
        from .source_paths import remote_profile
        from .contracts import analyze_graph
        if self.remotes and remote_profile(graph):
            return self.remotes.call(remote_profile(graph), 'validate', {'graph': graph.model_dump(mode='json'),
                                                                       'require_files': require_files})
        catalog = self.graph_catalog(graph)
        manifest, order = compile_graph(graph, catalog, self.root, require_files=require_files,
                                        input_roots=self.settings.input_roots)
        return {'valid': True, 'order': order, 'manifest': manifest, 'contracts': analyze_graph(graph, catalog, self.root)}

    def refresh_catalog(self):
        state = self.plugins.state()
        if state["generation"] != self.catalog.get("plugin_generation"):
            self.dependencies.sync(state)
            value = self.plugins.extend_catalog(self.base_catalog)
            self.catalog.update(value)
            write_json(self.directory / "operators.json", self.catalog)
            return True
        return False

    def _refresh_jobs(self, *, active_only=False):
        import psutil
        records = ((self.jobs_dir / key / 'job.json' for key, value in list(self.jobs.items())
                    if value['status'] in ('queued', 'running') or value.get('logs_complete') is False)
                   if active_only else self.jobs_dir.glob('*/job.json'))
        for record in records:
            value = read_json(record)
            if value:
                if value["status"] == "queued":
                    if not process_alive(value.get('owner', {})):
                        value['owner'] = self.owner
                        write_json(record, value)
                elif value["status"] == "running" or value.get("logs_complete") is False:
                    owner = value.get("owner", {})
                    try:
                        alive = psutil.Process(owner["pid"]).create_time() == owner["created"]
                    except (KeyError, psutil.NoSuchProcess):
                        alive = False
                    except psutil.AccessDenied:
                        alive = True  # Insufficient permission is not proof of a dead worker.
                    if not alive:
                        # Do not replay a half-finished analysis after a launcher
                        # crash. Stop only the recorded, identity-checked worker.
                        worker = value.get('worker', {})
                        if worker and process_alive(worker):
                            process = psutil.Process(worker['pid'])
                            try:
                                process.suspend()
                                children = process.children(recursive=True)
                                for child in children:
                                    try: child.suspend(); child.kill()
                                    except psutil.NoSuchProcess: pass
                                process.kill()
                                psutil.wait_procs([process, *children], timeout=5)
                            except psutil.NoSuchProcess:
                                pass
                        if value["status"] == "running":
                            value["status"] = "interrupted"
                            value["error"] = "本地服务重启，之前的任务未完成。"
                        self._launcher_event(value, "worker_interrupted", status=value["status"], error=value.get("error"))
                        value["finished_at"] = datetime.now(timezone.utc).isoformat()
                        value["logs_complete"] = True
                        self._release(value)
                        write_json(record, value)
                self.jobs[value["id"]] = value

    def _demo(self):
        path = self.assets_dir / "expression-demo.csv"
        if not path.exists():
            import csv, random
            rng = random.Random(42)
            with path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(f"gene_{i+1:02d}" for i in range(24))
                for row in range(128):
                    writer.writerow('nan' if rng.random() < .015 else f"{rng.gauss(0, 1) + (2 if row < 64 and col < 6 else 0):.5f}" for col in range(24))
        return {
            "schema_version": 2, "name": "表达矩阵 · 质量控制与降维", "base_dir": ".",
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
        from .source_paths import remote_profile
        if self.remotes and remote_profile(graph):
            return self.remotes.launch(graph)
        plugin_snapshot = self.plugins.snapshot(graph)
        graph = self.plugins.pin(graph, snapshot=plugin_snapshot)
        catalog = self.plugins._catalog(plugin_snapshot, self.base_catalog)
        from .parameters import freeze_graph
        from biopipe.parameter_values import split_task
        graph = freeze_graph(graph, catalog, self.root)
        manifest, order = compile_graph(graph, catalog, self.root, require_files=True, input_roots=self.settings.input_roots)
        try:
            allocation = self.admission.request(manifest)
        except ValueError as exc:
            raise GraphError(str(exc)) from exc
        with self.lock:
            self._refresh_jobs()
            if self._closed.is_set():
                raise GraphError('Studio is shutting down; no new jobs can be submitted')
            key = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
            directory = self.jobs_dir / key
            directory.mkdir()
            write_json(directory / "plugins.lock.json", plugin_snapshot)
            # Keep the saved graph unchanged. Only this run receives the fixed
            # host reservation; a worker never independently claims 90% again.
            memory = manifest['runtime']['memory']
            if allocation['memory_enabled']:
                memory['budget_mb'] = allocation['budget_bytes'] / MIB
                memory['process_limit_mb'] = allocation['process_limit_bytes'] / MIB
            task, parameter_values = split_task(relative_manifest(manifest, directory, catalog))
            write_json(directory / "parameters.json", parameter_values)
            (directory / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8")
            job = {"id": key, "name": graph.name, "status": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
                   "finished_at": None, "error": None, "exit_code": None, "logs_complete": False,
                   "order": order, "graph": graph.model_dump(mode="json"), "owner": self.owner,
                   "allocation": allocation, 'queued_reason': 'Waiting for available host memory and CPU',
                   'reservation_key': str(directory.resolve()),
                   'progress': {'phase': 'queued', 'completed': 0, 'total': len(order), 'percent': 0}}
            job["plugins"] = {"generation": plugin_snapshot["generation"], "packages": plugin_snapshot["packages"]}
            if plugin_snapshot.get('bundled_updates'):
                job['plugins']['bundled_updates'] = plugin_snapshot['bundled_updates']
            if any(node.kind == "route" for node in graph.nodes):
                _, job["node_owners"] = expand_routes(graph, self.catalog)
            self.jobs[key] = job
            write_json(directory / "job.json", job)
            self._launcher_event(job, 'job_queued', allocation=allocation)
            self._dispatch()
            self._wake.set()
            return self.details(key)

    def _schedule(self):
        while not self._closed.is_set():
            self._wake.wait(.25)
            self._wake.clear()
            try:
                with self.lock:
                    self._refresh_jobs(active_only=True)
                    self._dispatch()
                    self.scheduler_error = None
            except Exception as exc:
                # Exposed in resources; do not silently abandon a durable queue.
                self.scheduler_error = f'{type(exc).__name__}: {exc}'

    def _dispatch(self):
        if self._closed.is_set():
            return
        pending = [job for job in self.jobs.values() if job['status'] == 'queued' and job.get('owner') == self.owner]
        for job in sorted(pending, key=lambda value: value['created_at']):
            if (job['allocation']['reserved_bytes'] > self.admission.capacity or
                    job['allocation']['cpu_threads'] > self.admission.cpus):
                job.update(status='failed', error='The queued reservation exceeds this host session capacity; resubmit with a smaller budget',
                           finished_at=datetime.now(timezone.utc).isoformat(), logs_complete=True, queued_reason=None)
                job['allocation']['state'] = 'released'
                job['progress']['phase'] = 'failed'
                self._launcher_event(job, 'admission_failed', error=job['error'])
                write_json(self.jobs_dir / job['id'] / 'job.json', job)
                continue
            if not self.admission.reserve(job['reservation_key'], job['allocation']):
                # FIFO within a launcher avoids starvation of a larger job.
                break
            job['allocation']['state'] = 'reserved'
            self._start(job)

    def _start(self, job):
        key = job['id']; directory = self.jobs_dir / key
        console = None
        try:
            job['status'] = 'running'
            job['started_at'] = datetime.now(timezone.utc).isoformat()
            job['queued_reason'] = None
            job['progress']['phase'] = 'preparing'
            write_json(directory / 'job.json', job)
            console = open(directory / 'console.log', 'a', encoding='utf-8')
            temporary = directory / 'tmp'; temporary.mkdir(exist_ok=True)
            env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', PYTHONFAULTHANDLER='1',
                       TEMP=str(temporary), TMP=str(temporary), MPLCONFIGDIR=str(self.directory / 'matplotlib'))
            threads = str(job['allocation']['cpu_threads'])
            for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                         'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'BIOPIPE_CPU_LIMIT'):
                env[name] = threads
            env['BIOPIPE_AVAILABLE_AT_START_BYTES'] = str(job['allocation']['available_at_start_bytes'])
            code_root = self.settings.code_root or self.root
            python = self.plugins.python_for(read_json(directory / 'plugins.lock.json'))
            console.write(f'[BioPipe launcher] Job {key}\nPython: {python}\nTask: {directory}\n')
            console.flush()
            self._launcher_event(job, 'worker_launching', python=python, allocation=job['allocation'], message='Starting analysis worker')
            process = subprocess.Popen([python, str(code_root / 'scripts/run.py'), str(directory)],
                                       cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                       stdout=console, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.processes[key] = process
            try:
                job['worker'] = process_identity(process.pid)
            except Exception:
                pass  # Already-exited workers are finalized by _watch.
            self.admission.started(job['reservation_key'], process.pid)
            self._launcher_event(job, 'worker_spawned', pid=process.pid)
            write_json(directory / 'job.json', job)
            watcher = threading.Thread(target=self._watch, args=(key, process, console), daemon=True)
            self.threads[key] = watcher
            watcher.start()
        except Exception as exc:
            self.threads.pop(key, None)
            if key in self.processes:
                from biopipe.processes import stop_tree
                stop_tree(self.processes.pop(key))
            job['status'], job['error'] = 'failed', f'{type(exc).__name__}: {exc}'
            if console is not None:
                try:
                    console.write(traceback.format_exc()); console.close()
                except OSError:
                    pass
            self._launcher_event(job, 'worker_start_failed', error=job['error'])
            job['finished_at'] = datetime.now(timezone.utc).isoformat()
            job['logs_complete'] = True
            job['progress']['phase'] = 'failed'
            self._release(job)
            write_json(directory / 'job.json', job)

    def _release(self, job):
        allocation = job.get('allocation', {})
        if allocation.get('state') == 'reserved':
            self.admission.release(job['reservation_key'])
            allocation['state'] = 'released'
            allocation['released_at'] = datetime.now(timezone.utc).isoformat()

    def resources(self):
        with self.lock:
            result = self.admission.resources()
            result['queued_jobs'] = sum(job['status'] == 'queued' for job in self.jobs.values())
            result['scheduler_error'] = getattr(self, 'scheduler_error', None)
            return result

    def _watch(self, key, process, console):
        # The runtime first attempts emergency spilling. If a plugin/native
        # process remains above its reservation, contain that job after a grace
        # period rather than allowing it to consume another admitted job's RAM.
        import psutil
        over_since = None
        pressure_error = None
        while True:
            try:
                code = process.wait(timeout=.25)
                break
            except subprocess.TimeoutExpired:
                try:
                    parent = psutil.Process(process.pid)
                    rss = parent.memory_info().rss
                    for child in parent.children(recursive=True):
                        try: rss += child.memory_info().rss
                        except psutil.Error: pass
                except psutil.Error:
                    continue
                limit = self.jobs[key]['allocation']['process_limit_bytes']
                if rss > limit:
                    over_since = over_since or time.monotonic()
                    if time.monotonic() - over_since >= 2:
                        pressure_error = f'Worker tree RSS {rss} exceeds its host reservation {limit}; emergency spill could not recover enough memory'
                        from biopipe.processes import stop_tree
                        stop_tree(process)
                else:
                    over_since = None
        with self.lock:
            job = self.jobs[key]
            summary = read_json(self.jobs_dir / key / "output/run_summary.json", {})
            if job["status"] != "cancelled":
                job["status"] = "complete" if code == 0 and summary.get("status") == "complete" and not pressure_error else "failed"
                job["error"] = pressure_error or summary.get("error") or (None if job["status"] == "complete" else
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
            self._release(job)
            job['progress'] = self._progress(job)
            write_json(self.jobs_dir / key / "job.json", job)
            self.processes.pop(key, None)
            self.threads.pop(key, None)
            self._wake.set()

    def _launcher_event(self, job, event, **details):
        # Separate journal: the parent never competes with the worker's JSONL writer.
        try:
            append_event(self.jobs_dir / job["id"] / "launcher.events.jsonl", event, **details)
        except OSError as exc:
            job["log_error"] = str(exc)

    def require(self, key):
        # Jobs created by the other launcher become visible without restarting.
        with self.lock:
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
        if self.remotes and self.remotes.owns(key):
            return self.remotes.job(key)
        with self.lock:
            job = dict(self.require(key))
            summary = read_json(self.jobs_dir / key / "output/run_summary.json")
            job["summary"] = summary
            job['progress'] = self._progress(job)
            queued = sorted((value for value in self.jobs.values() if value['status'] == 'queued'),
                            key=lambda value: value['created_at'])
            job['queue_position'] = next((index + 1 for index, value in enumerate(queued) if value['id'] == key), None)
            job["report"] = read_json(self._record_path(key, summary["memory_report"], summary)) if summary and summary.get("memory_report") else None
            if job["report"]:
                # Reports retain original audit locations on disk. API paths follow a moved workspace.
                for artifact in job["report"].get("artifacts", []):
                    if artifact.get("disk_uri"):
                        artifact["disk_uri"] = str(self._record_path(key, artifact["disk_uri"], summary))
                job["spill_counts"] = self.spill_counts(key)
            return safe_json(job)

    def _progress(self, job):
        total = len(job.get('order', []))
        progress = dict(job.get('progress') or {'completed': 0, 'total': total, 'percent': 0})
        progress['phase'] = job['status']
        progress['total'] = total
        # Read a bounded journal tail, using real step indices instead of a
        # timer-derived percentage. Long-running tools remain at their step.
        paths = sorted((self.jobs_dir / job['id'] / 'output/runs').glob('*/events.jsonl'))
        current = None
        if paths:
            with paths[-1].open('rb') as stream:
                size = stream.seek(0, os.SEEK_END)
                stream.seek(max(0, size - 65536))
                lines = stream.read().decode('utf-8', errors='replace').splitlines()
            for line in lines:
                try: event = json.loads(line)
                except json.JSONDecodeError: continue
                if event.get('event') == 'step_started' and isinstance(event.get('index'), int):
                    current = event['index']
                    progress['completed'] = max(progress['completed'], current - 1)
                    progress['current'] = event.get('name')
                elif event.get('event') == 'step_finished':
                    completed = event.get('index', current)
                    if isinstance(completed, int):
                        progress['completed'] = max(progress['completed'], completed)
        if job['status'] == 'complete':
            progress['completed'] = total
            progress.pop('current', None)
        progress['completed'] = min(total, progress['completed'])
        progress['percent'] = round(100 * progress['completed'] / total, 1) if total else 0
        return progress

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
            local = [{**{k: value[k] for k in ("id", "name", "status", "created_at", "finished_at", "error")},
                      'progress': self._progress(value), 'allocation': value.get('allocation'),
                      'execution_parent_id': value.get('graph', {}).get('runtime', {}).get('execution_parent_id'),
                      'queued_reason': value.get('queued_reason')}
                     for value in sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)[:60]]
        return sorted(local + (self.remotes.history() if self.remotes else []),
                      key=lambda item: item['created_at'], reverse=True)[:60]

    def cancel(self, key):
        if self.remotes and self.remotes.owns(key):
            return self.remotes.cancel(key)
        with self.lock:
            job = self.require(key)
            if job['status'] == 'queued':
                job['status'] = 'cancelled'
                job['finished_at'] = datetime.now(timezone.utc).isoformat()
                job['logs_complete'] = True
                job['queued_reason'] = None
                job['allocation']['state'] = 'released'
                job['progress']['phase'] = 'cancelled'
                self._launcher_event(job, 'job_cancelled', message='Cancelled before worker launch')
                write_json(self.jobs_dir / key / 'job.json', job)
                self._wake.set()
            if job["status"] == "running":
                if key not in self.processes:
                    raise GraphError("任务由另一个 BioPipe 窗口运行，请在启动它的窗口停止。")
                job["status"] = "cancelled"
                # Isolated calls poll this request and can flush their failure
                # log and clean exchange files before the fallback tree kill.
                (self.jobs_dir / key / 'cancel.requested').touch()
                process = self.processes[key]
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    from biopipe.processes import stop_tree
                    stop_tree(process)
                write_json(self.jobs_dir / key / "job.json", job)
            return self.details(key)

    def shutdown(self):
        self._closed.set()
        self._wake.set()
        if self.remotes:
            self.remotes.close()
        self.dependencies.cancel.set()
        for key in list(self.processes):
            self.cancel(key)
        with self.lock:
            for job in list(self.jobs.values()):
                if job['status'] == 'queued' and job.get('owner') == self.owner:
                    self.cancel(job['id'])
        for watcher in list(self.threads.values()):
            watcher.join(timeout=10)
        if self.scheduler is not threading.current_thread():
            self.scheduler.join(timeout=5)
        self.admission.close()

    def artifact(self, key, artifact_id):
        report = self.details(key).get("report")
        match = next((a for a in (report or {}).get("artifacts", []) if a["artifact_id"] == artifact_id), None)
        if not match or not match["disk_uri"]:
            raise KeyError("产物尚未保存，或这次运行没有保留它。")
        path = (Path(match["disk_uri"]) / ("files.json" if match.get("kind") == "file" else "data.npy")).resolve()
        if not path.is_relative_to(self.root):
            raise KeyError("产物文件不可用。")
        # Validate containment before using Windows' extended I/O path. A cache
        # directory can be renamed successfully past MAX_PATH while ordinary
        # stat/open subsequently report that the existing payload is absent.
        from biopipe.bytecode import filesystem_path
        path = Path(filesystem_path(path))
        if not path.is_file():
            raise KeyError("产物文件不可用。")
        return path, match

    def preview(self, key, artifact_id):
        path, descriptor = self.artifact(key, artifact_id)
        if descriptor.get("kind") == "file":
            payload = self._file_payload(key, path)
            return {"descriptor": descriptor, "rows": [], "points": [], "format": payload["format"],
                    "files": [{"role": role, "name": Path(value).name,
                                 "downloadable": Path(value).resolve().is_relative_to((self.jobs_dir / key / "output").resolve()),
                               "bytes": payload["fingerprints"][role]["size"]}
                              for role, value in payload["files"].items()], "info": payload["info"]}
        import numpy as np
        data = np.load(path, mmap_mode="r", allow_pickle=False)
        if data.ndim != 2 or data.dtype.kind not in "biuf":
            return {"descriptor": descriptor, "rows": [], "points": []}
        rows = data[:20, :8].tolist()
        points = data[:200, :2].tolist() if data.shape[1] >= 2 else []
        del data
        return safe_json({"descriptor": descriptor, "rows": rows, "points": points})

    def _file_payload(self, key, path):
        payload = read_json(path)
        summary = self.details(key).get('summary') or {}
        for role, value in payload['files'].items():
            try:
                payload['files'][role] = str(self._record_path(key, value, summary))
            except KeyError:
                # External sources remain external and are never downloadable.
                pass
        return payload

    def artifact_file(self, key, artifact_id, role):
        path, descriptor = self.artifact(key, artifact_id)
        if descriptor.get("kind") != "file":
            raise KeyError("Not a file dataset")
        from src.core.files import FileArtifact
        artifact = FileArtifact(**self._file_payload(key, path))
        artifact.validate()
        if role not in artifact.files:
            raise KeyError("Unknown file role")
        # Download generated outputs only. Source references can point outside
        # the job, but the HTTP endpoint must not become an arbitrary file reader.
        target = Path(artifact.files[role]).resolve()
        if not target.is_relative_to((self.jobs_dir / key / "output").resolve()):
            raise KeyError("This file is an external input, not a downloadable job output")
        return target

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
