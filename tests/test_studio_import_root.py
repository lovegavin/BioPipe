"""Studio imports task YAML from code_root even when its profile is elsewhere."""
from __future__ import annotations

from pathlib import Path
import tempfile
import time

import pytest

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


def _client(tmp_path, *, code_root=None):
    project = tmp_path / "project"
    task = project / "tasks" / "demo"
    (task / "input").mkdir(parents=True)
    (task / "input" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    settings = Settings(workspace, workspace / ".studio", dist, testing=True,
                        code_root=code_root or project, builtin_routes=False)
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


@pytest.mark.parametrize('relative', [False, True])
def test_import_rejects_paths_outside_both_configured_roots(tmp_path, relative):
    app, _ = _client(tmp_path)
    outside = tmp_path / 'outside.csv'
    outside.write_text('a,b\n1,2\n')
    path = '../outside.csv' if relative else outside.as_posix()
    with TestClient(app) as client:
        token = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/import', json={
            'text': YAML.replace('path: input/data.csv', f"path: '{path}'"), 'base_dir': '.',
        }, headers={'X-Studio-Token': token})
        assert response.status_code == 422, response.text


def test_imported_code_root_inputs_prepare_save_export_and_run():
    # Keep test data inside the configured source installation even when the
    # caller's normal pytest temp directory is on another drive.
    root = Path(__file__).resolve().parents[1]
    scratch = root / '.tmp'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='studio-import-', dir=scratch) as directory:
        app, task = _client(Path(directory), code_root=root)
        source = task / 'input/data.csv'
        with TestClient(app) as client:
            token = client.get('/api/bootstrap').json()['token']
            client.headers['X-Studio-Token'] = token
            response = client.post('/api/import', json={
                'text': YAML.replace('path: input/data.csv', f"path: '{source.as_posix()}'"),
                'base_dir': '.',
            })
            assert response.status_code == 200, response.text
            graph = response.json()
            graph['memory'] = {'enabled': True, 'budget_mb': 16, 'auto_spill': True, 'keep': ['norm']}
            prepared = client.post('/api/workflows/prepare', json=graph)
            assert prepared.status_code == 200, prepared.text
            graph = prepared.json()
            saved = client.post('/api/workflows/save', json={'graph': graph})
            assert saved.status_code == 200, saved.text
            assert saved.json()['parameters_file'].endswith('.json')
            assert client.post('/api/validate', json=graph).status_code == 200
            assert client.post('/api/contracts', json=graph).status_code == 200
            assert client.post('/api/export', json=graph).status_code == 200
            launched = client.post('/api/jobs', json=graph)
            assert launched.status_code == 202, launched.text
            key = launched.json()['id']
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                job = client.get(f'/api/jobs/{key}').json()
                if job['status'] in ('complete', 'failed', 'cancelled'):
                    break
                time.sleep(.05)
            assert job['status'] == 'complete', job
            assert source.read_text(encoding='utf-8') == 'a,b\n1,2\n'
