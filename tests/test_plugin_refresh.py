"""Drop-ins are validated transactions, with real workers and version retention."""
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from biopipe.dropins import single_file_wheel, snapshot
from biopipe.plugins import PluginManager, run_process
from src.web.api import create_app
from src.web.models import Graph
from src.web.service import Settings
from test_packages import run_worker

ROOT = Path(__file__).resolve().parents[1]
REPORT = '''from biopipe_sdk import Step
class Hello(Step):
    name = "lab.hello"
    category = "Quality control"
    icon = "CheckCircle"
    input_contracts = []
    output_contract = {"mode": "report"}
    parameters_schema = {"type": "object"}
    def run(self, ctx, inputs): pass
    def export(self, ctx): return {"value": 1}
'''


def test_probe_transport_preserves_unicode_and_failure_details(monkeypatch):
    monkeypatch.setenv('PYTHONIOENCODING', 'ascii')
    script = 'print(chr(0x4e2d) + chr(0xb2))'
    for environment in (None, dict(os.environ)):
        assert run_process([sys.executable, '-c', script], env=environment).strip() == '\u4e2d\u00b2'
    with pytest.raises(ValueError) as failure:
        run_process([sys.executable, '-c',
            'import sys; print("Dependency conflict details"); '
            'print("Resolver failed", file=sys.stderr); sys.exit(2)'])
    assert 'Dependency conflict details' in str(failure.value)
    assert 'Resolver failed' in str(failure.value)


def test_single_file_wrapper_is_deterministic_and_does_not_execute(tmp_path):
    source = tmp_path / 'a' / 'hello.py'
    source.parent.mkdir()
    source.write_text('raise AssertionError("must not import here")\n' + REPORT, encoding='utf-8')
    other = tmp_path / 'b' / 'hello.py'
    other.parent.mkdir()
    shutil.copy2(source, other)
    first = single_file_wheel(source, tmp_path / 'w1')
    second = single_file_wheel(other, tmp_path / 'w2')
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert any(n.endswith('/entry_points.txt') for n in archive.namelist())
        assert all(str(tmp_path).encode() not in archive.read(n) for n in archive.namelist())
    source.write_text('BIOPIPE_PLUGIN = {"dependencies": ["numpy\\nInvalid: value"]}\n' + REPORT)
    with pytest.raises(ValueError, match='requirement strings'):
        single_file_wheel(source, tmp_path / 'bad')


def test_snapshot_ignores_build_products_and_detects_real_changes(tmp_path):
    source = tmp_path / 'project'
    source.mkdir()
    (source / 'pyproject.toml').write_text('[project]\nname="hello"')
    (source / 'hello.py').write_text(REPORT)
    first = snapshot(source, tmp_path / 'one')
    (source / 'dist').mkdir()
    (source / 'dist/hello.whl').write_bytes(b'build artifact')
    assert snapshot(source, tmp_path / 'two') == first
    (source / 'hello.py').write_text(REPORT + '\n# changed\n')
    assert snapshot(source, tmp_path / 'three') != first


def test_empty_and_syntax_failure_leave_registry_unchanged(tmp_path, monkeypatch):
    manager = PluginManager(tmp_path, source_root=None)
    initial = manager.state()
    monkeypatch.setattr(manager, '_install_many', lambda *a, **kw: pytest.fail('must not install'))
    assert manager.refresh()['updated'] == []
    (manager.inbox / 'good.py').write_text(REPORT)
    (manager.inbox / 'bad.py').write_text('class Broken(')
    with pytest.raises(ValueError, match='bad.py'):
        manager.refresh()
    assert manager.state() == initial
    assert not list((manager.directory / 'staging').iterdir())


def test_dropins_hot_run_update_rollback_and_retained_pins(tmp_path, monkeypatch):
    manager = PluginManager(tmp_path / 's', source_root=None)
    hello = manager.inbox / 'hello.py'
    hello.write_text('BIOPIPE_PLUGIN = {"name": "lab-hello", "dependencies": ["numpy>=1.26"]}\n' + REPORT)
    resource = manager.inbox / 'resources.py'
    shutil.copy2(ROOT / 'examples/resource_plugin/resource_example/__init__.py', resource)
    before_modules = set(sys.modules)
    result = manager.refresh()
    assert result['updated'] == ['hello.py', 'resources.py']
    assert not any(n.startswith('biopipe_dropin_') for n in set(sys.modules) - before_modules)
    old = manager.state()
    descriptor = next(d for d in old['descriptors'] if d['id'] == 'lab.hello')
    assert descriptor['category'] == 'Quality control' and descriptor['icon'] == 'CheckCircle'
    path = tmp_path / 'array.npy'
    np.save(path, np.arange(12).reshape(3, 4))
    report, summary = run_worker(manager, old, tmp_path / 'run',
        {'X': {'path': str(path), 'dims': ['sample', 'feature']}},
        [{'name': 'example.stream_sum', 'inputs': ['X']}, {'name': 'lab.hello', 'inputs': []}])
    assert report['plans'][0]['mode'] == 'stream'
    assert report['event_counts']['source_prepare_complete'] == 1
    exported = json.loads((tmp_path / 'run/output' / summary['steps'][0]['export_path']).read_text())
    assert exported['sum'] == 66
    graph = Graph.model_validate({'nodes': [{'id': 'hello', 'kind': 'operator', 'operator': 'lab.hello',
                                            'position': {'x': 0, 'y': 0}}], 'edges': []})
    pinned = manager.pin(graph)
    # Changing the implementation without changing its version must invalidate the hash.
    hello.write_text(hello.read_text().replace('"value": 1', '"value": 2'))
    assert manager.refresh()['updated'] == ['hello.py']
    current = manager.state()
    assert current['generation'] != old['generation']
    assert manager.snapshot(pinned)['generation'] == old['generation']
    for state, expected, name in [(old, 1, 'old'), (current, 2, 'new')]:
        _, summary = run_worker(manager, state, tmp_path / name, {}, [{'name': 'lab.hello', 'inputs': []}])
        assert json.loads((tmp_path / name / 'output' / summary['steps'][0]['export_path']).read_text())['value'] == expected
    manager.manage('lab-hello', 'disable')
    disabled = manager.state()
    with monkeypatch.context() as scoped:
        scoped.setattr(manager, '_install_many', lambda *a, **kw: pytest.fail('unchanged refresh rebuilt environment'))
        assert manager.refresh()['updated'] == []
        assert manager.state() == disabled
    # A valid edit plus a duplicate ID must fail as one batch; neither is published.
    hello.write_text(hello.read_text().replace('"value": 2', '"value": 3'))
    duplicate = manager.inbox / 'duplicate.py'
    duplicate.write_text(REPORT)
    with pytest.raises(ValueError, match='same ID'):
        manager.refresh()
    assert manager.state() == disabled
    duplicate.unlink()
    manager.refresh()
    assert next(p for p in manager.state()['packages'] if p['name'] == 'lab-hello')['enabled'] is False
    manager.manage('lab-hello', 'remove')
    assert manager.refresh()['updated'] == []  # Refresh must not undo an explicit removal.
    assert not any(p['name'] == 'lab-hello' for p in manager.state()['packages'])


def test_refresh_api_is_async_token_protected_and_reports_errors(tmp_path, monkeypatch):
    app = create_app(Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True))
    manager = app.state.service.plugins
    entered, release = threading.Event(), threading.Event()
    def refresh():
        entered.set()
        assert release.wait(10)
        raise ValueError('broken.py: invalid output_contract')
    monkeypatch.setattr(manager, 'refresh', refresh)
    with TestClient(app) as client:
        token = client.get('/api/bootstrap').json()['token']
        assert client.post('/api/plugins/refresh').status_code == 403
        assert client.post('/api/plugins/open-folder').status_code == 403
        client.headers['X-Studio-Token'] = token
        assert client.post('/api/plugins/open-folder', json={'kind': []}).status_code == 422
        initial = manager.state()
        result = client.post('/api/plugins/refresh').json()
        assert entered.wait(5)
        assert client.post('/api/plugins/refresh').status_code == 409
        assert client.get('/api/operators').status_code == 200
        assert client.get('/api/plugins').json()['inbox'] == str(manager.inbox)
        release.set()
        for _ in range(100):
            operation = client.get('/api/plugins/operations/' + result['id']).json()
            if operation['status'] != 'running':
                break
            time.sleep(.01)
        assert operation['status'] == 'failed' and 'broken.py' in operation['error']
        assert manager.state() == initial


def test_source_library_discovers_plain_author_modules_without_manifest_edits(tmp_path, monkeypatch):
    import re
    from biopipe.source_library import SOURCE_DIRS
    source_root = tmp_path / 'code'
    for relative in [*SOURCE_DIRS.values(), 'biopipe/builtin_packages.json']:
        source, target = ROOT / relative, source_root / relative
        if source.is_dir():
            target.mkdir(parents=True)
            for file in source.glob('*.py'):
                # This lifecycle fixture exercises source registration and disk
                # hooks without downloading every optional native reader. Real
                # dependency declarations/repairs have their own tests.
                code = file.read_text(encoding='utf-8')
                code = re.sub(r'(?m)^    (dependencies|dependency_imports) = .+$', r'    \1 = []', code)
                (target / file.name).write_text(code, encoding='utf-8')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    manifest_before = (source_root / 'biopipe/builtin_packages.json').read_bytes()
    new_operator = source_root / SOURCE_DIRS['operator'] / 'hello.py'
    # Existing author style: original, unqualified IDs are accepted in their provider.
    new_operator.write_text(REPORT.replace('lab.hello', 'hello_hot').replace('CheckCircle', 'assets/hello.svg'))
    (new_operator.parent / 'assets').mkdir()
    (new_operator.parent / 'assets/hello.txt').write_text('retained resource')
    icon = new_operator.parent / 'assets/hello.svg'
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle r="8" fill="red"/></svg>')
    new_reader = source_root / SOURCE_DIRS['reader'] / 'hot_reader.py'
    new_reader.write_text((ROOT / 'examples/resource_plugin/resource_example/__init__.py').read_text().replace(
        'NpyReader', 'HotArrayReader').replace('example.disk_npy', 'HotArrayReader'))
    manager = PluginManager(tmp_path / 's', source_root=source_root)
    initial = manager.refresh()
    state = manager.state()
    assert len(initial['updated']) == 6
    descriptor = next(d for d in state['descriptors'] if d['id'] == 'hello_hot')
    assert descriptor['distribution'] == 'biopipe-core'
    assert descriptor['category'] == 'Quality control'
    assert descriptor['icon_image'].startswith('data:image/svg+xml;base64,')
    core = next(p for p in state['packages'] if p['name'] == 'biopipe-core')
    with zipfile.ZipFile(manager.directory / core['wheel']) as archive:
        resource_file = next(n for n in archive.namelist() if n.endswith('/steps/assets/hello.txt'))
        assert archive.read(resource_file) == b'retained resource'
    reader = next(d for d in state['descriptors'] if d['id'] == 'HotArrayReader')
    assert reader['resources']['disk_protocol'] == 'dense-writer-v1'
    path = tmp_path / 'array.npy'
    np.save(path, np.arange(12).reshape(3, 4))
    report, _ = run_worker(manager, state, tmp_path / 'reader',
        {'X': {'path': str(path), 'dims': ['sample', 'feature']}}, [{'name': 'describe', 'inputs': ['X']}])
    assert report['plans'][0]['mode'] == 'stream' and report['event_counts']['source_prepare_complete'] == 1
    assert (source_root / 'biopipe/builtin_packages.json').read_bytes() == manifest_before
    with monkeypatch.context() as scoped:
        scoped.setattr(manager, '_install_many', lambda *a, **kw: pytest.fail('unchanged library was rebuilt'))
        assert manager.refresh()['updated'] == []
    new_operator.write_text(new_operator.read_text().replace('"value": 1', '"value": 2'))
    icon.write_text(icon.read_text().replace('red', 'blue'))
    manager.refresh()
    newer = manager.state()
    assert next(d for d in newer['descriptors'] if d['id'] == 'hello_hot')['icon_image'] != descriptor['icon_image']
    # A failed source edit retains the successfully frozen code and catalog.
    new_operator.write_text('class Broken(')
    with pytest.raises(ValueError, match='hello.py'):
        manager.refresh()
    assert manager.state() == newer
    for lock, expected, directory in [(state, 1, 'old'), (newer, 2, 'new')]:
        _, summary = run_worker(manager, lock, tmp_path / directory, {}, [{'name': 'hello_hot', 'inputs': []}])
        result = json.loads((tmp_path / directory / 'output' / summary['steps'][0]['export_path']).read_text())
        assert result['value'] == expected
