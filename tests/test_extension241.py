"""Tests for the large-resource manifest, preflight operator and CLI helper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._resources_common import (
    Resource,
    check_many,
    check_resource,
    load_resources,
    manifest_path,
    remedy,
    require,
    resolve_root,
)
from src.task.step.steps.resource_preflight import ResourcePreflightStep

REPO = Path(__file__).resolve().parents[1]


def _tmp_resource(tmp_path: Path, files: dict[str, int]) -> Path:
    root = tmp_path / "resource"
    root.mkdir()
    for name, size in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return root


def test_manifest_lists_the_expected_resources() -> None:
    path = manifest_path()
    assert path.name == "resources.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["protocol_version"] == 1
    resources = load_resources()
    assert set(resources) >= {
        "proteinmpnn",
        "ligandmpnn",
        "esm2",
        "esm_if1",
        "esmfold",
        "colabfold",
        "alphafold2",
        "rfdiffusion",
    }
    for resource in resources.values():
        assert resource.files, resource.id
        assert resource.roots, resource.id
        assert resource.install, resource.id
        assert resource.url.startswith("http"), resource.id


def test_check_resource_reports_ok_partial_and_missing(tmp_path) -> None:
    esm2 = load_resources()["esm2"]
    root = _tmp_resource(tmp_path, {"esm2_t6_8M_UR50D.pt": 1024 * 1024})
    check = check_resource(esm2, root)
    assert check["status"] == "ok"
    assert check["root"] == str(root)
    assert check["missing"] == []
    assert check["files"]["esm2_t6_8M_UR50D.pt"]["present"] is True
    assert 0.9 < check["size_mb"] < 1.1

    empty = tmp_path / "empty"
    empty.mkdir()
    missing = check_resource(esm2, empty)
    assert missing["status"] == "partial"
    assert missing["missing"] == ["esm2_t6_8M_UR50D.pt"]

    absent = check_resource(esm2, tmp_path / "does-not-exist")
    assert absent["status"] == "missing"
    assert absent["root"] == ""
    assert "OPERON_ESM_MODEL_DIR" in remedy(absent)


def test_resolve_root_prefers_explicit_then_env(tmp_path, monkeypatch) -> None:
    rfdiffusion = load_resources()["rfdiffusion"]
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    assert resolve_root(rfdiffusion, explicit) == explicit
    monkeypatch.setenv("OPERON_RFDIFFUSION_PATH", str(explicit))
    assert resolve_root(rfdiffusion) == explicit
    monkeypatch.delenv("OPERON_RFDIFFUSION_PATH")
    assert resolve_root(rfdiffusion) is None or resolve_root(rfdiffusion).is_dir()


def test_require_raises_with_the_install_command(tmp_path) -> None:
    with pytest.raises(StepError, match="resource 'colabfold' is missing"):
        require("resource_preflight", "colabfold", tmp_path / "absent")
    with pytest.raises(StepError, match="unknown resource"):
        require("resource_preflight", "not-a-resource", tmp_path)


def test_preflight_operator_reports_every_file(tmp_path) -> None:
    root = _tmp_resource(tmp_path, {"esm2_t6_8M_UR50D.pt": 4096})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(
        ctx,
        [
            {
                "name": "resource_preflight",
                "inputs": [],
                "params": {"resource": "esm2", "root": str(root), "output": "resources"},
            }
        ],
    )
    form = ctx["resources"]
    assert form.dims == ["file", "statistic"]
    labels = [label for label, _ in sorted(form.labels["file"].items(), key=lambda item: item[1])]
    assert labels == ["esm2:esm2_t6_8M_UR50D.pt"]
    assert form.data.tolist() == [[1.0, pytest.approx(0.0039, abs=1e-3)]]
    assert form.info["n_resources"] == 1
    assert form.info["n_missing"] == 0
    assert form.info["statuses"] == {"esm2": "ok"}
    assert str(manifest_path()) == form.info["manifest"]


def test_preflight_strict_and_unknown_resource(tmp_path) -> None:
    step = ResourcePreflightStep()
    assert step.definition["inputs_arity"] == 0

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="missing resources"):
        run(
            ctx,
            [
                {
                    "name": "resource_preflight",
                    "inputs": [],
                    "params": {"resource": "esm2", "root": str(tmp_path / "none"), "strict": True},
                }
            ],
        )
    with pytest.raises(StepError, match="unknown resource"):
        run(
            ctx,
            [{"name": "resource_preflight", "inputs": [], "params": {"resource": "nope"}}],
        )


def test_cli_reports_status_and_exit_code(tmp_path) -> None:
    root = _tmp_resource(tmp_path, {"esm2_t6_8M_UR50D.pt": 2048})
    ok = subprocess.run(
        [sys.executable, "scripts/check_resources.py", "--resource", "esm2", "--root", str(root), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    assert payload["esm2"]["status"] == "ok"

    bad = subprocess.run(
        [sys.executable, "scripts/check_resources.py", "--resource", "esm2", "--root", str(tmp_path / "nope")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert bad.returncode == 1
    assert "MISSING" in bad.stdout
    assert "install:" in bad.stdout


def test_resource_dataclass_rejects_incomplete_entries() -> None:
    with pytest.raises(StepError, match="without an id"):
        Resource.from_entry({"files": ["a"]})
    with pytest.raises(StepError, match="lists no expected files"):
        Resource.from_entry({"id": "x", "files": []})


def test_check_many_all_resources() -> None:
    checks = check_many()
    assert set(checks) == set(load_resources())
    for check in checks.values():
        assert check["status"] in ("ok", "partial", "missing")
        assert isinstance(check["files"], dict)
    with pytest.raises(StepError, match="unknown resource"):
        check_many(["not-a-resource"])
