"""Deep Windows profiles keep worker results readable through both public APIs."""
import base64
import io
import json
from pathlib import Path
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from biopipe.bytecode import io_path
from biopipe.headless import create_headless_app
from src.web.api import create_app
from src.web.service import Settings


ROOT = Path(__file__).resolve().parents[1]


def deep_workspace(tmp_path):
    root = tmp_path / 'workspace'
    # Keep each component portable, but make ordinary generated run paths cross
    # MAX_PATH. Do not shorten the profile or enable host-wide Windows policies.
    while len(str(root)) < 208:
        root /= 'p' * min(60, max(1, 207 - len(str(root))))
    io_path(root).mkdir(parents=True)
    return root


@pytest.mark.parametrize('host', ['headless', 'desktop'])
def test_deep_profile_worker_outputs_and_api_readback(tmp_path, monkeypatch, host):
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')
    monkeypatch.setenv('BIOPIPE_REGISTRY_MAINTENANCE', '1')
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path / 'admission'))
    root = deep_workspace(tmp_path)
    io_path(root / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    settings = Settings(root, root / '.studio', root / 'no-frontend', testing=True,
                        code_root=ROOT, manifest_only_registry=True)
    app = (create_headless_app if host == 'headless' else create_app)(settings)
    graph = {'schema_version': 2, 'name': 'Deep profile publication regression', 'base_dir': '.',
             'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32,
                        'process_limit_mb': 768, 'chunk_mb': .01, 'io_buffer_kb': 4, 'keep': ['input']},
             'nodes': [{'id': 'input', 'kind': 'source', 'source': {'path': 'input.csv',
                        'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                       {'id': 'summary', 'kind': 'operator', 'operator': 'describe', 'params': {}},
                       {'id': 'plot', 'kind': 'operator', 'operator': 'scatter',
                        'params': {'dim': 'feature', 'x_label': 'a', 'y_label': 'b',
                                   'filename': 'deep-profile.png', 'figure_width_mm': 70,
                                   'figure_height_mm': 55, 'figure_dpi': 72}}],
             'edges': [{'id': 'summary-edge', 'source': 'input', 'target': 'summary'},
                       {'id': 'plot-edge', 'source': 'input', 'target': 'plot'}]}
    with TestClient(app, base_url='http://127.0.0.1') as client:
        connected = client.post('/api/agent/connect', headers={'X-BioPipe-Bridge': app.state.bridge.secret},
                                json={'name': 'deep-profile-test', 'scopes': ['context', 'edit', 'run']})
        assert connected.status_code == 200, connected.text
        client.headers.update({'Authorization': 'Bearer ' + connected.json()['token']})
        response = client.post('/api/v1/jobs', json={'graph': graph})
        assert response.status_code == 202, response.text
        key = response.json()['id']
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            response = client.get(f'/api/v1/jobs/{key}')
            assert response.status_code == 200, response.text
            result = response.json()
            if result['status'] not in {'queued', 'running'}:
                break
            time.sleep(.1)
        assert result['status'] == 'complete', result.get('error') or result
        service = app.state.service
        directory = service.jobs_dir / key
        assert result['progress']['percent'] == 100
        assert result['report'] and result['summary']['status'] == 'complete'
        assert len(result['summary']['memory_report']) > 260
        assert not result['summary']['memory_report'].startswith('\\\\?\\')
        paths = service.event_paths(key)
        assert paths and max(len(str(path)) for path in paths) > 260
        assert all(not str(path).startswith('\\\\?\\') for path in paths)
        assert service.events_path(key) in paths
        assert any(item['id'] == key for item in service.history())
        assert set(service.spill_counts(key)) == {'planned', 'emergency', 'final', 'correction'}
        _, snapshot = service.console_snapshot(key, result)
        assert '[describe]' in snapshot['console']

        console, offset = [], 0
        while True:
            part = client.get(f'/api/v1/jobs/{key}/logs', params={'offset': offset, 'limit': 97}).json()
            console.append(base64.b64decode(part['base64']))
            offset = part['offset']
            if part['done']:
                break
        assert '[describe]' in b''.join(console).decode('utf-8')
        frozen = json.loads(io_path(directory / 'parameters.json').read_text(encoding='utf-8'))
        assert next(step for step in frozen['steps'] if step['name'] == 'scatter')['params']['figure_width_mm'] == 70

        listing = client.get(f'/api/v1/jobs/{key}/artifacts').json()
        summary = next(item for item in listing['reports'] if item['name'] == 'describe')
        assert client.get(summary['href']).json()['global']['mean'] == 2.5
        retained = next(item for item in listing['artifacts'] if item['available'] and item['name'] == 'input')
        response = client.get(retained['href'])
        assert response.status_code == 200, response.text
        np.testing.assert_array_equal(np.load(io.BytesIO(response.content), allow_pickle=False), [[1, 2], [3, 4]])
        figures = listing['figures']
        assert {item['format'] for item in figures} == {'png', 'pdf', 'svg'}
        originals = {}
        for figure in figures:
            assert len(figure['path']) > 260
            assert not figure['path'].startswith('\\\\?\\')
            response = client.get(figure['href'])
            assert response.status_code == 200, response.text
            assert response.content == io_path(figure['path']).read_bytes()
            originals[figure['format']] = response.content
        assert originals['png'].startswith(b'\x89PNG\r\n\x1a\n')
        assert originals['pdf'].startswith(b'%PDF-')
        assert b'<svg' in originals['svg']

        if host == 'desktop':
            # Desktop routes and the agent API share the service but have
            # separate final file/SSE response boundaries.
            client.headers['X-Studio-Token'] = app.state.token
            assert client.get(f'/api/jobs/{key}/console').content == b''.join(console)
            events = client.get(f'/api/jobs/{key}/events')
            assert events.status_code == 200 and 'step_finished' in events.text
            response = client.get(f'/api/jobs/{key}/exports/{summary["index"]}')
            assert response.status_code == 200, response.text
            assert response.json()['global']['mean'] == 2.5
            response = client.get(f'/api/jobs/{key}/exports/{summary["index"]}/download')
            assert response.status_code == 200 and response.json()['global']['mean'] == 2.5
            plot = next(item for item in listing['reports'] if item['name'] == 'scatter')
            for fmt, original in originals.items():
                response = client.get(f'/api/jobs/{key}/exports/{plot["index"]}/figure', params={'format': fmt})
                assert response.status_code == 200 and response.content == original
            response = client.get(f'/api/jobs/{key}/artifacts/{retained["artifact_id"]}/download')
            assert response.status_code == 200
            np.testing.assert_array_equal(np.load(io.BytesIO(response.content), allow_pickle=False), [[1, 2], [3, 4]])

        # Existing containment policy must still reject a recorded external
        # figure. The native I/O alias is applied only after these checks.
        plot = next(item for item in listing['reports'] if item['name'] == 'scatter')
        report_path = service.export_file(key, plot['index'])
        saved_report = json.loads(io_path(report_path).read_text(encoding='utf-8'))
        outside = tmp_path / 'outside.svg'
        io_path(outside).write_text('<svg/>', encoding='utf-8')
        tampered = {**saved_report, 'path': str(outside), 'figures': []}
        io_path(report_path).write_text(json.dumps(tampered), encoding='utf-8')
        rejected = client.get(f'/api/v1/jobs/{key}/reports/{plot["index"]}/figure')
        assert rejected.status_code == 404
        io_path(report_path).write_text(json.dumps(saved_report), encoding='utf-8')
