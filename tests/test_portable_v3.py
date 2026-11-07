import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import pytest

from operon.portable import check_portable, export_portable
from operon.script_operators import inspect_script


def graph(tmp_path):
    source = tmp_path / 'input.txt'
    source.write_text('portable')
    script = tmp_path / 'copy.py'
    script.write_text('''# input: data file.txt
# output: result file.txt
import argparse
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--in-data')
p.add_argument('--out-result')
a = p.parse_args()
Path(a.out_result).write_text(Path(a.in_data).read_text().upper())
''')
    return {'name': 'Portable copy', 'nodes': [
        {'id': 'data', 'kind': 'source', 'source': {'path': str(source)}, 'position': {'x': 0, 'y': 0}},
        {'id': 'copy', 'kind': 'script', 'script': inspect_script(script), 'position': {'x': 100, 'y': 0}}],
        'edges': [{'id': 'edge', 'source': 'data', 'target': 'copy'}]}


def test_unsupported_native_and_missing_runtime_fail_closed(tmp_path):
    value = graph(tmp_path)
    with pytest.raises(ValueError, match='runtime-dir'):
        export_portable(value, tmp_path / 'export')
    value['nodes'][1] = {'id': 'copy', 'kind': 'operator', 'operator': 'pca', 'position': {'x': 100, 'y': 0}}
    with pytest.raises(ValueError, match='portable implementation'):
        check_portable(value)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows self-contained runtime relocation acceptance')
def test_actual_bundled_runtime_runs_after_relocation_without_operon(tmp_path):
    # Prepare a standard-library-only CPython tree, not a venv or a reference
    # back to the developer interpreter. No scientific dependencies are needed.
    base = Path(sys.base_prefix)
    runtime = tmp_path / 'prepared runtime'
    runtime.mkdir()
    for pattern in ('python.exe', '*.dll', 'LICENSE*'):
        for path in base.glob(pattern):
            shutil.copy2(path, runtime / path.name)
    for directory in ('Lib', 'DLLs'):
        shutil.copytree(base / directory, runtime / directory,
                        ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests'))
    (runtime / 'portable-runtime.json').write_text(json.dumps({'format': 'operon.portable-runtime',
        'schema_version': 1, 'platform': sys.platform, 'machine': platform.machine(), 'python': 'python.exe'}))
    result = export_portable(graph(tmp_path), tmp_path / 'export', runtime_dir=runtime)
    assert result['runtime_bundled']
    moved = tmp_path / 'moved package'
    (tmp_path / 'export').rename(moved)
    runner = moved / 'run.py'
    assert str(tmp_path) not in runner.read_text()
    runner.write_text(runner.read_text().replace(repr('inputs/data/input.txt'), repr(str(tmp_path / 'input.txt'))))
    run = subprocess.run([str(moved / 'runtime/python.exe'), '-I', str(moved / 'run.py')],
                         cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert run.returncode == 0, run.stderr
    assert (moved / 'results/copy/result.txt').read_text() == 'PORTABLE'
    probe = subprocess.run([str(moved / 'runtime/python.exe'), '-I', '-c',
                            "import importlib.util; assert importlib.util.find_spec('operon') is None"],
                           capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
