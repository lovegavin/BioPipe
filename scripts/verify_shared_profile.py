"""Verify exe and both Python entrypoints share a profile and live route index.

All writes are in an isolated verification directory, never the user's profile.
Also compares the three default path diagnostics, which do not mutate files.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    test = ROOT / ".verification" / ("shared-profile-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    unrelated = test / "unrelated cwd 中文"
    unrelated.mkdir(parents=True)
    profile = test / "shared data 中文"
    exe = ROOT / "dist/BioPipe Studio/BioPipe Studio.exe"
    env = {key: value for key, value in os.environ.items() if key not in ("BIOPIPE_STUDIO_HOME", "BIOPIPE_STUDIO_DATA")}
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0

    def command(args):
        result = subprocess.run(args, cwd=unrelated, env=env, capture_output=True, text=True,
                                encoding="utf-8", startupinfo=startup, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def paths():
        desktop = json.loads(command([str(exe), "--check-profile"]))
        python = [json.loads(command([sys.executable, "-B", str(ROOT / "scripts" / name), "--resolve-profile"]))
                  for name in ("studio.py", "desktop_server.py")]
        assert python[0] == python[1]
        assert desktop["ProfileDir"] == python[0]["profile_dir"]
        assert desktop["Workspace"] == python[0]["workspace"]
        assert desktop["Registry"] == python[0]["registry"]
        return desktop

    defaults = paths()
    env["BIOPIPE_STUDIO_HOME"] = str(profile)
    custom = paths()
    assert Path(custom["ProfileDir"]) == profile
    print("All three launchers resolved identical default and overridden profiles", flush=True)
    processes = []
    clients = []
    try:
        # The desktop entrypoint owns an ephemeral loopback socket and announces
        # it on stdout. stdin is its supported graceful shutdown interface.
        backend = subprocess.Popen([sys.executable, "-B", "-u", str(ROOT / "scripts/desktop_server.py"), "--wait-for-host"],
            cwd=unrelated, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=(test / "desktop-backend.log").open("w"),
            text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(backend)
        lines = queue.Queue()
        def collect():
            for line in backend.stdout:
                lines.put(line)
        threading.Thread(target=collect, daemon=True).start()
        backend.stdin.write("start\n"); backend.stdin.flush()
        deadline = time.monotonic() + 45
        desktop_url = None
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=.2)
            except queue.Empty:
                assert backend.poll() is None
                continue
            if line.startswith("BIOPIPE_READY "):
                desktop_url = json.loads(line[14:])["url"]
                break
        assert desktop_url
        with socket.socket() as port:
            port.bind(("127.0.0.1", 0))
            number = port.getsockname()[1]
        preview = subprocess.Popen([sys.executable, "-B", "-u", str(ROOT / "scripts/studio.py"), "--port", str(number)],
            cwd=unrelated, env=env, stdin=subprocess.DEVNULL, stdout=(test / "development.log").open("w"),
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(preview)
        clients = [httpx.Client(base_url=url, trust_env=False, timeout=10) for url in (desktop_url, f"http://127.0.0.1:{number}")]
        bootstraps = []
        for client in clients:
            deadline = time.monotonic() + 45
            while True:
                try:
                    data = client.get("/api/bootstrap").raise_for_status().json()
                    break
                except httpx.ConnectError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(.1)
            client.headers["X-Studio-Token"] = data["token"]
            bootstraps.append(data)
        assert bootstraps[0]["desktop"] and not bootstraps[1]["desktop"]
        assert bootstraps[0]["storage"]["registry"] == bootstraps[1]["storage"]["registry"] == custom["Registry"]
        baseline = len(clients[0].get("/api/routes").json())
        bundled_routes = json.loads((ROOT / "src/web/builtin_routes.json").read_text(encoding="utf-8"))["routes"]
        assert baseline == len(bundled_routes)
        for client, name in zip(clients, ("Desktop registered", "Development registered")):
            graph = {**bootstraps[0]["demo"], "name": name}
            saved = client.post("/api/workflows/save", json={"graph": graph}).raise_for_status().json()
            client.post("/api/routes/register", json={"workflow_ids": [saved["id"]]}).raise_for_status()
        assert clients[0].get("/api/routes").json() == clients[1].get("/api/routes").json()
        assert len(clients[0].get("/api/routes").json()) == baseline + 2
        print("Desktop/development APIs share both registered routes without a restart", flush=True)
        backend.stdin.write("shutdown\n"); backend.stdin.flush(); backend.wait(15)
        assert backend.returncode == 0
        command([str(exe), "--smoke-test"])
        command([str(exe), "--smoke-test"])
        assert len(json.loads(Path(custom["Registry"]).read_text(encoding="utf-8"))) == baseline + 2
        assert len(clients[1].get("/api/routes").json()) == baseline + 2
        log = next((profile / "logs").glob("desktop-*.log")).read_text(encoding="utf-8-sig")
        launches = log.split("Host starting;")[1:]
        assert len(launches) == 2
        assert all("Frontend ready" in launch and "Host stopped" in launch for launch in launches)
        result = {"status": "passed", "default": defaults, "isolated": custom,
                  "registered_routes": baseline + 2, "native_smoke_runs": 2,
                  "checks": ["three launcher path equality", "cwd independence", "shared env override",
                             "two live API processes", "cross-process route reload", "native restart persistence"]}
        (ROOT / ".verification/shared-profile-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    finally:
        for client in clients:
            client.close()
        for process in processes:
            if process.poll() is None:
                process.terminate(); process.wait(10)


if __name__ == "__main__":
    main()
