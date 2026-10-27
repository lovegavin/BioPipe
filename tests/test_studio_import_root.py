"""Studio imports task YAML from code_root even when its profile is elsewhere."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.web.api import create_app
from src.web.service import Settings

YAML = """
name: demo
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


def _client(tmp_path):
    project = tmp_path / "project"
    task = project / "tasks" / "demo"
    (task / "input").mkdir(parents=True)
    (task / "input" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    settings = Settings(workspace, workspace / ".studio", dist, testing=True,
                        code_root=project, builtin_routes=False)
    return create_app(settings), task


def test_import_searches_code_root_not_workspace(tmp_path):
    app, _ = _client(tmp_path)
    with TestClient(app) as client:
        token = client.get("/api/bootstrap").json()["token"]
        response = client.post("/api/import", json={"text": YAML, "base_dir": "."},
                               headers={"X-Studio-Token": token})
        assert response.status_code == 200, response.text
        graph = response.json()
        assert graph["base_dir"] == "tasks/demo"
        source = next(n for n in graph["nodes"] if n["kind"] == "source")
        assert Path(source["source"]["path"]).is_file()
        assert source["source"]["path"].endswith("input/data.csv")


def test_import_accepts_absolute_yaml_paths(tmp_path):
    app, task = _client(tmp_path)
    absolute = (task / "input" / "data.csv").as_posix()
    text = YAML.replace("path: input/data.csv", f"path: '{absolute}'")
    with TestClient(app) as client:
        token = client.get("/api/bootstrap").json()["token"]
        response = client.post("/api/import", json={"text": text, "base_dir": "."},
                               headers={"X-Studio-Token": token})
        assert response.status_code == 200, response.text
        graph = response.json()
        source = next(n for n in graph["nodes"] if n["kind"] == "source")
        assert source["source"]["path"] == absolute
