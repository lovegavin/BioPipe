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


def test_unique_suffix_uses_task_base_not_input_directory(tmp_path):
    _task(tmp_path, 'only_task')
    graph = import_manifest(YAML, '.', build_catalog(STEPS), tmp_path)
    assert graph.base_dir == 'tasks/only_task'
    assert Path(graph.nodes[0].source.path) == tmp_path / 'tasks/only_task/input/data.csv'


def test_named_task_and_route_are_still_ambiguous(tmp_path):
    _task(tmp_path)
    directory = tmp_path / 'routes/user_task/input'
    directory.mkdir(parents=True)
    (directory / 'data.csv').write_text('a,b\n3,4\n')
    with pytest.raises(GraphError, match='无法唯一定位'):
        import_manifest(YAML, '.', build_catalog(STEPS), tmp_path)


def test_export_keeps_cross_drive_input_paths(monkeypatch):
    import ntpath
    from src.web.graph import relative_manifest
    # Exercise Windows drive semantics on every host without requiring C:/D:.
    monkeypatch.setattr('src.web.graph.os.path.relpath', ntpath.relpath)
    manifest = {
        'sources': {'data': {'path': 'D:/data/counts.csv'}}, 'steps': [],
        'runtime': {'memory': {'cache_dir': 'C:/jobs/cache'}},
    }
    result = relative_manifest(manifest, 'C:/jobs/run')
    assert result['sources']['data']['path'] == 'D:/data/counts.csv'
    assert result['runtime']['memory']['cache_dir'].replace('\\', '/') == '../cache'
