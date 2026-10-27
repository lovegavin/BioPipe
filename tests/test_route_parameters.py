"""Saved/portable/run values survive edits to extension default declarations."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import time
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest
import yaml

from biopipe.parameter_values import read_values, split_task, restore_task
from src.core import ManifestError
from src.task.manifest import load_manifest
from src.web.api import create_app
from src.web.graph import compile_graph, import_manifest, GraphError
from src.web.models import Graph, SaveWorkflow
from src.web.parameters import freeze_graph, split_graph, restore_graph, export_bundle, import_bundle
from src.web.routes import RouteLibrary
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def studio(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=ROOT))
    with TestClient(app) as client:
        data = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = data['token']
        yield client, data, app.state.service


def node(graph, key):
    return next(item for item in graph.nodes if item.id == key)


def changed_catalog(catalog):
    result = deepcopy(catalog)
    for spec in result['operators']:
        if spec['id'] == 'pca':
            spec['parameters_schema']['properties']['n_components']['default'] = 3
            spec['runtime_defaults']['n_components'] = 3
    for spec in result['readers']:
        if '.csv' in spec['extensions']:
            spec['parameters_schema']['properties']['header']['default'] = False
            spec['runtime_defaults']['header'] = False
    return result


def test_saved_values_default_edit_restart_and_version_isolation(studio):
    client, data, service = studio
    original = Graph.model_validate(data['demo'])
    node(original, 'pca').params.pop('n_components')
    original.params = {'seed': 0, 'empty': [], 'flag': False, 'nothing': None}
    saved = service.routes.save(SaveWorkflow(graph=original))
    graph = Graph.model_validate(saved['graph'])
    assert node(graph, 'pca').params['n_components'] == 10  # Runtime default, not UI hint 2.
    assert node(graph, 'expression').source.args['header'] is True
    assert 'n_components' not in node(original, 'pca').params  # No caller mutation.
    path = service.routes.directory / saved['parameters_file']
    before = path.read_bytes()
    record = json.loads((service.routes.directory / f"{saved['id']}.json").read_text(encoding='utf-8'))
    assert 'params' not in record['graph']
    assert all('params' not in n for n in record['graph']['nodes'])
    values = json.loads(before)
    assert values['params'] == original.params
    assert values['nodes']['pca']['params']['n_components'] == 10

    catalog = changed_catalog(service.catalog)
    restarted = RouteLibrary(service.routes.directory, catalog, service.root)
    loaded = Graph.model_validate(restarted.get(saved['id'])['graph'])
    compiled, _ = compile_graph(loaded, catalog, service.root)
    assert compiled['steps'][1]['params']['n_components'] == 10
    assert compiled['sources']['expression']['args']['header'] is True
    fresh = freeze_graph(original, catalog, service.root)
    assert node(fresh, 'pca').params['n_components'] == 3
    assert node(fresh, 'expression').source.args['header'] is False

    node(loaded, 'pca').params['n_components'] = 4
    newer = restarted.save(SaveWorkflow(id=saved['id'], expected_version=1, graph=loaded))
    assert newer['parameters_file'] != saved['parameters_file']
    assert path.read_bytes() == before
    assert read_values(restarted.directory, newer['parameters_file'])['nodes']['pca']['params']['n_components'] == 4
    with pytest.raises(GraphError, match='更新'):
        restarted.save(SaveWorkflow(id=saved['id'], expected_version=1, graph=loaded))


def test_incomplete_and_explicit_values_are_saved_without_ui_default_injection(studio):
    _, data, service = studio
    graph = Graph.model_validate(data['demo'])
    node(graph, 'pca').params = {'n_components': 0, 'optional': None, 'flag': False, 'items': []}
    node(graph, 'expression').source.args = {'header': False}
    saved = service.routes.save(SaveWorkflow(graph=graph))
    result = Graph.model_validate(saved['graph'])
    assert node(result, 'pca').params == node(graph, 'pca').params
    assert node(result, 'expression').source.args['header'] is False
    with pytest.raises(GraphError):
        compile_graph(result, service.catalog, service.root)


def test_nested_branches_and_same_operator_instances_keep_separate_values(studio):
    _, data, service = studio
    inner = service.routes.save(SaveWorkflow(graph=Graph.model_validate(data['demo'])))
    graph = Graph.model_validate(data['demo'])
    graph.nodes = graph.nodes[:1]
    graph.edges = []
    for index, components in enumerate((4, 6)):
        route = {'id': inner['id'], 'name': 'nested', 'version': 1, 'graph': deepcopy(inner['graph'])}
        route['graph']['params'] = {'branch': index}
        next(n for n in route['graph']['nodes'] if n['id'] == 'pca')['params']['n_components'] = components
        graph.nodes.append(type(graph.nodes[0]).model_validate({
            'id': f'branch_{index}', 'kind': 'route', 'position': {'x': 1, 'y': index}, 'route': route}))
        from src.web.models import GraphEdge
        graph.edges.append(GraphEdge(id=f'edge_{index}', source='expression', target=f'branch_{index}'))
    saved = service.routes.save(SaveWorkflow(graph=graph))
    sidecar = read_values(service.routes.directory, saved['parameters_file'])
    assert [sidecar['nodes'][f'branch_{i}']['route']['nodes']['pca']['params']['n_components'] for i in (0, 1)] == [4, 6]
    restored = import_bundle(export_bundle(Graph.model_validate(saved['graph'])))
    manifest, _ = compile_graph(restored, changed_catalog(service.catalog), service.root)
    pcas = [s for s in manifest['steps'] if s['name'] == 'pca']
    assert [s['params']['n_components'] for s in pcas] == [4, 6]
    assert [s['context_params']['branch'] for s in pcas] == [0, 1]


def test_interrupted_pair_save_preserves_previous_version(studio, monkeypatch):
    _, data, service = studio
    library = service.routes
    saved = library.save(SaveWorkflow(graph=Graph.model_validate(data['demo'])))
    original_write = library._write
    def fail_commit(path, value):
        if path == library.directory / f"{saved['id']}.json":
            raise OSError('simulated interruption')
        original_write(path, value)
    monkeypatch.setattr(library, '_write', fail_commit)
    graph = Graph.model_validate(saved['graph'])
    node(graph, 'pca').params['n_components'] = 5
    with pytest.raises(OSError):
        library.save(SaveWorkflow(graph=graph, id=saved['id'], expected_version=1))
    restarted = RouteLibrary(library.directory, service.catalog, service.root)
    assert restarted.get(saved['id']) == saved


def test_missing_corrupt_and_mismatched_values_never_fall_back(studio):
    _, data, service = studio
    graph = freeze_graph(Graph.model_validate(data['demo']), service.catalog, service.root)
    topology, values = split_graph(graph)
    broken = deepcopy(values)
    broken['nodes']['pca']['operator'] = 'describe'
    with pytest.raises(ValueError, match='pca'):
        restore_graph(topology, broken)
    broken = deepcopy(values)
    del broken['nodes']['expression']
    with pytest.raises(ValueError):
        restore_graph(topology, broken)
    saved = service.routes.save(SaveWorkflow(graph=graph))
    path = service.routes.directory / saved['parameters_file']
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError, match='原文件已保留'):
        RouteLibrary(service.routes.directory, service.catalog, service.root)
    path.unlink()
    with pytest.raises(ValueError, match='原文件已保留'):
        RouteLibrary(service.routes.directory, service.catalog, service.root)
    for reference in ('../outside.json', str(service.root / 'outside.json')):
        with pytest.raises(ValueError):
            read_values(service.routes.directory, reference)


def test_bundle_api_and_run_use_concrete_task_values(studio):
    client, data, service = studio
    graph = deepcopy(data['demo'])
    next(n for n in graph['nodes'] if n['id'] == 'pca')['params'].pop('n_components')
    exported = client.post('/api/workflows/export', json=graph)
    assert exported.status_code == 200, exported.text
    with ZipFile(BytesIO(exported.content)) as archive:
        assert sorted(archive.namelist()) == ['execution.json', 'graph.json', 'parameters.json']
        assert json.loads(archive.read('parameters.json'))['nodes']['pca']['params']['n_components'] == 10
    bundle_path = service.root / 'saved.biopipe.zip'
    bundle_path.write_bytes(exported.content)
    from biopipe.cli import read_graph_file
    assert node(Graph.model_validate(read_graph_file(bundle_path)), 'pca').params['n_components'] == 10
    imported = client.post('/api/workflows/import', content=exported.content,
                           headers={'Content-Type': 'application/zip'})
    assert imported.status_code == 200, imported.text
    assert client.post('/api/workflows/import', content=b'bad zip').status_code == 422
    run_graph = imported.json()
    assert next(n for n in run_graph['nodes'] if n['id'] == 'pca')['params']['n_components'] == 10
    next(n for n in run_graph['nodes'] if n['id'] == 'pca')['params']['n_components'] = 4
    running = client.post('/api/jobs', json=run_graph)
    assert running.status_code == 202, running.text
    key = running.json()['id']
    directory = service.jobs_dir / key
    raw = yaml.safe_load((directory / 'task.yaml').read_text(encoding='utf-8'))
    assert raw['parameters_file'] == 'parameters.json'
    assert all('params' not in step for step in raw['steps'])
    values = read_values(directory, raw['parameters_file'])
    assert values['steps'][1]['params']['n_components'] == 4
    assert values['sources']['expression']['header'] is True
    hydrated = load_manifest(directory / 'task.yaml')
    assert hydrated['steps'][1]['params']['n_components'] == 4
    assert 'parameters_file' not in hydrated
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        job = client.get(f'/api/jobs/{key}').json()
        if job['status'] != 'running':
            break
        time.sleep(.1)
    assert job['status'] == 'complete', job.get('error')
    assert job['summary']['steps'][1]['name'] == 'pca'
    assert job['summary']['steps'][1]['params']['n_components'] == 4
    with pytest.raises(GraphError, match='参数'):
        import_manifest(yaml.safe_dump(raw), '.', service.catalog, service.root)
    (directory / 'parameters.json').unlink()
    with pytest.raises(ManifestError, match='parameter values'):
        load_manifest(directory / 'task.yaml')


def test_task_pair_roundtrip_and_identity_validation():
    manifest = {'sources': {'x': {'path': 'x.csv', 'dims': ['s', 'f'], 'args': {'header': False}}},
                'params': {'seed': 0}, 'steps': [
                    {'name': 'pca', 'inputs': ['x'], 'params': {'n_components': 2}, 'context_params': {'group': 'a'}},
                    {'name': 'pca', 'inputs': ['x'], 'params': {'n_components': 3}}]}
    task, values = split_task(manifest)
    assert restore_task(task, values) == manifest
    values['steps'][1]['name'] = 'describe'
    with pytest.raises(ValueError, match='do not match'):
        restore_task(task, values)


def test_bundle_rejects_extra_archive_paths_and_invalid_values(studio):
    _, data, service = studio
    graph = freeze_graph(Graph.model_validate(data['demo']), service.catalog, service.root)
    content = BytesIO(export_bundle(graph))
    with ZipFile(content, 'a') as archive:
        archive.writestr('../arbitrary.json', '{}')
    with pytest.raises(ValueError, match='only'):
        import_bundle(content.getvalue())
    topology, values = split_graph(graph)
    with pytest.raises(ValueError, match='do not match'):
        restore_graph(topology, None)


def test_legacy_inline_route_converts_on_explicit_save(studio):
    _, data, service = studio
    directory = service.root / 'inline'
    directory.mkdir()
    saved = {'id': 'route_abcdefabcdef', 'version': 1, 'updated_at': '2026-10-26', 'graph': data['demo']}
    (directory / f"{saved['id']}.json").write_text(json.dumps(saved), encoding='utf-8')
    library = RouteLibrary(directory, service.catalog, service.root)
    loaded = library.get(saved['id'])
    assert loaded['parameters_file'] is None
    converted = library.save(SaveWorkflow(graph=Graph.model_validate(loaded['graph']), id=saved['id'], expected_version=1))
    assert (directory / converted['parameters_file']).is_file()
    assert converted['graph']['nodes'][2]['params']['n_components'] == 2


def test_bundle_prepares_and_runs_after_default_rebuild_in_a_fresh_profile(tmp_path, monkeypatch):
    """A real index rebuild, not just a metadata update in an existing profile."""
    import shutil
    import biopipe.packages as packages
    from biopipe.registry import maintain
    checkout = tmp_path / 'checkout'
    for relative in ('src/task/step/steps', 'src/reader/readers'):
        shutil.copytree(ROOT / relative, checkout / relative, ignore=shutil.ignore_patterns('__pycache__'))
    (checkout / 'biopipe').mkdir()
    shutil.copy2(ROOT / 'biopipe/builtin_packages.json', checkout / 'biopipe/builtin_packages.json')
    monkeypatch.setattr(packages, '__file__', str(checkout / 'biopipe/packages.py'))

    def app_for(name):
        directory = tmp_path / name
        return create_app(Settings(directory, directory / 's', ROOT / 'frontend/dist', testing=True, code_root=ROOT))

    old_app = app_for('old')
    with TestClient(old_app) as client:
        data = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = data['token']
        graph = data['demo']
        next(n for n in graph['nodes'] if n['id'] == 'pca')['params'].pop('n_components')
        exported = client.post('/api/workflows/export', json=graph)
        assert exported.status_code == 200, exported.text
        bundle = exported.content
        prepared = import_bundle(bundle)
        old_service = old_app.state.service
        old_job = old_service.launch(prepared)
        old_service.threads[old_job['id']].join(timeout=40)
        assert old_service.details(old_job['id'])['status'] == 'complete'
        old_job_lock = old_service.jobs_dir / old_job['id'] / 'plugins.lock.json'
        old_lock_bytes = old_job_lock.read_bytes()
    old = import_bundle(bundle)
    old_pin = deepcopy(old.plugin_lock['pca'])
    assert node(old, 'pca').params['n_components'] == 10

    parameter = checkout / 'src/task/step/steps/pca.parameters.json'
    definition = json.loads(parameter.read_text(encoding='utf-8'))
    definition['properties']['n_components']['default'] = 20
    parameter.write_text(json.dumps(definition), encoding='utf-8')
    report = maintain('build', root=checkout, scope='packages')
    assert report['errors'] == [] and report['written']

    fresh_app = app_for('fresh')
    with TestClient(fresh_app) as client:
        data = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = data['token']
        service = fresh_app.state.service
        descriptor = next(d for d in service.plugins.state()['descriptors'] if d['id'] == 'pca')
        assert descriptor['parameters_schema']['properties']['n_components']['default'] == 20
        assert descriptor['implementation']['code_sha'] == old_pin['code_sha']
        assert descriptor['implementation']['declaration_sha'] != old_pin['declaration_sha']
        assert descriptor['implementation']['sha256'] != old_pin['sha256']
        # The new profile contains only its new generation, not D1's snapshot.
        archives = list((service.plugins.directory / 'snapshots').glob('*.json'))
        assert len(archives) == 1
        assert old_pin['declaration_sha'] not in archives[0].read_text(encoding='utf-8')
        imported = client.post('/api/workflows/import', content=bundle)
        assert imported.status_code == 200, imported.text
        prepared = client.post('/api/workflows/prepare', json=imported.json())
        assert prepared.status_code == 200, prepared.text
        prepared_graph = Graph.model_validate(prepared.json())
        assert node(prepared_graph, 'pca').params['n_components'] == 10
        running = client.post('/api/jobs', json=prepared.json())
        assert running.status_code == 202, running.text
        key = running.json()['id']
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            job = client.get(f'/api/jobs/{key}').json()
            if job['status'] != 'running':
                break
            time.sleep(.1)
        assert job['status'] == 'complete', job.get('error')
        assert next(s for s in job['summary']['steps'] if s['name'] == 'pca')['params']['n_components'] == 10
        lock = json.loads((service.jobs_dir / key / 'plugins.lock.json').read_text(encoding='utf-8'))
        selected = next(d for d in lock['descriptors'] if d['id'] == 'pca')
        assert selected['parameters_schema']['properties']['n_components']['default'] == 20
    assert old.plugin_lock['pca'] == old_pin
    assert old_job_lock.read_bytes() == old_lock_bytes
    archived = next(d for d in json.loads(old_lock_bytes)['descriptors'] if d['id'] == 'pca')
    from biopipe_sdk.declarations import load_class
    assert load_class(archived).parameters_schema['properties']['n_components']['default'] == 10


def test_published_v05_bundle_runs_in_a_new_profile_without_old_snapshots(tmp_path):
    """Replay the public-release demo pins, not a user route or copied profile."""
    history = json.loads((ROOT / 'biopipe/bundled_history.json').read_text(encoding='utf-8'))
    pins = {identifier: deepcopy(p['implementation']) for p in history['packages']
            for identifier in p['operators'] if any(r['tag'] == 'v0.5.1' for r in p['releases'])}
    directory = tmp_path / 'fresh'
    app = create_app(Settings(directory, directory / 's', ROOT / 'frontend/dist', testing=True, code_root=ROOT))
    with TestClient(app) as client:
        bootstrap = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = bootstrap['token']
        graph = Graph.model_validate(bootstrap['demo'])
        graph = app.state.service.prepare_graph(graph)
        graph.plugin_lock = {key: pins[key] for key in graph.plugin_lock}
        original = export_bundle(graph)
        frozen_values = split_graph(graph)[1]
        snapshots = list((app.state.service.plugins.directory / 'snapshots').glob('*.json'))
        assert len(snapshots) == 1
        assert pins['pca']['code_sha'] not in snapshots[0].read_text(encoding='utf-8')
        imported = client.post('/api/workflows/import', content=original)
        assert imported.status_code == 200, imported.text
        prepared = client.post('/api/workflows/prepare', json=imported.json())
        assert prepared.status_code == 200, prepared.text
        assert split_graph(Graph.model_validate(prepared.json()))[1] == frozen_values
        running = client.post('/api/jobs', json=imported.json())
        assert running.status_code == 202, running.text
        service = app.state.service
        service.threads[running.json()['id']].join(timeout=40)
        job = service.details(running.json()['id'])
        assert job['status'] == 'complete', job.get('error')
        assert any('released' in u['reason'] for u in job['plugins']['bundled_updates'])
        assert node(import_bundle(original), 'pca').params['n_components'] == 2
