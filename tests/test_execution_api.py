"""Execution routing boundaries, parent SSE and arbitrary parameter files."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


class FakeExecutions:
    def __init__(self, service):
        self.service = service
        self.jobs = {}
        self.calls = []
        self.closed = False
        self.timeline = []

    def applies(self, graph):
        return 'mode' in graph.runtime.get('execution', {})

    def catalog(self, graph):
        return self.service.graph_catalog(graph)

    def prepare(self, graph):
        self.calls.append('prepare')
        return self.service.prepare_graph(graph)

    def validate(self, graph, require_files=True):
        self.calls.append('validate')
        return {'valid': True, 'order': [], 'execution_plan': self.plan(graph)}

    def plan(self, graph):
        return {'mode': graph.runtime['execution']['mode'], 'units': [], 'transfers': [], 'warnings': []}

    def resources(self):
        return {'targets': [{'target': {'kind': 'local'}, 'name': 'Local', **self.service.resources()}]}

    def launch(self, graph):
        job = {'id': 'execution-test', 'name': graph.name, 'status': 'queued', 'created_at': '2026-01-01',
               'finished_at': None, 'error': None, 'logs_complete': False,
               'progress': {'phase': 'queued', 'completed': 0, 'total': 1, 'percent': 0},
               'children': [{'id': 'stage-child'}], 'graph': graph.model_dump(mode='json')}
        self.jobs[job['id']] = job
        return job

    def owns(self, key):
        return key in self.jobs

    def details(self, key):
        job = dict(self.jobs[key])
        if self.timeline:
            job.update(self.timeline.pop(0))
        return job

    def history(self):
        return list(self.jobs.values())

    def cancel(self, key):
        self.jobs[key].update(status='cancelled', logs_complete=True)
        return self.jobs[key]

    def events_path(self, key):
        return self.service.root / 'parent.events.jsonl'

    def console_path(self, key):
        return self.service.root / 'parent.console.log'

    def shutdown(self):
        self.closed = True


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Route wiring is independent of the separate execution planner tests.
    monkeypatch.setitem(sys.modules, 'src.web.execution', SimpleNamespace(ExecutionService=FakeExecutions))
    app = create_app(Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=ROOT))
    with TestClient(app) as browser:
        data = browser.get('/api/bootstrap').json()
        browser.headers['X-Studio-Token'] = data['token']
        browser.graph = deepcopy(data['demo'])
        browser.graph['runtime'] = {'execution': {'mode': 'auto', 'kind': 'local'}}
        yield browser
    assert app.state.executions.closed


def test_plan_resources_prepare_validate_save_and_job_routing(client, monkeypatch):
    assert client.post('/api/execution/plan', json=client.graph).json()['mode'] == 'auto'
    resource = client.get('/api/execution/resources').json()['targets'][0]
    assert resource['capacity_bytes'] >= resource['reserved_bytes']
    assert client.post('/api/workflows/prepare', json=client.graph).status_code == 200
    assert client.post('/api/workflows/save', json={'graph': client.graph}).status_code == 200
    assert client.post('/api/validate', json=client.graph).json()['valid'] is True
    assert client.post('/api/contracts', json=client.graph).status_code == 200
    assert client.post('/api/workflows/export', json=client.graph).status_code == 200
    assert '路线包' in client.post('/api/export', json=client.graph).json()['message']
    job = client.post('/api/jobs', json=client.graph).json()
    assert job['status'] == 'queued'
    assert client.get('/api/jobs/' + job['id']).json()['status'] == 'queued'
    monkeypatch.setattr(client.app.state.service, 'history', lambda: [
        {'id': 'stage-child', 'created_at': '2026-01-03'},
        {'id': 'other-stage', 'created_at': '2026-01-04', 'execution_parent_id': job['id']},
        {'id': 'standalone', 'created_at': '2026-01-02'}])
    assert {entry['id'] for entry in client.get('/api/jobs').json()} == {'standalone', job['id']}
    assert client.post('/api/jobs/' + job['id'] + '/cancel', json={}).json()['status'] == 'cancelled'


def test_history_excludes_reconnected_remote_children_in_old_and_new_summaries(client, monkeypatch):
    parent = client.post('/api/jobs', json=client.graph).json()
    execution = client.app.state.executions
    execution.jobs[parent['id']]['children'] = [
        {'id': 'worker-1', 'target': {'kind': 'ssh', 'profile_id': 'server-a'}},
        {'id': 'local-stage', 'target': {'kind': 'local'}}]
    # Simulate a reconnect returning both old summaries without lineage and
    # newer server summaries. Server-local IDs belong to separate namespaces.
    summaries = [
        {'id': 'ssh-server-a-worker-1', 'created_at': '2026-01-03'},
        {'id': 'ssh-server-a-worker-2', 'created_at': '2026-01-03', 'execution_parent_id': parent['id']},
        {'id': 'local-stage', 'created_at': '2026-01-03'},
        {'id': 'ssh-server-b-worker-1', 'created_at': '2026-01-02'},
        {'id': 'worker-1', 'created_at': '2026-01-02'},
        {'id': 'standalone', 'created_at': '2026-01-02'}]
    monkeypatch.setattr(client.app.state.service, 'history', lambda: deepcopy(summaries))
    expected = {parent['id'], 'ssh-server-b-worker-1', 'worker-1', 'standalone'}
    assert {entry['id'] for entry in client.get('/api/jobs').json()} == expected
    assert {entry['id'] for entry in client.get('/api/bootstrap').json()['history']} == expected


def test_parent_sse_waits_for_active_states_and_preserves_final_logs(client):
    job = client.post('/api/jobs', json=client.graph).json()
    execution = client.app.state.executions
    execution.events_path(job['id']).write_text(json.dumps({'event': 'final-note'}) + '\n', encoding='utf-8')
    execution.console_path(job['id']).write_text('final console evidence', encoding='utf-8')
    execution.timeline = [  # First details is the existence check.
        {'status': 'queued', 'logs_complete': True},
        {'status': 'waiting_connection', 'logs_complete': True},
        {'status': 'uploading', 'logs_complete': True},
        {'status': 'complete', 'logs_complete': True}]
    result = client.get('/api/jobs/' + job['id'] + '/events')
    payloads = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith('data: ')]
    assert [payload['job']['status'] for payload in payloads] == ['waiting_connection', 'uploading', 'complete']
    assert [payload['done'] for payload in payloads] == [False, False, True]
    assert any('final console evidence' in payload.get('console', '') for payload in payloads)
    assert client.get('/api/jobs/' + job['id'] + '/console').text == 'final console evidence'


def test_reference_upload_keeps_raw_bytes_without_reader_inference(client):
    content = b'chr1\t12345\nchr2\t23456\n'
    result = client.post('/api/assets/reference', params={'filename': 'reference.chrom.sizes', 'base_dir': 'nested'},
                         content=content)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['bytes'] == len(content) and body['location'] == {'kind': 'local'}
    saved = client.app.state.service.root / 'nested' / body['path']
    assert saved.read_bytes() == content
    assert client.post('/api/assets/reference', params={'filename': '../escape'}, content=b'x').status_code == 422
    assert client.post('/api/assets/reference', params={'filename': 'valid', 'base_dir': '../../..'}, content=b'x').status_code == 422


def test_reference_upload_limit_and_empty_payload_leave_no_partial_files(client):
    service = client.app.state.service
    before = set(service.assets_dir.iterdir())
    service.settings.max_upload = 4
    assert client.post('/api/assets/reference?filename=large.ref', content=b'12345').status_code == 413
    assert client.post('/api/assets/reference?filename=empty.ref', content=b'').status_code == 422
    assert set(service.assets_dir.iterdir()) == before
