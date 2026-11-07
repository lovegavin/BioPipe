"""Environment installation stays explicit across HTTP, MCP and CLI transports."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from biopipe.client import Client, ClientError
from biopipe.headless import create_headless_app
from src.web.service import Settings
from test_headless_application import auth, environment, graph


ROOT = Path(__file__).resolve().parents[1]


def test_prepare_environment_requires_plugins_not_edit_or_run_and_never_submits(environment, monkeypatch):
    from biopipe.mcp_server import create_server
    app = create_headless_app(Settings(environment, environment / '.studio', environment / 'no-ui', testing=True, code_root=ROOT))
    calls = []
    def validate(value, **options):
        calls.append((value, options))
        return {'readiness': {'status': 'ready'}}
    monkeypatch.setattr(app.state.application, 'validate', validate)
    body = graph(environment)
    with TestClient(app, base_url='http://127.0.0.1') as http:
        class HTTPClient:
            def request(self, path, payload=None):
                response = http.get('/api' + path) if payload is None else http.post('/api' + path, json=payload)
                return Client.decode(response)
        server = create_server(HTTPClient())
        for scopes in (['context'], ['context', 'edit'], ['context', 'edit', 'run']):
            http.headers.update(auth(http, app, scopes))
            denied = http.post('/api/v1/workflows/prepare-environment', json={'graph': body})
            assert denied.status_code == 403 and 'plugins' in denied.text
        async def check_mcp():
            with pytest.raises(Exception, match='plugins'):
                await server.call_tool('biopipe_workflow_prepare_environment', {'graph': body})
            assert not calls
            http.headers.update(auth(http, app, ['context', 'plugins']))
            await server.call_tool('biopipe_workflow_prepare_environment', {'graph': body})
        asyncio.run(check_mcp())
        assert calls == [(body, {'require_files': False, 'repair': True})]
        # Installer capability does not grant either workflow-edit or job-run capability.
        assert http.post('/api/v1/jobs', json={'graph': body}).status_code == 403
        assert http.post('/api/v1/workflows', json={'graph': body}).status_code == 403
        assert http.get('/api/v1/jobs').json() == []


@pytest.mark.parametrize('action,plugins', [('prepare-environment', True), ('validate', False), ('prepare', False)])
def test_cli_only_explicit_preparation_requests_install_scope(tmp_path, monkeypatch, action, plugins):
    from biopipe import cli
    body = {'nodes': [], 'edges': []}
    path = tmp_path / 'route.json'; path.write_text(json.dumps(body), encoding='utf-8')
    calls, connected, closed = [], [], []
    class FakeClient:
        def __init__(self, *args, **options):
            connected.append(options)
        def request(self, endpoint, payload=None):
            calls.append((endpoint, payload))
            return body if endpoint == '/v1/workflows/prepare' else {'readiness': {'status': 'ready'}}
        def close(self):
            closed.append(True)
    monkeypatch.setattr(cli, 'Client', FakeClient)
    args = cli.parser().parse_args(['--workspace', str(tmp_path), 'workflow', action, str(path)])
    cli.execute(args)
    assert ('plugins' in connected[0]['scopes']) is plugins
    assert 'run' not in connected[0]['scopes'] and len(closed) == 1
    assert calls[0] == ('/v1/workflows/' + action, {'graph': body, **({'require_files': False} if action == 'validate' else {})})
    assert all('/jobs' not in endpoint for endpoint, _ in calls)
    if plugins:
        assert len(calls) == 1


@pytest.mark.parametrize('flags,plugins,run', [([], False, False), (['--allow-run'], False, True), (['--allow-plugins'], True, False)])
def test_mcp_server_never_adds_install_scope_without_explicit_flag(tmp_path, monkeypatch, flags, plugins, run):
    from biopipe import cli, mcp_server
    connected = []
    class FakeClient:
        def __init__(self, *args, **options):
            connected.append(options)
        def close(self):
            pass
    monkeypatch.setattr(mcp_server, 'Client', FakeClient)
    monkeypatch.setattr(mcp_server, 'create_server', lambda client: SimpleNamespace(run=lambda **kwargs: None))
    mcp_server.serve(cli.parser().parse_args(['--workspace', str(tmp_path), 'mcp', *flags]))
    assert ('plugins' in connected[0]['scopes']) is plugins
    assert ('run' in connected[0]['scopes']) is run


def test_explicit_preparation_waits_longer_but_never_retries_or_upgrades_permission():
    client = Client.__new__(Client)
    calls = []
    def denied(path, **options):
        calls.append((path, options))
        return httpx.Response(403, json={'detail': "Agent connection requires 'plugins' capability"})
    client.http = SimpleNamespace(post=denied)
    client.restart = lambda: pytest.fail('An explicit preparation must not reconnect or broaden permission')
    with pytest.raises(ClientError, match='plugins'):
        client.request('/v1/workflows/prepare-environment', {'graph': {}})
    assert len(calls) == 1 and calls[0][1]['timeout'] == 1800
    def timeout(path, **options):
        calls.append((path, options))
        raise httpx.ReadTimeout('installer still running')
    client.http = SimpleNamespace(post=timeout)
    with pytest.raises(httpx.ReadTimeout):
        client.request('/v1/workflows/prepare-environment', {'graph': {}})
    assert len(calls) == 2  # One attempt per explicit request.


def test_ssh_dependency_repair_allows_a_quiet_install_but_other_rpc_stays_bounded(monkeypatch):
    from biopipe.remote import client as module
    connection = module.SSHConnection.__new__(module.SSHConnection)
    connection.lock = threading.RLock()
    connection.channel = SimpleNamespace(closed=False, sendall=lambda value: None)
    connection.client = SimpleNamespace(get_transport=lambda: SimpleNamespace(is_active=lambda: True))
    connection.close = lambda: None
    identities, deadlines = [], []
    monkeypatch.setattr(module, 'transmit', lambda request, *args: identities.append(request['id']))
    monkeypatch.setattr(module.time, 'monotonic', lambda: 0)
    class Reply:
        progress = 0
        ack = None
        def __init__(self, *args):
            pass
        def feed(self, line):
            return {'id': identities[-1], 'ok': True, 'value': {'ready': True}}
    monkeypatch.setattr(module, 'Decoder', Reply)
    def quiet_installer(deadline):
        deadlines.append(deadline)
        if deadline < 130:
            raise TimeoutError('No frame before the ordinary RPC deadline')
        return 'complete after 130 seconds'
    connection._line = quiet_installer
    assert connection.call('validate_environment', {'repair': True}) == {'ready': True}
    assert deadlines[-1] == 1800
    with pytest.raises(module.RemoteError, match='SSH'):
        connection.call('validate_environment', {'repair': False})
    assert deadlines[-1] == 100


def test_cli_diff_and_targeted_undo_are_bounded_and_do_not_request_run_or_install(tmp_path, monkeypatch):
    from biopipe import cli
    calls, scopes = [], []
    class FakeClient:
        def __init__(self, *args, **kwargs): scopes.extend(kwargs['scopes'])
        def session(self, selected): return selected
        def request(self, path, payload=None): calls.append((path, payload)); return {'next_cursor': 3}
        def close(self): pass
    monkeypatch.setattr(cli, 'Client', FakeClient)
    prefix = ['--workspace', str(tmp_path), '--session', 'selected']
    cli.execute(cli.parser().parse_args([*prefix, 'graph', 'diff', '--transaction-id', 'tx', '--offset', '2', '--limit', '3']))
    assert calls[-1] == ('/sessions/selected/transactions/tx?offset=2&limit=3', None)
    cli.execute(cli.parser().parse_args([*prefix, 'graph', 'undo', '--document', 'main', '--expected-revision', '7', '--transaction-id', 'tx']))
    assert calls[-1][1] == {'document_id': 'main', 'expected_revision': 7, 'transaction_id': 'tx'}
    cli.execute(cli.parser().parse_args([*prefix, 'events', 'get', '--after', '2', '--limit', '1']))
    assert calls[-1] == ('/sessions/selected/events?after=2&limit=1', None)
    assert 'plugins' not in scopes and 'run' not in scopes
