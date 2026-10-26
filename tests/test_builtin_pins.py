"""Source upgrades must not select an unusable historical bundled lock."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from biopipe.packages import bundled_state
from biopipe.plugins import PluginManager
from src.web.models import Graph

ROOT = Path(__file__).resolve().parents[1]


def test_old_builtin_graph_runs_after_source_upgrade_without_repin(tmp_path, monkeypatch):
    current = deepcopy(bundled_state())
    previous = deepcopy(current)
    for package in previous['packages']:
        if package['name'] == 'biopipe-core':
            package['sha256'] = '0' * 64
    for descriptor in previous['descriptors']:
        if descriptor['distribution'] == 'biopipe-core':
            descriptor['implementation']['sha256'] = '0' * 64
    manager = PluginManager(tmp_path / 'profile')
    graph = Graph.model_validate({'nodes': [{'id': 'summary', 'kind': 'operator',
        'operator': 'describe', 'position': {'x': 0, 'y': 0}, 'params': {}}], 'edges': []})
    with monkeypatch.context() as old:
        old.setattr('biopipe.plugins.bundled_state', lambda: previous)
        graph = manager.pin(graph)
    original = graph.model_dump(mode='json')
    archive = {p: p.read_bytes() for p in (manager.directory / 'snapshots').glob('*.json')}
    state = manager.snapshot(manager.pin(graph))
    job = tmp_path / 'new-job'
    job.mkdir()
    (job / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    (job / 'task.yaml').write_text('sources: {}\nsteps: []\n', encoding='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run.py'), str(job)],
        capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert graph.model_dump(mode='json') == original
    assert all(p.read_bytes() == data for p, data in archive.items())


def test_launch_records_rebinding_and_preserves_history(tmp_path, monkeypatch):
    from src.task import STEPS
    from src.task.operator_catalog import build_catalog
    from src.web.service import JobService, Settings
    previous = deepcopy(bundled_state())
    for package in previous['packages']:
        if package['name'] == 'biopipe-core':
            package['sha256'] = '0' * 64
    for d in previous['descriptors']:
        if d['distribution'] == 'biopipe-core':
            d['implementation']['sha256'] = '0' * 64
    with monkeypatch.context() as old:
        old.setattr('biopipe.plugins.bundled_state', lambda: previous)
        service = JobService(Settings(tmp_path, tmp_path / '.studio', tmp_path, testing=True, code_root=ROOT), build_catalog(STEPS))
        graph = service.plugins.pin(Graph.model_validate(service.demo))
    history = service.jobs_dir / 'previous'
    history.mkdir()
    old_lock = history / 'plugins.lock.json'
    old_lock.write_text(json.dumps(previous), encoding='utf-8')
    before = old_lock.read_bytes()
    try:
        job = service.launch(graph)
        service.threads[job['id']].join(timeout=45)
        final = service.details(job['id'])
        assert final['status'] == 'complete', final
        selected = json.loads((service.jobs_dir / job['id'] / 'plugins.lock.json').read_text())
        assert any(u['operator'] == 'describe' for u in selected['bundled_updates'])
        assert final['plugins']['bundled_updates'] == selected['bundled_updates']
        console = (service.jobs_dir / job['id'] / 'console.log').read_text(encoding='utf-8')
        assert 'Updated bundled source pins' in console
        events = [json.loads(line) for p in (service.jobs_dir / job['id'] / 'output/runs').glob('*/events.jsonl')
                  for line in p.read_text(encoding='utf-8').splitlines()]
        assert any(e['event'] == 'bundled_pins_updated' for e in events)
        assert old_lock.read_bytes() == before
    finally:
        service.shutdown()


def test_builtin_cache_tracks_edits_and_manifest_without_restart(tmp_path, monkeypatch):
    import biopipe.packages as packages
    root = tmp_path / 'checkout'
    (root / 'biopipe').mkdir(parents=True)
    source = root / 'src/task/step/steps/example.py'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'value = 1\n')
    index = root / 'biopipe/builtin_packages.json'
    manifest = {'packages': [{'name': 'example', 'version': '1.0', 'origin': 'bundled',
        'descriptors': [{'id': 'example', 'entry_point': 'src.task.step.steps.example:Example'}]}]}
    index.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(packages, '__file__', str(root / 'biopipe/packages.py'))
    first = packages.bundled_state()
    assert packages.bundled_state() is first
    # Newlines are not an implementation change, including Windows Git checkouts.
    source.write_bytes(b'value = 1\r\n')
    assert packages.bundled_state() == first
    source.write_bytes(b'value = 123\n')
    assert packages.bundled_state()['packages'][0]['sha256'] != first['packages'][0]['sha256']
    manifest['packages'][0]['version'] = '2.0'
    index.write_text(json.dumps(manifest), encoding='utf-8')
    assert packages.bundled_state()['packages'][0]['version'] == '2.0'


def test_nested_builtin_pins_normalize_but_wheel_pins_stay_strict(tmp_path):
    from biopipe.pins import resolve
    state = deepcopy(bundled_state())
    state['generation'] = 'current'
    old = deepcopy(state)
    descriptor = next(d for d in old['descriptors'] if d['id'] == 'describe')
    descriptor['implementation']['sha256'] = '0' * 64
    graph = Graph.model_validate({'nodes': [{'id': 'route', 'kind': 'route', 'position': {'x': 0, 'y': 0},
        'route': {'id': 'route_000000000001', 'version': 1, 'name': 'nested', 'graph': {
            'nodes': [], 'edges': [], 'plugin_lock': {'describe': descriptor['implementation']}}}}],
        'edges': [], 'plugin_lock': {'describe': next(d for d in state['descriptors'] if d['id'] == 'describe')['implementation']}})
    assert resolve(graph, [state, old], bundled_state())['bundled_updates'][0]['operator'] == 'describe'
    # A wheel replacing a bundled provider is still a real, immutable version.
    descriptor['origin'] = 'wheel'
    with pytest.raises(ValueError, match='Conflicting plugin versions'):
        resolve(graph, [state, old], bundled_state())


def test_unknown_pin_is_not_silently_updated(tmp_path):
    manager = PluginManager(tmp_path)
    state = manager.state()
    graph = Graph.model_validate({'nodes': [], 'edges': [], 'plugin_lock': {
        'describe': {'package': 'biopipe-core', 'version': '1.0.0', 'sha256': 'f' * 64}}})
    with pytest.raises(ValueError, match='Unknown or wheel pins'):
        manager.snapshot(graph)


def test_worker_still_rejects_a_stale_frozen_job_lock(tmp_path):
    # Once the job exists, it must not silently execute different source bytes.
    state = deepcopy(bundled_state())
    for descriptor in state['descriptors']:
        if descriptor['distribution'] == 'biopipe-core':
            descriptor['implementation']['sha256'] = '0' * 64
    state.update(package_protocol_version=2, bundled_seen=[p['name'] for p in state['packages']])
    (tmp_path / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    (tmp_path / 'task.yaml').write_text('sources: {}\nsteps: []\n', encoding='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run.py'), str(tmp_path)],
        capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode != 0
    assert 'Bundled implementation changed since this graph was pinned' in result.stderr
    events = [json.loads(line) for path in (tmp_path / 'output/runs').glob('*/events.jsonl')
              for line in path.read_text(encoding='utf-8').splitlines()]
    assert any('Bundled implementation changed' in json.dumps(event) for event in events)


def test_retained_wheel_generation_refreshes_only_bundled_metadata(tmp_path):
    from biopipe.pins import resolve
    state = deepcopy(bundled_state())
    state.update(generation='new', code_paths=['environments/new/code'], shared_paths=['targets/shared'])
    package = {'name': 'lab-tool', 'version': '2', 'sha256': 'new', 'origin': 'wheel', 'enabled': True}
    descriptor = {'id': 'lab.tool', 'distribution': 'lab-tool', 'origin': 'wheel',
                  'implementation': {'package': 'lab-tool', 'version': '2', 'sha256': 'new'},
                  'execution': {'mode': 'isolated', 'paths': ['targets/private']}}
    state['packages'].append(package)
    state['descriptors'].append(descriptor)
    old = deepcopy(state)
    old.update(generation='old', code_paths=['environments/old/code'])
    old['packages'][-1].update(version='1', sha256='old')
    old['descriptors'][-1]['implementation'].update(version='1', sha256='old')
    for p in old['packages']:
        if p['name'] == 'biopipe-core': p['sha256'] = '0' * 64
    for d in old['descriptors']:
        if d['distribution'] == 'biopipe-core': d['implementation']['sha256'] = '0' * 64
    graph = Graph.model_validate({'nodes': [], 'edges': [], 'plugin_lock': {'lab.tool': old['descriptors'][-1]['implementation']}})
    saved = deepcopy(old)
    chosen = resolve(graph, [state, old], bundled_state())
    assert old == saved
    assert chosen['code_paths'] == old['code_paths']
    assert chosen['shared_paths'] == old['shared_paths']
    assert next(d for d in chosen['descriptors'] if d['id'] == 'lab.tool') == old['descriptors'][-1]
    assert next(d for d in chosen['descriptors'] if d['id'] == 'compare_groups')['implementation']['sha256'] != '0' * 64


def test_pin_diagnostic_is_read_only_and_respects_profile(tmp_path):
    profile = tmp_path / 'custom-profile'
    job = profile / 'workspace/.studio/jobs/example'
    job.mkdir(parents=True)
    lock = job / 'plugins.lock.json'
    lock.write_text(json.dumps(bundled_state()), encoding='utf-8')
    graph = profile / 'workspace/.studio/draft.json'
    graph.write_text(json.dumps({'plugin_lock': {'describe': {'sha256': 'old'}}}), encoding='utf-8')
    before = {p: p.read_bytes() for p in (lock, graph)}
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/diagnose_pins.py'), '--profile-dir', str(profile)],
        capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0, result.stderr
    assert 'repin' not in result.stdout.lower()
    assert all(p.read_bytes() == content for p, content in before.items())
    assert not list(profile.rglob('*.bak'))
