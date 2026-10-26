from extension_fixtures import write_extension
"""Real conflicting wheels, real processes, real memory/streaming protocols."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import yaml

from biopipe.dropins import write_wheel
from biopipe.plugins import PluginManager
from biopipe.wire import Wire

ROOT = Path(__file__).resolve().parents[1]


def provider(tmp_path, name, version, body):
    from biopipe.dropins import single_file_wheel
    path = tmp_path / (name + '.py')
    write_extension(path, 'BIOPIPE_PLUGIN = ' + repr({'name': name, 'dependencies': [f'biopipe-test-dependency=={version}']}) + '\n' + body)
    return single_file_wheel(path, tmp_path / 'providers')


REPORT = '''from biopipe_sdk import Step
import biopipe_test_dependency as dep
import os, sys
class Shared(Step):
    name = 'test.shared'
    input_contracts = []
    output_contract = {'mode': 'report'}
    parameters_schema = {'type': 'object'}
    def run(self, ctx, inputs):
        ctx.log('shared version ' + dep.VERSION)
    def export(self, ctx):
        return {'version': dep.VERSION, 'pid': os.getpid(), 'python': sys.executable}
'''

ISOLATED = '''from biopipe_sdk import Step, Form
import biopipe_test_dependency as dep
import os, sys
class Scale(Step):
    name = 'test.scale'
    inputs_arity = 1
    input_contracts = [{'numeric': True}]
    output_contract = {'mode': 'passthrough', 'input': 0}
    output_parameter = 'output'
    parameters_schema = {'type': 'object', 'properties': {'output': {'type': 'string', 'default': 'scaled'}}}
    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 12345, int(inputs[0].data.nbytes)
    def run(self, ctx, inputs):
        f = inputs[0]
        os.write(1, b'native isolation diagnostic')
        ctx[ctx.step_params.get('output', 'test.scale')] = Form(f.data * int(dep.VERSION), f.dims, f.labels, f.info, f.axis_info)
        ctx.log('isolated version ' + dep.VERSION)
    def export(self, ctx):
        return {'version': dep.VERSION, 'pid': os.getpid(), 'python': sys.executable}
'''

STREAM = '''from biopipe_sdk import Step
import biopipe_test_dependency as dep
import os, sys
class Sum(Step):
    name = 'test.sum'
    inputs_arity = 1
    input_contracts = [{'numeric': True}]
    output_contract = {'mode': 'report'}
    parameters_schema = {'type': 'object'}
    supports_streaming = True
    stream_protocol = 'flat-reduction-v1'
    stream_buffer_multiplier = 2
    def run(self, ctx, inputs): raise AssertionError('must stream')
    def run_stream(self, ctx, stream):
        self.total, self.count, self.maximum = 0, 0, 0
        for block in stream['chunks']:
            self.total += float(block.sum(dtype='float64'))
            self.count += 1
            self.maximum = max(self.maximum, block.nbytes)
    def export(self, ctx):
        return {'version': dep.VERSION, 'sum': self.total, 'chunks': self.count, 'max_bytes': self.maximum,
                'pid': os.getpid(), 'python': sys.executable}
'''

READER = '''from biopipe_sdk import Reader, Form
from src.core.contracts import reader_contract
import numpy as np
import biopipe_test_dependency as dep
class DiskReader(Reader):
    name = 'test.reader'
    extensions = ['.isolated']
    parameters_schema = {'type': 'object'}
    output_contract = reader_contract()
    supports_disk_read = True
    disk_protocol = 'dense-writer-v1'
    def probe(self, path, **args):
        a = np.load(path, mmap_mode='r')
        return {'shape': list(a.shape), 'dtype': str(a.dtype), 'dense_bytes': int(a.nbytes), 'preparation_bytes': int(a.nbytes)}
    def read(self, path, dims, labels, **args): raise AssertionError('must read to disk')
    def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
        a = np.load(path, mmap_mode='r')
        for row in range(writer.shape[0]):
            for column in range(0, writer.shape[1], max(1, chunk_bytes // a.dtype.itemsize)):
                writer.write(row, column, a[row, column:column + max(1, chunk_bytes // a.dtype.itemsize)])
        return {'dims': dims, 'labels': {d: {str(i): i for i in range(n)} for d, n in zip(dims, a.shape)},
                'info': {'missing_code': float('nan'), 'dependency': dep.VERSION}, 'axis_info': {}}
'''


@pytest.fixture
def installed(tmp_path, monkeypatch):
    wheelhouse = tmp_path / 'wheels'
    for version in ['1', '2']:
        write_wheel({'biopipe_test_dependency/__init__.py': f'VERSION = "{version}"\n'.encode()},
                    'biopipe-test-dependency', version, [], wheelhouse)
    monkeypatch.setenv('PIP_NO_INDEX', '1')
    monkeypatch.setenv('PIP_FIND_LINKS', str(wheelhouse))
    manager = PluginManager(tmp_path / 'data', source_root=None)
    shared = provider(tmp_path, 'test-shared', '1', REPORT)
    isolated = provider(tmp_path, 'test-isolated', '2', ISOLATED)
    streaming = provider(tmp_path, 'test-stream', '2', STREAM)
    manager.install_many([shared, isolated, streaming])
    return manager


def worker(manager, tmp_path, steps, memory=None):
    tmp_path.mkdir(parents=True)
    data = np.arange(12000, dtype=np.float64).reshape(300, 40)
    np.savetxt(tmp_path / 'input.csv', data, delimiter=',')
    state = manager.state()
    (tmp_path / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    manifest = {'sources': {'X': {'path': 'input.csv', 'dims': ['sample', 'feature'], 'args': {'header': False}}}, 'steps': steps,
                'runtime': {'memory': {'enabled': True, 'budget_mb': 4, 'chunk_mb': .01, **(memory or {})}}}
    (tmp_path / 'task.yaml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
    result = subprocess.run([manager.python_for(state), str(ROOT / 'scripts/run.py'), str(tmp_path)],
                            cwd=ROOT, text=True, encoding='utf-8', capture_output=True, timeout=90)
    summary = json.loads((tmp_path / 'output/run_summary.json').read_text())
    return result, summary, data


def test_conflicts_use_same_python_and_only_conflicting_steps_leave_worker(installed, tmp_path):
    state = installed.state()
    ds = {d['id']: d for d in state['descriptors']}
    assert ds['test.shared']['execution']['mode'] == 'shared'
    assert ds['test.scale']['execution']['mode'] == ds['test.sum']['execution']['mode'] == 'isolated'
    assert 'python' not in state
    assert installed.python_for(state) == sys.executable
    assert 'biopipe_test_dependency' not in sys.modules
    steps = [{'name': 'test.shared', 'inputs': []}, {'name': 'test.scale', 'inputs': ['X'], 'params': {'output': 'Y'}},
             {'name': 'test.sum', 'inputs': ['Y']}, {'name': 'test.sum', 'inputs': ['X']}, {'name': 'test.shared', 'inputs': []}]
    result, summary, data = worker(installed, tmp_path / 'run', steps)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'native isolation diagnostic' in result.stdout
    reports = [json.loads((tmp_path / 'run/output' / s['export_path']).read_text()) for s in summary['steps']]
    assert [r['version'] for r in reports] == ['1', '2', '2', '2', '1']
    assert len({r['python'] for r in reports}) == 1
    assert reports[0]['pid'] == reports[-1]['pid'] != reports[1]['pid']
    assert reports[2]['sum'] == float(data.sum()) * 2
    assert reports[3]['sum'] == float(data.sum())
    assert reports[2]['chunks'] > 1 and reports[2]['max_bytes'] <= .01 * 1024**2
    memory = json.loads(Path(summary['memory_report']).read_text())
    assert memory['plans'][1]['workspace_estimate_bytes'] > data.nbytes + 12345
    assert memory['plans'][2]['mode'] == 'stream'
    assert memory['event_counts']['isolated_finished'] == 4
    assert not list(Path(summary['memory_report']).parent.glob('ipc-*'))


def test_transport_obeys_disk_quota_and_keeps_traceback(installed, tmp_path):
    result, summary, _ = worker(installed, tmp_path / 'quota', [{'name': 'test.scale', 'inputs': ['X']}], {'disk_limit_mb': .01})
    assert result.returncode != 0
    assert summary['status'] == 'failed' and 'quota' in summary['error']
    assert Path(summary['event_log']).stat().st_size > 0
    assert not list(Path(summary['event_log']).parent.glob('ipc-*'))


def test_isolated_disk_reader_stages_larger_than_budget_then_streams(installed, tmp_path):
    reader = provider(tmp_path, 'test-reader', '2', READER)
    installed.install(reader)
    run = tmp_path / 'reader-run'
    run.mkdir()
    data = np.arange(256 * 1024, dtype=np.float64).reshape(256, 1024)
    with (run / 'input.isolated').open('wb') as file:
        np.save(file, data)
    state = installed.state()
    (run / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    manifest = {'sources': {'X': {'path': 'input.isolated', 'dims': ['sample', 'feature']}},
                'steps': [{'name': 'test.sum', 'inputs': ['X']}],
                'runtime': {'memory': {'enabled': True, 'budget_mb': 1, 'chunk_mb': .01}}}
    (run / 'task.yaml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
    result = subprocess.run([installed.python_for(state), str(ROOT / 'scripts/run.py'), str(run)], cwd=ROOT,
                            text=True, encoding='utf-8', capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((run / 'output/run_summary.json').read_text())
    report = json.loads(Path(summary['memory_report']).read_text())
    assert report['event_counts']['source_prepare_complete'] == 1
    assert report['event_counts']['densify_block_spill'] > 0
    assert report['plans'][0]['mode'] == 'stream'
    assert report['managed_peak_bytes'] < report['budget_bytes'] < data.nbytes
    exported = json.loads((run / 'output' / summary['steps'][0]['export_path']).read_text())
    assert exported['sum'] == float(data.sum())


def test_failed_child_preserves_traceback_and_exits(installed, tmp_path):
    bad = provider(tmp_path, 'test-error', '2', REPORT.replace('test.shared', 'test.error').replace("ctx.log('shared version ' + dep.VERSION)", "raise ValueError('isolation-synthetic-failure')"))
    installed.install(bad)
    result, summary, _ = worker(installed, tmp_path / 'error', [{'name': 'test.error', 'inputs': []}])
    assert result.returncode != 0 and 'isolation-synthetic-failure' in summary['error']
    assert 'Traceback' in result.stdout + result.stderr
    events = [json.loads(line) for line in Path(summary['event_log']).read_text(encoding='utf-8').splitlines()]
    import psutil
    child_pids = [e['pid'] for e in events if e.get('event') == 'isolated_started']
    assert child_pids and all(not psutil.pid_exists(pid) for pid in child_pids)


def test_one_source_file_can_keep_compatible_class_shared(installed, tmp_path):
    from biopipe.dropins import single_file_wheel
    source = tmp_path / 'mixed.py'
    shared = REPORT.replace('test.shared', 'test.mixed_shared').replace('class Shared(Step):',
        'class Shared(Step):\n    dependencies = ["biopipe-test-dependency==1"]')
    isolated = ISOLATED.replace('test.scale', 'test.mixed_scale').replace('class Scale(Step):',
        'class Scale(Step):\n    dependencies = ["biopipe-test-dependency==2"]')
    write_extension(source, 'BIOPIPE_PLUGIN = {"name": "test-mixed"}\n' + shared + '\n' + isolated)
    installed.install(single_file_wheel(source, tmp_path / 'mixed-wheel'))
    descriptors = {d['id']: d for d in installed.state()['descriptors']}
    assert descriptors['test.mixed_shared']['execution']['mode'] == 'shared'
    assert descriptors['test.mixed_scale']['execution']['mode'] == 'isolated'
    result, summary, _ = worker(installed, tmp_path / 'mixed-run',
        [{'name': 'test.mixed_shared', 'inputs': []}, {'name': 'test.mixed_scale', 'inputs': ['X']}])
    assert result.returncode == 0, result.stdout + result.stderr
    reports = [json.loads((tmp_path / 'mixed-run/output' / s['export_path']).read_text()) for s in summary['steps']]
    assert [r['version'] for r in reports] == ['1', '2']
    assert reports[0]['pid'] != reports[1]['pid']


def test_session_probes_selected_targets_and_retains_passed_status(installed, monkeypatch):
    from biopipe.dependencies import DependencySession
    from biopipe.targets import inspect_entries
    calls = []
    def inspect(state, entries, directory):
        calls.append([e['id'] for e in entries])
        return inspect_entries(state, entries, directory)
    monkeypatch.setattr('biopipe.targets.inspect_entries', inspect)
    session = DependencySession(installed)
    first = session.check(repair=False)
    assert all(e['status'] == 'passed' for e in first['entries'] if e['id'].startswith('test.'))
    session.check(repair=False)
    assert all(not key.startswith('test.') for call in calls[1:] for key in call)


def test_desktop_cancel_stops_isolated_child_and_preserves_logs(installed, tmp_path):
    import time
    import psutil
    from fastapi.testclient import TestClient
    from src.web.api import create_app
    from src.web.service import Settings
    slow = provider(tmp_path, 'test-slow', '2', REPORT.replace('test.shared', 'test.slow').replace(
        "ctx.log('shared version ' + dep.VERSION)", "ctx.log('child-ready'); __import__('time').sleep(60)"))
    installed.install(slow)
    app = create_app(Settings(tmp_path, installed.directory.parent, ROOT / 'frontend/dist', testing=True, code_root=ROOT))
    with TestClient(app) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/jobs', json={'nodes': [{'id': 'slow', 'kind': 'operator', 'operator': 'test.slow',
                                      'position': {'x': 0, 'y': 0}}], 'edges': []})
        assert response.status_code == 202, response.text
        key = response.json()['id']
        directory = installed.directory.parent / 'jobs' / key
        deadline = time.monotonic() + 20
        pid = None
        while time.monotonic() < deadline:
            for log in directory.glob('output/runs/*/events.jsonl'):
                for line in log.read_text(encoding='utf-8').splitlines():
                    event = json.loads(line)
                    if event['event'] == 'isolated_started' and event['operation'] == 'run':
                        pid = event['pid']
            if pid: break
            time.sleep(.05)
        assert pid and psutil.pid_exists(pid)
        response = client.post(f'/api/jobs/{key}/cancel', json={})
        assert response.status_code == 200 and response.json()['status'] == 'cancelled'
        deadline = time.monotonic() + 10
        while psutil.pid_exists(pid) and time.monotonic() < deadline:
            time.sleep(.05)
        assert not psutil.pid_exists(pid)
        assert (directory / 'console.log').stat().st_size > 0
        assert not list(directory.glob('output/runs/*/ipc-*'))


def test_transitive_conflict_isolated_and_unavailable_package_rolls_back(installed, tmp_path):
    from biopipe.dropins import single_file_wheel
    write_wheel({'biopipe_test_transitive.py': b'VALUE = 2\n'}, 'biopipe-test-transitive', '1',
                ['biopipe-test-dependency==2'], tmp_path / 'wheels')
    source = tmp_path / 'transitive.py'
    write_extension(source, 'BIOPIPE_PLUGIN = {"name": "test-transitive", "dependencies": ["biopipe-test-transitive==1"]}\n'
                      + REPORT.replace('test.shared', 'test.transitive'))
    installed.install(single_file_wheel(source, tmp_path / 'transitive-wheel'))
    state = installed.state()
    assert next(d for d in state['descriptors'] if d['id'] == 'test.transitive')['execution']['mode'] == 'isolated'
    result, summary, _ = worker(installed, tmp_path / 'transitive-run', [{'name': 'test.transitive', 'inputs': []}])
    assert result.returncode == 0, result.stdout + result.stderr
    exported = json.loads((tmp_path / 'transitive-run/output' / summary['steps'][0]['export_path']).read_text())
    assert exported['version'] == '2'
    original = installed.registry.read_bytes()
    source.write_text(source.read_text().replace('biopipe-test-transitive==1', 'biopipe-no-such-test-distribution==0'))
    with pytest.raises(ValueError, match='No matching distribution|Could not find a version'):
        installed.install(single_file_wheel(source, tmp_path / 'missing-wheel'))
    assert installed.registry.read_bytes() == original


def test_forced_cancel_reaps_owned_descendants():
    import psutil
    from biopipe.processes import stop_tree
    process = subprocess.Popen([sys.executable, '-u', '-c',
        'import subprocess,sys,time; child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
        'print(child.pid, flush=True); time.sleep(60)'], stdout=subprocess.PIPE, text=True)
    child_pid = int(process.stdout.readline().strip())
    try:
        stop_tree(process)
        assert process.poll() is not None
        assert not psutil.pid_exists(child_pid)
    finally:
        if process.poll() is None: process.kill()
        if psutil.pid_exists(child_pid): psutil.Process(child_pid).kill()
        process.stdout.close()


def test_wire_preserves_axis_metadata_encoders_and_rejects_unknown_objects(tmp_path):
    from src.core import Form
    from src.reader.readers._encoder import LabelEncoder
    encoder = LabelEncoder()
    encoder.fit_transform(['a', 'b'])
    form = Form(np.arange(2), ['sample'], {'sample': {'a': 0, 'b': 1}},
                {'missing_code': float('nan'), 'group': np.array(['a', 'b']), 'encoders': {'sample': {'group': encoder}},
                 'tuple': (1, 2), 'set': {'x', 'y'}}, {'sample': ['group']})
    wire = Wire(tmp_path)
    wire.write('data.json', form)
    actual = wire.read('data.json')
    actual.validate()
    assert actual.axis_info == form.axis_info
    assert actual.info['tuple'] == (1, 2) and actual.info['set'] == {'x', 'y'}
    assert actual.info['encoders']['sample']['group'].mapping == encoder.mapping
    np.testing.assert_array_equal(actual.info['group'], form.info['group'])
    with pytest.raises(TypeError, match='Unsupported isolated metadata'):
        wire.encode(object())


@pytest.mark.parametrize('group, entry', [('biopipe.operators', 'mixed:Shared\nisolated = mixed:Isolated'), ('biopipe.modules', 'mixed')])
def test_ordinary_wheel_requires_explicit_v3_manifest(tmp_path, group, entry):
    from biopipe.install_targets import wheel_entries
    wheel = write_wheel({
        'mixed.py': b'from biopipe_sdk import Step\nclass Shared(Step):\n dependencies = ["example==1"]\nclass Isolated(Step):\n dependencies = ["example==2"]\n',
        'ordinary-1.dist-info/entry_points.txt': f'[{group}]\nshared = {entry}\n'.encode(),
    }, 'ordinary', '1', ['common>=1'], tmp_path)
    with pytest.raises(ValueError, match='protocol v3 wheel requires biopipe.json'):
        wheel_entries(wheel)
