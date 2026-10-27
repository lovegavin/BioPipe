"""Relocation checks use real subprocesses, paths with spaces, and independent cwd."""
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import httpx
import numpy as np
import pytest
import yaml

from src.web.api import create_app
from src.web.models import Graph
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def settings(workspace, code_root=ROOT):
    return Settings(workspace, workspace / ".studio", code_root / "frontend/dist",
                    testing=True, code_root=code_root, desktop=True)


def bootstrap(client):
    data = client.get("/api/bootstrap").json()
    client.headers["X-Studio-Token"] = data["token"]
    return data


def finished(client, key):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{key}")
        assert response.status_code == 200, response.text
        job = response.json()
        if job["status"] != "running":
            assert job["status"] == "complete", job
            return job
        time.sleep(.1)
    pytest.fail("Relocation worker did not finish")


def copy_code(destination):
    destination.mkdir(parents=True)
    for name in ("src", "scripts", "biopipe", "biopipe_sdk"):
        shutil.copytree(ROOT / name, destination / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    dist = ROOT / "frontend/dist"
    if dist.is_dir():
        shutil.copytree(dist, destination / "frontend/dist")


def test_dependency_manifests_do_not_reference_local_builds():
    for path in ROOT.glob("requirements*.txt"):
        content = path.read_text(encoding="utf-8-sig")
        assert "file:" not in content and "/home/" not in content and "feedstock_root" not in content
    environment = yaml.safe_load((ROOT / "environment.yml").read_text(encoding="utf-8-sig"))
    assert "prefix" not in environment
    assert not any("cuda" in str(dep) or "_libgcc_mutex" in str(dep) for dep in environment["dependencies"])


def test_active_source_has_no_developer_paths():
    from scripts.audit_portability import active_files, audit_files
    assert audit_files(active_files(ROOT), ROOT)["findings"] == []


def test_export_runs_after_moving_code_and_data_from_unrelated_cwd(tmp_path):
    original = tmp_path / "first checkout"
    original.mkdir()
    with TestClient(create_app(settings(original))) as client:
        graph = bootstrap(client)["demo"]
        graph["memory"].update(budget_mb=64, cache_dir="cache", keep=["pcs"])
        response = client.post("/api/export", json=graph)
        assert response.status_code == 200, response.text
        exported = response.json()["yaml"]
        manifest = yaml.safe_load(exported)
        assert not Path(manifest["sources"]["expression"]["path"]).is_absolute()
        assert manifest["runtime"]["memory"]["cache_dir"] == "cache"
        (original / "task.yaml").write_text(exported, encoding="utf-8")
    relocated = tmp_path / "搬迁 BioPipe"
    copy_code(relocated)
    shutil.copytree(original, relocated, dirs_exist_ok=True)
    # Remove the old usable location by renaming this test-owned directory only.
    retired = tmp_path / "retired checkout"
    assert original.resolve().parent == retired.resolve().parent == tmp_path.resolve()
    original.rename(retired)
    elsewhere = tmp_path / "unrelated cwd"
    elsewhere.mkdir()
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=str(tmp_path / "mpl"))
    result = subprocess.run([sys.executable, str(relocated / "scripts/run.py"), str(relocated)],
                            cwd=elsewhere, env=env, text=True, encoding="utf-8", capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((relocated / "output/run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
    report = json.loads(Path(summary["memory_report"]).read_text(encoding="utf-8"))
    pcs = next(a for a in report["artifacts"] if a["name"] == "pcs")
    assert Path(pcs["disk_uri"]).is_relative_to(relocated)
    assert np.load(Path(pcs["disk_uri"]) / "data.npy", allow_pickle=False).shape == (128, 2)
    assert not (retired / "output").exists()


def test_moved_workspace_keeps_history_arrays_figures_and_runnable_task(tmp_path):
    original = tmp_path / "old workspace"
    original.mkdir()
    with TestClient(create_app(settings(original))) as client:
        graph = bootstrap(client)["demo"]
        graph["memory"].update(budget_mb=64, keep=["pcs"], cache_dir="shared-cache")
        graph["nodes"].append({"id": "hist", "kind": "operator", "operator": "histogram", "position": {"x": 0, "y": 0},
                               "params": {"dim": "component", "value_label": "PC1", "filename": "pc1.png"}})
        graph["edges"].append({"id": "pca-hist", "source": "pca", "target": "hist", "targetHandle": "in-0"})
        assert client.post("/api/draft", json=graph).status_code == 200
        response = client.post("/api/jobs", json=graph)
        assert response.status_code == 202, response.text
        key = response.json()["id"]
        job = finished(client, key)
        pcs = next(a for a in job["report"]["artifacts"] if a["name"] == "pcs")
        array = client.get(f"/api/jobs/{key}/artifacts/{pcs['artifact_id']}/download").content
        figure = client.get(f"/api/jobs/{key}/exports/3/figure").content
        manifest = yaml.safe_load((original / ".studio/jobs" / key / "task.yaml").read_text(encoding="utf-8"))
        assert not Path(manifest["sources"]["expression"]["path"]).is_absolute()
    moved = tmp_path / "新电脑 workspace"
    assert original.resolve().parent == moved.resolve().parent == tmp_path.resolve()
    original.rename(moved)
    with TestClient(create_app(settings(moved))) as client:
        restored = bootstrap(client)
        assert restored["draft"] == Graph.model_validate(graph).model_dump(mode="json")
        assert client.get("/api/jobs").json()[0]["status"] == "complete"
        response = client.get(f"/api/jobs/{key}")
        assert response.status_code == 200, response.text
        new_pcs = next(a for a in response.json()["report"]["artifacts"] if a["name"] == "pcs")
        assert Path(new_pcs["disk_uri"]).is_relative_to(moved)
        assert client.get(f"/api/jobs/{key}/artifacts/{pcs['artifact_id']}/download").content == array
        assert client.get(f"/api/jobs/{key}/artifacts/{pcs['artifact_id']}/preview").status_code == 200
        assert client.get(f"/api/jobs/{key}/exports/3/figure").content == figure
        response = client.post("/api/jobs", json=restored["draft"])
        assert response.status_code == 202, response.text
        finished(client, response.json()["id"])


@pytest.mark.parametrize("old", [PurePosixPath("/tmp/previous/workspace"), PureWindowsPath("Z:/previous/workspace")])
def test_historical_paths_rebase_across_os_without_allowing_escape(tmp_path, old):
    app = create_app(settings(tmp_path))
    service = app.state.service
    old_task = old / ".studio/jobs/run1"
    summary = {"task_dir": str(old_task)}
    path = service._record_path("run1", str(old_task / "output/runs/run1/memory_report.json"), summary)
    assert path == tmp_path / ".studio/jobs/run1/output/runs/run1/memory_report.json"
    with pytest.raises(KeyError):
        service._record_path("run1", str(old.parent / "outside.npy"), summary)
    with pytest.raises(KeyError):
        service._record_path("run1", "../../../../outside.npy", summary)


@pytest.mark.skipif(not (ROOT / "frontend/dist/index.html").is_file(),
                    reason="frontend build artifacts are not present")
def test_desktop_worker_completes_with_host_control_pipe_open(tmp_path):
    """A worker must start while the backend is blocked reading host commands."""
    workspace = tmp_path / "workspace"
    temporary = tmp_path / "tmp"
    temporary.mkdir()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               TEMP=str(temporary), TMP=str(temporary))
    log_path = tmp_path / "desktop-backend.log"
    with log_path.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-B", "-u", str(ROOT / "scripts/desktop_server.py"),
             "--workspace", str(workspace), "--frontend", str(ROOT / "frontend/dist"), "--wait-for-host"],
            cwd=tmp_path, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            server.stdin.write("start\n")
            server.stdin.flush()
            deadline = time.monotonic() + 30
            origin = None
            while time.monotonic() < deadline:
                content = log_path.read_text(encoding="utf-8")
                assert server.poll() is None, content
                for line in content.splitlines():
                    if line.startswith("BIOPIPE_READY "):
                        origin = json.loads(line.removeprefix("BIOPIPE_READY "))["url"]
                if origin:
                    break
                time.sleep(.1)
            assert origin, log_path.read_text(encoding="utf-8")
            with httpx.Client(base_url=origin, trust_env=False, timeout=10) as client:
                data = bootstrap(client)
                graph = data["demo"]
                graph["memory"].update(budget_mb=64, keep=["pcs"])
                response = client.post("/api/jobs", json=graph)
                assert response.status_code == 202, response.text
                job = finished(client, response.json()["id"])
                assert not server.stdin.closed  # Keep the real command pipe open throughout the run.
                pcs = next(a for a in job["report"]["artifacts"] if a["name"] == "pcs")
                assert pcs["shape"] == [128, 2]
        finally:
            if server.poll() is None:
                server.stdin.write("shutdown\n")
                server.stdin.flush()
            server.stdin.close()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                import psutil
                for child in reversed(psutil.Process(server.pid).children(recursive=True)):
                    child.kill()
                server.kill()
                server.wait(timeout=5)
        assert server.returncode == 0, log_path.read_text(encoding="utf-8")
