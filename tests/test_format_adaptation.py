"""Type safety, actual conversion, portable kernels and graph integration."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from biopipe.conversions import converter_registry, execute_conversion, plan_conversion
from biopipe_sdk.formats import Adaptation, DataFormats
from src.core import Form


def port(representation='numpy.ndarray', logical_type='matrix', **metadata):
    return {'logical_type': logical_type, 'representations': [representation], 'metadata': metadata}


def form():
    return Form(np.arange(12, dtype=np.float32).reshape(3, 4)[:, ::-1],
        ['sample', 'feature'], {'sample': {str(i): i for i in range(3)}, 'feature': {str(i): i for i in range(4)}},
        {'group': ['a', 'b', 'c'], 'missing_code': float('nan')}, {'sample': ['group']})


def test_logical_types_before_encoding_and_metadata_loss():
    assert plan_conversion(port(), port(logical_type='list'))['status'] == 'incompatible'
    assert 'explicit' in str(plan_conversion(port(), port(logical_type='list')))
    assert plan_conversion(port(), port(assembly='hg38'))['status'] == 'unknown'
    assert plan_conversion(port(assembly='hg19'), port(assembly='hg38'))['status'] == 'incompatible'
    assert plan_conversion(None, None) == {'status': 'compatible', 'reasons': []}
    assert plan_conversion(None, port())['status'] == 'unknown'
    assert plan_conversion(None, None, {'mode': 'fixed', 'converters': ['matrix.npy.write']})['status'] == 'unknown'


def test_direct_conversion_policy_and_frozen_identity():
    direct = plan_conversion(port(), port())['conversion_plan']
    assert direct['converters'] == []
    planned = plan_conversion(port(), port('npy.memmap'))
    assert planned['status'] == 'compatible'
    assert planned['conversion_plan']['converters'][0]['id'] == 'matrix.npy.write'
    assert len(planned['conversion_plan']['converters'][0]['code_sha']) == 64
    assert plan_conversion(port(), port('npy.memmap'), {'mode': 'disabled'})['status'] == 'incompatible'
    assert plan_conversion(port(), port('npy.memmap'), {'mode': 'fixed', 'converters': ['matrix.npy.view']})['status'] == 'incompatible'
    assert plan_conversion(port(), port('csv'))['status'] == 'incompatible'
    with pytest.raises(ValueError):
        Adaptation(mode='auto', converters=['matrix.npy.write'])


def test_bounded_deterministic_search():
    entries = [dict(id=f'cycle{i}', source=f'f{i}', target=f'f{i+1}', logical_type='matrix', lossless=True) for i in range(8)]
    assert plan_conversion(port('f0'), port('f8'), registry=entries)['status'] == 'incompatible'
    entries += [dict(id='short', source='f0', target='f8', logical_type='matrix', lossless=True)]
    a = plan_conversion(port('f0'), port('f8'), registry=entries)
    assert a == plan_conversion(port('f0'), port('f8'), registry=list(reversed(entries)))
    assert a['conversion_plan']['converters'][0]['id'] == 'short'


def test_real_roundtrip_no_dense_copy_metadata_preserved(tmp_path):
    original = form()
    direct = execute_conversion(original, plan_conversion(port(), port())['conversion_plan'], tmp_path)
    assert direct is original and not list(tmp_path.iterdir())
    plan = plan_conversion(port(), port('npy.memmap', dtype='float32'))
    assert plan['status'] == 'unknown'  # dtype cannot be guessed
    plan = plan_conversion(port(dtype='float32'), port('npy.memmap', dtype='float32'))['conversion_plan']
    admitted, ticks = [], []
    disk = execute_conversion(original, plan, tmp_path, buffer_bytes=16,
                              admit=admitted.append, checkpoint=lambda: ticks.append(True))
    assert isinstance(disk.data, np.memmap)
    np.testing.assert_array_equal(disk.data, original.data)
    assert disk.axis_info == original.axis_info and disk.labels == original.labels
    assert disk.info['group'] == original.info['group']
    assert np.isnan(disk.info['missing_code'])
    assert admitted and len(ticks) > 1 and not disk.data.flags.writeable
    view = execute_conversion(disk, plan_conversion(port('npy.memmap'), port())['conversion_plan'], tmp_path)
    assert type(view.data) is np.ndarray and np.shares_memory(view.data, disk.data)


def test_runtime_preconditions_and_cancel(tmp_path):
    plan = plan_conversion(port(dtype='float64'), port('npy.memmap', dtype='float64'))['conversion_plan']
    with pytest.raises(ValueError, match='metadata'):
        execute_conversion(form(), plan, tmp_path)
    plan = plan_conversion(port(), port('npy.memmap'))['conversion_plan']
    altered = deepcopy(plan)
    altered['converters'][0]['code_sha'] = '0' * 64
    with pytest.raises(ValueError, match='changed'):
        execute_conversion(form(), altered, tmp_path)
    def stop():
        raise RuntimeError('cancel')
    with pytest.raises(RuntimeError, match='cancel'):
        execute_conversion(form(), plan, tmp_path, checkpoint=stop)
    assert not list(tmp_path.iterdir())
    def deny(count):
        raise MemoryError('disk quota')
    with pytest.raises(MemoryError, match='quota'):
        execute_conversion(form(), plan, tmp_path, admit=deny)


def catalog():
    spec = dict(id='consume', title='consume', inputs_arity=1, outputs=[], output_parameter='output',
        parameters_schema={'type': 'object', 'properties': {'output': {'type': 'string', 'default': 'out'}}}, runtime_defaults={'output': 'out'},
        contracts={'version': 1, 'inputs': [{'ndim': 2}], 'output': {'mode': 'passthrough'}},
        data_formats={'inputs': [port('npy.memmap')], 'outputs': [port('npy.memmap')]})
    reader = dict(id='TestReader', extensions=['.csv'], requires_siblings=[], handles_compression=True,
        contracts={'output': {'ndim': 2}}, parameters_schema={'type': 'object'}, data_formats={'inputs': [], 'outputs': [port()]})
    return {'operators': [spec], 'readers': [reader]}


def graph():
    from src.web.models import Graph
    return Graph.model_validate({'nodes': [
        {'id': 'data', 'kind': 'source', 'position': {'x': 0, 'y': 0}, 'source': {'path': 'input.csv'}},
        {'id': 'end', 'kind': 'operator', 'operator': 'consume', 'params': {'output': 'out'}, 'position': {'x': 200, 'y': 0}}],
        'edges': [{'id': 'edge', 'source': 'data', 'target': 'end'}]})


def test_compile_freezes_converter_and_bad_types_block(tmp_path):
    from src.web.graph import compile_graph, GraphError
    from src.web.contracts import analyze_graph
    c = catalog()
    analysis = analyze_graph(graph(), c, tmp_path)
    assert analysis['edges'][0]['conversion_plan']['converters'][0]['id'] == 'matrix.npy.write'
    manifest, ids = compile_graph(graph(), c, tmp_path)
    assert ids == ['end']
    assert manifest['steps'][0]['conversions'][0]['edge_id'] == 'edge'
    c['operators'][0]['data_formats']['inputs'][0]['logical_type'] = 'list'
    with pytest.raises(GraphError, match='Logical type'):
        compile_graph(graph(), c, tmp_path)


def test_runner_executes_frozen_converter_and_disk_quota(tmp_path, monkeypatch):
    from src.task import Context, STEPS, run
    from src.task.step.base import Step
    class Consumer(Step):
        name = "consume"
        inputs_arity = 1
        parameters_schema = {'type': 'object'}
        input_contracts = [{'ndim': 2}]
        output_contract = {'mode': 'report'}
        outputs = []
        output_parameter = None
        def run(self, ctx, inputs):
            assert isinstance(inputs[0].data, np.memmap)
            assert inputs[0].axis_info == {'sample': ['group']}
        def export(self, ctx):
            return {'ok': True}
    from extension_fixtures import bound_fixture
    monkeypatch.setitem(STEPS, 'consume', bound_fixture(Consumer))
    plan = plan_conversion(port(), port('npy.memmap'))['conversion_plan']
    steps = [{'name': 'consume', 'inputs': ['data'], 'params': {},
              'conversions': [{'port': 0, 'edge_id': 'edge', 'plan': plan}]}]
    ctx = Context(tmp_path, {'runtime': {'memory': {'enabled': True, 'budget_mb': 16, 'disk_limit_mb': 1}}})
    ctx['data'] = form()
    try:
        run(ctx, steps)
        assert ctx.memory.counts['conversion_finished'] == 1
        assert ctx.memory.store.disk_bytes > 0
    finally:
        ctx.memory.close('complete')


def test_kernel_exports_without_biopipe(tmp_path):
    from biopipe import converter_kernels
    target = tmp_path / 'converter_kernels.py'
    target.write_text(Path(converter_kernels.__file__).read_text(encoding='utf-8'), encoding='utf-8')
    script = tmp_path / 'run.py'
    script.write_text('import sys\nimport numpy as np\nfrom converter_kernels import array_to_npy\n'
                      'a=array_to_npy(np.arange(12).reshape(3,4), "out.npy", buffer_bytes=16)\n'
                      'assert a.sum()==66\nassert not any(k.startswith("biopipe") for k in sys.modules)\n')
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_optional_sdk_36_capabilities_keep_old_descriptors_unchanged():
    from biopipe_sdk.protocol import validate_declaration
    value = {'protocol_version': 3, 'id': 'format_test', 'version': '1.0.0', 'kind': 'operator',
             'entry_point': 'sample:Step', 'code_sha': 'a' * 64, 'declaration_sha': 'b' * 64,
             'title': 'Format test', 'parameters_schema': {'type': 'object'},
             'contracts': {'version': 1, 'inputs': [{}], 'output': {'mode': 'passthrough'}},
             'resources': {'memory_modes': ['full']}, 'inputs_arity': 1, 'outputs': ['out']}
    before = deepcopy(value)
    validate_declaration(value)
    assert value == before
    value['data_formats'] = {'inputs': [port()], 'outputs': [port()]}
    with pytest.raises(ValueError, match='3.6'):
        validate_declaration(value)
    value['protocol_revision'] = '3.6'
    validate_declaration(value)
    value['data_formats']['inputs'] = []
    with pytest.raises(ValueError, match='input port'):
        validate_declaration(value)


def test_failed_converter_reservation_does_not_leak_or_underflow(tmp_path):
    from types import SimpleNamespace
    import threading
    from biopipe.conversions import apply_step_conversions
    from src.task.memory.config import MemoryBudgetError
    def denied(*args):
        raise MemoryBudgetError('insufficient memory')
    store = SimpleNamespace(cache_root=tmp_path, reserved=0, disk_bytes=0, lock=threading.RLock(), ensure=denied)
    memory = SimpleNamespace(store=store, config=SimpleNamespace(io_buffer_bytes=65536, budget_bytes=1024))
    ctx = SimpleNamespace(memory=memory, task_dir=tmp_path)
    plan = plan_conversion(port(), port('npy.memmap'))['conversion_plan']
    with pytest.raises(MemoryBudgetError):
        apply_step_conversions(ctx, [form()], [{'port': 0, 'edge_id': 'e', 'plan': plan}])
    assert store.reserved == 0 and store.disk_bytes == 0


def test_sdk37_requires_formats_and_preserves_legacy_model():
    from biopipe.packages import bundled_entries
    from biopipe_sdk.protocol import Descriptor, validate_declaration
    descriptor = deepcopy(next(d for _, d in bundled_entries('operator') if d['id'] == 'pca'))
    Descriptor.model_validate(descriptor)
    descriptor['protocol_revision'] = '3.7'
    descriptor.pop('data_formats', None)
    with pytest.raises(ValueError, match='requires explicit'):
        Descriptor.model_validate(descriptor)
    descriptor['data_formats'] = {'inputs': [port('form', 'form')], 'outputs': [port('form', 'form')]}
    validate_declaration(descriptor)
    descriptor['data_formats']['inputs'] = []
    with pytest.raises(ValueError, match='input port'):
        validate_declaration(descriptor)


def test_form_identity_keeps_payload_and_metadata_without_scratch(tmp_path):
    original = form()
    plan = plan_conversion(port('form', 'form'), port('form', 'form'))['conversion_plan']
    assert execute_conversion(original, plan, tmp_path) is original
    assert not list(tmp_path.iterdir())
    assert plan_conversion(port('form', 'form'), port())['status'] == 'incompatible'


def test_native_reader_form_bridge_runs_legacy_operator(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from biopipe_sdk.native_array import NativeArray
    import src.reader as readers
    from src.task import Context, run
    original = form()
    original.data[:] += 1
    payload = NativeArray(original.data, original.dims, original.labels, original.info, original.axis_info)
    reader = SimpleNamespace(parameters_schema={'type': 'object'}, handles_compression=True,
        output_contract={'version': 1, 'numeric': True},
        _declaration={'data_formats': {'outputs': [port('native.ndarray', 'form')]}},
        read=lambda *a, **k: payload)
    monkeypatch.setattr(readers, 'pick_reader', lambda *a: reader)
    loaded = readers.read_source(tmp_path / 'synthetic.native', original.dims, original.labels)
    assert loaded.data is original.data
    assert loaded.axis_info == original.axis_info
    plan = plan_conversion(port('native.ndarray', 'form'), port('form', 'form'))['conversion_plan']
    assert execute_conversion(loaded, plan, tmp_path / 'scratch') is loaded
    ctx = Context(tmp_path / 'task', {})
    ctx['x'] = loaded
    try:
        run(ctx, [{'name': 'log_transform', 'inputs': ['x'], 'params': {'base': 2, 'pseudocount': 1, 'output': 'y'}}])
        np.testing.assert_allclose(ctx['y'].data, np.log2(original.data + 1))
    finally:
        ctx.finalize()


def test_native_bridge_requires_metadata_and_checks_reader_container():
    from biopipe_sdk.native_array import NativeArray, as_form, reader_output
    with pytest.raises(ValueError, match='explicit Form metadata'):
        as_form(np.zeros((2, 2)))
    with pytest.raises(Exception):
        as_form(NativeArray(np.zeros((2, 2)), ['sample'], {}, {}, {}))
    with pytest.raises(ValueError, match='different container'):
        reader_output(object(), {'data_formats': {'outputs': [port('form', 'form')]}})
    assert plan_conversion(port('native.ndarray', 'form'), port(logical_type='list'))['status'] == 'incompatible'


def test_legacy_projection_is_read_only_and_does_not_invent_matrix_semantics():
    from biopipe_sdk.formats import effective_formats
    legacy = {'inputs_arity': 1, 'outputs': ['x'], 'contracts': {'inputs': [{'numeric': True}], 'output': {'mode': 'pca'}}}
    before = deepcopy(legacy)
    assert effective_formats(legacy)['inputs'][0]['logical_type'] == 'form'
    assert effective_formats(legacy)['outputs'][0]['logical_type'] == 'form'
    assert legacy == before
    legacy['contracts']['inputs'] = [{}]
    assert effective_formats(legacy)['inputs'][0]['logical_type'] == 'form'
    legacy['contracts']['inputs'] = [{'kind': ['form', 'file']}]
    assert effective_formats(legacy)['inputs'] == [None]


def test_sdk37_requires_both_arrays_even_for_report():
    from biopipe.packages import bundled_entries
    from biopipe_sdk.protocol import Descriptor
    descriptor = deepcopy(next(d for _, d in bundled_entries('operator') if d['id'] == 'pca'))
    descriptor.update(protocol_revision='3.7', inputs_arity=0, outputs=[], output_parameter=None, data_formats={})
    with pytest.raises(ValueError, match='inputs and outputs'):
        Descriptor.model_validate(descriptor)
    descriptor['data_formats'] = {'inputs': [], 'outputs': []}
    Descriptor.model_validate(descriptor)


def test_real_file_readers_project_file_artifact_not_form():
    from biopipe.packages import bundled_entries
    from biopipe_sdk.formats import effective_formats
    readers = {d['id']: d for _, d in bundled_entries('reader')}
    checked = []
    for name, descriptor in readers.items():
        if descriptor['contracts']['output'].get('kind') == 'file':
            assert effective_formats(descriptor)['outputs'][0]['representations'] == ['file_artifact'], name
            checked.append(name)
    assert 'FastqReader' in checked


@pytest.mark.parametrize('bad_output', [False, True])
def test_direct_runner_checks_declared_input_and_output_containers(tmp_path, monkeypatch, bad_output):
    from src.core import FileArtifact
    from src.task import Context, STEPS, run
    from src.task.step.base import Step
    path = tmp_path / 'data.txt'
    path.write_text('file data')
    artifact = FileArtifact('txt', {'data': str(path)})
    class Declared(Step):
        name = 'declared_guard'
        inputs_arity = 1
        outputs = ['out']
        parameters_schema = {'type': 'object'}
        definition = {'data_formats': {'inputs': [port('form', 'form')], 'outputs': [port('form', 'form')]}}
        def run(self, ctx, inputs):
            ctx['out'] = artifact
    monkeypatch.setitem(STEPS, Declared.name, Declared)
    ctx = Context(tmp_path / 'run', {})
    ctx['in'] = form() if bad_output else artifact
    try:
        with pytest.raises(ValueError, match='different container'):
            run(ctx, [{'name': Declared.name, 'inputs': ['in'], 'params': {}}])
    finally:
        ctx.finalize()


def test_nested_route_preserves_explicit_native_format_boundary(tmp_path):
    from src.web.models import Graph, RouteDefinition
    from src.web.contracts import analyze_graph
    c = catalog()
    c['readers'][0]['data_formats']['outputs'] = [port('form', 'form')]
    c['operators'][0]['data_formats'] = {'inputs': [port('form', 'form')], 'outputs': [port('native.ndarray', 'form')]}
    inner = graph().model_dump(mode='json')
    inner['interface'] = {'version': 1, 'inputs': [{'node_id': 'data', 'label': 'Input', 'contract': {'ndim': 2}}],
                          'outputs': [{'node_id': 'end', 'handle': 'out', 'label': 'Output', 'contract': {'ndim': 2}}]}
    route = RouteDefinition(id='route_012345abcdef', name='Native route', version=1, graph=Graph.model_validate(inner))
    c['operators'].append(dict(id='legacy', title='Legacy', inputs_arity=1, outputs=[], output_parameter=None,
        parameters_schema={'type': 'object'}, runtime_defaults={},
        contracts={'version': 1, 'inputs': [{'numeric': True, 'ndim': 2}], 'output': {'mode': 'report'}}))
    outer = Graph.model_validate({'nodes': [
        graph().model_dump(mode='json')['nodes'][0],
        {'id': 'nested', 'kind': 'route', 'position': {'x': 100, 'y': 0}, 'route': route.model_dump(mode='json')},
        {'id': 'old', 'kind': 'operator', 'operator': 'legacy', 'position': {'x': 200, 'y': 0}}],
        'edges': [{'id': 'before', 'source': 'data', 'target': 'nested'},
                  {'id': 'after', 'source': 'nested', 'sourceHandle': 'out-0', 'target': 'old'}]})
    result = analyze_graph(outer, c, tmp_path)
    boundary = next(e for e in result['edges'] if e['id'] == 'after')
    assert boundary['conversion_plan']['converters'][0]['id'] == 'form.ndarray.wrap'
    assert next(e for e in result['edges'] if e['id'] == 'before')['status'] == 'compatible'


def test_legacy_route_interface_does_not_persist_inferred_formats(tmp_path):
    from src.web.routes import prepare_interface
    c = catalog()
    for descriptor in c['readers'] + c['operators']:
        descriptor.pop('data_formats', None)
    prepared = prepare_interface(graph(), c, tmp_path)
    for boundary in [*prepared.interface.inputs, *prepared.interface.outputs]:
        assert 'data_format' not in boundary.contract
    c = catalog()
    explicit = prepare_interface(graph(), c, tmp_path)
    assert explicit.interface.inputs[0].contract['_format_explicit']
    assert explicit.interface.inputs[0].contract['data_format']


def test_format_value_rejects_rank_and_storage_mismatch(tmp_path):
    from biopipe_sdk.native_array import validate_format_value
    from src.core import FileArtifact
    path = tmp_path / 'data.txt'; path.write_text('x')
    with pytest.raises(ValueError, match='container'):
        validate_format_value(FileArtifact('txt', {'data': str(path)}),
                              {'logical_type': 'form', 'representations': ['form', 'numpy.ndarray']})
    with pytest.raises(ValueError, match='representation|mapped'):
        validate_format_value(form(), port('npy.memmap'))
    vector = Form(np.arange(3.), ['sample'], {'sample': {'a': 0, 'b': 1, 'c': 2}}, {'missing_code': float('nan')})
    with pytest.raises(ValueError, match='logical type'):
        validate_format_value(vector, port())
    with pytest.raises(ValueError, match='metadata'):
        validate_format_value(form(), port('form', 'form', dtype='float64'))


def test_generic_form_identity_keeps_disk_reducer_streaming(tmp_path, monkeypatch):
    from test_memory_runtime import context, events
    from src.task import STEPS, run
    cls = STEPS['describe']
    declaration = deepcopy(getattr(cls, '_declaration', {}))
    declaration['data_formats'] = {'inputs': [port('form', 'form')], 'outputs': []}
    monkeypatch.setattr(cls, '_declaration', declaration, raising=False)
    ctx = context(tmp_path, chunk_mb=.00001)
    ctx['X'] = form()
    ctx.forms.spill(ctx.forms.entry('X'), 'force_disk_stream')
    plan = plan_conversion(port('form', 'form'), port('form', 'form'))['conversion_plan']
    try:
        run(ctx, [{'name': 'describe', 'inputs': ['X'],
                   'conversions': [{'port': 0, 'edge_id': 'identity', 'plan': plan}]}])
    finally:
        ctx.finalize()
    assert ctx.memory.report['plans'][0]['mode'] == 'stream'
    assert not any(event['event'] == 'load' for event in events(ctx))
