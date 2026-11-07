import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import threading
import time

import pytest

from operon.remote.client import RemoteError
from operon.remote.provision import Shell, source_archive
from src.web.remote_service import ConnectionProfile, RemoteManager

ROOT = Path(__file__).resolve().parents[1]


def test_archive_is_repeatable_and_contains_only_distributable_code(tmp_path):
    for name in ('pyproject.toml', 'README.md', 'requirements-hic-linux.txt'):
        (tmp_path / name).write_text('public')
    (tmp_path / 'scripts').mkdir()
    for name in ('run.py', 'desktop_server.py', 'maintainer_only.py'):
        (tmp_path / 'scripts' / name).write_text('# public source')
    for name in ('src/a.py', 'src/reader/a.parameters.json', 'src/reader/a.Reader.md', 'src/__pycache__/cached.py',
                 '.studio/password.json', '.tmp/test.py', 'dist/user.json', 'src/dataset.csv'):
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('content')
    a = source_archive(tmp_path)
    time.sleep(.01)
    assert source_archive(tmp_path) == a
    with tarfile.open(fileobj=io.BytesIO(a)) as archive:
        assert all(member.mtime >= 946684800 for member in archive)
        assert set(archive.getnames()) == {'pyproject.toml', 'README.md', 'requirements-hic-linux.txt',
            'src/a.py', 'src/reader/a.parameters.json', 'src/reader/a.Reader.md', 'scripts/run.py', 'scripts/desktop_server.py'}
    (tmp_path / 'scripts/maintainer_only.py').unlink()
    assert source_archive(tmp_path) == a  # Source checkout and desktop archive agree.


def test_managed_profile_needs_no_python_paths_and_keeps_existing_profiles_manual():
    minimal = dict(name='Server', host='example.org', username='researcher', environment='managed')
    assert ConnectionProfile(**minimal).workspace == ''
    with pytest.raises(ValueError): ConnectionProfile(**{**minimal, 'environment': 'existing'})
    for path in ('relative/path', '/tmp/../etc', '/tmp/unsafe\npath'):
        with pytest.raises(ValueError): ConnectionProfile(**minimal, managed_root=path)
    old = {**minimal, 'app_dir': '/opt/code', 'workspace': '/work'}; old.pop('environment')
    assert ConnectionProfile(**old).environment == 'existing'


def test_shell_failure_and_cancel_are_actionable_and_bounded():
    class Channel:
        def sendall(self, command): self.command = command.decode()
    class Connection:
        channel = Channel()
        closed = False
        def _line(self, deadline):
            marker = re.search(r'BP_SETUP_[a-f0-9]+', self.channel.command)[0]
            return marker + ' 12'
        def close(self): self.closed = True
    connection = Connection(); event = threading.Event()
    shell = Shell(connection, lambda line: None, event)
    with pytest.raises(RemoteError, match='环境准备失败'): shell.run('false')
    event.set()
    with pytest.raises(RemoteError, match='取消'): shell.run('true')


def test_setup_status_remains_responsive_while_connect_is_busy(tmp_path):
    from types import SimpleNamespace
    started, release = threading.Event(), threading.Event()
    class Connection:
        connected = True
        info = {'history': [], 'workspace': '/work'}
        def __init__(self, *args): started.set(); release.wait(5)
        def close(self): self.connected = False
    manager = RemoteManager(SimpleNamespace(directory=tmp_path), connection_factory=Connection)
    record = manager.save(dict(name='Test', host='example.org', username='u', environment='managed'))
    errors = []
    def connect():
        try: manager.connect(record['id'], {'password': 'never-write-this'})
        except RemoteError as error: errors.append(error.code)
    thread = threading.Thread(target=connect); thread.start()
    assert started.wait(2)
    assert manager.setup_status(record['id'])['running']
    manager.disconnect(record['id']); release.set(); thread.join(3)
    assert errors == ['remote_cancelled']
    assert not manager.setup_status(record['id'])['running']
    assert not manager.connections
    assert 'never-write-this' not in manager.path.read_text()


def test_deployment_requirements_are_independent_of_optional_library():
    from operon.remote import install_linux as installer
    specs, entries = installer.requirements(ROOT)
    assert {'pairtools==1.1.2', 'cooltools==0.7.1', 'pandas==2.2.3'} <= set(specs)
    assert {'build_contacts', 'analyze_contacts', 'align_reads'} <= {d['id'] for d in entries}
    from packaging.requirements import Requirement
    conda_provided = {name.lower() for name in installer.CONDA_PROVIDED}
    shared = [entry for entry in entries if not (entry.get('resources') or {}).get('environment')]
    isolated = [entry['id'] for entry in entries if (entry.get('resources') or {}).get('environment')]
    assert {'boltz_predict', 'antifold_design', 'esm3_fold'} <= set(isolated)
    assert not any('torch' in spec or 'transformers' in spec for spec in specs)
    assert not any('boltz' in spec or 'antifold' in spec for spec in specs)


@pytest.mark.parametrize('broken', [False, True])
def test_installer_repairs_transitive_dependencies_without_reinstalling_healthy_graph(monkeypatch, tmp_path, broken):
    from types import SimpleNamespace
    from operon.remote import install_linux as installer
    # Every declared package is present, but a dependency of one may be missing.
    monkeypatch.setattr(installer.metadata, 'version', lambda name: '1.0')
    installs = []
    def run(command, **kwargs):
        if 'check' in command:
            return SimpleNamespace(returncode=int(broken), stdout='parent requires child' if broken else '')
        installs.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(installer.subprocess, 'run', run)
    monkeypatch.setattr(installer, '_ensure_python_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_conda_extras', lambda: True)
    monkeypatch.setattr(installer, '_ensure_isolated_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_isolated_environments', lambda *a, **k: True)
    installer.ensure_requirements(['parent==1.0'], tmp_path/'requirements.txt')
    assert bool(installs) == broken
    if broken:
        request = Path(installs[0][installs[0].index('-r')+1])
        assert request.read_text() == 'parent==1.0\n'


def test_native_bootstrap_does_not_mix_conda_and_pip_scientific_abis(monkeypatch):
    import operon.remote.provision as module
    uploaded = {}
    class ScriptShell:
        def __init__(self, *args): pass
        def run(self, command, **kwargs):
            if 'BP_SYSTEM' in command: return 'BP_SYSTEM=Linux\nBP_ARCH=x86_64\nBP_HOME=/home/test'
            return ''
        def upload(self, name, data): uploaded[name] = data
    monkeypatch.setattr(module, 'Shell', ScriptShell)
    monkeypatch.setattr(module, 'source_archive', lambda root: b'synthetic code')
    result = module.provision(None, {}, lambda text: None, threading.Event(), ROOT)
    script = next(data.decode() for name, data in uploaded.items() if name.endswith('.sh'))
    native = next(line for line in script.splitlines() if '"$bp_action"' in line)
    assert '--strict-channel-priority python=3.11 pip bwa=0.7.19 samtools=1.22.1' in native
    assert '"python=3.11 pip' not in native and "'python=3.11 pip" not in native
    assert 'gxx_linux-64' not in native and 'openmm' not in native and 'pdbfixer' not in native
    assert 'cooltools=' not in native and 'numpy=' not in native and 'pandas=' not in native
    assert 'PATH=' in script and 'install_linux.py' in script
    assert '/mnt/c/' not in script and '/mnt/d/' not in script
    assert f"!= '{module.CONDA_SPECS}'" in script
    assert f"printf '%s' '{module.CONDA_SPECS}'" in script
    assert '/bin/micromamba' in script
    assert 'unset CONDA_PREFIX' in script
    assert result['workspace'] == '/home/test/.local/share/operon/workspace'


def test_setup_log_is_created_before_upload_and_reported_on_failure(monkeypatch):
    import operon.remote.provision as module
    commands, uploads, messages = [], [], []
    class ScriptShell:
        def __init__(self, *args): pass
        def run(self, command, **kwargs):
            commands.append(command)
            if 'BP_SYSTEM' in command:
                return 'BP_SYSTEM=Linux\nBP_ARCH=x86_64\nBP_HOME=/home/test'
            if 'bp_setup_pid' in command:
                raise RemoteError('synthetic install failure', code='remote_setup_failed')
            return ''
        def upload(self, path, data):
            uploads.append((path, list(commands)))
    monkeypatch.setattr(module, 'Shell', ScriptShell)
    monkeypatch.setattr(module, 'source_archive', lambda root: b'synthetic code')
    with pytest.raises(RemoteError, match='完整安装日志') as error:
        module.provision(None, {'managed_root': '/custom/server space'}, messages.append, threading.Event(), ROOT)
    log = '/custom/server space/managed-v1/setup-' + hashlib.sha256(b'synthetic code').hexdigest()[:20] + '.log'
    assert error.value.code == 'remote_setup_failed' and log in str(error.value)
    assert any(log in message for message in messages)
    assert any(log in command and 'printf' in command for command in uploads[0][1])
    assert any('tee -a' in command and 'pipefail' in command for command in commands)
    final = next(command for command in commands if 'bp_setup_pid' in command)
    assert " >> '" + log + "'" in final

def test_installer_prefers_mirror_wheels_and_falls_back_to_source(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from operon.remote import install_linux as installer

    monkeypatch.setattr(installer.metadata, 'version', lambda name: '1.0')
    calls = []

    def run(command, **kwargs):
        if 'check' in command:
            return SimpleNamespace(returncode=1, stdout='', stderr='')
        calls.append(list(command))
        if '--only-binary=:all:' in command:
            return SimpleNamespace(returncode=1, stdout='no wheel for pyarrow', stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(installer.subprocess, 'run', run)
    monkeypatch.setattr(installer, '_ensure_python_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_conda_extras', lambda: True)
    monkeypatch.setattr(installer, '_ensure_isolated_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_isolated_environments', lambda *a, **k: True)
    monkeypatch.setattr(installer.shutil, 'which', lambda name: '/opt/env/bin/' + name)
    installer.ensure_requirements(['pyarrow==21.0.0'], tmp_path / 'requirements.txt')
    assert len(calls) == 2
    assert '--only-binary=:all:' in calls[0]
    assert '--only-binary=:all:' not in calls[1]
    for command in calls:
        assert 'https://pypi.tuna.tsinghua.edu.cn/simple' in command
        assert '--trusted-host' in command
    assert 'CC' in (installer.compiler_environment())


def test_cxx_toolchain_is_installed_only_for_source_builds():
    from operon.remote import install_linux as module

    source = Path(module.__file__).read_text()
    assert 'gxx_linux-64' in source
    assert 'cmake' in source and 'make' in source
    assert 'OPERON_MAMBA' in source

def test_installer_skips_conda_only_packages_and_pins_build_fragile_sdists(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from operon.remote import install_linux as installer

    specs, _ = installer.requirements(ROOT)
    assert not any(spec.lower().startswith(('pdbfixer', 'openmm', 'pysam', 'antifold')) for spec in specs)

    monkeypatch.setattr(installer.metadata, 'version', lambda name: '1.0')
    calls = []
    constraints_seen = []

    def run(command, **kwargs):
        if 'check' in command:
            return SimpleNamespace(returncode=1, stdout='', stderr='')
        calls.append(list(command))
        if '--constraint' in command:
            constraints_seen.append(Path(command[command.index('--constraint') + 1]).read_text())
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(installer.subprocess, 'run', run)
    monkeypatch.setattr(installer, '_ensure_python_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_conda_extras', lambda: True)
    monkeypatch.setattr(installer, '_ensure_isolated_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_isolated_environments', lambda *a, **k: True)
    installer.ensure_requirements(['pyarrow>=14'], tmp_path / 'requirements.txt')
    assert len(calls) == 1
    assert 'pyarrow<22' in constraints_seen[0]
    assert 'libcst<1.8' in constraints_seen[0]


def test_installer_source_fallback_prefers_binaries_and_keeps_constraints(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from operon.remote import install_linux as installer

    monkeypatch.setattr(installer.metadata, 'version', lambda name: '1.0')
    calls = []

    def run(command, **kwargs):
        if 'check' in command:
            return SimpleNamespace(returncode=1, stdout='', stderr='')
        calls.append(list(command))
        if '--only-binary=:all:' in command:
            return SimpleNamespace(returncode=1, stdout='no wheel', stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(installer.subprocess, 'run', run)
    monkeypatch.setattr(installer, '_ensure_python_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_conda_extras', lambda: True)
    monkeypatch.setattr(installer, '_ensure_isolated_extras', lambda *a, **k: True)
    monkeypatch.setattr(installer, '_ensure_isolated_environments', lambda *a, **k: True)
    installer.ensure_requirements(['pyarrow>=14'], tmp_path / 'requirements.txt')
    assert len(calls) == 2
    assert '--only-binary=:all:' in calls[0]
    assert '--prefer-binary' in calls[1]
    assert '--only-binary=:all:' not in calls[1]
    for command in calls:
        assert '--constraint' in command

def test_split_failures_keeps_openmm_extras_non_fatal():
    from operon.remote.install_linux import split_failures

    results = {
        'structure_openmm_energy': {'status': 'failed', 'error': "No module named 'openmm'"},
        'structure_md_rmsf': {'status': 'failed', 'error': "No module named 'pdbfixer'"},
        'sequence_net_charge': {'status': 'passed', 'error': ''},
        'structure_rmsd': {'status': 'failed', 'error': 'numpy missing'},
    }
    required, optional = split_failures(results)
    assert list(required) == ['structure_rmsd']
    assert set(optional) == {'structure_openmm_energy', 'structure_md_rmsf'}
