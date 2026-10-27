"""Portable stage artifacts preserve metadata without cross-machine pickle."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from biopipe.exchange import export_outputs, register_source
from biopipe.remote.transfers import TransferStore
from src.core import Form
from src.core.files import FileArtifact
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.memory.config import MemoryBudgetError
from src.web.transfers import TransferClient


def form(shape=(3, 4)):
    dims = ['row', 'column'] if len(shape) == 2 else ['axis'+str(i) for i in range(len(shape))]
    return Form(np.arange(np.prod(shape), dtype=np.float64).reshape(shape), dims,
                {dim: {str(i): i for i in range(size)} for dim, size in zip(dims, shape)},
                {'missing_code': np.nan})


def context(path, *, budget=None, outputs=None, inputs=None):
    memory = {'enabled': False} if budget is None else {'enabled': True, 'budget_mb': budget,
                 'chunk_mb': .001, 'io_buffer_kb': 1, 'keep': outputs or []}
    return Context(path, {'runtime': {'memory': memory, 'exchange_outputs': outputs or [],
                                     'exchange_inputs': inputs or []}})


def moved(entry, folder):
    folder.mkdir(parents=True)
    for item in entry['files']:
        shutil.copyfile(item['path'], folder/item['name'])
    return folder/'value.bpform'


def test_form_axis_metadata_encoder_and_hic_files_roundtrip(tmp_path):
    origin = context(tmp_path/'origin', outputs=['analysis'])
    target = context(tmp_path/'target', inputs=['analysis'])
    try:
        source = tmp_path/'expected.tsv'; source.write_text('bin\tvalue\n0\t1\n')
        matrix = form()
        encoder = LabelEncoder(); encoder.fit_transform(['A', 'B'])
        matrix.info.update(encoders={'column': {'0': encoder}}, chrom=np.array(['chr1', 'chr2', 'chr3']),
                           hic_files={'table': str(source)}, hic_fingerprints=FileArtifact('tsv', {'table': str(source)}).fingerprints)
        matrix.axis_info = {'row': ['chrom']}
        origin['analysis'] = matrix
        index = export_outputs(origin)
        packet = moved(index['analysis'], tmp_path/'received')
        serialized = json.loads(packet.read_text(encoding='utf-8'))
        assert serialized['audit'] and not any(item['name'].endswith('.pkl') for item in index['analysis']['files'])
        target.register_source('analysis', {'path': str(packet)})
        result = target['analysis']
        np.testing.assert_array_equal(result.data, matrix.data)
        np.testing.assert_array_equal(result.info['chrom'], matrix.info['chrom'])
        assert result.axis_info == matrix.axis_info
        assert result.info['encoders']['column']['0'].mapping == encoder.mapping
        assert Path(result.info['hic_files']['table']).parent == packet.parent
        assert result.info['hic_files']['table'] != str(source)
        FileArtifact('tsv', result.info['hic_files'], fingerprints=result.info['hic_fingerprints']).validate()
        assert matrix.info['hic_files']['table'] == str(source)
    finally:
        origin.finalize(); target.finalize()


def test_file_artifact_through_verified_transfer_group(tmp_path):
    origin = context(tmp_path/'origin', outputs=['reads'])
    target = context(tmp_path/'target', budget=1, inputs=['reads'])
    try:
        source = tmp_path/'reads.pairs.gz'; source.write_bytes(b'file-backed source'*100)
        origin['reads'] = FileArtifact('pairs', {'pairs': str(source)}, {'sorted': True})
        entry = export_outputs(origin)['reads']
        store = TransferStore(tmp_path/'server', resolve_input=lambda p: Path(p), scan_bytes=4096)
        transfer = TransferClient(store.dispatch, tmp_path/'client', chunk_bytes=1024)
        refs = [{'name': item['name'], 'reference': transfer.upload(item['path'])} for item in entry['files']]
        group = transfer.materialize(refs)
        target.register_source('reads', {'path': group['paths']['value.bpform']})
        assert target.forms.entry('reads').form is None
        result = target['reads']
        assert isinstance(result, FileArtifact) and result.info['sorted']
        assert Path(result.files['pairs']).read_bytes() == source.read_bytes()
        assert Path(result.files['pairs']).parent == Path(group['path'])
    finally:
        origin.finalize(); target.finalize()


def test_managed_disk_export_does_not_load_the_matrix(tmp_path, monkeypatch):
    origin = context(tmp_path/'origin', budget=2, outputs=['matrix'])
    target = context(tmp_path/'target', budget=.1, inputs=['matrix'])
    try:
        matrix = form((128, 128))
        origin['matrix'] = matrix
        entry = origin.forms.entry('matrix')
        origin.forms.spill(entry, 'test')
        assert entry.form is None
        def forbidden(*args, **kwargs): raise AssertionError('Export performed full mode load')
        monkeypatch.setattr(origin.forms, '_load', forbidden)
        exported = export_outputs(origin)['matrix']
        assert entry.form is None
        packet = moved(exported, tmp_path/'received')
        target.register_source('matrix', {'path': str(packet)})
        imported = target.forms.entry('matrix')
        assert imported.form is None and imported.disk_loader is not None
        target.forms.stage_source(imported)
        assert imported.form is None and imported.disk is not None
        restored = np.load(imported.disk/'data.npy', mmap_mode='r', allow_pickle=False)
        np.testing.assert_array_equal(restored, matrix.data)
        with pytest.raises(MemoryBudgetError): target['matrix']
    finally:
        origin.finalize(); target.finalize()


def test_unstaged_source_is_exported_via_disk_loader(tmp_path):
    origin = context(tmp_path/'origin', budget=.1, outputs=['matrix'])
    try:
        matrix = form((128, 128))
        def forbidden(): raise AssertionError('Unexpected eager reader')
        def disk_loader(writer, chunk):
            for row in range(128): writer.write(row, 0, matrix.data[row])
            return {key: getattr(matrix, key) for key in ('dims', 'labels', 'info', 'axis_info')}
        origin.forms.register_source('matrix', forbidden, tmp_path/'virtual',
            {'shape': [128, 128], 'dtype': 'float64', 'dense_bytes': matrix.data.nbytes}, disk_loader)
        result = export_outputs(origin)
        assert result['matrix']['contract']['dims'] == ['row', 'column']
        assert origin.forms.entry('matrix').form is None
    finally:
        origin.finalize()


def test_non_2d_source_requires_full_admission(tmp_path):
    origin = context(tmp_path/'origin', outputs=['cube'])
    target = context(tmp_path/'target', budget=.06, inputs=['cube'])
    try:
        origin['cube'] = form((32, 32, 32))
        packet = moved(export_outputs(origin)['cube'], tmp_path/'received')
        target.register_source('cube', {'path': str(packet)})
        assert target.forms.entry('cube').disk_loader is None
        with pytest.raises(MemoryBudgetError): target['cube']
    finally:
        origin.finalize(); target.finalize()


def test_route_output_alias_and_ordinary_path_metadata(tmp_path):
    origin = context(tmp_path/'origin', outputs=['expanded_inner_result', 'other'])
    target = context(tmp_path/'target', inputs=['route_result'])
    try:
        origin.manifest['runtime']['exchange_aliases'] = {'route_result': 'expanded_inner_result'}
        matrix = form()
        historical = tmp_path/'old-machine-output'/'directory-that-does-not-exist'
        matrix.info['historical_directory'] = historical
        origin['expanded_inner_result'] = matrix
        origin['other'] = form()
        exported = export_outputs(origin)
        assert exported['route_result'] == exported['expanded_inner_result']
        assert 'other' in exported
        assert not any(item['name'].startswith('blob-') for item in exported['route_result']['files'])
        index = json.loads((origin.out_dir/'exchange.json').read_text(encoding='utf-8'))
        assert index['route_result']['path'] == exported['route_result']['path']
        packet = moved(exported['route_result'], tmp_path/'received')
        target.register_source('route_result', {'path': str(packet)})
        assert target['route_result'].info['historical_directory'] == historical
        assert not historical.exists()
    finally:
        origin.finalize(); target.finalize()


def test_packet_traversal_absolute_file_reference_and_mutation_fail(tmp_path):
    origin = context(tmp_path/'origin', outputs=['matrix'])
    target = context(tmp_path/'target', budget=1, inputs=['matrix'])
    try:
        origin['matrix'] = form()
        exported = export_outputs(origin)['matrix']
        packet = moved(exported, tmp_path/'received')
        original = json.loads(packet.read_text(encoding='utf-8'))
        bad = deepcopy(original)
        data = next(item[1] for item in bad['value']['value']['items'] if item[0] == 'data')
        data['file'] = '../escape.npy'
        packet.write_text(json.dumps(bad), encoding='utf-8')
        with pytest.raises(ValueError, match='basenames'): target.register_source('matrix', {'path': str(packet)})
        packet.write_text(json.dumps(original), encoding='utf-8')
        target.register_source('matrix', {'path': str(packet)})
        packet.write_text(json.dumps(original)+' ', encoding='utf-8')
        with pytest.raises(ValueError, match='changed'): target['matrix']
        external = tmp_path/'outside'; external.write_bytes(b'not owned by the packet')
        malicious = {'version': 1, 'value': {'type': 'file_artifact', 'value': {'type': 'dict', 'items': [
            ['format', 'pairs'], ['files', {'type': 'dict', 'items': [['pairs', str(external)]]}],
            ['info', {'type': 'dict', 'items': []}], ['fingerprints', {'type': 'dict', 'items': []}]]}}}
        packet.write_text(json.dumps(malicious), encoding='utf-8')
        register_source(target, 'files', packet)
        with pytest.raises(ValueError, match='outside'): target['files']
    finally:
        origin.finalize(); target.finalize()
