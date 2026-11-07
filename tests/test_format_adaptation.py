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
