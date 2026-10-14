"""Exercise source hot refresh through a copied, real Windows desktop release.

Run with the Python environment to test. The original release and user profile
are never modified; --output must name a new, preferably short directory.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import httpx
import psutil

MODULE = '''from biopipe_sdk import Step
class ReleaseRefresh(Step):
    name = "release.hot_refresh"
    title = "Release refresh check"
    category = "Quality control"
    icon = "CheckCircle"
    input_contracts = []
    output_contract = {"mode": "report"}
    parameters_schema = {"type": "object"}
    def run(self, ctx, inputs): pass
    def export(self, ctx): return {"value": VALUE}
'''


def poll(read, done, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read()
        if done(value):
            return value
        time.sleep(.2)
    raise AssertionError("Timed out waiting for desktop hot-refresh verification")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This acceptance check requires Windows and WebView2")
    executable = args.executable.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    application = output / "app"
    shutil.copytree(executable.parent, application)
    profile, temporary = output / "profile", output / "tmp"
    profile.mkdir()
    temporary.mkdir()
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("BIOPIPE_BACKEND_ROOT", "PYTHONPATH", "PYTHONHOME")}
    environment.update(BIOPIPE_PYTHON=sys.executable,
                       BIOPIPE_RUNTIME_CONFIG=str(output / "runtime.json"),
                       PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                       TEMP=str(temporary), TMP=str(temporary),
                       DOTNET_BUNDLE_EXTRACT_BASE_DIR=str(temporary / "bundle"))
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    host = subprocess.Popen([str(application / executable.name), "--data-dir", str(profile)],
                            cwd=temporary, env=environment, startupinfo=startup)
    checks = []
    try:
        def ready():
            logs = "\n".join(p.read_text(encoding="utf-8-sig") for p in (profile / "logs").glob("*.log"))
            assert host.poll() is None, logs
            return "Frontend ready" in logs
        poll(ready, bool)
        port = int((profile / "port.txt").read_text())
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=15) as client:
            def get(path):
                response = client.get(path)
                response.raise_for_status()
                return response.json()
            def post(path, body=None):
                response = client.post(path, json=body)
                response.raise_for_status()
                return response.json()
            bootstrap = get("/api/bootstrap")
            client.headers["X-Studio-Token"] = bootstrap["token"]
            assert bootstrap["desktop"]
            initial = get("/api/plugins")
            source_dir = Path(initial["source_directories"]["operator"])
            assert source_dir == application / "src/task/step/steps", source_dir
            original_ids = {d["id"] for d in initial["descriptors"]}
            checks.append("Real packaged WebView2 host and relocated source directory")
            source = source_dir / "release_hot_refresh.py"
            source.write_text(MODULE.replace("VALUE", "1"), encoding="utf-8")

            def refresh(success=True):
                started = post("/api/plugins/refresh")
                result = poll(lambda: get("/api/plugins/operations/" + started["id"]),
                              lambda item: item["status"] != "running", timeout=600)
                assert result["status"] == ("complete" if success else "failed"), result
                return result

            def run(graph):
                started = post("/api/jobs", graph)
                result = poll(lambda: get("/api/jobs/" + started["id"]),
                              lambda item: item["status"] != "running", timeout=120)
                assert result["status"] == "complete", result
                return result

            refresh()
            state = get("/api/plugins")
            assert original_ids <= {d["id"] for d in state["descriptors"]}
            descriptor = next(d for d in state["descriptors"] if d["id"] == "release.hot_refresh")
            assert descriptor["category"] == "Quality control" and descriptor["icon"] == "CheckCircle"
            assert "release.hot_refresh" in {d["id"] for d in get("/api/operators")["operators"]}
            checks.append("Plain author module discovered with metadata; original catalog retained")
            graph = {"name": "Hot refresh acceptance", "nodes": [{"id": "check", "kind": "operator",
                     "operator": "release.hot_refresh", "position": {"x": 0, "y": 0}}], "edges": [],
                     "memory": {"enabled": True, "budget_mb": 64}}
            pinned = deepcopy(graph)
            pinned["plugin_lock"] = {descriptor["id"]: descriptor["implementation"]}
            def value(job):
                data_dir = Path(bootstrap["storage"]["data_dir"])
                export = data_dir / "jobs" / job["id"] / "output" / job["summary"]["steps"][0]["export_path"]
                return json.loads(export.read_text(encoding="utf-8"))["value"]
            assert value(run(graph)) == 1
            source.write_text(MODULE.replace("VALUE", "2"), encoding="utf-8")
            refresh()
            assert value(run(graph)) == 2 and value(run(pinned)) == 1
            checks.append("Same-version source update runs new code; pinned graph runs old code")
            generation = get("/api/plugins")["generation"]
            assert refresh()["result"]["updated"] == []
            assert get("/api/plugins")["generation"] == generation
            source.write_text("class Broken(", encoding="utf-8")
            assert "release_hot_refresh.py" in refresh(False)["error"]
            assert get("/api/plugins")["generation"] == generation
            assert value(run(graph)) == 2
            checks.append("Unchanged scan skips rebuild; invalid edit keeps executable previous generation")
            demo = deepcopy(bootstrap["demo"])
            demo["memory"].update(enabled=True, budget_mb=64, keep=["pcs"])
            completed = run(demo)
            assert any(a["name"] == "pcs" and a["shape"] == [128, 2]
                       for a in completed["report"]["artifacts"])
            assert completed["report"]["event_counts"]
            checks.append("Existing branched PCA workflow, resource planning and persisted logs")
            assert host.poll() is None
            result = {"status": "passed", "version": get("/health")["studio"],
                      "python": sys.version, "executable": str(executable), "checks": checks}
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2), flush=True)
    finally:
        if host.poll() is None:
            children = psutil.Process(host.pid).children(recursive=True)
            host.kill()
            host.wait(timeout=15)
            _, alive = psutil.wait_procs(children, timeout=15)
            assert not alive, f"Test host leaked processes: {[p.pid for p in alive]}"


if __name__ == "__main__":
    main()
