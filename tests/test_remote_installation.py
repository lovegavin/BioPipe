"""Separate server discovery from installation across desktop versions."""
from copy import deepcopy
import json
import threading
from types import SimpleNamespace

import pytest

from biopipe.remote.client import RemoteError, SSHConnection
from biopipe.remote.handshake import CAPABILITIES
from biopipe.remote.installation import validate
from biopipe.remote import provision


def receipt():
    return {'schema_version': 1, 'server_id': 'server-identity', 'version': '0.7.1',
            'app_dir': '/srv/shared/biopipe', 'python': '/srv/shared/python/bin/python',
            'workspace': '/srv/jobs'}


def info():
    return {'protocol_version': 1, 'version': '99.2.0', 'catalog': {'operators': [], 'readers': []},
            'handshake': {'version': 1, 'operator_protocol': 3, 'catalog_digest': 'registry-digest',
                          'server_id': 'server-identity', 'capabilities': list(CAPABILITIES)}}


def test_discovery_reads_receipt_without_archiving_uploading_or_installing(monkeypatch):
    commands = []
    class Shell:
        def __init__(self, *args): pass
        def run(self, command, **kwargs):
            commands.append(command)
            if 'BP_HOME' in command: return 'BP_HOME=/home/researcher'
            return 'BP_SERVER_DOCUMENT\n' + json.dumps(receipt()) + '\nBP_SERVER_END'
        def upload(self, *args): pytest.fail('Routine discovery uploaded data')
    monkeypatch.setattr(provision, 'Shell', Shell)
    monkeypatch.setattr(provision, 'source_archive', lambda *a: pytest.fail('Routine discovery scanned local code'))
    for desktop in ('desktop-A', 'desktop-B'):
        result = provision.locate(None, {'name': desktop}, lambda m: None, threading.Event())
        assert result['app_dir'] == '/srv/shared/biopipe'
        assert result['python'] == '/srv/shared/python/bin/python'
        assert result['workspace'] == '/srv/jobs'
    assert len(commands) == 4
    assert not any(word in ' '.join(commands) for word in ('find ', 'pip ', 'mkdir ', 'tar ', 'source-'))
    assert '/home/researcher/.local/share/biopipe/server.json' in commands[-1]


def test_discovery_preserves_explicit_workspace_and_reports_missing_registration(monkeypatch):
    class Shell:
        output = ''
        def __init__(self, *args): pass
        def run(self, *args, **kwargs): return self.output
    monkeypatch.setattr(provision, 'Shell', Shell)
    config = {'managed_root': '/custom/server', 'workspace': '/my-project'}
    with pytest.raises(RemoteError) as failure:
        provision.locate(None, config, lambda m: None, threading.Event())
    assert failure.value.code == 'server_not_installed'
    Shell.output = 'BP_SERVER_DOCUMENT\n' + json.dumps(receipt()) + '\nBP_SERVER_END'
    assert provision.locate(None, config, lambda m: None, threading.Event())['workspace'] == '/my-project'


@pytest.mark.parametrize('patch', [{'schema_version': 2}, {'python': '../python'}, {'app_dir': '/srv/../etc'},
                                  {'workspace': '/srv/path\ncommand'}, {'server_id': None}])
def test_installation_document_rejects_invalid_entries(patch):
    with pytest.raises(ValueError): validate({**receipt(), **patch})


def test_handshake_accepts_different_app_version_and_reuses_matching_catalog():
    connection = SSHConnection.__new__(SSHConnection)
    cached = info()
    fresh = deepcopy(cached); fresh.pop('catalog'); fresh['catalog_unchanged'] = True
    requests = []
    connection.call = lambda method, params: (requests.append((method, params)) or fresh)
    result = connection.handshake(cached)
    assert result['catalog'] == cached['catalog']
    assert result['version'] == '99.2.0'
    assert requests[0][0] == 'handshake'
    assert requests[0][1]['known_catalog_digest'] == 'registry-digest'
    assert 'app_version' not in requests[0][1]


@pytest.mark.parametrize('problem', ['protocol', 'capability', 'uncached', 'digest'])
def test_handshake_rejects_incompatible_or_unproven_cache(problem):
    connection = SSHConnection.__new__(SSHConnection)
    result = info()
    if problem == 'protocol': result['protocol_version'] = 7
    if problem == 'capability': result['handshake']['capabilities'] = ['jobs']
    if problem in ('uncached', 'digest'):
        result.pop('catalog'); result['catalog_unchanged'] = True
    if problem == 'digest': result['handshake']['catalog_digest'] = 'changed'
    connection.call = lambda *args: result
    with pytest.raises(RemoteError): connection.handshake(info() if problem == 'digest' else None)


@pytest.mark.parametrize('install', [False, True])
def test_managed_transport_invokes_only_requested_install_action(monkeypatch, install):
    import paramiko
    calls, sent = [], []
    channel = SimpleNamespace(settimeout=lambda *a: None, exec_command=lambda c: sent.append(c),
                              sendall=lambda c: sent.append(c), close=lambda: None)
    transport = SimpleNamespace(open_session=lambda **k: channel, set_keepalive=lambda *a: None)
    client = SimpleNamespace(set_missing_host_key_policy=lambda p: None, connect=lambda *a, **k: None,
                             get_transport=lambda: transport, close=lambda: None)
    monkeypatch.setattr(paramiko, 'SSHClient', lambda: client)
    def action(name):
        def run(connection, profile, *args):
            calls.append(name)
            return {**profile, 'app_dir': '/shared/app', 'python': '/shared/bin/python', 'workspace': '/shared/work'}
        return run
    monkeypatch.setattr(provision, 'locate', action('locate'))
    monkeypatch.setattr(provision, 'provision', action('install'))
    monkeypatch.setattr(SSHConnection, '_line', lambda *a: 'BIOPIPE_REMOTE_READY 1')
    monkeypatch.setattr(SSHConnection, 'handshake', lambda *a: info())
    profile = {'host': 'example.org', 'port': 22, 'username': 'researcher', 'auth': 'password',
               'environment': 'managed', 'mode': 'exec'}
    connection = SSHConnection(profile, {}, install=install)
    assert calls == ['install' if install else 'locate']
    assert '/shared/app' in sent[-1].decode()
    connection.close()
