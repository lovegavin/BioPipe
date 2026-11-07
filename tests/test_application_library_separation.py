"""Independent application/library ownership, without changing v3 entry IDs."""
import json
from pathlib import Path

from operon import packages
from operon.library_location import source_root


def test_application_has_no_operator_implementations_or_manifest():
    root = Path(__file__).resolve().parents[1]
    assert not (root / 'operon/builtin_packages.json').exists()
    for folder in ('src/task/step/steps', 'src/reader/readers'):
        assert {p.name for p in (root / folder).glob('*.py')} == {'__init__.py'}
        assert not list((root / folder).glob('*.parameters.json'))
    assert source_root(root) == root / 'library/seed'


def test_base_service_without_library_has_empty_valid_registry(tmp_path, monkeypatch):
    from operon.plugins import PluginManager
    monkeypatch.setattr('operon.library_location.source_root', lambda root=None: None)
    assert packages.bundled_manifest() == {'protocol_version': 3, 'packages': []}
    state = PluginManager(tmp_path, source_root=None).state()
    assert state['descriptors'] == state['packages'] == []
    assert state['package_protocol_version'] == 3


def test_empty_library_can_start_service_and_render_sdk_figure(tmp_path, monkeypatch):
    monkeypatch.setattr('operon.library_location.source_root', lambda root=None: None)
    from src.web.api import create_app
    from src.web.service import Settings
    from fastapi.testclient import TestClient
    app = create_app(Settings(tmp_path, tmp_path / 'profile', tmp_path / 'frontend', testing=True))
    with TestClient(app) as client:
        assert client.get('/api/bootstrap').status_code == 200
    from types import SimpleNamespace
    from operon_sdk.figures import save_matplotlib
    import matplotlib.pyplot as plt
    context = SimpleNamespace(out_dir=tmp_path, memory=None, step_params={})
    figure, axis = plt.subplots()
    axis.plot([0, 1], [0, 1])
    result = save_matplotlib(context, figure, 'independent.png')
    assert {item['format'] for item in result['figures']} == {'png', 'pdf', 'svg'}


def test_relocated_seed_preserves_entry_points_and_runtime_hashes():
    from operon_sdk.declarations import load_class, implementation_root
    descriptor = next(d for _, d in packages.bundled_entries('operator') if d['id'] == 'pca')
    assert descriptor['entry_point'] == 'src.task.step.steps.pca:PcaStep'
    assert implementation_root(descriptor['entry_point']) == source_root()
    assert load_class(descriptor).name == 'pca'


def test_base_install_does_not_prepare_every_optional_environment(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from operon.remote import install_linux as installer
    monkeypatch.setattr(installer.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    def forbidden(*a, **kw):
        raise AssertionError('base installer attempted optional environment installation')
    monkeypatch.setattr(installer, '_ensure_isolated_environments', forbidden)
    monkeypatch.setattr(installer, '_ensure_python_extras', forbidden)
    assert installer.ensure_requirements([], tmp_path / 'request.txt') == {}


def test_default_changes_leave_application_version_and_source_untouched(tmp_path):
    root = Path(__file__).resolve().parents[1]
    app = (root / 'pyproject.toml').read_bytes()
    library = json.loads((root / 'library/release.json').read_text())
    assert library['version'] != '2.3.0'
    from operon.source_library import seed_sources
    target = tmp_path / 'library'
    seed_sources(root, target)
    params = target / 'src/task/step/steps/pca.parameters.json'
    value = json.loads(params.read_text(encoding='utf-8'))
    value['properties']['n_components']['default'] = 2
    params.write_text(json.dumps(value), encoding='utf-8')
    assert (root / 'pyproject.toml').read_bytes() == app
