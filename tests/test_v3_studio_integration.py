"""The graphical authoring endpoints and the actual isolated worker agree."""
import json
from pathlib import Path
import time

from fastapi.testclient import TestClient

from operon.application import ACTIVE
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = '''# output: result file.csv
import argparse
from pathlib import Path
scale = 3
parser = argparse.ArgumentParser()
parser.add_argument('--out-result')
args = parser.parse_args()
Path(args.out_result).write_text('value\\n' + str(scale) + '\\n')
'''


def test_editor_script_freeze_and_real_worker(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')
    monkeypatch.setenv('OPERON_ADMISSION_DIR', str(tmp_path / 'admission'))
    monkeypatch.setenv('TEMP', str(tmp_path))
    monkeypatch.setenv('TMP', str(tmp_path))
    from operon.dependencies import DependencySession
    calls = []
    original = DependencySession.check
    def checked(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)
    monkeypatch.setattr(DependencySession, 'check', checked)
    app = create_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        boot = client.get('/api/bootstrap').json()
        headers = {'X-Studio-Token': boot['token']}
        assert calls == []  # Opening the app is not dependency preparation.
        response = client.post('/api/scripts/inspect', headers=headers, json={'filename': 'scale.py', 'code': SCRIPT})
        assert response.status_code == 200, response.text
        inspected = response.json()
        assert inspected['candidates'][0]['name'] == 'scale'
        extracted = client.post('/api/scripts/extract', headers=headers,
                                json={'script': inspected['script'], 'names': ['scale']})
        assert extracted.status_code == 200, extracted.text
        script = extracted.json()['script']
        graph = {'name': 'Script end-to-end', 'nodes': [{'id': 'script1', 'kind': 'script', 'title': 'Scale',
                 'position': {'x': 0, 'y': 0}, 'script': script, 'params': {'scale': 7}}], 'edges': [], 'memory': {'enabled': True, 'budget_mb': 32}}
        ready = client.post('/api/validate', headers=headers, json=graph)
        assert ready.status_code == 200, ready.text
        assert ready.json()['readiness']['status'] == 'ready', ready.text
        frozen = client.post('/api/workflows/prepare', headers=headers, json=graph)
        assert frozen.status_code == 200, frozen.text
        assert frozen.json()['nodes'][0]['kind'] == 'script'
        assert frozen.json()['nodes'][0]['params'] == {'scale': 7}
        # Same shared application entry as the desktop Run button.
        job = app.state.application.jobs.launch(frozen.json())
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = app.state.application.jobs.details(job['id'])
            if result['status'] not in ACTIVE:
                break
            time.sleep(.1)
        assert result['status'] == 'complete', result
        outputs = list((tmp_path / '.studio/jobs' / job['id']).rglob('result.csv'))
        assert outputs and outputs[0].read_text().strip() == 'value\n7'
        exported = client.post('/api/workflows/export-yaml', headers=headers, json=frozen.json())
        assert exported.status_code == 200, exported.text
        imported = client.post('/api/workflows/import', headers={**headers, 'Content-Type': 'application/zip'}, content=exported.content)
        assert imported.status_code == 200, imported.text
        assert imported.json()['nodes'][0]['script'] == script
        assert imported.json()['nodes'][0]['params'] == {'scale': 7}
        published = client.post('/api/scripts/publish', headers=headers, json={
            'script': script, 'operator_id': 'lab.scale_test', 'title': 'Scale', 'category': 'Quality control'})
        assert published.status_code == 200, published.text
        saved = next(item for item in published.json()['catalog']['operators'] if item['id'] == 'lab.scale_test')
        assert saved['category'] == 'Quality control'
        assert all(call.get('repair') is False for call in calls)


def test_static_inspection_does_not_execute(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        headers = {'X-Studio-Token': client.get('/api/bootstrap').json()['token']}
        response = client.post('/api/scripts/inspect', headers=headers,
                               json={'filename': 'never.py', 'code': 'raise RuntimeError("not during inspection")'})
        assert response.status_code == 200, response.text
        response = client.post('/api/scripts/inspect', headers=headers,
                               json={'filename': '../escape.py', 'code': 'pass'})
        assert response.status_code == 422


def test_branched_file_scripts_keep_both_outputs(tmp_path, monkeypatch):
    from operon.workflow_spec import load_workflow
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('TEMP', str(tmp_path))
    monkeypatch.setenv('TMP', str(tmp_path))
    monkeypatch.setenv('OPERON_ADMISSION_DIR', str(tmp_path / 'admission'))
    graph = load_workflow(ROOT / 'examples/workflows/script_pipeline/workflow.yaml')
    # There are no external source files; the generated file fans out twice.
    graph['base_dir'] = '.'
    app = create_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1'):
        job = app.state.application.jobs.launch(graph)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = app.state.application.jobs.details(job['id'])
            if result['status'] not in ACTIVE:
                break
            time.sleep(.1)
        assert result['status'] == 'complete', result
        outputs = list((tmp_path / '.studio/jobs' / job['id']).rglob('table.csv'))
        assert len(outputs) == 3
        content = [file.read_text().strip() for file in outputs]
        assert content.count('value\n2.0\n4.0\n6.0\n8.0\n10.0') == 2
