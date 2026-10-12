"""Shared launcher paths, conservative legacy imports and concurrent writers."""
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
from src.web.migration import migrate_profile
from src.web.models import Graph, SaveWorkflow, Workspace
from src.web.profile import legacy_locations, resolve_profile
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
    assert first.migrate_legacy
    assert not user.exists()  # Path diagnostics must be read-only.
    assert resolve_profile(ROOT, home=user, environ={"BIOPIPE_STUDIO_HOME": "custom"}).profile_dir == user / "custom"
    override = resolve_profile(ROOT, home=user, environ={"BIOPIPE_STUDIO_HOME": "env"}, profile_dir="cli")
    assert override.profile_dir == user / "cli" and not override.migrate_legacy
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


def test_legacy_discovery_is_generic_and_deduplicated(tmp_path):
    appdata = tmp_path / "appdata"
    physical = appdata / "BioPipe Studio/workspace/.studio"
    virtual = tmp_path / "AppData/Local/Packages/Any.Editor_123/LocalCache/Local/BioPipe Studio/workspace/.studio"
    checkout = tmp_path / "checkout"
    for folder in (physical, virtual, checkout / ".local/studio"):
        folder.mkdir(parents=True)
    found = list(legacy_locations(checkout, home=tmp_path, environ={"LOCALAPPDATA": str(appdata)}))
    assert {data for _, data in found} == {physical, virtual, checkout / ".local/studio"}


def old_library(root, catalog, relative=".studio"):
    service = JobService(settings(root, relative), catalog)
    library = service.routes
    graph = Graph.model_validate(service.demo)
    saved = library.save(SaveWorkflow(graph=graph))
    library.register([saved["id"]])
    library.save_workspace(Workspace(active_id="original", documents=[{"id": "original", "graph": graph,
                                                                      "workflow_id": saved["id"], "workflow_version": 1}]))
    return service, saved


def test_import_merges_aliases_preserves_conflicts_and_never_auto_registers(tmp_path, catalog):
    dev, first = old_library(tmp_path / "dev", catalog, ".local/studio")
    desktop, duplicate = old_library(tmp_path / "desktop", catalog)
    unsaved_registration = desktop.routes.save(SaveWorkflow(graph=Graph.model_validate({**desktop.demo, "name": "Saved only"})))
    # A third old profile reuses the same ID but has a different body/version.
    third, _ = old_library(tmp_path / "third", catalog)
    collision = deepcopy(first)
    collision["graph"]["name"] = "Distinct conflict"
    (third.routes.directory / f"{first['id']}.json").write_text(json.dumps(collision), encoding="utf-8")
    third.routes.changed()
    third.routes.register([first["id"]])
    target = settings(tmp_path / "new user profile/workspace")
    sources = [(s.root, s.directory) for s in (dev, desktop, third)]
    before = {p: p.read_bytes() for s in (dev, desktop, third) for p in s.routes.directory.glob("*.json")}
    migrate_profile(target, catalog, sources)
    library = RouteLibrary(target.data_dir / "workflows", catalog, target.root)
    assert len(library.routes()) == 2
    assert {r["name"] for r in library.routes()} == {"表达矩阵 · 质量控制与降维", "Distinct conflict"}
    assert unsaved_registration["id"] not in {r["id"] for r in library.routes()}
    assert library.get(first["id"])["graph"]["name"] != "Distinct conflict"
    for document in library.load_workspace()["documents"]:
        compile_graph(Graph.model_validate(document["graph"]), catalog, target.root, require_files=True)
    for path, content in before.items():
        assert path.read_bytes() == content
    after = {p: p.read_bytes() for p in library.directory.glob("*.json")}
    migrate_profile(target, catalog, sources)
    assert after == {p: p.read_bytes() for p in library.directory.glob("*.json")}
    receipts = list((target.data_dir / "migrations").glob("*/complete.json"))
    assert len(receipts) == 3
    assert all((p.parent / "source/workflows/registry.json").is_file() for p in receipts)


def test_corrupt_registry_does_not_become_empty_or_overwrite_target(tmp_path, catalog):
    legacy, _ = old_library(tmp_path / "old", catalog)
    target, _ = old_library(tmp_path / "new", catalog)
    registry = target.routes.directory / "registry.json"
    before = registry.read_bytes()
    (legacy.routes.directory / "registry.json").write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError, match="原文件已保留"):
        migrate_profile(target.settings, catalog, [(legacy.root, legacy.directory)])
    assert registry.read_bytes() == before
    registry.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError, match="注册表损坏"):
        RouteLibrary(target.routes.directory, catalog, target.root)
    assert registry.read_text() == "broken"


def test_legacy_overlay_file_resolves_into_another_known_profile(tmp_path, catalog, monkeypatch):
    old, saved = old_library(tmp_path / "real AppData", catalog)
    overlay_root = tmp_path / "package cache"
    overlaid = overlay_root / ".studio/assets/expression-demo.csv"
    overlaid.parent.mkdir(parents=True)
    overlaid.write_text("a,b\n101,202\n", encoding="utf-8")
    original_input = old.assets_dir / "expression-demo.csv"
    path_type = type(original_input)
    original_resolve = path_type.resolve
    def resolve(path, *args, **kwargs):
        return overlaid if path == original_input else original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(path_type, "resolve", resolve)
    target = settings(tmp_path / "new/workspace")
    migrate_profile(target, catalog, [(old.root, old.directory), (overlay_root, overlay_root / ".studio")])
    library = RouteLibrary(target.data_dir / "workflows", catalog, target.root)
    graph = library.get(saved["id"])["graph"]
    copied = target.root / graph["nodes"][0]["source"]["path"]
    assert copied.read_bytes() == overlaid.read_bytes()
    receipt = next((target.data_dir / "migrations").glob("*/complete.json"))
    assert json.loads(receipt.read_text(encoding="utf-8"))["warnings"] == []


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
