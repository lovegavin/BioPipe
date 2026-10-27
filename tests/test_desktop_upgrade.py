import json

import pytest

from biopipe.desktop_upgrade import upgrade_profile
from biopipe.migrate import convert_documents, convert_task
from biopipe.plugins import PluginManager
from src.web.profile import resolve_profile


def test_incomplete_canvas_upgrades_once_with_backup_and_keeps_jobs(tmp_path):
    profile = resolve_profile(tmp_path, profile_dir=tmp_path / 'profile')
    manager = PluginManager(profile.data_dir)
    old = manager.state()
    old['package_protocol_version'] = old['protocol_version'] = 2
    manager.registry.write_text(json.dumps(old), encoding='utf-8')
    graph = {'schema_version': 1, 'name': 'Unfinished', 'nodes': [
        {'id': 'survival', 'kind': 'operator', 'operator': 'kaplan_meier', 'position': {'x': 0, 'y': 0}, 'params': {}}], 'edges': []}
    # Find the operator requiring these labels instead of depending on UI titles.
    descriptor = next(d for d in old['descriptors'] if 'time_label' in d['parameters_schema'].get('required', []))
    graph['nodes'][0]['operator'] = descriptor['id']
    route = profile.data_dir / 'workflows/workspace.json'
    route.parent.mkdir(exist_ok=True)
    route.write_text(json.dumps({'schema_version': 1, 'active_id': 'a', 'documents': [{'id': 'a', 'graph': graph}]}))
    before = route.read_bytes()
    job = profile.data_dir / 'jobs/old/graph.json'
    job.parent.mkdir(parents=True)
    job.write_bytes(before)
    result = upgrade_profile(profile)
    assert result['backup'] and manager.state()['package_protocol_version'] == 3
    assert job.read_bytes() == before
    values = json.loads(route.read_text())['documents'][0]['graph']['nodes'][0]['params']
    assert 'time_label' not in values
    from pathlib import Path
    backup = Path(result['backup'])
    manifest = json.loads((backup / 'manifest.json').read_text())
    entry = next(e for e in manifest['files'] if e['path'] == str(route))
    assert (backup / entry['backup']).read_bytes() == before
    assert upgrade_profile(profile) is None
    with pytest.raises(ValueError, match='required'):
        convert_task({'sources': {}, 'steps': [{'name': descriptor['id'], 'params': {}}]}, old['descriptors'])


def test_draft_upgrade_still_rejects_invalid_supplied_values():
    descriptor = {'id': 'op', 'parameters_schema': {'type': 'object', 'required': ['x'],
                  'properties': {'x': {'type': 'integer', 'minimum': 1}}, 'additionalProperties': False}}
    graph = {'name': 'Draft', 'nodes': [{'id': 'op', 'kind': 'operator', 'operator': 'op', 'params': {'x': -1}}], 'edges': []}
    with pytest.raises(ValueError, match='minimum'):
        convert_documents(graph, [descriptor])


def test_external_legacy_providers_block_automatic_upgrade_without_writes(tmp_path):
    profile = resolve_profile(tmp_path, profile_dir=tmp_path / 'profile')
    manager = PluginManager(profile.data_dir)
    old = manager.state()
    old['package_protocol_version'] = 2
    old['packages'].append({'name': 'authors-provider', 'origin': 'wheel'})
    manager.registry.write_text(json.dumps(old))
    before = manager.registry.read_bytes()
    with pytest.raises(ValueError, match='external providers'):
        upgrade_profile(profile)
    assert manager.registry.read_bytes() == before
    assert not (profile.data_dir / 'migrations/v3').exists()
