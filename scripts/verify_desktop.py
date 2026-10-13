"""Windows integration smoke: real host, WebView2, duplicate launch and crash cleanup."""
from __future__ import annotations

from datetime import datetime
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]


def wait_until(condition, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.1)
    raise AssertionError("Desktop verification timed out")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=ROOT / "dist/BioPipe Studio/BioPipe Studio.exe")
    executable = parser.parse_args().executable.resolve()
    profile = ROOT / ".verification" / ("desktop-lifecycle-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    profile.mkdir(parents=True)
    os.environ["BIOPIPE_RUNTIME_CONFIG"] = str(profile / "runtime.json")
    log = profile / "logs" / ("desktop-" + datetime.now().strftime("%Y%m%d") + ".log")
    def log_text():
        return log.read_text(encoding="utf-8-sig") if log.exists() else ""
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    command = [str(executable), "--data-dir", str(profile)]
    owned = []
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        (profile / "port.txt").write_text(str(occupied.getsockname()[1]))
        host = subprocess.Popen(command, cwd=profile, startupinfo=startup)
        try:
            wait_until(lambda: "Frontend ready" in log_text() or host.poll() is not None)
            assert host.poll() is None, log_text()
            port = int((profile / "port.txt").read_text())
            assert port != occupied.getsockname()[1]
            duplicate = subprocess.run(command + ["--smoke-test"], cwd=profile,
                                       startupinfo=startup, timeout=15)
            assert duplicate.returncode == 0 and log_text().count("Host starting;") == 1
            origin = f"http://127.0.0.1:{port}"
            with httpx.Client(base_url=origin, trust_env=False, timeout=10) as client:
                data = client.get("/api/bootstrap").json()
                client.headers["X-Studio-Token"] = data["token"]
                wait_until(lambda: bool(client.get("/api/agent/sessions").json()), seconds=20)
                sessions = client.get("/api/agent/sessions").json()
                context = client.get(f"/api/agent/sessions/{sessions[-1]['id']}/context?scope=document")
                assert context.status_code == 200 and context.json()["total_nodes"] == 4
                assert data["agent_config"]["args"][-1] == "mcp"
                result = client.post("/api/jobs", json=data["demo"])
                assert result.status_code == 202, result.text
                key = result.json()["id"]
            owned = [p for p in psutil.Process(host.pid).children(recursive=True) if "python" in p.name().lower()]
            assert len(owned) >= 3, "Expected backend plus an active worker"
            host.kill()  # Only this verification's host; Windows Job Object owns its children.
            host.wait(timeout=10)
            _, alive = psutil.wait_procs(owned, timeout=10)
            assert not alive, f"Leaked backend/worker processes: {[p.pid for p in alive]}"
            with socket.socket() as connection:
                assert connection.connect_ex(("127.0.0.1", port)) != 0
            reopened = subprocess.run(command + ["--smoke-test"], cwd=profile,
                                      startupinfo=startup, timeout=90)
            assert reopened.returncode == 0, log_text()
            record = json.loads((profile / "workspace/.studio/jobs" / key / "job.json").read_text(encoding="utf-8"))
            assert record["status"] in ("interrupted", "complete")
            assert "Draft flushed to workspace" in log_text() and "Host stopped" in log_text()
            assert (profile / "workspace/.studio/draft.json").is_file()
            result = {"status": "passed", "profile": str(profile), "checks": [
                "real WebView2 frontend bootstrap", "desktop agent session and context", "occupied port fallback", "single desktop instance",
                "active worker cleanup after host crash", "interrupted history recovery",
                "draft flush", "graceful backend shutdown"], "python_processes_reaped": len(owned)}
            (ROOT / ".verification/desktop-host-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
        finally:
            if host.poll() is None:
                host.kill()
                host.wait(timeout=10)


if __name__ == "__main__":
    main()
