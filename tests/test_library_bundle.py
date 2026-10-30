"""A library update cannot replace the application or partially publish providers."""
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest

from biopipe.library_bundle import build_bundle, unpack_bundle
from biopipe.plugins import PluginManager
from biopipe.source_library import SOURCE_DIRS
from test_packages import run_worker

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def library_bundle(tmp_path_factory):
    return Path(build_bundle(ROOT, tmp_path_factory.mktemp('library'), '1.0.0')['bundle'])


def test_sources_are_lazy_persistent_and_outside_application(tmp_path):
    manager = PluginManager(tmp_path)
    assert manager.manifest_only
    manager.state()
    target = manager.source_root
    assert target.is_relative_to(tmp_path) and not target.exists()
    manager.ensure_source_root()
    parameter = next((target / SOURCE_DIRS['operator']).glob('*.parameters.json'))
    parameter.write_text('{"author_edit": true}', encoding='utf-8')
    restarted = PluginManager(tmp_path)
    restarted.ensure_source_root()
    assert restarted.source_root == target
    assert json.loads(parameter.read_text()) == {'author_edit': True}
    assert json.loads((ROOT / parameter.relative_to(target)).read_text()) != {'author_edit': True}


def test_explicit_refresh_detaches_factory_without_changing_application(tmp_path):
    manager = PluginManager(tmp_path)
    original = manager.state()
    result = manager.refresh()
    assert result['updated']
    state = manager.state()
    assert state['library_detached']
    assert all(p['origin'] == 'wheel' for p in state['packages'])
    assert {d['id'] for d in state['descriptors']} == {d['id'] for d in original['descriptors']}
    assert manager.refresh()['generation'] == state['generation']
    # Simulate a profile already refreshed by 0.8.2, before source-root receipts.
    from biopipe.plugins import atomic_json
    state.pop('library_detached')
    state['source_library'].pop('root')
    atomic_json(manager.registry, state)
    manager.refresh()
    assert manager.state()['library_detached']
    assert manager.state()['source_library']['root']


def test_bundle_validation_and_atomic_independent_install(tmp_path, library_bundle, monkeypatch):
    manager = PluginManager(tmp_path / 'profile')
    before = manager.state()
    manager.manage('biopipe-microbiome', 'disable')
    state = manager.install(library_bundle)
    assert state['generation'] != before['generation']
    assert {d['id'] for d in state['descriptors']} == {d['id'] for d in before['descriptors']}
    assert all(p['origin'] == 'wheel' for p in state['packages'])
    assert next(p for p in state['packages'] if p['name'] == 'biopipe-microbiome')['enabled'] is False
    assert manager.source_root.is_relative_to(tmp_path)
    assert manager.source_root.joinpath('biopipe/builtin_packages.json').is_file()
    assert manager.refresh()['updated'] == []
    assert manager.install(library_bundle)['generation'] == state['generation']
    # A newer factory library in the application must not replace an installed one.
    changed = deepcopy(manager.bundled_state())
    for p in changed['packages']:
        p['sha256'] = 'factory-upgrade'
    changed['packages'].append({**changed['packages'][0], 'name': 'new-factory-provider'})
    monkeypatch.setattr(manager, 'bundled_state', lambda: changed)
    assert manager.state()['generation'] == state['generation']
    assert not any(p['name'] == 'new-factory-provider' for p in manager.state()['packages'])
    # Real worker uses the separately installed Reader/step and memory planner.
    data = tmp_path / 'input.csv'
    data.write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    _, summary = run_worker(manager, state, tmp_path / 'run',
        {'X': {'path': str(data), 'dims': ['sample', 'feature'], 'labels': {'feature': 'builtin'}}},
        [{'name': 'describe', 'inputs': ['X']}])
    assert summary['steps']
    # Tampering and an unrefreshed local edit must both leave the registry intact.
    damaged = tmp_path / 'damaged.biopipe-library.zip'
    with zipfile.ZipFile(library_bundle) as source, zipfile.ZipFile(damaged, 'w') as destination:
        first = next(n for n in source.namelist() if n.endswith('.parameters.json'))
        for entry in source.infolist():
            destination.writestr(entry, b'{}' if entry.filename == first else source.read(entry.filename))
    with pytest.raises(ValueError, match='checksum'):
        manager.install(damaged)
    assert manager.state()['generation'] == state['generation']
    parameter = next((manager.source_root / SOURCE_DIRS['operator']).glob('*.parameters.json'))
    parameter.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='unrefreshed'):
        manager.install(library_bundle)
    assert manager.state()['generation'] == state['generation']


def test_unsafe_archive_is_rejected_before_writing(tmp_path):
    path = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('../outside.py', 'raise RuntimeError()')
    with pytest.raises(ValueError, match='archive path'):
        unpack_bundle(path, tmp_path / 'unpack')
    assert not (tmp_path / 'outside.py').exists()
