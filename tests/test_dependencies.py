"""Readiness is session state, not a timer or a persisted success flag."""
from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from biopipe.dependencies import DependencySession, probe
from biopipe_sdk.dependencies import requirements, source_requirements


def descriptor(name, dependencies=None):
    return {'id': name, 'kind': 'operator', 'title': name, 'version': '1.0.0',
            'distribution': 'lab', 'entry_point': 'lab:' + name,
            'dependencies': dependencies or [], 'implementation': {'sha256': 'original'}}


class Manager:
    def __init__(self, path):
        self.directory = path / 'plugins'
        self.registry = self.directory / 'registry.json'
        self.directory.mkdir()
        self.lock = threading.RLock()
        self.value = {'packages': [{'name': 'lab'}], 'descriptors': [descriptor('a'), descriptor('b', ['missing>=1'])]}
        self.registry.write_text(json.dumps(self.value))
    def state(self): return deepcopy(self.value)
    def python_for(self, state): return state.get('python', 'base')
    def _publish(self, state):
        self.value = deepcopy(state)
        self.registry.write_text(json.dumps(state))
        return state


def test_success_is_cached_failures_retry_new_entries_checked_and_restart_resets(tmp_path):
    manager = Manager(tmp_path)
    calls = []
    fixed = False
    def inspector(python, entries, directory):
        calls.append([e['id'] for e in entries])
        return {e['id']: {'status': 'failed' if e['id'] == 'b' and not fixed else 'passed', 'error': ''} for e in entries}
    session = DependencySession(manager, inspector=inspector)
    session.check(repair=False)
    session.check(repair=False)
    assert calls == [['a', 'b'], ['b']]
    manager.value['descriptors'].append(descriptor('c'))
    fixed = True
    session.check(repair=False)
    assert calls[-1] == ['b', 'c']
    session.check(repair=False)
    assert len(calls) == 3
    assert all(e['status'] == 'passed' for e in session.snapshot()['entries'])
    session2 = DependencySession(manager, inspector=inspector)
    session2.check(repair=False)
    assert calls[-1] == ['a', 'b', 'c']
    assert (tmp_path / 'logs/dependencies.jsonl').is_file()


def test_changed_implementation_invalidates_only_its_own_status(tmp_path):
    manager = Manager(tmp_path)
    calls = []
    def inspector(python, entries, directory):
        calls.append([e['id'] for e in entries])
        return {e['id']: {'status': 'passed', 'error': ''} for e in entries}
    session = DependencySession(manager, inspector=inspector)
    session.check()
    manager.value['descriptors'][1]['implementation']['sha256'] = 'changed'
    session.check()
    assert calls == [['a', 'b'], ['b']]


def test_failed_repair_does_not_publish_or_invalidate_passed_entry(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    original = manager.registry.read_bytes()
    def inspector(python, entries, directory):
        return {e['id']: {'status': 'passed' if e['id'] == 'a' else 'failed', 'error': 'missing'} for e in entries}
    def install(manager, state, entries):
        assert [e['id'] for e in entries] == ['b']
        raise ValueError('ResolutionImpossible: version conflict')
    monkeypatch.setattr('biopipe.install_targets.repair_entries', install)
    session = DependencySession(manager, inspector=inspector)
    state = session.check()
    assert state['running'] is False
    assert state['entries'][0]['status'] == 'passed'
    assert 'version conflict' in state['entries'][1]['error']
    assert manager.registry.read_bytes() == original


def test_repair_publishes_only_after_reprobe_passes(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    calls = []
    def inspector(python, entries, directory):
        calls.append((python, [e['id'] for e in entries]))
        return {e['id']: {'status': 'passed' if e['id'] == 'a' or python == 'candidate' else 'failed', 'error': ''} for e in entries}
    monkeypatch.setattr('biopipe.install_targets.repair_entries', lambda *args, **kwargs: {**manager.state(), 'python': 'candidate'})
    session = DependencySession(manager, inspector=inspector)
    assert all(e['status'] == 'passed' for e in session.check()['entries'])
    assert calls == [('base', ['a', 'b']), ('candidate', ['b'])]
    assert json.loads(manager.registry.read_text())['python'] == 'candidate'


def test_requirements_validate_and_scan_without_importing():
    assert source_requirements('raise RuntimeError()\nclass A:\n dependencies = ["numpy>=1.26"]') == ['numpy>=1.26']
    for value in [['x @ file:///tmp/x'], ['numpy\n--bad'], ['numpy>=??'], 'numpy']:
        with pytest.raises(ValueError): requirements(value)


def test_probe_checks_versions_markers_and_import_errors():
    result = probe([descriptor('a', ['numpy>=0']), descriptor('b', ['numpy<0']),
                    descriptor('c', ['biopipe-impossible-package; python_version < "1"']),
                    {**descriptor('d'), 'dependency_imports': ['biopipe_missing_module']}])
    assert result['a']['status'] == result['c']['status'] == 'passed'
    assert 'installed' in result['b']['error']
    assert 'ModuleNotFoundError' in result['d']['error']


def test_dependency_api_is_token_protected_and_does_not_recheck_success(tmp_path):
    import time
    from fastapi.testclient import TestClient
    from src.web.api import create_app
    from src.web.service import Settings
    root = Path(__file__).resolve().parents[1]
    app = create_app(Settings(tmp_path, tmp_path / 'data', root / 'frontend/dist', testing=True))
    calls = []
    def inspector(python, entries, directory):
        calls.append(len(entries))
        return {e['id']: {'status': 'passed', 'error': ''} for e in entries}
    app.state.service.dependencies.inspector = inspector
    with TestClient(app) as client:
        assert client.post('/api/plugins/dependencies').status_code == 403
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        for _ in range(2):
            operation = client.post('/api/plugins/dependencies').json()
            for _ in range(100):
                operation = client.get('/api/plugins/operations/' + operation['id']).json()
                if operation['status'] != 'running': break
                time.sleep(.02)
            assert operation['status'] == 'complete', operation
        state = client.get('/api/plugins').json()['dependencies']
        assert not state['running']
        assert all(e['status'] == 'passed' for e in state['entries'])
        assert calls == [len(state['entries'])]


def test_shutdown_cancels_probe_process_without_leaving_it_alive(tmp_path):
    import sys
    import time
    import psutil
    from biopipe.plugins import process_context, run_process
    pid_file = tmp_path / 'probe.pid'
    cancel = threading.Event()
    errors = []
    def worker():
        process_context.cancel = cancel
        try:
            run_process([sys.executable, '-c',
                         'import os,sys,time; from pathlib import Path; '
                         'Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)', pid_file])
        except ValueError as exc:
            errors.append(str(exc))
        finally:
            process_context.cancel = None
    thread = threading.Thread(target=worker)
    thread.start()
    deadline = time.monotonic() + 10
    try:
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert pid_file.exists()
    finally:
        cancel.set()
        thread.join(5)
    assert not thread.is_alive()
    assert errors and 'cancelled' in errors[0]
    assert not psutil.pid_exists(int(pid_file.read_text()))


def test_installer_uses_bundled_wheel_when_selected_python_has_no_pip(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    import ensurepip
    wheels = list((Path(ensurepip.__file__).parent / '_bundled').glob('pip-*.whl'))
    if not wheels:
        pytest.skip('This Python vendor does not ship an ensurepip wheel')
    config = tmp_path / 'paths.json'
    config.write_text(json.dumps({'paths': []}), encoding='utf-8')
    probe = subprocess.run([sys.executable, '-I', '-S', '-c',
                            'import importlib.util; assert importlib.util.find_spec("pip") is None'], capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
    bootstrap = Path(__file__).resolve().parents[1] / 'biopipe/runtime_bootstrap.py'
    result = subprocess.run([sys.executable, '-I', '-S', str(bootstrap), str(config), 'pip', '--version'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert '.whl' in result.stdout and 'pip ' in result.stdout
