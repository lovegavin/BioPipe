"""Library mutations remain visible without blocking routine editor requests."""
import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from operon.plugins import PluginManager
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def application(tmp_path):
    return create_app(Settings(tmp_path, tmp_path / '.studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, manifest_only_registry=True))


def test_unchanged_editor_requests_do_not_reparse_registry_or_stage_scripts(tmp_path, monkeypatch):
    app = application(tmp_path)
    with TestClient(app) as client:
        boot = client.get('/api/bootstrap').json()
        unchanged = client.get('/api/operators', params={'generation': boot['catalog']['plugin_generation']})
        assert unchanged.status_code == 200 and unchanged.json() is None
        manager = app.state.service.plugins
        monkeypatch.setattr(manager, 'state', lambda: pytest.fail('Unchanged catalog reread the registry'))
        assert client.get('/api/operators').status_code == 200
        response = client.post('/api/scripts/inspect', headers={'X-Studio-Token': boot['token']},
                               json={'filename': 'untouched.py', 'code': '\ufeffvalue = 2\nraise RuntimeError("never run")'})
        assert response.status_code == 200, response.text
        assert response.json()['candidates'][0]['schema']['default'] == 2
        assert not (app.state.service.directory / 'script-inspection').exists()


def test_external_atomic_library_changes_invalidate_catalog(tmp_path):
    app = application(tmp_path)
    with TestClient(app) as client:
        before = client.get('/api/operators').json()
        other = PluginManager(app.state.service.directory)
        package = other.state()['packages'][0]['name']
        other.manage(package, 'disable')
        after = client.get('/api/operators', params={'generation': before['plugin_generation']}).json()
        assert before['plugin_generation'] != after['plugin_generation']
        assert len(after['operators']) + len(after.get('readers', [])) < len(before['operators']) + len(before.get('readers', []))
        other.manage(package, 'enable')
        restored = client.get('/api/operators').json()
        assert restored['operators'] == before['operators']


def test_catalog_refresh_does_not_run_file_io_on_async_server_loop(tmp_path, monkeypatch):
    app = application(tmp_path)
    original = app.state.service.refresh_catalog
    def refresh():
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        return original()
    monkeypatch.setattr(app.state.service, 'refresh_catalog', refresh)
    with TestClient(app) as client:
        assert client.get('/api/operators').status_code == 200


def test_replace_during_read_is_not_hidden_by_a_later_file_stamp(tmp_path, monkeypatch):
    app = application(tmp_path)
    manager = app.state.service.plugins
    other = PluginManager(app.state.service.directory)
    original = manager.state
    with TestClient(app) as client:
        client.get('/api/operators')
        first = other.state()
        first['bundled_seen'].append('first-external-edit')
        other._publish(first)
        latest = {}
        def state():
            value = original()
            update = deepcopy(value)
            update['bundled_seen'].append('during-read')
            latest.update(other._publish(update))
            return value
        monkeypatch.setattr(manager, 'state', state)
        client.get('/api/operators')
        monkeypatch.setattr(manager, 'state', original)
        assert client.get('/api/operators').json()['plugin_generation'] == latest['generation']


def test_unchanged_source_refresh_hashes_without_staging_and_detects_same_size_edit(tmp_path, monkeypatch):
    from operon import source_library
    root = tmp_path / 'sources'
    for directory in ('src/task/step/steps', 'src/reader/readers', 'operon'):
        (root / directory).mkdir(parents=True)
    code = root / 'src/task/step/steps/example.py'
    code.write_text('value = 1\n', encoding='utf-8')
    (root / 'operon/builtin_packages.json').write_text('{"packages": []}', encoding='utf-8')
    fingerprint = source_library.snapshot_sources(root, tmp_path / 'initial-copy')
    assert fingerprint == source_library.snapshot_sources(root)
    manager = SimpleNamespace(source_root=root, managed_sources=False)
    current = {'packages': [], 'source_library': {'sha256': fingerprint, 'packages': []}}
    original = source_library.snapshot_sources
    def snapshot(root, staged=None):
        if staged is not None:
            raise RuntimeError('changed-source-snapshot')
        return original(root)
    monkeypatch.setattr(source_library, 'snapshot_sources', snapshot)
    result = source_library.prepare(manager, current, tmp_path / 'refresh')
    assert result['updated'] == [] and result['wheels'] == []
    assert not (tmp_path / 'refresh').exists()
    code.write_text('value = 2\n', encoding='utf-8')
    with pytest.raises(RuntimeError, match='changed-source-snapshot'):
        source_library.prepare(manager, current, tmp_path / 'changed')
