"""Coordinator integration with real scientific workers and two workspaces.

SSH authentication/framing is covered separately by test_remote_transfer. This
module substitutes only the connection transport: both destination services,
file movement, admission, manifests and scientific subprocesses remain real.
"""
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from biopipe.remote.client import RemoteError
from biopipe.remote.server import RemoteService
from src.web.execution import ExecutionService
from src.web.execution_plan import ACTIVE
from src.web.models import Graph, SaveWorkflow
from src.web.operator_catalog import catalog_from_descriptors
from src.web.parameters import export_bundle, import_bundle
from src.web.remote_service import RemoteManager
from src.web.routes import prepare_interface
from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]
LOCAL = {'kind': 'local'}


@pytest.fixture
def studio(tmp_path, monkeypatch):
    temporary = ROOT/'.tmp'/'ectmp'
    temporary.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('TMP', str(temporary))
    monkeypatch.setenv('TEMP', str(temporary))
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')
    # Each synthetic host uses its own admission ledger, with no writes to the
    # actual desktop profile. The scientific processes are not mocked.
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path/'remote-admission'))
    remote = RemoteService(tmp_path/'r', input_roots=[tmp_path/'r'])
    local = JobService(Settings(tmp_path/'l', tmp_path/'l'/'s', ROOT/'frontend/dist',
                               testing=True, code_root=ROOT, admission_dir=tmp_path/'local-admission'),
                       catalog_from_descriptors())
    for service in (local, remote.service):
        service.admission.baseline_bytes = 512 * 1024**2
    control = SimpleNamespace(calls=[], disconnect_after_run=False, upload_entered=None, upload_gate=None)
    class Connection:
        def __init__(self, record, credentials):
            self.connected = True
            self.info = remote.dispatch('bootstrap', {})
        def call(self, method, params=None):
            if not self.connected:
                raise RemoteError('Synthetic SSH disconnected', code='remote_disconnected')
            params = params or {}
            if method == 'transfer_chunk' and control.upload_gate is not None:
                control.upload_entered.set()
                if not control.upload_gate.wait(15):
                    raise TimeoutError('Test upload gate was not released')
            result = remote.dispatch(method, params)
            control.calls.append((method, deepcopy(params), deepcopy(result)))
            if method == 'run' and control.disconnect_after_run:
                control.disconnect_after_run = False
                self.connected = False
            return result
        def close(self): self.connected = False
    manager = local.remotes = RemoteManager(local, connection_factory=Connection)
    profile = manager.save({'name': 'Synthetic server', 'host': '127.0.0.1', 'username': 'test',
                            'app_dir': '/synthetic/biopipe', 'workspace': '/synthetic/workspace'})
    manager.connect(profile['id'], {'password': 'synthetic-only'})
    executions = local.executions = ExecutionService(local)
    local.routes.catalog_for = executions.catalog
    source = local.root/'input.csv'
    source.write_text('a,b,c,d\n1,2,4,8\n2,5,7,3\n3,8,1,6\n7,2,9,4\n4,6,3,5\n8,1,6,2\n', encoding='utf-8')
    state = SimpleNamespace(local=local, remote=remote, manager=manager, executions=executions,
                            profile=profile['id'], control=control, source=source,
                            ssh={'kind': 'ssh', 'profile_id': profile['id']})
    try:
        yield state
    finally:
        if control.upload_gate is not None: control.upload_gate.set()
        executions.shutdown()
        manager.close()
        local.shutdown()
        remote.service.shutdown()


def workflow(studio, *, environment=None):
    return Graph.model_validate({'name': 'Scientific execution integration', 'memory': {
        'enabled': True, 'auto_spill': True, 'budget_mb': 32, 'process_limit_mb': 512,
        'chunk_mb': .01, 'io_buffer_kb': 4},
        'runtime': {'execution': {'mode': 'manual', 'max_parallel_tasks': 2, **(environment or LOCAL)}},
        'nodes': [
            {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0}, 'input_count': 0,
             'source': {'path': str(studio.source), 'location': LOCAL, 'dims': ['sample', 'feature'],
                        'labels': {'sample': 'auto', 'feature': 'builtin'}}},
            {'id': 'normalize', 'kind': 'operator', 'operator': 'normalize', 'position': {'x': 1, 'y': 0},
             'params': {'dim': 'sample', 'method': 'total', 'output': 'normalized'}},
            {'id': 'pca', 'kind': 'operator', 'operator': 'pca', 'position': {'x': 2, 'y': 0},
             'params': {'dim': 'feature', 'n_components': 2, 'output': 'pcs'}},
            {'id': 'describe', 'kind': 'operator', 'operator': 'describe', 'position': {'x': 3, 'y': 0}}],
        'edges': [{'id': f'e{i}', 'source': left, 'target': right} for i, (left, right) in enumerate(
            [('input', 'normalize'), ('normalize', 'pca'), ('pca', 'describe')])]})


def wait_for(studio, key, predicate=None, timeout=60):
    predicate = predicate or (lambda value: value['status'] not in ACTIVE)
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        value = studio.executions.details(key)
        if predicate(value):
            return value
        time.sleep(.05)
    pytest.fail(f'Coordinator did not reach expected state: {value}')


def completed(studio, graph):
    started = studio.executions.launch(graph)
    result = wait_for(studio, started['id'])
    assert result['status'] == 'complete', result.get('error') or result.get('console')
    assert result['logs_complete'] and result['summary']['n_steps'] == 3
    assert result['progress']['percent'] == 100
    assert '[BioPipe launcher]' in result['console']
    return result


def test_real_all_local_worker_and_saved_parameter_snapshot(studio):
    result = completed(studio, workflow(studio))
    assert len(result['children']) == 1 and result['children'][0]['target'] == LOCAL
    assert not studio.remote.service.jobs
    child = result['children'][0]
    directory = studio.local.jobs_dir/child['id']
    assert (directory/'parameters.json').is_file()
    params = json.loads((directory/'parameters.json').read_text(encoding='utf-8'))
    assert 'n_components' in json.dumps(params) and 'total' in json.dumps(params)
    assert result['report']['budget_bytes'] == 32*1024**2
    assert studio.local.resources()['reserved_bytes'] == 0


def test_real_remote_worker_upload_and_completed_content_reuse(studio):
    graph = workflow(studio, environment=studio.ssh)
    first = completed(studio, graph)
    assert len(first['children']) == 1 and first['children'][0]['target'] == studio.ssh
    assert not studio.local.jobs and len(studio.remote.service.jobs) == 1
    chunks = [row for row in studio.control.calls if row[0] == 'transfer_chunk']
    assert chunks
    remote_job = studio.remote.service.details(first['children'][0]['id'])
    remote_source = next(node for node in remote_job['graph']['nodes'] if node['kind'] == 'source')['source']['path']
    assert Path(remote_source).is_relative_to(studio.remote.service.root)
    assert Path(remote_source).read_bytes() == studio.source.read_bytes()
    before = len(chunks)
    second = completed(studio, graph)
    assert second['children'][0]['id'] != first['children'][0]['id']
    assert len([row for row in studio.control.calls if row[0] == 'transfer_chunk']) == before
    assert any(row[0] == 'transfer_begin' and row[2]['complete'] for row in studio.control.calls)
    assert studio.local.resources()['reserved_bytes'] == studio.remote.service.resources()['reserved_bytes'] == 0


def routed_workflow(studio):
    graph = workflow(studio)
    source = graph.nodes[0].model_copy(deep=True)
    source.id = 'inner_input'
    source.source.location = None
    pca = graph.nodes[2].model_copy(deep=True)
    inner = Graph.model_validate({'name': 'Reusable PCA', 'nodes': [source.model_dump(), pca.model_dump()],
                                'edges': [{'id': 'inner', 'source': 'inner_input', 'target': 'pca'}]})
    inner = prepare_interface(inner, studio.local.catalog, studio.local.root)
    inner.nodes[0].source.path = '/old-computer/placeholder.csv'
    from src.web.models import GraphNode
    route = GraphNode.model_validate({'id': 'route_pca', 'kind': 'route', 'title': 'Reusable PCA',
        'position': {'x': 2, 'y': 0}, 'route': {'id': 'route_123456abcdef', 'version': 1, 'name': inner.name,
                                           'graph': inner.model_dump()}})
    graph.nodes[2] = route
    graph.edges[1].target = 'route_pca'
    graph.edges[2].source = 'route_pca'
    graph.runtime['execution']['node_targets'] = {'route_pca': studio.ssh}
    return graph


def test_real_local_ssh_local_form_handoff_and_route_output_alias(studio):
    graph = routed_workflow(studio)
    result = completed(studio, graph)
    assert [child['target'] for child in result['children']] == [LOCAL, studio.ssh, LOCAL]
    assert len(result['execution_plan']['transfers']) == 2
    first, middle, final = result['children']
    local_packet = json.loads((studio.local.jobs_dir/first['id']/'output'/'exchange.json').read_text(encoding='utf-8'))
    server_packet = json.loads((studio.remote.service.jobs_dir/middle['id']/'output'/'exchange.json').read_text(encoding='utf-8'))
    assert 'normalized' in local_packet
    assert 'route_pca__out_1' in server_packet
    assert server_packet['route_pca__out_1']['contract']['dims'] == ['sample', 'component']
    assert any(row[0] == 'transfer_read' for row in studio.control.calls)
    assert any(row[0] == 'transfer_chunk' for row in studio.control.calls)
    final_job = studio.local.details(final['id'])
    source = next(node for node in final_job['graph']['nodes'] if node['kind'] == 'source')
    assert source['id'] in final_job['graph']['runtime']['exchange_inputs']
    assert Path(source['source']['path']).is_relative_to(studio.local.directory/'exchange')
    report_path = studio.executions.export_file(result['id'], 2)
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    assert report['shape'] == [6, 2] and report['dims'] == ['sample', 'component']
    assert report['info']['representation'] == 'scores'
    assert report['labels']['component'] == {'PC1': 0, 'PC2': 1}
    assert report['global']['n_valid'] == 12 and report['global']['n_missing'] == 0
    assert studio.local.resources()['reserved_bytes'] == studio.remote.service.resources()['reserved_bytes'] == 0


def test_remote_worker_continues_offline_then_coordinator_reconnects(studio):
    studio.control.disconnect_after_run = True
    started = studio.executions.launch(workflow(studio, environment=studio.ssh))
    paused = wait_for(studio, started['id'], lambda value: value['status'] == 'waiting_connection')
    assert len(paused['children']) == 1 and not paused['logs_complete']
    child_id = paused['children'][0]['id']
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        child = studio.remote.service.details(child_id)
        if child['status'] not in ACTIVE:
            break
        time.sleep(.05)
    assert child['status'] == 'complete', child.get('error')
    assert studio.executions.details(started['id'])['status'] == 'waiting_connection'
    studio.manager.connect(studio.profile, {})
    result = wait_for(studio, started['id'])
    assert result['status'] == 'complete', result.get('error')
    assert result['logs_complete'] and '[describe]' in result['console']
    assert len(studio.remote.service.jobs) == 1  # Reconnection did not resubmit.
    assert len([row for row in studio.control.calls if row[0] == 'run']) == 1


def test_cancel_during_upload_never_starts_science_and_releases_reservations(studio):
    studio.control.upload_entered = threading.Event()
    studio.control.upload_gate = threading.Event()
    started = studio.executions.launch(workflow(studio, environment=studio.ssh))
    assert studio.control.upload_entered.wait(15), studio.executions.details(started['id'])
    studio.executions.cancel(started['id'])
    studio.control.upload_gate.set()
    result = wait_for(studio, started['id'])
    assert result['status'] == 'cancelled' and result['logs_complete']
    assert not result['children'] and not studio.remote.service.jobs
    assert studio.local.resources()['reserved_bytes'] == studio.remote.service.resources()['reserved_bytes'] == 0
    # A second task can reuse the acknowledged prefix after cancellation.
    studio.control.upload_gate = None
    retried = completed(studio, workflow(studio, environment=studio.ssh))
    assert retried['status'] == 'complete'
    assert any(row[0] == 'transfer_begin' and row[2]['offset'] > 0 for row in studio.control.calls)


def test_saved_execution_and_parameters_are_independent_immutable_versions(studio):
    first = workflow(studio)
    first.name = 'Local document'
    first.memory['budget_mb'] = 16
    second = workflow(studio, environment=studio.ssh)
    second.name = 'Server document'
    second.memory['budget_mb'] = 64
    second.runtime['execution']['max_parallel_tasks'] = 3
    second.nodes[2].params['n_components'] = 3
    saved_a = studio.local.routes.save(SaveWorkflow(graph=first))
    saved_b = studio.local.routes.save(SaveWorkflow(graph=second))
    directory = studio.local.routes.directory
    paths_a = [directory/saved_a[key] for key in ('parameters_file', 'execution_file')]
    paths_b = [directory/saved_b[key] for key in ('parameters_file', 'execution_file')]
    before_a, before_b = [p.read_bytes() for p in paths_a], [p.read_bytes() for p in paths_b]
    persisted = json.loads((directory/(saved_b['id']+'.json')).read_text(encoding='utf-8'))
    assert 'memory' not in persisted['graph']
    assert 'execution' not in persisted['graph'].get('runtime', {})
    config = json.loads(paths_b[1].read_text(encoding='utf-8'))
    assert config['memory']['budget_mb'] == 64 and config['execution']['profile_id'] == studio.profile
    loaded = Graph.model_validate(deepcopy(saved_b['graph']))
    loaded.memory['budget_mb'] = 48
    loaded.runtime['execution']['max_parallel_tasks'] = 1
    loaded.nodes[2].params['n_components'] = 1
    newer = studio.local.routes.save(SaveWorkflow(id=saved_b['id'], expected_version=1, graph=loaded))
    assert newer['parameters_file'] != saved_b['parameters_file']
    assert newer['execution_file'] != saved_b['execution_file']
    assert [p.read_bytes() for p in paths_a] == before_a
    assert [p.read_bytes() for p in paths_b] == before_b
    original_a = Graph.model_validate(studio.local.routes.get(saved_a['id'])['graph'])
    assert original_a.memory['budget_mb'] == 16 and original_a.nodes[2].params['n_components'] == 2
    assert original_a.runtime['execution']['kind'] == 'local'
    restored = import_bundle(export_bundle(Graph.model_validate(saved_b['graph'])))
    assert restored.memory['budget_mb'] == 64 and restored.nodes[2].params['n_components'] == 3
    assert restored.runtime['execution']['max_parallel_tasks'] == 3
    assert restored.runtime['execution']['profile_id'] == studio.profile


def test_legal_boundary_artifact_named_outputs_roundtrips(studio):
    graph = workflow(studio)
    graph.nodes[1].params['output'] = 'outputs'
    graph.runtime['execution']['node_targets'] = {'pca': studio.ssh}
    result = completed(studio, graph)
    assert [child['target'] for child in result['children']] == [LOCAL, studio.ssh, LOCAL]
    first = result['children'][0]
    index = json.loads((studio.local.jobs_dir/first['id']/'output'/'exchange.json').read_text(encoding='utf-8'))
    assert set(index) == {'outputs'} and index['outputs']['contract']['dims'] == ['sample', 'feature']
    report = json.loads(Path(studio.executions.export_file(result['id'], 2)).read_text(encoding='utf-8'))
    assert report['shape'] == [6, 2]


def test_offline_server_cancellation_waits_for_acknowledgement_on_reconnect(studio):
    pool = studio.remote.service.admission
    blocker = 'synthetic-cpu-capacity'
    assert pool.reserve(blocker, {'reserved_bytes': 0, 'cpu_threads': pool.cpus})
    try:
        studio.control.disconnect_after_run = True
        started = studio.executions.launch(workflow(studio, environment=studio.ssh))
        waiting = wait_for(studio, started['id'], lambda value: value['status'] == 'waiting_connection')
        child_id = waiting['children'][0]['id']
        assert studio.remote.service.details(child_id)['status'] == 'queued'
        studio.executions.cancel(started['id'])
        pending = wait_for(studio, started['id'], lambda value: value.get('cancel_pending', False))
        assert not pending['logs_complete'] and pending['status'] == 'waiting_connection'
        assert studio.remote.service.details(child_id)['status'] == 'queued'
        studio.manager.connect(studio.profile, {})
        result = wait_for(studio, started['id'])
        assert result['status'] == 'cancelled' and result['logs_complete']
        assert not result.get('cancel_pending')
        cancelled = studio.remote.service.details(child_id)
        assert cancelled['status'] == 'cancelled' and cancelled['logs_complete']
        assert not studio.remote.service.processes
    finally:
        pool.release(blocker)
    assert pool.resources()['reserved_bytes'] == 0
    assert studio.local.resources()['reserved_bytes'] == 0


def test_remote_source_same_path_same_size_changed_content_uses_new_local_cache(studio):
    server_source = studio.remote.service.root/'input.csv'
    first_bytes = studio.source.read_bytes()
    server_source.write_bytes(first_bytes)
    graph = workflow(studio)
    graph.nodes[0].source.path = str(server_source)
    from src.web.models import ExecutionTarget
    graph.nodes[0].source.location = ExecutionTarget.model_validate(studio.ssh)
    first = completed(studio, graph)
    first_job = studio.local.details(first['children'][0]['id'])
    first_cache = Path(next(n for n in first_job['graph']['nodes'] if n['kind'] == 'source')['source']['path'])
    assert first_cache.read_bytes() == first_bytes
    second_bytes = first_bytes.replace(b'1,2,4,8', b'9,2,4,8')
    assert len(second_bytes) == len(first_bytes) and second_bytes != first_bytes
    server_source.write_bytes(second_bytes)
    second = completed(studio, graph)
    second_job = studio.local.details(second['children'][0]['id'])
    second_cache = Path(next(n for n in second_job['graph']['nodes'] if n['kind'] == 'source')['source']['path'])
    assert first_cache != second_cache
    assert first_cache.read_bytes() == first_bytes and second_cache.read_bytes() == second_bytes
    assert not studio.remote.service.jobs
