import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import threading
import time

import pytest

from biopipe.remote.client import RemoteError
from biopipe.remote.provision import Shell, source_archive
from src.web.remote_service import ConnectionProfile, RemoteManager

ROOT = Path(__file__).resolve().parents[1]


def test_archive_is_repeatable_and_contains_only_distributable_code(tmp_path):
    for name in ('pyproject.toml', 'README.md', 'requirements-hic-linux.txt'):
        (tmp_path / name).write_text('public')
    (tmp_path / 'scripts').mkdir()
    for name in ('run.py', 'desktop_server.py', 'maintainer_only.py'):
        (tmp_path / 'scripts' / name).write_text('# public source')
    for name in ('src/a.py', 'src/reader/a.parameters.json', 'src/__pycache__/cached.py',
                 '.studio/password.json', '.tmp/test.py', 'dist/user.json', 'src/dataset.csv'):
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('content')
    a = source_archive(tmp_path)
    time.sleep(.01)
    assert source_archive(tmp_path) == a
    with tarfile.open(fileobj=io.BytesIO(a)) as archive:
        assert set(archive.getnames()) == {'pyproject.toml', 'README.md', 'requirements-hic-linux.txt',
            'src/a.py', 'src/reader/a.parameters.json', 'scripts/run.py', 'scripts/desktop_server.py'}
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


def test_deployment_requirements_include_all_current_provider_dependencies():
    from biopipe.remote.install_linux import requirements
    specs, entries = requirements(ROOT)
    assert {'pairtools==1.1.2', 'cooltools==0.7.1', 'pandas==2.2.3'} <= set(specs)
    assert {'build_contacts', 'analyze_contacts', 'align_reads'} <= {d['id'] for d in entries}
    assert all(set(entry.get('dependencies', [])) <= set(specs) for entry in entries)


@pytest.mark.parametrize('broken', [False, True])
def test_installer_repairs_transitive_dependencies_without_reinstalling_healthy_graph(monkeypatch, tmp_path, broken):
    from types import SimpleNamespace
    from biopipe.remote import install_linux as installer
    # Every declared package is present, but a dependency of one may be missing.
    monkeypatch.setattr(installer.metadata, 'version', lambda name: '1.0')
    installs = []
    def run(command, **kwargs):
        if 'check' in command:
            return SimpleNamespace(returncode=int(broken), stdout='parent requires child' if broken else '')
        installs.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(installer.subprocess, 'run', run)
    installer.ensure_requirements(['parent==1.0'], tmp_path/'requirements.txt')
    assert bool(installs) == broken
    if broken:
        request = Path(installs[0][installs[0].index('-r')+1])
        assert request.read_text() == 'parent==1.0\n'


def test_native_bootstrap_does_not_mix_conda_and_pip_scientific_abis(monkeypatch):
    import biopipe.remote.provision as module
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
    assert 'c-compiler' in native and 'samtools=1.22.1' in native
    assert 'cooltools=' not in native and 'numpy=' not in native and 'pandas=' not in native
    assert 'run -p' in script and 'install_linux.py' in script
    assert result['workspace'] == '/home/test/.local/share/biopipe/workspace'
