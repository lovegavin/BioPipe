"""Server registry reads trust compiled metadata; explicit refresh owns discovery."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from biopipe.plugins import PluginManager
from src.web.models import Graph


def write_operator(root, name='example'):
    definition = {'protocol_version': 3, 'id': 'lab.' + name, 'version': '1.0.0',
                  'kind': 'operator', 'title': name, 'category': 'Plugins',
                  'contracts': {'version': 1, 'inputs': [], 'output': {'mode': 'report'}},
                  'resources': {'memory_modes': ['full'], 'supports_cuda': False},
                  'inputs_arity': 0, 'outputs': [], 'output_parameter': None}
    source = root / 'src/task/step/steps' / (name + '.py')
    source.write_text('from biopipe_sdk import Step\nclass Example(Step):\n'
                      f'    definition = {definition!r}\n'
                      '    provider = "lab-example"\n'
                      '    def run(self, ctx, inputs): pass\n'
                      '    def export(self, ctx): return {"value": 1}\n', encoding='utf-8')
    source.with_suffix('.parameters.json').write_text('{"type": "object"}', encoding='utf-8')
    return source


def publish_manifest(root):
    from biopipe.registry import package_manifest, scan_sources
    records, errors = scan_sources(root)
    assert not errors
    manifest = package_manifest(records, {'packages': []})
    (root / 'biopipe/builtin_packages.json').write_text(json.dumps(manifest), encoding='utf-8')
    return manifest


@pytest.fixture
def source_tree(tmp_path, monkeypatch):
    import biopipe.packages as packages
    root = tmp_path / 'source'
    for folder in ('biopipe', 'src/task/step/steps', 'src/reader/readers'):
        (root / folder).mkdir(parents=True)
    write_operator(root)
    publish_manifest(root)
    monkeypatch.setattr(packages, '__file__', str(root / 'biopipe/packages.py'))
    return root


def forbid_provider_access(guard, source, manager):
    """Allow registry/manifests, never provider paths or declaration rebuilding."""
    import biopipe.dropins
    import biopipe.registry
    import biopipe_sdk.declarations
    roots = [source / 'src', manager.directory / 'packages', manager.directory / 'inbox']
    environments = manager.directory / 'environments'

    def forbidden(*args, **kwargs):
        pytest.fail('routine registry read inspected provider code')

    for operation in ('stat', 'glob', 'iterdir', 'read_text', 'read_bytes', 'open'):
        original = getattr(Path, operation)

        def checked(path, *args, _original=original, **kwargs):
            if (any(path.is_relative_to(root) for root in roots) or
                    path.is_relative_to(environments) and 'code' in path.relative_to(environments).parts):
                forbidden()
            return _original(path, *args, **kwargs)

        guard.setattr(Path, operation, checked)
    guard.setattr(Path, 'rglob', forbidden)
    for name in ('code_hash', 'verify_code', 'verify_archive', 'source_declarations',
                 'compile_declaration', 'load_class'):
        guard.setattr(biopipe_sdk.declarations, name, forbidden)
    guard.setattr(biopipe.registry, 'scan_sources', forbidden)
    guard.setattr(biopipe.dropins, 'source_files', forbidden)


def graph():
    return Graph.model_validate({'nodes': [{'id': 'report', 'kind': 'operator',
        'operator': 'lab.example', 'position': {'x': 0, 'y': 0}}], 'edges': []})


def test_manifest_only_initialization_catalog_and_archived_snapshot_do_not_scan(source_tree, tmp_path, monkeypatch):
    manager = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, manager)
        first = manager.state()
        pinned = manager.pin(graph())
        assert manager.snapshot(pinned)['generation'] == first['generation']
        assert manager.extend_catalog({})['operators'][0]['id'] == 'lab.example'
        assert manager.catalog_for(pinned, {})['plugin_generation'] == first['generation']
        manager.manage('lab-example', 'disable')
        # The archived enabled generation must be resolved without source checks.
        archived = manager.snapshot(pinned)
        assert archived['generation'] == first['generation']
        restored = manager.manage('lab-example', 'restore')
        assert restored['descriptors'][0]['implementation'] == first['descriptors'][0]['implementation']
        assert manager.state()['generation'] == restored['generation']


def test_manifest_only_retains_installed_wheel_metadata_without_inspection(source_tree, tmp_path, monkeypatch):
    manager = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
    state = manager.state()
    wheel = {'name': 'lab-installed', 'version': '1.0.0', 'origin': 'wheel',
             'sha256': '1' * 64, 'enabled': True, 'wheel': 'packages/provider.whl'}
    descriptor = deepcopy(state['descriptors'][0])
    descriptor.update(id='installed.example', entry_point='installed.example:Example',
                      distribution=wheel['name'], origin='wheel', code_sha='2' * 64)
    descriptor['implementation'] = {**descriptor['implementation'], 'package': wheel['name'],
                                    'sha256': wheel['sha256'], 'code_sha': descriptor['code_sha']}
    state['packages'].append(wheel)
    state['descriptors'].append(descriptor)
    state['code_paths'] = ['environments/installed/code']
    manager._publish(state)
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, manager)
        assert manager.state()['descriptors'][-1] == descriptor
        assert len(manager.extend_catalog({})['operators']) == 2
        assert manager.snapshot(graph())['generation'] == state['generation']


def test_source_edits_are_deferred_only_in_manifest_mode(source_tree, tmp_path):
    ordinary = PluginManager(tmp_path / 'desktop', source_root=source_tree)
    server = PluginManager(tmp_path / 'server', source_root=source_tree, manifest_only=True)
    before, indexed = ordinary.state(), server.state()
    source = source_tree / 'src/task/step/steps/example.py'
    source.write_text(source.read_text(encoding='utf-8') + '\n# edited implementation\n', encoding='utf-8')
    assert server.state() == indexed
    after = ordinary.state()
    assert after['generation'] != before['generation']
    assert after['packages'][0]['sha256'] != before['packages'][0]['sha256']
    assert ordinary.manifest_only is False


@pytest.mark.parametrize('enabled', [True, False])
def test_existing_profile_keeps_overlays_and_pins_on_manifest_only_transition(source_tree, tmp_path, monkeypatch, enabled):
    from biopipe_sdk.declarations import declaration_hash
    monkeypatch.setattr('biopipe_sdk.declarations.implementation_root', lambda entry: source_tree)
    ordinary = PluginManager(tmp_path / 'profile', source_root=source_tree)
    descriptor = ordinary.state()['descriptors'][0]
    overlay = deepcopy(descriptor)
    overlay['title'] = 'Saved custom title'
    overlay['parameters_schema'] = {'type': 'object', 'properties': {
        'report_title': {'type': 'string', 'default': 'Saved report default'}}}
    before = ordinary.update_declarations({'protocol_version': 3, 'descriptors': [overlay]})
    pinned = ordinary.pin(graph())
    if not enabled:
        before = ordinary.manage('lab-example', 'disable')
    saved = deepcopy(before['descriptors'][0])
    server = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, server)
        migrated = server.state()
        assert migrated['packages'][0]['manifest_only'] is True
        assert migrated['packages'][0]['enabled'] is enabled
        assert migrated['packages'][0]['sha256'] != before['packages'][0]['sha256']
        assert migrated['descriptors'][0] == saved
        assert server.snapshot(pinned)['descriptors'][0]['code_sha'] == saved['code_sha']
        if enabled:
            assert server.snapshot(pinned)['descriptors'][0] == saved
        restarted = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
        assert restarted.state() == migrated
        assert restarted.snapshot(pinned)['descriptors'][0]['code_sha'] == saved['code_sha']
    # Subsequent canonical manifest changes still replace compiled declarations.
    index = source_tree / 'biopipe/builtin_packages.json'
    manifest = json.loads(index.read_text(encoding='utf-8'))
    shipped = manifest['packages'][0]['descriptors'][0]
    shipped['title'] = 'Updated shipped title'
    shipped['declaration_sha'] = declaration_hash(shipped)
    index.write_text(json.dumps(manifest), encoding='utf-8')
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, server)
        refreshed = server.state()
        assert refreshed['descriptors'][0]['title'] == 'Updated shipped title'
        assert refreshed['packages'][0]['enabled'] is enabled
        assert refreshed['generation'] != migrated['generation']


def test_republished_manifest_updates_generation_and_code_identity(source_tree, tmp_path, monkeypatch):
    manager = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
    before = manager.state()
    source = source_tree / 'src/task/step/steps/example.py'
    source.write_text(source.read_text(encoding='utf-8') + '\n# new implementation\n', encoding='utf-8')
    write_operator(source_tree, 'added')
    manifest = publish_manifest(source_tree)
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, manager)
        after = manager.state()
        assert after['generation'] != before['generation']
        assert {d['id'] for d in after['descriptors']} == {'lab.example', 'lab.added'}
        assert after['packages'][0]['code_sha'] == manifest['packages'][0]['descriptors'][0]['code_sha']
        assert after['packages'][0]['code_sha'] != before['packages'][0]['code_sha']
        assert manager.state()['generation'] == after['generation']


def test_manifest_only_refresh_discovers_added_source_and_publishes_generation(source_tree, tmp_path, monkeypatch):
    manager = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
    before = manager.state()
    shipped = (source_tree / 'biopipe/builtin_packages.json').read_bytes()
    write_operator(source_tree, 'added')
    assert manager.state() == before
    result = manager.refresh()
    after = manager.state()
    assert result['generation'] == after['generation'] != before['generation']
    assert result['updated'] == ['lab-example']
    assert {d['id'] for d in after['descriptors']} == {'lab.example', 'lab.added'}
    assert after['packages'][0]['origin'] == 'wheel'
    assert (source_tree / 'biopipe/builtin_packages.json').read_bytes() == shipped
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, manager)
        assert manager.state()['generation'] == after['generation']
        assert {d['id'] for d in manager.extend_catalog({})['operators']} == {'lab.example', 'lab.added'}


def test_manifest_only_registry_does_not_relax_runtime_code_validation(source_tree, tmp_path, monkeypatch):
    from biopipe_sdk.declarations import load_class
    manager = PluginManager(tmp_path / 'profile', source_root=source_tree, manifest_only=True)
    descriptor = manager.state()['descriptors'][0]
    source = source_tree / 'src/task/step/steps/example.py'
    source.write_text(source.read_text(encoding='utf-8') + '\n# stale compiled manifest\n', encoding='utf-8')
    monkeypatch.setattr('biopipe_sdk.declarations.implementation_root', lambda entry: source_tree)
    with pytest.raises(ValueError, match='Implementation code hash mismatch'):
        load_class(descriptor)


def test_job_service_wires_opt_in_and_retains_desktop_default(source_tree, tmp_path, monkeypatch):
    from src.web.service import JobService, Settings
    project = tmp_path / 'project'
    project.mkdir()
    settings = Settings(project, project / 'profile', project / 'dist', testing=True,
                        manifest_only_registry=True)
    manager = PluginManager(settings.data_dir, source_root=source_tree, manifest_only=True)
    assert Settings(project, project / 'desktop', project / 'dist').manifest_only_registry is False
    with monkeypatch.context() as guard:
        forbid_provider_access(guard, source_tree, manager)
        service = JobService(settings, {})
        try:
            assert service.plugins.manifest_only is True
            assert service.catalog['operators'][0]['id'] == 'lab.example'
            assert service.refresh_catalog() is False
        finally:
            service.shutdown()
