"""Verify a packaged Operon runtime and real worker without claiming GUI tests.

Run with the package's runtime/python/python.exe. All runtime state, synthetic
inputs and logs stay in a new evidence directory; the actual user profile and
installation identity are never changed. Exit 0 means every recorded check passed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import traceback
from urllib.request import build_opener, ProxyHandler, Request
from urllib.error import HTTPError
import uuid

ROOT = Path(__file__).resolve().parents[1]
GENERATE = '''# output: table file.csv
import argparse
import csv
rows = 3
p = argparse.ArgumentParser()
p.add_argument('--out-table', required=True)
args = p.parse_args()
with open(args.out_table, 'w', newline='', encoding='utf-8') as handle:
    writer = csv.writer(handle)
    writer.writerow(['value'])
    writer.writerows([value] for value in range(1, rows + 1))
'''
SCALE = '''# input: table file.csv
# output: table file.csv
import argparse
import csv
factor = 2
p = argparse.ArgumentParser()
p.add_argument('--in-table', required=True)
p.add_argument('--out-table', required=True)
args = p.parse_args()
with open(args.in_table, newline='', encoding='utf-8') as source:
    with open(args.out_table, 'w', newline='', encoding='utf-8') as destination:
        writer = csv.writer(destination)
        writer.writerow(['value'])
        for row in csv.DictReader(source):
            writer.writerow([float(row['value']) * factor])
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--work-dir', type=Path, help='New, nonexistent evidence directory')
    parser.add_argument('--version', default='3.0.0')
    parser.add_argument('--prepare-analysis', action='store_true',
                        help='Authorize online route-only dependency preparation and real PCA/plot CLI/MCP acceptance in the temporary profile')
    parser.add_argument('--allow-development', action='store_true', help='Explicitly waive bundled-interpreter/EXE checks for source development')
    args = parser.parse_args(argv)
    report_path = args.report.resolve()
    if report_path.exists():
        parser.error('Report exists; choose a new report path to preserve evidence')
    work = args.work_dir.resolve() if args.work_dir else report_path.parent / ('operon-candidate-' + uuid.uuid4().hex[:12])
    if work.exists():
        parser.error('Work directory must not exist')
    if work.is_relative_to(ROOT):
        parser.error('Evidence must be outside the installation directory')
    work.mkdir(parents=True)
    report = {'product': 'Operon', 'version': args.version, 'status': 'failed', 'checks': [],
              'started': datetime.now(timezone.utc).isoformat(), 'package_root': str(ROOT),
              'python': sys.executable, 'work_dir': str(work),
              'ui_observation': 'Not performed. This verifies a packaged backend and worker, not double-click installation or desktop interactions.'}
    original_environment = dict(os.environ)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))

    def check(name, evidence=True):
        report['checks'].append({'name': name, 'passed': True, 'evidence': evidence})

    try:
        if not args.allow_development:
            assert Path(sys.executable).resolve() == (ROOT / 'runtime/python/python.exe').resolve(), 'Use this package\'s bundled Python'
            assert (ROOT / 'Operon Studio.exe').is_file(), 'Missing Operon Studio.exe'
            manifest = json.loads((ROOT / 'package-manifest.json').read_text(encoding='utf-8'))
            assert manifest['version'] == args.version and manifest['python_bundled'] is True
        check('Selected packaged interpreter', {'bundled': not args.allow_development, 'python': sys.executable})
        runtime_manifest = Path(sys.executable).parent / 'operon-runtime.json'
        runtime_mode = json.loads(runtime_manifest.read_text(encoding='utf-8')).get('mode') if runtime_manifest.is_file() else None
        def analysis_packages():
            import importlib.util
            return [name for name in ('torch', 'pandas', 'scipy', 'matplotlib', 'sklearn', 'biotite', 'pyarrow')
                    if importlib.util.find_spec(name) is not None]
        if runtime_mode == 'management':
            assert not analysis_packages(), 'Scientific dependencies leaked into the management runtime'
            check('Management runtime excludes analysis packages')
        home = work / 'home'
        for relative in ('home', 'temp', 'appdata/local', 'appdata/roaming', 'config'):
            (work / relative).mkdir(parents=True, exist_ok=True)
        for key in list(os.environ):
            if key.upper().startswith(('OPERON_', 'OPERON_', 'PYTHON', 'CONDA')) or key.upper() in {'VIRTUAL_ENV', 'PIP_TARGET', 'PIP_PREFIX'}:
                del os.environ[key]
        os.environ.update(HOME=str(home), USERPROFILE=str(home),
                          LOCALAPPDATA=str(work / 'appdata/local'), APPDATA=str(work / 'appdata/roaming'),
                          XDG_CONFIG_HOME=str(work / 'config'), XDG_CACHE_HOME=str(work / 'cache'),
                          TEMP=str(work / 'temp'), TMP=str(work / 'temp'), TMPDIR=str(work / 'temp'),
                          OPERON_RUNTIME_CONFIG=str(work / 'runtime.json'), OPERON_ADMISSION_DIR=str(work / 'admission'),
                          PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        import operon
        assert operon.__version__ == args.version
        assert Path(operon.__file__).resolve().is_relative_to(ROOT)
        from src.web.profile import resolve_profile
        dummy = work / 'identity-probe'
        dummy.mkdir()
        identity = uuid.uuid4().hex
        (dummy / 'operon-install.json').write_text(json.dumps({'schema_version': 1, 'isolated': True,
                                                              'profile_id': identity, 'product': 'operon'}), encoding='utf-8')
        probe = resolve_profile(dummy, home=home, environ={})
        assert probe.profile_dir == home / '.operon/profiles' / identity
        assert not probe.profile_dir.exists(), 'Profile resolution should be read-only'
        check('Operon isolated profile policy', probe.as_dict())
        frontend = ROOT / 'frontend'
        if not (frontend / 'index.html').is_file():
            frontend = frontend / 'dist'
        assert (frontend / 'index.html').is_file(), 'Packaged frontend missing'
        assert 'Operon' in (frontend / 'index.html').read_text(encoding='utf-8'), 'Frontend title is not branded Operon'
        check('Frontend product title')
        isolated = (ROOT / 'operon-install.json').is_file()
        profile = resolve_profile(ROOT) if isolated else resolve_profile(ROOT, profile_dir=home / '.operon/candidate')
        assert profile.profile_dir.is_relative_to(home)
        command = [sys.executable, '-I', '-X', 'utf8', '-B', str(ROOT / 'scripts/desktop_server.py'),
                   '--frontend', str(frontend), '--wait-for-host']
        if not isolated:
            command += ['--profile-dir', str(profile.profile_dir)]
        from operon.processes import owned_process
        ready = queue.Queue()
        with (work / 'backend.log').open('w', encoding='utf-8') as log:
            with owned_process(command, cwd=ROOT, env=dict(os.environ), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding='utf-8') as child:
                def drain():
                    for line in child.stdout:
                        log.write(line)
                        log.flush()
                        if line.startswith('OPERON_READY '):
                            ready.put(json.loads(line[len('OPERON_READY '):]))
                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                try:
                    child.stdin.write('start\n')
                    child.stdin.flush()
                    deadline = time.monotonic() + 90
                    while True:
                        try:
                            instance = ready.get(timeout=.2)
                            break
                        except queue.Empty:
                            assert child.poll() is None, 'Backend exited before readiness; see backend.log'
                            assert time.monotonic() < deadline, 'Backend readiness timed out; see backend.log'
                    opener = build_opener(ProxyHandler({}))
                    token = None
                    def request(path, payload=None, raw=False, content_type='application/json'):
                        headers = {'X-Studio-Token': token} if token else {}
                        if payload is not None:
                            headers['Content-Type'] = content_type
                            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                        else:
                            body = None
                        with opener.open(Request(instance['url'] + path, data=body, headers=headers), timeout=60) as response:
                            content = response.read()
                        return content if raw else json.loads(content)
                    boot = request('/api/bootstrap')
                    token = boot['token']
                    assert request('/openapi.json')['info']['title'] == 'Operon Studio'
                    assert Path(boot['storage']['profile_dir']).resolve() == profile.profile_dir
                    assert request('/health')['studio'] == args.version
                    check('Packaged API branding and isolated storage', boot['storage'])
                    try:
                        request('/api/workflows/import', b'not a zip archive', content_type='application/zip')
                    except HTTPError as exc:
                        assert exc.code == 422, f'Invalid archive returned HTTP {exc.code}'
                        assert 'Invalid workflow archive' in exc.read().decode('utf-8')
                    else:
                        raise AssertionError('Invalid workflow archive was accepted')
                    assert request('/health')['studio'] == args.version
                    check('Invalid archive is rejected without stopping the service')
                    snapshots = {}
                    for name, code, parameter, default in (('generate', GENERATE, 'rows', 3), ('scale', SCALE, 'factor', 2)):
                        imported = request('/api/scripts/inspect', {'filename': name + '.py', 'code': code})
                        extracted = request('/api/scripts/extract', {'script': imported['script'], 'names': [parameter]})
                        assert extracted['values'][parameter] == default
                        assert extracted['script']['parameters_schema']['properties'][parameter]['default'] == default
                        snapshots[name] = extracted['script']
                    check('Imported literals become independent parameter defaults', {'rows': 3, 'factor': 2})
                    graph = {'name': 'Operon synthetic branch acceptance', 'nodes': [
                        {'id': 'generate', 'kind': 'script', 'script': snapshots['generate'], 'params': {'rows': 4}, 'position': {'x': 0, 'y': 0}},
                        {'id': 'branch_a', 'kind': 'script', 'script': snapshots['scale'], 'params': {'factor': 5}, 'position': {'x': 300, 'y': 0}},
                        {'id': 'branch_b', 'kind': 'script', 'script': snapshots['scale'], 'params': {'factor': 7}, 'position': {'x': 300, 'y': 200}}],
                        'edges': [{'id': 'a', 'source': 'generate', 'target': 'branch_a'},
                                  {'id': 'b', 'source': 'generate', 'target': 'branch_b'}],
                        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32}}
                    frozen = request('/api/workflows/prepare', graph)
                    # Later declaration defaults cannot replace explicit frozen values.
                    updated = deepcopy(frozen)
                    for node in updated['nodes']:
                        for field in node['script']['parameters_schema']['properties'].values():
                            field['default'] = 99
                    updated = request('/api/workflows/prepare', updated)
                    assert [n['params'] for n in updated['nodes']] == [{'rows': 4}, {'factor': 5}, {'factor': 7}]
                    archive = request('/api/workflows/export-yaml', frozen, raw=True)
                    (work / 'workflow.workflow.zip').write_bytes(archive)
                    restored = request('/api/workflows/import', archive, content_type='application/zip')
                    assert [n['params'] for n in restored['nodes']] == [n['params'] for n in frozen['nodes']]
                    assert len(restored['edges']) == 2
                    check('Frozen values and branched YAML archive roundtrip')
                    validation = request('/api/validate', restored)
                    assert validation['readiness']['status'] == 'ready', validation
                    launched = request('/api/jobs', restored)
                    deadline = time.monotonic() + 120
                    while True:
                        job = request('/api/jobs/' + launched['id'])
                        if job['status'] not in {'queued', 'preparing', 'uploading', 'running', 'waiting_connection'}:
                            break
                        assert time.monotonic() < deadline, 'Synthetic job timed out'
                        time.sleep(.2)
                    assert job['status'] == 'complete', job
                    job_directory = profile.data_dir / 'jobs' / launched['id']
                    contents = [p.read_text(encoding='utf-8').replace('\r\n', '\n').strip() for p in job_directory.rglob('table.csv')]
                    assert len(contents) == 3, contents
                    assert 'value\n5.0\n10.0\n15.0\n20.0' in contents
                    assert 'value\n7.0\n14.0\n21.0\n28.0' in contents
                    assert (job_directory / 'parameters.json').is_file()
                    assert list(job_directory.rglob('memory_report.json'))
                    check('Real branched worker and memory/parameter artifacts', {'job_id': launched['id'], 'output_files': 3})
                    (work / 'job.json').write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
                    if args.prepare_analysis:
                        # The flag is an explicit installation permission. The
                        # six-phase helper still requires a separate run scope.
                        from operon.client import instances
                        selected = [item for item in instances(profile.data_dir) if item['pid'] == child.pid]
                        assert len(selected) == 1, 'Cannot identify the owned acceptance backend'
                        command = [sys.executable, '-I', str(ROOT / 'scripts/verify_release_agent.py'), 'backend',
                                   '--code-root', str(ROOT), '--python', sys.executable,
                                   '--workspace', str(profile.workspace), '--instance', selected[0]['instance_id'],
                                   '--evidence', str(work / 'analysis-agent'), '--version', args.version,
                                   '--allow-headless', '--prepare-environment']
                        with (work / 'analysis-agent.log').open('w', encoding='utf-8') as analysis_log:
                            subprocess.run(command, cwd=ROOT, env=dict(os.environ), stdout=analysis_log,
                                           stderr=subprocess.STDOUT, check=True, timeout=1800)
                        analysis = json.loads((work / 'analysis-agent/backend-report.json').read_text(encoding='utf-8'))
                        assert analysis['passed'], analysis
                        check('Explicit dependency preparation and real CLI/MCP PCA/plot run', {'checks': len(analysis['checks'])})
                        # Test the receipt shipped inside this package as well
                        # as source CI. A fresh profile has no historical registry.
                        from src.web.models import Graph
                        from src.web.parameters import export_bundle, split_graph
                        history = json.loads((ROOT / 'operon/bundled_history.json').read_text(encoding='utf-8'))
                        old_pins = {key: entry['implementation'] for entry in history['packages']
                                    if any(release['tag'] == 'v2.6.0' for release in entry['releases'])
                                    for key in entry['operators']}
                        legacy = json.loads((work / 'analysis-agent/prepared-graph.json').read_text(encoding='utf-8'))
                        legacy['plugin_lock'] = {key: old_pins[key] for key in legacy['plugin_lock']}
                        before = split_graph(Graph.model_validate(legacy))[1]
                        archive = export_bundle(Graph.model_validate(legacy))
                        restored = request('/api/workflows/import', archive, content_type='application/zip')
                        prepared = request('/api/workflows/prepare', restored)
                        assert split_graph(Graph.model_validate(prepared))[1] == before
                        launched = request('/api/jobs', restored)
                        deadline = time.monotonic() + 120
                        while True:
                            job = request('/api/jobs/' + launched['id'])
                            if job['status'] not in {'queued', 'preparing', 'uploading', 'running', 'waiting_connection'}:
                                break
                            assert time.monotonic() < deadline, 'Released-pin job timed out'
                            time.sleep(.2)
                        assert job['status'] == 'complete', job
                        assert {item['operator'] for item in job['plugins']['bundled_updates']} == set(legacy['plugin_lock'])
                        check('Released v2.6 pins import and run with frozen values', {'job_id': launched['id']})
                        if runtime_mode == 'management':
                            assert not analysis_packages(), 'Dependency preparation modified the application runtime'
                            check('Application runtime remains analysis-free after preparation')
                finally:
                    started = time.monotonic()
                    if child.poll() is None:
                        try:
                            child.stdin.write('shutdown\n')
                            child.stdin.flush()
                            child.stdin.close()
                        except (BrokenPipeError, OSError):
                            pass
                        child.wait(timeout=15)
                    reader.join(timeout=3)
                    report['backend_exit'] = {'code': child.returncode, 'seconds': round(time.monotonic() - started, 3)}
                    assert child.returncode == 0, 'Backend did not exit normally; see backend.log'
                    assert not reader.is_alive(), 'Backend log pipe remained open'
        check('Backend clean shutdown', report['backend_exit'])
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    finally:
        os.environ.clear()
        os.environ.update(original_environment)
        report['finished'] = datetime.now(timezone.utc).isoformat()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(report_path), 'work_dir': str(work)}, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
