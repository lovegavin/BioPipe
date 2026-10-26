"""Shared launcher paths, explicit profiles and concurrent writers."""
from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.task import STEPS
from src.task.operator_catalog import build_catalog
from src.web.graph import compile_graph, GraphError
from src.web.models import Graph, SaveWorkflow, Workspace
from src.web.profile import resolve_profile
from src.web.routes import RouteLibrary
from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def catalog():
    return build_catalog(STEPS)


def settings(root, relative=".studio"):
    return Settings(root, root / relative, ROOT / "frontend/dist", testing=True, code_root=ROOT)


def test_profile_independent_of_checkout_cwd_and_appdata(tmp_path, monkeypatch):
    user = tmp_path / "用户 home"
    monkeypatch.chdir(tmp_path)
    first = resolve_profile(tmp_path / "checkout A", home=user, environ={"LOCALAPPDATA": str(tmp_path / "real")})
    second = resolve_profile(tmp_path / "relocated exe", home=user, environ={"LOCALAPPDATA": str(tmp_path / "MSIX/cache")})
    assert first == second
    assert first.profile_dir == user / ".biopipe/studio"
    assert not user.exists()  # Path diagnostics must be read-only.
    assert resolve_profile(ROOT, home=user, environ={"BIOPIPE_STUDIO_HOME": "custom"}).profile_dir == user / "custom"
    override = resolve_profile(ROOT, home=user, environ={"BIOPIPE_STUDIO_HOME": "env"}, profile_dir="cli")
    assert override.profile_dir == user / "cli"
    with pytest.raises(ValueError, match="--workspace"):
        resolve_profile(ROOT, home=user, environ={"BIOPIPE_STUDIO_DATA": "old"})
    with pytest.raises(ValueError):
        resolve_profile(ROOT, home=user, environ={}, workspace=tmp_path, data_dir="../escape")


def test_both_python_entrypoints_use_identical_resolver(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "BIOPIPE_STUDIO_DATA"}
    env.update(BIOPIPE_STUDIO_HOME=str(tmp_path / "shared 中文"), PYTHONIOENCODING="utf-8")
    results = []
    for script in ("studio.py", "desktop_server.py"):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / script), "--resolve-profile"],
                                cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
        assert result.returncode == 0, result.stderr
        results.append(json.loads(result.stdout))
    assert results[0] == results[1]
    assert not (tmp_path / "shared 中文").exists()












def write_route(root, graph, barrier):
    library = RouteLibrary(Path(root) / ".studio/workflows", build_catalog(STEPS), Path(root))
    barrier.wait(timeout=20)
    saved = library.save(SaveWorkflow(graph=Graph.model_validate(graph)))
    library.register([saved["id"]])


def test_concurrent_process_registration_and_live_reload(tmp_path, catalog):
    service = JobService(settings(tmp_path), catalog)
    library = service.routes
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    processes = [ctx.Process(target=write_route, args=(str(tmp_path), {**service.demo, "name": name}, barrier))
                 for name in ("Desktop", "Development")]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(40)
            assert process.exitcode == 0
        assert {r["name"] for r in library.routes()} == {"Desktop", "Development"}
        saved = library.list_saved()[0]
        other = RouteLibrary(library.directory, catalog, tmp_path)
        other.save(SaveWorkflow(id=saved["id"], expected_version=1, graph=Graph.model_validate(service.demo)))
        with pytest.raises(GraphError, match="其他页面更新"):
            library.save(SaveWorkflow(id=saved["id"], expected_version=1, graph=Graph.model_validate(service.demo)))
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate(); process.join(5)


def test_second_launcher_does_not_interrupt_active_worker(tmp_path, catalog):
    first = JobService(settings(tmp_path), catalog)
    graph = Graph.model_validate(first.demo)
    graph.memory["budget_mb"] = 64
    launched = first.launch(graph)
    try:
        second = JobService(settings(tmp_path), catalog)
        job = second.require(launched["id"])
        assert job["status"] == "running"
        with pytest.raises(GraphError, match="另一个"):
            second.cancel(launched["id"])
        with pytest.raises(GraphError, match="已有任务"):
            second.launch(graph)
        second.shutdown()
        assert first.require(launched["id"])["status"] == "running"
    finally:
        first.shutdown()
