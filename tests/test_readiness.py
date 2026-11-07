"""Readiness is route-scoped, target-specific, read-only and safely reusable."""
from copy import deepcopy
from types import SimpleNamespace
import threading

import pytest

from operon import readiness
from src.web.models import Graph


def workflow():
    return Graph.model_validate({'nodes': [
        {'id': 'data', 'kind': 'source', 'source': {'path': 'data.csv'}, 'position': {'x': 0, 'y': 0}},
        {'id': 'op', 'kind': 'operator', 'operator': 'test', 'position': {'x': 10, 'y': 0}, 'params': {'x': 1}}],
        'edges': [{'id': 'e', 'source': 'data', 'target': 'op'}]})


class Dependencies:
    def __init__(self):
        self.lock = threading.RLock()
        self.entries = {}
        self.calls = []
        self.probes = []
        self.fail = False

    def sync(self, state):
        for item in state['descriptors']:
            self.entries.setdefault(item['id'], {'id': item['id'], 'status': 'unchecked'})

    def snapshot(self):
        return {'entries': deepcopy(list(self.entries.values()))}

    def check(self, *, ids, repair, repair_r):
        self.calls.append((ids, repair, repair_r))
        for key in ids:
            if self.entries[key]['status'] != 'passed':
                self.probes.append(key)
                self.entries[key]['status'] = 'failed' if self.fail else 'passed'
        return self.snapshot()


@pytest.fixture
def app(tmp_path, monkeypatch):
    state = {'generation': 'g1', 'descriptors': [{'id': 'test', 'resources': {}}, {'id': 'CSV', 'resources': {}}]}
    catalog = {'operators': [{'id': 'test', 'parameters_schema': {'type': 'object'}}],
               'readers': [{'id': 'CSV', 'extensions': ['.csv']}]}
    environment = {'key': 1}
    monkeypatch.setattr(readiness, 'environment_identity', lambda *args: deepcopy(environment))
    plugins = SimpleNamespace(state=lambda: state, snapshot=lambda graph: state)
    service = SimpleNamespace(plugins=plugins, dependencies=Dependencies(), root=tmp_path,
                              settings=SimpleNamespace(input_roots=[tmp_path]))
    value = SimpleNamespace(service=service, catalog_for=lambda graph: catalog)
    value.readiness = readiness.ReadinessService(value)
    value.environment = environment
    (tmp_path / 'data.csv').write_text('x\n1\n')
    return value


def test_ready_cache_ignores_layout_but_invalidates_values_inputs_generation_and_environment(app):
    graph = workflow()
    first = app.readiness.validate(graph, {}, require_files=True)
    assert first['status'] == 'ready' and not first['cached']
    assert app.service.dependencies.calls == [(['CSV', 'test'], False, False)]
    graph.nodes[1].position.x = 40
    assert app.readiness.validate(graph, {}, require_files=True)['cached']
    graph.nodes[1].params['x'] = 2
    assert not app.readiness.validate(graph, {}, require_files=True)['cached']
    assert len(app.service.dependencies.probes) == 2  # successful dependency checks survive parameter edits
    (app.service.root / 'data.csv').write_text('x\n12345\n')
    assert not app.readiness.validate(graph, {}, require_files=True)['cached']
    app.service.plugins.state()['generation'] = 'g2'
    assert not app.readiness.validate(graph, {}, require_files=True)['cached']
    app.environment['key'] = 2
    assert not app.readiness.validate(graph, {}, require_files=True)['cached']
    assert len(app.service.dependencies.probes) == 4


def test_blocked_never_cached_and_validation_never_repairs(app):
    app.service.dependencies.fail = True
    assert app.readiness.validate(workflow(), {})['status'] == 'blocked'
    app.service.dependencies.fail = False
    assert app.readiness.validate(workflow(), {})['status'] == 'ready'
    assert len(app.service.dependencies.calls) == 2
    assert all(not repair and not repair_r for _, repair, repair_r in app.service.dependencies.calls)


def test_nested_route_placeholders_do_not_register_reader_dependencies(app):
    graph = workflow()
    inner = workflow()
    inner.nodes[0].source.path = 'placeholder.unknown'
    inner.nodes[0].source.reader = 'not-installed-placeholder'
    graph.nodes[1] = graph.nodes[1].model_copy(update={'kind': 'route', 'operator': None,
        'route': __import__('src.web.models', fromlist=['RouteDefinition']).RouteDefinition(
            id='route_0123456789ab', version=1, name='route', graph=inner)})
    assert readiness.required_ids(graph, app.catalog_for(graph), ['op']) == {'test', 'CSV'}


def test_remote_script_probed_on_selected_host_and_connection_rechecked(app, monkeypatch):
    graph = workflow()
    graph.nodes[1] = graph.nodes[1].model_copy(update={'kind': 'script', 'operator': None,
                                                    'script': {'language': 'python', 'code': 'remote-only'}})
    calls = []
    def call(target, method, payload):
        calls.append((target, method, payload))
        return {'entries': {'CSV': {'status': 'passed'}}, 'scripts': {'op': {'status': 'passed'}}}
    app.service.remotes = SimpleNamespace(call=call)
    from operon import script_operators
    monkeypatch.setattr(script_operators, 'inspect_script_environment', lambda value: pytest.fail('Must not inspect remote scripts locally'))
    plan = {'execution_plan': {'units': [{'target': {'kind': 'ssh', 'profile_id': 'server'}, 'node_ids': ['op']}]}}
    for _ in range(2):
        result = app.readiness.validate(graph, plan)
        assert result['status'] == 'ready' and not result['cached']
    assert len(calls) == 2 and calls[0][2]['scripts']['op']['code'] == 'remote-only'
    def offline(*args):
        raise ConnectionError('offline')
    app.service.remotes.call = offline
    assert app.readiness.validate(graph, plan)['status'] == 'blocked'


def test_selected_operating_system_enforced_before_dependency_probe(app, monkeypatch):
    app.service.plugins.state()['descriptors'][0]['resources'] = {'external_tools': ['bwa']}
    monkeypatch.setattr(readiness.platform, 'system', lambda: 'Windows')
    result = app.readiness.validate(workflow(), {})
    assert result['status'] == 'blocked'
    assert next(item for item in result['blocked'] if item['id'] == 'test')['status'] == 'unsupported'
    assert app.service.dependencies.probes == ['CSV']


def test_scoped_pins_do_not_require_other_hosts_operators():
    graph = workflow()
    graph.plugin_lock = {'test': {'version': '1'}, 'remote_only': {'version': '2'}}
    assert readiness.scoped_pins(graph, {'test'}).plugin_lock == {'test': {'version': '1'}}
    assert 'remote_only' in graph.plugin_lock


def test_remote_dispatch_validates_scripts_and_never_installs_implicitly(app, monkeypatch):
    from operon.remote.server import RemoteService
    from operon import script_operators
    monkeypatch.setattr(script_operators, 'inspect_script_environment',
                        lambda value: {'status': 'passed', 'language': value['language']})
    remote = RemoteService.__new__(RemoteService)
    remote.service, remote.transport_leases = app.service, {}
    result = remote.dispatch('validate_environment', {'ids': ['test'], 'scripts': {'script': {'language': 'python'}}})
    assert result['entries']['test']['status'] == 'passed'
    assert result['scripts']['script']['language'] == 'python'
    assert app.service.dependencies.calls == [(['test'], False, False)]
    with pytest.raises(ValueError, match='explicit list'):
        remote.dispatch('validate_environment', {'ids': 'test'})


def test_application_validation_can_reach_explicit_repair_after_failed_placement(app, monkeypatch):
    from operon.application import Application
    from src.web import execution
    from src.web.graph import GraphError
    graph = workflow()
    graph.runtime['execution'] = {'kind': 'local', 'mode': 'manual'}
    selected = execution.ExecutionService.__new__(execution.ExecutionService)
    selected.service = app.service
    selected.prepare = lambda value: value
    selected.catalog = app.catalog_for
    selected._validate_structure = lambda value: ({}, ['op'])
    selected._size = lambda *args: 10
    selected.infos = lambda **kwargs: [{'target': {'kind': 'local'}, 'system': 'windows',
        'catalog': app.catalog_for(graph), 'tools': {}, 'dependencies': app.service.dependencies.snapshot()}]
    monkeypatch.setattr(execution, 'analyze_graph', lambda *args, **kwargs: {'edges': []})
    app.executions = selected
    app.service.dependencies.sync(app.service.plugins.state())
    app.service.dependencies.fail = True
    for entry in app.service.dependencies.entries.values():
        entry['status'] = 'failed'
    with pytest.raises(GraphError, match='dependencies are not ready'):
        selected.plan(graph)
    blocked = Application.validate(app, graph)
    assert blocked['readiness']['status'] == 'blocked'
    assert blocked['execution_plan']['validation_only']
    original = app.service.dependencies.check
    def prepare(**kwargs):
        if kwargs['repair']:
            app.service.dependencies.fail = False
        return original(**kwargs)
    app.service.dependencies.check = prepare
    repaired = Application.validate(app, graph, repair=True)
    assert repaired['readiness']['status'] == 'ready'
    assert app.service.dependencies.calls[-1] == (['CSV', 'test'], True, True)
    assert 'validation_only' not in selected.plan(graph)


def test_remote_reference_paths_are_not_statted_on_editor_or_served_from_local_cache(app, monkeypatch):
    graph = workflow()
    graph.runtime['execution'] = {'kind': 'local', 'file_locations': {
        'op.params.reference': {'kind': 'ssh', 'profile_id': 'server'}}}
    graph.nodes[1].params['reference'] = '/server/reference.fasta'
    monkeypatch.setattr(app.readiness, '_input_stamps', lambda *args: pytest.fail('Remote path must not be statted locally'))
    for _ in range(2):
        assert not app.readiness.validate(graph, {})['cached']
