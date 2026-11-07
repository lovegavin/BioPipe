"""Guides and small agent responses work through actual public transports."""
import asyncio
from copy import deepcopy
import json
import re
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from operon.guidance import guide, TOPICS
from operon.agent_views import wait_job
from operon.headless import create_headless_app
from operon.operator_docs import OperatorDocs
from src.web.service import Settings
from test_headless_application import auth, graph, environment

ROOT = Path(__file__).resolve().parents[1]


def test_guides_are_offline_cached_bounded_and_cli_readable(tmp_path):
    for topic in TOPICS:
        value = guide(topic)
        assert value['content'] and len(value['content']) < 4000
        cached = guide(topic, if_sha256=value['sha256'])
        assert cached['not_modified'] and 'content' not in cached
    with pytest.raises(ValueError, match='Unknown guide'):
        guide('../client')
    result = subprocess.run([sys.executable, '-m', 'operon', '--workspace', str(tmp_path),
                             'help', 'workflow', '--compact'], cwd=ROOT,
                            capture_output=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == guide('workflow')
    assert len(result.stdout.splitlines()) == 1
    assert not (tmp_path / '.studio').exists()


def test_ranked_brief_search_and_selected_docs_are_metadata_first(tmp_path, monkeypatch):
    from test_operator_docs import extension
    from operon_sdk.declarations import source_declarations, compile_declaration
    path, _ = extension(tmp_path, unsafe=True)
    base = compile_declaration(source_declarations(path, 'answer')[0], tmp_path)
    def item(key, title, description, aliases=None):
        return {**deepcopy(base), 'id': key, 'title': title, 'description': description,
                'title_aliases': aliases or [], 'documentation': {**base['documentation'], 'summary': description},
                'distribution': 'test', 'implementation': {'code_sha': 'a' * 64}}
    state = {'generation': 'rank-test', 'packages': [{'name': 'test'}], 'descriptors': [
        item('reliability', 'Reliability', 'Compute reliability'),
        item('sequence_liability_scan', 'Sequence liability scan', 'Find sequence liabilities'),
        item('structure_interface_core', 'Structure interface core', 'Analyse an interface', ['结构界面分析']),
        item('aaa', 'Something else', 'Find sequence liability in an example')]}
    docs = OperatorDocs(SimpleNamespace(directory=tmp_path, state=lambda: state))
    monkeypatch.setattr('operon.operator_docs.document_bytes', lambda *a: pytest.fail('metadata imported Markdown'))
    full = docs.search('liability')
    brief = docs.search('liability', view='brief')
    assert [i['id'] for i in brief['items']] == ['sequence_liability_scan', 'aaa']
    assert 'implementation' not in brief['items'][0]
    assert len(json.dumps(brief)) < len(json.dumps(full))
    assert docs.search('结构界面分析')['items'][0]['id'] == 'structure_interface_core'
    assert docs.search('structure_interface_core')['items'][0]['id'] == 'structure_interface_core'
    assert docs.search('liability', limit=1)['next_offset'] == 1
    schema = docs.describe(['aaa'], view='schema')['items'][0]
    assert 'parameters_schema' in schema['descriptor'] and 'implementation' not in schema['descriptor']
    page = docs.describe(['aaa'], view='docs', sections=['parameters'])['items'][0]
    assert 'parameters_schema' not in page['descriptor'] and 'parameters' in page['documentation']['content']
    with pytest.raises(ValueError, match='view'):
        docs.search(view='unknown')


def test_wait_keeps_receipt_timeout_and_does_not_resubmit(monkeypatch):
    from operon import agent_views
    current = [0.0]
    monkeypatch.setattr(agent_views.time, 'monotonic', lambda: current[0])
    monkeypatch.setattr(agent_views.time, 'sleep', lambda n: current.__setitem__(0, current[0] + n))
    paths = []
    def read(path):
        paths.append(path)
        return {'id': 'job', 'status': 'running', 'graph': {'large': True}}
    result = wait_job(SimpleNamespace(request=read), {'id': 'job', 'status': 'running', 'request_id': 'same'}, timeout=1)
    assert result['wait_timed_out'] and result['request_id'] == 'same' and 'graph' not in result
    assert paths and all(p == '/v1/jobs/job?view=brief' for p in paths)
    for value in (-1, float('nan'), float('inf')):
        with pytest.raises(ValueError, match='timeout'):
            wait_job(SimpleNamespace(request=read), {'id': 'job', 'status': 'running'}, value)


def test_api_guide_permissions_openapi_and_real_third_party_example(environment):
    from examples.api_client.run_workflow import run_workflow, copy_result
    from operon.client import Client
    root = environment
    app = create_headless_app(Settings(root, root / '.studio', root / 'no-ui', testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as http:
        assert http.get('/api/v1/guides').status_code == 403
        assert http.get('/api/v1/openapi.json').status_code == 403
        http.headers.update(auth(http, app, ['context']))
        assert http.get('/api/v1/guides/workflow').json() == guide('workflow')
        spec = http.get('/api/v1/openapi.json').json()
        assert '/api/v1/jobs' in spec['paths'] and all(p.startswith('/api/v1/') for p in spec['paths'])
        assert spec['security'] == [{'OperonToken': []}]
        assert http.post('/api/v1/jobs', json={'graph': graph(root)}).status_code == 403
        http.headers.update(auth(http, app, ['context', 'run']))
        def request(path, payload=None):
            response = http.get('/api' + path) if payload is None else http.post('/api' + path, json=payload)
            return Client.decode(response)
        downloads = []
        def download(path, target):
            response = http.get('/api' + path)
            assert response.status_code == 200
            target.write_bytes(response.content)
            downloads.append(path)
            return {'path': str(target)}
        client = SimpleNamespace(request=request, download=download)
        # Execute the JSON shown to users, so a tutorial edit cannot silently
        # diverge from the graph exercised by this integration test.
        tutorial = (ROOT / 'docs/api_quickstart.md').read_text(encoding='utf-8')
        body = json.loads(re.search(r'```json\n(.*?)\n```', tutorial, re.S).group(1))
        installed_example = json.loads(re.search(r'```json\n(.*?)\n```', guide('workflow')['content'], re.S).group(1))
        assert body == installed_example
        body['memory'] = graph(root)['memory']  # Bounded test budget; same public route.
        result = run_workflow(client, body, 'api-example-once', timeout=60)
        assert result['job']['status'] == 'complete', result
        assert 'graph' not in result['job'] and result['results']['reports']
        key = result['job']['id']
        job = request('/v1/jobs/' + key)
        assert job['allocation']['memory_enabled']
        assert (root / '.studio/jobs' / key / 'parameters.json').is_file()
        output = root / 'native-report.json'
        copy_result(client, result['results'], result['results']['reports'][0]['href'], output)
        assert json.loads(output.read_text())['global']['mean'] == 2.5
        with pytest.raises(ValueError, match='exact href'):
            copy_result(client, result['results'], '/api/v1/jobs/another/private', output)
        assert len(downloads) == 1
        log = request('/v1/jobs/' + key + '/logs?limit=64&encoding=text')
        assert log['text'] and 'base64' not in log and log['offset'] == 64
        legacy = request('/v1/jobs/' + key + '/logs?limit=64')
        assert 'text' in legacy and 'base64' in legacy


def test_mcp_guides_resources_and_brief_defaults_without_data_imports():
    from operon.mcp_server import create_server
    calls = []
    class FakeClient:
        def request(self, path, payload=None):
            calls.append((path, payload))
            return {'id': 'j', 'status': 'complete'} if '/jobs/' in path else {'items': []}
    server = create_server(FakeClient())
    async def exercise():
        topics = await server.call_tool('operon_guide', {'topic': 'index'})
        assert topics
        await server.call_tool('operon_operator_search', {'query': 'pca'})
        assert 'limit=5' in calls[-1][0] and 'view=brief' in calls[-1][0]
        await server.call_tool('operon_operator_describe', {'ids': ['pca'], 'view': 'docs', 'sections': ['purpose']})
        assert calls[-1][1]['view'] == 'docs'
        await server.call_tool('operon_job', {'job_id': 'j', 'wait_seconds': 1})
        assert calls[-1][0].endswith('?view=brief')
        resources = await server.list_resources()
        assert 'operon://guide' in {str(r.uri) for r in resources}
    asyncio.run(exercise())
