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

from scripts.desktop_server import bind_loopback
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def desktop_settings(workspace):
    return Settings(workspace, workspace / ".studio", ROOT / "frontend/dist",
                    testing=True, code_root=ROOT, desktop=True)


def test_draft_survives_server_restart_and_does_not_require_runnable_graph(tmp_path):
    settings = desktop_settings(tmp_path / "独立工作目录")
    with TestClient(create_app(settings)) as client:
        bootstrap = client.get("/api/bootstrap").json()
        assert bootstrap["desktop"] and bootstrap["draft"] is None
        draft = deepcopy(bootstrap["demo"])
        draft["name"] = "草稿 with spaces"
        draft["edges"] = []
        assert client.post("/api/draft", json=draft).status_code == 403
        client.headers["X-Studio-Token"] = bootstrap["token"]
        assert client.post("/api/draft", json=draft).status_code == 200
    with TestClient(create_app(settings)) as client:
        restored = client.get("/api/bootstrap").json()["draft"]
        assert restored["name"] == draft["name"] and restored["edges"] == []
        assert restored["nodes"][0]["source"]["path"].startswith(".studio/assets/")
    assert (settings.data_dir / "draft.json").is_file()
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
        assert preview.status_code == 200 and len(preview.json()["points"]) == 128
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/jobs").json()[0]["status"] == "complete"
    assert not (settings.root / "scripts").exists()


def test_preferred_port_conflict_falls_back_without_stealing_listener():
    with bind_loopback() as occupied, bind_loopback(occupied.getsockname()[1]) as fallback:
        assert fallback.getsockname()[0] == "127.0.0.1"
        assert fallback.getsockname()[1] != occupied.getsockname()[1]


@pytest.mark.skipif(not (ROOT / "frontend/dist/index.html").is_file(),
                    reason="frontend build artifacts are not present")
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
                if line.startswith("BIOPIPE_READY "):
                    url = json.loads(line[14:])["url"]
                    break
            assert url and not url.endswith(":" + str(occupied.getsockname()[1]))
            with httpx.Client(trust_env=False) as client:
                assert client.get(url + "/ready").json()["status"] == "ok"
                assert client.get(url).status_code == 200
                assert client.get(url + "/api/bootstrap").json()["desktop"]
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
