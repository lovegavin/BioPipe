"""Desktop lifecycle and writable-workspace integration, using the real engine."""
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from scripts.desktop_server import bind_loopback, report_stalled_shutdown
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_stalled_shutdown_reports_threads_only_until_backend_finishes(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr('faulthandler.dump_traceback', lambda **kwargs: calls.append(kwargs))
    finished = threading.Event()
    report_stalled_shutdown(finished, delay=0)
    assert len(calls) == 1 and calls[0]['all_threads']
    assert '[Operon shutdown]' in capsys.readouterr().err
    finished.set()
    report_stalled_shutdown(finished, delay=0)
    assert len(calls) == 1 and not capsys.readouterr().err


@pytest.mark.parametrize('phase', ['installer', 'bytecode'])
def test_backend_shutdown_cancels_dependency_preparation(tmp_path, phase):
    import psutil
    pid_file = tmp_path / 'installer-child.pid'
    child_code = ('import os,sys,time; from pathlib import Path; '
                  'Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)')
    parent_code = ('import subprocess,sys,time; from pathlib import Path; '
                   'subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]); '
                   'p=Path(sys.argv[2]); '
                   '\nwhile not p.exists(): time.sleep(.01)\n')
    if phase == 'bytecode':
        # Instrument only the compiler, in both the backend and any compiler
        # child. The production cancellation/ownership path stays unchanged.
        # A blocked single file catches both non-cancellable loops and designs
        # that only check cancellation between files.
        import operon.bytecode
        compiler = tmp_path / 'slow_compiler.py'
        release = tmp_path / 'release-compiler'
        compiler.write_text(f'''
import os as _os, time as _time, py_compile as _compiler
from pathlib import Path as _Path
_original_compile = _compiler.compile
def _blocked_compile(*args, **kwargs):
    _Path({str(pid_file)!r}).write_text(str(_os.getpid()))
    while not _Path({str(release)!r}).exists():
        _time.sleep(.02)
    return _original_compile(*args, **kwargs)
_compiler.compile = _blocked_compile
''' + Path(operon.bytecode.__file__).read_text(encoding='utf-8'), encoding='utf-8')
        target = tmp_path / 'synthetic-dependency'
        target.mkdir()
        (target / 'value.py').write_text('VALUE = 42\n', encoding='utf-8')
        setup = f'''import runpy, operon.bytecode
operon.bytecode.precompile = runpy.run_path({str(compiler)!r})['precompile']'''
        operation = f'operon.bytecode.precompile({str(target)!r})'
    else:
        setup = ''
        operation = f'run_process([sys.executable, "-c", {parent_code!r}, {child_code!r}, {str(pid_file)!r}])'
    bootstrap = tmp_path / 'installing_backend.py'
    bootstrap.write_text(f'''
import sys
sys.path.insert(0, {str(ROOT)!r})
from operon.dependencies import DependencySession
from operon.plugins import run_process
import operon.install_targets
{setup}
DependencySession._inspect = lambda self, state, entries: {{
    item['id']: {{'status': 'failed', 'error': 'Synthetic missing dependency'}} for item in entries}}
def repair(manager, state, entries):
    {operation}
    return state
operon.install_targets.repair_entries = repair
from scripts.desktop_server import main
main()
''', encoding='utf-8')
    environment = dict(os.environ, OPERON_DEPENDENCY_SCOPE='esm_embedding',
                       OPERON_RUNTIME_CONFIG=str(tmp_path / 'runtime.json'),
                       OPERON_ADMISSION_DIR=str(tmp_path / 'admission'), PYTHONUTF8='1')
    log_path = tmp_path / 'shutdown.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-u', str(bootstrap), '--workspace',
                                    str(tmp_path / 'workspace'), '--wait-for-host'],
                                   env=environment, stdin=subprocess.PIPE, stdout=log, stderr=log, text=True)
        try:
            process.stdin.write('start\n')
            process.stdin.flush()
            deadline = time.monotonic() + 30
            url = None
            while not url and time.monotonic() < deadline:
                assert process.poll() is None, log_path.read_text(encoding='utf-8')
                for line in log_path.read_text(encoding='utf-8').splitlines():
                    if line.startswith('OPERON_READY '):
                        url = json.loads(line.split(' ', 1)[1])['url']
                if not url:
                    time.sleep(.05)
            assert url, log_path.read_text(encoding='utf-8')
            # 3.0 startup must not install. Exercise cancellation only after an
            # explicit preparation request through the real desktop endpoint.
            assert not pid_file.exists()
            with httpx.Client(base_url=url, trust_env=False, timeout=10) as client:
                token = client.get('/api/bootstrap').json()['token']
                requested = client.post('/api/plugins/dependencies', headers={'X-Studio-Token': token})
                assert requested.status_code == 200, requested.text
            deadline = time.monotonic() + 30
            while not pid_file.exists() and time.monotonic() < deadline:
                assert process.poll() is None, log_path.read_text(encoding='utf-8')
                time.sleep(.05)
            assert pid_file.exists(), log_path.read_text(encoding='utf-8')
            time.sleep(.3)
            process.stdin.write('shutdown\n')
            process.stdin.close()
            assert process.wait(timeout=5) == 0, log_path.read_text(encoding='utf-8')
            assert not psutil.pid_exists(int(pid_file.read_text()))
            assert 'Application shutdown complete.' in log_path.read_text(encoding='utf-8')
        finally:
            if pid_file.exists():
                try:
                    child = psutil.Process(int(pid_file.read_text()))
                    if str(pid_file) in child.cmdline():
                        child.kill()
                except psutil.NoSuchProcess:
                    pass
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def desktop_settings(workspace):
    return Settings(workspace, workspace / ".studio", ROOT / "frontend/dist",
                    testing=True, code_root=ROOT, desktop=True)


def test_draft_survives_server_restart_and_does_not_require_runnable_graph(tmp_path):
    settings = desktop_settings(tmp_path / "独立工作目录")
    with TestClient(create_app(settings)) as client:
        bootstrap = client.get("/api/bootstrap").json()
        assert bootstrap["desktop"] and "draft" not in bootstrap
        draft = deepcopy(bootstrap["demo"])
        draft["name"] = "草稿 with spaces"
        draft["edges"] = []
        assert client.post("/api/workspace", json={"schema_version": 1, "active_id": "a", "documents": [{"id": "a", "graph": draft}]}).status_code == 403
        client.headers["X-Studio-Token"] = bootstrap["token"]
        assert client.post("/api/workspace", json={"schema_version": 1, "active_id": "a", "documents": [{"id": "a", "graph": draft}]}).status_code == 200
    with TestClient(create_app(settings)) as client:
        restored = client.get("/api/workspace").json()["documents"][0]["graph"]
        assert restored["name"] == draft["name"] and restored["edges"] == []
        assert restored["nodes"][0]["source"]["path"].startswith(".studio/assets/")
    assert not (settings.data_dir / "draft.json").exists()
    assert (settings.data_dir / "workflows/workspace.json").is_file()
    assert (settings.data_dir / "operators.json").is_file()


def test_worker_runs_from_separate_workspace_and_preserves_results(tmp_path):
    settings = desktop_settings(tmp_path / "Workspace with spaces 中文")
    with TestClient(create_app(settings)) as client:
        bootstrap = client.get("/api/bootstrap").json()
        client.headers["X-Studio-Token"] = bootstrap["token"]
        graph = bootstrap["demo"]
        graph["memory"] = {"enabled": True, "budget_mb": 64, "auto_spill": True, "keep": ["pcs"]}
        response = client.post("/api/jobs", json=graph)
        assert response.status_code == 202, response.text
        key = response.json()["id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{key}").json()
            if job["status"] != "running":
                break
            time.sleep(.1)
        assert job["status"] == "complete", job
        assert job["order"] == ["quality", "pca", "summary"]
        output = next(a for a in job["report"]["artifacts"] if a["name"] == "pcs")
        assert output["shape"] == [128, 2]
        assert Path(output["disk_uri"]).is_relative_to(settings.root)
        preview = client.get(f"/api/jobs/{key}/artifacts/{output['artifact_id']}/preview")
        assert preview.status_code == 200, preview.text
        assert len(preview.json()["points"]) == 128
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/jobs").json()[0]["status"] == "complete"
    assert not (settings.root / "scripts").exists()


def test_preferred_port_conflict_falls_back_without_stealing_listener():
    with bind_loopback() as occupied, bind_loopback(occupied.getsockname()[1]) as fallback:
        assert fallback.getsockname()[0] == "127.0.0.1"
        assert fallback.getsockname()[1] != occupied.getsockname()[1]


@pytest.mark.parametrize("exit_mode", ["shutdown", "eof"])
def test_desktop_server_owns_port_and_exits_with_host(tmp_path, exit_mode):
    workspace = tmp_path / "desktop process 中文"
    lines = queue.Queue()
    with bind_loopback() as occupied, open(tmp_path / "server.log", "w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "scripts/desktop_server.py"), "--workspace", str(workspace),
             "--port", str(occupied.getsockname()[1]), "--wait-for-host"],
            cwd=tmp_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        def collect():
            for line in process.stdout:
                lines.put(line)
        threading.Thread(target=collect, daemon=True).start()
        try:
            process.stdin.write("start\n")
            process.stdin.flush()
            deadline = time.monotonic() + 45
            url = None
            while time.monotonic() < deadline:
                try:
                    line = lines.get(timeout=.2)
                except queue.Empty:
                    assert process.poll() is None, (tmp_path / "server.log").read_text(encoding="utf-8")
                    continue
                if line.startswith("OPERON_READY "):
                    url = json.loads(line.split(" ", 1)[1])["url"]
                    break
            assert url and not url.endswith(":" + str(occupied.getsockname()[1]))
            with httpx.Client(trust_env=False) as client:
                assert client.get(url + "/ready").json()["status"] == "ok"
                assert client.get(url).status_code == 200
                bootstrap = client.get(url + "/api/bootstrap").json()
                assert bootstrap["desktop"]
                if exit_mode == "shutdown":
                    # Keep the actual host pipe open through the backend's first
                    # NumPy import. In-process TestClient runs preload NumPy and
                    # cannot expose a native import waiting on the stdin reader.
                    client.headers["X-Studio-Token"] = bootstrap["token"]
                    running = client.post(url + "/api/jobs", json=bootstrap["demo"])
                    assert running.status_code == 202, running.text
                    key = running.json()["id"]
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        job = client.get(url + "/api/jobs/" + key).json()
                        if job["status"] != "running":
                            break
                        time.sleep(.1)
                    assert job["status"] == "complete", job
                    output = next(a for a in job["report"]["artifacts"] if a["name"] == "pcs")
                    preview = client.get(url + f"/api/jobs/{key}/artifacts/{output['artifact_id']}/preview")
                    assert preview.status_code == 200 and len(preview.json()["points"]) == 128
                    exported = client.post(url + "/api/workflows/export", json=bootstrap["demo"])
                    assert exported.status_code == 200 and exported.content.startswith(b"PK")
            if exit_mode == "shutdown":
                process.stdin.write("shutdown\n")
                process.stdin.flush()
            process.stdin.close()
            assert process.wait(timeout=15) == 0
            with socket.socket() as connection:
                assert connection.connect_ex(("127.0.0.1", int(url.rsplit(":", 1)[1]))) != 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()


def test_safe_json_during_first_numpy_import(monkeypatch):
    from types import ModuleType
    from src.web.service import safe_json
    # Import inserts a module before its native types have initialized.
    monkeypatch.setitem(sys.modules, "numpy", ModuleType("numpy"))
    assert safe_json({"status": "running", "finished": None}) == {"status": "running", "finished": None}
