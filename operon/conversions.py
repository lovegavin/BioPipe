"""Bounded, fail-closed representation planning and execution.

Registry discovery reads data only; scientific imports happen only at execution.
"""
from copy import deepcopy
import hashlib
import heapq
import json
from pathlib import Path
import shutil
import uuid

from operon_sdk.formats import Adaptation, FormatPort


def converter_registry():
    source = Path(__file__).with_name('converter_kernels.py')
    identity = hashlib.sha256(source.read_bytes()).hexdigest()
    entries = [dict(id=key, version='1.0.0', code_sha=identity, logical_type='matrix',
                 source=before, target=after, lossless=True, cost=cost,
                 dependencies=['numpy>=1.26'], portable={'module': 'converter_kernels.py', 'function': function})
            for key, before, after, cost, function in [
                ('matrix.npy.write', 'numpy.ndarray', 'npy.memmap', 10, 'array_to_npy'),
                ('matrix.npy.view', 'npy.memmap', 'numpy.ndarray', 1, 'mmap_to_array')]]
    from operon_sdk import native_array
    entries.append(dict(id='form.ndarray.wrap', version='1.0.0',
        code_sha=hashlib.sha256(Path(native_array.__file__).read_bytes()).hexdigest(),
        logical_type='form', source='native.ndarray', target='form', lossless=True,
        cost=1, dependencies=['numpy>=1.26']))
    return entries


def plan_conversion(source, target, policy=None, *, registry=None):
    """Return a plan or a typed diagnostic, without reading any source payload."""
    policy = Adaptation.model_validate(policy or {}).model_dump()
    def result(status, reason=None, chain=(), representation=None):
        value = {'status': status, 'reasons': [reason] if reason else []}
        if source and target:
            value['conversion_plan'] = {'logical_type': source['logical_type'],
                'source': deepcopy(source), 'target': deepcopy(target),
                'representation': representation, 'converters': deepcopy(list(chain))}
        return value
    if source is None and target is None:
        if policy['mode'] == 'fixed':
            return result('unknown', 'Fixed adaptation requires declared data_formats on both ports')
        return result('compatible')  # Old v3/v3.5 path, not an inferred format.
    if source is None or target is None:
        return result('unknown', 'Both ports must declare data_formats before format adaptation')
    source = FormatPort.model_validate(source).model_dump()
    target = FormatPort.model_validate(target).model_dump()
    if source['logical_type'] != target['logical_type']:
        return result('incompatible', f"Logical type {source['logical_type']} cannot feed {target['logical_type']}; insert an explicit scientific conversion operator")
    for key, value in target['metadata'].items():
        if key not in source['metadata']:
            return result('unknown', f'Missing logical metadata: {key}')
        if source['metadata'][key] != value:
            return result('incompatible', f'Logical metadata differs: {key}; insert an explicit operator')
    # Outputs describe the actual representation, not a menu to demand from code.
    if len(source['representations']) != 1:
        return result('unknown', 'Output must resolve to one actual representation before execution')
    initial = source['representations'][0]
    if policy['mode'] != 'fixed' and initial in target['representations']:
        return result('compatible', representation=initial)
    if policy['mode'] == 'disabled':
        return result('incompatible', 'Representation mismatch; automatic adaptation is disabled')
    converters = converter_registry() if registry is None else registry
    valid = sorted((d for d in converters if d.get('lossless') is True and
                    d.get('logical_type') == source['logical_type']), key=lambda d: d['id'])
    if len(valid) > 128:
        return result('incompatible', 'Converter candidate limit exceeded')
    queue = [(0, (), initial, (), (initial,))]
    visited = 0
    while queue and visited < 256:
        cost, ids, current, chain, representations = heapq.heappop(queue)
        visited += 1
        if current in target['representations'] and (policy['mode'] != 'fixed' or list(ids) == policy['converters']):
            return result('compatible', chain=chain, representation=current)
        if len(chain) >= 4:
            continue
        for item in valid:
            if item['source'] != current or item['target'] in representations:
                continue
            if policy['mode'] == 'fixed' and (len(ids) >= len(policy['converters']) or item['id'] != policy['converters'][len(ids)]):
                continue
            heapq.heappush(queue, (cost + max(0, item.get('cost', 1)), (*ids, item['id']),
                                  item['target'], (*chain, item), (*representations, item['target'])))
    return result('incompatible', 'No verified lossless converter chain satisfies these ports')


def execute_conversion(form, plan, directory, *, buffer_bytes=65536, admit=None, checkpoint=lambda: None):
    """Preserve Form metadata; convert only the numeric data representation."""
    import numpy as np
    from src.core import Form, FileArtifact
    from .converter_kernels import array_to_npy, mmap_to_array
    declared = plan['source']['representations'][0]
    if declared == 'native.ndarray':
        from operon_sdk.native_array import as_form
        form = as_form(form)
    if declared == 'form' and not isinstance(form, Form):
        raise ValueError('Declared Form representation requires an actual Form')
    if declared == 'file_artifact' and not isinstance(form, FileArtifact):
        raise ValueError('Declared file_artifact requires an actual FileArtifact')
    form.validate()
    if plan['logical_type'] == 'matrix' and (not isinstance(form, Form) or form.data.ndim != 2):
        raise ValueError('Matrix conversion requires an actual two-dimensional Form')
    if plan['logical_type'] == 'list' and isinstance(form, Form) and form.data.ndim != 1:
        raise ValueError('A matrix is not a logical list; insert an explicit operator')
    if declared not in {'form', 'native.ndarray'} and isinstance(form, Form) and form.data.dtype.hasobject:
        raise ValueError('Object arrays cannot be automatically converted')
    actual = ('npy.memmap' if isinstance(form.data, np.memmap) else 'numpy.ndarray') if isinstance(form, Form) else form.info.get('representation')
    if declared == 'form' and isinstance(form, Form):
        actual = 'form'
    elif declared == 'file_artifact' and isinstance(form, FileArtifact):
        actual = 'file_artifact'
    elif declared == 'native.ndarray' and isinstance(form, Form):
        actual = 'native.ndarray'
    # A managed spill may have materialized an ndarray as a memmap already.
    if actual not in {declared, 'npy.memmap'}:
        raise ValueError('Runtime representation differs from the frozen source declaration')
    registry = {d['id']: d for d in converter_registry()}
    current = declared
    for step in plan['converters']:
        if registry.get(step['id']) != step:
            raise ValueError('Converter implementation changed; revalidate the workflow')
        if step['source'] != current or step['logical_type'] != plan['logical_type']:
            raise ValueError('Invalid frozen converter chain')
        current = step['target']
    target = plan['representation']
    if target != current or target not in plan['target']['representations']:
        raise ValueError('Invalid frozen conversion target')
    metadata = {**plan['source'].get('metadata', {}), **plan['target'].get('metadata', {})}
    for key, value in metadata.items():
        observed = ({'dims': form.dims, 'dtype': str(form.data.dtype), 'shape': list(form.data.shape)}.get(key, form.info.get(key))
                    if isinstance(form, Form) else form.info.get(key))
        if observed != value:
            raise ValueError(f'Runtime logical metadata mismatch: {key}')
    if actual == target:
        return form
    if target == 'form' and actual == 'native.ndarray':
        return form
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if target == 'npy.memmap':
        path = directory / (uuid.uuid4().hex + '.npy')
        needed = int(form.data.nbytes) + 4096
        if admit:
            admit(needed)
        if shutil.disk_usage(directory).free < needed:
            raise OSError('Insufficient conversion scratch space')
        data = array_to_npy(form.data, path, buffer_bytes=buffer_bytes, checkpoint=checkpoint)
    elif target == 'numpy.ndarray':
        data = mmap_to_array(form.data)
    else:
        raise ValueError('Frozen converter has no executable implementation')
    # The data remains readonly and metadata is not reinterpreted or truncated.
    return Form(data, list(form.dims), {k: dict(v) for k, v in form.labels.items()},
                dict(form.info), {k: list(v) for k, v in form.axis_info.items()})


def apply_step_conversions(ctx, forms, plans):
    """Integrate conversion scratch and buffers with the existing memory owner."""
    memory = ctx.memory
    folder = (memory.store.cache_root if memory else ctx.out_dir) / 'conversions'
    for spec in plans:
        port, plan = spec['port'], spec['plan']
        if not 0 <= port < len(forms):
            raise ValueError('Conversion references an unavailable input')
        before = sum(p.stat().st_size for p in folder.glob('*.npy')) if folder.exists() else 0
        buffer = min(memory.config.io_buffer_bytes, max(1, memory.config.budget_bytes // 8)) if memory else 65536
        reserved = 0
        def checkpoint():
            if (ctx.task_dir / 'cancel.requested').exists():
                raise RuntimeError('Conversion cancelled')
            if memory:
                memory._barrier()
        def admit(count):
            if memory:
                from src.task.memory.config import DiskBudgetError
                store = memory.store
                with store.lock:
                    limit = memory.config.disk_limit_bytes
                    if limit is not None and store.disk_bytes + store.staging_disk_bytes + store.transport_disk_bytes + count > limit:
                        raise DiskBudgetError('Format conversion exceeds the run disk quota')
        try:
            if memory and any(c['id'] == 'matrix.npy.write' for c in plan['converters']):
                with memory.store.lock:
                    memory.store.ensure(2 * buffer, 'conversion_buffer')
                    memory.store.reserved += 2 * buffer
                    reserved = 2 * buffer
            ctx.event('conversion_started', edge=spec['edge_id'], converters=[c['id'] for c in plan['converters']])
            forms[port] = execute_conversion(forms[port], plan, folder, buffer_bytes=buffer,
                                              admit=admit, checkpoint=checkpoint)
            ctx.event('conversion_finished', edge=spec['edge_id'], representation=plan['representation'])
        finally:
            if memory:
                memory.store.reserved -= reserved
                after = sum(p.stat().st_size for p in folder.glob('*.npy')) if folder.exists() else 0
                memory.store.disk_bytes += after - before
    return forms
