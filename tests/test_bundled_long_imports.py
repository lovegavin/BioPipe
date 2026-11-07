"""Setup-owned runtimes and -S dependency workers load deep native modules."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from biopipe.bytecode import io_path

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows native import paths')
@pytest.mark.parametrize('worker', [False, True])
def test_deep_native_extension_and_zip_import(tmp_path, worker):
    target = tmp_path / 'native'
    while len(str(target)) < 280:
        target /= 'n' * min(60, 280 - len(str(target)))
    io_path(target).mkdir(parents=True)
    native = Path(importlib.util.find_spec('_queue').origin)
    shutil.copy2(native, io_path(target / native.name))
    archive = tmp_path / 'modules.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('zipped_probe.py', 'value = 42\n')
    probe = ('import _queue,json,zipped_probe; '
             'print(json.dumps({"origin":_queue.__file__,"zip":zipped_probe.value}))')
    if worker:
        io_path(target / 'native_probe.py').write_text(probe)
        config = tmp_path / 'paths.json'
        config.write_text(json.dumps({'paths': [str(target), str(archive)]}))
        args = [str(ROOT / 'biopipe/runtime_bootstrap.py'), str(config), 'native_probe']
    else:
        code = ('import sys; sys.path[:0] = sys.argv[1:3]; '
                'exec(open(sys.argv[3],encoding="utf-8").read()); ' + probe)
        args = ['-c', code, str(target), str(archive), str(ROOT / 'scripts/bundled_paths.pth')]
    completed = subprocess.run([sys.executable, '-I', '-S', *args], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result['zip'] == 42
    assert result['origin'].startswith('\\\\?\\')
    assert str(target) in result['origin']
