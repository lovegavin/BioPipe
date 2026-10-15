"""Regression coverage for source staging and Studio/core capability gaps."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import time

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

from src.task import Context, STEPS, run
from src.task.memory import MemoryBudgetError, DiskBudgetError
from src.task.operator_catalog import build_catalog
from src.web.api import create_app
from src.web.graph import import_manifest, compile_graph
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def studio(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=ROOT))
    with TestClient(app) as client:
        bootstrap = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = bootstrap['token']
        yield client, app, bootstrap


def test_large_workspace_autosave_and_agent_sync(studio):
    client, _, data = studio
    graph = deepcopy(data['demo'])
    graph['params'] = {'large': 'x' * (2 * 1024**2 + 100)}
    workspace = {'schema_version': 1, 'active_id': 'page', 'documents': [{'id': 'page', 'graph': graph}]}
    assert client.post('/api/workspace', json=workspace).status_code == 200
    assert client.get('/api/workspace').json()['documents'][0]['graph']['params'] == graph['params']
    response = client.post('/api/agent/sessions', json={'workspace': workspace})
    assert response.status_code == 200, response.text
    text = yaml.safe_dump({'sources': {'X': {'path': 'x.csv', 'dims': ['sample', 'feature']}},
                           'steps': [{'name': 'describe', 'inputs': ['X']}], 'params': graph['params']})
    response = client.post('/api/import', json={'text': text})
    assert response.status_code == 200, response.text
    assert response.json()['params'] == graph['params']


def test_yaml_roundtrip_preserves_context_memory_and_alignment(tmp_path):
    catalog = build_catalog(STEPS)
    raw = {'name': 'roundtrip', 'sources': {name: {'path': 'x.csv', 'dims': ['sample', 'feature'],
                'labels': {'sample': 'auto', 'feature': 'builtin'}} for name in ('source A', 'B')},
           'steps': [{'name': 'concat', 'inputs': ['source A', 'B'], 'params': {
               'axis': 'feature', 'output': 'joined', 'align': {'dim': 'sample', 'key': {'source A': 'id', 'B': 'id'}}}}],
           'params': {'seed': 42}, 'notes': {'owner': 'lab'},
           'runtime': {'memory': {'enabled': False}, 'custom': {'flag': True}}}
    graph = import_manifest(yaml.safe_dump(raw), '.', catalog, tmp_path)
    compiled, _ = compile_graph(graph, catalog, tmp_path)
    assert compiled['runtime'] == raw['runtime']
    assert compiled['params'] == raw['params'] and compiled['notes'] == raw['notes']
    assert set(compiled['steps'][0]['params']['align']['key']) == set(compiled['steps'][0]['inputs'])
    raw.pop('runtime')
    assert import_manifest(yaml.safe_dump(raw), '.', catalog, tmp_path).memory['enabled'] is False


def make_mtx(directory, shape=(1000, 1000), compressed=False):
    path = directory / ('matrix.mtx.gz' if compressed else 'matrix.mtx')
    text = f'%%MatrixMarket matrix coordinate real general\n% example\n{shape[0]} {shape[1]} 4\n1 1 2\n1 1 3\n{shape[0]} {shape[1]} 7\n2 3 -1\n'
    if compressed:
        path.write_bytes(gzip.compress(text.encode()))
    else:
        path.write_text(text)
    (directory / 'features.tsv').write_text('\n'.join(f'g{i}' for i in range(shape[0])))
    (directory / 'barcodes.tsv').write_text('\n'.join(f'c{i}' for i in range(shape[1])))
    return path


def source_context(directory, path, **memory):
    manifest = {'sources': {'X': {'path': str(path), 'dims': ['sample', 'feature'],
                                  'labels': {'sample': 'builtin', 'feature': 'builtin'}}},
                'steps': [{'name': 'describe', 'inputs': ['X'], 'params': {}}],
                'runtime': {'memory': {'budget_mb': 1, 'chunk_mb': .01, 'keep': ['X'], **memory}}}
    context = Context(directory, manifest)
    context.register_source('X', manifest['sources']['X'])
    return context, manifest


@pytest.mark.parametrize('compressed', [False, True])
def test_mtx_preparation_streams_without_full_densification(tmp_path, monkeypatch, compressed):
    path = make_mtx(tmp_path, compressed=compressed)
    from src.reader.readers.mtx_reader import MtxReader
    monkeypatch.setattr(MtxReader, 'read', lambda *a, **k: pytest.fail('eager reader must not run'))
    ctx, manifest = source_context(tmp_path, path)
    try:
        entry = ctx.forms.entry('X')
        assert entry.source_probe['file_bytes'] == path.stat().st_size
        assert entry.source_probe['dense_bytes'] == 4_000_000
        run(ctx, manifest['steps'])
        assert entry.form is None and entry.disk
        actual = np.load(entry.disk / 'data.npy', mmap_mode='r')
        assert actual[0, 0] == 5 and actual[-1, -1] == 7 and actual[1, 2] == -1
        assert float(actual.sum()) == 11
        del actual
        events = [json.loads(line) for line in ctx.memory.event_path.read_text().splitlines()]
        prepared = next(e for e in events if e['event'] == 'source_prepare_complete')
        assert prepared['buffer_peak_bytes'] <= .021 * 1024**2
        assert next(i for i,e in enumerate(events) if e['event'] == 'source_prepare_complete') < next(i for i,e in enumerate(events) if e['event'] == 'step_plan')
        with pytest.raises(MemoryBudgetError):
            ctx['X']
    finally:
        ctx.memory.close('complete')


@pytest.mark.parametrize('encoding', ['dense', 'csr', 'csc'])
@pytest.mark.parametrize('layer', [False, True])
def test_h5ad_disk_values_labels_and_no_eager_anndata(tmp_path, monkeypatch, encoding, layer):
    import anndata as ad
    import pandas as pd
    from scipy import sparse
    data = np.arange(36, dtype=np.float32).reshape(6, 6)
    matrix = data if encoding == 'dense' else getattr(sparse, encoding + '_matrix')(data)
    value = ad.AnnData(X=matrix, obs=pd.DataFrame(index=[f's{i}' for i in range(6)]),
                      var=pd.DataFrame(index=[f'f{i}' for i in range(6)]))
    if layer:
        value.layers['counts'] = matrix * 2
    path = tmp_path / 'input.h5ad'
    value.write_h5ad(path)
    monkeypatch.setattr(ad, 'read_h5ad', lambda *a, **k: pytest.fail('whole AnnData read is forbidden'))
    from src.reader import pick_reader
    reader = pick_reader(path)
    from src.reader.disk import DenseDiskWriter
    args = {'layer': 'counts'} if layer else {}
    probe = reader.probe(path, **args)
    target = tmp_path / 'result.npy'
    writer = DenseDiskWriter(target, probe['shape'], block_bytes=16, budget_bytes=32)
    try:
        metadata = reader.read_to_disk(path, ['sample', 'feature'], {}, writer, 16, **args)
    finally:
        writer.close()
    np.testing.assert_array_equal(np.load(target), data * (2 if layer else 1))
    assert metadata['labels']['sample']['s5'] == 5
    assert writer.peak_bytes <= 32


def test_source_disk_quota_and_malformed_input_cleanup(tmp_path):
    path = make_mtx(tmp_path)
    ctx, _ = source_context(tmp_path, path, disk_limit_mb=.1)
    try:
        with pytest.raises(DiskBudgetError):
            ctx.forms.stage_source(ctx.forms.entry('X'))
        assert not list(ctx.forms.cache_root.iterdir())
    finally:
        ctx.memory.close('failed')

    path.write_text(path.read_text().rsplit('\n', 2)[0] + '\n')
    ctx, _ = source_context(tmp_path, path)
    try:
        with pytest.raises(Exception, match='truncated'):
            ctx.forms.stage_source(ctx.forms.entry('X'))
        assert not list(ctx.forms.cache_root.iterdir())
    finally:
        ctx.memory.close('failed')


def test_planner_releases_only_required_clean_blocks(tmp_path):
    path = make_mtx(tmp_path)
    ctx, _ = source_context(tmp_path, path)
    try:
        entry = ctx.forms.entry('X')
        ctx.forms.stage_source(entry)
        assert len(entry.source_blocks) == 2
        ctx.forms.ensure(ctx.memory.config.budget_bytes - entry.source_block_bytes, 'next_operator')
        assert len(entry.source_blocks) == 1
        assert ctx.forms.managed == entry.source_block_bytes
        chunks = ctx.forms.chunks(entry, 123)
        assert sum(float(chunk.sum()) for chunk in chunks) == 11
        ctx.forms._remove(entry)
        assert ctx.forms.managed == 0 and ctx.forms.disk_bytes == 0
    finally:
        ctx.memory.close('complete')


def test_nested_route_alignment_and_global_context(tmp_path):
    from src.web.models import Graph, GraphNode, GraphEdge, Position, RouteDefinition
    from src.web.routes import prepare_interface, expand_routes
    catalog = build_catalog(STEPS)
    raw = {'sources': {name: {'path': 'x.csv', 'dims': ['sample', 'feature']} for name in ('A', 'B')},
           'steps': [{'name': 'concat', 'inputs': ['A', 'B'], 'params': {'axis': 'feature', 'output': 'joined',
                     'align': {'dim': 'sample', 'key': {'A': 'id', 'B': 'id'}}}}], 'params': {'seed': 42}}
    inner = prepare_interface(import_manifest(yaml.safe_dump(raw), '.', catalog, tmp_path), catalog, tmp_path)
    source_nodes = [n.model_copy(deep=True) for n in inner.nodes if n.kind == 'source']
    for node in source_nodes:
        node.id = 'outer_' + node.id
    route = GraphNode(id='route', kind='route', position=Position(x=0, y=0),
                      route=RouteDefinition(id='route_abcdefabcdef', version=1, name='inner', graph=inner))
    outer = Graph(nodes=source_nodes + [route], edges=[GraphEdge(id=f'e{i}', source=n.id, target='route',
                  targetHandle=f'in-{i}') for i,n in enumerate(source_nodes)], params={'seed': 7, 'parent': True})
    expanded, _ = expand_routes(outer, catalog)
    op = next(n for n in expanded.nodes if n.kind == 'operator')
    assert set(op.params['align']['key']) == {n.id for n in source_nodes}
    assert op.context_params == {'seed': 42, 'parent': True}


def test_context_overrides_are_step_local(tmp_path, monkeypatch):
    from src.task.step.base import Step
    observed = []
    class Observe(Step):
        name = 'observe_context'
        inputs_arity = 0
        def run(self, ctx, inputs):
            observed.append(dict(ctx.params))
    monkeypatch.setitem(STEPS, Observe.name, Observe)
    steps = [{'name': Observe.name, 'context_params': {'seed': 42}}, {'name': Observe.name}]
    ctx = Context(tmp_path, {'sources': {}, 'steps': steps, 'params': {'seed': 7}})
    run(ctx, steps)
    assert observed == [{'seed': 42}, {'seed': 7}] and ctx.params == {'seed': 7}


def test_block_emergency_spill_and_duplicate_values(tmp_path):
    from src.reader.disk import DenseDiskWriter
    events = []
    target = tmp_path / 'data.npy'
    writer = DenseDiskWriter(target, (2, 5), block_bytes=8, budget_bytes=16,
                             pressure=lambda: True, event=lambda action, **kw: events.append(kw))
    try:
        writer.write(0, 0, [1, 2, 3, 4, 5])
        writer.add(0, 0, 4)
        writer.add(1, 4, 7)
    finally:
        writer.close()
    np.testing.assert_array_equal(np.load(target), [[5, 2, 3, 4, 5], [0, 0, 0, 0, 7]])
    assert any(e['reason'] == 'rss_pressure' for e in events)


def test_plugin_endpoints_use_worker_and_publish_only_success(studio, monkeypatch):
    client, app, _ = studio
    manager = app.state.service.plugins
    calls = []
    def install(wheel, *, remove=None):
        calls.append((Path(wheel).read_bytes() if wheel else None, remove))
        if wheel and Path(wheel).read_bytes() == b'bad':
            raise ValueError('invalid wheel')
        return manager.state()
    monkeypatch.setattr(manager, 'install', install)
    # This test isolates transactional publication; dependency subprocesses have
    # their own integration tests and may legitimately exceed the UI poll loop.
    monkeypatch.setattr(app.state.service.dependencies, 'check', lambda **kwargs: None)
    for content, expected in [(b'wheel', 'complete'), (b'bad', 'failed')]:
        response = client.post('/api/plugins/install?filename=lab-1-py3-none-any.whl', content=content)
        assert response.status_code == 200, response.text
        for _ in range(100):
            operation = client.get('/api/plugins/operations/' + response.json()['id']).json()
            if operation['status'] != 'running':
                break
            time.sleep(.01)
        assert operation['status'] == expected
    assert len(calls) == 2
    assert client.post('/api/plugins/install?filename=../bad.whl', content=b'x').status_code == 422
    assert client.post('/api/plugins/install?filename=lab.whl', content=b'x', headers={'X-Studio-Token': ''}).status_code == 403
    assert not list((manager.directory / 'incoming').iterdir())


def test_reader_and_operator_options_are_discoverable():
    catalog = build_catalog(STEPS)
    readers = {r['name']: r for r in catalog['readers']}
    assert {'header', 'sep', 'encoders'} <= set(readers['CsvReader']['parameters_schema']['properties'])
    assert readers['H5adReader']['parameters'][0]['type'] == 'string'
    ops = {o['name']: o for o in catalog['operators']}
    assert {'align', 'label'} <= set(ops['concat']['parameters_schema']['properties'])
    assert {'alpha', 'point_size', 'color_label'} <= {p['key'] for p in ops['scatter']['parameters']}


def test_duplicate_coordinates_keep_source_precision(tmp_path):
    from src.reader.readers.mtx_reader import MtxReader
    from src.reader.disk import DenseDiskWriter
    path = make_mtx(tmp_path, shape=(3, 3))
    path.write_text('%%MatrixMarket matrix coordinate real general\n3 3 3\n1 1 100000000\n1 1 1\n1 1 -100000000\n')
    reader = MtxReader()
    writer = DenseDiskWriter(tmp_path / 'result.npy', (3, 3), block_bytes=8, budget_bytes=16)
    try:
        reader.read_to_disk(path, ['sample', 'feature'], {}, writer, 16)
    finally:
        writer.close()
    assert np.load(tmp_path / 'result.npy')[0, 0] == 1
    assert not (tmp_path / 'accumulator.npy').exists()


def test_yaml_custom_dimensions_keep_omitted_reader_labels(tmp_path):
    raw = {'sources': {'X': {'path': 'matrix.mtx', 'dims': ['gene', 'cell']}},
           'steps': [{'name': 'describe', 'inputs': ['X']}]}
    graph = import_manifest(yaml.safe_dump(raw), '.', build_catalog(STEPS), tmp_path)
    assert graph.nodes[0].source.labels == {}
