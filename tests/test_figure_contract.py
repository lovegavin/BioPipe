import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from biopipe_sdk import register_figure, figure_collection
from src.web.service import JobService


def test_same_format_figures_are_independently_addressable_and_contained(tmp_path):
    directory = tmp_path / 'job' / 'output'
    directory.mkdir(parents=True)
    ctx = SimpleNamespace(out_dir=directory)
    reports = []
    for name in ('volcano', 'heatmap'):
        pdf = directory / (name + '.pdf')
        pdf.write_bytes(b'%PDF-' + name.encode())
        reports.append(register_figure(ctx, name, {'pdf': pdf}, title=name.title()))
    report = directory / 'report.json'
    report.write_text(json.dumps(figure_collection(*reports)))
    service = JobService.__new__(JobService)
    service.jobs_dir = tmp_path
    service.export_file = lambda key, index: report
    service._record_path = lambda key, value, summary: Path(value)
    for name in ('volcano', 'heatmap'):
        assert service.figure_file('job', 0, 'pdf', name).name == name + '.pdf'
    with pytest.raises(KeyError):
        service.figure_file('job', 0, 'pdf', 'missing')
    with pytest.raises(ValueError, match='Duplicate'):
        figure_collection(*reports, reports[0])
    outside = tmp_path / 'outside.pdf'
    outside.write_bytes(b'%PDF')
    with pytest.raises(ValueError, match='inside'):
        register_figure(ctx, 'outside', {'pdf': outside})
    report.write_text(json.dumps({'figures': [{'id': 'escape', 'format': 'pdf', 'path': str(outside)}]}))
    with pytest.raises(KeyError):
        service.figure_file('job', 0, 'pdf', 'escape')


def test_figure_id_reaches_remote_transport_and_cache_identity():
    from src.web.remote_service import RemoteManager
    service = RemoteManager.__new__(RemoteManager)
    seen = []
    service._output = lambda *args, **kwargs: seen.append((args, kwargs))
    service.figure_file('job', 1, 'pdf', 'heatmap')
    assert seen[0][1] == {'index': 1, 'format': 'pdf', 'figure_id': 'heatmap'}


def test_metadata_rejects_nonfinite_dimensions(tmp_path):
    path = tmp_path / 'x.svg'; path.write_text('<svg/>')
    for value in (float('nan'), float('inf'), -1, True):
        with pytest.raises(ValueError):
            register_figure(SimpleNamespace(out_dir=tmp_path), 'x', {'svg': path}, width_mm=value)
