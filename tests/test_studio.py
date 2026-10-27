"""Visual graph compilation and real local-worker API integration."""
from copy import deepcopy
import json
from pathlib import Path
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import numpy as np
import pytest
import yaml

from src.task import Context, STEPS, load_manifest
from src.task.operator_catalog import build_catalog
from src.web.api import create_app
from src.web.graph import GraphError, compile_graph, import_manifest
from src.web.models import Graph
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def studio(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / "s", ROOT / "frontend/dist", testing=True, code_root=ROOT))
    with TestClient(app) as client:
        data = client.get("/api/bootstrap").json()
        client.headers["X-Studio-Token"] = data["token"]
        yield client, data


def test_graph_fixed_order_branch_and_multiport(studio):
    client, data = studio
    graph = deepcopy(data["demo"])
    valid = client.post("/api/validate", json=graph)
    assert valid.status_code == 200
    assert valid.json()["order"] == ["quality", "pca", "summary"]
    graph["nodes"].append({"id": "join", "kind": "operator", "operator": "concat", "position": {"x": 0, "y": 0},
                            "input_count": 2, "params": {"axis": "component", "output": "combined"}})
    for i in (1, 0):
        graph["edges"].append({"id": f"join-{i}", "source": "pca", "target": "join", "targetHandle": f"in-{i}"})
    value = client.post("/api/export", json=graph)
    assert value.status_code == 200
    manifest = yaml.safe_load(value.json()["yaml"])
    assert manifest["steps"][-1]["inputs"] == ["pcs", "pcs"]
    assert manifest["steps"][-1]["name"] == "concat"


def test_graph_located_errors_and_file_boundary(studio):
    client, data = studio
    missing = deepcopy(data["demo"])
    missing["edges"].pop()
    response = client.post("/api/validate", json=missing)
    assert response.status_code == 422 and response.json()["node_id"] == "summary"
    bad = deepcopy(data["demo"])
    bad["nodes"][0]["source"]["path"] = "../outside.csv"
    assert client.post("/api/validate", json=bad).status_code == 422
    bad = deepcopy(data["demo"])
    bad["memory"]["keep"] = ["unknown"]
    assert client.post("/api/validate", json=bad).status_code == 422
    bad = deepcopy(data["demo"])
    bad["edges"] = [e for e in bad["edges"] if e["target"] != "quality"]
    bad["edges"].append({"id": "cycle", "source": "pca", "target": "quality", "targetHandle": "in-0"})
    response = client.post("/api/validate", json=bad)
    assert response.status_code == 422 and "环路" in response.json()["message"]
    bad = deepcopy(data["demo"])
    bad["nodes"][2]["params"]["n_components"] = 0
    assert client.post("/api/validate", json=bad).status_code == 422


def test_yaml_import_preserves_inplace_versions_and_native_defaults(tmp_path):
    catalog = build_catalog(STEPS)
    original = {"sources": {"X": {"path": "data.csv", "dims": ["sample", "feature"]}},
                "steps": [{"name": "missing", "inputs": ["X"], "params": {"dim": "feature", "output": "X"}},
                          {"name": "pca", "inputs": ["X"], "params": {"dim": "feature"}},
                          {"name": "describe", "inputs": ["X"]}], "runtime": {"memory": {"keep": ["X"]}}}
    graph = import_manifest(yaml.safe_dump(original), ".", catalog, tmp_path)
    manifest, order = compile_graph(graph, catalog, tmp_path)
    assert manifest["steps"][0]["params"]["threshold"] == .1
    assert manifest["steps"][1]["params"]["n_components"] == 10
    assert manifest["steps"][0]["inputs"] == [graph.nodes[0].id]
    alias = manifest["steps"][0]["params"]["output"]
    assert manifest["steps"][1]["inputs"] == [alias]
    assert manifest["steps"][2]["inputs"] == [alias]
    assert manifest["runtime"]["memory"]["keep"] == [alias]
    assert len(order) == 3


def test_only_run_start_scans_available_memory(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("psutil.virtual_memory", lambda: calls.append(1) or SimpleNamespace(available=1024**3))
    raw = {"sources": {"X": {"path": "data.csv", "dims": ["sample", "feature"]}},
           "steps": [{"name": "describe", "inputs": ["X"]}], "runtime": {"memory": {"enabled": True}}}
    path = tmp_path / "task.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    manifest = load_manifest(path)
    catalog = build_catalog(STEPS)
    graph = import_manifest(path.read_text(), ".", catalog, tmp_path)
    compile_graph(graph, catalog, tmp_path)
    assert calls == []
    ctx = Context(tmp_path, manifest)
    assert calls == [1] and ctx.memory.config.budget_bytes == int(1024**3 * .9)
    assert ctx.memory.config.available_at_start_bytes == 1024**3
    ctx.memory.configure([], STEPS)
    ctx.memory.close("failed")
    assert calls == [1]
    assert ctx.memory.report["available_at_start_bytes"] == 1024**3
    started = json.loads(ctx.memory.event_path.read_text(encoding="utf-8").splitlines()[0])
    assert started["available_at_start_bytes"] == 1024**3
    assert started["budget_bytes"] == int(1024**3 * .9)


def test_bootstrap_publishes_memory_policy_without_scanning(studio, monkeypatch):
    client, _ = studio
    monkeypatch.setattr("psutil.virtual_memory", lambda: pytest.fail("bootstrap must not scan RAM"))
    assert client.get("/api/bootstrap").json()["automatic_memory_fraction"] == .9


def test_startup_budget_preview_is_cached_and_has_no_fixed_cap(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("psutil.virtual_memory", lambda: calls.append(1) or SimpleNamespace(available=128 * 1024**3))
    app = create_app(Settings(tmp_path, tmp_path / "s", ROOT / "frontend/dist", testing=True, code_root=ROOT))
    with TestClient(app) as client:
        for _ in range(2):
            data = client.get("/api/bootstrap").json()
            assert data["automatic_memory_budget_bytes"] == int(128 * 1024**3 * .9)
    assert calls == [1]


def test_unavailable_memory_preview_does_not_invent_a_budget(tmp_path, monkeypatch):
    def unavailable():
        raise OSError("scanner unavailable")
    monkeypatch.setattr("psutil.virtual_memory", unavailable)
    app = create_app(Settings(tmp_path, tmp_path / "s", ROOT / "frontend/dist", testing=True, code_root=ROOT))
    with TestClient(app) as client:
        assert client.get("/api/bootstrap").json()["automatic_memory_budget_bytes"] is None


def test_session_token_and_streamed_upload(studio):
    client, data = studio
    response = client.post("/api/validate", json=data["demo"], headers={"X-Studio-Token": "invalid"})
    assert response.status_code == 403
    upload = client.post("/api/assets?filename=test.csv", content=b"a,b\n1,2\n3,4\n", headers={"Content-Type": "application/octet-stream"})
    assert upload.status_code == 200
    assert (client.app.state.service.root / upload.json()["path"]).read_bytes() == b"a,b\n1,2\n3,4\n"
    assert client.post("/api/assets?filename=code.py", content=b"print('x')").status_code == 422


def test_worker_can_be_cancelled_and_second_run_is_admitted_or_queued(studio):
    client, data = studio
    response = client.post("/api/jobs", json=data["demo"])
    assert response.status_code == 202
    key = response.json()["id"]
    second = client.post("/api/jobs", json=data["demo"])
    assert second.status_code == 202
    assert second.json()['status'] in ('running', 'queued')
    response = client.post(f"/api/jobs/{key}/cancel", json={})
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and key in client.app.state.service.processes:
        time.sleep(.05)
    assert key not in client.app.state.service.processes
    client.post(f"/api/jobs/{second.json()['id']}/cancel", json={})


def test_real_worker_branch_result_preview_history_and_events(studio):
    client, data = studio
    graph = deepcopy(data["demo"])
    graph["nodes"][2]["params"]["n_components"] = 3
    graph["memory"] = {"enabled": True, "auto_spill": True, "budget_mb": 16}
    response = client.post("/api/jobs", json=graph)
    assert response.status_code == 202
    key = response.json()["id"]
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{key}").json()
        if job["status"] != "running":
            break
        time.sleep(.15)
    assert job["status"] == "complete", job
    assert job["order"] == ["quality", "pca", "summary"]
    assert job["report"]["budget_bytes"] == 16 * 1024**2
    pcs = next(a for a in job["report"]["artifacts"] if a["name"] == "pcs")
    assert pcs["shape"] == [128, 3] and pcs["disk_uri"]
    preview = client.get(f"/api/jobs/{key}/artifacts/{pcs['artifact_id']}/preview").json()
    matrix = np.load(Path(pcs["disk_uri"]) / "data.npy", allow_pickle=False)
    assert len(preview["points"]) == 128 and len(preview["rows"]) == 20
    np.testing.assert_allclose(preview["rows"], matrix[:20, :8])
    report = client.get(f"/api/jobs/{key}/exports/1").json()
    assert report["n_components"] == 3 and len(report["explained_variance_ratio"]) == 3
    assert client.get("/api/jobs").json()[0]["id"] == key
    response = client.get(f"/api/jobs/{key}/events")
    assert response.status_code == 200 and '"done": true' in response.text
    assert '"event": "step_finished"' in response.text and '"event": "run_started"' in response.text
    assert client.get(f"/api/jobs/{key}/artifacts/{pcs['artifact_id']}/download").content.startswith(b"\x93NUMPY")


def test_plot_and_one_component_pca_work_in_studio(studio):
    client, data = studio
    graph = deepcopy(data["demo"])
    graph["nodes"][2]["params"]["n_components"] = 1
    graph["memory"]["budget_mb"] = 32
    graph["nodes"].append({"id": "hist", "kind": "operator", "operator": "histogram", "position": {"x": 0, "y": 0},
                            "params": {"dim": "component", "value_label": "PC1", "filename": "pc1.png"}})
    graph["edges"].append({"id": "pca-hist", "source": "pca", "target": "hist", "targetHandle": "in-0"})
    response = client.post("/api/jobs", json=graph)
    assert response.status_code == 202
    key = response.json()["id"]
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{key}").json()
        if job["status"] != "running":
            break
        time.sleep(.15)
    assert job["status"] == "complete", job
    image = client.get(f"/api/jobs/{key}/exports/3/figure")
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    assert client.get(f"/api/jobs/{key}/exports/1/download").json()["n_components"] == 1
