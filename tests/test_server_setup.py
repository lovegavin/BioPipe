import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from scripts import install_server as setup


def test_directory_resolution_preserves_unrelated_files_and_reuses_owned_child(tmp_path):
    (tmp_path / 'work.txt').write_text('keep')
    assert setup.destination(tmp_path) == tmp_path / 'Operon'
    (tmp_path / 'Operon').mkdir()
    (tmp_path / 'Operon/notes.txt').write_text('also keep')
    (tmp_path / 'Operon-2').write_text('file collision')
    target = setup.destination(tmp_path)
    assert target == tmp_path / 'Operon-3'
    target.mkdir()
    setup.atomic_json(target / 'operon-install.json', {'owner': setup.OWNER, 'status': 'preparing'})
    assert setup.destination(tmp_path) == target
    assert setup.destination(target) == target
    assert (tmp_path / 'work.txt').read_text() == 'keep'
    assert (tmp_path / 'Operon-2').read_text() == 'file collision'


def test_download_checksum_rejects_corruption(monkeypatch, tmp_path):
    monkeypatch.setattr(setup.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(b'wrong file'))
    with pytest.raises(ValueError, match='Checksum'):
        setup.download('https://example.test/package', tmp_path / 'package.whl', '0' * 64)


def test_publish_failure_restores_previous_launcher_document_and_receipt(tmp_path, monkeypatch):
    (tmp_path / 'bin').mkdir()
    launcher = tmp_path / 'bin/operon'
    launcher.write_text('old launcher')
    setup.atomic_json(tmp_path / 'server.json', {'server_id': 'keep', 'python': '/previous/python'})
    setup.atomic_json(tmp_path / 'operon-install.json', {'owner': setup.OWNER,
        'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()})
    originals = {p: p.read_bytes() for p in [launcher, tmp_path / 'server.json', tmp_path / 'operon-install.json']}
    attempt = tmp_path / 'attempt'; attempt.mkdir()
    original_write = setup.atomic_json
    def failure(path, value):
        if path.name == 'server.json':
            raise PermissionError('simulated write failure')
        return original_write(path, value)
    monkeypatch.setattr(setup, 'atomic_json', failure)
    with pytest.raises(PermissionError):
        setup.publish(tmp_path, attempt, {'server_id': 'new'}, {'owner': setup.OWNER}, 'new launcher')
    assert all(p.read_bytes() == content for p, content in originals.items())
    monkeypatch.setattr(setup, 'atomic_json', original_write)
    setup.publish(tmp_path, attempt, {'server_id': 'keep'}, {'owner': setup.OWNER}, 'new launcher')
    assert launcher.read_text() == 'new launcher'


def test_modified_launcher_is_not_overwritten(tmp_path):
    (tmp_path / 'bin').mkdir(); (tmp_path / 'bin/operon').write_text('user script')
    setup.atomic_json(tmp_path / 'operon-install.json', {'owner': setup.OWNER, 'launcher_sha256': 'old'})
    with pytest.raises(ValueError, match='modified'):
        setup.publish(tmp_path, tmp_path, {}, {}, 'replacement')
    assert (tmp_path / 'bin/operon').read_text() == 'user script'


def test_inherited_python_and_conda_settings_are_not_used(monkeypatch):
    for key in ('PYTHONPATH', 'CONDA_PREFIX', 'BIOPIPE_PYTHON', 'PIP_TARGET', 'VIRTUAL_ENV'):
        monkeypatch.setenv(key, 'old runtime')
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.example:8000')
    environment = setup.child_environment()
    assert not any(key in environment for key in ('PYTHONPATH', 'CONDA_PREFIX', 'BIOPIPE_PYTHON', 'PIP_TARGET', 'VIRTUAL_ENV'))
    assert environment['HTTPS_PROXY'] == 'http://proxy.example:8000'


def test_shell_bootstrap_uses_existing_verified_manager_constants():
    from biopipe.remote.provision import MAMBA_ARCHIVE_SHA, MAMBA_SHA, MAMBA_URL
    shell = Path('scripts/install_server.sh').read_text()
    assert all(value in shell for value in (MAMBA_ARCHIVE_SHA, MAMBA_SHA, MAMBA_URL))


def test_result_save_error_still_prints_machine_readable_installation_status(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(setup, 'install', lambda args: {'status': 'installed', 'install_dir': 'chosen'})
    target = tmp_path / 'result.json'; target.mkdir()
    assert setup.main(['--result', str(target)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'failed' and result['installation_status'] == 'installed'
    assert result['install_dir'] == 'chosen'


@pytest.mark.skipif(sys.platform != 'linux' or not os.environ.get('OPERON_TEST_SERVER_INSTALL'),
                    reason='Explicit clean Linux installation acceptance')
def test_real_server_install_reinstall_cli_and_yaml(tmp_path):
    source = Path(__file__).resolve().parents[1]
    parent = tmp_path / 'chosen directory'; parent.mkdir()
    sentinel = parent / 'research.txt'; sentinel.write_text('keep')
    workspace = tmp_path / 'my analysis data'
    def install(*extra):
        completed = subprocess.run([sys.executable, str(source / 'scripts/install_server.py'),
            '--prefix', str(parent), '--source', str(source), *extra], capture_output=True, text=True, timeout=900)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(completed.stdout)
    first = install('--workspace', str(workspace))
    assert Path(first['install_dir']) == parent / 'Operon'
    command = first['command']
    assert subprocess.run([command, '--version'], capture_output=True).returncode == 0
    import shutil
    project = Path(first['workspace']) / 'example'
    shutil.copytree(source / 'examples/workflows/script_pipeline', project)
    try:
        run = subprocess.run([command, 'run', str(project / 'workflow.yaml'), '--progress', '--brief'],
                             capture_output=True, text=True, timeout=90)
        assert run.returncode == 0, run.stdout + run.stderr
        assert json.loads(run.stdout)['status'] == 'complete'
    finally:
        subprocess.run([command, 'service', 'stop'], check=True, capture_output=True)
    second = install()
    assert second['python'] != first['python']
    assert second['install_dir'] == first['install_dir'] and Path(first['python']).exists()
    assert second['workspace'] == first['workspace'] == str(workspace)
    assert sentinel.read_text() == 'keep'


@pytest.mark.skipif(sys.platform != 'linux' or not os.environ.get('OPERON_TEST_SERVER_BOOTSTRAP'),
                    reason='Explicit Linux installation without a usable Python')
def test_real_server_bootstrap_without_preconfigured_python(tmp_path):
    source = Path(__file__).resolve().parents[1]
    tools = tmp_path / 'tools'; tools.mkdir()
    # Exercise the no-usable-Python entry point without changing the CI host.
    unavailable = tools / 'python3'; unavailable.write_text('#!/bin/sh\nexit 2\n'); unavailable.chmod(0o700)
    environment = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH']}
    result = subprocess.run(['bash', str(source / 'scripts/install_server.sh'), '--source', str(source),
        '--prefix', str(tmp_path / 'server')], env=environment, capture_output=True, text=True, timeout=1200)
    assert result.returncode == 0, result.stdout + result.stderr
    installed = json.loads(result.stdout)
    assert installed['status'] == 'installed'
    assert 'verified Python bootstrap' in result.stderr
    assert subprocess.run([installed['command'], '--version'], capture_output=True).returncode == 0
    python = Path(installed['python'])
    assert python.is_relative_to(tmp_path / 'server')
    # The temporary controller has been removed when the shell exits.
    assert not (python.parent.parent / 'pyvenv.cfg').exists()
