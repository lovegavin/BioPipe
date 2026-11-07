"""Terminal ergonomics must preserve service boundaries and machine-readable output."""
import json
from pathlib import Path

import pytest

from operon import cli


def test_relative_workspace_is_terminal_relative_without_starting_a_service(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    selected = []
    monkeypatch.setattr('operon.client.instances', lambda directory: selected.append(directory) or [])
    cli.main(['service', 'status', '--workspace', '.'])
    assert selected == [tmp_path / '.studio']
    assert json.loads(capsys.readouterr().out) == {'instances': []}
    assert not (tmp_path / '.studio').exists()


@pytest.mark.parametrize('command', [['workflow', 'validate'], ['workflow', 'prepare-environment'],
                                    ['environment', 'check'], ['environment', 'prepare']])
def test_blocked_validation_has_a_failure_exit_code(command, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'execute', lambda args: {'valid':True, 'readiness':{'status':'blocked', 'blocked':[{'message':'missing dependency'}]}})
    with pytest.raises(SystemExit) as error:
        cli.main([*command, 'workflow.yaml'])
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)['readiness']['status'] == 'blocked'


@pytest.mark.parametrize('command', [['run'], ['workflow', 'validate'], ['environment', 'check']])
def test_bad_project_is_rejected_before_starting_a_service(tmp_path, monkeypatch, command):
    path = tmp_path / 'workflow.yaml'
    path.write_text('format: wrong\n', encoding='utf-8')
    monkeypatch.setattr(cli, 'Client', lambda *args, **kw: pytest.fail('Invalid project started a service'))
    with pytest.raises(ValueError):
        cli.execute(cli.parser().parse_args(['--workspace', str(tmp_path), *command, str(path)]))


@pytest.mark.parametrize('action,endpoint,install', [('check','validate',False), ('prepare','prepare-environment',True)])
def test_environment_commands_reuse_shared_route_service(tmp_path, monkeypatch, action, endpoint, install):
    path = tmp_path / 'graph.json'
    path.write_text('{"nodes":[],"edges":[]}', encoding='utf-8')
    scopes, calls = [], []
    class Client:
        def __init__(self, *args, **kwargs): scopes.extend(kwargs['scopes'])
        def request(self, route, payload=None):
            calls.append((route, payload))
            return {'readiness': {'status':'ready'}}
        def close(self): pass
    monkeypatch.setattr(cli, 'Client', Client)
    result = cli.execute(cli.parser().parse_args(['--workspace',str(tmp_path),'environment',action,str(path)]))
    assert result['readiness']['status'] == 'ready'
    assert ('plugins' in scopes) is install
    assert 'run' not in scopes
    assert calls[0][0] == '/v1/workflows/' + endpoint and len(calls) == 1


def test_progress_uses_stderr_and_does_not_pollute_json(monkeypatch, capsys):
    class Client:
        def request(self, path): return {'id':'j1','status':'complete','progress':{'done':1}}
    monkeypatch.setattr('operon.agent_views.time.sleep', lambda _: None)
    result = cli._wait_job(Client(), {'id':'j1','status':'running'}, 1, view='brief', progress=True)
    captured = capsys.readouterr()
    assert result['status'] == 'complete' and captured.out == ''
    assert 'running' in captured.err and 'complete' in captured.err
