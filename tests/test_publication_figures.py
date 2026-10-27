"""Saved publication outputs contain full plot data, not the UI sample."""
import json
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import matplotlib
import numpy as np
from PIL import Image
import pytest

from src.core import Form
from src.task.step.steps._plot_helpers import setup_style, save_figure, figure_report, plt
from src.task.step.steps.scatter import ScatterStep


def context(tmp_path, **params):
    return SimpleNamespace(memory=None, out_dir=tmp_path, metadata={}, step_params=params)


def test_publication_files_are_saved_with_physical_size_white_background_and_editable_text(tmp_path):
    ctx = context(tmp_path, figure_width_mm=90, figure_height_mm=70, figure_dpi=300, figure_font_size=8)
    with plt.style.context('dark_background'):
        setup_style(ctx)
        fig, ax = plt.subplots()
        ax.plot([0,1,2], [1,3,2], label='Control')
        ax.set(xlabel='Time (h)', ylabel='Expression')
        ax.legend()
        path = save_figure(fig, ctx, 'expression.png')
    report = figure_report({'path':path})
    assert {f['format'] for f in report['figures']} == {'png','pdf','svg'}
    with Image.open(path) as image:
        assert image.size == (int(90/25.4*300), int(70/25.4*300))
        assert image.convert('RGB').getpixel((0,0)) == (255,255,255)
        assert image.info['dpi'][0] == pytest.approx(300, abs=.1)
    pdf = Path(path).with_suffix('.pdf').read_bytes()
    assert pdf.startswith(b'%PDF') and b'/FontFile2' in pdf
    svg = ET.parse(Path(path).with_suffix('.svg'))
    ns = {'s':'http://www.w3.org/2000/svg'}
    labels = [node.text for node in svg.findall('.//s:text', ns)]
    assert 'Time (h)' in labels and 'Expression' in labels and 'Control' in labels
    assert float(svg.getroot().get('width').removesuffix('pt')) == pytest.approx(90/25.4*72, abs=.01)
    assert not plt.fignum_exists(fig.number)


def test_scatter_uses_all_observations_and_collision_does_not_replace_previous_outputs(tmp_path):
    rng = np.random.default_rng(42)
    values = rng.normal(size=(501,2))
    form = Form(values, ['sample','component'],
                {'sample':{f's{i}':i for i in range(501)}, 'component':{'PC1':0,'PC2':1}}, {})
    ctx = context(tmp_path, dim='component', x_label='PC1', y_label='PC2', filename='scores.PDF')
    operator = ScatterStep(); operator.run(ctx, [form]); report = operator.export(ctx)
    assert report['n_points'] == 501 and report['filename'] == 'scores.pdf'
    before = {item['path']:Path(item['path']).read_bytes() for item in report['figures']}
    operator.run(ctx, [form]); second = operator.export(ctx)
    assert second['path'] != report['path']
    assert all(Path(path).read_bytes() == payload for path,payload in before.items())
    assert all(Path(item['path']).is_file() for item in second['figures'])


def test_output_path_stays_in_run_and_invalid_name_closes_figure(tmp_path):
    ctx = context(tmp_path)
    for name in ['../escape.png', 'not-an-image.html']:
        fig, _ = plt.subplots()
        with pytest.raises(ValueError): save_figure(fig, ctx, name)
        assert not plt.fignum_exists(fig.number)


def test_enrichment_legacy_field_is_exposed_as_saved_figure(tmp_path):
    ctx = context(tmp_path); setup_style(ctx)
    fig, _ = plt.subplots()
    path = save_figure(fig, ctx, 'enrichment.png')
    report = figure_report({'figure_path':path, 'n_plotted':4})
    assert report['path'] == path and len(report['figures']) == 3 and report['n_plotted'] == 4
