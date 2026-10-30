import json
from pathlib import Path

import pytest
from biopipe.r_runtime import RRuntime
from biopipe_sdk.r_dependencies import validate_r
from biopipe.dependencies import DependencySession
from test_dependencies import Manager

SPEC = {'version': '>=4.3,<5', 'packages': [{'name': 'ggplot2', 'source': 'cran', 'version': '>=3.5'}]}


def test_invalid_r_declarations_rejected_without_loading_code():
    for spec in ({'packages': 'ggplot2'}, {'packages': [{'name': 'x;system()', 'source': 'cran'}]},
                 {'version': 'latest'}, {'bioconductor': 'devel'}, {'shell': 'bad'},
                 {'packages': [{'name': 'x', 'source': 'github'}]}):
        with pytest.raises(ValueError): validate_r(spec)
    assert validate_r(SPEC)['packages'][-1]['name'] == 'jsonlite'


def test_success_receipt_reused_failure_never_published_and_versions_isolated(tmp_path, monkeypatch):
    runtime = RRuntime(tmp_path)
    exe = tmp_path / 'Rscript'; exe.write_text('fixture')
    calls = []
    monkeypatch.setattr(runtime, '_bootstrap', lambda spec: str(exe))
    monkeypatch.setattr(runtime, '_install', lambda *args: calls.append(args[1]))
    monkeypatch.setattr(runtime, '_probe', lambda *args: {'BIOPIPE_R': '4.4.3', 'ggplot2': '3.5.2'})
    first = runtime.ensure(SPEC)
    assert runtime.ensure(SPEC) == first and len(calls) == 1
    changed = {**SPEC, 'packages': [{'name': 'ggplot2', 'source': 'cran', 'version': '<3'}]}
    def fail(*args): raise ValueError('version mismatch')
    monkeypatch.setattr(runtime, '_probe', fail)
    with pytest.raises(ValueError): runtime.ensure(changed)
    assert not (tmp_path / 'receipts' / (runtime.key(changed) + '.json')).exists()
    assert calls[0] != calls[1]
    assert runtime.ensure(SPEC) == first


def test_r_session_pass_cache_and_changed_declaration_invalidation(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    manager.value['descriptors'][0]['resources'] = {'r': SPEC}
    probes = []
    def ensure(self, declaration, **kwargs):
        probes.append((declaration, kwargs))
    monkeypatch.setattr(RRuntime, 'ensure', ensure)
    session = DependencySession(manager, inspector=lambda python, entries, directory: {
        e['id']: {'status': 'passed', 'error': ''} for e in entries})
    session.check(); session.check()
    assert len(probes) == 1
    manager.value['descriptors'][0]['resources']['r'] = {**SPEC, 'version': '>=4.4,<5'}
    session.check()
    assert len(probes) == 2
    assert all(e['status'] == 'passed' for e in session.snapshot()['entries'])


def test_missing_r_cannot_report_passed_and_failure_is_retryable(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    manager.value['descriptors'][0]['resources'] = {'r': SPEC}
    def fail(*args, **kwargs): raise ValueError('R package unavailable')
    monkeypatch.setattr(RRuntime, 'ensure', fail)
    session = DependencySession(manager, inspector=lambda python, entries, directory: {
        e['id']: {'status': 'passed', 'error': ''} for e in entries})
    result = session.check()
    assert result['entries'][0]['status'] == 'failed'
    assert 'R package unavailable' in result['entries'][0]['error']
    monkeypatch.setattr(RRuntime, 'ensure', lambda *args, **kwargs: {})
    assert session.check()['entries'][0]['status'] == 'passed'


def test_run_r_uses_frozen_json_and_records_errors(tmp_path, monkeypatch):
    from biopipe.r_runtime import run_r
    from src.task.context import Context
    monkeypatch.setattr(RRuntime, 'ensure', lambda *args, **kwargs: {
        'executable': 'Rscript', 'library': str(tmp_path), 'versions': {'BIOPIPE_R': '4.4.3'}})
    seen = []
    def call(args, **kwargs):
        request = json.loads(Path(args[-1]).read_text())
        seen.append(request)
        return 'plot complete'
    monkeypatch.setattr('biopipe.r_runtime._call', call)
    ctx = Context(tmp_path, {'sources': {}, 'steps': []})
    try:
        ctx.step_params = {'palette': ['#0072B2', '#D55E00'], 'title': '中文'}
        result = run_r(ctx, SPEC, 'print(params$title)', inputs={'matrix': 'disk.tsv'})
        assert seen[0]['params'] == ctx.step_params
        assert seen[0]['inputs'] == {'matrix': 'disk.tsv'}
        assert (result / 'plot.R').is_file()
        assert ctx.metadata['operator_logs'][-1]['message'] == 'plot complete'
    finally: ctx.finalize()


def test_probe_rejects_actual_version_mismatch(tmp_path, monkeypatch):
    runtime = RRuntime(tmp_path)
    monkeypatch.setattr('biopipe.r_runtime._call', lambda *a, **k: 'BIOPIPE_R\t4.4.3\nggplot2\t2.0.0\njsonlite\t2.0.0\n')
    with pytest.raises(ValueError, match='ggplot2'):
        runtime._probe('Rscript', tmp_path, validate_r(SPEC))


def test_server_can_repair_r_while_python_repair_stays_disabled(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    manager.value['descriptors'][0]['resources'] = {'r': SPEC}
    calls = []
    monkeypatch.setattr(RRuntime, 'ensure', lambda self, spec, **kwargs: calls.append(kwargs))
    def forbidden(*args, **kwargs):
        pytest.fail('Python repair should not run during an R-only server repair')
    monkeypatch.setattr('biopipe.install_targets.repair_entries', forbidden)
    session = DependencySession(manager, inspector=lambda python, entries, directory: {
        e['id']: {'status': 'passed' if e['id'] == 'a' else 'failed', 'error': 'missing Python package'} for e in entries})
    result = session.check(repair=False, repair_r=True)
    assert calls == [{'repair': True, 'verify': True}]
    assert [e['status'] for e in result['entries']] == ['passed', 'failed']


def test_python_installation_receipt_never_certifies_r_packages():
    from biopipe.remote.handshake import installation_readiness
    from biopipe.platforms import systems_status
    entry = {'id': 'plot', 'resources': {'r': SPEC}, 'dependencies': []}
    receipt = installation_readiness([entry], {'plot': {'status': 'passed'}})
    assert 'plot' not in receipt['entries']
    assert systems_status(entry) == 'unknown'
