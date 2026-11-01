"""Installed distribution acceptance: no editable checkout or desktop assets."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_installed_wheel_runs_headless_worker_without_checkout(tmp_path):
    if importlib.util.find_spec('build') is None:
        pytest.skip('Install the dev extra for wheel acceptance')
    env = dict(os.environ, PYTHONPATH='', PYTHONNOUSERSITE='1', PYTHONUTF8='1',
               PYTHONIOENCODING='utf-8', BIOPIPE_ADMISSION_DIR=str(tmp_path / 'admission'),
               TEMP=str(tmp_path), TMP=str(tmp_path))
    def command(args, cwd=tmp_path, timeout=120):
        result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                                capture_output=True, encoding='utf-8', timeout=timeout)
        assert result.returncode == 0, (result.stdout + '\n' + result.stderr)[-12000:]
        return result.stdout

    output = tmp_path / 'dist'
    command([sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--outdir', output], cwd=ROOT)
    wheel = next(output.glob('*.whl'))
    runtime = tmp_path / 'runtime'
    # Reuse already installed third-party libraries; the BioPipe package itself
    # must come solely from this freshly built wheel in the isolated venv.
    command([sys.executable, '-m', 'venv', '--without-pip', '--system-site-packages', runtime])
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    command([sys.executable, '-m', 'pip', '--python', python, 'install', '--ignore-installed', '--no-deps', '--no-index', wheel])
    probe = json.loads(command([python, '-c',
        'import json,sys,biopipe,biopipe.worker; print(json.dumps({"path":biopipe.__file__,"worker":biopipe.worker.__file__,"sys_path":sys.path}))']))
    assert Path(probe['path']).is_relative_to(runtime)
    assert Path(probe['worker']).is_relative_to(runtime)
    assert all(Path(path or tmp_path).resolve() != ROOT for path in probe['sys_path'])
    installed_root = Path(probe['path']).parent.parent
    assert not (installed_root / 'scripts/run.py').exists()
    assert not (installed_root / 'frontend/dist').exists()

    workspace = tmp_path / 'analysis'; workspace.mkdir()
    (workspace / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    graph = {'schema_version': 2, 'name': 'Installed wheel acceptance', 'base_dir': '.',
             'memory': {'enabled': True, 'budget_mb': 32, 'process_limit_mb': 512, 'chunk_mb': .01,
                        'io_buffer_kb': 4, 'auto_spill': True, 'keep': ['input']},
             'nodes': [{'id': 'input', 'kind': 'source', 'source': {'path': 'input.csv', 'reader': 'CsvReader',
                        'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                       {'id': 'summary', 'kind': 'operator', 'operator': 'describe', 'params': {}}],
             'edges': [{'id': 'edge', 'source': 'input', 'target': 'summary'}]}
    graph_file = workspace / 'graph.json'; graph_file.write_text(json.dumps(graph), encoding='utf-8')
    cli = [python, '-m', 'biopipe', '--workspace', workspace]
    try:
        result = json.loads(command(cli + ['run', graph_file, '--request-id', 'installed-wheel', '--wait', '--timeout', '90']))
        assert result['status'] == 'complete', result.get('error')
        job_dir = workspace / '.studio/jobs' / result['id']
        checked = command([python, '-m', 'biopipe.worker', job_dir, '--check'])
        assert 'CHECK OK' in checked
        report = tmp_path / 'summary.json'
        command(cli + ['artifacts', 'report', result['id'], '0', '--output', report])
        assert json.loads(report.read_text(encoding='utf-8'))['global']['mean'] == 2.5
        assert result['graph']['memory']['auto_spill']
        assert result['report']['artifacts']
        assert json.loads(command(cli + ['sessions'])) == []
    finally:
        # Clean up even when an assertion fails after a detached launch.
        listed = json.loads(command(cli + ['jobs', 'list']))
        active = {'queued', 'preparing', 'running', 'uploading', 'waiting_connection'}
        for job in listed:
            if job['status'] in active:
                command(cli + ['jobs', 'cancel', job['id']])
        deadline = time.monotonic() + 15
        while any(job['status'] in active for job in json.loads(command(cli + ['jobs', 'list']))) and time.monotonic() < deadline:
            time.sleep(.1)
        command(cli + ['service', 'stop'])
        deadline = time.monotonic() + 15
        while json.loads(command(cli + ['service', 'status']))['instances'] and time.monotonic() < deadline:
            time.sleep(.1)
        assert not json.loads(command(cli + ['service', 'status']))['instances']
