"""Example adapters exercise real contracts and managed memory, not just imports."""
import json
from pathlib import Path

import numpy as np
from biopipe_sdk import Context, Form
from biopipe_sdk.declarations import bind_class, for_class
from biopipe_sdk.protocol import validate_parameters
from biopipe.parameter_values import split_task, restore_task
from src.task import STEPS, run


def test_volcano_collection_runs_with_memory_and_frozen_values(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'examples/plotting_plugin'))
    from biopipe_plot_examples.volcano import Volcano
    cls = bind_class(Volcano, for_class(Volcano))
    monkeypatch.setitem(STEPS, cls.name, cls)
    values = validate_parameters(cls.parameters_schema, {'fdr': .01, 'figure_width_mm': 95})
    spec = {'name': cls.name, 'inputs': ['x'], 'params': values}
    topology, snapshot = split_task({'sources': {}, 'steps': [spec],
                                     'runtime': {'memory': {'budget_mb': 128}}})
    cls.parameters_schema['properties']['fdr']['default'] = .2
    manifest = restore_task(topology, snapshot)
    ctx = Context(tmp_path, manifest)
    try:
        data = np.column_stack([np.linspace(-3, 3, 25), np.linspace(.001, .2, 25)])
        ctx['x'] = Form(data, ['feature', 'stat'],
                        {'feature': {f'g{i}': i for i in range(25)}, 'stat': {'log2FC': 0, 'padj': 1}})
        run(ctx, manifest['steps'])
        assert ctx.step_params['fdr'] == .01
        report = json.loads((ctx.out_dir / ctx.artifacts['exports'][0]['export_path']).read_text())
        assert len(report['figures']) == 6
        assert {f['id'] for f in report['figures']} == {'volcano', 'distribution'}
        assert all(f['width_mm'] == 95 and Path(f['path']).is_file() for f in report['figures'])
        assert ctx.memory is not None
    finally:
        ctx.finalize()


def test_r_domain_example_has_static_v3_declaration_and_separate_schema(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'examples/plotting_plugin'))
    from biopipe_plot_examples.complex_heatmap import ComplexHeatmap
    descriptor = for_class(ComplexHeatmap)
    cls = bind_class(ComplexHeatmap, descriptor)
    assert descriptor['protocol_version'] == 3
    assert descriptor['resources']['r']['packages'][0]['name'] == 'ComplexHeatmap'
    assert not cls.supports_streaming
    assert cls.parameters_schema['properties']['top_n']['default'] == 50
