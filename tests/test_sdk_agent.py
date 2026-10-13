"""Public protocol, transactional agent edits and real plugin/worker integration."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from biopipe_sdk import Form, Operator, port, project_metadata
from biopipe_sdk.protocol import Descriptor, validate_parameters
from biopipe_sdk.testing import run_operator
from src.task import STEPS
from src.task.operator_catalog import build_catalog
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gateway(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / ".studio", ROOT / "frontend/dist", testing=True, code_root=ROOT, desktop=True))
    with TestClient(app) as client:
        data = client.get("/api/bootstrap").json()
        client.headers["X-Studio-Token"] = data["token"]
        workspace = {"schema_version": 1, "active_id": "page_a", "documents": [{"id": "page_a", "graph": data["demo"]}]}
        state = client.post("/api/agent/sessions", json={"workspace": workspace}).json()
        yield client, app, data, state


def test_all_legacy_descriptors_are_public_and_preserve_names():
    catalog = build_catalog(STEPS)
    assert len(catalog["operators"]) == len(STEPS) == 46 and len(catalog["readers"]) == 13
    assert {d["id"] for d in catalog["operators"]} == set(STEPS)
    for descriptor in catalog["operators"] + catalog["readers"]:
        assert Descriptor.model_validate(descriptor).protocol_version == 1
        assert descriptor["contracts"]["output"] is not None
        assert descriptor["entry_point"].count(":") == 1
    assert next(d for d in catalog["operators"] if d["id"] == "pca")["output_parameter"] == "output"


class Shift(Operator):
    name = "tests.shift"
    input_contracts = [port(ndim=2)]
    output_contract = {"mode": "transform", "representation": "shifted"}
    parameters_schema = {"type": "object", "properties": {"offset": {"type": "number", "minimum": 0, "default": 1}}, "additionalProperties": False}

    def compute(self, inputs, params, context):
        form = inputs[0]
        info, axes = project_metadata(form, derived=True)
        info.update(representation="shifted", missing_code=float("nan"))
        context.log("Shift computed", rows=form.data.shape[0])
        return Form(data=form.data + params["offset"], dims=form.dims, labels=form.labels, info=info, axis_info=axes)


def test_sdk_executes_real_contracts_and_defaults():
    form = Form(data=np.array([[1., 2.]]), dims=["sample", "feature"],
                labels={"sample": {"a": 0}, "feature": {"x": 0, "y": 1}},
                info={"missing_code": np.nan, "group": np.array(["A"])}, axis_info={"sample": ["group"]})
    output = run_operator(Shift, [form])
    np.testing.assert_array_equal(output.data, [[2., 3.]])
    assert output.axis_info == {"sample": ["group"]}
    np.testing.assert_array_equal(form.data, [[1., 2.]])
    with pytest.raises(ValueError, match="minimum"):
        run_operator(Shift, [form], {"offset": -2})
    with pytest.raises(ValueError, match="Additional properties"):
        run_operator(Shift, [form], {"typo": 1})
    class Lying(Shift):
        output_contract = {"mode": "declare", "schema": {"ndim": 3}}
    with pytest.raises(Exception, match="contract"):
        run_operator(Lying, [form])


def test_parameter_schema_never_fetches_remote_references():
    with pytest.raises(ValueError, match="local JSON Schema"):
        validate_parameters({"type": "object", "properties": {"a": {"$ref": "https://invalid.example/schema"}}}, {})


def test_union_parameters_and_large_generated_graph():
    from biopipe_sdk.protocol import schema_to_fields
    from biopipe.documents import layout
    fields = schema_to_fields({"type": "object", "properties": {"value": {"type": ["number", "null"]}}})
    assert fields[0]["type"] == "number"
    graph = {"nodes": [{"id": f"n{i}"} for i in range(1000)],
             "edges": [{"source": f"n{i}", "target": f"n{i+1}"} for i in range(999)]}
    assert layout(graph)["nodes"][-1]["position"]["x"] == 60 + 999 * 300


def test_public_schema_files_match_live_models():
    from src.web.models import Graph, Workspace
    for name, cls in {"operator": Descriptor, "graph": Graph, "workspace": Workspace}.items():
        assert json.loads((ROOT / "biopipe_sdk/schemas" / f"{name}.json").read_text(encoding="utf-8")) == cls.model_json_schema()


def test_selection_scope_and_ui_revision(gateway):
    client, app, data, state = gateway
    url = f"/api/agent/sessions/{state['id']}"
    response = client.post(url + "/presence", json={"document_id": "page_a", "nodes": ["pca"], "edges": [], "focused_field": "param-n_components"})
    assert response.status_code == 200
    context = client.get(url + "/context").json()
    assert {n["id"] for n in context["nodes"]} == {"quality", "pca"}
    assert context["revision"] == 0 and context["ui_revision"] == 1
    assert context["selection"]["focused_field"] == "param-n_components"
    assert "contracts" in context and "data" not in context
    assert client.get(url + "/context?scope=document").json()["total_nodes"] == 4


def test_atomic_edits_conflicts_and_shared_undo(gateway):
    client, app, data, state = gateway
    url = f"/api/agent/sessions/{state['id']}"
    request = {"document_id": "page_a", "expected_revision": 0, "request_id": "request-1", "commands": [
        {"op": "update_node", "id": "pca", "patch": {"params": {"dim": "feature", "n_components": 3, "output": "pcs"}}},
        {"op": "add_node", "node": {"id": "extra", "kind": "operator", "operator": "describe"}},
        {"op": "connect", "edge": {"id": "extra-edge", "source": "pca", "target": "extra"}},
    ]}
    response = client.post(url + "/apply", json=request)
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["revision"] == 1 and changed["history"]["page_a"]["undo"] == 1
    assert client.post(url + "/apply", json=request).json()["revision"] == 1
    conflict = deepcopy(request); conflict["request_id"] = "request-2"
    assert client.post(url + "/apply", json=conflict).status_code == 409
    bad = {"document_id": "page_a", "expected_revision": 1, "commands": [
        {"op": "remove_node", "id": "extra"}, {"op": "connect", "edge": {"id": "bad", "source": "pca", "target": "quality"}}
    ]}
    assert client.post(url + "/apply", json=bad).status_code == 422
    assert client.get(url).json()["revision"] == 1
    restored = client.post(url + "/undo", json={"document_id": "page_a", "expected_revision": 1}).json()
    assert restored["workspace"]["documents"][0]["graph"]["nodes"] == state["workspace"]["documents"][0]["graph"]["nodes"]
    assert restored["revision"] == 2
    redone = client.post(url + "/undo", json={"document_id": "page_a", "expected_revision": 2, "redo": True}).json()
    assert len(redone["workspace"]["documents"][0]["graph"]["nodes"]) == 5
    # Old UI autosave is rejected rather than replacing the agent's edit.
    assert client.post(url + "/sync", json={"workspace": state["workspace"], "expected_revision": 0}).status_code == 409


def test_gateway_capabilities_and_revocation(gateway):
    client, app, data, state = gateway
    token = client.post("/api/agent/connect", headers={"X-BioPipe-Bridge": app.state.bridge.secret},
                        json={"name": "user", "scopes": ["context"]}).json()["token"]
    client.headers.pop("X-Studio-Token")
    assert client.get("/api/agent/sessions").status_code == 403
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/agent/sessions").status_code == 200
    url = f"/api/agent/sessions/{state['id']}"
    assert client.post(url + "/apply", json={}).status_code == 403
    assert client.post(url + "/run", json={}).status_code == 403
    assert client.post("/api/agent/plugins/install", json={}).status_code == 403
    connections = client.get("/api/agent/connections").json()
    client.headers["X-Studio-Token"] = data["token"]
    client.post("/api/agent/connections/revoke", json={"id": connections[0]["id"]})
    client.headers.pop("X-Studio-Token")
    assert client.get("/api/agent/sessions").status_code == 403


def test_open_generated_graph_without_positions_and_keep_old_tab(gateway):
    client, app, data, state = gateway
    graph = deepcopy(data["demo"])
    for node in graph["nodes"]:
        node.pop("position")
    response = client.post(f"/api/agent/sessions/{state['id']}/open", json={"graph": graph, "expected_revision": 0})
    assert response.status_code == 200, response.text
    assert len(response.json()["workspace"]["documents"]) == 2
    assert all("position" in node for node in response.json()["workspace"]["documents"][1]["graph"]["nodes"])


def test_view_changes_do_not_invalidate_graph_revision(gateway):
    client, app, data, state = gateway
    workspace = deepcopy(state["workspace"])
    workspace["documents"][0]["viewport"] = {"x": 10, "y": 30, "zoom": 1}
    response = client.post(f"/api/agent/sessions/{state['id']}/sync", json={"workspace": workspace, "expected_revision": 0})
    assert response.json()["revision"] == 0


def test_hot_plugin_install_worker_and_pinned_upgrade(gateway, tmp_path, monkeypatch):
    from biopipe.developer import scaffold, build
    from biopipe.plugins import PluginManager
    client, app, data, state = gateway
    source = tmp_path / "scale_plugin"
    scaffold(source)
    wheel = build(source)["wheels"][0]
    import zipfile
    with zipfile.ZipFile(wheel) as archive:
        descriptor_file = next(name for name in archive.namelist() if name.endswith(".dist-info/biopipe.json"))
        assert json.loads(archive.read(descriptor_file))["descriptors"][0]["id"] == "example.scale_plugin"
    # Runtimes can inherit dependencies through .pth files (including editable
    # installations). A plugin worker must resolve the same transitive paths.
    import sysconfig
    runtime_site = tmp_path / "runtime_site"
    runtime_site.mkdir()
    indirect = tmp_path / "indirect_dependency"
    indirect.mkdir()
    (indirect / "biopipe_test_dependency.py").write_text("VALUE = 42\n", encoding="utf-8")
    original_get_path = sysconfig.get_path
    parent_site = original_get_path("purelib")
    (runtime_site / "dependencies.pth").write_text(
        f"import site; site.addsitedir({parent_site!r})\n{indirect}\n", encoding="utf-8")
    monkeypatch.setattr(sysconfig, "get_path", lambda name, *args, **kwargs:
        str(runtime_site) if name == "purelib" else original_get_path(name, *args, **kwargs))
    manager = app.state.service.plugins
    installed = manager.install(wheel)
    dependency = subprocess.run([manager.python_for(installed), "-c",
        "import biopipe_test_dependency; print(biopipe_test_dependency.VALUE)"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert dependency.returncode == 0, dependency.stderr
    assert dependency.stdout.strip() == "42"
    assert len([d for d in installed["descriptors"] if d['distribution'] == 'scale-plugin']) == 1
    catalog = client.get("/api/operators").json()
    assert len(catalog["operators"]) == len(STEPS) + 1
    graph = deepcopy(data["demo"])
    graph["nodes"] = [graph["nodes"][0], {"id": "scale", "kind": "operator", "operator": "example.scale_plugin",
                                        "position": {"x": 400, "y": 80}, "params": {"factor": 3, "output": "scaled"}}]
    graph["edges"] = [{"id": "scale-edge", "source": "expression", "target": "scale"}]
    prepared = client.post("/api/workflows/prepare", json=graph)
    assert prepared.status_code == 200, prepared.text
    pinned = prepared.json()
    assert pinned["plugin_lock"]["example.scale_plugin"]["version"] == "0.1.0"
    response = client.post("/api/jobs", json=pinned)
    assert response.status_code == 202, response.text
    job = response.json()
    deadline = time.monotonic() + 45
    while job["status"] == "running" and time.monotonic() < deadline:
        time.sleep(.1)
        job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "complete", job
    project_file = source / "pyproject.toml"
    project_file.write_text(project_file.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.2.0"'), encoding="utf-8")
    implementation = source / "scale_plugin/__init__.py"
    implementation.write_text(implementation.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.2.0"'), encoding="utf-8")
    newer = manager.install(build(source)["wheels"][0])
    assert newer["generation"] != installed["generation"]
    from src.web.models import Graph
    assert manager.snapshot(Graph.model_validate(pinned))["generation"] == installed["generation"]
    assert manager.pin(Graph.model_validate(graph)).plugin_lock["example.scale_plugin"]["version"] == "0.2.0"
    # Uninstall hides the item but retains the generation needed by saved graphs.
    manager.install(None, remove="scale-plugin")
    assert len(client.get("/api/operators").json()["operators"]) == len(STEPS)
    assert client.post("/api/validate", json=pinned).status_code == 200
    saved = client.post("/api/workflows/save", json={"graph": pinned})
    assert saved.status_code == 200, saved.text
    registered = client.post("/api/routes/register", json={"workflow_ids": [saved.json()["id"]]})
    assert registered.status_code == 200, registered.text
    from src.web.models import Graph
    assert manager.snapshot(Graph.model_validate(pinned))["generation"] == installed["generation"]
    before = manager.state()
    with pytest.raises((ValueError, FileNotFoundError)):
        manager.install(tmp_path / "not-a-wheel.txt")
    assert manager.state() == before


def test_reader_plugin_is_discovered_and_runs_in_worker(gateway, tmp_path):
    from biopipe.developer import scaffold, build
    client, app, data, state = gateway
    source = tmp_path / "array_plugin"
    scaffold(source, "reader")
    manager = app.state.service.plugins
    manager.install(build(source)["wheels"][0])
    assert len(client.get("/api/operators").json()["readers"]) == 14
    np.save(tmp_path / "matrix.npy", np.arange(12, dtype=float).reshape(3, 4))
    graph = deepcopy(data["demo"])
    graph["nodes"] = [graph["nodes"][0], graph["nodes"][-1]]
    graph["nodes"][0]["source"]["path"] = "matrix.npy"
    graph["nodes"][0]["source"]["labels"] = {"sample": "auto", "feature": "auto"}
    graph["edges"] = [{"id": "edge", "source": "expression", "target": "summary"}]
    response = client.post("/api/jobs", json=graph)
    assert response.status_code == 202, response.text
    job = response.json()
    deadline = time.monotonic() + 45
    while job["status"] == "running" and time.monotonic() < deadline:
        time.sleep(.1)
        job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "complete", job
