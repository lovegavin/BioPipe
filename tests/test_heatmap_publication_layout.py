"""Heatmap raster size follows publication dimensions, not matrix width."""
from types import SimpleNamespace
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from src.core import Form
from src.task.step.steps.heatmap import HeatmapStep


@pytest.mark.parametrize('columns,width,height', [(500, 90, 70), (1500, 180, 120)])
def test_heatmap_keeps_cells_but_bounds_page_size(tmp_path, columns, width, height):
    values = np.arange(30 * columns, dtype=np.float32).reshape(30, columns)
    form = Form(values, ['feature', 'sample'],
        {'feature': {f'f{i}': i for i in range(30)}, 'sample': {f's{i}': i for i in range(columns)}}, {})
    ctx = SimpleNamespace(memory=None, out_dir=tmp_path, metadata={}, step_params={
        'dim': 'feature', 'other_dim': 'sample', 'select': 'all',
        'standardize': 'none', 'cluster_rows': False, 'cluster_cols': False,
        'show_col_labels': False, 'show_row_labels': False,
        'figure_width_mm': width, 'figure_height_mm': height, 'figure_dpi': 150,
        'filename': 'heatmap.png'})
    operator = HeatmapStep()
    operator.run(ctx, [form])
    report = operator.export(ctx)
    assert report['n_rows'] == 30 and report['n_cols'] == columns
    assert {item['format'] for item in report['figures']} == {'png', 'pdf', 'svg'}
    assert all(Path(item['path']).is_file() for item in report['figures'])
    with Image.open(report['path']) as image:
        assert image.size == (int(width / 25.4 * 150), int(height / 25.4 * 150))
