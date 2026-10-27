"""The installed server exchanges documents; maintenance probes are explicit."""
import json
import sys
import threading
import time
from types import SimpleNamespace
import uuid

import pytest

from biopipe.remote.handshake import (
    CAPABILITIES, HandshakeError, daemon_request, installation_readiness,
)
from biopipe.remote.server import RemoteService


def forbidden(*args, **kwargs):
    raise AssertionError('Routine discovery must not scan, import, inspect, or install')


def request(**values):
    return {**daemon_request()['params'], **values}


@pytest.fixture
def remote(tmp_path, monkeypatch):
    # Cold startup must also be document-only, including bundled provider pins.
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path / 'admission'))
    monkeypatch.setattr('biopipe.packages._provider_paths', forbidden)
    value = RemoteService(tmp_path / 'server', input_roots=[tmp_path])
    monkeypatch.setattr(value.service.plugins, 'refresh', forbidden)
    monkeypatch.setattr(value.service.dependencies, '_inspect', forbidden)
    monkeypatch.setattr('biopipe.install_targets.repair_entries', forbidden)
    yield value
    value.service.shutdown()
    value.handshake.close()


def entries(value):
    return {entry['id']: entry for entry in value['dependencies']['entries']}


def change_registry(remote, update):
    from src.web.storage import atomic_json
    path = remote.service.plugins.registry
    state = json.loads(path.read_text(encoding='utf-8'))
    update(state)
    state['generation'] = uuid.uuid4().hex
    atomic_json(path, state)


def enable_probes(remote, monkeypatch, *, missing=None):
    scans, probes = [], []
    def refresh():
        scans.append(True)
        return {'updated': [], 'unchanged': [], 'generation': remote.handshake.generation}
    def inspect(state, pending):
        probes.append([entry['id'] for entry in pending])
        return {entry['id']: {'status': 'failed' if entry['id'] == missing else 'passed',
                              'error': 'example>=1: not installed' if entry['id'] == missing else ''}
                for entry in pending}
    monkeypatch.setattr(remote.service.plugins, 'refresh', refresh)
    monkeypatch.setattr(remote.service.dependencies, '_inspect', inspect)
    return scans, probes


def refresh(remote, **params):
    started = remote.dispatch('refresh_registry', params)
    assert started['registry_refresh']['running']
    remote.handshake.maintenance_thread.join(timeout=10)
    result = remote.dispatch('refresh_status', {})
    assert not result['registry_refresh']['running']
    assert result['registry_refresh']['error'] is None
    return result


def test_repeated_handshake_uses_documents_and_caches_tool_lookups(remote, monkeypatch):
    lookups = []
    def which(name):
        lookups.append(name)
        return sys.executable
    monkeypatch.setattr('biopipe.remote.handshake.shutil.which', which)
    first = remote.dispatch('handshake', request(client_version='0.1.0'))
    count = len(lookups)
    assert count and len(set(lookups)) == count
    assert first['handshake']['capabilities'] == list(CAPABILITIES)
    assert all(entry['status'] == 'unchecked' for entry in entries(first).values())
    second = remote.dispatch('handshake', request(client_version='999.0.0', known_catalog_digest=first['handshake']['catalog_digest']))
    assert len(lookups) == count
    assert second['handshake'] == first['handshake']
    assert 'catalog' not in second and second['catalog_unchanged'] is True
    # Older clients still receive every original bootstrap field and catalog.
    legacy = remote.dispatch('bootstrap', {})
    assert legacy['catalog'] == first['catalog']
    assert legacy['protocol_version'] == 1


@pytest.mark.parametrize('values,code', [
    ({'version': 2}, 'handshake_incompatible'),
    ({'protocol_version': 2}, 'handshake_incompatible'),
    ({'operator_protocol': 2}, 'handshake_incompatible'),
    ({'required_capabilities': ['unknown-capability']}, 'capability_missing'),
    ({'required_capabilities': 'jobs'}, 'handshake_incompatible'),
])
def test_incompatible_clients_are_rejected_explicitly(remote, values, code):
    with pytest.raises(HandshakeError) as error:
        remote.dispatch('handshake', request(**values))
    assert error.value.code == code


def test_refresh_checks_only_unpassed_and_reports_missing_without_blocking(remote, monkeypatch):
    first = remote.dispatch('handshake', request())
    missing = next(iter(entries(first)))
    scans, probes = enable_probes(remote, monkeypatch, missing=missing)
    refreshed = refresh(remote)
    assert len(probes) == 1 and set(probes[0]) == set(entries(first))
    assert entries(refreshed)[missing]['status'] == 'failed'
    assert 'not installed' in entries(refreshed)[missing]['error']
    remote.dispatch('handshake', request())
    remote.dispatch('handshake', request())
    assert len(scans) == len(probes) == 1
    refresh(remote)
    assert len(scans) == 2 and probes[-1] == [missing]


def test_declaration_changes_keep_readiness_requirements_invalidate_one_entry(remote, monkeypatch):
    _, probes = enable_probes(remote, monkeypatch)
    before = refresh(remote)
    name = next(iter(entries(before)))
    def presentation(state):
        item = next(entry for entry in state['descriptors'] if entry['id'] == name)
        item['title'] = 'Updated presentation'
        item['declaration_sha'] = 'a' * 64
        item['implementation']['declaration_sha'] = 'a' * 64
    change_registry(remote, presentation)
    after = remote.dispatch('handshake', request())
    assert before['handshake']['catalog_digest'] != after['handshake']['catalog_digest']
    assert all(entry['status'] == 'passed' for entry in entries(after).values())
    assert entries(after)[name]['title'] == 'Updated presentation'
    refresh(remote)
    assert len(probes) == 1
    def requirements(state):
        item = next(entry for entry in state['descriptors'] if entry['id'] == name)
        item['dependencies'] = [*item.get('dependencies', []), 'example-new-requirement>=1']
    change_registry(remote, requirements)
    changed = remote.dispatch('handshake', request())
    assert entries(changed)[name]['status'] == 'unchecked'
    assert all(entry['status'] == 'passed' for key, entry in entries(changed).items() if key != name)
    refresh(remote)
    assert probes[-1] == [name]


def test_readiness_and_server_identity_survive_daemon_restart(remote, monkeypatch):
    enable_probes(remote, monkeypatch)
    monkeypatch.setattr('biopipe.remote.handshake.shutil.which', lambda name: sys.executable)
    first = refresh(remote)
    remote.service.shutdown()
    monkeypatch.setattr('biopipe.remote.handshake.shutil.which', forbidden)
    reopened = RemoteService(remote.service.root, input_roots=[remote.service.root.parent])
    try:
        monkeypatch.setattr(reopened.service.dependencies, '_inspect', forbidden)
        second = reopened.dispatch('handshake', request())
        assert first['handshake'] == second['handshake']
        assert all(entry['status'] == 'passed' for entry in entries(second).values())
    finally:
        reopened.service.shutdown()


def test_runtime_identity_change_invalidates_durable_passed_entries(remote, monkeypatch):
    from biopipe.remote.handshake import runtime_identity
    enable_probes(remote, monkeypatch)
    refresh(remote)
    remote.service.shutdown()
    altered = {**runtime_identity(), 'version': 'replacement interpreter'}
    monkeypatch.setattr('biopipe.remote.handshake.runtime_identity', lambda: altered)
    reopened = RemoteService(remote.service.root, input_roots=[remote.service.root.parent])
    try:
        state = reopened.dispatch('handshake', request())
        assert all(entry['status'] == 'unchecked' for entry in entries(state).values())
    finally:
        reopened.service.shutdown()


def test_managed_install_receipt_seeds_matching_base_dependencies(remote, monkeypatch):
    import biopipe.remote.handshake as module
    from biopipe.packages import bundled_manifest
    original_read = module._read
    descriptors = [entry for package in bundled_manifest()['packages'] for entry in package['descriptors']]
    results = {entry['id']: {'status': 'passed', 'error': ''} for entry in descriptors}
    receipt = {'dependency_readiness': installation_readiness(descriptors, results)}
    monkeypatch.setattr(module, '_read', lambda path: receipt if path.name == 'biopipe-ready.json' else original_read(path))
    reopened = module.ManifestHandshake(remote.service, remote.memory)
    assert all(entry['status'] == 'passed' for entry in entries(reopened.response(request())).values())


def test_installer_receipt_cannot_bypass_changed_requirements(remote, monkeypatch):
    import biopipe.remote.handshake as module
    original_read = module._read
    state = json.loads(remote.service.plugins.registry.read_text(encoding='utf-8'))
    results = {entry['id']: {'status': 'passed', 'error': ''} for entry in state['descriptors']}
    receipt = {'dependency_readiness': installation_readiness(state['descriptors'], results)}
    changed = state['descriptors'][0]['id']
    def update(value):
        value['descriptors'][0]['dependencies'] = ['changed-requirement>=1']
    change_registry(remote, update)
    monkeypatch.setattr(module, '_read', lambda path: receipt if path.name == 'biopipe-ready.json' else original_read(path))
    reopened = module.ManifestHandshake(remote.service, remote.memory)
    status = entries(reopened.response(request()))
    assert status[changed]['status'] == 'unchecked'
    assert all(entry['status'] == 'passed' for key, entry in status.items() if key != changed)


def mock_daemon_lock(tmp_path, monkeypatch):
    import biopipe.remote.server as module
    monkeypatch.setitem(sys.modules, 'fcntl', SimpleNamespace(LOCK_EX=1, flock=lambda *args: None))
    monkeypatch.setattr(module, 'socket_path', lambda workspace: tmp_path / 'daemon.sock')
    monkeypatch.setattr(module.subprocess, 'Popen', forbidden)
    return module


def test_compatible_existing_daemon_is_root_independent(remote, tmp_path, monkeypatch):
    module = mock_daemon_lock(tmp_path, monkeypatch)
    value = remote.dispatch('handshake', request())
    value['code_root'] = '/different/installed/server'
    value['version'] = '0.0.other-compatible-version'
    monkeypatch.setattr(module, 'rpc', lambda workspace, params: {'ok': True, 'value': value})
    module.ensure_daemon(remote.service.root)


@pytest.mark.parametrize('response', [
    {'ok': False, 'error': 'Unknown remote operation'},
    {'ok': True, 'value': {'protocol_version': 1, 'code_root': '/legacy'}},
])
def test_legacy_daemon_is_never_restarted(tmp_path, monkeypatch, response):
    module = mock_daemon_lock(tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'rpc', lambda *args: response)
    with pytest.raises(HandshakeError) as error:
        module.ensure_daemon(tmp_path)
    assert error.value.code == 'handshake_required'
    assert 'active jobs finish' in str(error.value)


def test_busy_daemon_is_never_replaced(tmp_path, monkeypatch):
    module = mock_daemon_lock(tmp_path, monkeypatch)
    def busy(*args):
        raise TimeoutError('The existing daemon is busy')
    monkeypatch.setattr(module, 'rpc', busy)
    with pytest.raises(TimeoutError):
        module.ensure_daemon(tmp_path)


def test_startup_errors_have_structured_sentinel(tmp_path, monkeypatch, capsys):
    import biopipe.remote.server as module
    monkeypatch.setattr(sys, 'argv', ['server', '--workspace', str(tmp_path)])
    def incompatible(*args):
        raise HandshakeError('Upgrade the running server', code='handshake_required')
    monkeypatch.setattr(module, 'ensure_daemon', incompatible)
    module.main()
    output = capsys.readouterr().out
    assert output.startswith('BIOPIPE_REMOTE_ERROR ')
    assert json.loads(output.split(' ', 1)[1])['code'] == 'handshake_required'
    assert 'BIOPIPE_REMOTE_READY' not in output


def test_refresh_is_single_flight_and_slow_scan_or_probe_does_not_block_handshakes(remote, monkeypatch):
    scanning, inspecting = threading.Event(), threading.Event()
    scan_release, probe_release = threading.Event(), threading.Event()
    scans = []
    def scan():
        scans.append(True)
        scanning.set()
        assert scan_release.wait(5)
        return {'updated': ['example']}
    def inspect(state, pending):
        inspecting.set()
        assert probe_release.wait(5)
        return {entry['id']: {'status': 'passed', 'error': ''} for entry in pending}
    monkeypatch.setattr(remote.service.plugins, 'refresh', scan)
    monkeypatch.setattr(remote.service.dependencies, '_inspect', inspect)
    try:
        start = time.monotonic()
        first = remote.dispatch('refresh_registry', {})
        assert time.monotonic() - start < 1
        assert first['registry_refresh']['running'] and scanning.wait(1)
        assert remote.dispatch('handshake', request())['registry_refresh']['running']
        assert remote.dispatch('refresh_registry', {})['registry_refresh']['running']
        assert len(scans) == 1
        scan_release.set()
        assert inspecting.wait(1)
        start = time.monotonic()
        during = remote.dispatch('handshake', request())
        assert time.monotonic() - start < 1
        assert during['dependencies']['running']
        assert remote.dispatch('resources', {})
        probe_release.set()
        remote.handshake.maintenance_thread.join(timeout=5)
        finished = remote.dispatch('refresh_status', {})
        assert not finished['registry_refresh']['running']
        assert finished['registry_refresh']['result'] == {'updated': ['example']}
        assert all(entry['status'] == 'passed' for entry in entries(finished).values())
    finally:
        scan_release.set()
        probe_release.set()
        remote.handshake.close()


def test_failed_background_refresh_preserves_readable_registry(remote, monkeypatch):
    first = remote.dispatch('handshake', request())
    def fail():
        raise ValueError('Invalid uploaded provider')
    monkeypatch.setattr(remote.service.plugins, 'refresh', fail)
    remote.dispatch('refresh_registry', {})
    remote.handshake.maintenance_thread.join(timeout=5)
    final = remote.dispatch('refresh_status', {})
    assert final['registry_refresh'] == {'running': False, 'error': 'Invalid uploaded provider', 'result': None}
    assert final['catalog'] == first['catalog']


def test_explicit_verify_all_rechecks_passed_entries(remote, monkeypatch):
    scans, probes = enable_probes(remote, monkeypatch)
    first = refresh(remote)
    refresh(remote)
    assert len(scans) == 2 and len(probes) == 1
    forced = refresh(remote, verify_all=True)
    assert len(scans) == 3 and len(probes) == 2
    assert probes[0] == probes[1]
    assert forced['dependencies'] == first['dependencies']


def test_forced_revalidation_revokes_installer_receipt_before_probe_finishes(remote, monkeypatch):
    import biopipe.remote.handshake as module
    from biopipe.dependencies import DependencySession
    original_read = module._read
    state = json.loads(remote.service.plugins.registry.read_text(encoding='utf-8'))
    results = {entry['id']: {'status': 'passed', 'error': ''} for entry in state['descriptors']}
    receipt = {'dependency_readiness': installation_readiness(state['descriptors'], results)}
    monkeypatch.setattr(module, '_read', lambda path: receipt if path.name == 'biopipe-ready.json' else original_read(path))
    remote.handshake = module.ManifestHandshake(remote.service, remote.memory)
    assert all(entry['status'] == 'passed' for entry in entries(remote.dispatch('handshake', request())).values())
    inspecting, release = threading.Event(), threading.Event()
    def inspect(state, pending):
        inspecting.set()
        assert release.wait(5)
        return {entry['id']: {'status': 'passed', 'error': ''} for entry in pending}
    monkeypatch.setattr(remote.service.plugins, 'refresh', lambda: {})
    monkeypatch.setattr(remote.service.dependencies, '_inspect', inspect)
    try:
        remote.dispatch('refresh_registry', {'verify_all': True})
        assert inspecting.wait(1)
        # Simulate a fresh process reading the durable receipt while the first
        # process has not committed any new successful probes yet.
        copy = SimpleNamespace(**vars(remote.service))
        copy.catalog = dict(remote.service.catalog)
        copy.dependencies = DependencySession(copy.plugins)
        replacement = module.ManifestHandshake(copy, remote.memory)
        assert not replacement.installed
        assert all(entry['status'] == 'unchecked' for entry in copy.dependencies.snapshot()['entries'])
    finally:
        release.set()
        remote.handshake.maintenance_thread.join(timeout=5)
