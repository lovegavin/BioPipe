"""Library-only exports exercised against source and released application runtimes."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError, ValidationError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.export_results import ExportResultsStep, native_results, write_array


def matrix(data=None):
    data = np.arange(6).reshape(3, 2) if data is None else data
    return Form(data, ['sample', 'feature'],
                {'sample': {'third': 2, 'one,quoted': 0, 'second': 1},
                 'feature': {'b': 1, 'a': 0}})


@pytest.fixture
def ctx(tmp_path):
    context = Context(tmp_path / 'task', {})
    yield context
    context.finalize()


def export(ctx, value, **params):
    ctx.step_params = {'output': 'saved', **params}
    step = ExportResultsStep()
    step.run(ctx, [value])
    return ctx['saved']


@pytest.mark.parametrize('format,delimiter', [('csv', ','), ('tsv', '\t')])
def test_table_labels_and_original_unchanged(ctx, format, delimiter):
    form = matrix()
    original = form.data.copy()
    artifact = export(ctx, form, format=format)
    with open(artifact.files['data'], newline='', encoding='utf-8') as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))
    assert rows == [['sample', 'a', 'b'], ['one,quoted', '0', '1'],
                    ['second', '2', '3'], ['third', '4', '5']]
    np.testing.assert_array_equal(form.data, original)
    artifact = export(ctx, form, format=format, include_labels=False)
    with open(artifact.files['data'], newline='', encoding='utf-8') as handle:
        assert next(csv.reader(handle, delimiter=delimiter)) == ['0', '1']


@pytest.mark.parametrize('array', [np.arange(120, dtype='>i4').reshape(4, 5, 6)[:, ::2, ::-1],
                                 np.zeros((0, 3), dtype='float32'),
                                 np.array(3.5), np.array(['aa', 'b']),
                                 np.array([(1, 2.)], dtype=[('x', 'i4'), ('y', 'f8')])])
def test_npy_dtype_shape_and_strides(tmp_path, array):
    path = tmp_path / 'out.npy'
    write_array(path, array, 32)
    actual = np.load(path, allow_pickle=False)
    assert actual.dtype == array.dtype and actual.shape == array.shape
    np.testing.assert_array_equal(actual, array)


def test_memmap_npy_export(tmp_path):
    data = np.lib.format.open_memmap(tmp_path / 'source.npy', mode='w+', dtype='float32', shape=(1024, 256))
    data[:] = np.arange(256)
    write_array(tmp_path / 'saved.npy', data[:, ::2], 4096)
    np.testing.assert_array_equal(np.load(tmp_path / 'saved.npy'), data[:, ::2])
    del data


def test_fasta_subset_and_chains(ctx):
    form = matrix()
    form.info = {'sequences': ['ACD/EFG', 'HIK', 'LMN']}
    form.axis_info = {'sample': ['sequences']}
    selected = form.subset_axis('sample', [2, 0])
    artifact = export(ctx, selected, format='fasta')
    assert Path(artifact.files['data']).read_text() == '>third\nLMN\n>one,quoted|chain=1\nACD\n>one,quoted|chain=2\nEFG\n'


@pytest.mark.parametrize('bad', ['../escape', 'a/b', 'a\\b', 'C:bad', 'CON', 'bad.', 'a\n'])
def test_bad_names(ctx, bad):
    with pytest.raises(StepError, match='basename'):
        export(ctx, matrix(), filename=bad)
    assert not ctx.has('saved')


@pytest.mark.parametrize('format', ['native', 'pdb', 'cif'])
def test_cannot_invent_original_files(ctx, format):
    with pytest.raises(StepError, match='no matching original'):
        export(ctx, matrix(), format=format)
    assert not ctx.has('saved')


def test_failed_conversion_cleans_partial(ctx):
    form = matrix()
    form.info = {'sequences': ['ACD', 'not a sequence', 'HI']}
    with pytest.raises(StepError, match='FASTA'):
        export(ctx, form, format='fasta')
    assert not ctx.has('saved')
    assert not list(ctx.out_dir.rglob('*.part'))
    assert not list(ctx.out_dir.rglob('*.fasta'))
    with pytest.raises(StepError, match='count'):
        form.info['sequences'] = ['ACD']
        export(ctx, form, format='fasta')
    with pytest.raises(StepError, match='object'):
        write_array(ctx.out_dir / 'unsafe.npy', np.array([object()], dtype=object), 100)


def test_native_reuse_and_external_copy(ctx, tmp_path, monkeypatch):
    path = ctx.artifact_path('original/design.pdb')
    path.write_bytes(b'HEADER synthetic\nEND\n')
    native = FileArtifact('pdb', {'structure': str(path)})
    import shutil
    with monkeypatch.context() as patch:
        patch.setattr(shutil, 'copyfile', lambda *a, **k: pytest.fail('same-task native file must not be copied'))
        saved = export(ctx, native, format='pdb')
    assert list(saved.files.values()) == [str(path)]
    assert saved.info['reused_roles'] == ['file_1']
    external = tmp_path / 'external.cif'
    external.write_bytes(b'data_synthetic\n')
    saved = export(ctx, FileArtifact('mmcif', {'structure': str(external)}), format='cif')
    copy = Path(next(iter(saved.files.values())))
    assert copy != external and copy.is_relative_to(ctx.out_dir)
    assert copy.read_bytes() == external.read_bytes() and external.exists()
    renamed = export(ctx, native, format='native', filename='renamed')
    assert Path(renamed.files['file_1']).name == 'renamed.pdb'
    path.write_bytes(b'changed original')
    with pytest.raises(ValidationError, match='changed'):
        export(ctx, native)


def test_latest_producer_only_and_report_fallback(ctx):
    path = ctx.artifact_path('native.fasta')
    path.write_text('>one\nACD\n')
    report = ctx.out_dir / 'producer.json'
    files = [{'path': str(path), 'format': 'fasta'}]
    report.write_text(json.dumps({'result_files': files}), encoding='utf-8')
    ctx.artifacts['exports'] = [{'index': 1, 'elapsed': 0, 'name': 'proteinmpnn_design',
                                'params': {'output': 'designs'}, 'export_path': 'producer.json'}]
    assert native_results(ctx, 'designs') == files  # isolated-worker fallback
    saved = export(ctx, matrix(), format='fasta', _input_names=['designs'])
    assert saved.files['file_1'] == str(path)
    # A transform reusing the same logical output name must invalidate attribution.
    (ctx.out_dir / 'transform.json').write_text('{}')
    ctx.artifacts['exports'].append({'index': 2, 'elapsed': 0, 'name': 'pca', 'params': {'output': 'designs'},
                                    'export_path': 'transform.json'})
    ctx.artifacts['native_results'] = {'designs': {'index': 1, 'files': files}}
    assert native_results(ctx, 'designs') == []


def test_reject_external_producer_reference(ctx, tmp_path):
    external = tmp_path / 'outside.pdb'
    external.write_text('END')
    ctx.artifacts['exports'] = [{'index': 1, 'elapsed': 0, 'name': 'rfdiffusion_design',
                                'params': {'output': 'designs'}, 'export_path': 'unused.json'}]
    ctx.artifacts['native_results'] = {'designs': {'index': 1, 'files': [{'path': str(external), 'format': 'pdb'}]}}
    with pytest.raises(StepError, match='escapes'):
        export(ctx, matrix(), format='pdb', _input_names=['designs'])


def test_managed_branch_continues_and_existing_viewer_opens_files(tmp_path):
    from src.web.service import JobService
    root = tmp_path / 'workspace'
    task = root / '.studio/jobs/branch'
    steps = [{'name': 'export_results', 'inputs': ['X'], 'params': {'output': 'saved', 'format': 'csv'}},
             {'name': 'describe', 'inputs': ['X']}]
    ctx = Context(task, {'steps': steps, 'runtime': {'memory': {'budget_mb': 32, 'chunk_mb': .01}}})
    try:
        ctx['X'] = matrix()
        run(ctx, steps)
        assert [entry['name'] for entry in ctx.artifacts['exports']] == ['export_results', 'describe']
        saved = ctx['saved']
        assert isinstance(saved, FileArtifact)
        path = Path(saved.files['data'])
        assert path.is_file()
    finally:
        ctx.finalize()
    manifest = task / 'export.files.json'
    manifest.write_text(json.dumps(saved.to_dict()), encoding='utf-8')
    service = JobService.__new__(JobService)
    service.root, service.jobs_dir = root, root / '.studio/jobs'
    service.details = lambda key: {'summary': {'task_dir': str(task)}}
    service.artifact = lambda key, identifier: (manifest, {'kind': 'file'})
    assert service.preview('branch', 'saved')['files'][0]['downloadable']
    assert service.artifact_file('branch', 'saved', 'data') == path
