"""An old/broken profile cannot influence a new Setup-owned installation."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.web.profile import resolve_profile


def identity(root, value='a' * 32):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'biopipe-install.json').write_text(json.dumps({'schema_version': 1, 'isolated': True, 'profile_id': value}))


def test_isolated_profile_ignores_old_profiles_environment_and_cwd(tmp_path, monkeypatch):
    home, install = tmp_path / 'home', tmp_path / 'install'
    old = home / '.biopipe/studio/workspace/.studio/plugins/registry.json'
    old.parent.mkdir(parents=True); old.write_bytes(b'broken old registry')
    identity(install)
    environment = {'BIOPIPE_STUDIO_HOME': str(home / 'old'), 'BIOPIPE_STUDIO_DATA': 'invalid-outside-workspace'}
    before = {p: p.read_bytes() for p in home.rglob('*') if p.is_file()}
    result = resolve_profile(install, home=home, environ=environment)
    monkeypatch.chdir(tmp_path)
    assert resolve_profile(install, home=home, environ=environment) == result
    assert result.profile_dir == home / '.biopipe/profiles' / ('a' * 32)
    assert not result.profile_dir.exists()
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert resolve_profile(install, home=home, environ=environment, profile_dir=result.profile_dir) == result
    # Headless auto-start passes the resolved workspace/data pair explicitly.
    assert resolve_profile(install, home=home, environ=environment, workspace=result.workspace, data_dir=result.data_dir) == result
    with pytest.raises(ValueError, match='own profile'):
        resolve_profile(install, home=home, profile_dir=home / '.biopipe/studio')


def test_reinstall_gets_a_new_identity_without_changing_previous_state(tmp_path):
    identity(tmp_path / 'first', 'a' * 32); identity(tmp_path / 'second', 'b' * 32)
    first = resolve_profile(tmp_path / 'first', home=tmp_path / 'home', environ={})
    second = resolve_profile(tmp_path / 'second', home=tmp_path / 'home', environ={})
    assert first != second
    first.data_dir.mkdir(parents=True)
    original = first.data_dir / 'draft.json'; original.write_bytes(b'precious workflow')
    assert not second.profile_dir.exists() and original.read_bytes() == b'precious workflow'


@pytest.mark.parametrize('profile_id', ['../studio', '', 'A' * 32, 'a' * 31])
def test_invalid_install_identity_fails_closed(tmp_path, profile_id):
    identity(tmp_path, profile_id)
    with pytest.raises(ValueError, match='Invalid isolated'):
        resolve_profile(tmp_path, home=tmp_path / 'home', environ={})


def test_portable_and_development_profiles_remain_compatible(tmp_path):
    assert resolve_profile(tmp_path, home=tmp_path / 'home', environ={}).profile_dir == tmp_path / 'home/.biopipe/studio'


def test_bundled_cli_uses_same_install_identity_and_sanitizes_overrides(tmp_path, monkeypatch):
    from biopipe.installation import configure_environment
    install = tmp_path / 'install'; identity(install)
    python = install / 'runtime/python/python.exe'
    monkeypatch.setattr(sys, 'executable', str(python))
    site = python.parent / 'Lib/site-packages'
    monkeypatch.setenv('BIOPIPE_BASE_PATHS', '["old-target"]')
    monkeypatch.setenv('BIOPIPE_ENVIRONMENTS_ROOT', str(tmp_path / 'old-deps'))
    monkeypatch.setenv('PYTHONPATH', 'old')
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.example:8080')
    # Restore every changed environment variable after this test.
    import os
    for key in list(os.environ) + ['PATH', 'PYTHONNOUSERSITE', 'PIP_CONFIG_FILE']:
        if key in os.environ:
            monkeypatch.setenv(key, os.environ[key])
        else:
            monkeypatch.delenv(key, raising=False)
    assert resolve_profile(site, home=tmp_path/'home', environ={}) == resolve_profile(install, home=tmp_path/'home', environ={})
    configure_environment(site)
    assert 'BIOPIPE_BASE_PATHS' not in os.environ and 'BIOPIPE_ENVIRONMENTS_ROOT' not in os.environ
    assert 'PYTHONPATH' not in os.environ and os.environ['PATH'].startswith(str(python.parent))
    assert os.environ['HTTPS_PROXY'] == 'http://proxy.example:8080'


def test_setup_probe_rejects_nonbundled_python_without_touching_old_profile(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / 'report.json'
    run = subprocess.run([sys.executable, '-I', str(root / 'scripts/install_maintenance.py'), '--report', str(report)],
                         capture_output=True, timeout=40)
    assert run.returncode == 2
    assert json.loads(report.read_bytes())['status'] == 'blocked'


def test_setup_probe_returns_result_without_writing_in_parent_log_directory(tmp_path, monkeypatch, capsys):
    from scripts import install_maintenance as probe
    import biopipe.runtime as runtime
    root = tmp_path / 'install'
    identity(root)
    monkeypatch.setattr(probe, 'ROOT', root)
    monkeypatch.setattr(sys, 'executable', str(root / 'runtime/python/python.exe'))
    monkeypatch.setattr(sys, 'argv', ['install_maintenance.py'])
    monkeypatch.setattr(runtime, 'CORE_MODULES', ())
    monkeypatch.setattr(Path, 'home', lambda: tmp_path / 'home')
    monkeypatch.setattr('src.web.storage.atomic_json', lambda *args: pytest.fail('Child attempted report filesystem write'))
    assert probe.main() == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'ready'
    assert not (tmp_path / 'home').exists()


def test_installed_cli_copy_cannot_publish_runtime_hint(tmp_path, monkeypatch):
    """The wheel in runtime/site-packages shares the desktop install identity."""
    import biopipe.runtime as runtime
    install = tmp_path / 'installed'
    identity(install)
    python = install / 'runtime/python/python.exe'
    monkeypatch.setattr(sys, 'executable', str(python))
    monkeypatch.setattr(runtime, '__file__', str(python.parent / 'Lib/site-packages/biopipe/runtime.py'))
    monkeypatch.setattr(runtime, 'CORE_MODULES', ())
    hint = tmp_path / 'runtime.json'
    assert runtime.remember_runtime(path=hint) is False
    assert not hint.exists()
    identity(install, '../old-profile')
    with pytest.raises(ValueError, match='Invalid isolated'):
        runtime.remember_runtime(path=hint)
    assert not hint.exists()


@pytest.mark.parametrize('existing_hint', [False, True])
def test_isolated_desktop_lifespan_does_not_publish_global_runtime(tmp_path, monkeypatch, existing_hint):
    """Exercise the successful startup path that overwrote portable installs' hint."""
    from fastapi.testclient import TestClient
    from src.web.api import create_app
    from src.web.service import Settings
    import biopipe.runtime as runtime

    # Model a successful bundled-runtime probe, independent of optional test-host deps.
    monkeypatch.setattr(runtime, 'CORE_MODULES', ())
    install = tmp_path / 'install'
    identity(install)
    monkeypatch.setattr(runtime, '__file__', str(install / 'biopipe/runtime.py'))
    hint = tmp_path / 'home/.biopipe/runtime.json'
    original = b'{"schema_version":1,"python":"old-portable-python"}\n'
    if existing_hint:
        hint.parent.mkdir(parents=True)
        hint.write_bytes(original)
    monkeypatch.setenv('BIOPIPE_RUNTIME_CONFIG', str(hint))
    root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / 'workspace'
    settings = Settings(workspace, workspace / '.studio', root / 'frontend/dist',
                        code_root=root, testing=False, desktop=True)
    app = create_app(settings)
    # The regression is startup persistence, not network dependency installation.
    monkeypatch.setattr(app.state, 'check_dependencies', lambda: None)
    with TestClient(app):
        assert hint.exists() is existing_hint
        if existing_hint:
            assert hint.read_bytes() == original
    assert hint.exists() is existing_hint
