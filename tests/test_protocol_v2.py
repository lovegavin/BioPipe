"""Public protocol, scientific defaults, and explicit lossless migration boundaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from biopipe.migrate import convert_documents, convert_source, convert_task, migrate, _publish
from biopipe.packages import bundled_state
from biopipe.plugins import PluginManager
from biopipe_sdk.protocol import Descriptor, PackageDescriptor, catalog_entry, validate_extension
from src.reader import READERS
from src.task import STEPS
from src.web.models import Graph


def graph():
    return {"schema_version": 1, "name": "Old analysis", "nodes": [
        {"id": "pca", "kind": "operator", "operator": "pca", "position": {"x": 12, "y": 34},
         "params": {"dim": "feature"}}], "edges": [], "runtime": {"memory": {"keep": ["pcs"]}}}


def test_every_implementation_declares_schema_without_registry_injection():
    for cls, kind in [(cls, "operator") for cls in STEPS.values()] + [(type(r), "reader") for r in READERS]:
        assert cls.parameters_schema is not None
        assert not hasattr(cls, "legacy_parameters")
        validate_extension(cls, kind)
    canonical = bundled_state()["descriptors"]
    removed = {"name", "module", "parameters", "runtime_defaults", "input_type", "output_type", "memory_modes", "supports_cuda", "output_contract", "legacy_parameters"}
    assert all(not (removed & d.keys()) and d["protocol_version"] == 2 for d in canonical)


def test_execution_defaults_are_separate_from_new_node_presets():
    descriptors = {d["id"]: d for d in bundled_state()["descriptors"]}
    pca = catalog_entry(descriptors["pca"])
    assert pca["runtime_defaults"]["n_components"] == 10
    assert next(p for p in pca["parameters"] if p["key"] == "n_components")["default"] == 2
    converted = convert_documents(graph(), list(descriptors.values()))
    assert converted["nodes"][0]["params"]["n_components"] == 10
    assert converted["runtime"] == graph()["runtime"]
    assert converted["nodes"][0]["position"] == {"x": 12, "y": 34}
    assert convert_documents(converted, list(descriptors.values())) == converted


def test_v1_declarations_and_graphs_are_rejected_by_live_protocol():
    d = {k: v for k, v in bundled_state()["descriptors"][0].items()
         if k not in {"distribution", "package_version", "origin", "implementation"}}
    Descriptor.model_validate(d)
    for bad in ({**d, "protocol_version": 1}, {**d, "name": d["id"]}):
        with pytest.raises(ValidationError):
            Descriptor.model_validate(bad)
    with pytest.raises(ValidationError):
        Graph.model_validate(graph())
    with pytest.raises(ValidationError):
        PackageDescriptor.model_validate({"name": "example", "version": "1.0.0", "protocol_version": 1, "descriptors": []})


def test_task_numeric_migration_and_nested_graph():
    descriptors = bundled_state()["descriptors"]
    task = {"sources": {}, "steps": [{"name": "normalize", "inputs": ["x"], "params": {"method": "cpm", "dim": "sample", "target_sum": "1e4", "output": "y"}}]}
    result = convert_task(task, descriptors)
    assert result["steps"][0]["params"]["target_sum"] == 10000
    assert result["steps"][0]["params"]["output"] == "y"
    wrapper = {"undo": [{"graph": graph()}], "selection": ["pca"]}
    assert convert_documents(wrapper, descriptors)["undo"][0]["graph"]["schema_version"] == 2


def test_file_dry_run_backup_idempotence_and_cli(tmp_path):
    target = tmp_path / "analysis.json"
    original = json.dumps(graph()).encode()
    target.write_bytes(original)
    preview = migrate(path=target)
    assert preview["changed"] == [str(target)] and preview["backup"] is None
    assert list(tmp_path.iterdir()) == [target] and target.read_bytes() == original
    result = migrate(path=target, apply=True)
    backup = Path(result["backup"])
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert (backup / manifest["files"][0]["backup"]).read_bytes() == original
    assert migrate(path=target, apply=True)["changed"] == []
    from biopipe.cli import parser, execute
    assert execute(parser().parse_args(["migrate", str(target)]))["changed"] == []


def test_profile_migration_preserves_disabled_removed_and_historical_jobs(tmp_path):
    root = tmp_path / "profile"
    directory = root / "workspace/.studio"
    manager = PluginManager(directory)
    state = manager.state()
    state["protocol_version"] = state["package_protocol_version"] = 1
    for d in state["descriptors"]:
        d["protocol_version"] = 1
    removed = "biopipe-microbiome"
    state["packages"] = [p for p in state["packages"] if p["name"] != removed]
    next(p for p in state["packages"] if p["name"] == "biopipe-genetics")["enabled"] = False
    manager.registry.write_text(json.dumps(state), encoding="utf-8")
    workspace = directory / "workflows/workspace.json"
    workspace.parent.mkdir()
    workspace.write_text(json.dumps({"schema_version": 1, "active_id": "a", "documents": [{"id": "a", "graph": graph()}]}))
    job = directory / "jobs/historical/graph.json"
    job.parent.mkdir(parents=True)
    job.write_text(json.dumps(graph()))
    originals = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="migrate"):
        manager.state()
    migrate(profile_dir=root)
    assert originals == {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    result = migrate(profile_dir=root, apply=True)
    assert result["backup"] and job.read_bytes() == originals[job]
    new = manager.state()
    assert new["package_protocol_version"] == 2
    assert removed not in {p["name"] for p in new["packages"]}
    assert not next(p for p in new["packages"] if p["name"] == "biopipe-genetics")["enabled"]
    assert json.loads(workspace.read_text())["documents"][0]["graph"]["schema_version"] == 2
    assert migrate(profile_dir=root)["changed"] == []


def test_failed_batch_rolls_back_and_keeps_original_backup(tmp_path, monkeypatch):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_bytes(b"original a"); b.write_bytes(b"original b")
    replace = Path.replace
    def fail_second(path, target):
        if target == b:
            raise OSError("simulated disk failure")
        return replace(path, target)
    monkeypatch.setattr(Path, "replace", fail_second)
    with pytest.raises(OSError, match="disk failure"):
        _publish({a: b"new a", b: b"new b"}, tmp_path / "backup")
    assert a.read_bytes() == b"original a" and b.read_bytes() == b"original b"
    receipt = next((tmp_path / "backup").glob("*/manifest.json"))
    assert json.loads(receipt.read_text())["status"] == "rolled_back"


def test_edit_after_preflight_is_not_overwritten(tmp_path):
    target = tmp_path / "route.json"
    target.write_bytes(b"user edit")
    with pytest.raises(ValueError, match="changed after migration preflight"):
        _publish({target: b"converted"}, tmp_path / "backup", expected={target: b"old"})
    assert target.read_bytes() == b"user edit"
    assert not (tmp_path / "backup").exists()


def test_source_conversion_is_static_and_keeps_author_code():
    text = 'raise RuntimeError("must never execute during migration")\nclass Example:\n    name = "example"\n    legacy_parameters = True\n    def run(self, ctx, inputs):\n        return 42\n'
    manifest = {"id": "example", "entry_point": "pkg:Example", "parameters_schema": {"type": "object", "properties": {"x": {"type": "number", "default": 10}}}, "parameters": [{"key": "x", "default": 2}]}
    result = convert_source(text, manifest)
    assert 'legacy_parameters' not in result
    assert 'return 42' in result and 'must never execute' in result
    assert "'x-ui-default': 2" in result
    assert convert_source(result, manifest) == result


def test_preflight_failure_never_rewrites_valid_files(tmp_path):
    root = tmp_path / "profile"
    directory = root / "workspace/.studio"
    manager = PluginManager(directory)
    state = manager.state()
    state.update(protocol_version=1, package_protocol_version=1)
    state["packages"].append({"name": "external-v1", "origin": "wheel"})
    manager.registry.write_text(json.dumps(state))
    before = manager.registry.read_bytes()
    with pytest.raises(ValueError, match="Rebuild v1 external"):
        migrate(profile_dir=root, apply=True)
    assert manager.registry.read_bytes() == before
    assert not (directory / "migrations").exists()
    path = tmp_path / "missing.json"
    missing = graph(); missing["nodes"][0]["operator"] = "lab.unavailable"
    path.write_text(json.dumps(missing))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="Missing v2 operator"):
        migrate(path=path, apply=True)
    assert path.read_bytes() == original
    assert not (tmp_path / ".biopipe-migration-backups").exists()


def test_sdk_requirement_checks_running_code_not_stale_build_metadata(tmp_path, monkeypatch):
    from biopipe import __version__
    from biopipe.targets import TargetBuilder
    from importlib import metadata
    monkeypatch.setattr(metadata, "version", lambda name: "0.4.1")
    builder = TargetBuilder(PluginManager(tmp_path), {})
    assert builder.prepare([f"biopipe-studio>={__version__},<1"])["mode"] == "shared"
    assert builder.prepare(['biopipe-studio>=999; python_version < "0"'])["mode"] == "shared"
    with pytest.raises(ValueError, match="incompatible BioPipe SDK"):
        builder.prepare(["biopipe-studio>=999"])
