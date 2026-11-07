"""No-window CLI/MCP execution and the shared application service contract."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from operon.headless import create_headless_app
from operon.application import ACTIVE
from operon.client import Client, instances
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def graph(root):
    (root / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    return {'schema_version': 2, 'name': 'Headless streaming summary', 'base_dir': '.',
            'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32, 'process_limit_mb': 512,
                       'chunk_mb': .01, 'io_buffer_kb': 4, 'keep': ['input']},
            'nodes': [{'id': 'input', 'kind': 'source', 'source': {'path': 'input.csv',
                       'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                      {'id': 'summary', 'kind': 'operator', 'operator': 'describe', 'params': {}}],
            'edges': [{'id': 'e1', 'source': 'input', 'target': 'summary'}]}


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    monkeypatch.setenv('OPERON_ADMISSION_DIR', str(tmp_path / 'admission'))
    scratch = tmp_path / 'tmp'; scratch.mkdir()
    monkeypatch.setenv('TEMP', str(scratch))
    monkeypatch.setenv('TMP', str(scratch))
    return tmp_path


def auth(client, app, scopes):
    response = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret},
                           json={'name': 'headless-test', 'scopes': scopes})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['token']}


def wait_job(get, key):
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        item = get(key)
        if item['status'] not in ACTIVE:
            return item
        time.sleep(.1)
    pytest.fail(f'Headless job did not finish: {item}')


def test_shared_services_permissions_frozen_values_and_artifacts(environment):
    root = environment
    settings = Settings(root, root / '.studio', root / 'nonexistent-ui', testing=True, code_root=ROOT)
    app = create_headless_app(settings)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.get('/api/bootstrap').status_code == 404
        assert client.get('/').status_code == 404
        assert client.get('/openapi.json').status_code == 404
        assert client.get('/health').status_code == 403
        assert client.get('/api/v1/workflows').status_code == 403
        assert client.get('/api/v1/environment').status_code == 403
        read = auth(client, app, ['context'])
        environment = client.get('/api/v1/environment', headers=read).json()
        assert environment['python'] == sys.executable
        assert environment['workspace'] == str(root.resolve())
        assert environment['dependency_policy'] == 'explicit-route-preparation'
        assert app.state.application.jobs.list() == []
        assert client.post('/api/v1/jobs', headers=read, json={'graph': graph(root)}).status_code == 403
        assert client.post('/api/v1/workflows', headers=read, json={'graph': graph(root)}).status_code == 403
        headers = auth(client, app, ['context', 'edit', 'run'])
        client.headers.update(headers)
        assert client.get('/health').status_code == 200
        assert client.get('/api/agent/sessions').json() == []
        body = graph(root)
        invalid_memory = deepcopy(body)
        invalid_memory['memory']['process_limit_mb'] = None
        invalid = client.post('/api/v1/workflows/validate', json={'graph': invalid_memory})
        assert invalid.status_code == 422
        assert 'process_limit_mb' in invalid.json()['message']
        prepared = client.post('/api/v1/workflows/prepare', json={'graph': body})
        assert prepared.status_code == 200, prepared.text
        saved = client.post('/api/v1/workflows', json={'graph': prepared.json()})
        assert saved.status_code == 200, saved.text
        item = saved.json()
        assert (root / '.studio/workflows' / item['parameters_file']).is_file()
        assert (root / '.studio/workflows' / item['execution_file']).is_file()
        stale = client.post('/api/v1/workflows', json={'graph': body, 'workflow_id': item['id'], 'expected_version': 999})
        assert stale.status_code == 409 and stale.json()['code'] == 'revision_conflict'
        request = {'workflow_id': item['id'], 'expected_version': 1, 'request_id': 'summary-1'}
        submitted = client.post('/api/v1/jobs', json=request)
        assert submitted.status_code == 202, submitted.text
        key = submitted.json()['id']
        retried = client.post('/api/v1/jobs', json=request)
        assert retried.json()['id'] == key and retried.json()['reused']
        result = wait_job(lambda k: client.get('/api/v1/jobs/' + k).json(), key)
        assert result['status'] == 'complete', result.get('error')
        assert result['allocation']['memory_enabled']
        assert (root / '.studio/jobs' / key / 'parameters.json').is_file()
        assert result['report']['streamed_steps'] if 'streamed_steps' in result['report'] else result['report']
        logs = client.get(f'/api/v1/jobs/{key}/logs?limit=64').json()
        assert logs['offset'] == 64 and logs['text']
        chunks = []
        cursor = 0
        while True:
            part = client.get(f'/api/v1/jobs/{key}/logs?offset={cursor}&limit=97').json()
            chunks.append(__import__('base64').b64decode(part['base64']))
            cursor = part['offset']
            if part['done']:
                break
        assert '[describe]' in b''.join(chunks).decode('utf-8')
        index = client.get(f'/api/v1/jobs/{key}/artifacts').json()
        report = client.get(index['reports'][0]['href']).json()
        assert report['global']['mean'] == 2.5
        assert index['artifacts']
        artifact = next(a for a in index['artifacts'] if a['available'])
        assert client.get(artifact['href']).status_code == 200
        assert client.get(f'/api/v1/jobs/{key}/artifacts/missing/file').status_code == 404
        parameters = client.get(index['provenance']['parameters']).json()
        assert parameters['job_id'] == key and 'describe' in parameters['plugin_lock']
        assert index['provenance']['operator_generation'] == result['plugins']['generation']
        # Original-file links are enumerated for every figure and format from
        # the run index, without reading pixels or fetching whole reports.
        from types import SimpleNamespace
        from operon_sdk.figures import register_figure, figure_collection
        output = root / '.studio/jobs' / key / 'output'
        figures = []
        originals = {}
        for name in ('first', 'second'):
            files = {}
            for fmt, content in [('svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'), ('pdf', b'%PDF-1.4\nfixture')]:
                path = output / (name + '.' + fmt); path.write_bytes(content)
                originals[(name, fmt)] = content
                files[fmt] = path
            figures.append(register_figure(SimpleNamespace(out_dir=output), name, files, width_mm=90, height_mm=75))
        declared = figure_collection(*figures)['figures']
        summary_path = output / 'run_summary.json'
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        summary['steps'][0]['figures'] = declared
        summary_path.write_text(json.dumps(summary), encoding='utf-8')
        report_path = output / summary['steps'][0]['export_path']
        report['figures'] = declared
        report_path.write_text(json.dumps(report), encoding='utf-8')
        indexed = client.get(f'/api/v1/jobs/{key}/artifacts').json()
        assert len(indexed['figures']) == 4
        for figure in indexed['figures']:
            opened = client.get(figure['href'])
            assert opened.status_code == 200 and opened.content == originals[(figure['id'], figure['format'])]
        updated = deepcopy(body); updated['name'] = 'Next route revision'
        assert client.post('/api/v1/workflows', json={'graph': updated, 'workflow_id': item['id'], 'expected_version': 1}).status_code == 200
        assert client.post('/api/v1/jobs', json=request).json()['id'] == key
        conflict = deepcopy(body); conflict['name'] = 'Changed payload'
        bad = client.post('/api/v1/jobs', json={'graph': conflict, 'request_id': 'summary-1'})
        assert bad.status_code == 409 and bad.json()['code'] == 'idempotency_conflict'


def test_submission_receipt_recovers_after_lost_response(environment, monkeypatch):
    root = environment
    app = create_headless_app(Settings(root, root / '.studio', root / 'none', testing=True, code_root=ROOT))
    application = app.state.application
    with TestClient(app, base_url='http://127.0.0.1'):
        payload = {'graph': graph(root), 'request_id': 'lost-response'}
        original = application.service.launch
        def lost_response(value):
            original(value)
            raise OSError('synthetic response publication interruption')
        monkeypatch.setattr(application.service, 'launch', lost_response)
        started = application.jobs.submit(payload)
        assert started['reused']
        assert application.jobs.submit(payload)['id'] == started['id']
        assert len(list(application.service.jobs_dir.glob('*/job.json'))) == 1
        result = wait_job(application.jobs.details, started['id'])
        assert result['status'] == 'complete', result.get('error')


def test_headless_submission_preserves_released_pin_migration_evidence(environment):
    root = environment
    app = create_headless_app(Settings(root, root / '.studio', root / 'no-ui', testing=True, code_root=ROOT))
    released = json.loads((ROOT / 'operon/bundled_history.json').read_text(encoding='utf-8'))
    old = next(package['implementation'] for package in released['packages']
               if 'describe' in package['operators'] and any(item['tag'] == 'v0.5.1' for item in package['releases']))
    body = graph(root); body['plugin_lock'] = {'describe': old}
    with TestClient(app, base_url='http://127.0.0.1') as client:
        client.headers.update(auth(client, app, ['context', 'run']))
        started = client.post('/api/v1/jobs', json={'graph': body, 'request_id': 'released-pins'})
        assert started.status_code == 202, started.text
        result = wait_job(lambda key: client.get('/api/v1/jobs/' + key).json(), started.json()['id'])
        assert result['status'] == 'complete', result.get('error')
        receipt = next(row for row in result['plugins']['bundled_updates'] if row['operator'] == 'describe')
        assert receipt['before'] == old and 'released' in receipt['reason']
        assert 'Updated bundled source pins' in client.get('/api/v1/jobs/' + result['id'] + '/logs').json()['text']


def test_unknown_submission_result_is_never_relaunched(environment, monkeypatch):
    from operon.documents import CommandError
    root = environment
    app = create_headless_app(Settings(root, root / '.studio', root / 'no-ui', testing=True, code_root=ROOT))
    calls = []
    def lost_result(prepared, **kwargs):
        calls.append(prepared)
        raise OSError('Connection vanished after possible remote acceptance')
    with TestClient(app, base_url='http://127.0.0.1'):
        tasks = app.state.application.jobs
        monkeypatch.setattr(tasks, '_launch', lost_result)
        request = {'graph': graph(root), 'request_id': 'uncertain-transport'}
        with pytest.raises(OSError, match='possible remote acceptance'):
            tasks.submit(request)
        with pytest.raises(CommandError) as failed:
            tasks.submit(request)
        assert failed.value.code == 'submission_uncertain' and len(calls) == 1


def test_manifest_only_startup_and_lifecycle_refuses_active_queue(environment, monkeypatch):
    from operon import packages
    def no_source_scan(*args, **kwargs):
        pytest.fail('Headless startup or polling scanned implementation sources')
    monkeypatch.setattr(packages, '_provider_paths', no_source_scan)
    root = environment
    app = create_headless_app(Settings(root, root / '.studio', root / 'none', testing=True, code_root=ROOT))
    assert app.state.service.plugins.manifest_only
    with TestClient(app, base_url='http://127.0.0.1') as client:
        client.headers.update(auth(client, app, ['context', 'edit', 'run']))
        assert client.get('/api/v1/operators?query=pca').status_code == 200
        assert client.post('/api/v1/operators/describe', json={'ids': ['describe'], 'sections': ['parameters']}).status_code == 200
        assert client.post('/api/v1/workflows/prepare', json={}).json()['code'] == 'invalid_request'
        # A real durable queued task, blocked only at the host reservation gate.
        monkeypatch.setattr(app.state.service.admission, 'reserve', lambda *args, **kwargs: False)
        job = client.post('/api/v1/jobs', json={'graph': graph(root), 'request_id': 'queued'}).json()
        assert job['status'] == 'queued'
        stopping = []
        app.state.request_shutdown = lambda: stopping.append(True)
        denied = client.post('/api/v1/service/stop', json={})
        assert denied.status_code == 409 and denied.json()['code'] == 'jobs_active'
        assert not stopping
        canceled = client.post(f'/api/v1/jobs/{job["id"]}/cancel', json={}).json()
        assert canceled['status'] == 'cancelled'
        assert client.post('/api/v1/service/stop', json={}).status_code == 200 and stopping
        rejected = client.post('/api/v1/jobs', json={'graph': graph(root), 'request_id': 'after-stop'})
        assert rejected.status_code == 503 and rejected.json()['code'] == 'service_stopping'


def test_remote_log_window_preserves_bytes_against_old_server():
    from types import SimpleNamespace
    import base64
    from operon.application import TaskService
    payload = ('alpha测试beta\n' * 100).encode('utf-8')
    calls = []
    class Remote:
        def owns(self, key): return True
        def job(self, key): return {'status': 'complete'}
        def reference(self, key): return {'profile_id': 'fixture', 'job_id': 'server-job'}
        def call(self, profile, method, params):
            calls.append(params)
            # Older agent ignores limit and returns up to 64 KiB.
            data = payload[params['offset']:params['offset'] + 65536]
            return {'base64': base64.b64encode(data).decode(), 'offset': params['offset'] + len(data), 'done': True}
    tasks = TaskService(SimpleNamespace(service=SimpleNamespace(remotes=Remote()), executions=SimpleNamespace(owns=lambda _: False)))
    cursor, parts = 0, []
    while True:
        part = tasks.logs('ssh-fixture-job', offset=cursor, limit=17)
        block = base64.b64decode(part['base64'])
        assert len(block) <= 17
        parts.append(block); cursor = part['offset']
        if part['done']:
            break
    assert b''.join(parts) == payload and all(call['limit'] == 17 for call in calls)


def test_context_only_remote_prepare_does_not_connect_install_or_execute(environment, monkeypatch):
    root = environment
    app = create_headless_app(Settings(root, root / '.studio', root / 'no-ui', testing=True, code_root=ROOT))
    service = app.state.service
    def forbidden(*args, **kwargs):
        raise AssertionError('Context-only preparation attempted an execution side effect')
    monkeypatch.setattr(service.remotes, 'connect', forbidden)
    monkeypatch.setattr(service.remotes, 'call', forbidden)
    monkeypatch.setattr(service.plugins, 'python_for', forbidden)
    monkeypatch.setattr(service.plugins, 'install_many', forbidden)
    monkeypatch.setattr(service, 'launch', forbidden)
    monkeypatch.setattr(service.remotes, 'status', lambda: [
        {'profile': {'id': 'offline', 'name': 'Cached server'}, 'connected': False,
         'info': {'catalog': service.catalog, 'system': 'linux', 'resources': {}, 'tools': {}}}])
    body = graph(root)
    body['runtime'] = {'execution': {'mode': 'manual', 'kind': 'ssh', 'profile_id': 'offline'}}
    with TestClient(app, base_url='http://127.0.0.1') as client:
        client.headers.update(auth(client, app, ['context']))
        prepared = client.post('/api/v1/workflows/prepare', json={'graph': body})
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()['plugin_lock']['describe']
        # Offline validation reports unavailable placement; it must never turn
        # a metadata request into an SSH connection or automatic deployment.
        checked = client.post('/api/v1/workflows/validate', json={'graph': body})
        assert checked.status_code == 422
        assert client.post('/api/v1/remotes/offline/connect', json={}).status_code == 403
        assert client.post('/api/v1/jobs', json={'graph': body}).status_code == 403


def test_real_cli_autostart_and_mcp_no_window(environment):
    root = environment
    source = root / 'route.json'; source.write_text(json.dumps(graph(root)), encoding='utf-8')
    directory = root / '.studio'
    args = [sys.executable, '-m', 'operon', '--workspace', str(root)]
    def cli(*tail):
        result = subprocess.run(args + list(tail), cwd=ROOT, capture_output=True, encoding='utf-8', timeout=100)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    control = None
    try:
        # Two independent command processes race to create the same profile
        # service. The startup and lifetime locks must yield one owner.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            starters = list(pool.map(lambda _: cli('service', 'start'), range(2)))
        assert len({v['instance_id'] for v in starters}) == 1
        assert 'operators' in cli('operators', 'list')
        search = cli('operators', 'search', 'describe', '--limit', '2')
        assert len(search['items']) <= 2 and search['total'] >= 1
        described = cli('operators', 'describe', 'describe', '--section', 'parameters')
        assert described['id'] == 'describe' and 'parameters' in described['documentation']['content']
        prepared_path = root / 'prepared.json'
        prepared = cli('workflow', 'prepare', str(source), '--require-files', '--output', str(prepared_path))
        assert json.loads(prepared_path.read_text(encoding='utf-8')) == prepared
        assert prepared['plugin_lock'] and prepared['memory']['enabled']
        started = cli('run', str(source), '--request-id', 'cli-actual-worker')
        assert started['id']
        assert instances(directory) and all(i.get('headless') for i in instances(directory))
        control = Client(directory, scopes=['context', 'edit', 'run'])
        assert control.sessions() == []
        result = wait_job(lambda key: control.request('/v1/jobs/' + key), started['id'])
        assert result['status'] == 'complete', result.get('error')
        waited = cli('jobs', 'wait', started['id'], '--timeout', '5', '--brief')
        assert waited['status'] == 'complete' and 'graph' not in waited
        assert 'graph' in cli('jobs', 'get', started['id'], '--view', 'full')
        assert cli('run', str(source), '--request-id', 'cli-actual-worker')['id'] == started['id']
        assert cli('jobs', 'logs', started['id'])['text']
        report = cli('artifacts', 'list', started['id'])
        target = root / 'summary.json'
        cli('artifacts', 'report', started['id'], '0', '--output', str(target))
        assert json.loads(target.read_text(encoding='utf-8'))['global']['mean'] == 2.5
        assert report['reports']
        # The tutorial is also usable as a real external process, not only as
        # an imported function in a TestClient fixture. Reuse the retained job.
        copied = root / 'external-summary.json'
        external = subprocess.run([sys.executable, str(ROOT / 'examples/api_client/run_workflow.py'),
                                   '--workspace', str(root), '--job', started['id'],
                                   '--href', report['reports'][0]['href'], '--output', str(copied)],
                                  cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT)},
                                  capture_output=True, encoding='utf-8', timeout=30)
        assert external.returncode == 0, external.stderr
        assert json.loads(external.stdout)['job']['id'] == started['id']
        assert json.loads(copied.read_text(encoding='utf-8'))['global']['mean'] == 2.5

        async def mcp_roundtrip(allow_run):
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            config = StdioServerParameters(command=sys.executable, args=args[1:] + ['mcp'] + (['--allow-run'] if allow_run else []),
                                           cwd=str(ROOT), env=dict(os.environ))
            async with stdio_client(config) as (reader, writer):
                async with ClientSession(reader, writer) as mcp:
                    await mcp.initialize()
                    listed = await mcp.call_tool('operon_sessions', {})
                    assert not listed.isError
                    request = {'graph': graph(root), 'request_id': 'mcp-no-window'}
                    value = await mcp.call_tool('operon_submit', request)
                    if not allow_run:
                        assert value.isError and 'capability' in value.content[0].text
                        return None
                    assert not value.isError, value
                    return json.loads(value.content[0].text)['id']
        asyncio.run(mcp_roundtrip(False))
        key = asyncio.run(mcp_roundtrip(True))
        result = wait_job(lambda k: control.request('/v1/jobs/' + k), key)
        assert result['status'] == 'complete', result.get('error')
        assert not control.sessions()
        # A normal service restart retains jobs, receipts and frozen workflow
        # parameters; the same submission never re-runs the scientific worker.
        control.request('/v1/service/stop', {})
        control.close(); control = None
        deadline = time.monotonic() + 15
        while instances(directory) and time.monotonic() < deadline:
            time.sleep(.1)
        assert not instances(directory)
        restarted = cli('run', str(source), '--request-id', 'cli-actual-worker')
        assert restarted['id'] == started['id'] and restarted['reused']
        assert len(list((directory / 'jobs').glob('*/job.json'))) == 2
        control = Client(directory, scopes=['context', 'edit', 'run'])
    finally:
        if control is None and instances(directory):
            control = Client(directory, scopes=['context', 'run'])
        if control:
            for job in control.request('/v1/jobs'):
                if job['status'] in ACTIVE:
                    control.request('/v1/jobs/' + job['id'] + '/cancel', {})
            deadline = time.monotonic() + 15
            while any(j['status'] in ACTIVE for j in control.request('/v1/jobs')) and time.monotonic() < deadline:
                time.sleep(.1)
            control.request('/v1/service/stop', {})
            control.close()
            deadline = time.monotonic() + 15
            while instances(directory) and time.monotonic() < deadline:
                time.sleep(.1)
            assert not instances(directory)
