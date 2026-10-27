"""Import should find task-local inputs without a manual base_dir."""
from __future__ import annotations

import pytest

from pathlib import Path

from src.task import STEPS
from src.task.operator_catalog import build_catalog
from src.web.graph import GraphError, import_manifest

YAML = """
name: user_task
sources:
  table:
    path: input/data.csv
    dims: [sample, feature]
    labels: {sample: auto, feature: builtin}
steps:
  - name: normalize
    inputs: [table]
    params: {method: cpm, dim: sample, output: norm}
"""


def _task(root, name="user_task"):
    task = root / "tasks" / name
    (task / "input").mkdir(parents=True)
    (task / "input" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    return task


def test_import_locates_task_by_yaml_name(tmp_path):
    _task(tmp_path)
    graph = import_manifest(YAML, ".", build_catalog(STEPS), tmp_path)
    assert graph.base_dir == "tasks/user_task"
    source = next(node for node in graph.nodes if node.kind == "source")
    assert source.source is not None
    assert Path(source.source.path).is_file()
    assert source.source.path.endswith("input/data.csv")


def test_import_rejects_ambiguous_duplicate_inputs(tmp_path):
    _task(tmp_path, "first")
    _task(tmp_path, "second")
    # The YAML name matches neither task directory, so two identical paths remain.
    with pytest.raises(GraphError, match="无法唯一定位"):
        import_manifest(YAML.replace("user_task", "unknown_task"), ".", build_catalog(STEPS), tmp_path)
