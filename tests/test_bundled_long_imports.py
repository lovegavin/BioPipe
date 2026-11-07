"""Setup-owned runtimes and -S dependency workers load deep native modules."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from operon.bytecode import io_path

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
        args = [str(ROOT / 'operon/runtime_bootstrap.py'), str(config), 'native_probe']
    else:
        code = ('import sys; sys.path[:0] = sys.argv[1:3]; '
                'exec(open(sys.argv[3],encoding="utf-8").read()); ' + probe)
        args = ['-c', code, str(target), str(archive), str(ROOT / 'scripts/bundled_imports.py')]
    completed = subprocess.run([sys.executable, '-I', '-S', *args], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result['zip'] == 42
    assert result['origin'].startswith('\\\\?\\')
    assert str(target) in result['origin']


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows import identity')
def test_short_source_import_keeps_original_identity(tmp_path):
    (tmp_path / 'identity_probe.py').write_text('value = 1\n')
    code = ('import sys; sys.path.insert(0,sys.argv[1]); '
            'exec(open(sys.argv[2],encoding="utf-8").read()); '
            'import identity_probe; print(identity_probe.__file__)')
    result = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(tmp_path),
        str(ROOT / 'scripts/bundled_imports.py')], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == str(tmp_path / 'identity_probe.py')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows package resource paths')
def test_deep_package_resources_keep_module_identity(tmp_path):
    target = tmp_path
    while len(str(target)) < 205:
        target /= 'r' * min(50, 205 - len(str(target)))
    package = target / 'resource_probe'
    io_path(package).mkdir(parents=True)
    io_path(package / '__init__.py').write_text('value = 7\n')
    resource = package / ('schemas' * 9) / 'metaschema.json'
    io_path(resource.parent).mkdir()
    io_path(resource).write_text('{"ready": true}\n')
    assert len(str(package / '__init__.py')) < 260 < len(str(resource))
    code = ('import sys,json; sys.path.insert(0,sys.argv[1]); '
            'exec(open(sys.argv[2],encoding="utf-8").read()); '
            'import resource_probe; from importlib.resources import files; '
            'print(json.dumps({"file":resource_probe.__file__,"data":json.loads('
            'files(resource_probe).joinpath(sys.argv[3],"metaschema.json").read_text())}))')
    result = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(target),
        str(ROOT / 'scripts/bundled_imports.py'), resource.parent.name],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed == {'file': str(package / '__init__.py'), 'data': {'ready': True}}
