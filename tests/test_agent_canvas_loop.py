"""Agent canvas loop: write into an existing document, set execution, polymer-only interface."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.core.forms import Form
from src.reader import read_source
from src.task.context import Context
from src.task.runner import run
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/vhh_1mel.pdb"


@pytest.fixture
def studio(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / ".studio", ROOT / "frontend/dist",
                              testing=True, code_root=ROOT, desktop=True))
    with TestClient(app) as client:
        data = client.get("/api/bootstrap").json()
        client.headers["X-Studio-Token"] = data["token"]
        workspace = {"schema_version": 1, "active_id": "page_a",
                     "documents": [{"id": "page_a", "graph": deepcopy(data["demo"])}]}
        state = client.post("/api/agent/sessions", json={"workspace": workspace}).json()
        yield client, state, data




def test_open_replaces_existing_document_and_returns_revision(studio):
    client, state, data = studio
    graph = deepcopy(data["demo"])
    graph["name"] = "replaced"
    session = state["id"]
    snapshot = client.get(f"/api/agent/sessions/{session}/context?scope=document").json()
    result = client.post(f"/api/agent/sessions/{session}/open",
                         json={"graph": graph, "expected_revision": snapshot["revision"],
                               "document_id": snapshot["document_id"], "mode": "replace"}).json()
    assert result["document_id"] == "page_a"
    fresh = client.get(f"/api/agent/sessions/{session}/context?scope=document").json()
    assert fresh["name"] == "replaced"
    assert len(fresh["nodes"]) == len(graph["nodes"])


def test_set_graph_command_replaces_graph_in_one_transaction(studio):
    client, state, data = studio
    session = state["id"]
    snapshot = client.get(f"/api/agent/sessions/{session}/context?scope=document").json()
    graph = deepcopy(data["demo"])
    graph["name"] = "set-graph"
    result = client.post(f"/api/agent/sessions/{session}/apply",
                         json={"document_id": "page_a", "expected_revision": snapshot["revision"],
                               "request_id": "set-graph-1",
                               "commands": [{"op": "set_graph", "graph": graph}]}).json()
    assert result["document_id"] == "page_a"
    assert client.get(f"/api/agent/sessions/{session}/context?scope=document").json()["name"] == "set-graph"


def test_set_execution_writes_runtime_and_repins(studio):
    client, state, data = studio
    session = state["id"]
    snapshot = client.get(f"/api/agent/sessions/{session}/context?scope=document").json()
    result = client.post(f"/api/agent/sessions/{session}/apply",
                         json={"document_id": "page_a", "expected_revision": snapshot["revision"],
                               "request_id": "exec-1",
                               "commands": [{"op": "configure",
                                             "patch": {"runtime": {"execution": {"kind": "local"}}}}]}).json()
    context = client.get(f"/api/agent/sessions/{session}/context?scope=document").json()
    assert context["runtime"]["execution"] == {"kind": "local"}
    assert context["plugin_lock"] is not None


def _pdb_form(path=FIXTURE):
    return read_source(path, ["atom", "field"], {"atom": "auto", "field": "builtin"})


def _run_interface(tmp_path, **extra):
    form = _pdb_form()
    ctx = Context(tmp_path, {"params": {}})
    ctx.step_params = {"atom_dim": "atom", "field_dim": "field", "binder_chains": "A,B",
                       "target_chains": "L,M", "core_fraction": 0.5, "probe_radius": 1.4,
                       "n_points": 92, "output": "iface", **extra}
    ctx["complex"] = form
    run(ctx, [{"name": "structure_interface_core", "inputs": ["complex"],
               "params": dict(ctx.step_params)}])
    return ctx["iface"]


def test_interface_core_is_polymer_only_by_default(tmp_path):
    form = _pdb_form()
    assert "HOH" in set(
        value for key, value in form.info["encoders"]["field"]["resname"].inverse.items()
    )
    interface = _run_interface(tmp_path)
    assert interface.info["n_interface"] == 88
    assert interface.info["n_core"] == 52
    assert interface.info["n_rim"] == 36
    assert interface.info["n_nonpolymer"] == 33


def test_interface_core_can_include_nonpolymer(tmp_path):
    interface = _run_interface(tmp_path, include_nonpolymer=True)
    assert interface.info["n_interface"] == 99
    assert interface.info["n_core"] == 58


def test_reader_excludes_solvent_on_request():
    form = read_source(FIXTURE, ["atom", "field"], {"atom": "auto", "field": "builtin"},
                       exclude_solvent=True)
    assert form.info["exclude_solvent"] is True
    assert form.info["n_excluded_solvent"] > 0
    assert form.data.shape[0] == 3908
