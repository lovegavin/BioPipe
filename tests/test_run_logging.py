"""Real worker failures and deterministic SSE completion boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import pytest

from src.web.api import create_app
from src.web.service import Settings, write_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def studio(tmp_path):
    settings = Settings(tmp_path, tmp_path / "s", ROOT / "frontend/dist", testing=True, code_root=ROOT)
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        data = client.get("/api/bootstrap").json()
        client.headers["X-Studio-Token"] = data["token"]
        yield client, data, app.state.service


def wait_job(client, key):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{key}").json()
        if job["status"] != "running" and job.get("logs_complete", True):
            return job
        time.sleep(.05)
    pytest.fail("Worker did not reach a terminal state")


def updates(client, key):
    response = client.get(f"/api/jobs/{key}/events")
    assert response.status_code == 200, response.text
    payloads = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert payloads[-1]["done"] is True
    return payloads


def test_spawn_failure_is_a_persisted_job_with_console_and_events(studio, monkeypatch):
    client, data, service = studio
    monkeypatch.setattr(service.plugins, "python_for", lambda _: str(service.root / "missing-python.exe"))
    response = client.post("/api/jobs", json=data["demo"])
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "failed" and job["finished_at"] and job["logs_complete"]
    console = client.get(f"/api/jobs/{job['id']}/console").text
    assert "FileNotFoundError" in console and "missing-python" in console
    payloads = updates(client, job["id"])
    assert any(e.get("error") for p in payloads for e in p["events"])
    assert any("FileNotFoundError" in (p.get("console") or "") for p in payloads)


def test_silent_worker_exit_keeps_exit_code_and_nonempty_console(studio):
    client, data, service = studio
    code = service.root / "silent"
    (code / "scripts").mkdir(parents=True)
    (code / "scripts/run.py").write_text("import os\nos._exit(7)\n", encoding="utf-8")
    service.settings.code_root = code
    key = client.post("/api/jobs", json=data["demo"]).json()["id"]
    job = wait_job(client, key)
    assert job["status"] == "failed" and job["exit_code"] == 7
    assert "7" in job["error"] and "summary" in job["error"].lower()
    before = client.get(f"/api/jobs/{key}/console").content
    assert b"exit code 7" in before
    assert any(e.get("error") for p in updates(client, key) for e in p["events"])
    # A fresh service must read the persisted evidence without relying on RAM.
    with TestClient(create_app(service.settings)) as reopened:
        assert reopened.get(f"/api/jobs/{key}/console").content == before
        assert reopened.get(f"/api/jobs/{key}").json()["exit_code"] == 7


def test_cli_records_failure_before_engine_import(tmp_path):
    code = tmp_path / "code"
    for name in ("scripts", "src/task", "biopipe"):
        (code / name).mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/run.py", code / "scripts/run.py")
    shutil.copy2(ROOT / "biopipe/__init__.py", code / "biopipe/__init__.py")
    if (ROOT / "biopipe/run_log.py").exists():
        shutil.copy2(ROOT / "biopipe/run_log.py", code / "biopipe/run_log.py")
    (code / "src/__init__.py").write_text("", encoding="utf-8")
    (code / "src/task/__init__.py").write_text("raise RuntimeError('bootstrap sentinel')\n", encoding="utf-8")
    task = tmp_path / "task"
    task.mkdir()
    process = subprocess.run([sys.executable, str(code / "scripts/run.py"), str(task)],
                             cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert process.returncode != 0 and "bootstrap sentinel" in process.stderr
    summary = json.loads((task / "output/run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed" and "bootstrap sentinel" in summary["error"]
    events = [json.loads(line) for line in Path(summary["event_log"]).read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event"] == "run_finished" and "bootstrap sentinel" in events[-1]["error"]


def test_memory_disabled_still_records_sources_and_steps(studio):
    client, data, _ = studio
    graph = deepcopy(data["demo"])
    graph["memory"] = {"enabled": False}
    key = client.post("/api/jobs", json=graph).json()["id"]
    job = wait_job(client, key)
    assert job["status"] == "complete", job
    events = [e for p in updates(client, key) for e in p["events"]]
    assert any(e["event"] == "source_loaded" for e in events)
    assert sum(e["event"] == "step_finished" for e in events) == 3
    assert any(e["event"] == "run_finished" and e["status"] == "complete" for e in events)
    assert job["summary"]["event_log"] and job["report"] is None


@pytest.mark.parametrize("initial_event", [False, True])
def test_sse_drains_events_created_at_the_completion_boundary(studio, monkeypatch, initial_event):
    client, _, service = studio
    key = "race"
    directory = service.jobs_dir / key
    path = directory / "output/runs/race/events.jsonl"
    path.parent.mkdir(parents=True)
    first = {"time": "2026-10-14T00:00:00+00:00", "event": "run_started"}
    last = {"time": "2026-10-14T00:00:01+00:00", "event": "run_finished", "error": "terminal sentinel"}
    if initial_event:
        path.write_text(json.dumps(first) + "\n", encoding="utf-8")
    job = {"id": key, "status": "running", "graph": {}, "order": [], "created_at": first["time"]}
    write_json(directory / "job.json", job)
    called = False
    def finish_during_status_read(_):
        nonlocal called
        if not called:
            path.write_text(json.dumps(first) + "\n" + json.dumps(last) + "\n", encoding="utf-8")
            called = True
        return {**job, "status": "failed", "error": last["error"], "logs_complete": True}
    monkeypatch.setattr(service, "details", finish_during_status_read)
    events = [e for p in updates(client, key) for e in p["events"]]
    assert events == [first, last]


def test_historical_empty_console_reports_what_was_recorded(studio):
    client, _, service = studio
    key = "old-empty"
    directory = service.jobs_dir / key
    directory.mkdir()
    (directory / "console.log").touch()
    write_json(directory / "job.json", {"id": key, "name": "old run", "status": "failed", "order": [],
               "created_at": "2026-10-14T00:00:00+00:00", "error": "recorded failure", "finished_at": None})
    response = client.get(f"/api/jobs/{key}/console")
    assert response.status_code == 200 and "recorded failure" in response.text
    assert "No worker output" in response.text
    assert (directory / "console.log").read_bytes() == b""  # Do not invent historical evidence.


def test_sse_drains_large_log_and_final_unterminated_row(studio):
    client, _, service = studio
    key = "many-events"
    directory = service.jobs_dir / key
    path = directory / "output/runs/large/events.jsonl"
    path.parent.mkdir(parents=True)
    rows = [{"event": "operator_log", "time": "2026-10-14T00:00:00Z", "message": str(i)} for i in range(451)]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    write_json(directory / "job.json", {"id": key, "status": "complete", "logs_complete": True})
    assert [e for p in updates(client, key) for e in p["events"]] == rows


def test_cancelled_job_waits_for_worker_log_flush(studio, monkeypatch):
    client, _, service = studio
    key = "cancel-drain"
    directory = service.jobs_dir / key
    directory.mkdir()
    job = {"id": key, "status": "cancelled", "logs_complete": False}
    write_json(directory / "job.json", job)
    calls = 0
    def finish(_):
        nonlocal calls
        calls += 1
        if calls == 2:
            (directory / "launcher.events.jsonl").write_text(json.dumps({"event": "worker_finished", "time": "2026-10-14T00:00:00Z"}) + "\n")
        return {**job, "logs_complete": calls >= 2}
    monkeypatch.setattr(service, "details", finish)
    payloads = updates(client, key)
    assert payloads[0]["done"] is False
    assert payloads[-1]["events"][0]["event"] == "worker_finished"


def test_console_tail_does_not_truncate_download_or_repeat_unchanged_content(studio):
    client, _, service = studio
    key = "large-console"
    directory = service.jobs_dir / key
    directory.mkdir()
    job = {"id": key, "status": "failed", "error": "sentinel"}
    write_json(directory / "job.json", job)
    content = b"start\n" + b"x" * 100_000 + b"\nfinal error"
    (directory / "console.log").write_bytes(content)
    signature, result = service.console_snapshot(key, job)
    assert result["console_truncated"] and result["console"].endswith("final error")
    assert len(result["console"]) == 64 * 1024
    assert service.console_snapshot(key, job, signature)[1] is None
    assert client.get(f"/api/jobs/{key}/console").content == content


def test_context_operator_logs_without_memory_runtime(tmp_path):
    from src.task import Context
    context = Context(tmp_path, {"sources": {}, "steps": [], "runtime": {"memory": {"enabled": False}}})
    context.log("operator message", rows=4)
    context._run_status = "complete"
    context.finalize()
    rows = [json.loads(line) for line in context.run_log.event_path.read_text(encoding="utf-8").splitlines()]
    assert any(row["event"] == "operator_log" and row["message"] == "operator message" and row["rows"] == 4 for row in rows)
    assert context.run_log.stream.closed
