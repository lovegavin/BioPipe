"""Long logical job paths retain streaming, frozen values and portable outputs."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from operon.bytecode import io_path
from operon.parameter_values import read_values, split_task
from operon.wire import Wire
from src.core import ContextError, FileArtifact, Form
from src.task import Context, load_manifest, run
from src.web.storage import atomic_json


def deep_directory(root):
    path = root
    while len(str(path.resolve())) < 280:
        path /= 'nested-job-' + 'x' * 35
    return path


def test_deep_job_frozen_values_stream_spill_mmap_exchange_and_logs(tmp_path):
    directory = deep_directory(tmp_path)
    manifest = {'params': {'frozen_value': 42}, 'sources': {},
                'steps': [{'name': 'describe', 'inputs': ['X'], 'params': {}}],
                'runtime': {'memory': {'budget_mb': 2, 'chunk_mb': .0001, 'keep': ['X']},
                            'exchange_outputs': ['X']}}
    topology, values = split_task(manifest)
    atomic_json(directory / 'parameters.json', values)
    io_path(directory / 'task.yaml').write_text(yaml.safe_dump(topology), encoding='utf-8')
    loaded = load_manifest(directory / 'task.yaml')
    assert loaded['params'] == {'frozen_value': 42}
    with pytest.raises(ValueError, match='stay inside'):
        read_values(directory, '../outside.json')

    original = np.arange(48, dtype=np.float64).reshape(12, 4)
    metadata = {'dims': ['sample', 'feature'],
                'labels': {'sample': {str(i): i for i in range(12)}, 'feature': {str(i): i for i in range(4)}},
                'info': {'pos': np.arange(12)}, 'axis_info': {'sample': ['pos']}}
    ctx = Context(directory, loaded)
    try:
        ctx['X'] = Form(original, **metadata)
        entry = ctx.forms.entry('X')
        ctx.forms.spill(entry, 'deep_path_regression')
        assert entry.disk.parent == ctx.forms.cache_root
        mapped = ctx.forms.read_metadata(entry, mmap=True)
        assert isinstance(mapped['info']['pos'], np.memmap)
        np.testing.assert_array_equal(mapped['info']['pos'], metadata['info']['pos'])
        mapped['info']['pos']._mmap.close()
        run(ctx, loaded['steps'])
        assert entry.form is None
        from operon.exchange import export_outputs
        exported = export_outputs(ctx)['X']
        assert Path(exported['path']).is_relative_to(ctx.out_dir)
        assert all(not item['path'].startswith('\\\\?\\') for item in exported['files'])
        # The loader stages into a second deep cache using DenseDiskWriter.
        target = Context(directory / 'received', {'runtime': {'memory': {'budget_mb': 2}, 'exchange_inputs': ['X']}})
        try:
            target.register_source('X', {'path': exported['path']})
            staged = target.forms.entry('X')
            target.forms.stage_source(staged)
            assert staged.form is None and staged.disk.parent == target.forms.cache_root
            np.testing.assert_array_equal(target['X'].data, original)
        finally:
            target.finalize()
        with pytest.raises(ContextError, match='outside'):
            ctx.forms._delete_folder(tmp_path)
    finally:
        ctx.finalize()
    summary = json.loads(io_path(ctx.out_dir / 'run_summary.json').read_text())
    report = json.loads(io_path(summary['memory_report']).read_text())
    assert report['status'] == 'complete'
    assert report['plans'][0]['mode'] == 'stream'
    assert not summary['memory_report'].startswith('\\\\?\\')
    output = json.loads(io_path(ctx.out_dir / summary['steps'][0]['export_path']).read_text())
    assert output['global']['mean'] == pytest.approx(original.mean())
    assert io_path(ctx.memory.event_path).read_text(encoding='utf-8').strip()


def test_deep_wire_file_artifacts_and_memory_maps_keep_logical_references(tmp_path):
    directory = deep_directory(tmp_path)
    io_path(directory).mkdir(parents=True)
    source = directory / 'input.pairs'
    io_path(source).write_text('synthetic pairs', encoding='utf-8')
    original = {'file': FileArtifact('pairs', {'data': str(source)}), 'array': np.arange(24).reshape(6, 4)}
    wire = Wire(directory)
    wire.write('request.json', original)
    restored = wire.read('request.json', mmap=True)
    assert restored['file'].files == {'data': str(source)}
    assert isinstance(restored['array'], np.memmap)
    np.testing.assert_array_equal(restored['array'], original['array'])
    restored['array']._mmap.close()
    assert wire.directory == directory.resolve()
    with pytest.raises(ValueError, match='Invalid IPC'):
        wire.path('../outside.npy')


def test_deep_publication_outputs_and_native_alias_registration(tmp_path):
    from operon_sdk.figures import register_figure, save_matplotlib
    from src.task.step.steps._plot_helpers import plt
    directory = deep_directory(tmp_path)
    ctx = SimpleNamespace(memory=None, out_dir=directory, metadata={}, step_params={'figure_width_mm': 60, 'figure_dpi': 100})
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [1, 3, 2])
    report = save_matplotlib(ctx, fig, 'plot.png', figure_id='plot')
    assert {item['format'] for item in report['figures']} == {'png', 'pdf', 'svg'}
    for item in report['figures']:
        assert Path(item['path']).is_relative_to(directory)
        assert io_path(item['path']).stat().st_size > 100
    image = Path(report['figures'][0]['path'])
    aliased = register_figure(ctx, 'alias', {image.suffix[1:]: io_path(image)})
    assert aliased['figures'][0]['path'] == str(image)
    with pytest.raises(ValueError, match='inside'):
        register_figure(SimpleNamespace(out_dir=tmp_path / 'other'), 'outside', {'png': image})
