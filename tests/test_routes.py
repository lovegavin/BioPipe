"""Saved interfaces, explicit registration, nested execution and portable workspaces."""
from copy import deepcopy
from pathlib import Path
import time

from fastapi.testclient import TestClient
import numpy as np
import pytest

from src.task import STEPS
from src.task.operator_catalog import build_catalog
from src.web.api import create_app
from src.web.contracts import analyze_graph
from src.web.graph import compile_graph, GraphError
from src.web.models import Graph, RouteDefinition, GraphNode, Position, SaveWorkflow
from src.web.routes import RouteLibrary, expand_routes, prepare_interface
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def route_studio(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist', testing=True, code_root=ROOT, desktop=True))
    with TestClient(app) as client:
        data = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = data['token']
        yield client, data, app


def register_demo(client, data):
    saved = client.post('/api/workflows/save', json={'graph': data['demo']})
    assert saved.status_code == 200, saved.text
    item = saved.json()
    assert client.get('/api/routes').json() == []  # Saving is not registration.
    registered = client.post('/api/routes/register', json={'workflow_ids': [item['id']]})
    assert registered.status_code == 200, registered.text
    return item, registered.json()[0]


def canvas(data, route, instances=1):
    graph = deepcopy(data['demo'])
    graph['name'] = 'Composite test'
    graph['nodes'] = [graph['nodes'][0]]
    graph['edges'] = []
    for i in range(instances):
        graph['nodes'].append({'id': f'route_{i}', 'kind': 'route', 'title': 'Reusable', 'position': {'x': 300, 'y': i*200}, 'params': {}, 'route': deepcopy(route)})
        graph['edges'].append({'id': f'input_{i}', 'source': 'expression', 'target': f'route_{i}', 'sourceHandle': 'out', 'targetHandle': 'in-0'})
        graph['nodes'].append({'id': f'report_{i}', 'kind': 'operator', 'operator': 'describe', 'position': {'x':600,'y':i*200}, 'params': {}})
        graph['edges'].append({'id': f'output_{i}', 'source': f'route_{i}', 'target': f'report_{i}', 'sourceHandle': 'out', 'targetHandle':'in-0'})
    return graph


def test_explicit_registration_versions_and_workspace_restore(route_studio):
    client, data, app = route_studio
    saved, route = register_demo(client, data)
    assert len(saved['graph']['interface']['inputs']) == 1
    assert [p['node_id'] for p in saved['graph']['interface']['outputs']] == ['pca']
    edited = deepcopy(saved['graph']); edited['name'] = 'Updated name'
    newer = client.post('/api/workflows/save', json={'graph':edited, 'id':saved['id'], 'expected_version':1})
    assert newer.status_code == 200 and newer.json()['version'] == 2
    assert client.get('/api/routes').json()[0]['version'] == 1
    assert client.post('/api/workflows/save', json={'graph':edited, 'id':saved['id'], 'expected_version':1}).status_code == 422
    workspace = {'schema_version':1, 'active_id':'b', 'documents':[
        {'id':'a','graph':saved['graph'], 'viewport':{'x':12,'y':-35,'zoom':.8}},
        {'id':'b','graph':canvas(data, route), 'workflow_id':saved['id'], 'workflow_version':1}],
        'closed_documents':[{'id':'closed','graph':edited}]}
    assert client.post('/api/workspace',json=workspace).status_code == 200
    loaded = client.get('/api/workspace').json()
    assert loaded['panel_widths'] == {'library': None, 'inspector': None}
    workspace['panel_widths'] = {'library': 304, 'inspector': 368}
    assert client.post('/api/workspace', json=workspace).status_code == 200
    assert loaded['documents'][0]['viewport']['zoom'] == .8
    assert loaded['documents'][1]['graph']['nodes'][1]['route']['version'] == 1
    assert loaded['closed_documents'][0]['graph']['name'] == 'Updated name'
    restarted = RouteLibrary(app.state.service.routes.directory, app.state.service.catalog, app.state.service.root)
    assert restarted.routes()[0]['version'] == 1 and restarted.load_workspace()['active_id'] == 'b'
    assert restarted.load_workspace()['panel_widths'] == {'library': 304, 'inspector': 368}
    workspace['panel_widths']['library'] = 900
    assert client.post('/api/workspace', json=workspace).status_code == 422
    assert client.get('/api/workspace').json()['panel_widths']['library'] == 304


def test_two_route_instances_expand_run_and_ignore_original_files(route_studio):
    client, data, app = route_studio
    saved, route = register_demo(client, data)
    route['graph']['nodes'][0]['source']['path'] = '../../original/computer/file.csv'
    graph = canvas(data, route, instances=2)
    graph['memory'] = {'enabled':True, 'budget_mb':32, 'auto_spill':True, 'keep':['route_0__out_1']}
    validation = client.post('/api/validate', json=graph)
    assert validation.status_code == 200, validation.text
    manifest = validation.json()['manifest']
    assert list(manifest['sources']) == ['expression']
    outputs = [s['params']['output'] for s in manifest['steps'] if 'output' in s['params']]
    assert len(set(outputs)) == 4 and len(manifest['steps']) == 8
    running = client.post('/api/jobs', json=graph)
    assert running.status_code == 202, running.text
    job = running.json()
    deadline = time.monotonic() + 40
    while job['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1); job=client.get(f"/api/jobs/{job['id']}").json()
    assert job['status'] == 'complete', job.get('error')
    assert job['graph']['nodes'][1]['route']['version'] == 1
    assert len(job['node_owners']) == 9
    assert job['report']['budget_bytes'] == 32*1024**2
    assert len(job['summary']['steps']) == 8
    assert (app.state.service.jobs_dir/job['id']/'job.json').exists()


def test_nested_multi_output_boundary_and_rejection(route_studio):
    client, data, app = route_studio
    _, route = register_demo(client, data)
    # Expose the clean matrix as well as the PCA result.
    route['graph']['interface']['outputs'].append({'node_id':'quality','handle':'out','label':'Clean','contract':{}})
    inner = canvas(data, route)
    inner['edges'][-1]['sourceHandle']='out-1'
    inner['interface']={'version':1,'inputs':[{'node_id':'expression','label':'Matrix','contract':{}}], 'outputs':[{'node_id':'route_0','handle':'out-0','label':'PCs','contract':{}}, {'node_id':'route_0','handle':'out-1','label':'Clean','contract':{}}]}
    outer_route = {'id':'route_123456789abc','version':1,'name':'Nested','graph':inner}
    graph=canvas(data, outer_route)
    graph['edges'][-1]['sourceHandle']='out-1'
    valid=client.post('/api/validate',json=graph)
    assert valid.status_code == 200, valid.text
    checks=client.post('/api/contracts',json=graph).json()
    assert checks['nodes']['route_0']['outputs'][0]['dims'] == ['sample','component']
    assert checks['nodes']['route_0']['outputs'][1]['dims'] == ['sample','feature']
    graph['edges'][-1]['sourceHandle']='out-9'
    assert client.post('/api/validate',json=graph).status_code == 422
    graph['edges'][-1]['sourceHandle']='out-1'
    graph['nodes'][1]['route']['id']=route['id']
    invalid=client.post('/api/validate',json=graph)
    assert invalid.status_code == 422 and '递归' in invalid.json()['message']


def test_registration_is_atomic_and_requires_complete_boundary(route_studio):
    client, data, _ = route_studio
    good=client.post('/api/workflows/save',json={'graph':data['demo']}).json()
    bad=deepcopy(data['demo']); bad['edges'].pop()
    incomplete=client.post('/api/workflows/save',json={'graph':bad})
    assert incomplete.status_code == 200
    response=client.post('/api/routes/register',json={'workflow_ids':[good['id'],incomplete.json()['id']]})
    assert response.status_code == 422 and client.get('/api/routes').json() == []


def test_registration_preserves_genotype_reader_contract_without_original_files(route_studio):
    client, data, _ = route_studio
    graph = deepcopy(data['demo'])
    graph['nodes'] = graph['nodes'][:2]
    graph['nodes'][0]['source'].update(path='moved/genotypes.vcf.gz', dims=['variant','sample'], labels={})
    graph['nodes'][1].update(operator='maf', params={'dim':'variant','threshold':.01,'output':'clean'})
    graph['edges'] = graph['edges'][:1]
    graph['memory'] = {'enabled':True}
    saved = client.post('/api/workflows/save',json={'graph':graph})
    assert saved.status_code == 200, saved.text
    response = client.post('/api/routes/register',json={'workflow_ids':[saved.json()['id']]})
    assert response.status_code == 200, response.text
    contract = response.json()[0]['graph']['interface']['inputs'][0]['contract']
    assert contract['info']['representation']['const'] == 'hard_call'
    assert contract['info']['ploidy']['min'] == 1
