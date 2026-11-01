"""Native profile storage remains atomic and reentrant at Windows long paths."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from biopipe.bytecode import filesystem_path
from src.web.storage import FileLock, atomic_json


def deep_directory(root):
    path = root
    while len(str(path.resolve())) < 280:
        path /= 'nested-profile-' + 'x' * 32
    return path


def test_atomic_json_long_path_preserves_old_value_and_cleans_failed_write(tmp_path, monkeypatch):
    target = deep_directory(tmp_path) / 'registry.json'
    native = Path(filesystem_path(target, resolve=False))
    first = {'label': '路径', 'wheel': 'packages/hash/example.whl'}
    atomic_json(target, first)
    assert json.loads(native.read_text(encoding='utf-8')) == first
    with pytest.raises(ValueError):
        atomic_json(target, {'invalid': float('nan')})
    assert json.loads(native.read_text(encoding='utf-8')) == first
    assert not list(native.parent.glob('*.tmp'))
    atomic_json(target, {'revision': 2})
    assert json.loads(native.read_text(encoding='utf-8')) == {'revision': 2}
    def failed_replace(*args):
        raise OSError('simulated atomic publication failure')
    with monkeypatch.context() as guard:
        guard.setattr('src.web.storage.os.replace', failed_replace)
        with pytest.raises(OSError, match='publication failure'):
            atomic_json(target, {'revision': 3})
    assert json.loads(native.read_text(encoding='utf-8')) == {'revision': 2}
    assert not list(native.parent.glob('*.tmp'))


def test_file_lock_long_path_reenters_through_native_alias(tmp_path):
    logical = deep_directory(tmp_path) / '.install.lock'
    native = Path(filesystem_path(logical, resolve=False))
    with FileLock(logical, timeout=.2):
        with FileLock(native, timeout=.2):
            assert native.is_file()
    # Both handles have released the same OS lock.
    with FileLock(logical, timeout=.2):
        pass


def test_file_lock_native_alias_excludes_other_processes(tmp_path):
    logical = deep_directory(tmp_path) / '.install.lock'
    native = Path(filesystem_path(logical, resolve=False))
    code = '''import sys
from src.web.storage import FileLock
try:
    with FileLock(sys.argv[1], timeout=.2): print('acquired')
except TimeoutError:
    print('blocked')
'''
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    def probe():
        result = subprocess.run([sys.executable, '-c', code, str(native)], env=environment,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    with FileLock(logical):
        assert probe() == 'blocked'
    assert probe() == 'acquired'


def test_atomic_json_keeps_lexical_path_without_resolving_links(tmp_path, monkeypatch):
    target = tmp_path / 'registry.json'
    monkeypatch.setattr(Path, 'resolve', lambda *a, **k: pytest.fail('atomic write resolved links'))
    atomic_json(target, {'lexical': True})
    assert json.loads(target.read_text()) == {'lexical': True}


def test_deep_profile_snapshot_and_generation_docs_remain_readable(tmp_path):
    from biopipe.plugins import PluginManager
    from biopipe.operator_docs import OperatorDocs
    from src.web.models import Graph
    profile = deep_directory(tmp_path)
    manager = PluginManager(profile, source_root=None, manifest_only=True)
    initial = manager.state()
    graph = manager.pin(Graph.model_validate({'nodes': [
        {'id': 'pca', 'kind': 'operator', 'operator': 'pca', 'params': {}, 'position': {'x': 0, 'y': 0}}
    ], 'edges': []}))
    owner = next(d['distribution'] for d in initial['descriptors'] if d['id'] == 'pca')
    manager.manage(owner, 'disable')
    reopened = PluginManager(profile, source_root=None, manifest_only=True)
    assert reopened.state()['generation'] != initial['generation']
    restored = reopened.snapshot(graph)
    assert restored['generation'] == initial['generation']
    assert not restored['_runtime_root'].startswith('\\\\?\\')
    described = OperatorDocs(reopened).describe(['pca'], sections=['purpose'], generation=initial['generation'])
    assert described['items'][0]['documentation']['content']['purpose']


def test_atomic_json_replaces_final_symlink_without_following_it(tmp_path):
    original = tmp_path / 'original.json'
    original.write_text('{"original": true}', encoding='utf-8')
    link = tmp_path / 'registry.json'
    try:
        link.symlink_to(original)
    except OSError as exc:
        pytest.skip(f'Symlink creation is unavailable: {exc}')
    atomic_json(link, {'replacement': True})
    assert json.loads(original.read_text()) == {'original': True}
    assert not link.is_symlink()
    assert json.loads(link.read_text()) == {'replacement': True}
